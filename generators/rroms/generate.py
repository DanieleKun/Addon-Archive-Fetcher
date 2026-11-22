#!/usr/bin/env python3
"""Generates dist/rroms.addon.json from the public r/ROMs megathread site sources.

The generator only reads the megathread's own page sources and (with --verify) public Internet Archive
metadata. Nothing is downloaded and no file lists are copied: the output is a catalog of Internet Archive
item identifiers grouped by category and console, in the format described in docs/SPEC.md.

Usage:
    python generators/rroms/generate.py                       # read the live site, write dist/rroms.addon.json
    python generators/rroms/generate.py --verify              # also drop collections Internet Archive removed
    python generators/rroms/generate.py --source-dir DIR      # read a local copy of the site sources
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

from addonlib import validate_manifest  # noqa: E402
from classify import classify, fix_path, should_expand  # noqa: E402
from parse import SIDEBAR_PATH, parse_page, parse_sidebar  # noqa: E402

ADDON_ID = "rroms-megathread"
ADDON_NAME = "r/ROMs Megathread"
ADDON_DESCRIPTION = (
    "Internet Archive collections listed by the r/ROMs megathread, grouped by manufacturer and console. "
    "Contains only identifiers of public Internet Archive items; no files."
)
HOMEPAGE = "https://r-roms.github.io/"
RAW_BASE = "https://raw.githubusercontent.com/r-roms/r-roms.github.io/HEAD"
USER_AGENT = "CartshelfAddons/1.0 (catalog generator)"
FORMAT_IN_TITLE = re.compile(r"(?:^|\s)\.([A-Za-z0-9]{2,5})\b")


class LocalSource:
    def __init__(self, root: Path):
        self.root = root

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text(encoding="utf-8")


class RemoteSource:
    def read(self, relative: str) -> str:
        request = urllib.request.Request(f"{RAW_BASE}/{quote(relative, safe='/')}", headers={"User-Agent": USER_AGENT})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.read().decode("utf-8")
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise
                last_error: Exception = error
            except (OSError, http.client.HTTPException) as error:
                last_error = error
            time.sleep(3 * (attempt + 1))
        raise OSError(f"could not read {relative}: {last_error}")


class ArchiveVerifier:
    """Finds collections Internet Archive no longer serves. Network trouble never removes anything."""

    def __init__(self, workers: int = 4):
        self.workers = workers
        self._status: dict[str, bool | None] = {}
        self._files: dict[str, list[str] | None] = {}

    @staticmethod
    def _get(url: str) -> dict | None:
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=90) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return {"error": "not found"}
            except (OSError, http.client.HTTPException, ValueError):
                pass
            time.sleep(2 * (attempt + 1))
        return None

    def _item_alive(self, identifier: str) -> bool | None:
        answer = self._get(f"https://archive.org/metadata/{quote(identifier)}/files_count")
        if answer is None:
            return None  # could not tell: keep the collection
        return bool(answer.get("result"))

    def _item_files(self, identifier: str) -> list[str] | None:
        answer = self._get(f"https://archive.org/metadata/{quote(identifier)}/files")
        if answer is None or "result" not in answer:
            return None
        return [entry["name"] for entry in answer["result"] if "name" in entry]

    def prepare(self, sources: set[tuple[str, str]]) -> None:
        identifiers = sorted({identifier for identifier, _ in sources})
        with ThreadPoolExecutor(self.workers) as pool:
            for identifier, alive in zip(identifiers, pool.map(self._item_alive, identifiers)):
                self._status[identifier] = alive
            with_path = sorted({identifier for identifier, path in sources if path and self._status.get(identifier)})
            for identifier, files in zip(with_path, pool.map(self._item_files, with_path)):
                self._files[identifier] = files

    def is_dead(self, identifier: str, path: str) -> bool:
        if self._status.get(identifier) is False:
            return True
        if path and self._status.get(identifier):
            files = self._files.get(identifier)
            if files is not None:
                return not any(name == path or name.startswith(path + "/") for name in files)
        return False


def load_platforms() -> dict:
    return json.loads((ROOT / "spec" / "platforms.json").read_text(encoding="utf-8"))


def format_of(title: str) -> str | None:
    match = FORMAT_IN_TITLE.search(title)
    return match.group(1).lower() if match else None


def collect(source, report: dict) -> dict[str, list[dict]]:
    """Returns console id -> collections, in the order the megathread lists them."""
    by_console: dict[str, list[dict]] = {}
    seen: set[tuple[str, str, str]] = set()
    pages = parse_sidebar(source.read(SIDEBAR_PATH))
    report["pages"] = len(pages)
    for _name, path in pages:
        try:
            rows = parse_page(source.read(f"src/routes{path}/+page.svelte"))
        except (OSError, urllib.error.URLError) as error:
            report.setdefault("unreadable_pages", []).append(f"{path}: {error}")
            continue
        for row in rows:
            report["rows"] += 1
            if not row.sources:
                report["rows_without_archive_link"] += 1
                continue
            console = classify(path, row.title, [ref.identifier for ref in row.sources])
            if console is None:
                report["unmapped"].append(f"{path}: {row.title}")
                continue
            several = len(row.sources) > 1
            for part, ref in enumerate(row.sources, start=1):
                fixed = fix_path(row.title, ref.identifier, ref.path)
                key = (console, ref.identifier, fixed)
                if key in seen:
                    continue
                seen.add(key)
                item_source: dict = {"type": "archive.org-item", "id": ref.identifier}
                if fixed:
                    item_source["path"] = fixed
                if should_expand(ref.identifier, fixed):
                    item_source["expand"] = "zip"
                title = f"{row.title} (Part {part})" if several and f"Part {part}" not in row.title else row.title
                collection = {"title": title, "source": item_source}
                fmt = format_of(row.title)
                if fmt:
                    collection["format"] = fmt
                by_console.setdefault(console, []).append(collection)
    return by_console


def build_manifest(by_console: dict[str, list[dict]], platforms: dict, version: str) -> dict:
    categories = []
    for category in platforms["categories"]:
        consoles = [
            {"id": console["id"], "name": console["name"], "collections": by_console[console["id"]]}
            for console in category["consoles"]
            if by_console.get(console["id"])
        ]
        if consoles:
            categories.append({"id": category["id"], "name": category["name"], "consoles": consoles})
    return {
        "spec": 1,
        "id": ADDON_ID,
        "name": ADDON_NAME,
        "version": version,
        "description": ADDON_DESCRIPTION,
        "homepage": HOMEPAGE,
        "categories": categories,
    }


def generate(source, *, verify: bool = False, version: str | None = None) -> tuple[dict, dict]:
    report: dict = {"pages": 0, "rows": 0, "rows_without_archive_link": 0, "unmapped": [], "removed_by_verify": []}
    platforms = load_platforms()
    by_console = collect(source, report)

    if verify:
        pairs = {(c["source"]["id"], c["source"].get("path", "")) for items in by_console.values() for c in items}
        verifier = ArchiveVerifier()
        verifier.prepare(pairs)
        for console, items in list(by_console.items()):
            kept = []
            for item in items:
                src = item["source"]
                if verifier.is_dead(src["id"], src.get("path", "")):
                    report["removed_by_verify"].append(f'{console}: {item["title"]} ({src["id"]})')
                else:
                    kept.append(item)
            by_console[console] = kept

    manifest = build_manifest(by_console, platforms, version or date.today().strftime("%Y.%m.%d"))
    result = validate_manifest(manifest, platforms)
    if not result.ok:
        raise SystemExit("generated manifest is invalid:\n" + "\n".join(result.errors[:20]))
    report["consoles"] = {c["id"]: len(c["collections"]) for cat in manifest["categories"] for c in cat["consoles"]}
    return manifest, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-dir", type=Path, help="read the megathread sources from this folder instead of GitHub")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "rroms.addon.json")
    parser.add_argument("--verify", action="store_true", help="check every collection against Internet Archive and drop dead ones")
    parser.add_argument("--allow-unmapped", action="store_true", help="do not fail when a row cannot be assigned to a console")
    args = parser.parse_args(argv)

    source = LocalSource(args.source_dir) if args.source_dir else RemoteSource()
    manifest, report = generate(source, verify=args.verify)

    # A missing page would silently drop whole consoles from the catalog, so never write a partial result.
    if report.get("unreadable_pages"):
        print("Pages that could not be read (nothing was written):", file=sys.stderr)
        for line in report["unreadable_pages"]:
            print(f"  {line}", file=sys.stderr)
        return 3

    if report["unmapped"]:
        print("Rows with an Internet Archive link that no rule could place:", file=sys.stderr)
        for line in report["unmapped"]:
            print(f"  {line}", file=sys.stderr)
        if not args.allow_unmapped:
            print("Add a rule in generators/rroms/classify.py (or pass --allow-unmapped).", file=sys.stderr)
            return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    counts = Counter(report["consoles"])
    print(f"{report['pages']} pages, {report['rows']} rows ({report['rows_without_archive_link']} without an Internet Archive link)")
    print(f"{len(counts)} consoles, {sum(counts.values())} collections -> {args.out}")
    if report["removed_by_verify"]:
        print(f"removed by --verify ({len(report['removed_by_verify'])}):")
        for line in report["removed_by_verify"]:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
