from abc import ABC
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path
from typing import Final, Protocol, final, override

from gexport import models


@final
@unique
class Action(Enum):
    SHOW = auto()
    HIDE = auto()
    LEAVE = auto()


class Crop(ABC):
    pass


@final
class CropBoundingBox(Crop):
    pass


@final
class CropLayer(Crop):
    def __init__(self, name: str) -> None:
        self.name: Final = name


@final
@dataclass(frozen=True, slots=True)
class Scale:
    factor: float


@final
@dataclass(frozen=True, slots=True)
class ScaleFrom:
    id: str


@final
@dataclass(frozen=True, slots=True)
class WidthHeight:
    width: int | None = None
    height: int | None = None
    allow_scale_up: bool = False

    def __post_init__(self) -> None:
        if self.width is None and self.height is None:
            raise ValueError('Either width or height must be given.')


type Resize = Scale | ScaleFrom | WidthHeight


class SupportsParent(Protocol):
    @property
    def default_action(self) -> Action: ...

    @property
    def default_crop(self) -> Crop | None: ...

    @property
    def default_mask(self) -> Action: ...

    @property
    def default_resize(self) -> Resize | None: ...


@final
class Layer:
    def __init__(
        self,
        parent: SupportsParent,
        action: Action | None = None,
        mask: Action | None = None,
        resize: Resize | None = None,
    ) -> None:
        self.parent = parent
        self._action = action
        self._mask = mask
        self._resize = resize

    @property
    def action(self) -> Action:
        return self._action or self.parent.default_action

    @property
    def mask(self) -> Action:
        return self._mask or self.parent.default_mask


class DefaultsMixin(SupportsParent):
    def __init__(
        self,
        parent: SupportsParent,
        default_action: Action | None = None,
        default_crop: Crop | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        self.parent: Final = parent
        self._default_action: Final = default_action
        self._default_crop: Final = default_crop
        self._default_mask: Final = default_mask
        self._default_resize: Final = default_resize

    @property
    @override
    def default_action(self) -> Action:
        return self._default_action or self.parent.default_action

    @property
    @override
    def default_crop(self) -> Crop | None:
        return self._default_crop or self.parent.default_crop

    @property
    @override
    def default_mask(self) -> Action:
        return self._default_mask or self.parent.default_mask

    @property
    @override
    def default_resize(self) -> Resize | None:
        return (
            self.parent.default_resize
            if self._default_resize is None
            else self._default_resize
        )


@final
class Group(DefaultsMixin, SupportsParent):
    def __init__(
        self,
        parent: SupportsParent,
        default_action: Action | None = None,
        default_crop: Crop | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        super().__init__(
            parent,
            default_action,
            default_crop,
            default_mask,
            default_resize,
        )
        self._default_layer: Final = Layer(self)
        self.layers: Final[dict[str, Layer]] = {}
        self.groups: Final[dict[str, Group]] = {}

    def add_layer(
        self,
        name: str,
        action: Action | None = None,
        mask: Action | None = None,
        resize: Resize | None = None,
    ) -> None:
        self.layers[name] = Layer(self, action=action, mask=mask, resize=resize)

    def add_group(
        self,
        name: str,
        default_action: Action | None = None,
        default_crop: Crop | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> 'Group':
        group = self.groups.get(name)

        if group is not None:
            raise KeyError(f'A group named {name!r} already exists')

        group = Group(
            self,
            default_action=default_action,
            default_crop=default_crop,
            default_mask=default_mask,
            default_resize=default_resize,
        )
        self.groups[name] = group
        return group

    def get_layer(self, path: Iterable[str]) -> Layer:
        head, *tail = path

        if tail:
            group = self.groups.get(head)
            return (
                self._default_layer if group is None else group.get_layer(tail)
            )
        else:
            return self.layers.get(head, self._default_layer)


@final
class Export(DefaultsMixin, SupportsParent):
    def __init__(
        self,
        parent: 'XCF',
        path: Path,
        id: str | None = None,
        default_action: Action | None = None,
        default_crop: Crop | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        super().__init__(
            parent,
            default_action,
            default_crop,
            default_mask,
            default_resize,
        )
        self.xcf: Final = parent
        self._path: Final = path
        self.id: Final = id
        self.root: Final = Group(self, default_action=default_action)

    @property
    def path(self) -> Path:
        stem = self._path.stem.replace('$stem', self.xcf.path.stem)
        return self._path.with_stem(stem)

    @property
    def crop(self) -> Crop | None:
        return self.default_crop

    @property
    def resize(self) -> Resize | None:
        return self.default_resize

    def add_layer(
        self,
        name: str,
        action: Action | None,
        mask: Action | None = None,
        resize: Resize | None = None,
    ) -> None:
        self.root.add_layer(name, action, mask=mask, resize=resize)

    def add_group(self, name: str, default_action: Action | None = None):
        return self.root.add_group(name, default_action=default_action)

    def get_layer(self, path: Iterable[str]):
        return self.root.get_layer(path)


@final
class XCF(DefaultsMixin, SupportsParent):
    def __init__(
        self,
        parent: SupportsParent,
        path: Path,
        default_action: Action | None = None,
        default_crop: Crop | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        super().__init__(
            parent,
            default_action,
            default_crop,
            default_mask,
            default_resize,
        )
        self.path = path
        self.exports: dict[Path, Export] = {}

    def add_export(
        self,
        path: Path,
        id: str | None = None,
        default_action: Action | None = None,
        default_crop: Crop | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> Export:
        export = Export(
            self,
            path,
            id=id,
            default_action=default_action,
            default_crop=default_crop,
            default_mask=default_mask,
            default_resize=default_resize,
        )

        self.exports[path] = export
        return export


@final
class Schema:
    def __init__(
        self,
        database_path: Path,
        default_action: Action = Action.LEAVE,
        default_crop: Crop | None = None,
        default_mask: Action = Action.LEAVE,
        default_resize: Resize | None = None,
    ) -> None:
        self.database_path = database_path
        self.default_crop = default_crop
        self.default_action = default_action
        self.default_mask = default_mask
        self.default_resize = default_resize
        self.xcfs: dict[Path, XCF] = {}

    def add_xcf(
        self,
        path: Path,
        default_action: Action | None = None,
        default_crop: Crop | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> XCF:
        xcf = XCF(
            self,
            path,
            default_action=default_action,
            default_crop=default_crop,
            default_mask=default_mask,
            default_resize=default_resize,
        )
        self.xcfs[xcf.path] = xcf
        return xcf

    def get_export_by_id(self, id_: str) -> Export:
        for xcf in self.xcfs.values():
            for export in xcf.exports.values():
                if export.id == id_:
                    return export
        raise ValueError(f'No export with ID {id_!r}')


def create_action_from_model(
    action_model: models.Action | None,
) -> Action | None:
    match action_model:
        case models.Action.SHOW:
            return Action.SHOW
        case models.Action.HIDE:
            return Action.HIDE
        case models.Action.LEAVE:
            return Action.LEAVE
        case None:
            return None


def add_actions_from_model(
    group: Group,
    group_model: list[models.Group | models.Layer | str]
    | models.Group
    | models.Layer
    | str
    | None,
    action: Action,
) -> None:
    match group_model:
        case list():
            for layer_model in group_model:
                add_actions_from_model(group, layer_model, action)

        case models.Group():
            group.add_layer(group_model.group, action)
            child_group = group.add_group(
                group_model.group,
                default_action=create_action_from_model(group_model.default),
            )
            add_actions_from_model(child_group, group_model.show, Action.SHOW)
            add_actions_from_model(child_group, group_model.hide, Action.HIDE)
            add_actions_from_model(child_group, group_model.leave, Action.LEAVE)

        case models.Layer(layer=name, mask=mask):
            group.add_layer(
                name,
                action=action,
                mask=create_action_from_model(mask),
            )

        case str():
            group.add_layer(group_model, action)

        case None:
            pass


def create_crop_from_model(
    model: models.CropAlgorithm | str | None,
) -> Crop | None:
    match model:
        case models.CropAlgorithm():
            return CropBoundingBox()
        case str() as name:
            return CropLayer(name)
        case None:
            return None


def create_resize_from_model(
    model: models.ScaleFrom | models.WidthHeight | float | None,
) -> Resize | None:
    match model:
        case models.ScaleFrom(scale_from=id_):
            return ScaleFrom(id_)
        case models.WidthHeight(
            width=width,
            height=height,
            allow_scale_up=allow_scale_up,
        ):
            return WidthHeight(
                width,
                height,
                allow_scale_up=allow_scale_up or False,
            )
        case float():
            return Scale(model)
        case int():
            raise TypeError
        case None:
            return None


def _expand_export_path(
    root_dir: Path, xcf_path: Path, export_path: Path
) -> Path:
    return (
        Path(xcf_path.parent, *export_path.parts[1:])
        if export_path.parts[0] == '$parent'
        else root_dir / export_path
    )


def add_export_from_model(
    root_dir: Path,
    xcf: XCF,
    export_path: Path,
    export_model: models.Export,
) -> Export:
    export = xcf.add_export(
        _expand_export_path(root_dir, xcf.path, export_path),
        id=export_model.id,
        default_action=create_action_from_model(export_model.default),
        default_crop=create_crop_from_model(export_model.crop),
        default_resize=create_resize_from_model(export_model.resize),
    )

    add_actions_from_model(export.root, export_model.show, Action.SHOW)
    add_actions_from_model(export.root, export_model.hide, Action.HIDE)
    add_actions_from_model(export.root, export_model.leave, Action.LEAVE)
    return export


def add_xcf_from_model(
    root_dir: Path,
    schema: Schema,
    xcf_path: Path,
    xcf_model: models.XCF,
) -> XCF:
    xcf = schema.add_xcf(
        root_dir / xcf_path,
        default_action=create_action_from_model(xcf_model.default),
        default_resize=create_resize_from_model(xcf_model.resize),
    )

    exports_model = xcf_model.exports

    def add_export_from_path(export_path: Path) -> None:
        xcf.add_export(_expand_export_path(root_dir, xcf.path, export_path))

    match exports_model:
        case dict():
            for export_path, export_model in exports_model.items():
                add_export_from_model(root_dir, xcf, export_path, export_model)
        case list():
            for export_path in exports_model:
                add_export_from_path(export_path)
        case Path() as export_path:
            add_export_from_path(export_path)
        case None:
            pass

    return xcf


def create_schema_from_model(
    schema_path: Path,
    schema_model: models.Schema,
) -> Schema:
    root_dir = schema_path.resolve(strict=True).parent

    schema = Schema(
        root_dir / schema_model.database,
        default_crop=create_crop_from_model(schema_model.crop),
        default_resize=create_resize_from_model(schema_model.resize),
    )

    if schema_model.xcfs is not None:
        for xcf_path, xcf_model in schema_model.xcfs.items():
            add_xcf_from_model(root_dir, schema, xcf_path, xcf_model)

    return schema


def load_schema(path: Path) -> Schema:
    schema = create_schema_from_model(path, models.load_schema(path))
    export_ids: set[str] = set()
    for xcf in schema.xcfs.values():
        for export in xcf.exports.values():
            if export.id is not None:
                if export.id in export_ids:
                    raise ValueError(f'Duplicate export ID {export.id!r}')
                export_ids.add(export.id)
    return schema
