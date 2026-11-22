#!/usr/bin/env python3
"""Validate addon manifests against the Cartshelf addon spec.

Usage:
    python tools/validate_addon.py my.addon.json [more.addon.json ...]

Exit status is 1 when any file has errors. Warnings never fail the run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from addonlib import validate_bytes  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help="manifest files to check")
    parser.add_argument("--platforms", type=Path, default=ROOT / "spec" / "platforms.json", help="canonical platform list")
    parser.add_argument("--no-platforms", action="store_true", help="skip the canonical id check")
    args = parser.parse_args(argv)

    platforms = None if args.no_platforms else json.loads(args.platforms.read_text(encoding="utf-8"))
    failed = False
    for path in args.files:
        try:
            raw = path.read_bytes()
        except OSError as error:
            print(f"{path}: INVALID (cannot read the file: {error.strerror or error})")
            failed = True
            continue
        report = validate_bytes(raw, platforms)
        status = "OK" if report.ok else "INVALID"
        print(f"{path}: {status} ({report.categories} categories, {report.consoles} consoles, {report.collections} collections)")
        for message in report.errors:
            print(f"  error:   {message}")
        for message in report.warnings:
            print(f"  warning: {message}")
        failed = failed or not report.ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
