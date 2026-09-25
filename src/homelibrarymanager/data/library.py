"""The catalogue: ``books.jsonl`` plus ``shelves.jsonl``, loaded together.

A book points at its shelf by *name* (``Book.shelf``) rather than by an opaque
id, which keeps both files readable in Notepad.  The cost is that the two files
can disagree, and that renaming a shelf has to touch both - so this module
provides :meth:`Library.rename_shelf` to do it in one place, and treats
disagreement as a display problem rather than an error.

Loading never discards anything a human typed.  A malformed line costs that one
line; a record missing a required field is kept and reported with its file line
number so the user can jump straight to it in Notepad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from ..config import (
    BOOKS_FILENAME,
    SHELVES_FILENAME,
    UNFILED_SHELF_NAME,
    UNPLACED_SHELF_NAME,
)
from ..core.errors import ParseIssue, ValidationProblem
from ..core.models import Book, Shelf
from .jsonl import ReadResult, read_records, write_records

SHELF_KIND = "书架"
BOOK_KIND = "书目"


@dataclass
class LoadReport:
    """Everything the UI needs to know about how a load went."""

    books_path: Path
    shelves_path: Path
    books_issues: List[ParseIssue] = field(default_factory=list)
    shelves_issues: List[ParseIssue] = field(default_factory=list)
    books_problems: List[ValidationProblem] = field(default_factory=list)
    shelves_problems: List[ValidationProblem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    books_file_missing: bool = False
    shelves_file_missing: bool = False
    duplicate_shelf_names: List[str] = field(default_factory=list)
    duplicate_shelf_sequences: List[str] = field(default_factory=list)
    #: Titles of books whose ``shelf`` names a shelf that does not exist.
    orphan_book_titles: List[str] = field(default_factory=list)
    #: Record counts, so the messages below can describe the situation.
    shelf_count: int = 0
    book_count: int = 0

    @property
    def issue_count(self) -> int:
        return len(self.books_issues) + len(self.shelves_issues)

    @property
    def problem_count(self) -> int:
        return len(self.books_problems) + len(self.shelves_problems)

    @property
    def has_problems(self) -> bool:
        return bool(
            self.issue_count
            or self.problem_count
            or self.warnings
            or self.duplicate_shelf_names
            or self.duplicate_shelf_sequences
            or self.orphan_book_titles
        )

    def all_messages(self) -> List[str]:
        """Every problem, phrased for display, in file order."""
        messages = [issue.describe() for issue in self.shelves_issues]
        messages.extend(problem.describe() for problem in self.shelves_problems)
        messages.extend(issue.describe() for issue in self.books_issues)
        messages.extend(problem.describe() for problem in self.books_problems)
        # Only report a missing file when the result is genuinely inconsistent.
        # Having books but no shelf file means every book loses its location,
        # which the user needs to know about.  The reverse - a shelf file with
        # no book file - is just "added a shelf, no books yet", and warning
        # about it on every launch would be pure noise.
        if self.shelves_file_missing and self.book_count:
            messages.append(
                "没有找到书架文件 {0}，{1} 本书的所属书架无法确认，"
                "它们会显示在“{2}”里".format(
                    SHELVES_FILENAME, self.book_count, UNFILED_SHELF_NAME
                )
            )
        if self.duplicate_shelf_names:
            messages.append(
                "书架名称重复：{0}（书目按名称指向书架，重名会让指向变得不明确）".format(
                    "、".join(self.duplicate_shelf_names)
                )
            )
        if self.duplicate_shelf_sequences:
            messages.append(
                "书架序号重复：{0}".format("、".join(self.duplicate_shelf_sequences))
            )
        if self.orphan_book_titles:
            messages.append(
                "有 {0} 本书指向了不存在的书架，已暂归“{1}”：{2}".format(
                    len(self.orphan_book_titles),
                    UNFILED_SHELF_NAME,
                    "、".join(self.orphan_book_titles[:10])
                    + ("…" if len(self.orphan_book_titles) > 10 else ""),
                )
            )
        return messages

    def describe(self) -> str:
        """One-line summary suitable for a status bar."""
        parts: List[str] = []
        if self.issue_count:
            parts.append("{0} 行无法解析".format(self.issue_count))
        if self.problem_count:
            parts.append("{0} 条缺少必填项".format(self.problem_count))
        if self.orphan_book_titles:
            parts.append("{0} 本书的书架不存在".format(len(self.orphan_book_titles)))
        if self.duplicate_shelf_names:
            parts.append("书架重名：{0}".format("、".join(self.duplicate_shelf_names)))
        if self.duplicate_shelf_sequences:
            parts.append("书架序号重复：{0}".format("、".join(self.duplicate_shelf_sequences)))
        if self.warnings:
            parts.append(self.warnings[0])
        return "；".join(parts) if parts else "数据文件读取正常"


def _validate(record, line_number: int, kind: str, path: Path) -> Optional[ValidationProblem]:
    missing = record.missing_required()
    if not missing:
        return None
    return ValidationProblem(
        path=path,
        line_number=line_number,
        kind=kind,
        message="缺少必填项：{0}".format("、".join(missing)),
    )


class Library:
    """An in-memory catalogue backed by two files on disk."""

    def __init__(self, directory: Union[str, Path]) -> None:
        self.directory = Path(directory)
        self.books_path = self.directory / BOOKS_FILENAME
        self.shelves_path = self.directory / SHELVES_FILENAME
        self.books: List[Book] = []
        self.shelves: List[Shelf] = []
        self.last_report: Optional[LoadReport] = None

    # -- loading ---------------------------------------------------------

    def load(self) -> LoadReport:
        report = LoadReport(books_path=self.books_path, shelves_path=self.shelves_path)

        self.shelves, shelves_result = self._load_file(
            self.shelves_path, Shelf.from_record, SHELF_KIND, report.shelves_problems
        )
        report.shelves_issues = shelves_result.issues
        report.shelves_file_missing = not self.shelves_path.exists()
        if shelves_result.encoding_warning:
            report.warnings.append("书架文件：" + shelves_result.encoding_warning)

        self.books, books_result = self._load_file(
            self.books_path, Book.from_record, BOOK_KIND, report.books_problems
        )
        report.books_issues = books_result.issues
        report.books_file_missing = not self.books_path.exists()
        if books_result.encoding_warning:
            report.warnings.append("书目文件：" + books_result.encoding_warning)

        report.duplicate_shelf_names = self.duplicate_shelf_names()
        report.duplicate_shelf_sequences = self.duplicate_shelf_sequences()
        report.orphan_book_titles = [book.display_title for book in self.orphan_books()]
        report.shelf_count = len(self.shelves)
        report.book_count = len(self.books)
        self.last_report = report
        return report

    def _load_file(self, path, factory, kind: str, problems: List[ValidationProblem]):
        """Read one file once; return the records and the raw read result."""
        result: ReadResult = read_records(path)
        records = []
        for raw, line_number in zip(result.records, result.lines):
            record = factory(raw)
            records.append(record)
            problem = _validate(record, line_number, kind, path)
            if problem is not None:
                problems.append(problem)
        return records, result

    # -- saving ----------------------------------------------------------

    def save(self) -> None:
        self.save_shelves()
        self.save_books()

    def save_books(self, backup: bool = True) -> Optional[Path]:
        return write_records(
            self.books_path, [book.to_record() for book in self.books], backup=backup
        )

    def save_shelves(self, backup: bool = True) -> Optional[Path]:
        return write_records(
            self.shelves_path, [shelf.to_record() for shelf in self.shelves], backup=backup
        )

    def ensure_files_exist(self) -> None:
        """Create empty catalogue files so a first run has something to open."""
        if not self.shelves_path.exists():
            self.save_shelves(backup=False)
        if not self.books_path.exists():
            self.save_books(backup=False)

    # -- queries ---------------------------------------------------------

    def shelf_by_name(self, name: str) -> Optional[Shelf]:
        for shelf in self.shelves:
            if shelf.name == name:
                return shelf
        return None

    def shelf_names(self) -> List[str]:
        return [shelf.name for shelf in self.shelves if shelf.name]

    def sorted_shelf_names(self) -> List[str]:
        """Shelf names in 序号 order - the order the sidebar shows them in.

        The book dialog's shelf picker uses this rather than insertion order, so
        the two lists agree.  Otherwise picking "the second shelf" in the dialog
        could mean something different from the second row in the sidebar.
        """
        return [shelf.name for shelf in self.sorted_shelves()]

    def sorted_shelves(self) -> List[Shelf]:
        """Shelves in 序号 order - '2' before '10', not after it."""
        return sorted(self.shelves, key=lambda shelf: (shelf.sort_key, shelf.name))

    def sorted_books(self) -> List[Book]:
        return sorted(self.books, key=lambda book: (book.sort_key, book.author))

    def duplicate_shelf_names(self) -> List[str]:
        return _duplicates(shelf.name for shelf in self.shelves)

    def duplicate_shelf_sequences(self) -> List[str]:
        return _duplicates(shelf.sequence for shelf in self.shelves)

    # -- which book sits where -------------------------------------------

    def books_on_shelf(self, name: str) -> List[Book]:
        return [book for book in self.books if book.shelf == name]

    def orphan_books(self) -> List[Book]:
        """Books pointing at a shelf that does not exist.

        Never fatal: they are shown under the virtual 未归档 shelf so the user
        can see them and correct the name, instead of having them disappear.
        """
        known = set(self.shelf_names())
        return [book for book in self.books if book.shelf and book.shelf not in known]

    def unplaced_books(self) -> List[Book]:
        """Books with no shelf value at all - simply not put anywhere yet."""
        return [book for book in self.books if not book.shelf]

    def group_by_shelf(self) -> Dict[str, List[Book]]:
        """Shelf name -> books, keyed in 序号 order.

        Unknown shelves collapse into 未归档 and shelfless books into 未上架, so
        the totals always add up and nothing silently disappears.
        """
        groups: Dict[str, List[Book]] = {shelf.name: [] for shelf in self.sorted_shelves()}
        for book in self.books:
            if not book.shelf:
                key = UNPLACED_SHELF_NAME
            elif book.shelf in groups:
                key = book.shelf
            else:
                key = UNFILED_SHELF_NAME
            groups.setdefault(key, []).append(book)
        return groups

    def shelf_summary(self) -> List[Tuple[str, int]]:
        """(shelf name, book count) in 序号 order, for a shelf list panel."""
        return [(shelf.name, len(self.books_on_shelf(shelf.name))) for shelf in self.sorted_shelves()]

    def incomplete_records(self) -> List[object]:
        """Records currently missing a required field, for a UI warning list."""
        return [shelf for shelf in self.shelves if shelf.missing_required()] + [
            book for book in self.books if book.missing_required()
        ]

    # -- mutation --------------------------------------------------------

    def add_book(self, book: Book) -> Book:
        self.books.append(book)
        return book

    def add_shelf(self, shelf: Shelf) -> Shelf:
        self.shelves.append(shelf)
        return shelf

    def rename_shelf(self, old_name: str, new_name: str) -> int:
        """Rename a shelf and repoint every book.  Returns books updated.

        This is the price of storing shelf *names* in the book file: a rename
        has to touch both files at once.  Keeping the catalogue readable in
        Notepad is worth having one function that does that correctly - and the
        alternative (a book silently pointing at a shelf that no longer exists)
        is exactly the failure this prevents.
        """
        shelf = self.shelf_by_name(old_name)
        if shelf is None:
            raise KeyError("找不到书架：{0}".format(old_name))
        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("书架名称不能为空")
        if new_name != old_name and self.shelf_by_name(new_name) is not None:
            raise ValueError("已存在同名书架：{0}".format(new_name))

        shelf.name = new_name
        moved = 0
        for book in self.books:
            if book.shelf == old_name:
                book.shelf = new_name
                moved += 1
        return moved

    def delete_shelf(
        self, name: str, move_to: str = "", delete_books: bool = False
    ) -> int:
        """Remove a shelf, deciding what happens to the books standing on it.

        书架 is a required field on a book, so a shelf cannot simply be removed
        and its books left pointing nowhere: the program would flag them as
        invalid the next time the file was read.  The caller must therefore say
        either where the books go (``move_to``) or that they go too
        (``delete_books``).

        Returns the number of books that were moved or deleted.
        """
        shelf = self.shelf_by_name(name)
        if shelf is None:
            raise KeyError("找不到书架：{0}".format(name))
        if move_to and move_to == name:
            raise ValueError("不能把书移到正在删除的那个书架上")
        if move_to and self.shelf_by_name(move_to) is None:
            raise ValueError("目标书架不存在：{0}".format(move_to))

        affected = self.books_on_shelf(name)
        if affected and not move_to and not delete_books:
            raise ValueError(
                "“{0}”上还有 {1} 本书，请先指定它们的去向".format(name, len(affected))
            )

        if move_to:
            for book in affected:
                book.shelf = move_to
        elif delete_books:
            self.books = [book for book in self.books if book.shelf != name]

        self.shelves.remove(shelf)
        return len(affected)

    def remove_book(self, book: Book) -> bool:
        try:
            self.books.remove(book)
            return True
        except ValueError:
            return False

    def remove_shelf(self, shelf: Shelf) -> bool:
        try:
            self.shelves.remove(shelf)
            return True
        except ValueError:
            return False


def _duplicates(values: Iterable[str]) -> List[str]:
    seen = {}
    for value in values:
        if value:
            seen[value] = seen.get(value, 0) + 1
    return sorted(value for value, count in seen.items() if count > 1)


# --------------------------------------------------------------------------
# Starting a fresh catalogue
# --------------------------------------------------------------------------


def archive_existing_files(
    directory: Union[str, Path], stamp: Optional[str] = None
) -> List[Tuple[Path, Path]]:
    """Rename existing catalogue files out of the way.  **Never deletes.**

    "Create a new file" is the most destructive thing this program can offer,
    because what gets replaced is the user's whole library.  Renaming to
    ``books.jsonl.20260911-213000.bak`` costs a few kilobytes, so a mis-click
    is always recoverable.

    Returns the ``(old path, new path)`` pairs that were moved.
    """
    directory = Path(directory)
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    moved: List[Tuple[Path, Path]] = []
    for name in (BOOKS_FILENAME, SHELVES_FILENAME):
        source = directory / name
        if not source.exists():
            continue
        target = directory / "{0}.{1}.bak".format(name, stamp)
        suffix = 1
        while target.exists():
            target = directory / "{0}.{1}.bak{2}".format(name, stamp, suffix)
            suffix += 1
        source.rename(target)
        moved.append((source, target))
    return moved


def create_fresh_catalogue(
    directory: Union[str, Path], archive_existing: bool = True
) -> Tuple["Library", List[Tuple[Path, Path]]]:
    """Start an empty catalogue in ``directory``.

    Existing files are archived rather than removed; pass
    ``archive_existing=False`` only when the folder is already known to be
    clean, otherwise the user's library is destroyed by a single click.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    archived = archive_existing_files(directory) if archive_existing else []
    library = Library(directory)
    library.shelves = []
    library.books = []
    library.save_shelves(backup=False)
    library.save_books(backup=False)
    return library, archived
