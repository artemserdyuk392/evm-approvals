"""SQLite cache of the last scanned block and the approval pairs seen so far,
so a repeat scan reads only new blocks instead of the whole history. The seen
table is what makes an incremental scan still return the full current set."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_state (
    chain_id INTEGER NOT NULL,
    owner TEXT NOT NULL,
    last_block INTEGER NOT NULL,
    PRIMARY KEY (chain_id, owner)
);
CREATE TABLE IF NOT EXISTS seen (
    chain_id INTEGER NOT NULL,
    owner TEXT NOT NULL,
    token TEXT NOT NULL,
    spender TEXT NOT NULL,
    kind TEXT NOT NULL,
    last_block INTEGER NOT NULL,
    last_value TEXT NOT NULL,
    last_tx TEXT NOT NULL,
    PRIMARY KEY (chain_id, owner, token, spender, kind)
);
"""


class Cache:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(_SCHEMA)

    def get_last_block(self, chain_id, owner):
        row = self.conn.execute(
            "SELECT last_block FROM scan_state WHERE chain_id=? AND owner=?",
            (chain_id, owner.lower())).fetchone()
        return row[0] if row else None

    def set_last_block(self, chain_id, owner, block):
        self.conn.execute(
            "INSERT INTO scan_state (chain_id, owner, last_block) VALUES (?,?,?) "
            "ON CONFLICT(chain_id, owner) DO UPDATE SET last_block=excluded.last_block",
            (chain_id, owner.lower(), block))
        self.conn.commit()

    def upsert_seen(self, chain_id, owner, records):
        rows = [(chain_id, owner.lower(), r["token"], r["spender"], r["kind"],
                 int(r["block"]), str(r["value"]), r.get("tx", ""))
                for r in records]
        # Keep the row from the highest block so last_value tracks the most
        # recent approve amount, not whichever record was written last.
        self.conn.executemany(
            "INSERT INTO seen "
            "(chain_id, owner, token, spender, kind, last_block, last_value, last_tx) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(chain_id, owner, token, spender, kind) DO UPDATE SET "
            "last_block=excluded.last_block, last_value=excluded.last_value, "
            "last_tx=excluded.last_tx WHERE excluded.last_block >= seen.last_block",
            rows)
        self.conn.commit()

    def get_seen(self, chain_id, owner):
        cur = self.conn.execute(
            "SELECT token, spender, kind, last_block, last_value, last_tx "
            "FROM seen WHERE chain_id=? AND owner=?", (chain_id, owner.lower()))
        return [{"token": t, "spender": s, "kind": k, "block": b,
                 "value": v, "tx": tx}
                for (t, s, k, b, v, tx) in cur.fetchall()]

    def close(self):
        self.conn.close()
