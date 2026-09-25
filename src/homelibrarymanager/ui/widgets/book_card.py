"""One book drawn as a card, matching the layout in the sketch.

    ┌──────────────────────────────────────────┐
    │ 罪全书                        ISBN：9787… │
    │ 作者：蜘蛛                出版日期：2008年 │
    └──────────────────────────────────────────┘

The card has a fixed size so the grid stays tidy, which means long titles have
to be elided rather than allowed to stretch it.
"""

from __future__ import annotations

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QFrame, QGridLayout, QSizePolicy

from ...core.models import Book
from ..theme import Theme
from .elided_label import ElidedLabel

#: Shown in place of an optional field the user has not filled in, so the card
#: reads as "nothing recorded" rather than looking broken.
EMPTY = "—"


class BookCard(QFrame):
    """A clickable summary of one book."""

    clicked = Signal(object)
    activated = Signal(object)

    def __init__(
        self, book: Book, theme: Theme, show_shelf: bool = False, parent=None
    ) -> None:
        super().__init__(parent)
        self.book = book
        self._theme = theme
        # Only worth showing in the 全部书目 view, where the cards are mixed
        # together and the shelf is exactly what the user is looking for.
        self._show_shelf = show_shelf

        self.setObjectName("BookCard")
        self.setProperty("selected", False)
        self.setFixedSize(theme.book_card_width, theme.book_card_height)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(self._tooltip())
        self._build()

    # -- construction ----------------------------------------------------

    def _build(self) -> None:
        grid = QGridLayout(self)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(3)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        # The sketch puts the ISBN beside the title, but a real 13-digit ISBN
        # does not fit in a right-hand column of a card this size - it was
        # eliding to "97875...".  Giving it a full-width row of its own keeps
        # the whole number readable, which is the only reason to show it.
        title = self._label(self.book.display_title, "BookCardTitle", Qt.AlignLeft)
        author = self._label(
            "作者：" + (self.book.author or EMPTY), "BookCardMeta", Qt.AlignLeft
        )
        published = self._label(
            "出版：" + (self.book.published or EMPTY), "BookCardMeta", Qt.AlignRight
        )
        isbn = self._label(
            "ISBN：" + (self.book.isbn or EMPTY), "BookCardMeta", Qt.AlignLeft
        )

        grid.addWidget(title, 0, 0, 1, 1 if self._show_shelf else 2)
        if self._show_shelf:
            grid.addWidget(
                self._label(
                    "书架：" + (self.book.shelf or EMPTY), "BookCardMeta", Qt.AlignRight
                ),
                0,
                1,
            )
        grid.addWidget(author, 1, 0)
        grid.addWidget(published, 1, 1)
        grid.addWidget(isbn, 2, 0, 1, 2)

    def _label(self, text: str, object_name: str, alignment) -> ElidedLabel:
        label = ElidedLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(alignment | Qt.AlignVCenter)
        # Ignored means "let the layout decide, elide instead of pushing out".
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        return label

    def _tooltip(self) -> str:
        book = self.book
        rows = [
            ("书名", book.title),
            ("作者", book.author),
            ("译者", book.translator),
            ("ISBN", book.isbn),
            ("出版时间", book.published),
            ("书架", book.shelf),
            ("备注", book.note),
        ]
        lines = ["{0}：{1}".format(label, value) for label, value in rows if value]
        for key, value in book.extra.items():
            lines.append("{0}：{1}".format(key, value))
        return "\n".join(lines)

    # -- state -----------------------------------------------------------

    def set_selected(self, selected: bool) -> None:
        """Toggle the highlight, re-polishing so the QSS rule takes effect."""
        selected = bool(selected)
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    # -- interaction -----------------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802 - Qt naming
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.book)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.book)
        super().mouseDoubleClickEvent(event)
