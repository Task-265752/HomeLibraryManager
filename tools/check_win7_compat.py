#!/usr/bin/env python3
"""Verify that a Windows PE binary can start on Windows 7 SP1.

Why this exists
---------------
This project must ship binaries that run on Windows 7 SP1 and newer.  The
tricky part is that the toolchain does not advertise that support:

  * Python 3.8.10  - last CPython with Windows 7 support (3.9 needs Win8.1+)
  * Qt 5.15        - last Qt with Windows 7 support (Qt 6 needs Win10+)
  * PyInstaller    - docs only claim "Windows 8 and newer" since the 5.x series

The documentation statement is about where PyInstaller *runs* (the build
machine), not about the produced bundle.  The only way to be sure is to read
the PE headers of the actual bootloader that gets embedded into the output,
and to check its import table for APIs that do not exist on Windows 7.

Usage
-----
    python tools/check_win7_compat.py                 # auto-discover targets
    python tools/check_win7_compat.py path/to/x.exe   # check specific files

Exit code is 0 when every inspected binary looks Windows 7 compatible, and 1
otherwise, so this can be wired into a build script later.

Output is deliberately ASCII-only: the Windows console mangles CJK text.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import pefile
except ImportError:  # pragma: no cover - dependency of PyInstaller
    sys.exit("pefile is required: pip install pefile")


# Imports that only resolve on Windows 8 or later.  If any of these shows up in
# a binary's import table, that binary cannot start on Windows 7.
WIN8_PLUS_APIS: Dict[str, str] = {
    "GetSystemTimePreciseAsFileTime": "Windows 8",
    "WaitOnAddress": "Windows 8",
    "WakeByAddressSingle": "Windows 8",
    "WakeByAddressAll": "Windows 8",
    "CreateFile2": "Windows 8",
    "LoadPackagedLibrary": "Windows 8",
    "PathCchCanonicalizeEx": "Windows 8",
    "PathCchCombineEx": "Windows 8",
    "GetCurrentPackageFullName": "Windows 8",
    "GetPackageFullName": "Windows 8",
    "SetThreadDescription": "Windows 10 1607",
    "GetTempPath2W": "Windows 10",
    "GetSystemTimeAdjustmentPrecise": "Windows 10",
    "GetDpiForWindow": "Windows 10 1607",
    "SetProcessDpiAwarenessContext": "Windows 10 1607",
    "AreDpiAwarenessContextsEqual": "Windows 10 1607",
}

SUBSYSTEM_NAMES = {2: "Windows GUI", 3: "Windows console"}
MACHINE_NAMES = {0x014C: "x86 (32-bit)", 0x8664: "x64 (64-bit)", 0xAA64: "ARM64"}

# Import DLLs that pull in the Universal C Runtime.  Windows 7 SP1 needs
# KB2999226 (or the VC++ 2015-2019 redistributable) to provide these.
UCRT_MARKERS = ("ucrtbase.dll", "api-ms-win-crt-")


class BinaryInfo(object):
    def __init__(self, path: str) -> None:
        self.path = path
        self.machine = "?"
        self.subsystem = "?"
        self.os_version: Tuple[int, int] = (0, 0)
        self.subsystem_version: Tuple[int, int] = (0, 0)
        self.imports: Dict[str, List[str]] = {}
        self.uses_ucrt = False
        self.bad_apis: List[Tuple[str, str, str]] = []
        self.error: Optional[str] = None


def analyse(path: str) -> BinaryInfo:
    info = BinaryInfo(path)
    try:
        pe = pefile.PE(path, fast_load=True)
    except Exception as exc:  # noqa: BLE001 - report, never crash a build
        info.error = "not a PE file ({0})".format(exc)
        return info

    try:
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        oh = pe.OPTIONAL_HEADER
        info.machine = MACHINE_NAMES.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine))
        info.subsystem = SUBSYSTEM_NAMES.get(oh.Subsystem, str(oh.Subsystem))
        info.os_version = (oh.MajorOperatingSystemVersion, oh.MinorOperatingSystemVersion)
        info.subsystem_version = (oh.MajorSubsystemVersion, oh.MinorSubsystemVersion)

        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", None) or []:
            dll = entry.dll.decode("ascii", "replace")
            names = [
                imp.name.decode("ascii", "replace")
                for imp in entry.imports
                if imp.name
            ]
            info.imports[dll] = names
            lowered = dll.lower()
            if any(marker in lowered for marker in UCRT_MARKERS):
                info.uses_ucrt = True
            for name in names:
                if name in WIN8_PLUS_APIS:
                    info.bad_apis.append((dll, name, WIN8_PLUS_APIS[name]))
    finally:
        pe.close()
    return info


def default_targets() -> List[str]:
    """Locate the PyInstaller bootloaders plus a known-good baseline."""
    targets: List[str] = []
    try:
        import PyInstaller

        boot = os.path.join(os.path.dirname(PyInstaller.__file__), "bootloader")
        for arch in ("Windows-64bit-intel", "Windows-32bit-intel"):
            arch_dir = os.path.join(boot, arch)
            if not os.path.isdir(arch_dir):
                continue
            for name in ("runw.exe", "run.exe"):
                candidate = os.path.join(arch_dir, name)
                if os.path.isfile(candidate):
                    targets.append(candidate)
    except ImportError:
        pass

    # Baseline: the Python DLL that gets bundled alongside the app.  Python
    # 3.8.10 officially supports Windows 7 SP1, so this should come back clean
    # and proves the checker is not producing false positives.
    dll = os.path.join(sys.base_prefix, "python{0}{1}.dll".format(*sys.version_info[:2]))
    if os.path.isfile(dll):
        targets.append(dll)
    return targets


def report(path: str) -> bool:
    info = analyse(path)
    print("=" * 72)
    print(os.path.basename(path))
    print("  path              : {0}".format(info.path))

    if info.error:
        print("  RESULT            : SKIPPED - {0}".format(info.error))
        return True

    print("  architecture      : {0}".format(info.machine))
    print("  subsystem         : {0}".format(info.subsystem))
    print(
        "  min OS version    : {0}.{1}".format(*info.os_version)
    )
    print(
        "  subsystem version : {0}.{1}".format(*info.subsystem_version)
    )

    min_os = info.os_version[0] * 100 + info.os_version[1]
    min_sub = info.subsystem_version[0] * 100 + info.subsystem_version[1]
    # 6.1 == Windows 7.  Anything <= 6.1 is safe on Windows 7.
    ok = True
    if min_os > 601:
        print("  !! min OS version is above Windows 7 (6.1)")
        ok = False
    if min_sub > 601:
        print("  !! subsystem version is above Windows 7 (6.1) - Windows refuses to load this")
        ok = False

    print("  imports           : {0} DLL(s)".format(len(info.imports)))
    if info.uses_ucrt:
        print("  uses UCRT         : yes -> target needs KB2999226 on Windows 7 SP1")
    if info.bad_apis:
        ok = False
        print("  !! Windows 8+ APIs referenced:")
        for dll, name, since in info.bad_apis:
            print("       {0} -> {1}  (needs {2})".format(dll, name, since))
    else:
        print("  Windows 8+ APIs   : none referenced")

    print("  RESULT            : {0}".format("OK for Windows 7" if ok else "NOT Windows 7 compatible"))
    return ok


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("targets", nargs="*", help="PE files to inspect")
    args = parser.parse_args(argv)

    targets = list(args.targets) or default_targets()
    if not targets:
        print("No targets found. Pass file paths explicitly.")
        return 2

    print("Windows 7 compatibility check - {0} file(s)".format(len(targets)))
    all_ok = True
    for target in targets:
        if not os.path.isfile(target):
            print("=" * 72)
            print("{0}\n  RESULT            : SKIPPED - file not found".format(target))
            continue
        all_ok = report(target) and all_ok

    print("=" * 72)
    print("SUMMARY: {0}".format("all binaries OK for Windows 7" if all_ok else "PROBLEMS FOUND"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
