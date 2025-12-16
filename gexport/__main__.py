from argparse import (
    Action,
    ArgumentParser,
    ArgumentTypeError,
    Namespace,
    _SubParsersAction,
)
from collections import ChainMap
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
from typing import Final, NoReturn, final

from gexport import models
from gexport.databaselib import open_database
from gexport.util import (
    check_bool,
    check_path,
    check_str_list,
    suppress_unhandled,
)


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class DumpArguments:
    xcf_path: Final[Path]


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class ExportArguments:
    interface: Final[bool]
    schema_path: Final[Path]
    substrings: Final[Sequence[str]]
    view: Final[bool]


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class JSONSchemaArguments:
    pass


@dataclass(frozen=True, kw_only=True, slots=True)
class AutoOrigin:
    pass


@dataclass(frozen=True, kw_only=True, slots=True)
class XYOrigin:
    x: Final[int]
    y: Final[int]


type Origin = AutoOrigin | XYOrigin


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class MetadataArguments:
    clean: Final[bool]
    database_path: Final[Path]
    origin: Final[Origin | None]
    substrings: Final[Sequence[str]]


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class ShellArguments:
    xcf_path: Final[Path]


type Arguments = (
    DumpArguments
    | ExportArguments
    | JSONSchemaArguments
    | MetadataArguments
    | ShellArguments
)

type Subparsers = _SubParsersAction[ArgumentParser]


def _add_schema_argument(parser: ArgumentParser) -> Action:
    return parser.add_argument(
        '-s',
        '--schema',
        default='gexport.yaml',
        type=Path,
        dest='schema_path',
    )


def _add_dump_parser(subparsers: Subparsers, name: str) -> None:
    parser = subparsers.add_parser(name)
    parser.add_argument('xcf_path', type=Path, metavar='xcf')


def _make_dump_args(ns: Namespace) -> DumpArguments:
    return DumpArguments(xcf_path=check_path(ns.xcf_path))


def _add_export_parser(subparsers: Subparsers, name: str) -> None:
    parser = subparsers.add_parser(name)
    _add_schema_argument(parser)
    parser.add_argument('-i', '--interface', action='store_true', default=True)
    parser.add_argument(
        '-I',
        '--no-interface',
        action='store_false',
        dest='interface',
    )
    parser.add_argument('-v', '--view', action='store_true')
    parser.add_argument('substrings', nargs='*')


def _make_export_args(ns: Namespace) -> ExportArguments:
    return ExportArguments(
        interface=check_bool(ns.interface),
        schema_path=check_path(ns.schema_path),
        substrings=tuple(check_str_list(ns.substrings)),
        view=check_bool(ns.view),
    )


def _add_json_schema_parser(subparsers: Subparsers, name: str) -> None:
    subparsers.add_parser(name)


def _make_json_schema_args(ns: Namespace) -> JSONSchemaArguments:
    _ = ns
    return JSONSchemaArguments()


def _parse_ordinate(text: str | None) -> int:
    return 0 if text is None else int(text.replace('n', '-'))


def _parse_origin(text: str) -> Origin:
    match = re.match(
        r"""
            \A
            (?P<auto> auto )
            | (?:
                (?P<x> [-n]?[0-9]+ )?
                (?: , (?P<y> [-n]?[0-9]+ )? )?
            )
            \Z
        """,
        text,
        flags=re.VERBOSE,
    )

    if match is None:
        raise ArgumentTypeError(f'invalid origin {text!r}')

    groups = match.groupdict()

    match match.groupdict():
        case {'auto': 'auto'}:
            return AutoOrigin()

        case {'x': x, 'y': y}:
            return XYOrigin(x=_parse_ordinate(x), y=_parse_ordinate(y))

        case _ as groups:
            raise ValueError(f'invalid match group dict ${groups!r}')


def _add_metadata_parser(subparsers: Subparsers, name: str) -> None:
    parser = subparsers.add_parser(name)
    _add_schema_argument(parser)
    parser.add_argument(
        '-d',
        '--database',
        type=Path,
        dest='database_path',
    )
    parser.add_argument(
        '-c',
        '--clean',
        action='store_true',
    )
    parser.add_argument('-o', '--origin', type=_parse_origin)
    parser.add_argument('substrings', nargs='*')


def _make_metadata_args(ns: Namespace) -> MetadataArguments:
    if ns.database_path is None:
        schema_path = check_path(ns.schema_path).resolve(strict=True)
        database_path = (
            schema_path.parent / models.load_schema(schema_path).database
        )
    else:
        database_path = check_path(ns.database_path)

    origin: object = ns.origin
    assert origin is None or isinstance(origin, (AutoOrigin, XYOrigin))

    return MetadataArguments(
        clean=check_bool(ns.clean),
        database_path=database_path,
        origin=origin,
        substrings=tuple(check_str_list(ns.substrings)),
    )


def _add_shell_parser(subparsers: Subparsers, name: str) -> None:
    parser = subparsers.add_parser(name)
    parser.add_argument('xcf_path', type=Path, metavar='xcf')


def _make_shell_args(ns: Namespace) -> ShellArguments:
    return ShellArguments(xcf_path=ns.xcf_path)


def parse_args() -> Arguments:
    parser = ArgumentParser()
    commands: dict[str, Callable[[Namespace], Arguments]] = {}

    subparsers = parser.add_subparsers(
        title='command',
        dest='command',
        required=True,
    )

    def command(
        name: str,
        make_command: Callable[[Subparsers, str], None],
        make_args: Callable[[Namespace], Arguments],
    ) -> None:
        make_command(subparsers, name)
        commands[name] = make_args

    command('dump', _add_dump_parser, _make_dump_args)
    command('export', _add_export_parser, _make_export_args)
    command('json-schema', _add_json_schema_parser, _make_json_schema_args)
    command('metadata', _add_metadata_parser, _make_metadata_args)
    command('shell', _add_shell_parser, _make_shell_args)
    ns = parser.parse_args()
    return commands[ns.command](ns)


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

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(self.make_args(), env=self.make_env(), check=True)


def do_dump(args: DumpArguments) -> NoReturn:
    GIMP(dump_path=args.xcf_path).exec()


def do_export(args: ExportArguments) -> None:
    gimp = GIMP(
        interface=args.interface,
        schema_path=args.schema_path,
        substrings=args.substrings,
    )

    print(gimp.make_shell_command())

    if not args.view:
        gimp.exec()

    with NamedTemporaryFile() as temp_file:
        gimp.results_path = Path(temp_file.name)
        gimp.run()
        results: list[str] = json.load(temp_file)

    if results:
        subprocess.run(('sxiv', '-t', *results))


def do_json_schema() -> None:
    json.dump(models.Schema.model_json_schema(), sys.stdout, indent=2)


def do_metadata(args: MetadataArguments) -> None:
    from rich.console import Console
    from rich.table import Table

    with open_database(args.database_path) as db:
        if args.clean:
            db.remove_data_for_missing_files()
        exports = list(db.iter_exports())

    if args.substrings:
        exports = [
            r for r in exports if any(s in r[0].stem for s in args.substrings)
        ]

    match args.origin:
        case AutoOrigin():
            x_origin = min(r.x_offset for r in exports)
            y_origin = min(r.y_offset for r in exports)
        case XYOrigin(x=x_origin, y=y_origin):
            pass
        case None:
            x_origin = y_origin = 0

    table = Table('Path', 'W', 'H', 'X←', 'Y↑', 'X→', 'Y↓', title='Exports')
    cwd = Path().resolve()

    for path, width, height, x_offset, y_offset in exports:
        table.add_row(
            str(path.relative_to(cwd, walk_up=True)),
            str(width),
            str(height),
            str(x_offset - x_origin),
            str(y_offset - y_origin),
            str(x_offset + width - x_origin),
            str(y_offset + height - y_origin),
        )

    console = Console()
    console.print(table)

    left = min(e.x_offset - x_origin for e in exports)
    top = min(e.y_offset - y_origin for e in exports)
    right = max(e.x_offset + e.width - x_origin for e in exports)
    bottom = max(e.y_offset + e.height - y_origin for e in exports)
    width = right - left
    height = bottom - top

    table = Table(
        'W',
        'H',
        'X←',
        'Y↑',
        'X→',
        'Y↓',
        title='Bounding Box',
    )
    table.add_row(
        str(width),
        str(height),
        str(left),
        str(top),
        str(right),
        str(bottom),
    )
    console.print(table)


def do_shell(args: ShellArguments) -> NoReturn:
    GIMP(
        batch='from IPython import embed; embed()',
        xcf_path=args.xcf_path,
    ).exec()


def main() -> None:
    suppress_unhandled(KeyboardInterrupt)
    args = parse_args()

    match args:
        case DumpArguments():
            do_dump(args)
        case ExportArguments():
            do_export(args)
        case JSONSchemaArguments():
            do_json_schema()
        case MetadataArguments():
            do_metadata(args)
        case ShellArguments():
            do_shell(args)


if __name__ == '__main__':
    main()
