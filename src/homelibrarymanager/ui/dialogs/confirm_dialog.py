"""A yes/no gate in front of anything that destroys data.

Derives from :class:`FormDialog`, so it matches the catalogue forms exactly
rather than looking like a borrowed system dialog.

Two deliberate safety choices:

* the confirm button carries the **danger** style, so it can never be mistaken
  for 保存 in a hurry;
* **取消 is the default button**, so pressing Enter out of habit cancels rather
  than deletes.  In a form, Enter meaning "save" is helpful; in a destructive
  prompt it is a trap.
"""

from __future__ import annotations

from typing import Optional

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QDialog, QLabel, QWidget

from ..theme import Theme
from .base_dialog import FormDialog


class ConfirmDialog(FormDialog):
    def __init__(
        self,
        theme: Theme,
        title: str,
        message: str,
        detail: str = "",
        confirm_text: str = "确认删除",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, title, "", parent)

        body = QLabel(message)
        body.setObjectName("BodyText")
        body.setWordWrap(True)
        self.form.addRow(body)

        if detail:
            note = QLabel(detail)
            note.setObjectName("DialogHint")
            note.setWordWrap(True)
            self.form.addRow(note)

        # Re-purpose the standard button row: the confirm action takes the
        # right-hand slot (where 保存 normally sits) but wears the danger style.
        self.delete_button.hide()
        self.save_button.setText(confirm_text)
        self.save_button.setObjectName("DangerButton")
        self.save_button.setDefault(False)
        style = self.save_button.style()
        style.unpolish(self.save_button)
        style.polish(self.save_button)

        self.cancel_button.setDefault(True)
        self.cancel_button.setFocus(Qt.OtherFocusReason)

    # -- FormDialog hooks ------------------------------------------------

    def _on_save(self) -> None:
        self.accept()

    def _on_delete(self) -> None:  # pragma: no cover - that button is hidden
        self.reject()

    # -- convenience -----------------------------------------------------

    @classmethod
    def ask(
        cls,
        parent: Optional[QWidget],
        theme: Theme,
        title: str,
        message: str,
        detail: str = "",
        confirm_text: str = "确认删除",
    ) -> bool:
        """Show the prompt and return True only if the user confirmed."""
        dialog = cls(theme, title, message, detail, confirm_text, parent)
        return dialog.exec_() == QDialog.Accepted
