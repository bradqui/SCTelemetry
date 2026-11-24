"""SQLite storage: members, sign-in, linked PCs, invites, API keys and the event log.

Live telemetry is never stored here; it lives in memory (``fleet.py``). Calls are
synchronous: each is a single indexed statement on a local file, well under a
millisecond, so they run on the event loop directly.

Every secret is stored as a SHA-256 hash only: sessions, PC tokens, invite and
pairing codes, API keys. Discord tokens (only for members who connect Discord)
are kept so the org role can be re-checked.

Schema changes are numbered migrations (``MIGRATIONS``), tracked with SQLite's
``user_version``: add a new entry at the end, never edit an old one.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1: accounts owned by the hub; Discord optional
    """
    CREATE TABLE members (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        avatar          TEXT,
        role            TEXT NOT NULL DEFAULT 'member',  -- member | admin
        active          INTEGER NOT NULL DEFAULT 1,      -- 0: suspended (lost the Discord role)
        created_at      INTEGER NOT NULL,
        discord_id      TEXT UNIQUE,
        discord_access  TEXT,
        discord_refresh TEXT,
        discord_expires INTEGER,
        discord_checked INTEGER
    );
    CREATE TABLE sessions (
        id_hash     TEXT PRIMARY KEY,
        member_id   TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        created_at  INTEGER NOT NULL,
        expires_at  INTEGER NOT NULL
    );
    CREATE TABLE agents (
        id          INTEGER PRIMARY KEY,
        member_id   TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        token_hash  TEXT NOT NULL UNIQUE,
        machine     TEXT NOT NULL,
        created_at  INTEGER NOT NULL,
        last_seen   INTEGER,
        revoked     INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE invites (
        id          INTEGER PRIMARY KEY,
        code_hash   TEXT NOT NULL UNIQUE,
        role        TEXT NOT NULL DEFAULT 'member',
        note        TEXT,
        created_by  TEXT,                                -- member id, "setup" or "api:<key id>"
        created_at  INTEGER NOT NULL,
        expires_at  INTEGER,                             -- NULL: never
        max_uses    INTEGER,                             -- NULL: unlimited
        uses        INTEGER NOT NULL DEFAULT 0,
        revoked     INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE pair_codes (                            -- short codes typed on another device
        code        TEXT PRIMARY KEY,
        kind        TEXT NOT NULL,                       -- link: an agent shows it
                                                         -- signin: a signed-in browser shows it
        secret_hash TEXT,                                -- link: the agent's polling secret
        machine     TEXT,
        member_id   TEXT REFERENCES members(id) ON DELETE CASCADE,
        created_at  INTEGER NOT NULL,
        expires_at  INTEGER NOT NULL
    );
    CREATE TABLE login_links (                           -- one-time sign-in links the agent opens
        token_hash  TEXT PRIMARY KEY,
        member_id   TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        expires_at  INTEGER NOT NULL
    );
    CREATE TABLE api_keys (
        id          INTEGER PRIMARY KEY,
        key_hash    TEXT NOT NULL UNIQUE,
        name        TEXT NOT NULL,
        scopes      TEXT NOT NULL,                       -- space-separated: read invites
        created_by  TEXT,
        created_at  INTEGER NOT NULL,
        last_used   INTEGER
    );
    CREATE TABLE events (
        id          INTEGER PRIMARY KEY,
        member_id   TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        t           INTEGER NOT NULL,
        kind        TEXT NOT NULL,
        data        TEXT NOT NULL
    );
    CREATE INDEX events_t ON events(t);
    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # 2: signed-in devices you can see and sign out (Account page)
    """
    ALTER TABLE sessions ADD COLUMN label TEXT;      -- "Safari on iPhone", from the User-Agent
    ALTER TABLE sessions ADD COLUMN how TEXT;        -- invite | code | link | discord | dev
    ALTER TABLE sessions ADD COLUMN last_seen INTEGER;
    """,
]

SESSION_DAYS = 30
SESSION_ID_LEN = 16
PAIR_CODE_TTL_S = 600
LOGIN_LINK_TTL_S = 120
# No 0/O, 1/I/L: codes are read off one screen and typed on another.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
ROLES = ("member", "admin")
API_SCOPES = ("read", "invites")


def now_ms() -> int:
    return int(time.time() * 1000)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_short_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    return f"{raw[:3]}-{raw[3:]}"


def normalize_code(code: str) -> str:
    raw = "".join(ch for ch in code.upper() if ch.isalnum())
    return f"{raw[:3]}-{raw[3:]}" if len(raw) == 6 else code.strip().upper()


def clean_name(name: str) -> str:
    """A display name: printable, single line, at most 32 characters."""
    name = " ".join("".join(ch for ch in str(name) if ch.isprintable()).split())
    return name[:32]


@dataclass
class Member:
    id: str
    name: str
    avatar: str | None
    role: str
    active: int
    created_at: int
    discord_id: str | None = None
    discord_access: str | None = None
    discord_refresh: str | None = None
    discord_expires: int | None = None
    discord_checked: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "avatar": self.avatar}

    def account(self) -> dict:
        return {
            **self.public(),
            "role": self.role,
            "active": bool(self.active),
            "discord": self.discord_id is not None,
            "created_at": self.created_at,
        }


@dataclass
class Agent:
    id: int
    member_id: str
    machine: str
    created_at: int
    last_seen: int | None
    revoked: bool


@dataclass
class Invite:
    id: int
    role: str
    note: str | None
    created_by: str | None
    created_at: int
    expires_at: int | None
    max_uses: int | None
    uses: int
    revoked: bool

    @property
    def usable(self) -> bool:
        return (
            not self.revoked
            and (self.expires_at is None or self.expires_at > now_ms())
            and (self.max_uses is None or self.uses < self.max_uses)
        )

    def public(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "note": self.note,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "max_uses": self.max_uses,
            "uses": self.uses,
            "usable": self.usable,
        }


class Database:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self.conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
            self.conn.execute("PRAGMA user_version").fetchone()
        except sqlite3.OperationalError as exc:
            uid = getattr(os, "getuid", lambda: None)()
            who = f" (uid {uid})" if uid is not None else ""
            raise SystemExit(
                f"Can't open the database {path}: {exc}. Its folder must exist and be "
                f"writable by the user the hub runs as{who}. "
                "In Docker the image fixes this on start; with a host folder mounted at "
                "/data, check it isn't read-only (deploy/README.md, Troubleshooting)."
            ) from exc
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    def migrate(self) -> int:
        """Bring the schema up to date. Returns the version it's at."""
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            self.conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
        return len(MIGRATIONS)

    def close(self) -> None:
        self.conn.close()

    def _one(self, sql: str, *args) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    # -- members

    def new_member(self, name: str, *, role: str = "member", avatar: str | None = None) -> Member:
        mid = "m_" + secrets.token_hex(8)
        self.conn.execute(
            "INSERT INTO members (id, name, avatar, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                mid,
                clean_name(name) or "Pilot",
                avatar,
                role if role in ROLES else "member",
                now_ms(),
            ),
        )
        member = self.member(mid)
        assert member is not None
        return member

    def member(self, member_id: str) -> Member | None:
        row = self._one("SELECT * FROM members WHERE id=?", member_id)
        return Member(**dict(row)) if row else None

    def member_by_discord(self, discord_id: str) -> Member | None:
        row = self._one("SELECT * FROM members WHERE discord_id=?", discord_id)
        return Member(**dict(row)) if row else None

    def members(self) -> list[Member]:
        rows = self.conn.execute("SELECT * FROM members ORDER BY name COLLATE NOCASE").fetchall()
        return [Member(**dict(r)) for r in rows]

    def admin_count(self) -> int:
        return self._one("SELECT COUNT(*) FROM members WHERE role='admin' AND active=1")[0]

    def rename(self, member_id: str, name: str) -> None:
        self.conn.execute("UPDATE members SET name=? WHERE id=?", (clean_name(name), member_id))

    def set_role(self, member_id: str, role: str) -> None:
        self.conn.execute("UPDATE members SET role=? WHERE id=?", (role, member_id))

    def set_active(self, member_id: str, active: bool) -> None:
        self.conn.execute("UPDATE members SET active=? WHERE id=?", (int(active), member_id))

    def delete_member(self, member_id: str) -> None:
        """Remove a member and everything about them (PCs, sessions, events)."""
        self.conn.execute("DELETE FROM members WHERE id=?", (member_id,))

    def set_discord(
        self,
        member_id: str,
        discord_id: str | None,
        *,
        access: str | None = None,
        refresh: str | None = None,
        expires: int | None = None,
        avatar: str | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE members SET discord_id=?, discord_access=?, discord_refresh=?,
                   discord_expires=?, discord_checked=?, avatar=COALESCE(?, avatar)
               WHERE id=?""",
            (
                discord_id,
                access,
                refresh,
                expires,
                now_ms() if discord_id else None,
                avatar,
                member_id,
            ),
        )

    def discord_checked(
        self,
        member_id: str,
        *,
        access: str | None = None,
        refresh: str | None = None,
        expires: int | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE members SET discord_checked=?,
                   discord_access=COALESCE(?, discord_access),
                   discord_refresh=COALESCE(?, discord_refresh),
                   discord_expires=COALESCE(?, discord_expires)
               WHERE id=?""",
            (now_ms(), access, refresh, expires, member_id),
        )

    # -- sessions (browser sign-in)

    def new_session(self, member_id: str, label: str | None = None, how: str | None = None) -> str:
        sid = secrets.token_urlsafe(32)
        t = now_ms()
        self.conn.execute(
            """INSERT INTO sessions (id_hash, member_id, created_at, expires_at, label, how,
                                     last_seen) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sha256(sid), member_id, t, t + SESSION_DAYS * 86_400_000, label, how, t),
        )
        return sid

    def touch_session(self, sid: str) -> None:
        """Note the device was used (at most every 5 minutes: it's for "last active")."""
        t = now_ms()
        self.conn.execute(
            "UPDATE sessions SET last_seen=? WHERE id_hash=? AND COALESCE(last_seen, 0) < ?",
            (t, sha256(sid), t - 300_000),
        )

    def member_sessions(self, member_id: str) -> list[dict]:
        """A member's signed-in devices. ``id`` is a prefix of the stored hash: enough to
        name one, useless for signing in."""
        rows = self.conn.execute(
            """SELECT id_hash, label, how, created_at, last_seen FROM sessions
               WHERE member_id=? AND expires_at > ?
               ORDER BY COALESCE(last_seen, created_at) DESC""",
            (member_id, now_ms()),
        ).fetchall()
        return [
            {
                "id": r["id_hash"][:SESSION_ID_LEN],
                "label": r["label"],
                "how": r["how"],
                "created_at": r["created_at"],
                "last_seen": r["last_seen"],
            }
            for r in rows
        ]

    def end_member_session(self, member_id: str, public_id: str) -> bool:
        if len(public_id) != SESSION_ID_LEN or not public_id.isalnum():
            return False
        cur = self.conn.execute(
            "DELETE FROM sessions WHERE member_id=? AND substr(id_hash, 1, ?)=?",
            (member_id, SESSION_ID_LEN, public_id),
        )
        return cur.rowcount > 0

    def end_other_sessions(self, member_id: str, keep_sid: str) -> int:
        cur = self.conn.execute(
            "DELETE FROM sessions WHERE member_id=? AND id_hash<>?", (member_id, sha256(keep_sid))
        )
        return cur.rowcount

    @staticmethod
    def session_public_id(sid: str) -> str:
        return sha256(sid)[:SESSION_ID_LEN] if sid else ""

    def session_member(self, sid: str) -> Member | None:
        row = self._one(
            """SELECT m.* FROM sessions s JOIN members m ON m.id = s.member_id
               WHERE s.id_hash=? AND s.expires_at > ?""",
            sha256(sid),
            now_ms(),
        )
        return Member(**dict(row)) if row else None

    def end_session(self, sid: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE id_hash=?", (sha256(sid),))

    def end_member_sessions(self, member_id: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE member_id=?", (member_id,))

    # -- agents (linked PCs)

    def new_agent(self, member_id: str, machine: str) -> tuple[Agent, str]:
        token = secrets.token_urlsafe(32)
        cur = self.conn.execute(
            "INSERT INTO agents (member_id, token_hash, machine, created_at) VALUES (?, ?, ?, ?)",
            (member_id, sha256(token), clean_name(machine) or "PC", now_ms()),
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

    def member_last_seen(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT member_id, MAX(last_seen) FROM agents WHERE revoked=0 GROUP BY member_id"
        )
        return {r[0]: r[1] for r in rows if r[1]}

    def linked_member_ids(self) -> set[str]:
        rows = self.conn.execute("SELECT DISTINCT member_id FROM agents WHERE revoked=0")
        return {r[0] for r in rows}

    # -- invites

    def new_invite(
        self,
        *,
        role: str = "member",
        note: str | None = None,
        created_by: str | None = None,
        expires_in_s: int | None = 7 * 86400,
        max_uses: int | None = 1,
    ) -> tuple[Invite, str]:
        code = secrets.token_urlsafe(12)
        expires = now_ms() + expires_in_s * 1000 if expires_in_s else None
        cur = self.conn.execute(
            """INSERT INTO invites (code_hash, role, note, created_by, created_at, expires_at,
                                    max_uses) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sha256(code),
                role if role in ROLES else "member",
                clean_name(note or "")[:80] or None,
                created_by,
                now_ms(),
                expires,
                max_uses,
            ),
        )
        invite = self.invite(cur.lastrowid or 0)
        assert invite is not None
        return invite, code

    def invite(self, invite_id: int) -> Invite | None:
        row = self._one("SELECT * FROM invites WHERE id=?", invite_id)
        return _invite(row) if row else None

    def invite_by_code(self, code: str) -> Invite | None:
        row = self._one("SELECT * FROM invites WHERE code_hash=?", sha256(code.strip()))
        return _invite(row) if row else None

    def invites(self) -> list[Invite]:
        rows = self.conn.execute(
            "SELECT * FROM invites WHERE revoked=0 AND IFNULL(created_by, '') != 'setup' "
            "ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        return [_invite(r) for r in rows]

    def use_invite(self, code: str) -> Invite | None:
        """Count one use, if the invite is still good. Returns it, or None."""
        invite = self.invite_by_code(code)
        if invite is None or not invite.usable:
            return None
        cur = self.conn.execute(
            "UPDATE invites SET uses = uses + 1 "
            "WHERE id=? AND (max_uses IS NULL OR uses < max_uses)",
            (invite.id,),
        )
        return invite if cur.rowcount else None

    def revoke_invite(self, invite_id: int) -> bool:
        cur = self.conn.execute("UPDATE invites SET revoked=1 WHERE id=?", (invite_id,))
        return cur.rowcount > 0

    def setup_invite(self) -> str | None:
        """While the hub has no admin: a fresh single-use admin invite (old ones revoked)."""
        self.conn.execute("UPDATE invites SET revoked=1 WHERE created_by='setup'")
        if self.admin_count():
            return None
        _invite, code = self.new_invite(
            role="admin", created_by="setup", note="First admin", expires_in_s=None, max_uses=1
        )
        return code

    # -- pairing codes (another device) and one-time sign-in links

    def _new_pair(self, kind: str, *, member_id=None, secret_hash=None, machine=None) -> str:
        t = now_ms()
        self.conn.execute("DELETE FROM pair_codes WHERE expires_at < ?", (t,))
        for _ in range(10):
            code = new_short_code()
            try:
                self.conn.execute(
                    "INSERT INTO pair_codes VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (code, kind, secret_hash, machine, member_id, t, t + PAIR_CODE_TTL_S * 1000),
                )
                return code
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("couldn't allocate a code")

    def new_link_code(self, machine: str) -> tuple[str, str]:
        """An agent wants linking: (code it shows, secret it polls with)."""
        secret = secrets.token_urlsafe(32)
        code = self._new_pair("link", secret_hash=sha256(secret), machine=clean_name(machine))
        return code, secret

    def link_code(self, code: str) -> sqlite3.Row | None:
        return self._one(
            "SELECT * FROM pair_codes WHERE code=? AND kind='link' AND expires_at > ?",
            normalize_code(code),
            now_ms(),
        )

    def confirm_link_code(self, code: str, member_id: str) -> bool:
        cur = self.conn.execute(
            """UPDATE pair_codes SET member_id=?
               WHERE code=? AND kind='link' AND expires_at > ? AND member_id IS NULL""",
            (member_id, normalize_code(code), now_ms()),
        )
        return cur.rowcount > 0

    def poll_link(self, secret: str) -> tuple[str, Agent | None, str | None]:
        """("pending" | "expired" | "linked", agent, token). The token is issued once."""
        row = self._one(
            "SELECT * FROM pair_codes WHERE secret_hash=? AND kind='link'", sha256(secret)
        )
        if row is None or row["expires_at"] < now_ms():
            return "expired", None, None
        if row["member_id"] is None:
            return "pending", None, None
        self.conn.execute("DELETE FROM pair_codes WHERE code=?", (row["code"],))
        agent, token = self.new_agent(row["member_id"], row["machine"] or "PC")
        return "linked", agent, token

    def new_signin_code(self, member_id: str) -> str:
        """A signed-in member adds a device: the code they type on it."""
        return self._new_pair("signin", member_id=member_id)

    def use_signin_code(self, code: str) -> Member | None:
        row = self._one(
            "SELECT * FROM pair_codes WHERE code=? AND kind='signin' AND expires_at > ?",
            normalize_code(code),
            now_ms(),
        )
        if row is None:
            return None
        self.conn.execute("DELETE FROM pair_codes WHERE code=?", (row["code"],))
        return self.member(row["member_id"])

    def new_login_link(self, member_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.conn.execute("DELETE FROM login_links WHERE expires_at < ?", (now_ms(),))
        self.conn.execute(
            "INSERT INTO login_links VALUES (?, ?, ?)",
            (sha256(token), member_id, now_ms() + LOGIN_LINK_TTL_S * 1000),
        )
        return token

    def use_login_link(self, token: str) -> Member | None:
        row = self._one(
            "SELECT * FROM login_links WHERE token_hash=? AND expires_at > ?",
            sha256(token),
            now_ms(),
        )
        if row is None:
            return None
        self.conn.execute("DELETE FROM login_links WHERE token_hash=?", (row["token_hash"],))
        return self.member(row["member_id"])

    # -- API keys (integrations: bots, scripts)

    def new_api_key(self, name: str, scopes: list[str], created_by: str) -> tuple[dict, str]:
        key = "ftk_" + secrets.token_urlsafe(32)
        scopes = [s for s in scopes if s in API_SCOPES] or ["read"]
        cur = self.conn.execute(
            "INSERT INTO api_keys (key_hash, name, scopes, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                sha256(key),
                clean_name(name) or "Integration",
                " ".join(scopes),
                created_by,
                now_ms(),
            ),
        )
        return self.api_key(cur.lastrowid or 0) or {}, key

    def api_key(self, key_id: int) -> dict | None:
        row = self._one("SELECT * FROM api_keys WHERE id=?", key_id)
        return _key(row) if row else None

    def api_keys(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM api_keys ORDER BY created_at").fetchall()
        return [_key(r) for r in rows]

    def api_key_by_secret(self, key: str) -> dict | None:
        row = self._one("SELECT * FROM api_keys WHERE key_hash=?", sha256(key))
        if row is None:
            return None
        self.conn.execute("UPDATE api_keys SET last_used=? WHERE id=?", (now_ms(), row["id"]))
        return _key(row)

    def delete_api_key(self, key_id: int) -> bool:
        return self.conn.execute("DELETE FROM api_keys WHERE id=?", (key_id,)).rowcount > 0

    # -- events

    def add_event(self, member_id: str, t: int, kind: str, data: dict) -> None:
        self.conn.execute(
            "INSERT INTO events (member_id, t, kind, data) VALUES (?, ?, ?, ?)",
            (member_id, t, kind, json.dumps(data, separators=(",", ":"))),
        )

    def recent_events(self, limit: int = 100, since: int | None = None) -> list[dict]:
        rows = self.conn.execute(
            "SELECT member_id, t, kind, data FROM events WHERE t > ? "
            "ORDER BY t DESC, id DESC LIMIT ?",
            (since or 0, limit),
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
        t = now_ms()
        self.conn.execute("DELETE FROM sessions WHERE expires_at < ?", (t,))
        self.conn.execute("DELETE FROM pair_codes WHERE expires_at < ?", (t,))
        self.conn.execute("DELETE FROM login_links WHERE expires_at < ?", (t,))
        return n

    # -- settings (changed by admins on the page)

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


def _agent(row: sqlite3.Row) -> Agent:
    return Agent(
        id=row["id"],
        member_id=row["member_id"],
        machine=row["machine"],
        created_at=row["created_at"],
        last_seen=row["last_seen"],
        revoked=bool(row["revoked"]),
    )


def _invite(row: sqlite3.Row) -> Invite:
    return Invite(
        id=row["id"],
        role=row["role"],
        note=row["note"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        max_uses=row["max_uses"],
        uses=row["uses"],
        revoked=bool(row["revoked"]),
    )


def _key(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "scopes": row["scopes"].split(),
        "created_at": row["created_at"],
        "last_used": row["last_used"],
    }
