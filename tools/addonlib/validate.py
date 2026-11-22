"""Reference validator for the Cartshelf addon manifest, spec version 1.

Pure standard library. The rules here mirror docs/SPEC.md; the app applies the same limits when it installs an addon.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

SPEC_VERSION = 1
SOURCE_ARCHIVE_ITEM = "archive.org-item"
SOURCE_HTTP_DIRECTORY = "http-directory"
SOURCE_FILE_LIST = "file-list"
SOURCE_FILES = "files"
WEB_SOURCES = (SOURCE_HTTP_DIRECTORY, SOURCE_FILE_LIST, SOURCE_FILES)
MAX_EXTENSIONS = 20
MAX_INLINE_FILES = 2_000
MD5 = re.compile(r"[0-9a-fA-F]{32}")

MAX_BYTES = 5 * 1024 * 1024
MAX_CATEGORIES = 100
MAX_CONSOLES = 500
MAX_COLLECTIONS = 10_000
MAX_COLLECTIONS_PER_CONSOLE = 2_000

ADDON_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,63}")
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,59}")
ARCHIVE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
FORMAT = re.compile(r"[a-z0-9]{1,8}")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    categories: int = 0
    consoles: int = 0
    collections: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _text(value: Any, where: str, report: Report, *, maximum: int, required: bool = True) -> str | None:
    if value is None:
        if required:
            report.errors.append(f"{where}: required")
        return None
    if not isinstance(value, str):
        report.errors.append(f"{where}: must be a string")
        return None
    if required and not value.strip():
        report.errors.append(f"{where}: must not be empty")
        return None
    if len(value) > maximum:
        report.errors.append(f"{where}: longer than {maximum} characters")
        return None
    return value


def _is_https_url(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 300:
        return False
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.hostname)


def _safe_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


def _is_private_host(host: str) -> bool:
    name = host.lower().rstrip(".")
    if name == "localhost" or name.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(name.strip("[]"))
    except ValueError:
        return False
    return not address.is_global


def _is_public_https_url(value: Any) -> bool:
    """https only, and never the device itself or a home network: the app refuses those addresses too."""
    if not isinstance(value, str) or len(value) > 2000:
        return False
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.hostname) and not _is_private_host(parts.hostname)


def _safe_name(name: Any) -> bool:
    return (isinstance(name, str) and name.strip() != "" and len(name) <= 300 and "/" not in name
            and "\\" not in name and "\x00" not in name and name not in (".", ".."))


def _validate_web_source(kind: str, source: dict, where: str, report: Report) -> None:
    if source.get("expand") is not None:
        report.errors.append(f"{where}.expand: only for {SOURCE_ARCHIVE_ITEM} sources")
    if kind in (SOURCE_HTTP_DIRECTORY, SOURCE_FILE_LIST):
        if not _is_public_https_url(source.get("url")):
            report.errors.append(f"{where}.url: must be an https:// address on the public internet")
    if kind == SOURCE_HTTP_DIRECTORY:
        extensions = source.get("extensions")
        if not (isinstance(extensions, list) and 1 <= len(extensions) <= MAX_EXTENSIONS):
            report.errors.append(f"{where}.extensions: 1-{MAX_EXTENSIONS} file extensions")
        else:
            for i, ext in enumerate(extensions):
                if not (isinstance(ext, str) and FORMAT.fullmatch(ext)):
                    report.errors.append(f"{where}.extensions[{i}]: must match ^{FORMAT.pattern}$")
    if kind == SOURCE_FILES:
        files = source.get("files")
        if not (isinstance(files, list) and 1 <= len(files) <= MAX_INLINE_FILES):
            report.errors.append(f"{where}.files: 1-{MAX_INLINE_FILES} files")
            return
        names: set[str] = set()
        for i, entry in enumerate(files):
            _validate_file(entry, f"{where}.files[{i}]", report, names)


def _validate_file(entry: Any, where: str, report: Report, names: set[str]) -> None:
    """Rules for an inline file; the app applies the same ones to every entry of a file-list feed."""
    if not isinstance(entry, dict):
        report.errors.append(f"{where}: must be an object")
        return
    name = entry.get("name")
    if not _safe_name(name):
        report.errors.append(f"{where}.name: 1-300 characters, no '/', '\\' or '..'")
    elif name in names:
        report.errors.append(f"{where}.name: duplicate file {name!r}")
    else:
        names.add(name)
    if not _is_public_https_url(entry.get("url")):
        report.errors.append(f"{where}.url: must be an https:// address on the public internet")
    size = entry.get("size")
    if size is not None and not (isinstance(size, int) and not isinstance(size, bool) and size >= 0):
        report.errors.append(f"{where}.size: must be a non-negative integer")
    md5 = entry.get("md5")
    if md5 is not None and not (isinstance(md5, str) and MD5.fullmatch(md5)):
        report.errors.append(f"{where}.md5: must be 32 hexadecimal characters")


def _validate_collection(item: Any, where: str, report: Report) -> None:
    if not isinstance(item, dict):
        report.errors.append(f"{where}: must be an object")
        return
    _text(item.get("title"), f"{where}.title", report, maximum=160)
    fmt = item.get("format")
    if fmt is not None and not (isinstance(fmt, str) and FORMAT.fullmatch(fmt)):
        report.errors.append(f"{where}.format: must match ^{FORMAT.pattern}$")
    source = item.get("source")
    if not isinstance(source, dict):
        report.errors.append(f"{where}.source: required object")
        return
    kind = source.get("type")
    if not isinstance(kind, str) or not kind:
        report.errors.append(f"{where}.source.type: required string")
        return
    if kind in WEB_SOURCES:
        _validate_web_source(kind, source, f"{where}.source", report)
        return
    if kind != SOURCE_ARCHIVE_ITEM:
        report.warnings.append(f"{where}.source.type: {kind!r} is unknown to this validator; apps that do not know it skip this collection")
        return
    identifier = source.get("id")
    if not (isinstance(identifier, str) and ARCHIVE_ID.fullmatch(identifier)):
        report.errors.append(f"{where}.source.id: must be an Internet Archive identifier")
    path = source.get("path")
    if path is not None and not (isinstance(path, str) and len(path) <= 300 and _safe_path(path)):
        report.errors.append(f"{where}.source.path: must be a relative path without '..', '\\' or leading '/'")
    expand = source.get("expand")
    if expand is not None and expand != "zip":
        report.errors.append(f'{where}.source.expand: must be "zip"')


def _validate_console(console: Any, where: str, report: Report, console_ids: set[str]) -> None:
    if not isinstance(console, dict):
        report.errors.append(f"{where}: must be an object")
        return
    console_id = console.get("id")
    if not (isinstance(console_id, str) and SLUG.fullmatch(console_id)):
        report.errors.append(f"{where}.id: must match ^{SLUG.pattern}$")
    elif console_id in console_ids:
        report.errors.append(f"{where}.id: duplicate console id {console_id!r}")
    else:
        console_ids.add(console_id)
    _text(console.get("name"), f"{where}.name", report, maximum=80)
    collections = console.get("collections")
    if not isinstance(collections, list):
        report.errors.append(f"{where}.collections: must be an array")
        return
    if not collections:
        report.warnings.append(f"{where}: console has no collections and will not be shown")
    if len(collections) > MAX_COLLECTIONS_PER_CONSOLE:
        report.errors.append(f"{where}.collections: more than {MAX_COLLECTIONS_PER_CONSOLE} entries")
        return
    report.collections += len(collections)
    for index, item in enumerate(collections):
        _validate_collection(item, f"{where}.collections[{index}]", report)


def _check_platforms(data: dict, platforms: dict, report: Report) -> None:
    known_categories = {c["id"]: c for c in platforms.get("categories", [])}
    known_consoles = {
        console["id"]: (category["id"], console["name"])
        for category in platforms.get("categories", [])
        for console in category.get("consoles", [])
    }
    for category in data.get("categories", []):
        if not isinstance(category, dict):
            continue
        category_id = category.get("id")
        if category_id not in known_categories:
            report.warnings.append(f"category {category_id!r} is not in spec/platforms.json (it will not merge with other addons)")
        for console in category.get("consoles", []) if isinstance(category.get("consoles"), list) else []:
            if not isinstance(console, dict):
                continue
            console_id = console.get("id")
            if console_id not in known_consoles:
                report.warnings.append(f"console {console_id!r} is not in spec/platforms.json (it will not merge with other addons)")
            elif known_consoles[console_id][0] != category_id:
                report.warnings.append(
                    f"console {console_id!r} is canonically in category {known_consoles[console_id][0]!r}, not {category_id!r}"
                )


def validate_manifest(data: Any, platforms: dict | None = None) -> Report:
    report = Report()
    if not isinstance(data, dict):
        report.errors.append("manifest: must be a JSON object")
        return report

    spec = data.get("spec")
    if type(spec) is not int or spec != SPEC_VERSION:
        report.errors.append(f"spec: must be {SPEC_VERSION}")
    addon_id = data.get("id")
    if not (isinstance(addon_id, str) and ADDON_ID.fullmatch(addon_id)):
        report.errors.append(f"id: must match ^{ADDON_ID.pattern}$")
    _text(data.get("name"), "name", report, maximum=60)
    _text(data.get("version"), "version", report, maximum=32)
    _text(data.get("description"), "description", report, maximum=400, required=False)
    homepage = data.get("homepage")
    if homepage is not None and not _is_https_url(homepage):
        report.errors.append("homepage: must be an https:// URL")

    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        report.errors.append("categories: must be a non-empty array")
        return report
    if len(categories) > MAX_CATEGORIES:
        report.errors.append(f"categories: more than {MAX_CATEGORIES} entries")
        return report

    category_ids: set[str] = set()
    console_ids: set[str] = set()
    for c_index, category in enumerate(categories):
        where = f"categories[{c_index}]"
        if not isinstance(category, dict):
            report.errors.append(f"{where}: must be an object")
            continue
        category_id = category.get("id")
        if not (isinstance(category_id, str) and SLUG.fullmatch(category_id)):
            report.errors.append(f"{where}.id: must match ^{SLUG.pattern}$")
        elif category_id in category_ids:
            report.errors.append(f"{where}.id: duplicate category id {category_id!r}")
        else:
            category_ids.add(category_id)
        _text(category.get("name"), f"{where}.name", report, maximum=60)
        consoles = category.get("consoles")
        if not isinstance(consoles, list):
            report.errors.append(f"{where}.consoles: must be an array")
            continue
        report.categories += 1
        for k_index, console in enumerate(consoles):
            report.consoles += 1
            _validate_console(console, f"{where}.consoles[{k_index}]", report, console_ids)

    if report.consoles > MAX_CONSOLES:
        report.errors.append(f"consoles: more than {MAX_CONSOLES} in total")
    if report.collections > MAX_COLLECTIONS:
        report.errors.append(f"collections: more than {MAX_COLLECTIONS} in total")
    if platforms is not None and report.ok:
        _check_platforms(data, platforms, report)
    return report


def validate_bytes(raw: bytes, platforms: dict | None = None) -> Report:
    if len(raw) > MAX_BYTES:
        report = Report()
        report.errors.append(f"file: larger than {MAX_BYTES} bytes")
        return report
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        report = Report()
        report.errors.append(f"file: not valid UTF-8 JSON ({error})")
        return report
    return validate_manifest(data, platforms)
