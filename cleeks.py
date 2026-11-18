from typing import TYPE_CHECKING

from cleek import task

from gexport.cli import make_parser

if TYPE_CHECKING:
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

_project_dir: Path | None = None


def _get_project_dir() -> Path:
    global _project_dir
    if _project_dir is None:
        from pathlib import Path

        _project_dir = Path(__file__).resolve(strict=True).parent
    return _project_dir
