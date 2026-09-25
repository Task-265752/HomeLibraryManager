"""Shared chrome for the four catalogue dialogs.

添加图书 / 编辑图书 / 添加书架 / 编辑书架 all inherit from :class:`FormDialog`,
so they do not merely *look* alike - they cannot drift apart.  One set of
margins, one title style, one required-field marker, one place for the error
message, one button row.  A subclass supplies the fields and says what to do
when 保存 or 删除 is pressed, and nothing else.

Required fields are marked with a red asterisk placed by :meth:`add_field`, so
the marker cannot be forgotten on one form and present on another.
"""

from __future__ import annotations

from typing import Optional

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..theme import Theme

#: The asterisk is drawn as rich text so it can be red while the label stays
#: muted - a separate widget would disturb the form layout's column widths.
_MARK = '<span style="color:{color}; font-weight:700;">*</span>'


class FormDialog(QDialog):
    """Base class for every form in the program."""

    def __init__(
        self,
        theme: Theme,
        title: str,
        hint: str = "",
        parent: Optional[QWidget] = None,
        width: int = 470,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._deleted = False

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self._build(title, hint)

    # -- construction ----------------------------------------------------

    def _build(self, title: str, hint: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        outer.addWidget(heading)

        if hint:
            note = QLabel(hint)
            note.setObjectName("DialogHint")
            note.setWordWrap(True)
            outer.addWidget(note)

        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.form.setHorizontalSpacing(16)
        self.form.setVerticalSpacing(10)
        self.form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        outer.addLayout(self.form)

        self.error = QLabel("")
        self.error.setObjectName("ErrorText")
        self.error.setWordWrap(True)
        self.error.hide()
        outer.addWidget(self.error)

        outer.addSpacing(6)
        outer.addLayout(self._build_buttons())

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("DangerButton")
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.clicked.connect(self._on_delete)
        self.delete_button.hide()
        row.addWidget(self.delete_button)

        row.addStretch(1)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)
        row.addWidget(self.cancel_button)

        self.save_button = QPushButton("保存")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_save)
        row.addWidget(self.save_button)

        return row

    # -- fields ----------------------------------------------------------

    def add_field(self, label_text: str, widget: QWidget, required: bool = False) -> QWidget:
        """Add a labelled row.  ``required`` draws the red asterisk."""
        label = QLabel()
        label.setTextFormat(Qt.RichText)
        label.setObjectName("FieldLabel")
        if required:
            label.setText(
                "{0} {1}".format(label_text, _MARK.format(color=self._theme.danger))
            )
        else:
            label.setText(label_text)
        self.form.addRow(label, widget)
        return widget

    def add_wide_field(self, label_text: str, widget: QWidget) -> QWidget:
        """A field that spans both columns - used for multi-line 备注."""
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        self.form.addRow(label)
        self.form.addRow(widget)
        return widget

    def enter_saves(self, *widgets: QWidget) -> None:
        """Make Enter in a single-line field trigger 保存."""
        for widget in widgets:
            entered = getattr(widget, "returnPressed", None)
            if entered is not None:
                entered.connect(self._on_save)

    def enable_delete(self, text: str = "删除") -> None:
        self.delete_button.setText(text)
        self.delete_button.show()

    # -- messages --------------------------------------------------------

    def set_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()
        self.adjustSize()

    def clear_error(self) -> None:
        self.error.clear()
        self.error.hide()

    # -- results ---------------------------------------------------------

    @property
    def deleted(self) -> bool:
        """True when the user asked to delete rather than save."""
        return self._deleted

    # -- to be provided by subclasses ------------------------------------

    def _on_save(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _on_delete(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError
