"""The left-hand list: 全部书目 plus every shelf.

The selected row is drawn as a filled pill with a small triangle pointing at the
book area, the way the sketch has it.  Qt item views leave custom drawing to a
delegate, so the look lives in :class:`ShelfItemDelegate` and every colour comes
from the active theme.

The first row is synthetic - it stands for "every book, whatever shelf" and
carries the sentinel :data:`ALL_BOOKS` instead of a :class:`Shelf`.  Storing a
string key for every row keeps the delegate unchanged, since it only ever reads
``DisplayRole`` and the count.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PySide2.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide2.QtGui import QColor, QFont, QFontMetrics, QPainter, QPolygon
from PySide2.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from ...core.models import Shelf
from ..theme import Theme

#: Width of the arrow that sticks out to the right of the selected pill.
TAIL_WIDTH = 15
#: Vertical breathing room above and below each pill.
ITEM_V_MARGIN = 3
COUNT_ROLE = Qt.UserRole + 1
SHELF_ROLE = Qt.UserRole + 2

#: Sentinel stored in ``Qt.UserRole`` for the "every book" row.  A plain string
#: rather than ``None`` so that ``None`` keeps meaning "nothing selected".
ALL_BOOKS = "__all_books__"

ALL_BOOKS_LABEL = "全部书目"


class ShelfItemDelegate(QStyledItemDelegate):
    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(0, self._theme.shelf_item_height)

    def paint(self, painter: QPainter, option, index) -> None:
        theme = self._theme
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        full = option.rect.adjusted(0, ITEM_V_MARGIN, 0, -ITEM_V_MARGIN)
        pill = QRect(
            full.left(), full.top(), max(0, full.width() - TAIL_WIDTH), full.height()
        )

        if selected:
            fill = QColor(theme.selection)
            outline = QColor(theme.selection)
            name_colour = QColor(theme.on_selection)
            count_colour = QColor(theme.on_primary_muted)
        else:
            fill = QColor(theme.card_hover if hovered else theme.surface)
            outline = QColor(theme.border)
            name_colour = QColor(theme.text)
            count_colour = QColor(theme.text_faint)

        painter.setBrush(fill)
        painter.setPen(outline)
        painter.drawRoundedRect(pill.adjusted(0, 0, -1, -1), theme.radius, theme.radius)

        font = QFont(painter.font())
        font.setPointSize(theme.body_pt)
        font.setBold(selected)
        painter.setFont(font)

        # The count is right-aligned, so reserve room for it before eliding the
        # name - otherwise a long shelf name is drawn straight over the number.
        count = index.data(COUNT_ROLE)
        count_text = "{0} 本".format(count) if count else ""
        count_width = QFontMetrics(font).horizontalAdvance(count_text) if count_text else 0
        name_area = pill.adjusted(13, 0, -13 - (count_width + 10 if count_text else 0), 0)

        painter.setPen(name_colour)
        metrics = QFontMetrics(font)
        name = metrics.elidedText(
            str(index.data(Qt.DisplayRole) or ""), Qt.ElideRight, max(0, name_area.width())
        )
        painter.drawText(name_area, Qt.AlignLeft | Qt.AlignVCenter, name)

        if count_text:
            count_font = QFont(font)
            count_font.setPointSize(theme.small_pt)
            count_font.setBold(False)
            painter.setFont(count_font)
            painter.setPen(count_colour)
            painter.drawText(
                pill.adjusted(0, 0, -13, 0), Qt.AlignRight | Qt.AlignVCenter, count_text
            )

        if selected:
            middle = pill.center().y()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.selection))
            painter.drawPolygon(
                QPolygon(
                    [
                        QPoint(pill.right() - 2, middle - 8),
                        QPoint(pill.right() - 2, middle + 8),
                        QPoint(full.right(), middle),
                    ]
                )
            )

        painter.restore()


class ShelfPanel(QWidget):
    """全部书目 + the shelf list, plus the 添加书架 button."""

    #: Emitted with a shelf *name*, or :data:`ALL_BOOKS`.
    selection_changed = Signal(str)
    add_shelf_requested = Signal()

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setObjectName("Sidebar")
        # Plain QWidget subclasses need this before a stylesheet background is
        # honoured; see the same note in HeaderBar.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(theme.sidebar_width)
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 16, 14, 16)
        outer.setSpacing(10)

        title = QLabel("书架")
        title.setObjectName("SidebarTitle")
        outer.addWidget(title)

        self.list = QListWidget()
        self.list.setObjectName("ShelfList")
        self.list.setItemDelegate(ShelfItemDelegate(self._theme, self.list))
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(True)
        self.list.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.list.currentItemChanged.connect(self._on_current_changed)
        outer.addWidget(self.list, 1)

        self.add_button = QPushButton("＋　添加书架")
        self.add_button.setObjectName("AddShelfButton")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setFixedHeight(44)
        self.add_button.clicked.connect(self.add_shelf_requested)
        outer.addWidget(self.add_button)

    # -- contents --------------------------------------------------------

    def set_shelves(
        self,
        shelves: Iterable[Shelf],
        counts: Optional[Dict[str, int]] = None,
        selected: str = "",
        total_books: int = 0,
    ) -> None:
        """Rebuild the list, restoring the selection where possible."""
        counts = counts or {}
        wanted = selected or self.selection()

        self.list.blockSignals(True)
        self.list.clear()

        all_item = QListWidgetItem(ALL_BOOKS_LABEL)
        all_item.setData(Qt.UserRole, ALL_BOOKS)
        all_item.setData(COUNT_ROLE, total_books)
        all_item.setToolTip(
            "显示所有书架上的全部书目，共 {0} 本".format(total_books)
        )
        self.list.addItem(all_item)

        for shelf in shelves:
            item = QListWidgetItem(shelf.display_name)
            item.setData(Qt.UserRole, shelf.name)
            item.setData(SHELF_ROLE, shelf)
            item.setData(COUNT_ROLE, counts.get(shelf.name, 0))
            item.setToolTip(
                "{0}\n序号：{1}\n书目：{2} 本{3}".format(
                    shelf.display_name,
                    shelf.sequence or "—",
                    counts.get(shelf.name, 0),
                    "\n说明：" + shelf.note if shelf.note else "",
                )
            )
            self.list.addItem(item)

        # Pick the row while signals are still blocked, then announce the result
        # exactly once, so a rebuild cannot produce a burst of updates.
        if not (wanted and self.select(wanted)):
            self.select_first()
        self.list.blockSignals(False)
        self.selection_changed.emit(self.selection())

    def select(self, key: str) -> bool:
        """Select by shelf name or :data:`ALL_BOOKS`."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.UserRole) == key:
                self.list.setCurrentItem(item)
                return True
        return False

    def select_first(self) -> None:
        """Land on the first real shelf; fall back to 全部书目 when there is none."""
        if self.list.count() > 1:
            self.list.setCurrentRow(1)
        elif self.list.count():
            self.list.setCurrentRow(0)

    def select_all_books(self) -> None:
        self.select(ALL_BOOKS)

    # -- current selection -----------------------------------------------

    def selection(self) -> str:
        """The shelf name, :data:`ALL_BOOKS`, or ``""`` when nothing is selected."""
        item = self.list.currentItem()
        if item is None:
            return ""
        return item.data(Qt.UserRole) or ""

    def selected_shelf(self) -> Optional[Shelf]:
        item = self.list.currentItem()
        return item.data(SHELF_ROLE) if item is not None else None

    def selected_name(self) -> str:
        shelf = self.selected_shelf()
        return shelf.name if shelf is not None else ""

    def is_all_books(self) -> bool:
        return self.selection() == ALL_BOOKS

    def _on_current_changed(self, current, previous) -> None:
        self.selection_changed.emit(self.selection())
