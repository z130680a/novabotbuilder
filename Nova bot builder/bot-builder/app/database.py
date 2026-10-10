from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# =========================================================
# Paths
# =========================================================

def get_base_dir() -> Path:
    """
    مسیر اصلی پروژه را مشخص می‌کند.

    در حالت معمول:
        C:\\Users\\...\\bot-builder

    در حالت exe:
        کنار فایل exe
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

DB_PATH = DATA_DIR / "nova.db"


# =========================================================
# Time
# =========================================================

def utc_now() -> str:
    """
    زمان فعلی UTC با دقت ثانیه.
    """

    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="seconds"
    )


# =========================================================
# Database connection
# =========================================================

def get_connection() -> sqlite3.Connection:
    """
    اتصال استاندارد به SQLite.
    """

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    # Foreign Keys
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    # WAL برای عملکرد بهتر در چند خواندن/نوشتن
    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    # کاهش مشکل lock در عملیات متوالی
    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    return connection


# =========================================================
# Init
# =========================================================

def init_db() -> None:
    """
    ساخت جدول‌ها و indexهای موردنیاز.
    """

    with get_connection() as conn:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT NOT NULL UNIQUE,

                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,

                role TEXT NOT NULL DEFAULT 'staff',

                created_at TEXT NOT NULL,
                last_login_at TEXT
            );


            CREATE TABLE IF NOT EXISTS workshop_meta (
                workshop_id INTEGER PRIMARY KEY,

                creator_user_id INTEGER,

                creator_username TEXT,

                creator_ip TEXT,

                created_at TEXT NOT NULL,

                updated_at TEXT,

                FOREIGN KEY (creator_user_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            );


            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                workshop_id INTEGER NOT NULL,

                telegram_user_id INTEGER NOT NULL,

                username TEXT,

                first_name TEXT,

                last_name TEXT,

                phone TEXT,

                status TEXT NOT NULL DEFAULT 'registered',

                reserved_at TEXT,

                waitlisted_at TEXT,

                cancelled_at TEXT,

                created_at TEXT NOT NULL,

                updated_at TEXT NOT NULL,

                UNIQUE(
                    workshop_id,
                    telegram_user_id
                )
            );


            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER,

                username TEXT,

                action TEXT NOT NULL,

                workshop_id INTEGER,

                ip TEXT,

                details TEXT,

                created_at TEXT NOT NULL,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            );


            CREATE INDEX IF NOT EXISTS
            idx_participants_workshop
            ON participants(workshop_id);


            CREATE INDEX IF NOT EXISTS
            idx_participants_status
            ON participants(status);


            CREATE INDEX IF NOT EXISTS
            idx_participants_user
            ON participants(telegram_user_id);


            CREATE INDEX IF NOT EXISTS
            idx_admin_logs_workshop
            ON admin_logs(workshop_id);


            CREATE INDEX IF NOT EXISTS
            idx_admin_logs_user
            ON admin_logs(user_id);


            CREATE INDEX IF NOT EXISTS
            idx_admin_logs_created_at
            ON admin_logs(created_at);
            """
        )


# =========================================================
# Users
# =========================================================

def create_user(
    username: str,
    password_hash: str,
    password_salt: str,
    role: str = "staff",
) -> dict[str, Any]:

    username = username.strip()
    role = role.strip() or "staff"

    if not username:
        raise ValueError(
            "username cannot be empty."
        )

    if not password_hash:
        raise ValueError(
            "password_hash cannot be empty."
        )

    if not password_salt:
        raise ValueError(
            "password_salt cannot be empty."
        )

    now = utc_now()

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                password_salt,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                password_salt,
                role,
                now,
            ),
        )

        user_id = cursor.lastrowid

        if user_id is None:
            raise RuntimeError(
                "Could not create user."
            )

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "User was created but could not be loaded."
        )

    return dict(row)


def get_user_by_username(
    username: str,
) -> dict[str, Any] | None:

    username = username.strip()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    return dict(row) if row else None


def get_user_by_id(
    user_id: int,
) -> dict[str, Any] | None:

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                username,
                role,
                created_at,
                last_login_at
            FROM users
            ORDER BY id DESC
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def update_last_login(
    user_id: int,
) -> None:

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE users
            SET last_login_at = ?
            WHERE id = ?
            """,
            (
                utc_now(),
                user_id,
            ),
        )


def count_users() -> int:

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            """
        ).fetchone()

    return int(
        row["count"]
    ) if row else 0


# =========================================================
# Workshop metadata
# =========================================================

def record_workshop_created(
    workshop_id: int,
    user: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    username = (
        str(user.get("username") or "anonymous")
        if user
        else "anonymous"
    )

    user_id = (
        user.get("id")
        if user
        else None
    )

    now = utc_now()

    with get_connection() as conn:
        linked_user_id = user_id

        if linked_user_id is not None:
            linked_user = conn.execute(
                """
                SELECT id
                FROM users
                WHERE id = ?
                  AND username = ?
                """,
                (
                    linked_user_id,
                    username,
                ),
            ).fetchone()

            # اگر این حساب در دیتابیس گزارش‌ها وجود
            # نداشته باشد، شناسه را NULL می‌گذاریم.
            # نام کاربری همچنان در گزارش ذخیره می‌شود.
            if linked_user is None:
                linked_user_id = None

        conn.execute(
            """
            INSERT INTO workshop_meta (
                workshop_id,
                creator_user_id,
                creator_username,
                creator_ip,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(workshop_id)
            DO UPDATE SET
                creator_user_id = excluded.creator_user_id,
                creator_username = excluded.creator_username,
                creator_ip = excluded.creator_ip,
                updated_at = excluded.updated_at
            """,
            (
                workshop_id,
                linked_user_id,
                username,
                ip,
                now,
                now,
            ),
        )


def touch_workshop(
    workshop_id: int,
    user: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:

    now = utc_now()

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE workshop_meta
            SET updated_at = ?
            WHERE workshop_id = ?
            """,
            (
                now,
                workshop_id,
            ),
        )

    if user:

        log_action(
            user=user,
            action="workshop_updated",
            workshop_id=workshop_id,
            ip=ip,
        )


def get_workshop_meta(
    workshop_id: int,
) -> dict[str, Any] | None:

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM workshop_meta
            WHERE workshop_id = ?
            """,
            (workshop_id,),
        ).fetchone()

    return dict(row) if row else None


# =========================================================
# Participants
# =========================================================

def upsert_participant(
    workshop_id: int,
    telegram_user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    status: str = "registered",
) -> None:

    allowed_statuses = {
        "registered",
        "waitlist",
        "cancelled",
    }

    status = status.strip()

    if status not in allowed_statuses:
        raise ValueError(
            f"Invalid participant status: {status}"
        )

    now = utc_now()

    reserved_at = (
        now
        if status == "registered"
        else None
    )

    waitlisted_at = (
        now
        if status == "waitlist"
        else None
    )

    cancelled_at = (
        now
        if status == "cancelled"
        else None
    )


    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO participants (
                workshop_id,
                telegram_user_id,
                username,
                first_name,
                last_name,
                phone,
                status,
                reserved_at,
                waitlisted_at,
                cancelled_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(
                workshop_id,
                telegram_user_id
            )

            DO UPDATE SET

                username =
                    excluded.username,

                first_name =
                    excluded.first_name,

                last_name =
                    excluded.last_name,

                phone =
                    excluded.phone,

                status =
                    excluded.status,


                reserved_at =
                    CASE
                        WHEN excluded.status = 'registered'
                        THEN COALESCE(
                            participants.reserved_at,
                            excluded.reserved_at
                        )
                        ELSE participants.reserved_at
                    END,


                waitlisted_at =
                    CASE
                        WHEN excluded.status = 'waitlist'
                        THEN COALESCE(
                            participants.waitlisted_at,
                            excluded.waitlisted_at
                        )
                        ELSE participants.waitlisted_at
                    END,


                cancelled_at =
                    CASE
                        WHEN excluded.status = 'cancelled'
                        THEN excluded.cancelled_at
                        ELSE participants.cancelled_at
                    END,


                updated_at =
                    excluded.updated_at
            """,
            (
                workshop_id,
                telegram_user_id,
                username,
                first_name,
                last_name,
                phone,
                status,
                reserved_at,
                waitlisted_at,
                cancelled_at,
                now,
                now,
            ),
        )


def get_participants(
    workshop_id: int,
    status: str | None = None,
) -> list[dict[str, Any]]:

    query = """
        SELECT *
        FROM participants
        WHERE workshop_id = ?
    """

    params: list[Any] = [
        workshop_id
    ]


    if status:

        query += """
            AND status = ?
        """

        params.append(
            status
        )


    query += """
        ORDER BY

            CASE status
                WHEN 'registered' THEN 1
                WHEN 'waitlist' THEN 2
                WHEN 'cancelled' THEN 3
                ELSE 4
            END,

            id ASC
    """


    with get_connection() as conn:

        rows = conn.execute(
            query,
            params,
        ).fetchall()


    return [
        dict(row)
        for row in rows
    ]


def get_workshop_participant_stats(
    workshop_id: int,
) -> dict[str, int]:

    result = {
        "registered": 0,
        "waitlist": 0,
        "cancelled": 0,
    }


    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT
                status,
                COUNT(*) AS count
            FROM participants
            WHERE workshop_id = ?
            GROUP BY status
            """,
            (workshop_id,),
        ).fetchall()


    for row in rows:

        status = row["status"]

        if status in result:

            result[status] = int(
                row["count"]
            )


    return result


def get_global_participant_count() -> int:

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM participants
            WHERE status = 'registered'
            """
        ).fetchone()


    return (
        int(row["count"])
        if row
        else 0
    )


def get_global_workshop_count() -> int:

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT COUNT(DISTINCT workshop_id) AS count
            FROM participants
            """
        ).fetchone()


    return (
        int(row["count"])
        if row
        else 0
    )


# =========================================================
# Admin logs
# =========================================================

def log_action(
    user: dict[str, Any] | None,
    action: str,
    workshop_id: int | None = None,
    ip: str | None = None,
    details: str | None = None,
) -> None:
    username = (
        str(user.get("username") or "anonymous")
        if user
        else "anonymous"
    )

    user_id = (
        user.get("id")
        if user
        else None
    )

    with get_connection() as conn:
        linked_user_id = user_id

        if linked_user_id is not None:
            linked_user = conn.execute(
                """
                SELECT id
                FROM users
                WHERE id = ?
                  AND username = ?
                """,
                (
                    linked_user_id,
                    username,
                ),
            ).fetchone()

            if linked_user is None:
                linked_user_id = None

        conn.execute(
            """
            INSERT INTO admin_logs (
                user_id,
                username,
                action,
                workshop_id,
                ip,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                linked_user_id,
                username,
                action,
                workshop_id,
                ip,
                details,
                utc_now(),
            ),
        )


def get_admin_logs(
    workshop_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:

    limit = max(
        1,
        min(limit, 1000)
    )


    if workshop_id is None:

        query = """
            SELECT *
            FROM admin_logs
            ORDER BY id DESC
            LIMIT ?
        """

        params = [
            limit
        ]

    else:

        query = """
            SELECT *
            FROM admin_logs
            WHERE workshop_id = ?
            ORDER BY id DESC
            LIMIT ?
        """

        params = [
            workshop_id,
            limit,
        ]


    with get_connection() as conn:

        rows = conn.execute(
            query,
            params,
        ).fetchall()


    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# Initialize database
# =========================================================

init_db()