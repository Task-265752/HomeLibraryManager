"""What the user should see before the main window appears.

The flow described by the project owner:

1. Choose the folder holding the catalogue and the settings file (or accept
   the portable default and let the program create the files).
2. Check the files and report anything wrong with their format.
3. If the shelf file is missing or empty, show a screen whose only action is
   "添加书架"; otherwise go straight to the normal screen.
4. Adding a shelf writes it to the shelf file and switches to the normal
   screen.

One deliberate departure from a literal reading of that spec
------------------------------------------------------------
Offering to **create new files is restricted to the case where the existing
file cannot be read at all.**  These files are meant to be edited by hand, so a
stray comma, a forgotten 作者 or a book pointing at a shelf that was deleted are
all normal states the program can carry straight on from.  Treating them as
fatal - and answering with a dialog whose OK button replaces the library -
would risk destroying an entire catalogue to "fix" one typo.

So those cases enter the app *with a warning*, and even the genuinely
unreadable case archives the old file instead of deleting it (see
:func:`homelibrarymanager.data.library.archive_existing_files`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from ..config import (
    BOOKS_FILENAME,
    SHELVES_FILENAME,
    DataLocation,
    resolve_data_dir,
)
from ..core.errors import DataFileError
from ..core.models import Shelf
from ..data.library import Library, LoadReport, create_fresh_catalogue
from ..data.settings import Settings
from .validation import build_shelf


class DataState(Enum):
    """How usable the catalogue in the chosen folder turned out to be."""

    READY = "ready"        # files present, nothing to report
    WARNINGS = "warnings"  # usable, but the user should be told something
    UNUSABLE = "unusable"  # a file cannot be read at all


@dataclass
class StartupResult:
    state: DataState
    location: DataLocation
    library: Library
    report: Optional[LoadReport] = None
    #: Messages ready to show, already phrased in plain language.
    messages: List[str] = field(default_factory=list)
    fatal_error: str = ""

    @property
    def has_shelves(self) -> bool:
        """False means the UI should show only the 添加书架 button."""
        return bool(self.library.shelves)

    @property
    def can_offer_new_files(self) -> bool:
        """Only a file we cannot read at all justifies offering a fresh start."""
        return self.state is DataState.UNUSABLE

    @property
    def should_warn(self) -> bool:
        return self.state is DataState.WARNINGS

    @property
    def is_fresh(self) -> bool:
        """True when neither catalogue file existed before this run."""
        if self.report is None:
            return False
        return self.report.books_file_missing and self.report.shelves_file_missing


def inspect_directory(directory: Union[str, Path, None]) -> StartupResult:
    """Load the catalogue in ``directory`` and classify the outcome.

    ``directory`` of ``None`` means "use the remembered choice, else the
    portable default next to the program".
    """
    location = resolve_data_dir(directory)
    try:
        location.directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return StartupResult(
            state=DataState.UNUSABLE,
            location=location,
            library=Library(location.directory),
            messages=["无法创建或访问目录：{0}".format(exc)],
            fatal_error=str(exc),
        )

    library = Library(location.directory)
    try:
        report = library.load()
    except DataFileError as exc:
        # The file exists but cannot be decoded - the one case where offering
        # "create a new file" is legitimate.
        return StartupResult(
            state=DataState.UNUSABLE,
            location=location,
            library=library,
            messages=[exc.message],
            fatal_error=exc.message,
        )

    messages = report.all_messages()
    return StartupResult(
        state=DataState.WARNINGS if messages else DataState.READY,
        location=location,
        library=library,
        report=report,
        messages=messages,
    )


@dataclass
class StartupPlan:
    """Whether the folder chooser must be shown before the main window.

    The project owner's rule: show the chooser **only on first run, or when the
    catalogue files are missing** - otherwise remember the previous folder and
    go straight to the main screen.  Nothing is more annoying than being asked
    the same question every single launch.
    """

    needs_location_prompt: bool
    suggested_directory: Path
    #: Why the prompt is being shown, ready to display in it.
    reason: str = ""
    #: Present only when no prompt is needed - the already-loaded catalogue.
    result: Optional[StartupResult] = None


def _catalogue_files(directory: Union[str, Path]) -> List[Path]:
    directory = Path(directory)
    return [
        path
        for path in (directory / BOOKS_FILENAME, directory / SHELVES_FILENAME)
        if path.exists()
    ]


def plan_startup(
    settings: Settings, explicit_directory: Union[str, Path, None] = None
) -> StartupPlan:
    """Decide between "show the folder chooser" and "go straight in"."""
    remembered = explicit_directory or (settings.data_dir or None)

    if remembered:
        directory = Path(remembered).expanduser()
        if not directory.is_dir():
            return StartupPlan(
                True, directory, "指定的目录不存在：{0}".format(directory)
            )
        if not _catalogue_files(directory):
            return StartupPlan(
                True,
                directory,
                "该目录里没有找到 {0} 或 {1}".format(BOOKS_FILENAME, SHELVES_FILENAME),
            )
        return StartupPlan(False, directory, "", inspect_directory(directory))

    # No remembered choice: fall back to the portable default.  If a previous
    # run already put files there, use them without pestering the user.
    default_directory = resolve_data_dir(None).directory
    if _catalogue_files(default_directory):
        return StartupPlan(False, default_directory, "", inspect_directory(default_directory))

    return StartupPlan(True, default_directory, "首次使用，请选择数据保存位置")


def start_fresh(directory: Union[str, Path]) -> StartupResult:
    """Archive whatever is in ``directory`` and begin an empty catalogue.

    The archived file names are returned in ``messages`` so the UI can tell the
    user where their old data went - silently replacing a library and saying
    nothing would be the worst possible outcome.
    """
    library, archived = create_fresh_catalogue(directory)
    messages: List[str] = []
    if archived:
        messages.append(
            "原有数据已备份保留（未删除）：{0}".format(
                "、".join(new.name for _, new in archived)
            )
        )
    return StartupResult(
        state=DataState.READY,
        location=resolve_data_dir(directory),
        library=library,
        report=library.load(),
        messages=messages,
    )


def add_shelf_to(
    library: Library,
    name: str,
    sequence: str,
    note: str = "",
    *,
    save: bool = True,
) -> Shelf:
    """Validate, add to ``library`` and (by default) persist immediately.

    Saving straight away matches the flow the project owner described: adding
    the first shelf writes it to the shelf file and the UI then shows the
    normal screen.
    """
    shelf = build_shelf(name, sequence, note, existing_names=library.shelf_names())
    library.add_shelf(shelf)
    if save:
        library.save_shelves()
    return shelf
