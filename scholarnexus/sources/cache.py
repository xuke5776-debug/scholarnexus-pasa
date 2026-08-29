"""SQLite 双层持久化缓存（查询级 + 论文级），跨查询复用以压低 API 调用数。"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Optional


class DiskCache:
    def __init__(self, path: str = ".sn_cache/cache.sqlite", ttl_days: float = 30.0):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.ttl = ttl_days * 86400
        self._local = threading.local()
        self._init()

    @property
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30)
            c.execute("PRAGMA journal_mode=WAL")
            self._local.conn = c
        return c

    def _init(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS kv ("
                          " k TEXT PRIMARY KEY, v TEXT NOT NULL,"
                          " ts REAL NOT NULL, ns TEXT)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ns ON kv(ns)")
        self.conn.commit()

    def get(self, key: str) -> Optional[Any]:
        row = self.conn.execute("SELECT v, ts FROM kv WHERE k=?", (key,)).fetchone()
        if not row:
            return None
        v, ts = row
        if self.ttl > 0 and time.time() - ts > self.ttl:
            return None
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any, ns: str = ""):
        self.conn.execute("INSERT OR REPLACE INTO kv(k,v,ts,ns) VALUES(?,?,?,?)",
                          (key, json.dumps(value, ensure_ascii=False),
                           time.time(), ns))
        self.conn.commit()

    def stats(self) -> dict:
        cur = self.conn.execute("SELECT ns, COUNT(*) FROM kv GROUP BY ns")
        return {ns or "_": n for ns, n in cur.fetchall()}
