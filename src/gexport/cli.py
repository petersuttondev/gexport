from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal, final

from pydantic.config import ConfigDict
from pydantic.fields import Field
from pydantic.main import BaseModel
from pydantic.type_adapter import TypeAdapter

if TYPE_CHECKING:
    from argparse import _SubParsersAction  # pyright: ignore[reportPrivateUsage]

type Subparsers = _SubParsersAction[ArgumentParser]

_DEFAULT_MANIFEST_PATH: Final[Path] = Path("gexport.yaml")


def _add_manifest_argument(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-m",
        "--manifest",
        default=_DEFAULT_MANIFEST_PATH,
        type=Path,
        dest="manifest_path",
    )


def _add_subcommand(subparsers: Subparsers, subcommand: str) -> ArgumentParser:
    parser = subparsers.add_parser(subcommand)
    parser.set_defaults(subcommand=subcommand)
    return parser


# -- export ------------------------------------------------------------------ #


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class ExportArgs:
    manifest_path: Final[Path]
    substrings: Final[tuple[str, ...]]


@final
class _ExportModel(BaseModel, frozen=True):  # pyright: ignore[reportUninitializedInstanceVariable]
    model_config = ConfigDict(extra="forbid")
    subcommand: Final[Literal["export"]]  # noqa: PYI064
    manifest_path: Final[Path]
    substrings: Final[list[str]]


def _add_export_parser(subparsers: Subparsers) -> None:
    parser = _add_subcommand(subparsers, "export")
    _add_manifest_argument(parser)
    parser.add_argument("substrings", nargs="*")


def _make_export_args(model: _ExportModel) -> ExportArgs:
    return ExportArgs(
        manifest_path=model.manifest_path, substrings=tuple(model.substrings)
    )


# -- layout ------------------------------------------------------------------ #


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class LayoutArgs:
    manifest_path: Final[Path]
    database_path: Final[Path | None]
    clean: Final[bool]
    substrings: Final[tuple[str, ...]]


@final
class _LayoutModel(BaseModel, frozen=True):  # pyright: ignore[reportUninitializedInstanceVariable]
    model_config = ConfigDict(extra="forbid")
    subcommand: Final[Literal["layout"]]  # noqa: PYI064
    manifest_path: Final[Path]
    database_path: Final[Path | None]
    clean: Final[bool]
    substrings: Final[list[str]]


def _add_layout_parser(subparsers: Subparsers) -> None:
    parser = _add_subcommand(subparsers, "layout")
    _add_manifest_argument(parser)
    parser.add_argument("-c", "--clean", action="store_true")
    parser.add_argument("-d", "--database", type=Path, dest="database_path")
    parser.add_argument("substrings", nargs="*")


def _make_layout_args(model: _LayoutModel) -> LayoutArgs:
    return LayoutArgs(
        manifest_path=model.manifest_path,
        database_path=model.database_path,
        clean=model.clean,
        substrings=tuple(model.substrings),
    )


# -- json-schema ------------------------------------------------------------- #


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class JSONSchemaArgs:
    pass


@final
class _JSONSchemaModel(BaseModel, frozen=True):  # pyright: ignore[reportUninitializedInstanceVariable]
    model_config = ConfigDict(extra="forbid")
    subcommand: Final[Literal["json-schema"]]  # noqa: PYI064


def _add_json_schema_parser(subparsers: Subparsers) -> None:
    _add_subcommand(subparsers, "json-schema")


def _make_json_schema_args() -> JSONSchemaArgs:
    return JSONSchemaArgs()


# ---------------------------------------------------------------------------- #

type Args = ExportArgs | LayoutArgs | JSONSchemaArgs


@final
class _DefaultModel(BaseModel, frozen=True):  # pyright: ignore[reportUninitializedInstanceVariable]
    model_config = ConfigDict(extra="forbid")
    subcommand: Final[Literal["default"]]  # noqa: PYI064


type _ArgsModel = _DefaultModel | _ExportModel | _LayoutModel | _JSONSchemaModel


def make_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="gexport")
    parser.set_defaults(subcommand="default")
    subparsers = parser.add_subparsers()
    _add_export_parser(subparsers)
    _add_layout_parser(subparsers)
    _add_json_schema_parser(subparsers)
    return parser


_args_model_adapter: Final = TypeAdapter[_ArgsModel](
    Annotated[_ArgsModel, Field(discriminator="subcommand")]
)


def _make_model(ns: Namespace) -> _ArgsModel:
    return _args_model_adapter.validate_python(vars(ns))


def _make_args(model: _ArgsModel) -> Args:
    match model.subcommand:
        case "default":
            return ExportArgs(
                manifest_path=_DEFAULT_MANIFEST_PATH, substrings=()
            )
        case "export":
            return _make_export_args(model)
        case "layout":
            return _make_layout_args(model)
        case "json-schema":
            return _make_json_schema_args()


def parse_args() -> Args:
    return _make_args(_make_model(make_parser().parse_args()))
