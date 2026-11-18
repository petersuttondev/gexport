from collections.abc import Iterable
from typing import Final

from gexport._export._gi import Gimp
from gexport._export._layout import Point, Region
from gexport._export._util import console, open_duplicate, traverse
from gexport._manifest import Crop, CropContent, CropLayer, CropLayers, Export


def _get_content_region(image: Gimp.Image) -> Region:
    with open_duplicate(image) as flat:
        layer = flat.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        if layer is None:
            raise ValueError("Cannot crop to content. No visible layers")
        flat.select_item(Gimp.ChannelOps.REPLACE, layer)
        _, non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(flat)
    if not non_empty:
        raise ValueError("Cannot crop to content. Image is transparent")
    return Region(x1, y1, x2 - x1, y2 - y1)


def _get_layer_region(image: Gimp.Image, layer_name: str) -> Region:
    layer = image.get_layer_by_name(layer_name)
    if layer is None:
        raise ValueError(f"No layer named {layer_name!r}")
    _, x, y = layer.get_offsets()
    return Region(x, y, layer.get_width(), layer.get_height())


_MIN_SIZE: Final = 1
_MAX_SIZE: Final = 524_288
_MIN_OFFSET: Final = -2_147_483_648
_MAX_OFFSET: Final = 2_147_483_647


def _get_visible_layers_bounding_box(layers: Iterable[Gimp.Layer]) -> Region:
    min_left = min_top = _MAX_OFFSET
    max_right = max_bottom = _MIN_OFFSET
    for layer, _ in traverse(layers, lambda layer: layer.get_visible()):
        if not isinstance(layer, Gimp.GroupLayer):
            _, left, top = layer.get_offsets()
            min_left = min(left, min_left)
            min_top = min(top, min_top)
            max_right = max(left + layer.get_width(), max_right)
            max_bottom = max(top + layer.get_height(), max_bottom)
    if max_right <= min_left or max_bottom <= min_top:
        raise ValueError("No visible layers")
    return Region(min_left, min_top, max_right - min_left, max_bottom - min_top)


def _get_crop_region(image: Gimp.Image, crop: Crop) -> Region:
    match crop:
        case CropContent():
            return _get_content_region(image)
        case CropLayer(name=layer_name):
            return _get_layer_region(image, layer_name)
        case CropLayers():
            return _get_visible_layers_bounding_box(image.get_layers())


def _crop_image(image: Gimp.Image, crop: Crop) -> Point:
    region = Region(0, 0, image.get_width(), image.get_height())
    crop_region = _get_crop_region(image, crop).intersect(region)
    if not image.crop(
        crop_region.w,
        crop_region.h,
        crop_region.x,
        crop_region.y,
    ):
        raise RuntimeError("Crop failed")
    return Point(crop_region.x, crop_region.y)


def _log_crop(image: Gimp.Image, crop: Crop, offset: Point) -> None:
    match crop:
        case CropContent():
            description = "content"
        case CropLayer(name=layer_name):
            description = f"layer [green]{layer_name!r}[/]"
        case CropLayers():
            description = "visible layers"
    w = image.get_width()
    h = image.get_height()
    x, y = offset
    console.print(
        f"Cropped to {description} [cyan]{w}[/]×[cyan]{h}[/]+[cyan]{x}[/]+[cyan]{y}[/]",
        emoji=False,
        highlight=False,
    )


def crop_image(export: Export, image: Gimp.Image) -> Point:
    offset = Point(0, 0)
    for crop in export.crops:
        offset = offset.add(_crop_image(image, crop))
        _log_crop(image, crop, offset)
    return offset
