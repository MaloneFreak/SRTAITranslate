"""Prompts for LLM engines and tolerant parsing of their answers."""
from __future__ import annotations

import json
import re
from typing import Optional

from ..languages import Language
from .base import TranslationRequest

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def language_label(lang: Optional[Language]) -> str:
    return lang.name if lang else "the source language (detect it)"


def build_system_prompt(req: TranslationRequest) -> str:
    src = language_label(req.source)
    tgt = req.target.name
    rules = [
        f"You are an expert subtitle translator. Translate subtitle lines from {src} into {tgt}.",
        "Rules:",
        '1. Reply with JSON only, in this exact shape: {"translations": [{"id": <id>, "text": "<translation>"}]}. '
        'Return every id from "lines", in the same order, and nothing else.',
        "2. Translate each line into its own item. A line can be part of a sentence that continues in the "
        "next line; split your translation the same way so each item still matches its original line.",
        f"3. Write natural, concise, spoken {tgt} that is easy to read on screen. Keep the tone, slang, "
        "humour and register of the original.",
        "4. Keep tags such as <i>, </i>, <b> and <font ...> around the words they belong to. Keep names, "
        "numbers and units correct.",
        '5. "context_before" and "context_after" are neighbouring lines for reference only. Never translate '
        "or return them.",
        "6. Never add notes, explanations or quotes around the text. If a line should stay unchanged (a name, "
        "a sound), return it unchanged.",
    ]
    if req.formality == "formal":
        rules.append(f"7. Use formal address in {tgt}.")
    elif req.formality == "informal":
        rules.append(f"7. Use informal, casual address in {tgt}.")
    if req.glossary:
        rules.append("Glossary (always use these translations):")
        for source, target in req.glossary:
            if target and target != source:
                rules.append(f'- "{source}" -> "{target}"')
            else:
                rules.append(f'- "{source}" -> keep as "{source}"')
    if req.notes.strip():
        rules.append("About this video (use it to choose the right words): " + req.notes.strip())
    return "\n".join(rules)


def build_user_payload(req: TranslationRequest) -> str:
    payload = {
        "context_before": req.context_before,
        "lines": [{"id": i + 1, "text": text} for i, text in enumerate(req.texts)],
        "context_after": req.context_after,
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_json(text: str):
    text = _THINK_RE.sub("", text).strip()
    text = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = text.find(open_ch), text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start: end + 1])
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def parse_translations(text: str, count: int) -> list[Optional[str]]:
    """Map an LLM answer back to ``count`` items (None for anything missing)."""
    result: list[Optional[str]] = [None] * count
    data = _extract_json(text or "")
    if data is None:
        return result
    if isinstance(data, dict):
        items = data.get("translations")
        if items is None:
            items = data.get("lines", data)
    else:
        items = data

    def put(index: int, value) -> None:
        if 0 <= index < count and isinstance(value, str) and value.strip():
            result[index] = value.strip()

    if isinstance(items, dict):  # {"1": "...", "2": "..."}
        for key, value in items.items():
            try:
                put(int(key) - 1, value)
            except (TypeError, ValueError):
                continue
    elif isinstance(items, list):
        for pos, item in enumerate(items):
            if isinstance(item, dict):
                idx = item.get("id")
                value = item.get("text", item.get("translation"))
                try:
                    put(int(idx) - 1 if idx is not None else pos, value)
                except (TypeError, ValueError):
                    put(pos, value)
            else:
                put(pos, item)
    return result


# --- TranslateGemma (Google's translation model) uses a fixed prompt format ---

def translategemma_prompt(text: str, source: Optional[Language], target: Language) -> str:
    src_name = source.name if source else "English"
    src_code = source.code if source else "en"
    tgt_name, tgt_code = target.name, target.code
    return (
        f"You are a professional {src_name} ({src_code}) to {tgt_name} ({tgt_code}) translator. "
        f"Your goal is to accurately convey the meaning and nuances of the original {src_name} text "
        f"while adhering to {tgt_name} grammar, vocabulary, and cultural sensitivities.\n"
        f"Produce only the {tgt_name} translation, without any additional explanations or commentary. "
        f"Please translate the following {src_name} text into {tgt_name}:\n\n\n{text}"
    )


def is_translategemma(model: str) -> bool:
    return "translategemma" in (model or "").lower()


def split_lines_answer(answer: str, count: int) -> list[Optional[str]]:
    """Split a plain-text multi-line answer; all-or-nothing on the line count."""
    answer = _THINK_RE.sub("", answer or "").strip()
    lines = [ln.strip() for ln in answer.split("\n") if ln.strip()]
    if len(lines) != count:
        return [None] * count
    return lines
