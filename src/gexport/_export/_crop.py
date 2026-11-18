from collections.abc import Iterable

from gexport._export._gi import Gimp
from gexport._export._layout import BoundingBox, Offsets
from gexport._export._util import open_duplicate, traverse
from gexport._manifest import CropContent, CropLayer, CropLayers, Export


def _get_crop_content_bbox(image: Gimp.Image) -> BoundingBox:
    with open_duplicate(image) as flat:
        layer = flat.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        if layer is None:
            raise ValueError("Cannot crop to content. No visible layers")
        flat.select_item(Gimp.ChannelOps.REPLACE, layer)
        _, non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(flat)
    if not non_empty:
        raise ValueError("Cannot crop to content. Image is transparent")
    return BoundingBox(width=x2 - x1, height=y2 - y1, x_offset=x1, y_offset=y1)


def _get_crop_layer_bbox(image: Gimp.Image, layer_name: str) -> BoundingBox:
    layer = image.get_layer_by_name(layer_name)
    if layer is None:
        raise ValueError(
            f"Failed to get crop_to layer. No layer named {layer_name!r}",
        )
    _, x_offset, y_offset = layer.get_offsets()
    return BoundingBox(
        layer.get_width(),
        layer.get_height(),
        max(x_offset, 0),
        max(y_offset, 0),
    )


def _get_crop_layers_bbox(
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
        raise ValueError("Cannot find bounding box")
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


def crop(export: Export, image: Gimp.Image) -> Offsets:
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
        offsets = Offsets(-origin[0], -origin[1])
    else:
        offsets = Offsets(bbox.x_offset - origin[0], bbox.y_offset - origin[1])
        print(
            f"Cropping to {crop_name}: {bbox.width}x{bbox.height}+{bbox.x_offset}+{bbox.y_offset}",
        )
        image.crop(*bbox)

    return offsets
