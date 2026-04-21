#!/usr/bin/env python3

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".viewer_builder" / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from viewer_builder.build import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
