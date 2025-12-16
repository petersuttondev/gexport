import builtins
from collections.abc import Callable, Generator, Iterable, Sequence
from contextlib import contextmanager
from pathlib import Path
import sys
from types import TracebackType
from typing import cast

import gi

gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
from gi.repository import Gio


def check_bool(object: object) -> bool:
    if isinstance(object, bool):
        return object
    raise TypeError(
        f'expected object to be a bool, got {type(object).__name__!r}',
    )


def check_path(object: object) -> Path:
    if isinstance(object, Path):
        return object
    raise TypeError(
        f'expected object to be a Path, got {type(object).__name__!r}',
    )


def check_str_list(object: object) -> list[str]:
    if not isinstance(object, list):
        raise TypeError(
            f'expected object to a list, got {type(object).__name__!r}',
        )
    for i, item in enumerate(cast(list[builtins.object], object)):
        if not isinstance(item, str):
            raise TypeError(
                f'expected object[{i}] to be a str, got {type(item).__name__!r}',
            )
    return cast(list[str], object)


def suppress_unhandled(*exceptions: type[BaseException]) -> None:
    prev_excepthook = sys.excepthook

    def excepthook(
        type: type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if not isinstance(value, exceptions):
            prev_excepthook(type, value, traceback)

    sys.excepthook = excepthook


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


@contextmanager
def open_image(path: Path) -> Generator[Gimp.Image]:
    image = Gimp.file_load(
        Gimp.RunMode.NONINTERACTIVE,
        Gio.File.new_for_path(str(path)),
    )

    if image is None:
        raise IOError(f'Cannot open {path}')

    try:
        yield image
    finally:
        image.delete()


@contextmanager
def open_image_duplicate(image: Gimp.Image) -> Generator[Gimp.Image]:
    duplicate = image.duplicate()
    try:
        yield duplicate
    finally:
        duplicate.delete()
