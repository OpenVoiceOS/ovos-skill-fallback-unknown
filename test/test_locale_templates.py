"""Validate that every locale resource template is well-formed.

Same technique as ovos-skill-alerts/ovos-skill-volume's sibling test:
every .voc/.dialog/.intent/.entity/.rx line under
ovos_skill_fallback_unknown/locale/ must expand cleanly per OVOS-INTENT-1
via ovos_spec_tools.expand(). This skill's locale/ layout is flat (no
vocab/ or dialog/ subdirectories -- e.g. locale/ca-ES/who.is.voc sits next
to locale/ca-ES/who.is.dialog), unlike alerts/volume, but the same walk +
expand() check applies unchanged.
"""
import os
import unittest

from ovos_spec_tools.expansion import expand

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_ROOT = os.path.join(REPO_ROOT, "ovos_skill_fallback_unknown", "locale")
EXTENSIONS = (".voc", ".intent", ".dialog", ".entity", ".rx")


class TestLocaleTemplates(unittest.TestCase):
    def test_all_templates_expand(self):
        failures = []
        for root, _, files in os.walk(LOCALE_ROOT):
            for fname in sorted(files):
                if not fname.endswith(EXTENSIONS):
                    continue
                path = os.path.join(root, fname)
                with open(path, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, start=1):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        try:
                            expand(line)
                        except Exception as e:
                            rel = os.path.relpath(path, REPO_ROOT)
                            failures.append(f"{rel}:{lineno}: {line!r} -> {e}")
        self.assertEqual(
            failures, [],
            "Malformed locale templates:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
