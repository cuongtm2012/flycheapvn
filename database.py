"""SQLite database init and helpers for FlyCheapVN."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Optional

DB_PATH = Path(__file__).parent / "flycheapvn.db"


def _db_path(db_path: Optional[Path] = None) -> Path:
    return db_path or DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    chat_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    lang TEXT DEFAULT 'vi',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    origin TEXT NOT NULL,
    dest TEXT NOT NULL,
    max_price INTEGER NOT NULL,
    currency TEXT DEFAULT 'VND',
    date_from TEXT,
    date_to TEXT,
    last_checked TIMESTAMP,
    last_price INTEGER,
    last_notified_price INTEGER,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cache (
    query_hash TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_limits (
    source TEXT PRIMARY KEY,
    last_reset TIMESTAMP,
    count INTEGER DEFAULT 0,
    max_per_hour INTEGER
);

CREATE TABLE IF NOT EXISTS user_rate_limits (
    telegram_id INTEGER PRIMARY KEY,
    window_start TIMESTAMP NOT NULL,
    count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS source_health (
    source TEXT PRIMARY KEY,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    circuit_open_until TIMESTAMP
);
"""


def init_db(db_path: Optional[Path] = None) -> None:
    path = _db_path(db_path)
    with get_connection(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_connection(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(_db_path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def upsert_user(
    telegram_id: int,
    chat_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, chat_id, username, first_name, last_active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                username = excluded.username,
                first_name = excluded.first_name,
                last_active = excluded.last_active
            """,
            (telegram_id, chat_id, username, first_name, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row["id"]


def get_user_id(telegram_id: int, db_path: Optional[Path] = None) -> Optional[int]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row["id"] if row else None


def get_cache(query_hash: str, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT response, source, expires_at FROM cache WHERE query_hash = ?",
            (query_hash,),
        ).fetchone()
        if not row:
            return None
        if row["expires_at"] < now:
            return None
        data = json.loads(row["response"])
        data["cached"] = True
        data["source"] = row["source"]
        return data


def get_stale_cache(query_hash: str, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT response, source FROM cache WHERE query_hash = ?",
            (query_hash,),
        ).fetchone()
        if not row:
            return None
        data = json.loads(row["response"])
        data["cached"] = True
        data["stale"] = True
        data["source"] = row["source"]
        return data


def set_cache(
    query_hash: str,
    response: dict[str, Any],
    source: str,
    ttl_minutes: int = 15,
    db_path: Optional[Path] = None,
) -> None:
    now = datetime.utcnow()
    expires = (now + timedelta(minutes=ttl_minutes)).isoformat()
    payload = {k: v for k, v in response.items() if k not in ("cached", "stale")}
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO cache (query_hash, response, source, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (query_hash, json.dumps(payload), source, now.isoformat(), expires),
        )
        conn.commit()


def cleanup_expired_cache(db_path: Optional[Path] = None) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
        conn.commit()
        return cursor.rowcount


def create_alert(
    user_id: int,
    origin: str,
    dest: str,
    max_price: int,
    currency: str = "VND",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO alerts (user_id, origin, dest, max_price, currency, date_from, date_to)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, origin.upper(), dest.upper(), max_price, currency, date_from, date_to),
        )
        conn.commit()
        return cursor.lastrowid


def get_active_alerts(user_id: int, db_path: Optional[Path] = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM alerts
            WHERE user_id = ? AND active = 1
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def update_alert_check(
    alert_id: int,
    last_price: Optional[int],
    last_notified_price: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        if last_notified_price is not None:
            conn.execute(
                """
                UPDATE alerts
                SET last_checked = ?, last_price = ?, last_notified_price = ?
                WHERE id = ?
                """,
                (now, last_price, last_notified_price, alert_id),
            )
        else:
            conn.execute(
                """
                UPDATE alerts SET last_checked = ?, last_price = ?
                WHERE id = ?
                """,
                (now, last_price, alert_id),
            )
        conn.commit()


def deactivate_alert(alert_id: int, user_id: int, db_path: Optional[Path] = None) -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE alerts SET active = 0 WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def increment_source_rate(source: str, max_per_hour: int, db_path: Optional[Path] = None) -> bool:
    """Returns False if rate limit exceeded."""
    now = datetime.utcnow()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT last_reset, count FROM rate_limits WHERE source = ?", (source,)
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO rate_limits (source, last_reset, count, max_per_hour) VALUES (?, ?, 1, ?)",
                (source, now.isoformat(), max_per_hour),
            )
            conn.commit()
            return True

        last_reset = datetime.fromisoformat(row["last_reset"])
        if now - last_reset >= timedelta(hours=1):
            conn.execute(
                "UPDATE rate_limits SET last_reset = ?, count = 1 WHERE source = ?",
                (now.isoformat(), source),
            )
            conn.commit()
            return True

        if row["count"] >= max_per_hour:
            return False

        conn.execute(
            "UPDATE rate_limits SET count = count + 1 WHERE source = ?",
            (source,),
        )
        conn.commit()
        return True


def record_source_result(source: str, success: bool, db_path: Optional[Path] = None) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT success_count, fail_count FROM source_health WHERE source = ?",
            (source,),
        ).fetchone()
        if not row:
            conn.execute(
                """
                INSERT INTO source_health (source, success_count, fail_count, last_success, last_failure, circuit_open_until)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (source, 1 if success else 0, 0 if success else 1, now if success else None, None if success else now),
            )
        elif success:
            conn.execute(
                """
                UPDATE source_health
                SET success_count = success_count + 1, last_success = ?, circuit_open_until = NULL
                WHERE source = ?
                """,
                (now, source),
            )
        else:
            circuit_until = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            conn.execute(
                """
                UPDATE source_health
                SET fail_count = fail_count + 1, last_failure = ?, circuit_open_until = ?
                WHERE source = ?
                """,
                (now, circuit_until, source),
            )
        conn.commit()


def is_circuit_open(source: str, db_path: Optional[Path] = None) -> bool:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT circuit_open_until FROM source_health WHERE source = ?",
            (source,),
        ).fetchone()
        if not row or not row["circuit_open_until"]:
            return False
        return row["circuit_open_until"] > now


def get_source_health_score(source: str, db_path: Optional[Path] = None) -> float:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT success_count, fail_count FROM source_health WHERE source = ?",
            (source,),
        ).fetchone()
        if not row:
            return 0.5
        total = row["success_count"] + row["fail_count"]
        if total == 0:
            return 0.5
        return row["success_count"] / total


def check_user_rate_limit(
    telegram_id: int, max_per_minute: int = 5, db_path: Optional[Path] = None
) -> bool:
    """Returns True if user is allowed, False if rate limited."""
    now = datetime.utcnow()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT window_start, count FROM user_rate_limits WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO user_rate_limits (telegram_id, window_start, count) VALUES (?, ?, 1)",
                (telegram_id, now.isoformat()),
            )
            conn.commit()
            return True

        window_start = datetime.fromisoformat(row["window_start"])
        if now - window_start >= timedelta(minutes=1):
            conn.execute(
                "UPDATE user_rate_limits SET window_start = ?, count = 1 WHERE telegram_id = ?",
                (now.isoformat(), telegram_id),
            )
            conn.commit()
            return True

        if row["count"] >= max_per_minute:
            return False

        conn.execute(
            "UPDATE user_rate_limits SET count = count + 1 WHERE telegram_id = ?",
            (telegram_id,),
        )
        conn.commit()
        return True
