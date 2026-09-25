"""Everything between launching the program and the main window appearing.

The shape of the sequence, and why:

1. **Ask for a folder only when it is actually needed.**  :func:`plan_startup`
   decides - a remembered folder that still holds its files goes straight
   through, so the common case is "double click, window opens".
2. **Warn about format problems, do not block on them.**  A mistyped line or a
   missing 作者 is something the user can fix from inside the app, and the app is
   perfectly usable meanwhile.
3. **Offer to start fresh only when a file cannot be decoded at all**, which is
   the single case where there is nothing usable to open.  Even then the old
   file is renamed aside rather than deleted.

Returns ``None`` when the user chose to quit, which is a normal outcome, not an
error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide2.QtWidgets import QDialog

from ..data.settings import Settings
from ..services.startup import (
    DataState,
    StartupResult,
    inspect_directory,
    plan_startup,
    start_fresh,
)
from .dialogs.confirm_dialog import ConfirmDialog
from .dialogs.location_dialog import LocationDialog
from .dialogs.warning_dialog import WarningDialog
from .theme import Theme


def run_startup(theme: Theme, settings: Settings) -> Optional[StartupResult]:
    """Resolve the catalogue before the main window is built."""
    plan = plan_startup(settings)

    if not plan.needs_location_prompt:
        return _resolve(theme, settings, plan.result)

    directory = _ask_for_directory(theme, plan.suggested_directory, plan.reason)
    if directory is None:
        return None
    return _resolve(theme, settings, inspect_directory(directory))


def _resolve(
    theme: Theme, settings: Settings, result: StartupResult
) -> Optional[StartupResult]:
    while True:
        if result.state is DataState.WARNINGS:
            WarningDialog(theme, result.messages).exec_()

        if result.state is not DataState.UNUSABLE:
            # Remember the folder so the next launch skips all of this.
            settings.data_dir = str(result.location.directory)
            settings.save()
            # Create the two files straight away.  Otherwise the user picks a
            # folder, sees nothing in it, and has no way to tell where their
            # library is going to live until they add a shelf.
            result.library.ensure_files_exist()
            return result

        create_new = ConfirmDialog.ask(
            parent=None,
            theme=theme,
            title="文件无法读取",
            message=result.fatal_error or "数据文件无法读取。",
            detail=(
                "是否新建一个空的书目文件？\n"
                "原来的文件会改名备份保留在同一个文件夹里，不会被删除。"
            ),
            confirm_text="新建文件",
        )
        if create_new:
            result = start_fresh(result.location.directory)
            continue

        directory = _ask_for_directory(
            theme, result.location.directory, "请换一个数据文件夹。"
        )
        if directory is None:
            return None
        result = inspect_directory(directory)


def _ask_for_directory(
    theme: Theme, suggested: Path, reason: str
) -> Optional[Path]:
    dialog = LocationDialog(theme, suggested, reason)
    if dialog.exec_() != QDialog.Accepted:
        return None
    return dialog.directory()
