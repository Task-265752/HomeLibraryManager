"""A ⋯ button whose three dots are painted rather than typed.

Typing the ellipsis character puts the dots on the font's baseline, so inside a
square button they read as "sitting low" instead of centred - and exactly how
low depends on which font the platform picked, which is why padding cannot fix
it.  Drawing the dots at the true centre makes the button identical in every
theme and on every platform.

The button's background still comes from the stylesheet: ``paintEvent`` asks the
style to draw ``CE_PushButton`` first, so ``#ActionButton`` keeps working and a
custom theme only has to supply colours.
"""

from __future__ import annotations

from PySide2.QtCore import QPointF, Qt
from PySide2.QtGui import QColor, QPainter
from PySide2.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter


class DotsButton(QPushButton):
    def __init__(
        self,
        colour: str,
        disabled_colour: str = "",
        parent=None,
        dot_radius: float = 2.0,
        dot_gap: float = 7.0,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ActionButton")
        self.setText("")  # drawn, never typed
        self._colour = colour
        self._disabled_colour = disabled_colour or colour
        self._dot_radius = dot_radius
        self._dot_gap = dot_gap

    def paintEvent(self, event):  # noqa: N802 - Qt naming
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        # Blank the (already empty) text so nothing is drawn over the dots if a
        # style decides to render a label anyway.
        option.text = ""
        painter.drawControl(QStyle.CE_PushButton, option)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(
            QColor(self._colour if self.isEnabled() else self._disabled_colour)
        )

        # Half-integer width/height keep the outer dots symmetric about the
        # centre rather than one pixel off.
        centre_x = self.width() / 2.0
        centre_y = self.height() / 2.0
        for offset in (-self._dot_gap, 0.0, self._dot_gap):
            painter.drawEllipse(
                QPointF(centre_x + offset, centre_y), self._dot_radius, self._dot_radius
            )
        painter.end()
