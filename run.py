#!/usr/bin/env python3
"""Development launcher.

    .venv\\Scripts\\python.exe run.py

Equivalent to ``python -m homelibrarymanager`` but works from a checkout
without setting PYTHONPATH.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from homelibrarymanager.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
