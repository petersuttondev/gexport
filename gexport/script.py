from collections.abc import Iterable
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Final, NamedTuple, final

import gi

gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
from gi.repository import Gio
from rich.console import Console

from gexport.databaselib import open_database
from gexport.schemalib import (
    Action,
    CropBoundingBox,
    CropLayer,
    Export,
    Group,
    Scale,
    WidthHeight,
    load_schema,
)
from gexport.util import open_image, open_image_duplicate, traverse


console: Final = Console()


def validate_group(group: Group, image: Gimp.Image):
    for name in group.layers:
        if image.get_layer_by_name(name) is None:
            raise ValueError(f'No layer named {name!r}')

    for child_group in group.groups.values():
        validate_group(child_group, image)


def validate(export: Export, image: Gimp.Image):
    validate_group(export.root, image)


@final
class BoundingBox(NamedTuple):
    width: int
    height: int
    x_offset: int
    y_offset: int


def get_bounding_box(
    image: Gimp.Image,
    layers: Iterable[Gimp.Layer],
) -> BoundingBox:
    min_left = max_width = image.get_width()
    min_top = max_height = image.get_height()
    max_right = max_bottom = 0

    for layer, _ in traverse(layers, lambda layer: layer.get_visible()):
        if not isinstance(layer, Gimp.GroupLayer):
            _, left, top = layer.get_offsets()
            min_left = min(left, min_left)
            min_top = min(top, min_top)
            max_right = max(left + layer.get_width(), max_right)
            max_bottom = max(top + layer.get_height(), max_bottom)

    if max_right < min_left or max_bottom < min_top:
        raise ValueError('Cannot find bounding box')

    min_left = max(min_left, 0)
    min_top = max(min_top, 0)
    max_right = min(max_right, max_width)
    max_bottom = min(max_bottom, max_height)

    return BoundingBox(
        width=max_right - min_left,
        height=max_bottom - min_top,
        x_offset=min_left,
        y_offset=min_top,
    )


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class ExportMetadata:
    width: Final[int]
    height: Final[int]
    x_offset: Final[int]
    y_offset: Final[int]


def create_export(image: Gimp.Image, export: Export) -> ExportMetadata:
    layers = image.get_layers()

    for layer, layer_path in traverse(layers):
        layer_actions = export.get_layer(layer_path)

        match layer_actions.action:
            case Action.SHOW:
                color = 'green'
                layer.set_visible(True)
            case Action.HIDE:
                color = 'red'
                layer.set_visible(False)
            case Action.LEAVE:
                color = 'dim'

        match layer_actions.mask:
            case Action.SHOW:
                mask = ' (masked)'
                layer.set_apply_mask(True)
            case Action.HIDE:
                mask = ''
                layer.set_apply_mask(False)
            case Action.LEAVE:
                mask = ' (masked)' if layer.get_apply_mask() else ''

        path = ' → '.join(layer_path)
        console.print(f'[{color}]{path}{mask}[/{color}]')

    bbox: BoundingBox | None

    match export.crop:
        case CropBoundingBox():
            crop_name = 'bounding box'
            bbox = get_bounding_box(image, image.get_layers())

        case CropLayer(name=name):
            layer = image.get_layer_by_name(name)

            if layer is None:
                raise ValueError(
                    f'Failed to get crop_to layer. No layer named {name!r}',
                )

            crop_name = name

            _, x_offset, y_offset = layer.get_offsets()

            bbox = BoundingBox(
                layer.get_width(),
                layer.get_height(),
                max(x_offset, 0),
                max(y_offset, 0),
            )
        case None:
            crop_name = 'none'
            bbox = None

        case _:
            raise ValueError('Unhandled crop type')

    if bbox is None:
        offsets = (0, 0)
    else:
        offsets = (bbox.x_offset, bbox.y_offset)
        print(
            f'Cropping to {crop_name}: {bbox.width}x{bbox.height}+{bbox.x_offset}+{bbox.y_offset}',
        )
        image.crop(*bbox)

    match export.resize:
        case Scale(factor):
            if not image.scale(
                round(factor * image.get_width()),
                round(factor * image.get_height()),
            ):
                raise RuntimeError('Scale failed')

            offsets = (round(factor * offsets[0]), round(factor * offsets[1]))
            print(
                f'Scaled to {image.get_width()}x{image.get_height()}+{offsets[0]}+{offsets[1]} (x{factor})'
            )

        case WidthHeight(width, height):
            assert width is not None or height is not None
            if width is None:
                x_factor = y_factor = height / image.get_height()
                width = round(x_factor * image.get_width())
            elif height is None:
                x_factor = y_factor = width / image.get_width()
                height = round(y_factor * image.get_height())
            else:
                x_factor = width / image.get_width()
                y_factor = height / image.get_height()
            if not image.scale(width, height):
                raise RuntimeError('Resize failed')
            offsets = (
                round(x_factor * offsets[0]),
                round(y_factor * offsets[1]),
            )
            print(
                f'Scaled to {image.get_width()}x{image.get_height()}+{offsets[0]}+{offsets[1]} ({x_factor}, {y_factor})',
            )

    metadata = ExportMetadata(
        width=image.get_width(),
        height=image.get_height(),
        x_offset=offsets[0],
        y_offset=offsets[1],
    )

    export.path.parent.mkdir(parents=True, exist_ok=True)

    Gimp.file_save(
        run_mode=Gimp.RunMode.NONINTERACTIVE,
        image=image,
        file=Gio.File.new_for_path(str(export.path)),
        options=None,
    )

    return metadata


def run() -> None:
    dump_path = os.environ.get('GEXPORT_DUMP')

    if dump_path is not None:
        from gexport import dump

        dump.run(Path(dump_path))
        return

    schema_path = Path(os.environ['GEXPORT_SCHEMA'])
    schema = load_schema(Path(schema_path))

    if 'GEXPORT_SUBSTRINGS' in os.environ:
        substrings = tuple(json.loads(os.environ['GEXPORT_SUBSTRINGS']))
    else:
        substrings = ()

    if substrings:

        def should_export(path: Path) -> bool:
            path_str = str(path)
            return any(substring in path_str for substring in substrings)

    else:

        def should_export(path: Path) -> bool:
            return True

    export_paths: list[str] = []

    with open_database(schema.database_path) as db:
        for xcf in schema.xcfs.values():
            with open_image(xcf.path) as image:
                for export in xcf.exports.values():
                    if should_export(export.path):
                        validate(export, image)
                        print('Exporting', export.path)
                        export_paths.append(str(export.path))
                        with open_image_duplicate(image) as duplicate:
                            metadata = create_export(duplicate, export)
                            db.save_export(
                                export.path,
                                metadata.width,
                                metadata.height,
                                metadata.x_offset,
                                metadata.y_offset,
                            )
                        print()

    results_path = os.environ.get('GEXPORT_RESULTS')

    if results_path is not None:
        with open(results_path, 'w') as results_file:
            json.dump(export_paths, results_file)
