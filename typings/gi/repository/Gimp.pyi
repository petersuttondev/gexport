from typing import Final as _Final
from gi.repository import Gio as _Gio
from gi.repository import GObject as _GObject


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


class ExportOptions(_GObject.Object):
    ...


class GroupLayer(Layer):
    ...


class MergeType(_GObject.GEnum):
    EXPAND_AS_NECESSARY = 0
    CLIP_TO_IMAGE = 1
    CLIP_TO_BOTTOM_LAYER = 2
    FLATTEN_IMAGE = 3


class Image(_GObject.Object):
    def autocrop(self, drawable: Drawable | None = None) -> bool:
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


class Item(_GObject.Object):
    def get_children(self) -> list[Item]:
        ...

    def get_name(self) -> str:
        ...

    def get_visible(self) -> bool:
        ...

    def set_visible(self, visible: bool) -> bool:
        ...


class Layer(Drawable):
    def get_apply_mask(self) -> bool:
        ...

    def set_apply_mask(self, apply_mask: bool) -> bool:
        ...


class PDB(_GObject.Object):
    def lookup_procedure(self, procedure_name: str) -> Procedure | None:
        ...


class PDBStatusType(_GObject.GEnum):
    EXECUTION_ERROR = 0
    CALLING_ERROR = 1
    PASS_THROUGH = 2
    SUCCESS = 3
    CANCEL = 4


class Procedure(_GObject.Object):
    def create_config(self) -> ProcedureConfig:
        ...

    def run(self, config: ProcedureConfig | None = None) -> ValueArray:
        ...


class ProcedureConfig(_GObject.Object):
    ...


class RunMode(_GObject.GEnum):
    INTERACTIVE = 0
    NONINTERACTIVE = 1
    WITH_LAST_VALS = 2


class ValueArray:
    # PyGObject unpacks the GObject.Value into a Python value
    def index(self, index: int) -> object:
        ...

    def length(self) -> int:
        ...


def file_load(run_mode: RunMode, file: _Gio.File) -> Image | None:
    ...


def file_save(
    run_mode: RunMode,
    image: Image,
    file: _Gio.File,
    options: ExportOptions | None = None,
) -> bool:
    ...


def get_images() -> list[Image]:
    ...


def get_pdb() -> PDB | None:
    ...
