from typing import TYPE_CHECKING

from cleek import task

from gexport.cli import make_parser

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


# -- Tasks ---------------------------------------------------------------------


@task
def clean(dry_run: bool = False) -> None:
    import shlex
    import subprocess

    args = ["git", "clean", "--force"]
    if dry_run:
        args.append("--dry-run")
    args.append("-X")
    args.append(".")
    print(shlex.join(args))
    subprocess.run(args, cwd=_get_project_dir(), check=True)


@task
def install() -> None:
    import subprocess

    subprocess.run(
        ("uv", "tool", "install", "--editable", _get_project_dir()),
        check=True,
    )


@task
def uninstall() -> None:
    import subprocess

    subprocess.run(("uv", "tool", "uninstall", "gexport"), check=True)


@task
def completion() -> None:
    import shtab

    print(shtab.complete(make_parser(), shell="zsh"), end="", flush=True)


# -- Utilities -----------------------------------------------------------------

type _Args = Iterable[_Args] | str


def _args_flatten(args: _Args, flat: list[str]) -> None:
    for arg in args:
        if isinstance(arg, str):
            flat.append(arg)
        else:
            _args_flatten(arg, flat)


def _args(*args: _Args) -> list[str]:
    flat: list[str] = []
    _args_flatten(args, flat)
    return flat


_project_dir: Path | None = None


def _get_project_dir() -> Path:
    global _project_dir
    if _project_dir is None:
        from pathlib import Path

        _project_dir = Path(__file__).resolve(strict=True).parent
    return _project_dir
