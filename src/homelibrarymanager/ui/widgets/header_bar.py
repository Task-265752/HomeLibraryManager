"""The blue bar across the top: product name, tagline and the search box.

The sketch stacks the title above the search box.  Putting them side by side
instead costs no width at 800px and buys back roughly 50px of vertical space,
which matters on the 800x600 floor the window has to support.
"""

from __future__ import annotations

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

from ...config import APP_NAME, APP_NAME_EN
from ..theme import Theme


class HeaderBar(QWidget):
    search_changed = Signal(str)

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setObjectName("HeaderBar")
        # A plain QWidget subclass ignores the "background" property from a
        # stylesheet unless it is told to paint a styled background - without
        # this the blue bar silently renders as nothing.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._build()

    def _build(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 14, 24, 14)
        outer.setSpacing(24)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(1)

        name = QLabel(APP_NAME)
        name.setObjectName("HeaderTitle")
        tagline = QLabel(APP_NAME_EN)
        tagline.setObjectName("HeaderSubtitle")

        titles.addWidget(name)
        titles.addWidget(tagline)
        outer.addLayout(titles)
        outer.addStretch(1)

        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText("搜索书架、书目、作者、ISBN…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        self.search.setMaximumWidth(460)
        self.search.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.search.textChanged.connect(self.search_changed)
        outer.addWidget(self.search, 2)

    # -- convenience -----------------------------------------------------

    def query(self) -> str:
        return self.search.text()

    def clear(self) -> None:
        self.search.clear()

    def focus_search(self) -> None:
        self.search.setFocus(Qt.ShortcutFocusReason)
        self.search.selectAll()
