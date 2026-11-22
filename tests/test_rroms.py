import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "generators" / "rroms"))

from addonlib import validate_manifest  # noqa: E402
from classify import classify, fix_path  # noqa: E402
import tempfile  # noqa: E402

from generate import LocalSource, format_of, generate, main  # noqa: E402
from parse import SourceRef, parse_page, parse_sidebar  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rroms"
PLATFORMS = json.loads((ROOT / "spec" / "platforms.json").read_text(encoding="utf-8"))


def consoles(manifest: dict) -> dict[str, list[dict]]:
    return {c["id"]: c["collections"] for cat in manifest["categories"] for c in cat["consoles"]}


class Parsing(unittest.TestCase):
    def test_sidebar_skips_non_console_sections(self):
        pages = parse_sidebar((FIXTURES / "src/lib/components/app-sidebar.svelte").read_text(encoding="utf-8"))
        self.assertEqual(
            ["/Nintendo/nintendo-games", "/Sega/sega-games", "/Sony/sony-playstation-portable"],
            [path for _name, path in pages],
        )

    def test_rows_keep_every_archive_link_and_decode_paths(self):
        rows = parse_page((FIXTURES / "src/routes/Sega/sega-games/+page.svelte").read_text(encoding="utf-8"))
        self.assertEqual(
            (SourceRef("ni-roms", "roms/Sega - 32X.zip"), SourceRef("nointro.32x", "")),
            rows[0].sources,
        )

    def test_rows_without_archive_links_have_no_sources(self):
        rows = parse_page((FIXTURES / "src/routes/Nintendo/nintendo-games/+page.svelte").read_text(encoding="utf-8"))
        self.assertEqual((), rows[0].sources)

    def test_html_entities_in_titles_are_decoded(self):
        rows = parse_page("<TableRow><TableCell>NEC - PC Engine CD &amp; TurboGrafx CD</TableCell></TableRow>")
        self.assertEqual("NEC - PC Engine CD & TurboGrafx CD", rows[0].title)


class Classification(unittest.TestCase):
    def check(self, page, title, ids, expected):
        self.assertEqual(expected, classify(page, title, ids), f"{title} on {page}")

    def test_nintendo_handhelds_and_consoles_are_separated(self):
        page = "/Nintendo/nintendo-games"
        self.check(page, "Nintendo - Game Boy", ["No-Intro_GameBoy_Collection"], "nintendo-gb")
        self.check(page, "Nintendo - Game Boy Color", ["No-Intro_GameBoy_Color_Collection"], "nintendo-gbc")
        self.check(page, "Nintendo - Game Boy Advance (e-Reader)", [], "nintendo-gba")
        self.check(page, "Nintendo - Super Nintendo Entertainment System", ["No-Intro_SNES_Collection"], "nintendo-snes")
        self.check(page, "Nintendo - NES Collection", ["NES_Test_Collection_3"], "nintendo-nes")
        self.check(page, "Nintendo - Nintendo 64DD", [], "nintendo-64dd")
        self.check(page, "Nintendo - N64 Collection", ["No-Intro_N64_Collection"], "nintendo-64")
        self.check(page, "Nintendo - Family Computer Disk System (QD)", [], "nintendo-fds")

    def test_dsi_is_split_from_ds(self):
        page = "/Nintendo/nintendo-ds"
        self.check(page, "DSi No-Intro 2024", [], "nintendo-dsi")
        self.check(page, "DSiWare", [], "nintendo-dsi")
        self.check(page, "DS No-Intro 2024", [], "nintendo-ds")

    def test_rules_are_scoped_to_their_page(self):
        self.check("/Nintendo/nintendo-wii-u", "Wii U: Nintendo 64 NUS", [], "nintendo-wii-u")

    def test_specific_rules_win_over_general_ones(self):
        self.check("/Retro & Arcade/arcade", "Arcade - Sega - Naomi 2", [], "arcade-sega-naomi-2")
        self.check("/Retro & Arcade/arcade", "Arcade - Sega - Naomi", [], "arcade-sega-naomi")
        self.check("/Retro & Arcade/retro-games", "PC Engine CD - TurboGrafx CD", ["pcecd-chd-zstd-redump"], "nec-pc-engine-cd")
        self.check("/Retro & Arcade/retro-games", "NEC - PC Engine - TurboGrafx 16", ["nointro.tg-16"], "nec-pc-engine")

    def test_identifier_can_disambiguate_a_vague_title(self):
        self.check("/Retro & Arcade/retro-games", "Atari Jaguar", ["jagcd-chd-zstd"], "atari-jaguar-cd")

    def test_unknown_page_and_unmatched_row(self):
        self.check("/Nowhere/page", "Anything", [], None)
        self.check("/PC/pc-games", "Some other site", [], None)

    def test_known_upstream_mistake_is_corrected(self):
        self.assertEqual("roms/Atari - 5200.zip", fix_path("Atari - 5200", "ni-roms", "roms/Atari - 2600.zip"))
        self.assertEqual("roms/Atari - 2600.zip", fix_path("Atari - 2600", "ni-roms", "roms/Atari - 2600.zip"))


class Generation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.report = generate(LocalSource(FIXTURES), version="test")

    def test_manifest_is_valid_without_warnings(self):
        result = validate_manifest(self.manifest, PLATFORMS)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual([], result.warnings)

    def test_consoles_are_grouped_by_category_in_platform_order(self):
        self.assertEqual(["nintendo", "sony", "sega"], [c["id"] for c in self.manifest["categories"]])
        tree = {c["id"]: [k["id"] for k in c["consoles"]] for c in self.manifest["categories"]}
        self.assertEqual(
            ["nintendo-snes", "nintendo-64", "nintendo-gb", "nintendo-gbc", "nintendo-gba"],
            tree["nintendo"],
        )
        self.assertEqual(["sony-psp"], tree["sony"])
        self.assertEqual(["sega-mega-drive", "sega-32x"], tree["sega"])

    def test_rows_with_only_other_hosts_are_skipped_and_counted(self):
        self.assertNotIn("nintendo-fds", consoles(self.manifest))
        self.assertNotIn("nintendo-64dd", consoles(self.manifest))
        self.assertEqual(3, self.report["rows_without_archive_link"])

    def test_one_collection_per_archive_link(self):
        titles = [c["title"] for c in consoles(self.manifest)["sega-32x"]]
        self.assertEqual(["Sega - 32X (Part 1)", "Sega - 32X (Part 2)"], titles)
        sources = [c["source"] for c in consoles(self.manifest)["sega-32x"]]
        self.assertEqual({"type": "archive.org-item", "id": "ni-roms", "path": "roms/Sega - 32X.zip", "expand": "zip"}, sources[0])

    def test_format_comes_from_the_title(self):
        psp = {c["title"]: c.get("format") for c in consoles(self.manifest)["sony-psp"]}
        self.assertEqual("iso", psp["PSP Redump .iso (Part 1)"])
        self.assertEqual("chd", psp["PSP Redump .chd (Part 1)"])
        self.assertIsNone(psp["PSP DLC"])
        self.assertEqual("chd", format_of("PSP Redump .chd (Part 2)"))

    def test_folder_paths_are_normalised(self):
        by_title = {c["title"]: c["source"] for c in consoles(self.manifest)["sony-psp"]}
        self.assertEqual("psp-chd-zstd", by_title["PSP Redump .chd (Part 1)"]["path"])
        self.assertEqual("[No-Intro] PSP DLC", by_title["PSP No-Intro DLC"]["path"])

    def test_nothing_is_left_unmapped(self):
        self.assertEqual([], self.report["unmapped"])


if __name__ == "__main__":
    unittest.main()


class UnreadablePage(unittest.TestCase):
    def test_a_missing_page_fails_the_run_and_writes_nothing(self):
        class MissingSega(LocalSource):
            def read(self, relative: str) -> str:
                if "sega" in relative:
                    raise OSError("simulated network failure")
                return super().read(relative)

        import generate as generate_module

        original = generate_module.LocalSource
        generate_module.LocalSource = MissingSega
        try:
            with tempfile.TemporaryDirectory() as folder:
                out = Path(folder) / "out.json"
                code = main(["--source-dir", str(FIXTURES), "--out", str(out)])
                self.assertEqual(3, code)
                self.assertFalse(out.exists())
        finally:
            generate_module.LocalSource = original
