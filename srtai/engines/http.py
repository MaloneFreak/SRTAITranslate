"""Small HTTP helper with retries, backoff and readable errors."""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from typing import Any, Optional

import requests

from .. import __version__
from .base import AuthError, CancelledError, EngineError

log = logging.getLogger(__name__)

USER_AGENT = f"SRTAITranslate/{__version__}"
_RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}

_session_local = threading.local()


def session() -> requests.Session:
    sess = getattr(_session_local, "session", None)
    if sess is None:
        sess = requests.Session()
        sess.headers["User-Agent"] = USER_AGENT
        _session_local.session = sess
    return sess


def _error_text(resp: requests.Response) -> str:
    try:
        data = resp.json()
    except ValueError:
        return resp.text[:300].strip() or resp.reason
    if isinstance(data, dict):
        err = data.get("error", data)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("detail") or err)[:300]
        if isinstance(err, str):
            return err[:300]
        msg = data.get("message") or data.get("detail")
        if msg:
            return str(msg)[:300]
    if isinstance(data, list) and data and isinstance(data[0], dict):
        err = data[0].get("error", data[0])
        return str(err.get("message") if isinstance(err, dict) else err)[:300]
    return str(data)[:300]


def request_json(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    payload: Any = None,
    params: Optional[dict] = None,
    timeout: float = 120,
    retries: int = 5,
    cancel_event: Optional[threading.Event] = None,
) -> Any:
    """Send a JSON request and return the decoded JSON response.

    Retries network errors, 429 and 5xx with exponential backoff (honouring
    Retry-After). Raises AuthError for 401/403 and EngineError otherwise.
    """
    attempt = 0
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        try:
            resp = session().request(
                method,
                url,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
                params=params,
                timeout=timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            if attempt >= retries:
                raise EngineError(
                    f"Could not connect to {_host(url)}. Check your internet connection or the server URL.",
                    retryable=True,
                ) from exc
            delay = _backoff(attempt)
        except requests.exceptions.Timeout as exc:
            if attempt >= retries:
                raise EngineError(f"{_host(url)} took too long to answer.", retryable=True) from exc
            delay = _backoff(attempt)
        else:
            if resp.ok:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise EngineError(f"Invalid response from {_host(url)}.") from exc
            message = _error_text(resp)
            if resp.status_code in (401, 403):
                raise AuthError(f"Access denied by {_host(url)} ({resp.status_code}): {message}",
                                status=resp.status_code)
            if resp.status_code == 456:  # DeepL quota exceeded
                raise EngineError(f"Quota exceeded: {message}", status=456)
            if resp.status_code not in _RETRY_STATUS or attempt >= retries:
                raise EngineError(f"{_host(url)} returned {resp.status_code}: {message}",
                                  retryable=resp.status_code in _RETRY_STATUS, status=resp.status_code)
            delay = _retry_after(resp) or _backoff(attempt)
            log.warning("%s returned %s, retrying in %.1fs: %s", _host(url), resp.status_code, delay, message)
        attempt += 1
        _sleep(delay, cancel_event)


def _host(url: str) -> str:
    try:
        return url.split("//", 1)[1].split("/", 1)[0]
    except IndexError:
        return url


def _backoff(attempt: int) -> float:
    return min(60.0, 2.0 * (2 ** attempt)) * (0.75 + random.random() * 0.5)


def _retry_after(resp: requests.Response) -> Optional[float]:
    value = resp.headers.get("retry-after")
    if not value:
        return None
    try:
        return min(120.0, max(0.5, float(value)))
    except ValueError:
        return None


def _sleep(seconds: float, cancel_event: Optional[threading.Event]) -> None:
    if cancel_event is None:
        time.sleep(seconds)
    elif cancel_event.wait(seconds):
        raise CancelledError()
