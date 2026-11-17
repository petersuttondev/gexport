from collections.abc import Iterable, Sequence
from pathlib import Path

from rich.console import Console
from rich.table import Column, Table

from gexport import models
from gexport.cli import LayoutArgs
from gexport.databaselib import Export, open_database


def _get_database_path(args: LayoutArgs) -> Path:
    if args.database_path is not None:
        return args.database_path
    manifest_path = args.manifest_path.resolve(strict=True)
    manifest = models.load_manifest(manifest_path)
    return manifest_path.parent / manifest.database


def _fetch_exports(
    database_path: Path, *, remove_layouts_without_files: bool = False
) -> list[Export]:
    with open_database(database_path) as db:
        if remove_layouts_without_files:
            db.remove_data_for_missing_files()
        return list(db.iter_exports())


def _filter_exports(
    exports: list[Export], substrings: Sequence[str]
) -> list[Export]:
    if not substrings:
        return exports
    return [r for r in exports if any(s in r.path.stem for s in substrings)]


def _create_table(exports: Iterable[Export]) -> Table:
    table = Table(
        Column("Name", justify="right"),
        "W",
        "H",
        "X←",
        "Y↑",
        "X→",
        "Y↓",
        "X",
        "Y",
        title="Exports",
    )

    for (
        path,
        width,
        height,
        x_offset,
        y_offset,
        x_scale,
        y_scale,
    ) in exports:
        table.add_row(
            str(path.name),
            str(width),
            str(height),
            str(x_offset),
            str(y_offset),
            str(x_offset + width),
            str(y_offset + height),
            str(x_scale),
            str(y_scale),
        )

    return table


def layout_subcommand(args: LayoutArgs) -> None:
    database_path = _get_database_path(args)
    exports = _fetch_exports(
        database_path, remove_layouts_without_files=args.clean
    )
    exports = _filter_exports(exports, args.substrings)
    table = _create_table(exports)
    Console().print(table)
