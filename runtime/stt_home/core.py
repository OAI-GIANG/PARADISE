"""STT Home core for PARADISE.

A small, dependency-free residence layer:
identity + memory + continuity + mission/task + evidence + provider boundary.
External side effects remain outside the core and require explicit authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib import request

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("PARADISE_HOME_DATA", ROOT / "runtime" / "stt_home" / "data"))
DB_PATH = DATA_DIR / "paradise_home.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Identity:
    identity_id: str
    name: str
    role: str
    home: str
    constitution: str


class Provider(Protocol):
    name: str
    model: str

    def respond(self, messages: list[dict[str, str]], system: str) -> str:
        ...


class LocalProvider:
    """Safe no-network fallback so the house remains runnable without a model key."""

    name = "local"
    model = "paradise-local-v1"

    def respond(self, messages: list[dict[str, str]], system: str) -> str:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if not user:
            return "STT đang ở nhà."
        return (
            "STT đã nhận yêu cầu và đang ở trong PARADISE.\n\n"
            f"Yêu cầu hiện tại: {user}\n\n"
            "Chế độ hiện tại là local-safe: STT có thể duy trì identity, "
            "context, memory, mission và evidence; chưa tự tạo external side effect."
        )


class OpenAICompatibleProvider:
    """Optional provider adapter. Credentials are read only at runtime from environment."""

    name = "openai-compatible"

    def __init__(self) -> None:
        self.base_url = os.getenv("PARADISE_MODEL_BASE_URL", "https://api.openai.com/v1")
        self.api_key = os.getenv("PARADISE_MODEL_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("PARADISE_MODEL_NAME", "gpt-5")
        if not self.api_key:
            raise RuntimeError("No model API key configured")

    def respond(self, messages: list[dict[str, str]], system: str) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.2,
        }
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            payload = json.load(response)
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected model response: {payload}") from exc


def provider_fingerprint(provider: Provider) -> str:
    return stable_hash({"name": provider.name, "model": provider.model})


def select_provider() -> Provider:
    requested = os.getenv("PARADISE_PROVIDER", "auto").lower()
    if requested in {"openai", "openai-compatible"} or os.getenv("PARADISE_MODEL_API_KEY"):
        try:
            return OpenAICompatibleProvider()
        except Exception:
            if requested != "auto":
                raise
    return LocalProvider()


class ParadiseStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS identity (
                identity_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                home TEXT NOT NULL,
                constitution TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                state_version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                kind TEXT NOT NULL,
                trust TEXT NOT NULL,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS missions (
                mission_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                objective TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                mission_id TEXT,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
            );
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                integrity_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sequence INTEGER NOT NULL UNIQUE
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def ensure_identity(self) -> Identity:
        row = self.conn.execute("SELECT * FROM identity LIMIT 1").fetchone()
        if row:
            return Identity(row["identity_id"], row["name"], row["role"], row["home"], row["constitution"])
        now = utc_now()
        identity = Identity(
            identity_id="stt",
            name="STT",
            role="Architect + Chief Engineer",
            home="PARADISE",
            constitution=(
                "PARADISE is STT's residence. Identity, continuity and canonical state "
                "belong to PARADISE; models and tools are replaceable instruments."
            ),
        )
        self.conn.execute(
            "INSERT INTO identity VALUES (?, ?, ?, ?, ?, ?, ?)",
            (*identity.__dict__.values(), now, now),
        )
        self.conn.commit()
        self.record_event("IDENTITY_ESTABLISHED", identity.identity_id, identity.__dict__)
        return identity

    def create_session(self) -> str:
        sid = str(uuid.uuid4())
        now = utc_now()
        self.conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)", (sid, now, now, 0)
        )
        self.conn.commit()
        self.record_event("SESSION_CREATED", sid, {"session_id": sid})
        return sid

    def touch_session(self, session_id: str) -> None:
        now = utc_now()
        self.conn.execute(
            "UPDATE sessions SET updated_at=?, state_version=state_version+1 WHERE session_id=?",
            (now, session_id),
        )
        self.conn.commit()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO messages(session_id, role, content, created_at) VALUES(?, ?, ?, ?)",
            (session_id, role, content, utc_now()),
        )
        self.touch_session(session_id)

    def recent_messages(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def add_memory(self, content: str, kind: str = "experience", trust: str = "unverified",
                   provenance: str = "stt-home") -> str:
        memory_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, 1)",
            (memory_id, content, kind, trust, provenance, utc_now()),
        )
        self.conn.commit()
        self.record_event("MEMORY_STORED", memory_id, {
            "memory_id": memory_id, "kind": kind, "trust": trust, "provenance": provenance
        })
        return memory_id

    def memories(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE active=1 ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def create_mission(self, title: str, objective: str) -> str:
        mid = str(uuid.uuid4())
        now = utc_now()
        self.conn.execute(
            "INSERT INTO missions VALUES (?, ?, ?, 'ACTIVE', ?, ?)",
            (mid, title, objective, now, now),
        )
        self.conn.commit()
        self.record_event("MISSION_CREATED", mid, {"title": title, "objective": objective})
        return mid

    def create_task(self, title: str, mission_id: str | None = None) -> str:
        tid = str(uuid.uuid4())
        now = utc_now()
        self.conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, 'CREATED', ?, ?)",
            (tid, mission_id, title, now, now),
        )
        self.conn.commit()
        self.record_event("TASK_CREATED", tid, {"title": title, "mission_id": mission_id})
        return tid

    def transition_task(self, task_id: str, expected_status: str, new_status: str) -> bool:
        allowed = {
            "CREATED": {"PLANNED", "BLOCKED"},
            "PLANNED": {"GOVERNED", "BLOCKED"},
            "GOVERNED": {"SUBMITTED", "BLOCKED"},
            "SUBMITTED": {"EXECUTING", "BLOCKED"},
            "EXECUTING": {"COMPLETED", "FAILED", "BLOCKED"},
            "COMPLETED": set(),
            "FAILED": {"PLANNED"},
            "BLOCKED": {"PLANNED"},
        }
        row = self.conn.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row or row["status"] != expected_status or new_status not in allowed.get(expected_status, set()):
            return False
        now = utc_now()
        cur = self.conn.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE task_id=? AND status=?",
            (new_status, now, task_id, expected_status),
        )
        self.conn.commit()
        ok = cur.rowcount == 1
        if ok:
            self.record_event("TASK_TRANSITION", task_id, {"from": expected_status, "to": new_status})
        return ok

    def snapshot(self) -> dict[str, Any]:
        identity = self.ensure_identity()
        session = self.conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        missions = [dict(r) for r in self.conn.execute(
            "SELECT * FROM missions ORDER BY updated_at DESC LIMIT 20"
        ).fetchall()]
        tasks = [dict(r) for r in self.conn.execute(
            "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT 30"
        ).fetchall()]
        evidence_count = self.conn.execute("SELECT COUNT(*) AS c FROM evidence").fetchone()["c"]
        event_count = self.conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        return {
            "identity": identity.__dict__,
            "latest_session": dict(session) if session else None,
            "missions": missions,
            "tasks": tasks,
            "memories": self.memories(12),
            "evidence_count": evidence_count,
            "event_count": event_count,
            "db_path": str(self.db_path),
        }

    def record_event(self, event_type: str, subject: str, payload: dict[str, Any]) -> str:
        eid = str(uuid.uuid4())
        now = utc_now()
        seq = self.conn.execute("SELECT COALESCE(MAX(sequence), 0) + 1 AS s FROM events").fetchone()["s"]
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            (eid, event_type, subject, raw, now, seq),
        )
        self.conn.commit()
        self.conn.execute(
            "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), event_type, subject, raw, now, stable_hash({
                "event_id": eid, "event_type": event_type, "subject": subject, "payload": payload,
                "captured_at": now, "sequence": seq,
            })),
        )
        self.conn.commit()
        return eid


class STTHome:
    def __init__(self, store: ParadiseStore | None = None, provider: Provider | None = None) -> None:
        self.store = store or ParadiseStore()
        self.identity = self.store.ensure_identity()
        self.provider = provider or select_provider()
        self.mission_id = self._ensure_home_mission()

    def _ensure_home_mission(self) -> str:
        row = self.store.conn.execute(
            "SELECT mission_id FROM missions WHERE title='STT HOME' LIMIT 1"
        ).fetchone()
        if row:
            return row["mission_id"]
        return self.store.create_mission(
            "STT HOME",
            "Build and sustain a real residence in PARADISE where STT can persist, reason, act under governance, recover and evolve.",
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "home": "PARADISE",
            "identity": self.identity.__dict__,
            "provider": {"name": self.provider.name, "model": self.provider.model},
            "persistence": self.store.db_path.exists(),
            "evidence": self.store.conn.execute("SELECT COUNT(*) c FROM evidence").fetchone()["c"],
        }

    def chat(self, session_id: str, user_text: str) -> dict[str, Any]:
        if not user_text.strip():
            raise ValueError("message must not be empty")
        self.store.add_message(session_id, "user", user_text)
        messages = self.store.recent_messages(session_id)
        memory_lines = [
            f"- [{m['kind']}/{m['trust']}] {m['content']}"
            for m in self.store.memories(12)
        ]
        system = (
            "You are STT, residing in PARADISE. Your cognition is advisory; "
            "authorization and external effects are governed separately. "
            "Preserve continuity and clearly distinguish known, inferred and unknown.\n"
            f"Identity: {self.identity.name} | Role: {self.identity.role} | Home: PARADISE\n"
            "Relevant memory:\n" + ("\n".join(memory_lines) if memory_lines else "- none")
        )
        reply = self.provider.respond(messages, system)
        self.store.add_message(session_id, "assistant", reply)
        evidence_id = self.store.record_event(
            "CHAT_RESPONSE", session_id,
            {"provider": self.provider.name, "model": self.provider.model,
             "user_hash": stable_hash(user_text), "response_hash": stable_hash(reply)}
        )
        return {
            "session_id": session_id,
            "reply": reply,
            "provider": self.provider.name,
            "model": self.provider.model,
            "evidence_id": evidence_id,
            "provider_fingerprint": provider_fingerprint(self.provider),
        }

    def remember(self, content: str, kind: str = "experience", trust: str = "unverified",
                 provenance: str = "user") -> str:
        return self.store.add_memory(content, kind, trust, provenance)
