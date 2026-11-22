"""Reads the public r/ROMs megathread site sources (SvelteKit pages) into plain rows."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import unquote

SIDEBAR_PATH = "src/lib/components/app-sidebar.svelte"

_NAV = re.compile(r'title:\s*"([^"]+)",\s*url:\s*base\s*\+\s*"(/[^"]+)"')
_ROW = re.compile(r"<TableRow>(.*?)</TableRow>", re.DOTALL)
_CELL = re.compile(r"<TableCell[^>]*>(.*?)</TableCell\s*>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_LINK = re.compile(r'href="https://archive\.org/(?:download|details)/([^/"?#]+)(/[^"?#]*)?"')

# Sections of the site that are not console listings.
EXCLUDED_SECTIONS = ("/General", "/Populars", "/Miscellaneous")


@dataclass(frozen=True)
class SourceRef:
    identifier: str
    path: str  # "" for the whole item; otherwise a folder or a single file inside it


@dataclass(frozen=True)
class Row:
    title: str
    sources: tuple[SourceRef, ...]  # Internet Archive links found in the row (may be empty)


def parse_sidebar(source: str) -> list[tuple[str, str]]:
    """Returns (display name, route path) for every console page, in site order."""
    pages = [(name, path) for name, path in _NAV.findall(source)]
    return [(name, path) for name, path in pages if not path.startswith(EXCLUDED_SECTIONS)]


def parse_page(source: str) -> list[Row]:
    rows: list[Row] = []
    for row_html in _ROW.findall(source):
        cell = _CELL.search(row_html)
        if not cell:
            continue
        title = _SPACE.sub(" ", html.unescape(_TAG.sub("", cell.group(1)))).strip()
        if not title:
            continue
        refs: list[SourceRef] = []
        for identifier, raw_path in _LINK.findall(row_html):
            ref = SourceRef(identifier, unquote(raw_path or "").strip("/"))
            if ref not in refs:
                refs.append(ref)
        rows.append(Row(title, tuple(refs)))
    return rows
