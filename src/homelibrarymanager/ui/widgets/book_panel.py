"""The right-hand area: the selected shelf's books as wrapping cards.

The two rounded buttons float over the bottom-right corner rather than sitting
in a toolbar, matching the sketch.  They are children of this widget and are
repositioned in ``resizeEvent``, so they stay pinned to the corner at any window
size without a layout slot of their own.

Empty states go through a ``QStackedWidget`` - swapping pages is cleaner than
trying to centre a message inside a flow layout, which positions items strictly
left to right.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.models import Book, Shelf
from ..theme import Theme
from .book_card import BookCard
from .dots_button import DotsButton
from .flow_layout import FlowLayout

PAGE_CARDS = 0
PAGE_MESSAGE = 1


class BookPanel(QWidget):
    add_book_requested = Signal()
    more_requested = Signal()
    book_selected = Signal(object)
    book_activated = Signal(object)

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._cards: List[BookCard] = []
        self._selected: Optional[Book] = None
        self._shelf: Optional[Shelf] = None

        self.setObjectName("BookPanel")
        # Plain QWidget subclasses need this before a stylesheet background is
        # honoured; see the same note in HeaderBar.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build()

    # -- construction ----------------------------------------------------

    def _build(self) -> None:
        theme = self._theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            theme.space_large, theme.space_large, theme.space_large, theme.space_large
        )
        outer.setSpacing(theme.space)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(10)
        self.heading = QLabel("")
        self.heading.setObjectName("ShelfHeading")
        self.subheading = QLabel("")
        self.subheading.setObjectName("ShelfSubheading")
        heading_row.addWidget(self.heading)
        heading_row.addWidget(self.subheading)
        heading_row.addStretch(1)
        outer.addLayout(heading_row)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # -- page: cards in a scroll area
        self.scroll = QScrollArea()
        self.scroll.setObjectName("BookScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.canvas = QWidget()
        self.canvas.setObjectName("BookCanvas")
        self.flow = FlowLayout(
            self.canvas, margin=0, h_spacing=theme.space, v_spacing=theme.space
        )
        self.scroll.setWidget(self.canvas)
        self.stack.addWidget(self.scroll)

        # -- page: a centred message
        message_page = QWidget()
        message_layout = QVBoxLayout(message_page)
        message_layout.setContentsMargins(0, 0, 0, 0)
        message_layout.addStretch(1)
        self.message = QLabel("")
        self.message.setObjectName("PlaceholderText")
        self.message.setAlignment(Qt.AlignCenter)
        self.message.setWordWrap(True)
        message_layout.addWidget(self.message)
        message_layout.addStretch(1)
        self.stack.addWidget(message_page)

        # -- floating actions
        size = theme.action_button
        self.add_button = self._action_button("＋", "添加图书")
        self.add_button.clicked.connect(self.add_book_requested)

        # The three dots are painted rather than typed; see DotsButton.
        self.more_button = DotsButton(
            theme.on_primary, theme.surface, self
        )
        self.more_button.setFixedSize(size, size)
        self.more_button.setCursor(Qt.PointingHandCursor)
        self.more_button.setToolTip("更多操作：编辑书架 / 编辑图书")
        self.more_button.clicked.connect(self.more_requested)

    def _action_button(self, text: str, tooltip: str) -> QPushButton:
        size = self._theme.action_button
        button = QPushButton(text, self)
        button.setObjectName("ActionButton")
        button.setFixedSize(size, size)
        button.setCursor(Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        return button

    def resizeEvent(self, event):  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._position_actions()

    def _position_actions(self) -> None:
        theme = self._theme
        size = theme.action_button
        margin = theme.space_large
        right = self.width() - margin - size
        bottom = self.height() - margin - size

        self.more_button.move(right, bottom)
        self.add_button.move(right - theme.space - size, bottom)
        self.add_button.raise_()
        self.more_button.raise_()

    # -- content ---------------------------------------------------------

    def show_shelf(self, shelf: Optional[Shelf], books: Iterable[Book]) -> None:
        books = list(books)
        self._shelf = shelf
        self.show_books(
            shelf.display_name if shelf is not None else "",
            "{0} 本".format(len(books)) if shelf is not None else "",
            books,
        )
        if not books:
            self.show_message("这个书架还是空的\n点右下角的 ＋ 添加第一本书")

    def show_all_books(self, books: Iterable[Book]) -> None:
        """Every book in the catalogue, whatever shelf each one is on."""
        books = list(books)
        self._shelf = None
        self.show_books("全部书目", "{0} 本".format(len(books)), books, show_shelf=True)
        if not books:
            self.show_message("书目还是空的\n点右下角的 ＋ 添加第一本书")

    def show_books(
        self,
        heading: str,
        subheading: str,
        books: Iterable[Book],
        show_shelf: bool = False,
    ) -> None:
        books = list(books)
        self.heading.setText(heading)
        self.subheading.setText(subheading)
        self._selected = None
        self._rebuild(books, show_shelf=show_shelf)

    def show_results(self, message: str, books: Iterable[Book]) -> None:
        """Used while a search is active - results span every shelf."""
        books = list(books)
        self._shelf = None
        self.show_books("搜索结果", message, books, show_shelf=True)
        if not books:
            self.show_message("没有找到匹配的书目\n换个关键词试试")

    def show_message(self, text: str) -> None:
        self.message.setText(text)
        self.stack.setCurrentIndex(PAGE_MESSAGE)

    def show_cards(self) -> None:
        self.stack.setCurrentIndex(PAGE_CARDS)

    def _rebuild(self, books: List[Book], show_shelf: bool = False) -> None:
        # Take the old cards out of the layout and hand them to deleteLater().
        # Deliberately NOT setParent(None): that turns each card into a
        # top-level window, and Qt creates a native window for it before the
        # deferred delete arrives.  Keeping the parent lets Qt destroy them
        # cleanly on the next event loop pass.
        for card in self._cards:
            self.flow.removeWidget(card)
            card.hide()
            card.deleteLater()
        self._cards = []

        for book in books:
            card = BookCard(book, self._theme, show_shelf=show_shelf, parent=self.canvas)
            card.clicked.connect(self._on_card_clicked)
            card.activated.connect(self.book_activated)
            card.show()
            self.flow.addWidget(card)
            self._cards.append(card)

        # Adding items to a layout only *asks* for a re-layout.  If the canvas
        # keeps the same size - which is exactly what happens when switching
        # between two shelves holding a similar number of books - that request
        # can be satisfied without the flow layout ever being run, and every new
        # card stays at (0, 0) stacked on top of the others.  That is what made
        # a shelf look like it had lost a book: the heading said "2 本" while
        # only the topmost card was visible.  Activating forces the geometry to
        # be applied straight away.
        self.canvas.updateGeometry()
        self.flow.invalidate()
        self.flow.activate()
        self._position_actions()
        if self._cards:
            self.show_cards()

    # -- selection -------------------------------------------------------

    def _on_card_clicked(self, book: Book) -> None:
        self.select_book(book)
        self.book_selected.emit(book)

    def select_book(self, book: Optional[Book]) -> None:
        self._selected = book
        for card in self._cards:
            card.set_selected(card.book is book)

    def selected_book(self) -> Optional[Book]:
        return self._selected

    def set_actions_enabled(self, enabled: bool) -> None:
        self.add_button.setEnabled(enabled)
        self.more_button.setEnabled(enabled and self._selected is not None)

    def card_count(self) -> int:
        return len(self._cards)
