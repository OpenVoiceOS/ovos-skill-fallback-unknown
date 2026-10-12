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
        # *whether* why_is matched at all.
        hits = self.skill.voc_match_span("why is the sky blue", "why_is")
        self.assertEqual(hits, [("why is", 0, 6)])
        self.assertEqual(
            self.skill._longest_voc_match("why is the sky blue", "why_is"), 6
        )
        # no match at all -> -1, not 0 or an empty-list truthiness bug
        self.assertEqual(
            self.skill._longest_voc_match("blleerghh foo bar", "why_is"), -1
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
            result = self.skill._longest_voc_match("why is the sky blue", "why_is")
        finally:
            del self.skill.voc_match_span
        self.assertEqual(calls, [("why is the sky blue", "why_is")])
        self.assertEqual(result, 6)

    def test_handle_fallback_picks_longest_matching_category(self):
        cases = {
            "who is the president": "who_is",
            "why is the sky blue": "why_is",
            "what is the time": "question",
            "blleerghh foo bar": "unknown",
        }
        for utt, expected in cases.items():
            self.spoken.clear()
            self.skill.handle_fallback(Message("", {"utterance": utt}))
            self.assertEqual(self.spoken, [expected], utt)


    def _dialog(self, utterance, lang):
        self.spoken.clear()
        self.skill.handle_fallback(Message("", {"utterance": utterance, "lang": lang},
                                           {"session": {"session_id": "test", "lang": lang}}))
        return self.spoken

    def test_conjunction_que_is_not_a_question(self):
        # accent folding makes the question word "qué"/"què" spell the
        # conjunction "que"; in gl-ES both are written "que"
        cases = [
            ("gl-ES", "fai que a música soe máis baixo"),
            ("gl-ES", "lémbrame que teño que mercar pan mañá"),
            ("gl-ES", "pon a radio que escoita a miña nai"),
            ("es-ES", "quiero que suene la alarma a las siete"),
            ("es-CO", "haz que la música suene más bajo"),
            ("ca-ES", "vull que l'alarma soni a les set"),
            ("oc-FR", "vòli que la musica sone mai bas"),
            ("es-ES", "ya no la necesito, así que quítala"),
            ("gl-ES", "oe, fai que a alarma soe máis tarde"),
            # a causal "que" after a comma
            ("es-ES", "apaga la luz, que quiero dormir"),
            ("es-ES", "date prisa, que llegamos tarde"),
            ("es-ES", "sube el volumen, que no oigo nada"),
            ("es-ES", "recuérdame mañana, que tengo médico"),
            ("es-CO", "prenda la luz, que está muy oscuro"),
            ("ca-ES", "apaga el llum, que vull dormir"),
            ("gl-ES", "apaga a luz, que quero durmir"),
            ("gl-ES", "sube o volume, que non oio nada"),
            ("oc-FR", "apaga lo lum, que vòli dormir"),
            # a filler or conjunction before "que" and a subjunctive
            ("es-ES", "y que suene la alarma a las siete"),
            ("es-ES", "pues que suene la alarma a las siete"),
            ("es-ES", "bueno, que suene la alarma a las siete"),
            ("es-ES", "oye, que pongas música"),
            ("es-ES", "a ver, que me pongas la radio"),
            ("es-CO", "pues que suene la alarma"),
            ("es-CO", "oiga, que me ponga música"),
            ("ca-ES", "doncs que soni l'alarma"),
            ("ca-ES", "i que soni l'alarma a les set"),
            ("ca-ES", "doncs què, posa música"),
            ("gl-ES", "e que soe a alarma ás sete"),
            ("gl-ES", "bo, que soe a alarma"),
            ("oc-FR", "e que la musica sone"),
            # gl-ES "é que" folds onto "e que"
            ("gl-ES", "é que non funciona a radio"),
            ("gl-ES", "apaga a luz, é que quero durmir"),
        ]
        for lang, utt in cases:
            with self.subTest(lang=lang, utterance=utt):
                self.assertEqual(self._dialog(utt, lang), ["unknown"])

    def test_interrogative_que_asks_a_question(self):
        # at the start, after a preposition, after a verb of telling or
        # knowing, or before a noun that only a question puts there
        cases = [
            ("gl-ES", "que opinas do Celta"),
            ("es-ES", "qué opinas de Madrid"),
            ("es-ES", "¿qué opinas de Madrid?"),
            ("es-CO", "qué opinas de Bogotá"),
            ("ca-ES", "què vol dir aquesta paraula"),
            ("oc-FR", "qué pensas d'aquò"),
            ("gl-ES", "en que ano estamos"),
            ("es-ES", "a qué hora sale el tren"),
            ("ca-ES", "de què tracta la pel·lícula"),
            ("oc-FR", "en qué an sèm"),
            ("gl-ES", "dime que cor é o ceo"),
            ("es-CO", "sabes qué hora es"),
            ("ca-ES", "saps què vol dir"),
            ("gl-ES", "hoxe que día é"),
            ("es-ES", "hoy qué día es"),
        ]
        for lang, utt in cases:
            with self.subTest(lang=lang, utterance=utt):
                self.assertEqual(self._dialog(utt, lang), ["question"])


if __name__ == "__main__":
    unittest.main()
