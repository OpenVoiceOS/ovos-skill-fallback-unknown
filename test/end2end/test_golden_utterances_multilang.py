"""Golden utterances in every locale pick the right fallback dialog.

This skill is a fallback skill. It registers no ``.intent`` files, so the m2v
pipeline builds no prototypes for it, and no intent engine routes to it. Its
fallback handler (``ovos_skill_fallback_unknown.UnknownSkill.handle_fallback``)
matches the utterance against ``question.voc``, ``who_is.voc`` and
``why_is.voc``, lets the longest matched phrase win, and speaks the dialog of
that name. With no match it speaks ``unknown``. The ``intent_label`` of a
golden row is the name of the dialog the skill must pick, read from the
``meta.dialog`` field of the ``ovos.utterance.speak`` message. The dialog text
is random and is never asserted.

Golden rows (``golden_utterances_<lang>.jsonl``) are natural questions. Every
row runs, including rows marked ``needs_manual`` or ``machine_generated``.
Negative rows (``negative_utterances_<lang>.jsonl``) are requests for other
skills. The skill must answer each of them with the ``unknown`` dialog, never
as a question. A language-neutral string of noise proves the ``unknown`` branch
in every locale.

One MiniCroft is booted per locale and stopped before the next one boots.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-fallback-unknown.openvoiceos"
END2END_DIR = Path(__file__).parent
LOCALE_DIR = END2END_DIR.parents[1] / "ovos_skill_fallback_unknown" / "locale"
UNKNOWN = "unknown"
UNKNOWN_UTTERANCE = "blleerghh foo bar"

# (lang, utterance) -> reason, for a measured defect that a fix has not
# reached yet. A row listed here that misses is an xfail; one that passes is
# a normal pass.
#
# voc_match folds accents and matches whole words, so a bare question word in
# question.voc also matches the same word used as a conjunction or relative
# pronoun inside a command. A command for another skill then gets the
# question dialog instead of unknown.
_BARE_QUE = "gl-ES question.voc holds the bare word 'que', which also matches the conjunction 'que'"
_BARE_ZER = "eu-ES question.voc holds the bare word 'zer', which also matches 'zer' in an indirect question"
KNOWN_BUGS = {
    ("gl-ES", "fai que a música soe máis baixo"): _BARE_QUE,
    ("gl-ES", "lémbrame que teño que mercar pan mañá"): _BARE_QUE,
    ("gl-ES", "pon a radio que escoita a miña nai"): _BARE_QUE,
    ("eu-ES", "erakutsi zer dagoen gaurko egutegian"): _BARE_ZER,
}


def _load(prefix):
    rows = []
    for path in sorted(END2END_DIR.glob(f"{prefix}_*.jsonl")):
        lang = path.stem.removeprefix(f"{prefix}_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.append(row)
    return rows


GOLDEN = _load("golden_utterances")
NEGATIVE = _load("negative_utterances")
LANGS = sorted({row["lang"] for row in GOLDEN})

CASES = (
    [pytest.param(r["lang"], r["utterance"], r["intent_label"],
                  id=f"{r['lang']}-{r['intent_label']}-{r['utterance']}") for r in GOLDEN]
    + [pytest.param(r["lang"], r["utterance"], UNKNOWN,
                    id=f"{r['lang']}-negative-{r['utterance']}") for r in NEGATIVE]
    + [pytest.param(lang, UNKNOWN_UTTERANCE, UNKNOWN,
                    id=f"{lang}-noise-{UNKNOWN_UTTERANCE}") for lang in LANGS]
)


@pytest.fixture(scope="module")
def minicroft_factory():
    cache = {"lang": None, "mc": None}

    def _get(lang):
        if cache["lang"] != lang:
            if cache["mc"] is not None:
                cache["mc"].stop()
            cache["mc"] = get_minicroft([SKILL_ID], max_wait=150, lang=lang)
            cache["lang"] = lang
        return cache["mc"]

    yield _get
    if cache["mc"] is not None:
        cache["mc"].stop()


def _spoken_dialog(mc, text, lang):
    session = Session(f"golden-{lang}-{text}")
    session.lang = lang
    session.pipeline = ["ovos-fallback-pipeline-plugin-low"]
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc, eof_msgs=["ovos.utterance.handled"], ignore_messages=[])
    capture.capture(utterance, timeout=30)
    for m in capture.finish():
        if m.msg_type in ("speak", "ovos.utterance.speak"):
            meta = (m.data or {}).get("meta") or {}
            if meta.get("skill") == SKILL_ID:
                return meta.get("dialog")
    return None


def test_every_locale_has_a_golden_file():
    shipped = {p.name for p in LOCALE_DIR.iterdir() if p.is_dir()}
    assert shipped == set(LANGS), (
        f"locales without golden rows: {sorted(shipped - set(LANGS))}; "
        f"golden rows without a locale: {sorted(set(LANGS) - shipped)}"
    )


@pytest.mark.timeout(300)
@pytest.mark.parametrize("lang,utterance,expected", CASES)
def test_fallback_dialog_multilang(minicroft_factory, lang, utterance, expected):
    dialog = _spoken_dialog(minicroft_factory(lang), utterance, lang)
    if dialog != expected and (lang, utterance) in KNOWN_BUGS:
        pytest.xfail(reason=f"known bug: {KNOWN_BUGS[(lang, utterance)]}")
    assert dialog == expected, f"[{lang}] {utterance!r}: expected dialog {expected!r}, got {dialog!r}"
