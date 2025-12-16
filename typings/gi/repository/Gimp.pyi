from enum import Enum as _Enum
from typing import Final as _Final
from gi.repository import Gio as _Gio


class _GetOffsetsResult(tuple[bool, int, int]):
    offset_x: _Final[int]
    offset_y: _Final[int]


class Drawable(Item):
    def get_height(self) -> int:
        ...

    def get_offsets(self) -> _GetOffsetsResult:
        ...

    def get_width(self) -> int:
        ...


class GroupLayer(Layer):
    ...


class MergeType(_Enum):
    EXPAND_AS_NECESSARY = 0
    CLIP_TO_IMAGE = 1
    CLIP_TO_BOTTOM_LAYER = 2
    FLATTEN_IMAGE = 3


class Image:
    def autocrop(self, drawble: Drawable | None = None) -> bool:
        ...

    def crop(
        self,
        new_width: int,
        new_height: int,
        offx: int,
        offy: int,
    ) -> bool:
        ...

    def delete(self) -> bool:
        ...

    def duplicate(self) -> Image:
        ...

    def get_layer_by_name(self, name: str) -> Layer | None:
        ...

    def get_layers(self) -> list[Layer]:
        ...

    def get_height(self) -> int:
        ...

    def get_name(self) -> str:
        ...

    def get_width(self) -> int:
        ...

    def merge_visible_layers(self, merge_type: MergeType) -> Layer:
        ...

    def scale(self, new_width: int, new_height: int) -> bool:
        ...

    def undo_group_end(self) -> bool:
        ...

    def undo_group_start(self) -> bool:
        ...


class Item:
    def get_children(self) -> list[Item]:
        ...

    def get_name(self) -> str:
        ...

    def get_visible(self) -> bool:
        ...

    def set_visible(self, visible: bool) -> None:
        ...


class Layer(Drawable):
    def get_apply_mask(self) -> bool:
        ...

    def set_apply_mask(self, apply_mask: bool) -> bool:
        ...


class PDB:
    def lookup_procedure(self, procedure_name: str) -> Procedure | None:
        ...


class Procedure:
    ...


class RunMode(_Enum):
    NONINTERACTIVE = ...


@staticmethod
def file_load(run_mode: RunMode, file: _Gio.File) -> Image | None:
    ...


@staticmethod
def file_save(
    run_mode: RunMode,
    image: Image,
    file: _Gio.File,
    options: None,
) -> bool:
    ...


@staticmethod
def get_images() -> list[Image]:
    ...


@staticmethod
def get_pdb() -> PDB | None:
    ...
