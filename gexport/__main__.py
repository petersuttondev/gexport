import json
import os
import subprocess
import sys
from collections import ChainMap
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import NoReturn, final

from gexport import models
from gexport.cli import ExportArgs, JSONSchemaArgs, MetadataArgs, parse_args
from gexport.databaselib import open_database
from gexport.util import suppress_unhandled


def _make_shell_command(
    args: Sequence[str],
    env_changes: Mapping[str, str],
) -> str:
    import shlex

    return ' '.join(
        (
            *(
                f'{key}={shlex.quote(value)}'
                for key, value in sorted(env_changes.items())
            ),
            shlex.join(args),
        )
    )


@final
class GIMP:
    def __init__(
        self,
        *,
        batch: str | None = None,
        dump_path: Path | None = None,
        interface: bool = False,
        results_path: Path | None = None,
        schema_path: Path | None = None,
        substrings: Iterable[str] | None = None,
        xcf_path: Path | None = None,
    ) -> None:
        self.batch = batch
        self.dump_path = dump_path
        self.interface = interface
        self.results_path = results_path
        self.schema_path = schema_path
        self.substrings = substrings
        self.xcf_path = xcf_path

    def make_args(self) -> list[str]:
        args: list[str] = []

        def push(*new_args: str) -> None:
            args.extend(new_args)

        push('gimp', '--new-instance')

        if not self.interface:
            push('--no-interface')

        push('--no-data', '--no-fonts', '--no-splash')

        if self.batch is None:
            batch = 'from gexport.script import run; run()'
            push(f'--batch={batch}')

        push(
            '--batch-interpreter=python-fu-eval',
            '--quit',
        )

        if self.xcf_path is not None:
            push(str(self.xcf_path))

        return args

    def make_env_changes(self) -> dict[str, str]:
        env: dict[str, str] = {}

        if self.dump_path is not None:
            env['GEXPORT_DUMP'] = str(self.dump_path)

        if self.results_path is not None:
            env['GEXPORT_RESULTS'] = str(self.results_path)

        if self.schema_path is not None:
            env['GEXPORT_SCHEMA'] = str(self.schema_path)

        if self.substrings:
            env['GEXPORT_SUBSTRINGS'] = json.dumps(self.substrings)

        return env

    def make_env(self) -> ChainMap[str, str]:
        return ChainMap(self.make_env_changes(), os.environ)

    def make_shell_command(self) -> str:
        return _make_shell_command(self.make_args(), self.make_env_changes())

    def exec(self) -> NoReturn:
        os.execve('/usr/bin/gimp', self.make_args(), self.make_env())

    def run(self) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(self.make_args(), env=self.make_env(), check=True)


def _export_subcommand(args: ExportArgs) -> None:
    gimp = GIMP(schema_path=args.schema_path, substrings=args.substrings)
    print(gimp.make_shell_command())
    gimp.exec()


def _json_schema_subcommand() -> None:
    json.dump(models.Schema.model_json_schema(), sys.stdout, indent=2)


def _metadata_subcommand(args: MetadataArgs) -> None:
    from rich.console import Console
    from rich.table import Column, Table

    if args.database_path is None:
        schema_path = args.schema_path
        database_path = (
            schema_path.resolve(strict=True).parent
            / models.load_schema(schema_path).database
        )
    else:
        database_path = args.database_path

    with open_database(database_path) as db:
        if args.clean:
            db.remove_data_for_missing_files()
        exports = list(db.iter_exports())

    if args.substrings:
        exports = [
            r for r in exports if any(s in r[0].stem for s in args.substrings)
        ]

    table = Table(
        Column('Name', justify='right'),
        'W',
        'H',
        'X←',
        'Y↑',
        'X→',
        'Y↓',
        'X',
        'Y',
        title='Exports',
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

    Console().print(table)


def main() -> None:
    suppress_unhandled(KeyboardInterrupt)
    args = parse_args()

    match args:
        case ExportArgs():
            _export_subcommand(args)
        case MetadataArgs():
            _metadata_subcommand(args)
        case JSONSchemaArgs():
            _json_schema_subcommand()


if __name__ == '__main__':
    main()
