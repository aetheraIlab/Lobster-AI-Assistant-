from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MessageRecord:
    channel: str
    user_id: str
    role: str
    content: str
    created_at: float


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_thread
                ON messages(channel, user_id, id)
                """
            )

    def add_message(self, channel: str, user_id: str, role: str, content: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO messages(channel, user_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (channel, user_id, role, content, time.time()),
            )

    def recent_messages(
        self, channel: str, user_id: str, limit: int = 12
    ) -> list[MessageRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT channel, user_id, role, content, created_at
                FROM messages
                WHERE channel = ? AND user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (channel, user_id, limit),
            ).fetchall()
        records = [
            MessageRecord(
                channel=row["channel"],
                user_id=row["user_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return list(reversed(records))

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def to_llm_messages(records: Iterable[MessageRecord]) -> list[dict[str, str]]:
    return [{"role": record.role, "content": record.content} for record in records]
