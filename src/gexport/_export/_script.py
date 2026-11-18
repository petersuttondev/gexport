import graphlib
from collections.abc import Callable
from pathlib import Path

from gexport._export._crop import crop_image
from gexport._export._gi import Gimp
from gexport._export._ipc import load_export_request, write_export_response
from gexport._export._layout import Layout, Point, Span
from gexport._export._save import save_image
from gexport._export._util import (
    console,
    open_duplicate,
    open_image,
    rasterize_all_visible_vector_layers,
    traverse,
)
from gexport._manifest import (
    Action,
    Export,
    Group,
    Scale,
    ScaleFrom,
    WidthHeight,
    load_manifest,
)
from gexport.databaselib import open_database

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


def _scale_span(factor: float, length: int, offset: int) -> Span:
    start = round(factor * offset)
    end = round(factor * (length + offset))
    return Span(end - start, start)


def _log_scale(
    scaled_image: Gimp.Image,
    offset: Point,
    x_factor: float,
    y_factor: float,
) -> None:
    w = scaled_image.get_width()
    h = scaled_image.get_height()
    x, y = offset
    print(f"Scaled to {w}x{h}+{x}+{y} (x{x_factor}, x{y_factor})")


def _scale(
    image: Gimp.Image,
    x_factor: float,
    y_factor: float,
    offset: Point,
    width: int | None = None,
    height: int | None = None,
) -> Point:
    x_span = _scale_span(x_factor, image.get_width(), offset.x)
    y_span = _scale_span(y_factor, image.get_height(), offset.y)
    # A requested width or height is exact. Spans can be off by one when the
    # scaled offset lands on .5
    if not image.scale(
        x_span.length if width is None else width,
        y_span.length if height is None else height,
    ):
        raise RuntimeError("Scale failed")
    offset = Point(x_span.offset, y_span.offset)
    _log_scale(image, offset, x_factor, y_factor)
    return offset


def _create_export(
    image: Gimp.Image,
    export: Export,
    working_dir: Path,
    get_scale_factor: Callable[[str], tuple[float, float]],
) -> Layout:
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

    if export.origin is None:
        origin = Point(0, 0)
    else:
        origin_layer = image.get_layer_by_name(export.origin)
        assert origin_layer is not None
        _, x_origin, y_origin = origin_layer.get_offsets()
        origin = Point(x_origin, y_origin)

    # GIMP 3.2.8 mishandles vector layers when cropping and scaling.
    rasterize_all_visible_vector_layers(image)
    offset = crop_image(export, image)
    offset = Point(offset.x - origin.x, offset.y - origin.y)
    cropped_width = image.get_width()
    cropped_height = image.get_height()

    match export.resize:
        case Scale(factor):
            x_factor = y_factor = factor
            offset = _scale(image, factor, factor, offset)

        case ScaleFrom(id_):
            x_factor, y_factor = get_scale_factor(id_)
            offset = _scale(image, x_factor, y_factor, offset)

        case WidthHeight(width, height, allow_scale_up):
            assert width is not None or height is not None
            if width is None:
                assert height is not None
                x_factor = y_factor = height / cropped_height
            elif height is None:
                x_factor = y_factor = width / cropped_width
            else:
                x_factor = width / cropped_width
                y_factor = height / cropped_height
            if (x_factor < 1 and y_factor < 1) or allow_scale_up:
                offset = _scale(
                    image, x_factor, y_factor, offset, width, height
                )

        case None:
            pass

    # Save the scale the image actually got, not the requested factor. Rounding
    # the size changes it, e.g. 2026px at x0.355457 becomes 720px, x0.355380,
    # and scale_from exports must line up with the image as exported
    layout = Layout(
        width=image.get_width(),
        height=image.get_height(),
        x_offset=offset.x,
        y_offset=offset.y,
        x_scale=image.get_width() / cropped_width,
        y_scale=image.get_height() / cropped_height,
    )

    # The WebP plugin's flattening leaves the clip backdrop's colour in
    # transparent pixels. Enabling Sharp YUV leaks this colour into edges.
    # Erase backdrop colour by flatten ourselves.
    if image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE) is None:
        console.print("[yellow]Warning: exporting empty image[/]")

    save_image(image, export.path, working_dir)
    return layout


def run() -> None:
    request = load_export_request()
    manifest = load_manifest(request.manifest_path)
    substrings = request.substrings

    if substrings:

        def should_export(path: Path) -> bool:
            path_str = str(path)
            return any(substring in path_str for substring in substrings)

    else:

        def should_export(path: Path) -> bool:
            del path
            return True

    export_paths: list[Path] = []
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
                        export_paths.append(export.path)
                        with open_duplicate(image) as duplicate:
                            layout = _create_export(
                                duplicate,
                                export,
                                request.working_dir,
                                get_scale,
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

    write_export_response(export_paths, request.working_dir)
