from enum import IntEnum as _IntEnum
from enum import IntFlag as _IntFlag


class Object:
    def get_property(self, property_name: str) -> object:
        ...

    def set_property(self, property_name: str, value: object) -> None:
        ...


class GEnum(_IntEnum):
    ...


class GFlags(_IntFlag):
    ...
