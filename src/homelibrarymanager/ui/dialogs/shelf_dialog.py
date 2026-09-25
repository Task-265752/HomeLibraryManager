"""添加书架 / 编辑书架.

Fields and rules come from the project owner's specification.  This class only
supplies the widgets; the chrome (title, required asterisks, error line, button
row) comes from :class:`FormDialog`, and the rules come from
:func:`~homelibrarymanager.services.validation.build_shelf`.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from PySide2.QtWidgets import QLineEdit, QPlainTextEdit

from ...core.models import Shelf
from ...services.validation import build_shelf
from ..theme import Theme
from .base_dialog import FormDialog
from .confirm_dialog import ConfirmDialog


class ShelfDialog(FormDialog):
    def __init__(
        self,
        theme: Theme,
        shelf: Optional[Shelf] = None,
        existing_names: Iterable[str] = (),
        book_count: int = 0,
        parent=None,
    ) -> None:
        editing = shelf is not None
        super().__init__(
            theme,
            "编辑书架" if editing else "添加书架",
            "带 * 的是必填项。书架序号可以填数字、字母或汉字。",
            parent,
        )

        self._editing = shelf
        self._book_count = book_count
        self._result: Optional[Shelf] = None
        # A shelf may keep its own name while being edited, so drop it from the
        # list of names that would count as a clash.
        self._taken: List[str] = [
            name for name in existing_names if name != (shelf.name if shelf else None)
        ]

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：客厅书架")
        self.name_edit.setMaxLength(60)

        self.sequence_edit = QLineEdit()
        self.sequence_edit.setPlaceholderText("例如：1 / A-01 / 客厅")
        self.sequence_edit.setMaxLength(40)

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("选填。例如：客厅东墙，靠窗")
        self.note_edit.setFixedHeight(72)

        self.add_field("书架名称", self.name_edit, required=True)
        self.add_field("书架序号", self.sequence_edit, required=True)
        self.add_wide_field("介绍说明", self.note_edit)
        self.enter_saves(self.name_edit, self.sequence_edit)

        if shelf is not None:
            self.name_edit.setText(shelf.name)
            self.sequence_edit.setText(shelf.sequence)
            self.note_edit.setPlainText(shelf.note)
            self.enable_delete("删除这个书架")

        self.name_edit.setFocus()

    # -- results ---------------------------------------------------------

    def shelf(self) -> Optional[Shelf]:
        """The validated shelf, or ``None`` when cancelled or deleting."""
        return self._result

    # -- FormDialog hooks ------------------------------------------------

    def _on_save(self) -> None:
        try:
            self._result = build_shelf(
                self.name_edit.text(),
                self.sequence_edit.text(),
                self.note_edit.toPlainText(),
                existing_names=self._taken,
            )
        except ValueError as exc:
            self.set_error(str(exc))
            return
        self.accept()

    def _on_delete(self) -> None:
        if self._book_count:
            # A shelf with books needs more than a yes/no: the books have to go
            # somewhere.  MainWindow asks that in ShelfDeleteDialog, which is
            # itself the confirmation - prompting here as well would make the
            # user answer twice for one action.
            self._deleted = True
            self.accept()
            return

        if not ConfirmDialog.ask(
            self,
            self._theme,
            "删除书架",
            "确定要删除书架“{0}”吗？".format(self._editing.display_name),
            "这个书架是空的，删除后无法撤销。",
        ):
            return
        self._deleted = True
        self.accept()
