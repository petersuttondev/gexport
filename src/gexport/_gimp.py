import os
import shlex
import subprocess
import sys
from collections import ChainMap
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import final, override

from gexport._env import GexportEnv


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
        manifest_path: Path,
        substrings: Iterable[str] = (),
    ) -> None:
        self.manifest_path = manifest_path
        self.substrings = list(substrings)

    def make_batch(self) -> str:
        return ";".join(
            (
                "import sys",
                f"sys.path.extend({sys.path!r})",
                "from gexport.script import run",
                "run()",
            )
        )

    def make_args(self) -> tuple[str, ...]:
        return (
            "gimp-console",
            "--new-instance",
            "--no-data",
            "--no-fonts",
            "--no-splash",
            f"--batch={self.make_batch()}",
            "--batch-interpreter=python-fu-eval",
            "--quit",
        )

    def make_gexport_env(self) -> GexportEnv:
        return GexportEnv(
            manifest=self.manifest_path,
            substrings=self.substrings,
        )

    def make_gexport_env_value(self) -> str:
        return self.make_gexport_env().model_dump_json()

    def make_env_additions(self) -> dict[str, str]:
        return {"GEXPORT_ENV": self.make_gexport_env_value()}

    def make_env(self) -> ChainMap[str, str]:
        return ChainMap(self.make_env_additions(), os.environ)

    def make_shell_command(self) -> str:
        return _make_shell_command(self.make_args(), self.make_env_additions())

    def run(self) -> None:
        subprocess.run(self.make_args(), env=self.make_env(), check=True)
