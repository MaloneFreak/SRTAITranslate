from pathlib import Path

import srt

from srtai.core.cache import TranslationCache
from srtai.core.pipeline import JobOptions, SubtitleTranslator, output_path_for, parse_glossary
from srtai import languages

from fakes import BrokenEngine, FlakyLLM, UpperEngine


def read_cues(path: Path):
    return list(srt.parse(path.read_text(encoding="utf-8")))


def test_offline_style_engine_merges_and_keeps_structure(sample_srt):
    engine = UpperEngine()
    events = []
    tr = SubtitleTranslator(engine, JobOptions(source_lang="en", target_lang="pt-BR"), on_event=events.append)
    result = tr.translate_file(sample_srt)
    assert result.ok, result.error
    assert result.output_path.name == "Movie.pt-BR.srt"
    cues = read_cues(result.output_path)
    assert len(cues) == 9
    assert cues[0].content == "{\\an8}<i>PREVIOUSLY ON THE SHOW...</i>"
    assert cues[1].content == "- WHERE ARE YOU GOING?\n- TO THE STORE."
    # Broken sentence (cues 3+4) was sent as one sentence and split back.
    assert ["I think that we should go home before it starts raining."] in [[t for t in c if t.startswith("I think")] for c in engine.calls]
    assert cues[2].content.startswith("I THINK")
    assert cues[3].content.endswith("RAINING.")
    assert cues[4].content == "♪ NEVER GONNA STOP ♪"
    assert cues[5].content == "♪♪"
    # Identical lines are translated once.
    flat = [t for call in engine.calls for t in call]
    assert flat.count("Thank you.") == 1
    assert cues[6].content == cues[7].content == "THANK YOU."
    # Inline tags are stripped for engines that can't keep them.
    assert "<i>" not in cues[8].content
    assert {e.kind for e in events} >= {"file_start", "progress", "preview", "file_done"}


def test_llm_style_engine_retries_missing_lines_and_gets_context(sample_srt):
    engine = FlakyLLM(drop_every=3)
    tr = SubtitleTranslator(engine, JobOptions(source_lang="en", target_lang="pt-BR", max_line_length=0))
    result = tr.translate_file(sample_srt)
    assert result.ok, result.error
    assert result.failed == 0
    cues = read_cues(result.output_path)
    assert cues[1].content == "- PT:Where are you going?\n- PT:To the store."
    assert cues[8].content == "PT:[DOOR SLAMS]\nPT:JOHN: I said <i>no</i>!"
    assert any(r.context_before for r in engine.requests)
    # No merging for context-aware engines.
    assert cues[2].content == "PT:I think that we should"


def test_failed_lines_are_kept_and_reported(sample_srt):
    engine = FlakyLLM(drop_every=0, fail_texts=("Thank you.",))
    events = []
    tr = SubtitleTranslator(engine, JobOptions(source_lang="en", target_lang="pt-BR"), on_event=events.append)
    result = tr.translate_file(sample_srt)
    assert result.ok
    assert result.failed == 2
    assert any(e.kind == "warning" for e in events)
    assert read_cues(result.output_path)[6].content == "Thank you."


def test_cache_makes_second_run_free(sample_srt, tmp_path):
    cache = TranslationCache(tmp_path / "tm.sqlite3")
    first = UpperEngine()
    SubtitleTranslator(first, JobOptions(source_lang="en", target_lang="pt-BR"), cache).translate_file(sample_srt)
    second = UpperEngine()
    result = SubtitleTranslator(second, JobOptions(source_lang="en", target_lang="pt-BR"), cache).translate_file(sample_srt)
    assert result.ok
    assert second.calls == []
    assert result.from_cache == result.segments


def test_engine_error_is_reported_not_raised(sample_srt):
    result = SubtitleTranslator(BrokenEngine(), JobOptions(source_lang="en")).translate_file(sample_srt)
    assert not result.ok
    assert "server exploded" in result.error


def test_bilingual_and_sdh(sample_srt):
    opts = JobOptions(source_lang="en", target_lang="pt-BR", bilingual=True, remove_sdh=True)
    result = SubtitleTranslator(UpperEngine(), opts).translate_file(sample_srt)
    cues = read_cues(result.output_path)
    assert cues[8].content.startswith("I SAID NO!")
    assert '<font color="#bfbfbf">I said <i>no</i>!</font>' in cues[8].content


def test_auto_detect_source(sample_srt):
    result = SubtitleTranslator(UpperEngine(), JobOptions(target_lang="de")).translate_file(sample_srt)
    assert result.ok
    assert result.source_lang == "en"


def test_cancel_before_start(sample_srt):
    tr = SubtitleTranslator(UpperEngine(), JobOptions(source_lang="en"))
    tr.cancel()
    assert tr.run([sample_srt]) == []


def test_output_names(tmp_path):
    pt = languages.require("pt-BR")
    src = tmp_path / "Show.S01E01.eng.srt"
    src.write_text("x")
    assert output_path_for(src, JobOptions(), pt).name == "Show.S01E01.pt-BR.srt"
    src2 = tmp_path / "Film.srt"
    assert output_path_for(src2, JobOptions(filename_pattern="{name}_{lang}"), pt).name == "Film_pt-BR.srt"
    # Never overwrite the input file.
    same = tmp_path / "Clip.pt-BR.srt"
    same.write_text("x")
    assert output_path_for(same, JobOptions(), pt).name == "Clip.pt-BR (2).srt"


def test_parse_glossary():
    assert parse_glossary("Winterfell\nNed = Ned Stark\n# comment\nKing's Landing -> Porto Real") == [
        ("Winterfell", "Winterfell"), ("Ned", "Ned Stark"), ("King's Landing", "Porto Real")]
