"""Autostart — delegates to platform adapter."""

from meetrec.platform import (
    autostart_current_executable_path as current_executable_path,
    autostart_disable as disable,
    autostart_enable as enable,
    autostart_get_registered_path as get_registered_path,
    autostart_is_enabled as is_enabled,
    autostart_is_supported as is_supported,
)

__all__ = [
    "current_executable_path",
    "disable",
    "enable",
    "get_registered_path",
    "is_enabled",
    "is_supported",
]
