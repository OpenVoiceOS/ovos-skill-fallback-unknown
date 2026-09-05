"""Multilingual golden-utterance end-to-end coverage for
ovos-skill-fallback-unknown.

test_fallback.py only exercises the en-US catch-all ("unknown") branch;
every other locale under locale/ (a flat layout: question.voc/.dialog,
who.is.voc/.dialog, why.is.voc/.dialog, unknown.dialog directly under
locale/<lang>/, no vocab/ or dialog/ subdirectories) was never routed
end-to-end. The skill's fallback handler (see
ovos_skill_fallback_unknown/__init__.py::handle_fallback) checks
voc_match against question/who.is/why.is in that order and falls
through to the "unknown" dialog if none match; there is no separate
intent to assert against (the fallback pipeline always claims the
utterance -- can_answer always returns True), so what this suite
verifies is WHICH of the four dialogs the skill picked, via the
``meta.dialog`` field ovos-workshop attaches to the
``ovos.utterance.speak`` message when a dialog is rendered. The
randomized dialog *text* is never asserted, matching test_fallback.py's
precedent.

Row construction: every question/who.is/why.is row is a natural-language
sample expanded directly from the locale's own question.voc / who.is.voc
/ why.is.voc via ovos_spec_tools.expand() -- no drafted or translated
content. The "unknown" (catch-all) branch is exercised with the same
language-neutral gibberish string test_fallback.py already uses
("blleerghh foo bar") -- it is not locale content, it is deliberately
unmatchable noise proving the fallthrough path, identical technique to
the existing en-US test.

One shared MiniCroft is booted with en-US as the primary language and
every covered locale as a secondary_lang (ovoscope>=1.6.5a1 /
padacioso>=2.2.3a1, cross-language detach fix) -- though this skill's
own routing does not depend on padacioso/padatious/adapt at all (it is a
pure fallback-pipeline + voc_match skill), so this mainly exercises
MiniCroft's per-locale resource loading, not intent-pipeline routing.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-fallback-unknown.openvoiceos"

_IGNORE = [
    "speak",
    "recognizer_loop:audio_output_start",
    "recognizer_loop:audio_output_end",
]

END2END_DIR = Path(__file__).parent

LANGS = [
    "ca-ES", "cs-CZ", "da-DK", "de-DE", "es-ES", "eu-ES", "fa-IR",
    "fr-FR", "gl-ES", "hu-HU", "it-IT", "nl-NL", "pl-PL", "pt-BR",
    "pt-PT", "ro-RO", "ru-RU", "sv-SE",
]

# Language-neutral gibberish, identical to test_fallback.py's en-US row --
# proves the "unknown" fallthrough branch fires when no question/who.is/
# why.is vocab matches, in every covered locale.
UNKNOWN_UTTERANCE = "blleerghh foo bar"


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


ALL_ROWS = []
for _lang in LANGS:
    for _row in _load_rows(_lang):
        ALL_ROWS.append(_row)
    ALL_ROWS.append({
        "skill_id": SKILL_ID,
        "utterance": UNKNOWN_UTTERANCE,
        "lang": _lang,
        "expected_dialog": "unknown",
        "needs_manual": False,
        "machine_generated": False,
    })


def _as_param(row):
    tag = "tier2" if row.get("machine_generated") else "tier1"
    return pytest.param(row, id=f"{row['lang']}-{tag}-{row['expected_dialog']}-{row['utterance']}")


GOLDEN_ROWS = [_as_param(r) for r in ALL_ROWS]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID], secondary_langs=LANGS)
    yield mc
    mc.stop()


def _speak_dialog(mc, text, lang, session_id):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = ["ovos-fallback-pipeline-plugin-low"]
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        eof_msgs=["ovos.utterance.handled"],
        ignore_messages=[],
    )
    capture.capture(utterance, timeout=30)
    messages = capture.finish()
    for m in messages:
        if m.msg_type in ("speak", "ovos.utterance.speak"):
            meta = (m.data or {}).get("meta") or {}
            if meta.get("skill") == SKILL_ID:
                return meta.get("dialog")
    return None


def _golden_id(row):
    return f"{row['lang']}-{row['expected_dialog']}-{row['utterance']}"


# Regression pin for real routing defects previously reproduced by this
# pass (gl-ES/ro-RO "que"/"ce este"/"ce va"/"ce a făcut" question.voc
# entries being literal substrings of the corresponding why.is.voc
# phrases). handle_fallback() now evaluates all three vocab classes and
# picks the *longest* matched phrase instead of the first one checked in
# fixed ['question', 'who.is', 'why.is'] order, so those rows pass outright
# and no longer need an entry here. Kept as an empty, ready-to-use
# mechanism for any future locale/order regression.
KNOWN_BUGS = {}


@pytest.mark.timeout(300)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_fallback_dialog_multilang(minicroft, row):
    dialog = _speak_dialog(minicroft, row["utterance"], row["lang"], f"golden-{_golden_id(row)}")
    matched = dialog == row["expected_dialog"]
    bug_key = (row["lang"], row["utterance"])
    if bug_key in KNOWN_BUGS and not matched:
        pytest.xfail(reason=f"known-bug: {KNOWN_BUGS[bug_key]}")
    if row.get("machine_generated") and not matched:
        pytest.xfail(reason="coverage-gap (machine-drafted, pending native validation)")
    assert matched, (
        f"[{row['lang']}] {row['utterance']!r}: expected dialog "
        f"{row['expected_dialog']!r}, got {dialog!r}"
    )
