"""Check GitHub for a newer release."""
from __future__ import annotations

import re
from typing import Optional

from .. import __version__

API_URL = "https://api.github.com/repos/MaloneFreak/SRTAITranslate/releases/latest"


def _parse(version: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", version or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - min(3, len(nums)))


def is_newer(version: str, current: str = __version__) -> bool:
    return _parse(version) > _parse(current)


def latest_release(timeout: float = 6) -> Optional[dict]:
    try:
        from ..engines import http

        resp = http.session().get(API_URL, timeout=timeout, headers={"Accept": "application/vnd.github+json"})
        if not resp.ok:
            return None
        data = resp.json()
        return {"version": data.get("tag_name", ""), "url": data.get("html_url", "")}
    except Exception:
        return None
