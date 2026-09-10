import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from ovos_skill_fallback_unknown import UnknownSkill


class TestFallbackHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_id = "ovos-skill-fallback-unknown.openvoiceos"
        cls.skill = UnknownSkill()
        cls.skill._startup(FakeBus(), cls.skill_id)

    def setUp(self):
        self.spoken = []
        self.skill.speak_dialog = lambda name, *a, **kw: self.spoken.append(name)

    def test_longest_voc_match_recovers_matched_entry_via_span(self):
        # adversarial: "why is" (6 chars) is a longer match than any
        # "question" vocab entry on this utterance, so _longest_voc_match
        # must recover it from voc_match_span rather than just knowing
        # *whether* why.is matched at all.
        hits = self.skill.voc_match_span("why is the sky blue", "why.is")
        self.assertEqual(hits, [("why is", 0, 6)])
        self.assertEqual(
            self.skill._longest_voc_match("why is the sky blue", "why.is"), 6
        )
        # no match at all -> -1, not 0 or an empty-list truthiness bug
        self.assertEqual(
            self.skill._longest_voc_match("blleerghh foo bar", "why.is"), -1
        )

    def test_longest_voc_match_delegates_to_voc_match_span(self):
        # pins the implementation to voc_match_span (the which-entry-of-one-voc
        # API) rather than a hand-rolled regex reimplementation of voc_match:
        # stubbing voc_match_span must be enough to control the result.
        calls = []

        def fake_span(utt, voc_filename, *a, **kw):
            calls.append((utt, voc_filename))
            return [("why is", 0, 6), ("why", 10, 13)]

        self.skill.voc_match_span = fake_span
        try:
            result = self.skill._longest_voc_match("why is the sky blue", "why.is")
        finally:
            del self.skill.voc_match_span
        self.assertEqual(calls, [("why is the sky blue", "why.is")])
        self.assertEqual(result, 6)

    def test_handle_fallback_picks_longest_matching_category(self):
        cases = {
            "who is the president": "who.is",
            "why is the sky blue": "why.is",
            "what is the time": "question",
            "blleerghh foo bar": "unknown",
        }
        for utt, expected in cases.items():
            self.spoken.clear()
            self.skill.handle_fallback(Message("", {"utterance": utt}))
            self.assertEqual(self.spoken, [expected], utt)


if __name__ == "__main__":
    unittest.main()
