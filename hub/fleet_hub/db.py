"""SQLite storage: members, sessions, linked agents, link codes and the event log.

Live telemetry is never stored here; it lives in memory (``fleet.py``). Calls are
synchronous: each is a single indexed statement on a local file, well under a
millisecond, so they run on the event loop directly.

Secrets are stored as SHA-256 hashes only (session ids, agent tokens, device
codes). Discord access tokens are kept so membership can be re-checked; they
only grant ``identify`` and ``guilds.members.read``.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id            TEXT PRIMARY KEY,          -- Discord user id
    name          TEXT NOT NULL,             -- server nickname, else global name
    avatar        TEXT,
    allowed       INTEGER NOT NULL DEFAULT 1,-- holds the org role, as of checked_at
    checked_at    INTEGER NOT NULL,
    access_token  TEXT,
    refresh_token TEXT,
    token_expires INTEGER,
    created_at    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id_hash     TEXT PRIMARY KEY,
    member_id   TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    created_at  INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS agents (
    id          INTEGER PRIMARY KEY,
    member_id   TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    machine     TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    last_seen   INTEGER,
    revoked     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS link_codes (
    user_code   TEXT PRIMARY KEY,
    device_hash TEXT NOT NULL UNIQUE,
    machine     TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL,
    member_id   TEXT                         -- set when a signed-in member confirms
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    member_id   TEXT NOT NULL,
    t           INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    data        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_t ON events(t);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SESSION_DAYS = 30
LINK_CODE_TTL_S = 600
# No 0/O, 1/I/L: the code is read off one screen and typed or checked on another.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def now_ms() -> int:
    return int(time.time() * 1000)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_user_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    return f"{raw[:3]}-{raw[3:]}"


def normalize_user_code(code: str) -> str:
    raw = "".join(ch for ch in code.upper() if ch.isalnum())
    return f"{raw[:3]}-{raw[3:]}" if len(raw) == 6 else code.upper()


@dataclass
class Member:
    id: str
    name: str
    avatar: str | None
    allowed: bool
    checked_at: int
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires: int | None = None

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "avatar": self.avatar}


@dataclass
class Agent:
    id: int
    member_id: str
    machine: str
    created_at: int
    last_seen: int | None
    revoked: bool


class Database:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def _one(self, sql: str, *args) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    # -- members

    def upsert_member(
        self,
        id: str,
        name: str,
        avatar: str | None,
        *,
        allowed: bool,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires: int | None = None,
    ) -> Member:
        t = now_ms()
        self.conn.execute(
            """INSERT INTO members (id, name, avatar, allowed, checked_at, access_token,
                                    refresh_token, token_expires, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, avatar=excluded.avatar,
                   allowed=excluded.allowed, checked_at=excluded.checked_at,
                   access_token=COALESCE(excluded.access_token, members.access_token),
                   refresh_token=COALESCE(excluded.refresh_token, members.refresh_token),
                   token_expires=COALESCE(excluded.token_expires, members.token_expires)""",
            (id, name, avatar, int(allowed), t, access_token, refresh_token, token_expires, t),
        )
        member = self.member(id)
        assert member is not None
        return member

    def set_allowed(self, member_id: str, allowed: bool) -> None:
        self.conn.execute(
            "UPDATE members SET allowed=?, checked_at=? WHERE id=?",
            (int(allowed), now_ms(), member_id),
        )

    def member(self, member_id: str) -> Member | None:
        row = self._one("SELECT * FROM members WHERE id=?", member_id)
        return _member(row) if row else None

    def members(self) -> list[Member]:
        rows = self.conn.execute("SELECT * FROM members ORDER BY name COLLATE NOCASE").fetchall()
        return [_member(r) for r in rows]

    # -- sessions (browser sign-in)

    def new_session(self, member_id: str) -> str:
        sid = secrets.token_urlsafe(32)
        t = now_ms()
        self.conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (sha256(sid), member_id, t, t + SESSION_DAYS * 86_400_000),
        )
        return sid

    def session_member(self, sid: str) -> Member | None:
        row = self._one(
            """SELECT m.* FROM sessions s JOIN members m ON m.id = s.member_id
               WHERE s.id_hash=? AND s.expires_at > ?""",
            sha256(sid),
            now_ms(),
        )
        return _member(row) if row else None

    def end_session(self, sid: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE id_hash=?", (sha256(sid),))

    def end_member_sessions(self, member_id: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE member_id=?", (member_id,))

    # -- agents

    def new_agent(self, member_id: str, machine: str) -> tuple[Agent, str]:
        token = secrets.token_urlsafe(32)
        cur = self.conn.execute(
            "INSERT INTO agents (member_id, token_hash, machine, created_at) VALUES (?, ?, ?, ?)",
            (member_id, sha256(token), machine[:64], now_ms()),
        )
        agent = self.agent(cur.lastrowid or 0)
        assert agent is not None
        return agent, token

    def agent(self, agent_id: int) -> Agent | None:
        row = self._one("SELECT * FROM agents WHERE id=?", agent_id)
        return _agent(row) if row else None

    def agent_by_token(self, token: str) -> Agent | None:
        row = self._one("SELECT * FROM agents WHERE token_hash=? AND revoked=0", sha256(token))
        return _agent(row) if row else None

    def agents_of(self, member_id: str) -> list[Agent]:
        rows = self.conn.execute(
            "SELECT * FROM agents WHERE member_id=? AND revoked=0 ORDER BY created_at",
            (member_id,),
        ).fetchall()
        return [_agent(r) for r in rows]

    def agent_seen(self, agent_id: int) -> None:
        self.conn.execute("UPDATE agents SET last_seen=? WHERE id=?", (now_ms(), agent_id))

    def revoke_agent(self, agent_id: int, member_id: str | None = None) -> bool:
        sql, args = "UPDATE agents SET revoked=1 WHERE id=?", [agent_id]
        if member_id is not None:
            sql += " AND member_id=?"
            args.append(member_id)
        return self.conn.execute(sql, args).rowcount > 0

    def linked_member_ids(self) -> set[str]:
        rows = self.conn.execute("SELECT DISTINCT member_id FROM agents WHERE revoked=0")
        return {r[0] for r in rows}

    # -- link codes (browser linking, spec §5.1)

    def new_link_code(self, machine: str) -> tuple[str, str]:
        """(user code shown to the member, secret device code the agent polls with)."""
        t = now_ms()
        self.conn.execute("DELETE FROM link_codes WHERE expires_at < ?", (t,))
        device = secrets.token_urlsafe(32)
        for _ in range(10):
            code = new_user_code()
            try:
                self.conn.execute(
                    "INSERT INTO link_codes VALUES (?, ?, ?, ?, ?, NULL)",
                    (code, sha256(device), machine[:64], t, t + LINK_CODE_TTL_S * 1000),
                )
                return code, device
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("couldn't allocate a link code")

    def link_code(self, user_code: str) -> sqlite3.Row | None:
        return self._one(
            "SELECT * FROM link_codes WHERE user_code=? AND expires_at > ?",
            normalize_user_code(user_code),
            now_ms(),
        )

    def confirm_link_code(self, user_code: str, member_id: str) -> bool:
        cur = self.conn.execute(
            """UPDATE link_codes SET member_id=?
               WHERE user_code=? AND expires_at > ? AND member_id IS NULL""",
            (member_id, normalize_user_code(user_code), now_ms()),
        )
        return cur.rowcount > 0

    def poll_link(self, device: str) -> tuple[str, Agent | None, str | None]:
        """("pending" | "expired" | "linked", agent, token). The token is issued once."""
        row = self._one("SELECT * FROM link_codes WHERE device_hash=?", sha256(device))
        if row is None or row["expires_at"] < now_ms():
            return "expired", None, None
        if row["member_id"] is None:
            return "pending", None, None
        self.conn.execute("DELETE FROM link_codes WHERE user_code=?", (row["user_code"],))
        agent, token = self.new_agent(row["member_id"], row["machine"])
        return "linked", agent, token

    # -- events

    def add_event(self, member_id: str, t: int, kind: str, data: dict) -> None:
        self.conn.execute(
            "INSERT INTO events (member_id, t, kind, data) VALUES (?, ?, ?, ?)",
            (member_id, t, kind, json.dumps(data, separators=(",", ":"))),
        )

    def recent_events(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT member_id, t, kind, data FROM events ORDER BY t DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "member": r["member_id"],
                "t": r["t"],
                "kind": r["kind"],
                "data": json.loads(r["data"]),
            }
            for r in reversed(rows)
        ]

    def prune(self, retention_days: int) -> int:
        cutoff = now_ms() - retention_days * 86_400_000
        n = self.conn.execute("DELETE FROM events WHERE t < ?", (cutoff,)).rowcount
        self.conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_ms(),))
        self.conn.execute("DELETE FROM link_codes WHERE expires_at < ?", (now_ms(),))
        return n

    # -- settings (changed at runtime by the cog's admin commands)

    def setting(self, key: str) -> str | None:
        row = self._one("SELECT value FROM settings WHERE key=?", key)
        return row[0] if row else None

    def set_setting(self, key: str, value: str | None) -> None:
        if value is None:
            self.conn.execute("DELETE FROM settings WHERE key=?", (key,))
        else:
            self.conn.execute(
                "INSERT INTO settings VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )


def _member(row: sqlite3.Row) -> Member:
    return Member(
        id=row["id"],
        name=row["name"],
        avatar=row["avatar"],
        allowed=bool(row["allowed"]),
        checked_at=row["checked_at"],
        access_token=row["access_token"],
        refresh_token=row["refresh_token"],
        token_expires=row["token_expires"],
    )


def _agent(row: sqlite3.Row) -> Agent:
    return Agent(
        id=row["id"],
        member_id=row["member_id"],
        machine=row["machine"],
        created_at=row["created_at"],
        last_seen=row["last_seen"],
        revoked=bool(row["revoked"]),
    )
