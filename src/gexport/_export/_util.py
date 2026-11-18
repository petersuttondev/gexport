from collections.abc import Callable, Generator, Iterable, Sequence
from contextlib import contextmanager
from pathlib import Path

from gexport._export._gi import Gimp, Gio


@contextmanager
def open_image(path: Path) -> Generator[Gimp.Image]:
    image = Gimp.file_load(
        Gimp.RunMode.NONINTERACTIVE,
        Gio.File.new_for_path(str(path)),
    )

    if image is None:
        raise OSError(f"Cannot open {path}")

    try:
        yield image
    finally:
        image.delete()


@contextmanager
def open_duplicate(image: Gimp.Image) -> Generator[Gimp.Image]:
    duplicate = image.duplicate()
    try:
        yield duplicate
    finally:
        duplicate.delete()


def rasterize_all_visible_vector_layers(image: Gimp.Image) -> None:
    for layer, _ in traverse(
        image.get_layers(), include=lambda layer: layer.get_visible()
    ):
        if isinstance(layer, Gimp.VectorLayer) and not layer.is_rasterized():  # noqa: SIM102
            if not layer.rasterize():
                raise RuntimeError(f"Failed to rasterize {layer.get_name()!r}")


def _traverse(
    layers: Iterable[Gimp.Item],
    include: Callable[[Gimp.Layer], bool],
    path: list[str],
) -> Iterable[tuple[Gimp.Layer, Sequence[str]]]:
    for layer in layers:
        if not isinstance(layer, Gimp.Layer):
            raise TypeError()
        if include(layer):
            path.append(layer.get_name())
            yield layer, path
            if isinstance(layer, Gimp.GroupLayer):
                yield from _traverse(layer.get_children(), include, path)
            path.pop()


def traverse(
    layers: Iterable[Gimp.Layer],
    include: Callable[[Gimp.Layer], bool] = lambda _: True,
):
    return _traverse(layers, include, [])
