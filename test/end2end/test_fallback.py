from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_utils.log import LOG

from ovoscope import End2EndTest, get_minicroft


class TestUnknownFallback(TestCase):
    """End-to-end coverage for the catch-all 'unknown' fallback skill.

    The skill registers a single fallback handler at priority 100 (lowest), so
    it only fires when nothing else in the pipeline matched. We drive it through
    the low-priority fallback pipeline with gibberish that no other skill can
    handle and assert the deterministic fallback message skeleton.
    """

    def setUp(self):
        LOG.set_level("DEBUG")
        self.skill_id = "ovos-skill-fallback-unknown.openvoiceos"
        self.minicroft = get_minicroft([self.skill_id])
        # the spoken 'unknown' dialog text is randomized, so we never assert on
        # it; ignore both the legacy and the migrated (ovos.*) speak topics
        self.ignore_messages = ["speak", "ovos.utterance.speak"]

    def tearDown(self):
        if self.minicroft:
            self.minicroft.stop()
        LOG.set_level("CRITICAL")

    def test_unknown_fallback(self):
        session = Session("123")
        # only the catch-all (low priority) fallback pipeline is needed; the
        # unknown skill is the last-resort handler
        session.pipeline = ["ovos-fallback-pipeline-plugin-low"]

        message = Message(
            "recognizer_loop:utterance",
            {"utterances": ["blleerghh foo bar"], "lang": "en-US"},
            {"session": session.serialize()},
        )

        expected_messages = [
            message,
            # fallback pipeline asks every fallback skill whether it can handle
            Message("ovos.skills.fallback.ping",
                    {"utterances": ["blleerghh foo bar"], "lang": "en-US"}),
            Message("ovos.skills.fallback.pong",
                    {"skill_id": self.skill_id, "can_handle": True},
                    {"skill_id": self.skill_id}),
            # the highest-priority capable fallback (this skill) is invoked
            Message(f"ovos.skills.fallback.{self.skill_id}.request",
                    {"skill_id": self.skill_id}),
            Message(f"ovos.skills.fallback.{self.skill_id}.start", {}),
            # here the skill speaks the randomized 'unknown' dialog (ignored)
            Message(f"ovos.skills.fallback.{self.skill_id}.response",
                    {"result": False,
                     "fallback_handler": "UnknownSkill.handle_fallback"}),
            Message("ovos.utterance.handled", {}),
        ]

        test = End2EndTest(
            minicroft=self.minicroft,
            skill_ids=[],
            eof_msgs=["ovos.utterance.handled"],
            flip_points=["recognizer_loop:utterance"],
            ignore_messages=self.ignore_messages,
            source_message=message,
            expected_messages=expected_messages,
        )

        test.execute()
