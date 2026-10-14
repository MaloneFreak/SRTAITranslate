import ast
import re
from pathlib import Path

import pytest

from srtai import languages
from srtai.subtitles import io as srt_io
from srtai.subtitles import text as tx


@pytest.mark.parametrize("content, dialogue, texts", [
    ("{\\an8}<i>Where are you going\nat this hour?</i>", False, ["Where are you going at this hour?"]),
    ("- Hi.\n- Hello, John.", True, ["Hi.", "Hello, John."]),
    ("Where?\n- Home.", True, ["Where?", "Home."]),
    ("- Where are you going\nat this hour?", False, ["Where are you going at this hour?"]),
    ("[DOOR SLAMS]\nJOHN: Get out!", True, ["[DOOR SLAMS]", "JOHN: Get out!"]),
    ("JOHN: I said\nno way!", True, ["JOHN: I said no way!"]),
    ("I said <i>no</i>!", False, ["I said <i>no</i>!"]),
])
def test_split_cue(content, dialogue, texts):
    parts = tx.split_cue(content)
    assert parts.dialogue == dialogue
    assert [s.text for s in parts.segments] == texts


def test_split_cue_keeps_wrappers_and_music():
    parts = tx.split_cue("{\\an8}<i>Hello\nthere</i>")
    assert (parts.prefix, parts.open_tags, parts.close_tags) == ("{\\an8}", "<i>", "</i>")
    music = tx.split_cue("♪ Never gonna stop ♪").segments[0]
    assert (music.lead, music.text, music.trail) == ("♪ ", "Never gonna stop", " ♪")
    assert not tx.split_cue("♪♪").segments[0].translatable


def test_join_cue_roundtrip_dialogue():
    parts = tx.split_cue("- Hi.\n- Hello.")
    parts.segments[0].translation, parts.segments[1].translation = "Oi.", "Olá."
    assert tx.join_cue(parts) == "- Oi.\n- Olá."


def test_wrap_balances_lines_and_respects_tags():
    lines = tx.wrap("This is a long subtitle line that should be split nicely, in two lines.", 42)
    assert len(lines) == 2 and all(len(l) <= 42 for l in lines)
    assert tx.wrap("Short.", 42) == ["Short."]
    tagged = tx.wrap('<font color="#ff0">This is a long subtitle</font> line that should be split nicely.', 30)
    assert all(l.count("<") == l.count(">") for l in tagged)
    assert tx.wrap("x" * 200, 0) == ["x" * 200]


def test_remove_sdh():
    assert tx.remove_sdh("[DOOR SLAMS]\nJOHN: Get out!") == "Get out!"
    assert tx.remove_sdh("- (laughs)\n- That's funny.") == "That's funny."
    assert tx.remove_sdh("(sighs)") == ""


def test_sentence_helpers():
    assert tx.merge_texts(["I think we should...", "...go home now."]) == "I think we should go home now."
    assert not tx.ends_sentence("Hello...") and tx.ends_sentence("Hello.")
    assert tx.continues_sentence("and then") and not tx.continues_sentence("And then")
    parts = tx.split_proportional("Eu acho que nós deveríamos ir para casa agora, antes que chova.", [20, 25])
    assert len(parts) == 2 and all(parts)
    assert tx.split_proportional("Sim.", [5, 5]) is None


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "cp1252"])
def test_read_detects_encoding(tmp_path, encoding):
    text = "1\n00:00:01,000 --> 00:00:02,000\nCafé crème, s'il vous plaît.\n\n"
    path = tmp_path / "a.srt"
    path.write_bytes(text.encode(encoding))
    sub = srt_io.read(path)
    assert sub.cues[0].content == "Café crème, s'il vous plaît."


def test_read_rejects_non_subtitles(tmp_path):
    path = tmp_path / "x.srt"
    path.write_text("just some text")
    with pytest.raises(srt_io.SubtitleError):
        srt_io.read(path)


def test_languages():
    assert languages.get("pt").code == "pt-BR"
    assert languages.get("PT-br").nllb == "por_Latn"
    assert languages.get("zh").code == "zh-Hans"
    assert languages.get("auto") is None
    assert languages.require("de").deepl_source == "DE"
    codes = [l.code for l in languages.LANGUAGES]
    assert len(codes) == len(set(codes))
    assert all(l.nllb and re.fullmatch(r"[a-z]{3}_[A-Z][a-z]{3}", l.nllb) for l in languages.LANGUAGES)


def test_every_ui_string_has_a_portuguese_translation():
    gui = Path(__file__).resolve().parent.parent / "srtai" / "gui"
    src = (gui / "i18n.py").read_text(encoding="utf-8")
    pt = ast.literal_eval(src[src.index("PT = {") + 5: src.index("\n}\n") + 2])
    used = set()
    for f in gui.glob("*.py"):
        code = f.read_text(encoding="utf-8")
        used |= set(re.findall(r'\bt\(\s*"((?:[^"\\]|\\.)*)"', code))
        for one, many in re.findall(r'plural\([^,]+,\s*"([^"]+)",\s*"([^"]+)"', code):
            used |= {one, many}
    from srtai.engines import providers

    used |= {p.note for p in providers.PROVIDERS if p.note}
    missing = sorted(u for u in used if u not in pt)
    assert not missing, missing
