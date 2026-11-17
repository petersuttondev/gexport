import json
import os
import shlex
import subprocess
import sys
from collections import ChainMap
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import NoReturn, final, override


def _make_shell_command(
    args: Sequence[str],
    env_changes: Mapping[str, str],
) -> str:

    return " ".join(
        (
            *(
                f"{key}={shlex.quote(value)}"
                for key, value in sorted(env_changes.items())
            ),
            shlex.join(args),
        )
    )


@final
class GIMP:
    @override
    def __init__(
        self,
        *,
        batch: str | None = None,
        dump_path: Path | None = None,
        results_path: Path | None = None,
        manifest_path: Path | None = None,
        substrings: Iterable[str] | None = None,
        xcf_path: Path | None = None,
    ) -> None:
        self.batch = batch
        self.dump_path = dump_path
        self.results_path = results_path
        self.manifest_path = manifest_path
        self.substrings = substrings
        self.xcf_path = xcf_path

    def make_args(self) -> list[str]:
        args = [
            "gimp-console",
            "--new-instance",
            "--no-data",
            "--no-fonts",
            "--no-splash",
        ]

        if self.batch is None:
            batch = "\n".join(
                (
                    "import sys",
                    f"sys.path.extend({sys.path!r})",
                    "from gexport.script import run",
                    "run()",
                )
            )
            args.append(f"--batch={batch}")
        args.append("--batch-interpreter=python-fu-eval")
        args.append("--quit")
        if self.xcf_path is not None:
            args.append(str(self.xcf_path))
        return args

    def make_env_changes(self) -> dict[str, str]:
        env: dict[str, str] = {}

        if self.dump_path is not None:
            env["GEXPORT_DUMP"] = str(self.dump_path)

        if self.results_path is not None:
            env["GEXPORT_RESULTS"] = str(self.results_path)

        if self.manifest_path is not None:
            env["GEXPORT_MANIFEST"] = str(self.manifest_path)

        if self.substrings:
            env["GEXPORT_SUBSTRINGS"] = json.dumps(self.substrings)

        return env

    def make_env(self) -> ChainMap[str, str]:
        return ChainMap(self.make_env_changes(), os.environ)

    def make_shell_command(self) -> str:
        return _make_shell_command(self.make_args(), self.make_env_changes())

    def exec(self) -> NoReturn:
        args = self.make_args()
        os.execvpe(args[0], args, self.make_env())

    def run(self) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(self.make_args(), env=self.make_env(), check=True)
