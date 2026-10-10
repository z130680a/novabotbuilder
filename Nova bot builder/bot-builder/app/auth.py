import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time

from pathlib import Path

from fastapi import Request


# بارگذاری تنظیمات .env در صورت نصب بودن python-dotenv
try:
    from dotenv import load_dotenv

    load_dotenv()

except ImportError:
    pass


ADMIN_ACCESS_CODE = (
    os.getenv("NOVA_ADMIN_ACCESS_CODE", "").strip()
    or os.getenv("ADMIN_REGISTER_CODE", "").strip()
)


# =========================================================
# Paths / Session Settings
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "users.db"
SECRET_FILE = BASE_DIR / ".session_secret"

SESSION_COOKIE = "nova_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7

COOKIE_SECURE = (
    os.getenv("NOVA_COOKIE_SECURE", "false")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)


# =========================================================
# Session Secret
# =========================================================

def _get_secret() -> bytes:
    # اگر کلید معتبر در محیط تعریف شده باشد، از آن استفاده می‌کنیم.
    env_secret = os.getenv(
        "NOVA_SESSION_SECRET",
        "",
    ).strip()

    if len(env_secret.encode("utf-8")) >= 32:
        return env_secret.encode("utf-8")

    if SECRET_FILE.exists():
        secret = SECRET_FILE.read_bytes()

        if len(secret) >= 32:
            return secret

    secret = secrets.token_bytes(32)

    SECRET_FILE.write_bytes(secret)

    return secret


SESSION_SECRET = _get_secret()

# =========================================================
# Database
# =========================================================

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)

    conn.row_factory = sqlite3.Row

    return conn


def init_db() -> None:

    conn = get_db()

    try:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                last_ip TEXT,
                country TEXT,
                city TEXT,
                region TEXT,
                timezone TEXT
            )
            """
        )

        conn.commit()

        # -------------------------------------------------
        # Safe migration for older databases
        # -------------------------------------------------

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        migrations = {
            "last_login_at": "TEXT",
            "last_ip": "TEXT",
            "country": "TEXT",
            "city": "TEXT",
            "region": "TEXT",
            "timezone": "TEXT",
        }

        for column, column_type in migrations.items():

            if column not in columns:

                conn.execute(
                    f"""
                    ALTER TABLE users
                    ADD COLUMN {column} {column_type}
                    """
                )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# Passwords
# =========================================================

def hash_password(
    password: str,
) -> str:

    salt = secrets.token_bytes(16)

    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=64,
    )

    return (
        "scrypt$16384$8$1$"
        + base64.urlsafe_b64encode(
            salt
        ).decode("ascii")
        + "$"
        + base64.urlsafe_b64encode(
            derived
        ).decode("ascii")
    )


def verify_password(
    password: str,
    stored_hash: str,
) -> bool:

    try:

        parts = stored_hash.split("$")

        if len(parts) != 6:
            return False

        (
            algorithm,
            n,
            r,
            p,
            salt_b64,
            hash_b64,
        ) = parts

        if algorithm != "scrypt":
            return False

        salt = base64.urlsafe_b64decode(
            salt_b64.encode("ascii")
        )

        expected = base64.urlsafe_b64decode(
            hash_b64.encode("ascii")
        )

        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )

        return hmac.compare_digest(
            actual,
            expected,
        )

    except Exception:

        return False


# =========================================================
# Users
# =========================================================

def create_user(
    username: str,
    password: str,
    role: str = "user",
):

    username = str(
        username or ""
    ).strip()

    password = str(
        password or ""
    )

    if not username:

        raise ValueError(
            "نام کاربری الزامی است."
        )

    if len(username) < 3:

        raise ValueError(
            "نام کاربری باید حداقل ۳ کاراکتر باشد."
        )

    if len(username) > 32:

        raise ValueError(
            "نام کاربری نباید بیشتر از ۳۲ کاراکتر باشد."
        )

    if len(password) < 8:

        raise ValueError(
            "رمز عبور باید حداقل ۸ کاراکتر باشد."
        )

    if role not in {
        "user",
        "admin",
    }:

        role = "user"

    created_at = time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                hash_password(password),
                role,
                created_at,
            ),
        )

        conn.commit()

        return cursor.lastrowid

    except sqlite3.IntegrityError:

        raise ValueError(
            "این نام کاربری قبلا ثبت شده است."
        )

    finally:

        conn.close()


def get_user_by_username(
    username: str,
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (
                str(
                    username or ""
                ).strip(),
            ),
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:

        conn.close()


def get_user_by_id(
    user_id: int,
):

    try:

        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:

        conn.close()

def list_auth_users() -> list[dict]:
    conn = get_db()

    try:
        rows = conn.execute(
            """
            SELECT
                id,
                username,
                role,
                created_at,
                last_login_at,
                last_ip,
                country,
                city,
                region,
                timezone
            FROM users
            ORDER BY id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


def count_auth_users() -> int:
    conn = get_db()

    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()

        return int(row["total"]) if row else 0

    finally:
        conn.close()


def authenticate(
    username: str,
    password: str,
):

    user = get_user_by_username(
        username
    )

    if not user:
        return None

    if not verify_password(
        password,
        user["password_hash"],
    ):

        return None

    return user


def update_login_info(
    user_id: int,
    ip: str = "",
    country: str = "",
    city: str = "",
    region: str = "",
    timezone: str = "",
) -> None:

    login_time = time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET
                last_login_at = ?,
                last_ip = ?,
                country = ?,
                city = ?,
                region = ?,
                timezone = ?
            WHERE id = ?
            """,
            (
                login_time,
                ip,
                country,
                city,
                region,
                timezone,
                int(user_id),
            ),
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# Sessions
# =========================================================

def make_session(
    user_id: int,
) -> str:

    expires = (
        int(time.time())
        + SESSION_MAX_AGE
    )

    payload = (
        f"{int(user_id)}:{expires}"
        .encode("utf-8")
    )

    signature = hmac.new(
        SESSION_SECRET,
        payload,
        hashlib.sha256,
    ).hexdigest()

    raw = (
        f"{int(user_id)}:"
        f"{expires}:"
        f"{signature}"
    )

    return base64.urlsafe_b64encode(
        raw.encode("utf-8")
    ).decode("ascii")


def read_session(
    token: str,
):

    try:

        raw = base64.urlsafe_b64decode(
            token.encode("ascii")
        ).decode("utf-8")

        (
            user_id,
            expires,
            signature,
        ) = raw.split(":")

        user_id = int(
            user_id
        )

        expires = int(
            expires
        )

        if expires < int(
            time.time()
        ):

            return None

        payload = (
            f"{user_id}:{expires}"
            .encode("utf-8")
        )

        expected = hmac.new(
            SESSION_SECRET,
            payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected,
        ):

            return None

        return get_user_by_id(
            user_id
        )

    except Exception:

        return None


def get_current_user(
    request: Request,
):

    token = request.cookies.get(
        SESSION_COOKIE
    )

    if not token:
        return None

    return read_session(
        token
    )


def clear_login_cookie(
    response,
):

    response.delete_cookie(
        key=SESSION_COOKIE
    )

    return response




# =========================================================
# Admin Compatibility Helpers
# =========================================================

def register_account(
    username: str,
    password: str,
    access_code: str,
) -> dict:
    expected_code = (
        os.getenv("NOVA_ADMIN_ACCESS_CODE", "").strip()
        or os.getenv("ADMIN_REGISTER_CODE", "").strip()
    )

    if not expected_code:
        raise ValueError(
            "کد دسترسی مدیر در تنظیمات سرور تعریف نشده است."
        )

    if not hmac.compare_digest(
        str(access_code or ""),
        expected_code,
    ):
        raise ValueError(
            "کد دسترسی مدیر صحیح نیست."
        )

    conn = get_db()

    try:
        existing_admin = conn.execute(
            """
            SELECT id
            FROM users
            WHERE role = 'admin'
            LIMIT 1
            """
        ).fetchone()

    finally:
        conn.close()

    if existing_admin:
        raise ValueError(
            "حساب مدیر قبلاً ساخته شده است."
        )

    user_id = create_user(
        username=username,
        password=password,
        role="admin",
    )

    user = get_user_by_id(user_id)

    if not user:
        raise ValueError(
            "حساب مدیر ایجاد شد اما اطلاعات آن بازیابی نشد."
        )

    return user

def set_login_cookie(
    response,
    user_id: int,
):
    response.set_cookie(
        key=SESSION_COOKIE,
        value=make_session(user_id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )

    return response

# =========================================================
# Initialization
# =========================================================

def init_auth() -> None:

    init_db()


# =========================================================
# Direct Run
# =========================================================

if __name__ == "__main__":

    init_auth()

    print(
        f"Auth database ready: {DB_FILE}"
    )







def update_user_role(user_id: int, role: str) -> None:
    """Change a user's role."""
    if role not in {"user", "admin"}:
        raise ValueError("نقش انتخاب‌شده معتبر نیست.")

    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role, int(user_id)),
        )
        if cursor.rowcount == 0:
            raise ValueError("کاربر پیدا نشد.")
        conn.commit()
    finally:
        conn.close()


def update_user_password(user_id: int, password: str) -> None:
    """Set a new password using the existing password hash."""
    password = str(password or "")
    if len(password) < 8:
        raise ValueError("رمز عبور باید حداقل ۸ کاراکتر باشد.")

    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(password), int(user_id)),
        )
        if cursor.rowcount == 0:
            raise ValueError("کاربر پیدا نشد.")
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: int) -> None:
    """Delete a user only if at least one admin will remain."""
    user_id = int(user_id)
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")

        target = conn.execute(
            "SELECT id, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if target is None:
            raise ValueError("کاربر پیدا نشد.")

        if target["role"] == "admin":
            admins = conn.execute(
                "SELECT COUNT(*) AS total FROM users WHERE role = 'admin'"
            ).fetchone()["total"]

            if int(admins) <= 1:
                raise ValueError("حذف آخرین مدیر سیستم مجاز نیست.")

        conn.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()