import gi as _gi

_gi.require_version("Gimp", "3.0")
del _gi

from gi.repository import Gimp, Gio  # pyright: ignore[reportMissingModuleSource]

__all__ = ("Gimp", "Gio")
