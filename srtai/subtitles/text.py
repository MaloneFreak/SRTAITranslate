"""Subtitle text handling: splitting cues into translatable segments and rebuilding them.

The goal is to send engines clean sentences while keeping everything that makes a
subtitle file work: ASS position tags ({\\an8}), italics wrappers, dialogue dashes,
music notes and readable line lengths.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

TAG_RE = re.compile(r"</?(?:i|b|u|s|font)(?:\s[^<>]*)?>", re.IGNORECASE)
ASS_RE = re.compile(r"\{\\[^{}]*\}")
DIALOGUE_RE = re.compile(r"^\s*[-–—]\s*")
MUSIC_CHARS = "♪♫"
_WRAP_OPEN_RE = re.compile(r"^((?:<(?:i|b|u)>|<font\b[^<>]*>)+)", re.IGNORECASE)
_WRAP_CLOSE_RE = re.compile(r"((?:</(?:i|b|u|font)>)+)$", re.IGNORECASE)
_TOKEN_RE = re.compile(r"(?:<[^<>]*>|\S)+")
_SDH_BRACKETS_RE = re.compile(r"\[[^\[\]]*\]|\([^()]*\)|（[^（）]*）")
_SPEAKER_RE = re.compile(r"^(\s*[-–—]?\s*)[A-Z][A-Z0-9 .'\-]{1,30}:\s*")
_TERMINAL = tuple(".!?…\"'»”。！？)♪♫")
_ELLIPSIS_RE = re.compile(r"^(?:\.\.\.|…)\s*")


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def visible_len(text: str) -> int:
    return len(strip_tags(text))


def has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in strip_tags(text))


@dataclass
class Segment:
    text: str                 # text sent to the translator
    lead: str = ""            # kept as-is before the text ("- ", "♪ ")
    trail: str = ""           # kept as-is after the text (" ♪")
    translatable: bool = True
    translation: str | None = None

    def rendered(self) -> str:
        body = self.translation if self.translation is not None else self.text
        return f"{self.lead}{body}{self.trail}"


@dataclass
class CueParts:
    prefix: str = ""          # ASS override tags such as {\an8}
    open_tags: str = ""       # wrapper tags around the whole cue, e.g. "<i>"
    close_tags: str = ""
    dialogue: bool = False    # one segment per line (speakers, sound descriptions)
    segments: list[Segment] = field(default_factory=list)


def remove_sdh(content: str) -> str:
    """Remove hearing-impaired annotations: [DOOR SLAMS], (laughs), SPEAKER: labels."""
    original = content.split("\n")
    lines = []
    for line in original:
        line = _SDH_BRACKETS_RE.sub("", line)
        line = _SPEAKER_RE.sub(r"\1", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if has_letters(line) or strip_tags(line).strip(" -–—.,"):
            lines.append(line)
    # A lone dialogue dash left over from removed lines is no longer a dialogue.
    if len(lines) == 1 and len(original) > 1:
        lines[0] = DIALOGUE_RE.sub("", lines[0])
    return "\n".join(lines)


def _split_music(text: str) -> tuple[str, str, str]:
    lead = trail = ""
    m = re.match(rf"^([{MUSIC_CHARS}]+\s*)", text)
    if m:
        lead = m.group(1)
        text = text[m.end():]
    m = re.search(rf"(\s*[{MUSIC_CHARS}]+)$", text)
    if m:
        trail = m.group(1)
        text = text[: m.start()]
    return lead, text, trail


def _unwrap(lines: list[str]) -> tuple[str, str, list[str]]:
    """Detect formatting tags that wrap the whole cue (or every line identically)."""
    joined = "\n".join(lines)
    m_open = _WRAP_OPEN_RE.match(joined)
    m_close = _WRAP_CLOSE_RE.search(joined)
    if m_open and m_close:
        inner = joined[m_open.end(): m_close.start()]
        open_tags, close_tags = m_open.group(1), m_close.group(1)
        # Only a real wrapper if the inner text does not reopen/close the same tags.
        if not TAG_RE.search(inner):
            return open_tags, close_tags, inner.split("\n")
    # Every line wrapped with the same tags: <i>a</i>\n<i>b</i>
    opens, closes, inners = set(), set(), []
    for line in lines:
        mo, mc = _WRAP_OPEN_RE.match(line), _WRAP_CLOSE_RE.search(line)
        if not (mo and mc):
            return "", "", lines
        inner = line[mo.end(): mc.start()]
        if TAG_RE.search(inner):
            return "", "", lines
        opens.add(mo.group(1).lower())
        closes.add(mc.group(1).lower())
        inners.append(inner)
    if len(opens) == 1 and len(closes) == 1 and lines:
        mo = _WRAP_OPEN_RE.match(lines[0])
        mc = _WRAP_CLOSE_RE.search(lines[0])
        return mo.group(1), mc.group(1), inners
    return "", "", lines


def split_cue(content: str) -> CueParts:
    """Break a cue's content into segments ready for translation."""
    parts = CueParts()
    content = content.replace("\r\n", "\n").strip()
    prefix_tags = ASS_RE.findall(content)
    if prefix_tags:
        parts.prefix = "".join(prefix_tags)
        content = ASS_RE.sub("", content).strip()

    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    if not lines:
        return parts
    parts.open_tags, parts.close_tags, lines = _unwrap(lines)
    lines = [ln.strip() for ln in lines if ln.strip()]

    # Dialogue: a later line starts with a dash ("- Hi.\n- Hello." or "Hi.\n- Hello.").
    if len(lines) >= 2 and any(DIALOGUE_RE.match(ln) for ln in lines[1:]):
        parts.dialogue = True
        speakers: list[list[str]] = []  # [dash, text]
        for line in lines:
            m = DIALOGUE_RE.match(line)
            if m or not speakers:
                speakers.append(["- " if m else "", line[m.end():] if m else line])
            else:
                speakers[-1][1] += " " + line
        for dash, text in speakers:
            parts.segments.append(_make_segment(text, dash))
        return parts

    # Sound descriptions / speaker labels on their own line keep their own line:
    # "[DOOR SLAMS]\nJOHN: Get out!"
    if len(lines) >= 2 and any(_is_annotation_line(ln) for ln in lines):
        parts.dialogue = True
        groups: list[str] = []
        for line in lines:
            if _is_annotation_line(line) or not groups or _is_sound_line(groups[-1]):
                groups.append(line)
            else:
                groups[-1] += " " + line
        parts.segments.extend(_make_segment(g) for g in groups)
        return parts

    text = " ".join(lines)
    m = DIALOGUE_RE.match(text)
    parts.segments.append(_make_segment(text[m.end():] if m else text, "- " if m else ""))
    return parts


def _is_sound_line(line: str) -> bool:
    return bool(re.fullmatch(r"[\[(\uff08][^\[\]()]*[\])\uff09]", strip_tags(line).strip()))


def _is_annotation_line(line: str) -> bool:
    return _is_sound_line(line) or bool(_SPEAKER_RE.match(strip_tags(line).strip()))


def _make_segment(text: str, dash: str = "") -> Segment:
    lead, body, trail = _split_music(text.strip())
    body = body.strip()
    return Segment(text=body, lead=dash + lead, trail=trail, translatable=has_letters(body))


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def wrap(text: str, max_len: int = 42) -> list[str]:
    """Split text into balanced subtitle lines (usually 1-2, at most 3)."""
    text = " ".join(text.split())
    if max_len <= 0 or visible_len(text) <= max_len:
        return [text]
    words = _tokens(text)
    if len(words) < 2:
        return [text]
    n_lines = min(3, max(2, math.ceil(visible_len(text) / max_len)))
    if visible_len(text) <= 2 * max_len + 8:
        n_lines = 2
    return _balanced(words, n_lines)


def _balanced(words: list[str], n_lines: int) -> list[str]:
    lengths = [visible_len(w) for w in words]
    lines: list[str] = []
    start = 0
    for line_no in range(n_lines - 1):
        remaining_lines = n_lines - line_no
        rest = sum(lengths[start:]) + (len(words) - start - 1)
        target = rest / remaining_lines
        best_i, best_cost = start + 1, math.inf
        acc = -1
        for i in range(start + 1, len(words) - (remaining_lines - 2)):
            acc += lengths[i - 1] + 1
            cost = abs(acc - target)
            plain = strip_tags(words[i - 1])
            if plain.endswith((",", ";", ":", ".", "!", "?", "…")):
                cost -= 4  # prefer breaking after punctuation
            if acc > target:
                cost += 1  # prefer a slightly shorter top line (pyramid shape)
            if cost < best_cost:
                best_i, best_cost = i, cost
        lines.append(" ".join(words[start:best_i]))
        start = best_i
    lines.append(" ".join(words[start:]))
    return [ln for ln in lines if ln]


def join_cue(parts: CueParts, max_len: int = 42) -> str:
    """Rebuild cue content from (translated) segments."""
    if not parts.segments:
        return parts.prefix
    if parts.dialogue and len(parts.segments) > 1:
        lines = [seg.rendered().strip() for seg in parts.segments]
    else:
        lines = wrap(parts.segments[0].rendered().strip(), max_len)
    body = "\n".join(lines)
    if parts.open_tags:
        body = f"{parts.open_tags}{body}{parts.close_tags}"
    return f"{parts.prefix}{body}"


# --- Sentence merging for engines that translate each item without context ---

def ends_sentence(text: str) -> bool:
    plain = strip_tags(text).rstrip()
    if plain.endswith(("...", "…")):
        return False
    return plain.endswith(_TERMINAL)


def continues_sentence(text: str) -> bool:
    plain = strip_tags(text).lstrip()
    if not plain:
        return False
    if plain.startswith(("...", "…")):
        return True
    first = plain[0]
    return first.isalpha() and first.islower()


def merge_texts(texts: list[str]) -> str:
    merged = texts[0].rstrip()
    for nxt in texts[1:]:
        left = re.sub(r"\s*(?:\.\.\.|…)$", "", merged) if continues_sentence(nxt) else merged
        merged = f"{left} {_ELLIPSIS_RE.sub('', nxt.strip())}"
    return " ".join(merged.split())


def split_proportional(text: str, weights: list[int]) -> list[str] | None:
    """Split a translated sentence back into len(weights) parts at word boundaries.

    Returns None when the text has too few words to give every part something.
    """
    words = _tokens(text)
    n = len(weights)
    if n == 1:
        return [text.strip()]
    if len(words) < n:
        return None
    total_w = sum(max(1, w) for w in weights)
    lengths = [visible_len(w) for w in words]
    total_len = sum(lengths) + len(words) - 1
    parts: list[str] = []
    start = 0
    cum_w = 0
    for k in range(n - 1):
        cum_w += max(1, weights[k])
        target = total_len * cum_w / total_w
        best_i, best_cost = None, math.inf
        acc = sum(lengths[:start]) + start - 1
        for i in range(start + 1, len(words) - (n - k - 2)):
            acc += lengths[i - 1] + 1
            cost = abs(acc - target)
            if strip_tags(words[i - 1]).endswith((",", ";", ":", ".", "!", "?", "…")):
                cost -= max(3, total_len * 0.08)
            if cost < best_cost:
                best_i, best_cost = i, cost
        if best_i is None:
            return None
        parts.append(" ".join(words[start:best_i]))
        start = best_i
    parts.append(" ".join(words[start:]))
    if any(not p for p in parts):
        return None
    return parts
