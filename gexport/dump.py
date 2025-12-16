from pathlib import Path
import sys
from typing import TypedDict, final

import yaml
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp

from gexport.util import open_image, traverse

type Show = list[Group | str]


@final
class Group(TypedDict):
    group: str
    show: Show


def run(xcf_path: Path) -> None:
    root_show: Show = []
    groups: dict[str, Group] = {}

    with open_image(xcf_path) as image:
        for layer, path in traverse(image.get_layers()):
            if not layer.get_visible():
                continue

            show = root_show

            for group_name in path[:-1]:
                group = groups.get(group_name)

                if group is None:
                    group = Group(group=group_name, show=[])
                    show.append(group)
                    groups[group_name] = group

                show = group['show']

            if not isinstance(layer, Gimp.GroupLayer):
                show.append(path[-1])

    yaml.dump({'show': root_show}, sys.stdout)
