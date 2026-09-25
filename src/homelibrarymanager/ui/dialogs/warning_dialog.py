"""List the problems found in the catalogue files, then let the user in.

Deliberately **not** an error box that blocks the program.  A mistyped line, a
record without an 作者 or a book pointing at a shelf that was deleted are all
things the user can fix from inside the app - or in Notepad - and refusing to
open the library over them would be far worse than the problems themselves.

The "create new files" offer is saved for the one case that genuinely needs it:
a file that cannot be decoded at all.  See :mod:`homelibrarymanager.services.startup`.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QLabel, QPlainTextEdit

from ..theme import Theme
from .base_dialog import FormDialog

MAX_SHOWN = 40


class WarningDialog(FormDialog):
    def __init__(
        self,
        theme: Theme,
        messages: Iterable[str],
        parent=None,
    ) -> None:
        super().__init__(theme, "数据文件有一些问题", "", parent, width=620)
        self._messages: List[str] = list(messages)

        shown = self._messages[:MAX_SHOWN]
        if len(self._messages) > MAX_SHOWN:
            shown.append(
                "…… 还有 {0} 条，未在此列出。".format(len(self._messages) - MAX_SHOWN)
            )

        lead = QLabel(
            "程序仍然可以正常使用，以下问题不会导致数据丢失。\n"
            "你可以在程序里修改，也可以直接用记事本编辑文件。"
        )
        lead.setObjectName("BodyText")
        lead.setWordWrap(True)
        self.form.addRow(lead)

        listing = QPlainTextEdit()
        listing.setReadOnly(True)
        listing.setPlainText("\n".join(shown))
        listing.setFixedHeight(190)
        self.form.addRow(listing)

        # A single acknowledgement: there is nothing to decide here.
        self.cancel_button.hide()
        self.save_button.setText("继续")
        self.save_button.setDefault(True)
        self.save_button.setFocus(Qt.OtherFocusReason)

    # -- FormDialog hooks ------------------------------------------------

    def _on_save(self) -> None:
        self.accept()

    def _on_delete(self) -> None:  # pragma: no cover - that button is hidden
        self.reject()

    def messages(self) -> List[str]:
        return list(self._messages)
