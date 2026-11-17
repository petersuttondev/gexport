import graphlib
import json
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple, cast, final

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp, Gio  # pyright: ignore[reportMissingModuleSource]
from rich.console import Console

from gexport._manifest import (
    Action,
    CropContent,
    CropLayer,
    CropLayers,
    Export,
    Group,
    Scale,
    ScaleFrom,
    WidthHeight,
    load_manifest,
)
from gexport.databaselib import open_database
from gexport.util import open_image, open_image_duplicate, traverse

console: Final = Console()

# -- Validation -------------------------------------------------------------- #


def _validate_group(group: Group, image: Gimp.Image) -> None:
    for name in group.layers:
        if image.get_layer_by_name(name) is None:
            raise ValueError(f"No layer named {name!r}")
    for child_group in group.groups.values():
        _validate_group(child_group, image)


def _validate_origin(export: Export, image: Gimp.Image) -> None:
    origin = export.origin
    if origin is not None and image.get_layer_by_name(origin) is None:
        raise ValueError(f"Cannot find origin layer {export.origin!r}")


def validate(export: Export, image: Gimp.Image):
    _validate_group(export.root, image)
    _validate_origin(export, image)


# ---------------------------------------------------------------------------- #


@final
class _BoundingBox(NamedTuple):
    width: int
    height: int
    x_offset: int
    y_offset: int


@final
class _Offsets(NamedTuple):
    x: int
    y: int


def _get_crop_content_bbox(image: Gimp.Image) -> _BoundingBox:
    with open_image_duplicate(image) as flat:
        layer = flat.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        if layer is None:
            raise ValueError("Cannot crop to content. No visible layers")
        flat.select_item(Gimp.ChannelOps.REPLACE, layer)
        _, non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(flat)
    if not non_empty:
        raise ValueError("Cannot crop to content. Image is transparent")
    return _BoundingBox(width=x2 - x1, height=y2 - y1, x_offset=x1, y_offset=y1)


def _get_crop_layer_bbox(image: Gimp.Image, layer_name: str) -> _BoundingBox:
    layer = image.get_layer_by_name(layer_name)

    if layer is None:
        raise ValueError(
            f"Failed to get crop_to layer. No layer named {layer_name!r}",
        )

    _, x_offset, y_offset = layer.get_offsets()

    return _BoundingBox(
        layer.get_width(),
        layer.get_height(),
        max(x_offset, 0),
        max(y_offset, 0),
    )


def _get_crop_layers_bbox(
    image: Gimp.Image,
    layers: Iterable[Gimp.Layer],
) -> _BoundingBox:
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
        raise ValueError("Cannot find bounding box")
    min_left = max(min_left, 0)
    min_top = max(min_top, 0)
    max_right = min(max_right, max_width)
    max_bottom = min(max_bottom, max_height)
    return _BoundingBox(
        width=max_right - min_left,
        height=max_bottom - min_top,
        x_offset=min_left,
        y_offset=min_top,
    )


def _crop(export: Export, image: Gimp.Image) -> _Offsets:
    match export.crop:
        case CropContent():
            crop_name = "content"
            bbox = _get_crop_content_bbox(image)
        case CropLayer(name=crop_name):
            bbox = _get_crop_layer_bbox(image, crop_name)
        case CropLayers():
            crop_name = "layers"
            bbox = _get_crop_layers_bbox(image, image.get_layers())
        case None:
            crop_name = "none"
            bbox = None

    if export.origin is None:
        origin = (0, 0)
    else:
        origin_layer = image.get_layer_by_name(export.origin)
        assert origin_layer is not None
        _, x_origin, y_origin = origin_layer.get_offsets()
        origin = max(x_origin, 0), max(y_origin, 0)

    if bbox is None:
        offsets = _Offsets(-origin[0], -origin[1])
    else:
        offsets = _Offsets(bbox.x_offset - origin[0], bbox.y_offset - origin[1])
        print(
            f"Cropping to {crop_name}: {bbox.width}x{bbox.height}+{bbox.x_offset}+{bbox.y_offset}",
        )
        image.crop(*bbox)

    return offsets


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class ExportLayout:
    width: Final[int]
    height: Final[int]
    x_offset: Final[int]
    y_offset: Final[int]
    x_scale: Final[float]
    y_scale: Final[float]


@final
class _Span(NamedTuple):
    length: int
    offset: int


def _scale_span(factor: float, length: int, offset: int) -> _Span:
    start = round(factor * offset)
    end = round(factor * (length + offset))
    return _Span(end - start, start)


def _log_scale(
    scaled_image: Gimp.Image,
    offsets: _Offsets,
    x_factor: float,
    y_factor: float,
) -> None:
    w = scaled_image.get_width()
    h = scaled_image.get_height()
    x, y = offsets
    print(f"Scaled to {w}x{h}+{x}+{y} (x{x_factor}, x{y_factor})")


def _scale(
    image: Gimp.Image,
    x_factor: float,
    y_factor: float,
    offsets: _Offsets,
    width: int | None = None,
    height: int | None = None,
) -> _Offsets:
    x_span = _scale_span(x_factor, image.get_width(), offsets.x)
    y_span = _scale_span(y_factor, image.get_height(), offsets.y)
    # A requested width or height is exact. Spans can be off by one when the
    # scaled offset lands on .5
    if not image.scale(
        x_span.length if width is None else width,
        y_span.length if height is None else height,
    ):
        raise RuntimeError("Scale failed")
    offsets = _Offsets(x_span.offset, y_span.offset)
    _log_scale(image, offsets, x_factor, y_factor)
    return offsets


def _save_webp(image: Gimp.Image, path: Path) -> None:
    pdb = Gimp.get_pdb()
    assert pdb is not None
    proc = pdb.lookup_procedure("file-webp-export")
    assert proc is not None
    config = proc.create_config()
    config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    config.set_property("image", image)
    config.set_property("file", Gio.File.new_for_path(str(path)))
    config.set_property("options", None)
    config.set_property("lossless", False)
    config.set_property("quality", 90.0)
    config.set_property("alpha-quality", 100.0)
    # Sharp YUV ignores alpha, so it puts a saturated halo on hard edges next to
    # transparent areas (e.g. orange on a brown wall). It may help at hard
    # edges between saturated colours but makes little visual difference in
    # low-saturation photos and increases file size roughly 5%.
    config.set_property("use-sharp-yuv", False)
    config.set_property("include-color-profile", False)
    config.set_property("include-exif", False)
    config.set_property("include-iptc", False)
    config.set_property("include-thumbnail", False)
    config.set_property("include-xmp", False)
    result = proc.run(config)
    if result.index(0) != Gimp.PDBStatusType.SUCCESS:
        raise RuntimeError(f"Export failed: {path}")


def _save_generic(image: Gimp.Image, path: Path) -> None:
    Gimp.file_save(
        run_mode=Gimp.RunMode.NONINTERACTIVE,
        image=image,
        file=Gio.File.new_for_path(str(path)),
        options=None,
    )


def _save(image: Gimp.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    match path.suffix.lower():
        case ".webp":
            save = _save_webp
        case _:
            save = _save_generic
    save(image, path)


def _create_export(
    image: Gimp.Image,
    export: Export,
    get_scale_factor: Callable[[str], tuple[float, float]],
) -> ExportLayout:
    layers = image.get_layers()

    for layer, layer_path in traverse(layers):
        layer_actions = export.get_layer(layer_path)

        match layer_actions.action:
            case Action.SHOW:
                color = "green"
                layer.set_visible(True)
            case Action.HIDE:
                color = "red"
                layer.set_visible(False)
            case Action.LEAVE:
                color = "dim"

        match layer_actions.mask:
            case Action.SHOW:
                mask = " (masked)"
                layer.set_apply_mask(True)
            case Action.HIDE:
                mask = ""
                layer.set_apply_mask(False)
            case Action.LEAVE:
                mask = " (masked)" if layer.get_apply_mask() else ""

        path = " → ".join(layer_path)
        console.print(f"[{color}]{path}{mask}[/{color}]")

    offsets = _crop(export, image)
    cropped_width = image.get_width()
    cropped_height = image.get_height()

    match export.resize:
        case Scale(factor):
            x_factor = y_factor = factor
            offsets = _scale(image, factor, factor, offsets)

        case ScaleFrom(id_):
            x_factor, y_factor = get_scale_factor(id_)
            offsets = _scale(image, x_factor, y_factor, offsets)

        case WidthHeight(width, height, allow_scale_up):
            assert width is not None or height is not None
            if width is None:
                assert height is not None
                x_factor = y_factor = height / image.get_height()
            elif height is None:
                x_factor = y_factor = width / image.get_width()
            else:
                x_factor = width / image.get_width()
                y_factor = height / image.get_height()
            if (x_factor < 1 and y_factor < 1) or allow_scale_up:
                offsets = _scale(
                    image, x_factor, y_factor, offsets, width, height
                )

        case None:
            pass

    # Save the scale the image actually got, not the requested factor. Rounding
    # the size changes it, e.g. 2026px at x0.355457 becomes 720px, x0.355380,
    # and scale_from exports must line up with the image as exported
    layout = ExportLayout(
        width=image.get_width(),
        height=image.get_height(),
        x_offset=offsets[0],
        y_offset=offsets[1],
        x_scale=image.get_width() / cropped_width,
        y_scale=image.get_height() / cropped_height,
    )

    # The WebP plugin's flattening leaves the clip backdrop's colour in
    # transparent pixels. Enabling Sharp YUV leaks this colour into edges.
    # Erase backdrop colour by flatten ourselves.
    if image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE) is None:
        console.print("[yellow]Warning: exporting empty image[/]")

    _save(image, export.path)
    return layout


def run() -> None:
    manifest_path = Path(os.environ["GEXPORT_MANIFEST"])
    manifest = load_manifest(Path(manifest_path))

    if "GEXPORT_SUBSTRINGS" in os.environ:
        json_substrings = cast(
            list[str], json.loads(os.environ["GEXPORT_SUBSTRINGS"])
        )
        substrings = tuple(json_substrings)
    else:
        substrings = ()

    if substrings:

        def should_export(path: Path) -> bool:
            path_str = str(path)
            return any(substring in path_str for substring in substrings)

    else:

        def should_export(path: Path) -> bool:
            del path
            return True

    export_paths: list[str] = []

    with open_database(manifest.database_path) as db:

        def get_scale(id_: str) -> tuple[float, float]:
            return db.get_scale(manifest.get_export_by_id(id_).path)

        for xcf in manifest.xcfs.values():
            graph: dict[Export, set[Export]] = {
                export: set() for export in xcf.exports.values()
            }
            for export in xcf.exports.values():
                if isinstance(export.resize, ScaleFrom):
                    graph[export].add(
                        manifest.get_export_by_id(export.resize.id)
                    )
            exports = graphlib.TopologicalSorter(graph).static_order()
            with open_image(xcf.path) as image:
                for export in exports:
                    if should_export(export.path):
                        validate(export, image)
                        print("Exporting", export.path)
                        export_paths.append(str(export.path))
                        with open_image_duplicate(image) as duplicate:
                            layout = _create_export(
                                duplicate, export, get_scale
                            )
                            db.save_export(
                                export.path,
                                layout.width,
                                layout.height,
                                layout.x_offset,
                                layout.y_offset,
                                layout.x_scale,
                                layout.y_scale,
                            )
                        print()

    results_path = os.environ.get("GEXPORT_RESULTS")

    if results_path is not None:
        with open(results_path, "w") as results_file:
            json.dump(export_paths, results_file)
