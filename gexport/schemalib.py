from abc import ABC
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path
from typing import Final, Protocol, final

from gexport import models


@final
@unique
class Action(Enum):
    SHOW = auto()
    HIDE = auto()
    LEAVE = auto()


@final
@dataclass(frozen=True, slots=True)
class Scale:
    factor: float


@final
@dataclass(frozen=True, slots=True)
class WidthHeight:
    width: int | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        if self.width is None and self.height is None:
            raise ValueError('Either width or height must be given.')


type Resize = Scale | WidthHeight


class SupportsParent(Protocol):
    @property
    def default_action(self) -> Action: ...

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

    @property
    def resize(self) -> Resize | None:
        return (
            self.parent.default_resize if self._resize is None else self._resize
        )


class DefaultsMixin(SupportsParent):
    def __init__(
        self,
        parent: SupportsParent,
        default_action: Action | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        self.parent = parent
        self._default_action = default_action
        self._default_mask = default_mask
        self._default_resize = default_resize

    @property
    def default_action(self) -> Action:
        return self._default_action or self.parent.default_action

    @property
    def default_mask(self) -> Action:
        return self._default_mask or self.parent.default_mask

    @property
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
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        super().__init__(parent, default_action, default_mask, default_resize)
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
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> 'Group':
        group = self.groups.get(name)

        if group is not None:
            raise KeyError(f'A group named {name!r} already exists')

        group = Group(
            self,
            default_action=default_action,
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
class Export(DefaultsMixin, SupportsParent):
    def __init__(
        self,
        parent: SupportsParent,
        path: Path,
        crop: Crop | None = None,
        default_action: Action | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        super().__init__(parent, default_action, default_mask, default_resize)
        self.path: Final = path
        self.crop: Final = crop
        self.root: Final = Group(self, default_action=default_action)

    @property
    def resize(self) -> Resize | None:
        resize = self.default_resize
        return self.parent.default_resize if resize is None else resize

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
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> None:
        super().__init__(parent, default_action, default_mask, default_resize)
        self.path = path
        self.exports: dict[Path, Export] = {}

    def add_export(
        self,
        path: Path,
        crop: Crop | None = None,
        default_action: Action | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> Export:
        asset = Export(
            self,
            path,
            crop=crop,
            default_action=default_action,
            default_mask=default_mask,
            default_resize=default_resize,
        )

        self.exports[path] = asset
        return asset


@final
class Schema:
    def __init__(
        self,
        database_path: Path,
        default_action: Action = Action.LEAVE,
        default_mask: Action = Action.LEAVE,
        default_resize: Resize | None = None,
    ) -> None:
        self.database_path = database_path
        self.default_action = default_action
        self.default_mask = default_mask
        self.default_resize = default_resize
        self.xcfs: dict[Path, XCF] = {}

    def add_xcf(
        self,
        path: Path,
        default_action: Action | None = None,
        default_mask: Action | None = None,
        default_resize: Resize | None = None,
    ) -> XCF:
        xcf = XCF(
            self,
            path,
            default_action=default_action,
            default_mask=default_mask,
            default_resize=default_resize,
        )
        self.xcfs[xcf.path] = xcf
        return xcf


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


def create_resize_from_model(
    model: models.WidthHeight | float | None,
) -> Resize | None:
    match model:
        case float():
            return Scale(model)
        case models.WidthHeight(width=width, height=height):
            return WidthHeight(width, height)
        case None:
            return None


def add_export_from_model(
    root_dir: Path,
    xcf: XCF,
    export_path: Path,
    export_model: models.Export,
) -> Export:
    crop: Crop | None

    match export_model.crop:
        case models.CropAlgorithem():
            crop = CropBoundingBox()
        case str() as name:
            crop = CropLayer(name)
        case None:
            crop = None

    export = xcf.add_export(
        root_dir / export_path,
        crop=crop,
        default_action=create_action_from_model(export_model.default),
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

    if xcf_model.exports is not None:
        for export_path, export_model in xcf_model.exports.items():
            add_export_from_model(root_dir, xcf, export_path, export_model)

    return xcf


def create_schema_from_model(
    schema_path: Path,
    schema_model: models.Schema,
) -> Schema:
    root_dir = schema_path.resolve(strict=True).parent

    schema = Schema(
        root_dir / schema_model.database,
        default_resize=create_resize_from_model(schema_model.resize),
    )

    if schema_model.xcfs is not None:
        for xcf_path, xcf_model in schema_model.xcfs.items():
            add_xcf_from_model(root_dir, schema, xcf_path, xcf_model)

    return schema


def load_schema(path: Path) -> Schema:
    return create_schema_from_model(path, models.load_schema(path))
