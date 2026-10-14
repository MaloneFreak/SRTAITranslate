"""The translation pipeline: SRT file in, translated SRT file out.

Steps for each file:
 1. read (encoding detection) and optionally remove hearing-impaired annotations
 2. split cues into segments (dialogue lines, italics, music notes...)
 3. detect the source language when set to auto
 4. build translation units (merging broken sentences for engines without context)
 5. reuse cached translations, batch the rest, translate in parallel with retries
 6. rebuild cues with balanced line breaks and write the new file
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import srt

from .. import languages
from ..engines.base import (AuthError, CancelledError, ConfigError, Engine, EngineError,
                            TranslationRequest)
from ..subtitles import io as srt_io
from ..subtitles import text as tx
from .cache import TranslationCache
from .detect import detect_language

log = logging.getLogger(__name__)

MAX_MERGE_CUES = 3
MAX_MERGE_CHARS = 260
MAX_MERGE_GAP = 2.0  # seconds between cues


@dataclass
class JobOptions:
    source_lang: str = languages.AUTO
    target_lang: str = "pt-BR"
    max_line_length: int = 42
    merge_sentences: bool = True
    bilingual: bool = False
    remove_sdh: bool = False
    output_dir: str = ""                 # empty: next to the input file
    filename_pattern: str = "{name}.{lang}"
    output_encoding: str = "utf-8"
    overwrite: bool = True
    use_cache: bool = True
    context_notes: str = ""
    glossary: str = ""
    formality: str = "default"


@dataclass
class Event:
    kind: str           # status | file_start | progress | preview | warning | file_done | file_error | done
    file: Optional[str] = None
    data: dict = field(default_factory=dict)


@dataclass
class FileResult:
    input_path: Path
    output_path: Optional[Path] = None
    cues: int = 0
    segments: int = 0
    from_cache: int = 0
    failed: int = 0
    source_lang: Optional[str] = None
    seconds: float = 0.0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.output_path is not None


@dataclass
class _Unit:
    text: str
    refs: list[tuple[int, int]]      # (cue index, segment index)
    weights: list[int]
    translation: Optional[str] = None


def parse_glossary(raw: str) -> list[tuple[str, str]]:
    pairs = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s*(?:=>|->|→|=|\t)\s*", line, maxsplit=1)
        source = parts[0].strip()
        target = parts[1].strip() if len(parts) > 1 else source
        if source:
            pairs.append((source, target or source))
    return pairs


_LANG_SUFFIX_RE = re.compile(r"^[a-z]{2,3}(?:[-_][A-Za-z]{2,4})?$")


def output_path_for(input_path: Path, options: JobOptions, target: languages.Language) -> Path:
    stem = input_path.stem
    head, _, last = stem.rpartition(".")
    if head and (_LANG_SUFFIX_RE.match(last) and (languages.get(last) or last.lower() in {"eng", "por", "spa", "ger"})):
        stem = head  # "Movie.en" -> "Movie"
    name = (options.filename_pattern or "{name}.{lang}").format(name=stem, lang=target.code)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    out_dir = Path(options.output_dir) if options.output_dir else input_path.parent
    out = out_dir / f"{name}.srt"
    if out.resolve() == input_path.resolve() or (out.exists() and not options.overwrite):
        n = 2
        while True:
            candidate = out_dir / f"{name} ({n}).srt"
            if not candidate.exists():
                return candidate
            n += 1
    return out


class SubtitleTranslator:
    """Runs translation jobs. Thread-safe cancellation via ``cancel()``."""

    def __init__(self, engine: Engine, options: JobOptions, cache: Optional[TranslationCache] = None,
                 on_event: Optional[Callable[[Event], None]] = None):
        self.engine = engine
        self.options = options
        self.cache = cache if (cache is not None and options.use_cache) else None
        self.on_event = on_event or (lambda e: None)
        self._cancel = threading.Event()
        self._prepared = False

    # -- public API -------------------------------------------------------
    def cancel(self) -> None:
        self._cancel.set()
        self.engine.cancel_event.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self, paths: list[str | Path]) -> list[FileResult]:
        results = []
        for path in paths:
            if self.cancelled:
                break
            results.append(self.translate_file(Path(path)))
        self.on_event(Event("done", data={"results": results, "cancelled": self.cancelled}))
        return results

    def translate_file(self, path: Path) -> FileResult:
        result = FileResult(input_path=path)
        started = time.monotonic()
        if not self.cancelled:
            self.engine.cancel_event.clear()  # may be set by a failed previous file
        self.on_event(Event("file_start", str(path)))
        try:
            self._translate_file(path, result)
        except CancelledError:
            result.error = "cancelled"
        except (AuthError, ConfigError, EngineError, srt_io.SubtitleError) as exc:
            result.error = str(exc)
        except Exception as exc:  # unexpected bug: keep the app alive and log it
            log.exception("Unexpected error translating %s", path)
            result.error = f"Unexpected error: {exc}"
        result.seconds = time.monotonic() - started
        if result.ok:
            self.on_event(Event("file_done", str(path), {"result": result}))
        else:
            self.on_event(Event("file_error", str(path), {"result": result, "error": result.error}))
        return result

    # -- internals --------------------------------------------------------
    def _status(self, message: str, fraction: Optional[float] = None, file: Optional[str] = None) -> None:
        self.on_event(Event("status", file, {"message": message, "fraction": fraction}))

    def _translate_file(self, path: Path, result: FileResult) -> None:
        opts = self.options
        target = languages.require(opts.target_lang)
        sub = srt_io.read(path)
        cues = sub.cues
        if opts.remove_sdh:
            for cue in cues:
                cue.content = tx.remove_sdh(cue.content)
            cues = [c for c in cues if c.content.strip()]
        result.cues = len(cues)
        originals = [c.content for c in cues]
        parts = [tx.split_cue(c.content) for c in cues]

        source = languages.get(opts.source_lang)
        if source is None:
            source = detect_language([s.text for p in parts for s in p.segments if s.translatable])
            if source is None and self.engine.needs_source_language:
                raise ConfigError("Could not detect the source language. Please choose it manually.")
            self._status(f"Detected language: {source.name if source else 'unknown'}", file=str(path))
        result.source_lang = source.code if source else None
        if source and source.code == target.code:
            raise ConfigError(f"The subtitle is already in {target.name}.")

        if not self._prepared:
            self.engine.prepare(lambda msg, frac: self._status(msg, frac, str(path)))
            self._prepared = True

        units = self._build_units(cues, parts)
        result.segments = sum(len(u.refs) for u in units)
        total = result.segments
        done = 0

        def report(unit: _Unit) -> None:
            nonlocal done
            done += len(unit.refs)
            ci = unit.refs[0][0]
            self.on_event(Event("progress", str(path), {"done": done, "total": total}))
            self.on_event(Event("preview", str(path), {
                "index": ci + 1, "start": cues[ci].start, "original": unit.text,
                "translation": unit.translation if unit.translation is not None else "",
            }))

        signature = self._signature()
        src_code = source.code if source else "auto"
        if self.cache:
            cached = self.cache.get_many(signature, src_code, target.code, [u.text for u in units])
            for unit in units:
                if unit.text in cached:
                    unit.translation = cached[unit.text]
                    result.from_cache += len(unit.refs)
                    report(unit)

        pending = [u for u in units if u.translation is None]
        if pending:
            self._run_units(pending, units, source, target, report, signature, src_code)

        # Merged sentences that could not be split back are translated line by line.
        retry_units: list[_Unit] = []
        for unit in units:
            if unit.translation is None:
                continue
            if len(unit.refs) == 1:
                ci, si = unit.refs[0]
                parts[ci].segments[si].translation = unit.translation
                continue
            pieces = tx.split_proportional(unit.translation, unit.weights)
            if pieces is None:
                for ci, si in unit.refs:
                    retry_units.append(_Unit(self._unit_text(parts[ci].segments[si]), [(ci, si)], [1]))
            else:
                for (ci, si), piece in zip(unit.refs, pieces):
                    parts[ci].segments[si].translation = piece
        if retry_units:
            self._run_units(retry_units, retry_units, source, target, lambda u: None, signature, src_code)
            for unit in retry_units:
                if unit.translation is not None:
                    ci, si = unit.refs[0]
                    parts[ci].segments[si].translation = unit.translation

        failed = sum(1 for p in parts for s in p.segments if s.translatable and s.translation is None)
        result.failed = failed
        if failed:
            self.on_event(Event("warning", str(path), {
                "message": f"{failed} line(s) could not be translated and were kept in the original language."}))
        if self.cancelled:
            raise CancelledError()

        new_cues = []
        for cue, part, original in zip(cues, parts, originals):
            content = tx.join_cue(part, opts.max_line_length)
            if opts.bilingual:
                plain_original = tx.ASS_RE.sub("", original).strip()
                content = f'{content}\n<font color="#bfbfbf">{plain_original}</font>'
            new_cues.append(srt.Subtitle(index=cue.index, start=cue.start, end=cue.end, content=content))
        out_path = output_path_for(path, opts, target)
        srt_io.write(out_path, new_cues, encoding=opts.output_encoding)
        result.output_path = out_path
        log.info("Wrote %s (%d cues, %d cached, %d failed)", out_path, len(new_cues), result.from_cache, failed)

    def _signature(self) -> str:
        o = self.options
        extra = hashlib.sha1(f"{o.formality}|{o.glossary}|{o.context_notes}".encode()).hexdigest()[:10]
        return f"{self.engine.signature()}|{extra}"

    def _unit_text(self, seg: tx.Segment) -> str:
        return seg.text if self.engine.supports_tags else tx.strip_tags(seg.text)

    def _build_units(self, cues: list[srt.Subtitle], parts: list[tx.CueParts]) -> list[_Unit]:
        units: list[_Unit] = []
        merge = self.options.merge_sentences and self.engine.prefers_sentences
        open_unit: Optional[_Unit] = None
        last_end = None
        for ci, part in enumerate(parts):
            single = (not part.dialogue and len(part.segments) == 1 and part.segments[0].translatable)
            for si, seg in enumerate(part.segments):
                if not seg.translatable:
                    open_unit = None
                    continue
                text = self._unit_text(seg)
                if not text.strip():
                    continue
                if (merge and single and open_unit is not None and last_end is not None
                        and len(open_unit.refs) < MAX_MERGE_CUES
                        and len(open_unit.text) + len(text) < MAX_MERGE_CHARS
                        and (cues[ci].start - last_end).total_seconds() < MAX_MERGE_GAP
                        and not tx.ends_sentence(open_unit.text)
                        and tx.continues_sentence(text)):
                    open_unit.text = tx.merge_texts([open_unit.text, text])
                    open_unit.refs.append((ci, si))
                    open_unit.weights.append(len(text))
                else:
                    unit = _Unit(text, [(ci, si)], [len(text)])
                    units.append(unit)
                    open_unit = unit if (merge and single) else None
                last_end = cues[ci].end
            if not single:
                open_unit = None
        return units

    def _run_units(self, pending: list[_Unit], all_units: list[_Unit], source, target,
                   report: Callable[[_Unit], None], signature: str, src_code: str) -> None:
        engine = self.engine
        opts = self.options
        glossary = parse_glossary(opts.glossary)
        position = {id(u): i for i, u in enumerate(all_units)}

        # Engines without context translate identical lines once.
        groups: dict[str, list[_Unit]] = {}
        if not engine.uses_context:
            for unit in pending:
                groups.setdefault(unit.text, []).append(unit)
            work = [g[0] for g in groups.values()]
        else:
            work = pending

        batches = [work[i: i + max(1, engine.batch_size)] for i in range(0, len(work), max(1, engine.batch_size))]

        def make_request(batch: list[_Unit]) -> TranslationRequest:
            req = TranslationRequest(texts=[u.text for u in batch], source=source, target=target,
                                     notes=opts.context_notes, glossary=glossary, formality=opts.formality)
            if engine.uses_context:
                first, last = position[id(batch[0])], position[id(batch[-1])]
                req.context_before = [u.text for u in all_units[max(0, first - 3): first]]
                req.context_after = [u.text for u in all_units[last + 1: last + 3]]
            return req

        def translate_batch(batch: list[_Unit], depth: int = 0) -> list[Optional[str]]:
            if self.cancelled:
                raise CancelledError()
            try:
                out = engine.translate(make_request(batch))
            except (AuthError, ConfigError, CancelledError):
                raise
            except EngineError as exc:
                if exc.retryable:
                    raise  # the HTTP layer already retried with backoff; give up on this file
                if len(batch) == 1:
                    log.warning("Line could not be translated: %s", exc)
                    return [None]
                log.warning("Batch of %d failed (%s); retrying in smaller parts", len(batch), exc)
                out = [None] * len(batch)
            out = list(out) + [None] * (len(batch) - len(out))
            missing = [i for i, t in enumerate(out) if t is None]
            if missing and len(batch) > 1 and depth < 6:
                sub = [batch[i] for i in missing]
                half = max(1, len(sub) // 2)
                fixed: list[Optional[str]] = []
                for chunk in (sub[:half], sub[half:]):
                    if chunk:
                        fixed.extend(translate_batch(chunk, depth + 1))
                for i, value in zip(missing, fixed):
                    out[i] = value
            return out

        def finish(batch: list[_Unit], out: list[Optional[str]]) -> None:
            pairs = []
            for unit, value in zip(batch, out):
                members = groups.get(unit.text, [unit]) if not engine.uses_context else [unit]
                for member in members:
                    member.translation = value
                    report(member)
                if value is not None:
                    pairs.append((unit.text, value))
            if self.cache:
                self.cache.put_many(signature, src_code, target.code, pairs)

        workers = max(1, engine.max_workers)
        if workers == 1:
            for batch in batches:
                finish(batch, translate_batch(batch))
            return
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="srtai") as pool:
            futures: dict[Future, list[_Unit]] = {}
            queue = list(batches)
            try:
                while queue or futures:
                    while queue and len(futures) < workers:
                        batch = queue.pop(0)
                        futures[pool.submit(translate_batch, batch)] = batch
                    done, _ = wait(list(futures), return_when=FIRST_COMPLETED)
                    for fut in done:
                        batch = futures.pop(fut)
                        finish(batch, fut.result())
            except BaseException:
                engine.cancel_event.set()  # stop the other workers quickly
                for fut in futures:
                    fut.cancel()
                raise
