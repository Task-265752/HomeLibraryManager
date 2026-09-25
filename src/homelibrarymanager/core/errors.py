"""Error types shared across the application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class HomeLibraryManagerError(Exception):
    """Base class so callers can catch everything this program raises."""


class DataFileError(HomeLibraryManagerError):
    """A catalogue file could not be read or written.

    Carries a message written for a non-technical reader, because these end up
    in a dialog box rather than in a log nobody looks at.
    """

    def __init__(self, message: str, path: Path = None) -> None:  # type: ignore[assignment]
        super().__init__(message)
        self.message = message
        self.path = path


@dataclass(frozen=True)
class ParseIssue:
    """One line that could not be understood.

    We keep reading after a bad line instead of abandoning the whole file, so a
    single typo made in Notepad costs the user one record rather than the
    entire catalogue.
    """

    path: Path
    line_number: int
    raw: str
    message: str

    def describe(self) -> str:
        snippet = self.raw.strip()
        if len(snippet) > 60:
            snippet = snippet[:57] + "..."
        return "第 {0} 行：{1}（内容：{2}）".format(
            self.line_number, self.message, snippet or "空"
        )


@dataclass(frozen=True)
class ValidationProblem:
    """A record that parsed fine but breaks a rule, e.g. a blank 作者.

    The record is *not* discarded - losing something the user just typed would
    be worse than showing it with a warning - so this only ever reports.
    """

    path: Path
    line_number: int
    kind: str
    message: str

    def describe(self) -> str:
        return "{0}文件第 {1} 行：{2}".format(self.kind, self.line_number, self.message)
