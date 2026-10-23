"""No locale ships a resource that en-US lacks (OVOS-INTENT-2 §2.3).

For every role except .blacklist and .prompt, the (role, base name) pairs of
each shipped locale must be a subset of the en-US pairs. The reverse
direction, a locale that lacks a pair en-US has, is not asserted here.
"""
import unittest
from pathlib import Path

LOCALE_ROOT = Path(__file__).resolve().parents[2] / "ovos_skill_fallback_unknown" / "locale"
EXEMPT_SUFFIXES = {".blacklist", ".prompt", ".json"}


def resource_pairs(lang_dir: Path) -> set:
    return {(path.suffix, path.stem)
            for path in lang_dir.rglob("*")
            if path.is_file() and path.suffix not in EXEMPT_SUFFIXES}


class TestLocaleParity(unittest.TestCase):
    def test_no_locale_has_a_resource_en_us_lacks(self):
        reference = resource_pairs(LOCALE_ROOT / "en-US")
        extra = {}
        for lang_dir in sorted(p for p in LOCALE_ROOT.iterdir() if p.is_dir()):
            surplus = resource_pairs(lang_dir) - reference
            if surplus:
                extra[lang_dir.name] = sorted(f"{stem}{suffix}" for suffix, stem in surplus)
        self.assertEqual(extra, {})


if __name__ == "__main__":
    unittest.main()
