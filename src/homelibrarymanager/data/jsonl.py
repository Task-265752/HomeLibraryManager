"""Line-oriented JSON reading and writing, tuned for hand editing.

Two Windows-specific details drive the codec, and both are needed for the
"can be opened in Notepad" requirement to actually hold on Windows 7:

* **UTF-8 with BOM.**  Notepad on Windows 7 does not detect UTF-8 without a
  byte-order mark.  It falls back to the system ANSI code page (GBK on a
  Chinese system) and renders Chinese text as mojibake.  Windows 10 1903+
  fixed this, but this project targets Windows 7 and newer.
* **CRLF line endings.**  Windows 7 Notepad only understands CRLF; a file
  using bare LF is displayed as one enormous single line.

The reader is deliberately forgiving, because the file is expected to be edited
by hand: blank lines are ignored, a malformed line costs only that one record,
and a file saved by Notepad as ANSI is still read correctly (with a warning).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from ..config import BACKUP_SUFFIX, FILE_FORMAT, FILE_FORMAT_VERSION
from ..core.errors import DataFileError, ParseIssue

#: Writing with ``utf-8-sig`` emits a BOM; reading with it consumes a BOM if
#: present and otherwise behaves like plain UTF-8.
ENCODING = "utf-8-sig"

#: Notepad may re-save the file as ANSI.  ``gb18030`` is a superset of GBK and
#: decodes those bytes without losing anything on a Chinese system.
FALLBACK_ENCODINGS: Sequence[str] = ("gb18030",)

#: Reserved keys for the first line, which records the format and version so a
#: future release can migrate the file.  Their absence is not an error.
HEADER_FORMAT_KEY = "_format"
HEADER_VERSION_KEY = "_version"

_JSON_ERROR_HINTS = (
    ("Expecting ',' delimiter", "缺少逗号，或引号没有正确配对"),
    ("Expecting property name enclosed in double quotes", "字段名必须用双引号括起来"),
    ("Unterminated string starting at", "字符串缺少结束引号"),
    ("Invalid control character", "字符串里有非法控制字符"),
    ("Expecting value", "冒号后面缺少值"),
    ("Extra data", "这一行有多个 JSON 对象，每行只能有一个"),
    ("Expecting ':' delimiter", "字段名后面缺少冒号"),
)


def _explain(error: ValueError) -> str:
    """Turn a json module message into something a non-programmer can act on."""
    # Position 0 means the line does not begin with a value at all, which is
    # what happens when a stray sentence or a note gets typed into the file.
    # The generic hints below would describe that as a missing colon, sending
    # the user to look for a colon that was never the problem.
    if getattr(error, "pos", None) == 0:
        return "这一行不是有效的 JSON"
    text = str(error)
    for needle, hint in _JSON_ERROR_HINTS:
        if needle in text:
            return hint
    return "不是合法的 JSON（{0}）".format(text)


@dataclass
class ReadResult:
    records: List[Dict[str, Any]] = field(default_factory=list)
    #: 1-based file line number for each entry in ``records``, kept in step so
    #: validation messages can point the user at the exact line to fix.
    lines: List[int] = field(default_factory=list)
    issues: List[ParseIssue] = field(default_factory=list)
    encoding: str = ENCODING
    encoding_warning: str = ""
    header_seen: bool = False


def _decode(data: bytes, path: Path) -> tuple:
    """Decode as UTF-8 (BOM optional), falling back to GBK with a warning."""
    if not data:
        return "", ENCODING, ""
    try:
        return data.decode(ENCODING), ENCODING, ""
    except UnicodeDecodeError:
        pass
    for encoding in FALLBACK_ENCODINGS:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        warning = (
            "文件不是 UTF-8 编码，已按 {0} 读取。"
            "建议用记事本“另存为”并选择 UTF-8，否则中文可能显示错乱。".format(encoding)
        )
        return text, encoding, warning
    raise DataFileError(
        "文件编码无法识别（既不是 UTF-8 也不是 GBK）。"
        "请用记事本打开后“另存为”，编码选择 UTF-8。",
        path,
    )


def read_records(path: Union[str, Path]) -> ReadResult:
    """Parse one JSON object per line, collecting problems instead of raising."""
    path = Path(path)
    result = ReadResult()
    if not path.exists():
        return result

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise DataFileError("无法读取数据文件：{0}".format(exc), path)

    text, encoding, warning = _decode(payload, path)
    result.encoding = encoding
    result.encoding_warning = warning

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except ValueError as exc:
            result.issues.append(ParseIssue(path, number, line, _explain(exc)))
            continue
        if not isinstance(value, dict):
            result.issues.append(ParseIssue(path, number, line, "每行必须是一个 JSON 对象"))
            continue
        if HEADER_FORMAT_KEY in value:
            result.header_seen = True
            continue
        result.records.append(value)
        result.lines.append(number)
    return result


def make_header() -> Dict[str, Any]:
    return {HEADER_FORMAT_KEY: FILE_FORMAT, HEADER_VERSION_KEY: FILE_FORMAT_VERSION}


def write_records(
    path: Union[str, Path],
    records: Sequence[Mapping[str, Any]],
    *,
    backup: bool = True,
    write_header: bool = True,
) -> Optional[Path]:
    """Atomically replace ``path`` with one JSON object per line.

    Writing goes to a temporary file in the same folder which is then renamed
    over the target.  A crash or power cut therefore leaves either the old file
    or the new one, never a half-written catalogue.

    Returns the backup path when a backup was taken.
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DataFileError("无法创建数据目录：{0}".format(exc), path)

    backup_path: Optional[Path] = None
    if backup and path.exists():
        candidate = path.with_name(path.name + BACKUP_SUFFIX)
        try:
            shutil.copy2(str(path), str(candidate))
            backup_path = candidate
        except OSError:
            # A missing backup is not worth failing the save over.
            backup_path = None

    payload: List[Mapping[str, Any]] = []
    if write_header:
        payload.append(make_header())
    payload.extend(records)

    tmp_path: Optional[Path] = None
    try:
        handle_fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        # newline="\r\n" makes Python emit CRLF, which Windows 7 Notepad needs.
        with os.fdopen(handle_fd, "w", encoding=ENCODING, newline="\r\n") as handle:
            for record in payload:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp_path), str(path))
        tmp_path = None
    except OSError as exc:
        raise DataFileError("保存数据文件失败：{0}".format(exc), path)
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return backup_path
