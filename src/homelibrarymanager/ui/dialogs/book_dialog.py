"""添加图书 / 编辑图书.

The shelf is a combo box rather than a text field, because the project owner
made it required and a typed-in shelf that does not exist would land the book
under 未归档 the moment the file was read back.  It defaults to whichever shelf
is currently open, which is almost always the answer.

编辑图书 can also delete, which is why the destructive button is separated to
the far left of the button row.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from PySide2.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QSizePolicy

from ...core.models import Book
from ...services.validation import build_book
from ..theme import Theme
from .base_dialog import FormDialog
from .confirm_dialog import ConfirmDialog

#: Shown in the shelf combo when no shelf is open, so the user has to choose.
#: Used by the 全部书目 view, where there is no "current shelf" to default to.
SHELF_PLACEHOLDER = "请选择书架"


class BookDialog(FormDialog):
    def __init__(
        self,
        theme: Theme,
        book: Optional[Book] = None,
        shelf_names: Iterable[str] = (),
        default_shelf: str = "",
        parent=None,
    ) -> None:
        editing = book is not None
        super().__init__(
            theme,
            "编辑图书" if editing else "添加图书",
            "带 * 的是必填项。",
            parent,
            width=500,
        )

        self._editing = book
        self._shelf_names: List[str] = list(shelf_names)
        self._result: Optional[Book] = None

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("必填")
        self.title_edit.setMaxLength(200)

        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("必填")
        self.author_edit.setMaxLength(200)

        self.shelf_combo = QComboBox()
        # The "choose one" row is always present, so a default that no longer
        # matches any shelf cannot silently fall back to whichever shelf happens
        # to sit at index 0.  That fallback used to file books under the wrong
        # shelf without telling anyone.
        self.shelf_combo.addItem(SHELF_PLACEHOLDER)
        self.shelf_combo.addItems(self._shelf_names)
        # Without this the combo hugs its longest entry and looks unlike every
        # other field in the form.
        self.shelf_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.translator_edit = QLineEdit()
        self.translator_edit.setPlaceholderText("选填")
        self.translator_edit.setMaxLength(200)

        self.isbn_edit = QLineEdit()
        self.isbn_edit.setPlaceholderText("选填，例如 9787536692930")
        self.isbn_edit.setMaxLength(40)

        self.published_edit = QLineEdit()
        self.published_edit.setPlaceholderText("选填，例如 2008 / 2008-01 / 2008年5月")
        self.published_edit.setMaxLength(40)

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("选填")
        self.note_edit.setFixedHeight(64)

        # Required fields are grouped at the top so the two that must be filled
        # in are the first thing the eye lands on.
        self.add_field("书名", self.title_edit, required=True)
        self.add_field("作者", self.author_edit, required=True)
        self.add_field("书架", self.shelf_combo, required=True)
        self.add_field("译者", self.translator_edit)
        self.add_field("ISBN书号", self.isbn_edit)
        self.add_field("出版时间", self.published_edit)
        self.add_wide_field("备注", self.note_edit)
        self.enter_saves(self.title_edit, self.author_edit, self.translator_edit,
                         self.isbn_edit, self.published_edit)

        self._populate(book, default_shelf)
        if book is not None:
            self.enable_delete("删除这本书")
        self.title_edit.setFocus()

    def _populate(self, book: Optional[Book], default_shelf: str) -> None:
        if book is not None:
            self.title_edit.setText(book.title)
            self.author_edit.setText(book.author)
            self.translator_edit.setText(book.translator)
            self.isbn_edit.setText(book.isbn)
            self.published_edit.setText(book.published)
            self.note_edit.setPlainText(book.note)
            target = book.shelf or default_shelf
        else:
            target = default_shelf

        # findText("") matches nothing, which is what we want: an unset target
        # leaves the placeholder selected so 保存 reports "请选择一个书架".
        # That also covers editing a book whose shelf was removed from the file
        # by hand - it must ask rather than quietly move the book elsewhere.
        index = self.shelf_combo.findText(target) if target else -1
        self.shelf_combo.setCurrentIndex(index if index >= 0 else 0)

    # -- results ---------------------------------------------------------

    def book(self) -> Optional[Book]:
        """The validated book, or ``None`` when cancelled or deleting."""
        return self._result

    # -- FormDialog hooks ------------------------------------------------

    def _on_save(self) -> None:
        choice = self.shelf_combo.currentText()
        if choice == SHELF_PLACEHOLDER:
            self.set_error("请选择一个书架。")
            return
        try:
            self._result = build_book(
                self.title_edit.text(),
                self.author_edit.text(),
                choice,
                self.translator_edit.text(),
                self.isbn_edit.text(),
                self.published_edit.text(),
                self.note_edit.toPlainText(),
                shelf_names=self._shelf_names,
                existing=self._editing,
            )
        except ValueError as exc:
            self.set_error(str(exc))
            return
        self.accept()

    def _on_delete(self) -> None:
        # Confirmed here rather than after the dialog closes: that way a
        # last-second change of mind returns the user to the form with their
        # edits intact instead of throwing them away.
        if not ConfirmDialog.ask(
            self,
            self._theme,
            "删除图书",
            "确定要删除《{0}》吗？".format(self._editing.display_title),
            "删除后无法撤销，书目文件里对应的那一行会被移除。",
        ):
            return
        self._deleted = True
        self.accept()
