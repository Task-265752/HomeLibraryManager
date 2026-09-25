"""Asked before a shelf that still holds books is deleted.

The project owner made 书架 a required field on a book.  So deleting a shelf
cannot simply clear it on its books: that would leave records the program would
flag as invalid the very next time the file was read.  The user has to say where
the books go - onto another shelf, or out of the catalogue with the shelf.

Either way nothing is lost silently, and the destructive choice is spelled out
with the number of books it affects.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QWidget,
)

from ...core.models import Shelf
from ..theme import Theme
from .base_dialog import FormDialog


class ShelfDeleteDialog(FormDialog):
    def __init__(
        self,
        theme: Theme,
        shelf: Shelf,
        book_count: int,
        other_shelves: Sequence[str] = (),
        parent=None,
    ) -> None:
        super().__init__(theme, "删除书架", "", parent)
        self._other: List[str] = list(other_shelves)
        self._move_to = ""
        self._delete_books = False

        body = QLabel(
            "书架“{0}”上还有 {1} 本书。\n请决定这些书怎么办：".format(
                shelf.display_name, book_count
            )
        )
        body.setObjectName("BodyText")
        body.setWordWrap(True)
        self.form.addRow(body)

        self.group = QButtonGroup(self)

        self.move_radio = QRadioButton("移到其他书架：")
        self.shelf_combo = QComboBox()
        self.shelf_combo.addItems(self._other)

        move_row = QHBoxLayout()
        move_row.setSpacing(8)
        move_row.addWidget(self.move_radio)
        move_row.addWidget(self.shelf_combo, 1)
        move_widget = QWidget()
        move_widget.setLayout(move_row)
        self.form.addRow(move_widget)

        self.delete_radio = QRadioButton(
            "连同这 {0} 本书一起删除".format(book_count)
        )
        self.form.addRow(self.delete_radio)

        self.group.addButton(self.move_radio)
        self.group.addButton(self.delete_radio)

        if self._other:
            self.move_radio.setChecked(True)
        else:
            # Nothing to move to, so the only way forward is deleting the books.
            self.move_radio.setEnabled(False)
            self.shelf_combo.setEnabled(False)
            self.delete_radio.setChecked(True)

        self.save_button.setText("确认删除")

    # -- results ---------------------------------------------------------

    def move_to(self) -> str:
        """Destination shelf, or ``""`` when the books are to be deleted."""
        if self.move_radio.isChecked():
            return self.shelf_combo.currentText()
        return ""

    def delete_books(self) -> bool:
        return self.delete_radio.isChecked()

    # -- FormDialog hooks ------------------------------------------------

    def _on_save(self) -> None:
        if self.move_radio.isChecked() and not self.shelf_combo.currentText():
            self.set_error("请选择一个目标书架。")
            return
        self._move_to = self.move_to()
        self._delete_books = self.delete_books()
        self.accept()

    def _on_delete(self) -> None:  # pragma: no cover - the base hides it
        self.reject()
