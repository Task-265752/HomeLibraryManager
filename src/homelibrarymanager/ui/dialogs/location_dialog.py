"""Choose the folder that holds the catalogue.

Shown **only on a first run, or when the remembered folder has lost its files** -
never on every launch, because being asked the same question each time is the
most annoying thing a small program can do.

Whatever is chosen is remembered in ``settings.ini``, so the next launch goes
straight to the main window.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ...config import is_writable
from ..theme import Theme
from .base_dialog import FormDialog


class LocationDialog(FormDialog):
    def __init__(
        self,
        theme: Theme,
        directory: Path,
        reason: str = "",
        parent=None,
    ) -> None:
        super().__init__(
            theme,
            "选择数据保存位置",
            "书目和书架文件会保存在这个文件夹里，可以整个文件夹拷到 U 盘带走。",
            parent,
            width=560,
        )
        self._directory: Optional[Path] = None

        if reason:
            why = QLabel(reason)
            why.setObjectName("DialogHint")
            why.setWordWrap(True)
            self.form.addRow(why)

        self.path_edit = QLineEdit(str(directory))
        self.path_edit.setPlaceholderText("例如：D:\\我的图书")
        self.path_edit.setMinimumWidth(320)

        browse = QPushButton("浏览…")
        browse.setObjectName("SecondaryButton")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse)

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.path_edit, 1)
        layout.addWidget(browse)

        self.add_field("数据文件夹", row, required=True)

        note = QLabel(
            "文件夹里还没有 {0} / {1} 的话，程序会自动创建。".format(
                "books.jsonl", "shelves.jsonl"
            )
        )
        note.setObjectName("DialogHint")
        note.setWordWrap(True)
        self.form.addRow(note)

        self.save_button.setText("开始使用")
        self.path_edit.returnPressed.connect(self._on_save)
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    # -- actions ---------------------------------------------------------

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "选择数据文件夹", self.path_edit.text().strip() or str(Path.home())
        )
        if chosen:
            self.path_edit.setText(chosen)

    def _on_save(self) -> None:
        text = self.path_edit.text().strip()
        if not text:
            self.set_error("请选择或填写数据文件夹。")
            return

        candidate = Path(text).expanduser()
        if not is_writable(candidate):
            self.set_error(
                "这个位置无法写入（可能没有权限，或所在磁盘不可写）。请换一个文件夹。"
            )
            return

        self._directory = candidate
        self.accept()

    # -- result ----------------------------------------------------------

    def directory(self) -> Optional[Path]:
        return self._directory
