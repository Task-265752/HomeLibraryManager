"""Application identity, file names, and where the catalogue files live.

Data location policy
--------------------
The project owner chose *portable* storage: the catalogue files sit next to
the program so the whole folder can be copied onto a USB stick and carried
around.  The catch is that a folder is not always writable - if someone
unpacks the program into ``C:\\Program Files`` we cannot create ``books.jsonl``
there.  Rather than refusing to start, :func:`resolve_data_dir` probes the
preferred folder and transparently falls back to the user's documents folder,
reporting the substitution so the UI can tell the user where their data went.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

#: Shown in the window title and About box.
APP_NAME = "家庭图书管理系统"
#: The English product name.  Used wherever an ASCII-only identifier is needed:
#: the .exe, the distribution folder, the ZIP name and the Python package.
APP_NAME_EN = "HomeLibraryManager"
#: Folder name under the user's Documents when the portable folder is read-only.
APP_ID = "HomeLibraryManager"
APP_VERSION = "0.1.0"
ORG_NAME = "HomeLibraryManager"

#: Images referenced by the stylesheet and the window icon.  Qt's stylesheet
#: cannot draw a dropdown arrow from borders the way CSS can, so a couple of
#: tiny PNGs are unavoidable; keeping them in one place also gives the packaged
#: build a single directory to bundle.
RESOURCES_DIRNAME = "resources"

# --------------------------------------------------------------------------
# Catalogue files
# --------------------------------------------------------------------------
# The extension is deliberately cosmetic: the loader identifies the format by
# content rather than by suffix, so renaming these to ``.txt`` (which makes
# Windows open them in Notepad on a double click) keeps working.
BOOKS_FILENAME = "books.jsonl"
SHELVES_FILENAME = "shelves.jsonl"

#: Written next to a catalogue file just before it is replaced.
BACKUP_SUFFIX = ".bak"

#: Remembers the chosen data folder and window geometry.  A plain INI on
#: purpose (see data/settings.py): QSettings would put this in the registry,
#: which would make the "unzip anywhere and run" promise false.
SETTINGS_FILENAME = "settings.ini"

#: Recorded on the first line so a future version can migrate the file.
FILE_FORMAT = "hlm-catalog"
FILE_FORMAT_VERSION = 1

#: Virtual shelf that collects books whose ``shelf`` value matches no shelf.
#: Nothing is ever moved or renamed on disk because of this - it only affects
#: how the books are grouped for display.
UNFILED_SHELF_NAME = "未归档"

#: Virtual shelf for books that have no ``shelf`` value at all.
UNPLACED_SHELF_NAME = "未上架"

# --------------------------------------------------------------------------
# Window geometry (800x600 is the stated floor, 4K is handled by HiDPI)
# --------------------------------------------------------------------------
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
DEFAULT_WINDOW_WIDTH = 1180
DEFAULT_WINDOW_HEIGHT = 760

#: Overrides portable detection; handy for tests and for a command line flag.
DATA_DIR_ENV = "HLM_DATA_DIR"


@dataclass(frozen=True)
class DataLocation:
    """Result of working out where the catalogue files should live."""
    directory: Path
    portable: bool
    #: Empty when the preferred folder was usable.  Otherwise a short,
    #: user-facing explanation of why we fell back.
    fallback_reason: str = ""

    @property
    def books_path(self) -> Path:
        return self.directory / BOOKS_FILENAME

    @property
    def shelves_path(self) -> Path:
        return self.directory / SHELVES_FILENAME


def application_dir() -> Path:
    """Folder holding the program: the .exe when frozen, the project otherwise."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/homelibrarymanager/config.py -> src/homelibrarymanager -> src -> project root
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """Folder holding the bundled images.

    PyInstaller unpacks data files under ``sys._MEIPASS``, so the frozen and
    source layouts differ; both are handled here so callers never care.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "homelibrarymanager" / RESOURCES_DIRNAME
    return Path(__file__).resolve().parent / RESOURCES_DIRNAME


def resource_path(name: str) -> str:
    """Absolute path to a bundled image, in the forward-slash form QSS wants."""
    return str(resource_dir() / name).replace("\\", "/")


def _documents_dir() -> Path:
    """Per-platform 'My Documents', used when the program folder is read-only."""
    if sys.platform == "win32":
        profile = os.environ.get("USERPROFILE")
        base = Path(profile) if profile else Path.home()
        return base / "Documents"
    if sys.platform == "darwin":
        return Path.home() / "Documents"
    base = os.environ.get("XDG_DATA_HOME")
    return Path(base) if base else Path.home() / ".local" / "share"


def is_writable(folder: Path) -> bool:
    """True when we can actually create files in ``folder``.

    Existence is not enough: a folder can exist and still be read-only, which
    is exactly what happens under ``C:\\Program Files``.
    """
    probe = folder / ".hlm-write-test"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(probe, "w", encoding="ascii") as handle:
            handle.write("x")
        probe.unlink()
        return True
    except OSError:
        try:
            probe.unlink()
        except OSError:
            pass
        return False


def resolve_data_dir(explicit: Optional[Union[str, Path]] = None) -> DataLocation:
    """Decide where the catalogue files go, falling back when necessary."""
    if explicit is not None:
        target = Path(explicit).expanduser()
        return DataLocation(target, portable=False, fallback_reason="")

    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return DataLocation(Path(override).expanduser(), portable=False, fallback_reason="")

    program_dir = application_dir()
    if is_writable(program_dir):
        return DataLocation(program_dir, portable=True)

    fallback = _documents_dir() / APP_ID
    reason = (
        "程序所在目录不可写（常见于安装在 C:\\Program Files 下），"
        "数据已改存到：{0}".format(fallback)
    )
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Last resort: a hidden folder in the home directory.  Still better
        # than refusing to run.
        fallback = Path.home() / ("." + APP_ID.lower())
        fallback.mkdir(parents=True, exist_ok=True)
        reason = "程序目录与文档目录均不可写，数据已改存到：{0}".format(fallback)
    return DataLocation(fallback, portable=False, fallback_reason=reason)
