"""Translation memory: a small SQLite cache of already translated texts.

It makes re-running a cancelled/crashed job instant for the parts already done and
avoids paying twice for the same lines when an API is used.
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from pathlib import Path


class TranslationCache:
    def __init__(self, path: str | Path | None):
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        if path is None:
            return
        try:
            self._conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS tm ("
                " key TEXT PRIMARY KEY, engine TEXT, src TEXT, tgt TEXT,"
                " source_text TEXT, target_text TEXT, created REAL)"
            )
            self._conn.commit()
        except sqlite3.Error:
            self._conn = None

    @property
    def enabled(self) -> bool:
        return self._conn is not None

    @staticmethod
    def make_key(signature: str, src: str, tgt: str, text: str) -> str:
        raw = "\x1f".join((signature, src, tgt, text))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def get_many(self, signature: str, src: str, tgt: str, texts: list[str]) -> dict[str, str]:
        if not self._conn or not texts:
            return {}
        keys = {self.make_key(signature, src, tgt, t): t for t in texts}
        found: dict[str, str] = {}
        with self._lock:
            items = list(keys.items())
            for i in range(0, len(items), 500):
                chunk = items[i: i + 500]
                marks = ",".join("?" * len(chunk))
                rows = self._conn.execute(
                    f"SELECT key, target_text FROM tm WHERE key IN ({marks})", [k for k, _ in chunk]
                ).fetchall()
                for key, target in rows:
                    found[keys[key]] = target
        return found

    def put_many(self, signature: str, src: str, tgt: str, pairs: list[tuple[str, str]]) -> None:
        if not self._conn or not pairs:
            return
        now = time.time()
        rows = [
            (self.make_key(signature, src, tgt, s), signature, src, tgt, s, t, now)
            for s, t in pairs
            if t is not None
        ]
        with self._lock:
            try:
                self._conn.executemany("INSERT OR REPLACE INTO tm VALUES (?,?,?,?,?,?,?)", rows)
                self._conn.commit()
            except sqlite3.Error:
                pass

    def clear(self) -> None:
        if not self._conn:
            return
        with self._lock:
            self._conn.execute("DELETE FROM tm")
            self._conn.commit()
            self._conn.execute("VACUUM")

    def count(self) -> int:
        if not self._conn:
            return 0
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM tm").fetchone()[0]

    def close(self) -> None:
        if self._conn:
            with self._lock:
                self._conn.close()
            self._conn = None
