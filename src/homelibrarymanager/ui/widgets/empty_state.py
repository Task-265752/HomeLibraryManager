"""What the window shows when there is not a single shelf yet.

The project owner's rule: in that state the interface shows **only** a
"添加书架" button, so the user is never faced with an empty book area and a
control that cannot do anything.  The first shelf is also what turns the window
into its normal two-column layout.
"""

from __future__ import annotations

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..theme import Theme


class EmptyState(QWidget):
    add_shelf_requested = Signal()

    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)
        layout.addStretch(1)

        title = QLabel("还没有书架")
        title.setObjectName("EmptyStateTitle")
        title.setAlignment(Qt.AlignCenter)

        hint = QLabel("先建一个书架，就可以往里放书了。\n书架名称和书架序号是必填的。")
        hint.setObjectName("EmptyStateHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)

        button = QPushButton("添加书架")
        button.setObjectName("PrimaryButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumWidth(160)
        button.clicked.connect(self.add_shelf_requested)

        button_row = QVBoxLayout()
        button_row.addWidget(button, 0, Qt.AlignHCenter)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(8)
        layout.addLayout(button_row)
        layout.addStretch(2)
