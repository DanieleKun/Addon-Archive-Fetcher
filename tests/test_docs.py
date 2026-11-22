import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from gen_platforms_doc import render  # noqa: E402


class GeneratedDocs(unittest.TestCase):
    def test_platforms_doc_matches_platforms_json(self):
        platforms = json.loads((ROOT / "spec" / "platforms.json").read_text(encoding="utf-8"))
        current = (ROOT / "docs" / "PLATFORMS.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(
            render(platforms),
            current,
            "docs/PLATFORMS.md is stale: run python tools/gen_platforms_doc.py",
        )


if __name__ == "__main__":
    unittest.main()
