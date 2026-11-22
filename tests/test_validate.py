import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from addonlib import validate_bytes, validate_manifest  # noqa: E402

PLATFORMS = json.loads((ROOT / "spec" / "platforms.json").read_text(encoding="utf-8"))


def base() -> dict:
    return json.loads((ROOT / "examples" / "minimal.addon.json").read_text(encoding="utf-8"))


def first_collection(manifest: dict) -> dict:
    return manifest["categories"][0]["consoles"][0]["collections"][0]


class ExamplesAndPlatforms(unittest.TestCase):
    def test_every_example_is_valid(self):
        for path in sorted((ROOT / "examples").glob("*.addon.json")):
            with self.subTest(example=path.name):
                report = validate_bytes(path.read_bytes(), PLATFORMS)
                self.assertTrue(report.ok, report.errors)

    def test_generated_catalog_is_valid_when_present(self):
        path = ROOT / "dist" / "rroms.addon.json"
        if not path.exists():
            self.skipTest("dist/rroms.addon.json has not been generated")
        report = validate_bytes(path.read_bytes(), PLATFORMS)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual([], report.warnings)

    def test_platform_ids_are_unique_and_well_formed(self):
        ids = [console["id"] for category in PLATFORMS["categories"] for console in category["consoles"]]
        self.assertEqual(len(ids), len(set(ids)))
        categories = [category["id"] for category in PLATFORMS["categories"]]
        self.assertEqual(len(categories), len(set(categories)))


class Rejections(unittest.TestCase):
    def assert_invalid(self, manifest, needle: str):
        report = validate_manifest(manifest)
        self.assertFalse(report.ok, "expected the manifest to be rejected")
        self.assertTrue(any(needle in error for error in report.errors), report.errors)

    def test_wrong_spec_version(self):
        manifest = base()
        manifest["spec"] = 2
        self.assert_invalid(manifest, "spec")

    def test_expand_zip_is_accepted_and_other_values_are_rejected(self):
        manifest = base()
        first_collection(manifest)["source"]["expand"] = "zip"
        self.assertTrue(validate_manifest(manifest, PLATFORMS).ok)
        first_collection(manifest)["source"]["expand"] = "rar"
        report = validate_manifest(manifest, PLATFORMS)
        self.assertTrue(any("source.expand" in e for e in report.errors), report.errors)

    def test_trailing_newline_in_ids_is_rejected(self):
        manifest = base()
        manifest["id"] = "my-addon\n"
        self.assertFalse(validate_manifest(manifest, PLATFORMS).ok)

    def test_missing_source_type_is_an_error(self):
        manifest = base()
        del first_collection(manifest)["source"]["type"]
        report = validate_manifest(manifest, PLATFORMS)
        self.assertTrue(any("source.type" in e for e in report.errors), report.errors)

    def test_float_spec_and_bare_https_homepage_are_rejected(self):
        manifest = base()
        manifest["spec"] = 1.0
        self.assertFalse(validate_manifest(manifest, PLATFORMS).ok)
        manifest = base()
        manifest["homepage"] = "https://"
        self.assertFalse(validate_manifest(manifest, PLATFORMS).ok)

    def test_deeply_nested_json_is_reported_not_raised(self):
        self.assertFalse(validate_bytes(b"[" * 200000, PLATFORMS).ok)

    def test_missing_name(self):
        manifest = base()
        del manifest["name"]
        self.assert_invalid(manifest, "name")

    def test_bad_addon_id(self):
        manifest = base()
        manifest["id"] = "Not Valid"
        self.assert_invalid(manifest, "id")

    def test_homepage_must_be_https(self):
        manifest = base()
        manifest["homepage"] = "http://example.com"
        self.assert_invalid(manifest, "homepage")

    def test_empty_categories(self):
        manifest = base()
        manifest["categories"] = []
        self.assert_invalid(manifest, "categories")

    def test_duplicate_console_ids(self):
        manifest = base()
        manifest["categories"][0]["consoles"].append(copy.deepcopy(manifest["categories"][0]["consoles"][0]))
        self.assert_invalid(manifest, "duplicate console id")

    def test_path_traversal_is_rejected(self):
        for path in ("../secret", "a/../b", "/absolute", "back\\slash", "a//b"):
            with self.subTest(path=path):
                manifest = base()
                first_collection(manifest)["source"]["path"] = path
                self.assert_invalid(manifest, "source.path")

    def test_bad_archive_identifier(self):
        manifest = base()
        first_collection(manifest)["source"]["id"] = "has space"
        self.assert_invalid(manifest, "source.id")

    def test_bad_format(self):
        manifest = base()
        first_collection(manifest)["format"] = ".ISO"
        self.assert_invalid(manifest, "format")

    def test_title_too_long(self):
        manifest = base()
        first_collection(manifest)["title"] = "x" * 161
        self.assert_invalid(manifest, "title")

    def test_not_json(self):
        self.assertFalse(validate_bytes(b"<html>", None).ok)
        self.assertFalse(validate_bytes(b"[]", None).ok)

    def test_too_large(self):
        self.assertFalse(validate_bytes(b" " * (5 * 1024 * 1024 + 1), None).ok)


class WebSources(unittest.TestCase):
    def check(self, source: dict) -> list[str]:
        manifest = base()
        first_collection(manifest)["source"] = source
        report = validate_manifest(manifest)
        self.assertEqual([], [w for w in report.warnings if "skip" in w])
        return report.errors

    def test_valid_web_sources(self):
        self.assertEqual([], self.check({"type": "http-directory", "url": "https://example.org/gb/", "extensions": ["gb", "zip"]}))
        self.assertEqual([], self.check({"type": "file-list", "url": "https://example.org/gb.json"}))
        self.assertEqual([], self.check({"type": "files", "files": [
            {"name": "Tobu Tobu Girl (World).gb", "url": "https://example.org/t.gb", "size": 65536,
             "md5": "0123456789abcdef0123456789ABCDEF"}]}))

    def test_web_sources_need_public_https_addresses(self):
        for url in ("http://example.org/a.json", "https://192.168.1.1/a.json", "https://nas.local/a.json",
                    "https://127.0.0.1/a.json", "https://[::1]/a.json", "ftp://example.org/a.json"):
            with self.subTest(url=url):
                self.assertTrue(self.check({"type": "file-list", "url": url}))

    def test_directory_needs_extensions(self):
        self.assertTrue(self.check({"type": "http-directory", "url": "https://example.org/gb/"}))
        self.assertTrue(self.check({"type": "http-directory", "url": "https://example.org/gb/", "extensions": ["GB!"]}))

    def test_inline_files_are_checked(self):
        for files in (
            [],
            [{"name": "../evil.gb", "url": "https://example.org/e.gb"}],
            [{"name": "a.gb", "url": "https://example.org/a.gb", "md5": "nope"}],
            [{"name": "a.gb", "url": "https://example.org/a.gb", "size": -1}],
            [{"name": "a.gb", "url": "https://example.org/a.gb"}, {"name": "a.gb", "url": "https://example.org/b.gb"}],
        ):
            with self.subTest(files=files):
                self.assertTrue(self.check({"type": "files", "files": files}))

    def test_expand_is_only_for_internet_archive(self):
        self.assertTrue(self.check({"type": "file-list", "url": "https://example.org/a.json", "expand": "zip"}))


class Warnings(unittest.TestCase):
    def test_unknown_source_type_is_a_warning_not_an_error(self):
        manifest = base()
        first_collection(manifest)["source"] = {"type": "future-source", "id": "x"}
        report = validate_manifest(manifest)
        self.assertTrue(report.ok)
        self.assertTrue(any("skip this collection" in warning for warning in report.warnings))

    def test_unknown_console_id_warns_about_merging(self):
        manifest = base()
        manifest["categories"][0]["consoles"][0]["id"] = "my-custom-console"
        report = validate_manifest(manifest, PLATFORMS)
        self.assertTrue(report.ok)
        self.assertTrue(any("will not merge" in warning for warning in report.warnings))

    def test_console_in_wrong_category_warns(self):
        manifest = base()
        manifest["categories"][0]["id"] = "nintendo"
        report = validate_manifest(manifest, PLATFORMS)
        self.assertTrue(any("canonically in category" in warning for warning in report.warnings))


if __name__ == "__main__":
    unittest.main()
