"""Application settings, stored as a plain INI file next to the program.

Deliberately **not** ``QSettings``.  On Windows ``QSettings`` defaults to the
registry, which would quietly break the project's core promise: unzip anywhere,
carry it on a USB stick, write nothing outside the folder.  ``configparser`` is
in the standard library, produces a file the user can read and edit in Notepad,
and keeps this module free of Qt so it can be tested without a display.

Like the catalogue files, the INI is written as UTF-8 with a BOM and CRLF line
endings so Windows 7 Notepad displays it correctly.  A corrupt settings file is
never fatal - the defaults are simply used, because losing window geometry is
not worth refusing to start over.
"""

from __future__ import annotations

import configparser
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from ..config import SETTINGS_FILENAME

GENERAL = "general"
WINDOW = "window"

#: Chosen data folder.  Empty means "use the portable default".
KEY_DATA_DIR = "data_dir"
#: Base64 of QMainWindow.saveGeometry(), opaque to this module.
KEY_GEOMETRY = "geometry"
KEY_WINDOW_STATE = "state"


class Settings:
    """A tiny key/value store with per-section defaults."""

    DEFAULTS = {
        GENERAL: {KEY_DATA_DIR: ""},
        WINDOW: {KEY_GEOMETRY: "", KEY_WINDOW_STATE: ""},
    }

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        self._parser = configparser.ConfigParser()
        self.reset()

    # -- persistence -----------------------------------------------------

    def reset(self) -> None:
        self._parser = configparser.ConfigParser()
        for section, values in self.DEFAULTS.items():
            self._parser[section] = dict(values)

    def load(self) -> None:
        """Read the file, falling back to defaults if it is missing or broken."""
        self.reset()
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8-sig") as handle:
                self._parser.read_file(handle)
        except (OSError, configparser.Error, UnicodeDecodeError):
            # A damaged settings file is not worth blocking startup over.
            self.reset()

    def save(self) -> None:
        """Write atomically, so a crash cannot leave a half-written file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle_fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name + ".", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(handle_fd, "w", encoding="utf-8-sig", newline="\r\n") as handle:
                self._parser.write(handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(tmp_path), str(self.path))
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    # -- access ----------------------------------------------------------

    def get(self, section: str, key: str, default: str = "") -> str:
        if not self._parser.has_section(section):
            return default
        return self._parser.get(section, key, fallback=default)

    def set(self, section: str, key: str, value: str) -> None:
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, key, "" if value is None else str(value))

    # -- convenience -----------------------------------------------------

    @property
    def data_dir(self) -> str:
        return self.get(GENERAL, KEY_DATA_DIR)

    @data_dir.setter
    def data_dir(self, value: Union[str, Path, None]) -> None:
        self.set(GENERAL, KEY_DATA_DIR, "" if value is None else str(value))

    @property
    def geometry(self) -> str:
        return self.get(WINDOW, KEY_GEOMETRY)

    @geometry.setter
    def geometry(self, value: str) -> None:
        self.set(WINDOW, KEY_GEOMETRY, value or "")

    @property
    def window_state(self) -> str:
        return self.get(WINDOW, KEY_WINDOW_STATE)

    @window_state.setter
    def window_state(self, value: str) -> None:
        self.set(WINDOW, KEY_WINDOW_STATE, value or "")

    def known_sections(self) -> List[str]:
        return list(self._parser.sections())
