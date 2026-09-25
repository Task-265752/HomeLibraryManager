"""The application window.

Structure, top to bottom:

    ┌──────────────────────────────────────────────────────────┐
    │ HeaderBar  家庭图书管理系统 / Home Library Manager + 搜索 │
    ├────────────┬─────────────────────────────────────────────┤
    │ ShelfPanel │ BookPanel                                   │
    │  (书架列表) │  书架标题 + 卡片流，右下角悬浮 ＋ / …        │
    └────────────┴─────────────────────────────────────────────┘

When the catalogue holds no shelves at all, the body is swapped for
:class:`EmptyState`, which shows only the 添加书架 button - the project owner's
rule for the first run.
"""

from __future__ import annotations

from typing import Optional

from PySide2.QtCore import QByteArray, QPoint, Qt
from PySide2.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QShortcut,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide2.QtGui import QKeySequence

from ..config import (
    APP_NAME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
)
from ..data.library import Library
from ..data.settings import Settings
from ..services.search import search
from .dpi import initial_window_size
from .dialogs.book_dialog import BookDialog
from .dialogs.shelf_delete_dialog import ShelfDeleteDialog
from .dialogs.shelf_dialog import ShelfDialog
from .theme import Theme, get_theme
from .widgets.book_panel import BookPanel
from .widgets.empty_state import EmptyState
from .widgets.header_bar import HeaderBar
from .widgets.shelf_panel import ALL_BOOKS, ShelfPanel

PAGE_EMPTY = 0
PAGE_COLUMNS = 1


class MainWindow(QMainWindow):
    def __init__(
        self,
        library: Library,
        settings: Optional[Settings] = None,
        theme: Optional[Theme] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.settings = settings
        self.theme = theme or get_theme()
        #: Shelf name or ALL_BOOKS - which row of the sidebar is open.
        self._selection = ""

        self._build()
        self._restore_geometry()
        self.refresh()

    # -- construction ----------------------------------------------------

    def _build(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        width, height = initial_window_size(
            DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT
        )
        self.resize(width, height)

        root = QWidget()
        root.setObjectName("RootSurface")
        # See the note in HeaderBar: without this a stylesheet background on a
        # plain QWidget is ignored.
        root.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = HeaderBar(self.theme)
        self.header.search_changed.connect(self._on_search)
        outer.addWidget(self.header)

        self.body = QStackedWidget()
        outer.addWidget(self.body, 1)

        self.empty_state = EmptyState(self.theme)
        self.empty_state.add_shelf_requested.connect(self.add_shelf)
        self.body.addWidget(self.empty_state)

        self.columns = QWidget()
        columns = QHBoxLayout(self.columns)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)

        self.shelf_panel = ShelfPanel(self.theme)
        self.shelf_panel.selection_changed.connect(self._on_selection_changed)
        self.shelf_panel.add_shelf_requested.connect(self.add_shelf)
        columns.addWidget(self.shelf_panel)

        self.book_panel = BookPanel(self.theme)
        self.book_panel.add_book_requested.connect(self.add_book)
        self.book_panel.more_requested.connect(self._on_more)
        self.book_panel.book_selected.connect(self._on_book_selected)
        self.book_panel.book_activated.connect(self.edit_book)
        columns.addWidget(self.book_panel, 1)

        self.body.addWidget(self.columns)

        QShortcut(QKeySequence.Find, self, activated=self.header.focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_shelf)

    # -- geometry --------------------------------------------------------

    def _restore_geometry(self) -> None:
        if self.settings is None:
            return
        encoded = (self.settings.geometry or "").strip()
        if not encoded:
            return
        try:
            self.restoreGeometry(QByteArray.fromBase64(encoded.encode("ascii")))
        except (ValueError, TypeError):
            # A corrupt value must never stop the window from opening.
            pass

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        if self.settings is not None:
            try:
                self.settings.geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
                self.settings.save()
            except (OSError, ValueError):
                pass
        super().closeEvent(event)

    # -- content ---------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the shelf list and the book area from :attr:`library`."""
        shelves = self.library.sorted_shelves()
        if not shelves:
            self.body.setCurrentIndex(PAGE_EMPTY)
            self._selection = ""
            return

        self.body.setCurrentIndex(PAGE_COLUMNS)
        counts = dict(self.library.shelf_summary())
        self.shelf_panel.set_shelves(
            shelves,
            counts,
            selected=self._selection,
            total_books=len(self.library.books),
        )
        # Update the book area directly rather than leaving it to the
        # selection_changed signal set_shelves emits.  The signal does reach it,
        # but that path runs inside a slot, where PySide2 swallows exceptions:
        # anything going wrong there would leave the book area showing stale
        # content with nothing on screen to say why.
        self._show_selection()

    def _show_selection(self) -> None:
        if self.shelf_panel.is_all_books():
            self.book_panel.show_all_books(self.library.sorted_books())
            return
        shelf = self.shelf_panel.selected_shelf()
        if shelf is not None:
            self.book_panel.show_shelf(shelf, self.library.books_on_shelf(shelf.name))

    def _follow(self, shelf_name: str) -> None:
        """Stay on 全部书目 if it is open, otherwise follow the changed book."""
        self._selection = ALL_BOOKS if self.shelf_panel.is_all_books() else shelf_name

    # -- signals ---------------------------------------------------------

    def _on_selection_changed(self, key: str) -> None:
        self._selection = key
        if self.header.query().strip():
            # A search is on screen; leave it alone rather than yanking the
            # results away because the user clicked something.
            return
        self._show_selection()

    def _on_book_selected(self, book) -> None:
        self.book_panel.set_actions_enabled(True)

    def _on_search(self, text: str) -> None:
        query = (text or "").strip()
        if not query:
            self._show_selection()
            return
        results = search(self.library, query)
        self.book_panel.show_results(results.describe(), results.books)

    # -- shelf actions ---------------------------------------------------

    def add_shelf(self) -> None:
        dialog = ShelfDialog(
            self.theme, existing_names=self.library.shelf_names(), parent=self
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        shelf = dialog.shelf()
        if shelf is None:
            return
        self.library.add_shelf(shelf)
        if self._save(self.library.save_shelves):
            self._selection = shelf.name
            self.refresh()

    def edit_shelf(self, shelf) -> None:
        if shelf is None:
            return
        dialog = ShelfDialog(
            self.theme,
            shelf=shelf,
            existing_names=self.library.shelf_names(),
            # Lets the dialog decide whether to confirm here or hand the books
            # over to ShelfDeleteDialog in MainWindow.
            book_count=len(self.library.books_on_shelf(shelf.name)),
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        if dialog.deleted:
            self._delete_shelf(shelf)
            return

        updated = dialog.shelf()
        if updated is None:
            return

        # A rename has to repoint every book that names this shelf, which is
        # what Library.rename_shelf exists for; the other two fields are a copy.
        if updated.name != shelf.name:
            self.library.rename_shelf(shelf.name, updated.name)
            self._selection = updated.name
        shelf.sequence = updated.sequence
        shelf.note = updated.note
        if self._save(self.library.save):
            self.refresh()

    def _delete_shelf(self, shelf) -> None:
        """Delete a shelf, first deciding what happens to the books on it.

        书架 is required on a book, so the books cannot simply be left behind
        pointing at nothing - the program would flag them on the next load.
        """
        books = self.library.books_on_shelf(shelf.name)
        others = [s.name for s in self.library.sorted_shelves() if s.name != shelf.name]

        move_to = ""
        delete_books = False
        if books:
            dialog = ShelfDeleteDialog(
                self.theme, shelf, len(books), other_shelves=others, parent=self
            )
            if dialog.exec_() != QDialog.Accepted:
                return
            move_to = dialog.move_to()
            delete_books = dialog.delete_books()

        try:
            self.library.delete_shelf(
                shelf.name, move_to=move_to, delete_books=delete_books
            )
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "无法删除", str(exc))
            return

        self._selection = move_to or (others[0] if others else "")
        if self._save(self.library.save):
            self.refresh()

    # -- book actions ----------------------------------------------------

    def add_book(self) -> None:
        if not self.library.shelves:
            QMessageBox.information(
                self, "添加图书", "还不能添加图书：请先建一个书架。"
            )
            return

        # In the 全部书目 view no shelf is open, so BookDialog shows an unset
        # combo and the user has to choose - which is the agreed behaviour.
        current = self.shelf_panel.selected_shelf()
        dialog = BookDialog(
            self.theme,
            shelf_names=self.library.sorted_shelf_names(),
            default_shelf=current.name if current is not None else "",
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        book = dialog.book()
        if book is None:
            return

        self.library.add_book(book)
        if self._save(self.library.save_books):
            self.header.clear()
            self._follow(book.shelf)
            self.refresh()

    def edit_book(self, book) -> None:
        if book is None:
            return
        dialog = BookDialog(
            self.theme, book=book, shelf_names=self.library.shelf_names(), parent=self
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        if dialog.deleted:
            self.library.remove_book(book)
            if self._save(self.library.save_books):
                self.refresh()
            return

        updated = dialog.book()
        if updated is None:
            return

        book.title = updated.title
        book.author = updated.author
        book.shelf = updated.shelf
        book.translator = updated.translator
        book.isbn = updated.isbn
        book.published = updated.published
        book.note = updated.note
        # build_book copies extra across, so hand-written fields survive an edit.
        book.extra = updated.extra

        if self._save(self.library.save):
            self.header.clear()
            self._follow(book.shelf)
            self.refresh()

    # -- the ⋯ menu -------------------------------------------------------

    def _on_more(self) -> None:
        """编辑书架 and 编辑图书 both live behind the three-dot button."""
        shelf = self.shelf_panel.selected_shelf()
        book = self.book_panel.selected_book()

        menu = QMenu(self)
        edit_shelf = menu.addAction("编辑当前书架…")
        edit_shelf.setEnabled(shelf is not None)
        edit_book = menu.addAction(
            "编辑选中图书…" if book is not None else "编辑图书（请先点选一本书）"
        )
        edit_book.setEnabled(book is not None)

        button = self.book_panel.more_button
        chosen = menu.exec_(button.mapToGlobal(QPoint(0, button.height() + 4)))

        if chosen is edit_shelf:
            self.edit_shelf(shelf)
        elif chosen is edit_book:
            self.edit_book(book)

    # -- helpers ---------------------------------------------------------

    def _save(self, operation) -> bool:
        """Persist, reporting failure instead of silently keeping the change."""
        try:
            operation()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            QMessageBox.warning(self, "保存失败", str(exc))
            return False
        return True
