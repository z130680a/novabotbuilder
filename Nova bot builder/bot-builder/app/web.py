import sys
from pathlib import Path
from contextlib import asynccontextmanager
from html import escape
from typing import Optional

# =========================================================
# Python Path
# =========================================================

APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))


# =========================================================
# FastAPI
# =========================================================

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


# =========================================================
# Project Imports
# =========================================================

from admin import router as admin_router

from auth import (
    init_auth,
    get_current_user,
    create_user,
    authenticate,
    update_login_info,
    set_login_cookie,
)

from database import (
    init_db,
    log_action,
    record_workshop_created,
    touch_workshop,
    get_workshop_meta,
)

from agent import agent
from builder import build_bot
from code_generator import generate_bot_code
from bot_manager import bot_manager
from sandbox import run_sandbox

from modifier import modify_workshop

from workshop_store import (
    load_workshops,
    add_workshop,
    get_workshop,
    update_workshop,
    delete_workshop,
    save_workshops,
)

from workshop_status import get_workshop_status

from ip_location import (
    get_client_ip,
    lookup_ip,
)


# =========================================================
# Base Directories
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

ASSETS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Database / Auth Initialization
# =========================================================

init_db()
init_auth()


# =========================================================
# App Lifespan
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        generated_bot = (
            BASE_DIR
            / "generated_bots"
            / "generated_bot.py"
        )

        workshops = load_workshops()

        if workshops and generated_bot.exists():
            bot_manager.start_bot()
            print("Telegram bot started successfully.")

        yield

    except Exception as exc:
        print(
            f"[App Lifespan Error] "
            f"{type(exc).__name__}: {exc}"
        )
        raise

# =========================================================
# FastAPI App
# =========================================================

app = FastAPI(
    title="Nova Bot Builder",
    lifespan=lifespan,
)


# =========================================================
# Static Files
# =========================================================

app.mount(
    "/assets",
    StaticFiles(
        directory=str(ASSETS_DIR),
    ),
    name="assets",
)


# =========================================================
# Routers
# =========================================================

app.include_router(
    admin_router
)


# =========================================================
# Authentication Helpers
# =========================================================

def require_user(
    request: Request,
):

    user = get_current_user(
        request
    )

    if not user:
        return None

    return user


def require_admin(
    request: Request,
):

    user = get_current_user(
        request
    )

    if not user:
        return None

    if user.get("role") != "admin":
        return None

    return user


# =========================================================
# General Helpers
# =========================================================

def model_to_dict(value):

    if hasattr(
        value,
        "model_dump",
    ):
        return value.model_dump()

    if hasattr(
        value,
        "dict",
    ):
        return value.dict()

    if isinstance(
        value,
        dict,
    ):
        return dict(value)

    return dict(value)


def clean_text(
    value,
) -> str:

    return str(
        value or ""
    ).strip()


def effective_spec(
    workshop: dict,
) -> dict:

    nested = workshop.get(
        "spec"
    )

    if isinstance(
        nested,
        dict,
    ):
        spec = dict(
            nested
        )

    else:
        spec = {}

    for key in (
        "bot_name",
        "purpose",
        "capacity",
        "features",
        "missing_information",
        "event_date",
        "event_time",
        "event_end_time",
    ):

        if (
            key in workshop
            and workshop.get(key) is not None
        ):

            spec[key] = workshop.get(
                key
            )

    return spec


def spec_value(
    spec: dict,
    key: str,
    default="-",
):

    value = spec.get(
        key,
        default,
    )

    if (
        value is None
        or value == ""
    ):

        return default

    return value


def normalize_questions(
    value,
) -> list[str]:

    if not value:
        return []

    if isinstance(
        value,
        list,
    ):

        return [
            clean_text(item)
            for item in value
            if clean_text(item)
        ]

    value = clean_text(
        value
    )

    return [
        value
    ] if value else []


def normalize_datetime_for_form(
    value,
) -> str:

    value = clean_text(
        value
    )

    if not value:
        return ""

    parts = value.split(
        ":"
    )

    if len(parts) >= 2:

        hour = parts[0].strip()
        minute = parts[1].strip()

        if (
            hour.isdigit()
            and minute.isdigit()
        ):

            return (
                hour.zfill(2)
                + ":"
                + minute.zfill(2)
            )

    return value


def apply_event_fields(
    spec: dict,
    event_date: Optional[str],
    event_time: Optional[str],
    event_end_time: Optional[str] = None,
) -> dict:

    result = dict(
        spec
    )

    result["event_date"] = clean_text(
        event_date
    )

    result["event_time"] = clean_text(
        event_time
    )

    result["event_end_time"] = clean_text(
        event_end_time
    )

    return result


# =========================================================
# Workshop Permissions
# =========================================================

def can_user_manage_workshop(
    user: dict,
    workshop_id: int,
) -> bool:

    if not user:
        return False

    if user.get("role") == "admin":
        return True

    workshop = get_workshop(
        workshop_id
    )

    if workshop:

        owner_id = workshop.get(
            "owner_user_id"
        )

        if (
            owner_id is not None
            and user.get("id") is not None
        ):

            try:

                return (
                    int(owner_id)
                    == int(user["id"])
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

    meta = get_workshop_meta(
        workshop_id
    )

    if not meta:
        return False

    try:

        return (
            int(
                meta.get(
                    "creator_user_id",
                    -1,
                )
            )
            == int(
                user.get(
                    "id",
                    -2,
                )
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return False


# =========================================================
# Workshop Status
# =========================================================

def normalize_status(
    spec: dict,
) -> dict:

    try:

        status = get_workshop_status(
            spec
        )

    except Exception:

        return {
            "code": "invalid",
            "label": "نامشخص",
        }

    if isinstance(
        status,
        dict,
    ):

        code = clean_text(
            status.get(
                "code",
                "invalid",
            )
        )

        label = clean_text(
            status.get(
                "label",
                "نامشخص",
            )
        )

        return {
            "code": code or "invalid",
            "label": label or "نامشخص",
        }

    code = clean_text(
        getattr(
            status,
            "code",
            "invalid",
        )
    )

    label = clean_text(
        getattr(
            status,
            "label",
            "نامشخص",
        )
    )

    return {
        "code": code or "invalid",
        "label": label or "نامشخص",
    }


def status_for_ui(
    spec: dict,
) -> dict:

    status = normalize_status(
        spec
    )

    code = status["code"]

    if code in (
        "active",
        "upcoming",
        "ongoing",
    ):

        return {
            "code": "active",
            "label": "فعال",
        }

    if code == "ended":

        return {
            "code": "ended",
            "label": "غیرفعال",
        }

    return {
        "code": "invalid",
        "label": "نامشخص",
    }


# =========================================================
# UI Helpers
# =========================================================

def feature_chips(
    features,
) -> str:

    if not isinstance(
        features,
        list,
    ):

        features = []

    if not features:

        return """
        <span class="muted">
            قابلیتی ثبت نشده
        </span>
        """

    parts = []

    for feature in features:

        parts.append(
            f"""
            <span class="feature-chip">
                <span class="chip-dot"></span>
                {escape(str(feature))}
            </span>
            """
        )

    return "".join(
        parts
    )


def status_badge(
    spec: dict,
) -> str:

    status = status_for_ui(
        spec
    )

    code = status["code"]
    label = status["label"]

    if code == "active":

        icon = "🟢"

    elif code == "ended":

        icon = "⚪"

    else:

        icon = "🟠"

    return f"""
    <div class="status-badge {escape(code)}">
        <span>{icon}</span>
        {escape(label)}
    </div>
    """


def spec_card(
    spec: dict,
) -> str:

    bot_name = escape(
        str(
            spec_value(
                spec,
                "bot_name",
                "نام کارگاه ثبت نشده",
            )
        )
    )

    purpose = escape(
        str(
            spec_value(
                spec,
                "purpose",
                "توضیحی ثبت نشده",
            )
        )
    )

    capacity = escape(
        str(
            spec_value(
                spec,
                "capacity",
                "نامشخص",
            )
        )
    )

    event_date = escape(
        str(
            spec_value(
                spec,
                "event_date",
                "تعیین نشده",
            )
        )
    )

    event_time = escape(
        str(
            spec_value(
                spec,
                "event_time",
                "تعیین نشده",
            )
        )
    )

    event_end_time = escape(
        str(
            spec_value(
                spec,
                "event_end_time",
                "تعیین نشده",
            )
        )
    )

    features = feature_chips(
        spec.get(
            "features",
            [],
        )
    )

    return f"""
    <div class="spec-card">

        <div class="spec-main">

            <div>

                <h3>
                    {bot_name}
                </h3>

                <p class="muted">
                    {purpose}
                </p>

            </div>

            <div class="badge">
                ظرفیت {capacity} نفر
            </div>

        </div>

        <div class="info-grid">

            <div class="info-box">

                <span class="info-label">
                    تاریخ برگزاری
                </span>

                <strong>
                    {event_date}
                </strong>

            </div>

            <div class="info-box">

                <span class="info-label">
                    ساعت شروع
                </span>

                <strong>
                    {event_time}
                </strong>

            </div>

            <div class="info-box">

                <span class="info-label">
                    ساعت پایان
                </span>

                <strong>
                    {event_end_time}
                </strong>

            </div>

            <div class="info-box">

                <span class="info-label">
                    ظرفیت
                </span>

                <strong>
                    {capacity} نفر
                </strong>

            </div>

        </div>

        <div class="feature-list">
            {features}
        </div>

    </div>
    """


def error_message(
    exc: Exception,
) -> str:

    message = str(
        exc
    )

    lower = message.lower()

    if (
        "timed out" in lower
        or "timeout" in lower
    ):

        return (
            "زمان پاسخ Agent تمام شد. "
            "دوباره درخواست را ارسال کنید."
        )

    return (
        message
        or
        "خطای نامشخص رخ داد."
    )


def failed_tests_text(
    sandbox_result: dict,
) -> str:

    failed = []

    for test in sandbox_result.get(
        "tests",
        [],
    ):

        if not test.get(
            "passed",
            False,
        ):

            name = test.get(
                "name",
                "Test",
            )

            message = test.get(
                "message",
                "",
            )

            failed.append(
                f"{name}: {message}"
            )

    if failed:

        return "\n".join(
            failed
        )

    return str(
        sandbox_result
    )


def render_error_page(
    title: str,
    heading: str,
    message: str,
    back_url: str = "/dashboard",
    back_text: str = "← بازگشت",
) -> HTMLResponse:

    content = f"""
    <section class="card error-card">

        <div class="result-header">

            <div class="result-title">

                <div class="result-check error">
                    ✕
                </div>

                <div>

                    <h1>
                        {escape(heading)}
                    </h1>

                    <p>
                        عملیات انجام نشد.
                    </p>

                </div>

            </div>

        </div>

        <div class="error-box">
            {escape(message)}
        </div>

        <div class="actions top-gap">

            <a
                class="button button-secondary"
                href="{escape(back_url, quote=True)}"
            >
                {escape(back_text)}
            </a>

        </div>

    </section>
    """

    return HTMLResponse(
        make_page(
            content,
            title,
        )
    )


# =========================================================
# CSS
# =========================================================

BASE_STYLE = """
* {
    box-sizing: border-box;
}

:root {
    --bg: #070b16;
    --card: rgba(17,24,39,.82);
    --border: rgba(255,255,255,.09);
    --text: #f8fafc;
    --text-soft: #aab4c5;
    --text-muted: #748097;
    --blue: #5b8cff;
    --purple: #8b5cf6;
    --cyan: #22d3ee;
    --green: #22c55e;
    --orange: #f59e0b;
    --red: #ef4444;
    --radius-lg: 26px;
}

html {
    scroll-behavior: smooth;
}

body {
    margin: 0;
    min-height: 100vh;
    color: var(--text);
    font-family: Tahoma, Arial, sans-serif;
    background:
        radial-gradient(
            circle at 10% 15%,
            rgba(91,140,255,.14),
            transparent 28%
        ),
        radial-gradient(
            circle at 90% 10%,
            rgba(139,92,246,.13),
            transparent 25%
        ),
        radial-gradient(
            circle at 50% 90%,
            rgba(34,211,238,.08),
            transparent 25%
        ),
        var(--bg);
    overflow-x: hidden;
}

body::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(
            rgba(255,255,255,.018) 1px,
            transparent 1px
        ),
        linear-gradient(
            90deg,
            rgba(255,255,255,.018) 1px,
            transparent 1px
        );
    background-size: 45px 45px;
    pointer-events: none;
    z-index: -1;
}

a {
    color: inherit;
}

.page {
    width: min(1180px, calc(100% - 32px));
    margin: 0 auto;
    padding: 24px 0 70px;
}

.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    padding: 10px 0 30px;
}

.brand {
    display: flex;
    align-items: center;
    gap: 13px;
    text-decoration: none;
}

.brand-logo {
    width: 48px;
    height: 48px;
    flex: 0 0 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.brand-logo img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
}

.brand {
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none;
}

.brand-info {
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.header-status {
    display: flex;
    align-items: center;
    gap: 8px;
}


.online-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 12px rgba(34,197,94,.75);
}

.hero {
    position: relative;
    overflow: hidden;
    padding: 55px 45px;
    margin-bottom: 22px;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background:
        linear-gradient(
            135deg,
            rgba(24,33,58,.92),
            rgba(12,18,34,.88)
        );
    box-shadow: 0 35px 80px rgba(0,0,0,.30);
}

.hero h1 {
    margin: 0 0 18px;
    max-width: 850px;
    font-size: clamp(30px, 5vw, 54px);
    line-height: 1.25;
    letter-spacing: -1.6px;
}

.hero h1 span,
.hero-box h1 span {
    background:
        linear-gradient(
            90deg,
            #8db0ff,
            #c2a2ff,
            #74e7f7
        );
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.hero p {
    margin: 0;
    max-width: 760px;
    color: var(--text-soft);
    font-size: 15px;
    line-height: 2;
}

.hero-badge {
    display: inline-flex;
    align-items: center;
    padding: 8px 12px;
    margin-bottom: 20px;
    border: 1px solid rgba(91,140,255,.24);
    border-radius: 999px;
    color: #c8d6ff;
    font-size: 12px;
    background: rgba(91,140,255,.08);
}

.card {
    padding: 30px;
    margin-bottom: 22px;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background:
        linear-gradient(
            180deg,
            rgba(17,24,39,.80),
            rgba(11,17,30,.78)
        );
    box-shadow: 0 20px 55px rgba(0,0,0,.22);
}

.result-header,
.section-head,
.input-footer,
.spec-main,
.dashboard-header,
.dashboard-actions {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
}

.section-head {
    margin-bottom: 22px;
}

.section-title {
    margin: 0 0 7px;
    font-size: 21px;
    font-weight: 800;
}

.section-description {
    margin: 0;
    color: var(--text-soft);
    font-size: 13px;
    line-height: 1.9;
}

.result-title {
    display: flex;
    align-items: center;
    gap: 13px;
}

.result-title h1 {
    margin: 0 0 5px;
    font-size: 22px;
}

.result-title p {
    margin: 0;
    color: var(--text-soft);
    font-size: 12px;
}

.result-check,
.section-icon {
    display: flex;
    align-items: center;
    justify-content: center;
}

.result-check {
    width: 48px;
    height: 48px;
    flex: 0 0 48px;
    border-radius: 15px;
    background: rgba(34,197,94,.12);
    border: 1px solid rgba(34,197,94,.20);
    font-size: 21px;
}

.result-check.error {
    background: rgba(239,68,68,.12);
    border-color: rgba(239,68,68,.22);
}

.section-icon {
    width: 46px;
    height: 46px;
    flex: 0 0 46px;
    border-radius: 14px;
    font-size: 21px;
    background:
        linear-gradient(
            135deg,
            rgba(91,140,255,.15),
            rgba(139,92,246,.14)
        );
    border: 1px solid rgba(255,255,255,.07);
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 999px;
    white-space: nowrap;
    font-size: 11px;
    font-weight: 700;
}

.status-badge.active {
    color: #a7f3d0;
    border: 1px solid rgba(34,197,94,.18);
    background: rgba(34,197,94,.08);
}

.status-badge.ended {
    color: #cbd5e1;
    border: 1px solid rgba(148,163,184,.18);
    background: rgba(148,163,184,.08);
}

.status-badge.invalid {
    color: #fde68a;
    border: 1px solid rgba(245,158,11,.18);
    background: rgba(245,158,11,.08);
}

.badge {
    padding: 8px 12px;
    border-radius: 999px;
    color: #cfe0ff;
    font-size: 11px;
    background: rgba(91,140,255,.08);
    border: 1px solid rgba(91,140,255,.16);
    white-space: nowrap;
}

.spec-main {
    align-items: center;
}

.spec-main h3 {
    margin: 0 0 7px;
    font-size: 20px;
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-top: 18px;
}

.info-box {
    padding: 14px;
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 14px;
}

.info-label {
    display: block;
    margin-bottom: 8px;
    color: var(--text-muted);
    font-size: 12px;
}

.info-box strong {
    font-size: 15px;
}

.feature-list {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 14px;
}

.feature-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 9px;
    border-radius: 9px;
    border: 1px solid rgba(91,140,255,.12);
    color: #cdd8ec;
    background: rgba(91,140,255,.06);
    font-size: 10px;
}

.chip-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--blue);
}

.form-group {
    margin-bottom: 15px;
}

.form-group label,
.auth-card label {
    display: block;
    margin: 0 0 8px;
    color: #dbe4f2;
    font-size: 12px;
    font-weight: 700;
}

input,
textarea {
    font-family: Tahoma, Arial, sans-serif;
}

input[type="text"],
input[type="time"],
input[type="password"] {
    width: 100%;
    height: 48px;
    padding: 0 14px;
    outline: none;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 14px;
    color: var(--text);
    font-size: 13px;
    background: rgba(255,255,255,.025);
}

textarea {
    width: 100%;
    min-height: 165px;
    padding: 18px;
    resize: vertical;
    outline: none;
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 16px;
    color: var(--text);
    font-size: 14px;
    line-height: 2;
    background: rgba(255,255,255,.025);
}

input:focus,
textarea:focus {
    border-color: rgba(91,140,255,.55);
    box-shadow: 0 0 0 4px rgba(91,140,255,.08);
}

input::placeholder,
textarea::placeholder {
    color: #667085;
}

.actions,
.hero-actions,
.workshop-actions,
.dashboard-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 11px;
}

.top-gap {
    margin-top: 20px;
}

.button,
.primary-btn,
.secondary-btn,
.danger-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 13px 18px;
    border-radius: 13px;
    cursor: pointer;
    color: #fff;
    border: 0;
    font-family: Tahoma, Arial, sans-serif;
    font-size: 13px;
    font-weight: 700;
    text-decoration: none;
    transition:
        transform .18s ease,
        filter .18s ease;
}

.button:hover,
.primary-btn:hover,
.secondary-btn:hover,
.danger-btn:hover {
    transform: translateY(-2px);
    filter: brightness(1.06);
}

.button-primary,
.primary-btn {
    background:
        linear-gradient(
            135deg,
            #4f7cff,
            #7658f6
        );
    box-shadow:
        0 12px 30px
        rgba(91,140,255,.24);
}

.button-secondary,
.secondary-btn {
    background: rgba(255,255,255,.055);
    border: 1px solid rgba(255,255,255,.08);
}

.button-telegram {
    background:
        linear-gradient(
            135deg,
            #229ed9,
            #268bd2
        );
}

.button-danger,
.danger-btn {
    background: rgba(239,68,68,.10);
    border: 1px solid rgba(239,68,68,.18);
    color: #fecaca;
}

.full-btn {
    width: 100%;
    margin-top: 24px;
}

.helper-text,
.muted {
    color: var(--text-muted);
    font-size: 11px;
    line-height: 1.9;
}

.input-footer {
    align-items: center;
    margin-top: 12px;
}

.spec-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 13px;
    margin-top: 18px;
}

.error-card {
    border-color: rgba(239,68,68,.22);
    background:
        linear-gradient(
            180deg,
            rgba(48,18,25,.60),
            rgba(24,13,20,.70)
        );
}

.success-card {
    border-color: rgba(34,197,94,.18);
}

.error-box {
    padding: 17px;
    margin-top: 17px;
    border-radius: 14px;
    border: 1px solid rgba(239,68,68,.16);
    background: rgba(239,68,68,.06);
    color: #fecaca;
    font-size: 12px;
    line-height: 2;
    white-space: pre-wrap;
    direction: rtl;
}

.status-flow {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 24px 0;
}

.status-step {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 13px;
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 14px;
}

.status-step-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    flex: 0 0 34px;
    border-radius: 10px;
    background: rgba(34,197,94,.10);
}

.status-step strong {
    display: block;
    margin-bottom: 3px;
    font-size: 11px;
}

.status-step span {
    color: var(--text-muted);
    font-size: 10px;
}

.landing {
    min-height: 75vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 50px 20px;
}

.hero-box {
    width: 100%;
    max-width: 950px;
    text-align: center;
    padding: 70px 40px;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 28px;
    background: rgba(255,255,255,.03);
    box-shadow: 0 30px 100px rgba(0,0,0,.25);
}

.hero-box h1 {
    font-size: 52px;
    line-height: 1.25;
    margin: 0 auto 20px;
    max-width: 850px;
}

.hero-description {
    color: rgba(255,255,255,.65);
    max-width: 650px;
    margin: 0 auto 35px;
    line-height: 2;
    font-size: 17px;
}

.hero-features {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
}

.feature-box {
    padding: 22px;
    border-radius: 18px;
    background: rgba(255,255,255,.04);
    text-align: right;
}

.feature-box strong {
    display: block;
    margin-bottom: 8px;
}

.feature-box span {
    color: rgba(255,255,255,.55);
    font-size: 13px;
}

.auth-wrapper {
    min-height: 75vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 30px 20px;
}

.auth-card {
    width: 100%;
    max-width: 460px;
    padding: 40px;
    border-radius: 24px;
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.08);
}

.auth-logo {
    font-size: 14px;
    letter-spacing: 4px;
    margin-bottom: 25px;
    opacity: .7;
}

.auth-card h1 {
    margin: 0 0 10px;
}

.auth-card p {
    color: rgba(255,255,255,.55);
    line-height: 1.8;
    margin-bottom: 30px;
}

.auth-card input {
    width: 100%;
    height: 48px;
    box-sizing: border-box;
    padding: 0 16px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,.1);
    background: rgba(0,0,0,.2);
    color: white;
    outline: none;
}

.auth-card label {
    margin-top: 16px;
}

.auth-footer {
    text-align: center;
    margin-top: 25px;
    color: rgba(255,255,255,.55);
}

.auth-footer a {
    color: white;
    text-decoration: none;
}

.empty-state {
    padding: 80px 30px;
    text-align: center;
    border: 1px dashed rgba(255,255,255,.12);
    border-radius: 24px;
}

.empty-icon {
    width: 60px;
    height: 60px;
    margin: 0 auto 20px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255,255,255,.06);
    font-size: 30px;
}

.workshops-grid {
    display: grid;
    grid-template-columns: repeat(
        auto-fit,
        minmax(280px, 1fr)
    );
    gap: 18px;
}

.workshop-card {
    padding: 24px;
    border-radius: 20px;
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.08);
}

.workshop-top {
    display: flex;
    justify-content: space-between;
    gap: 15px;
}

.workshop-label {
    color: rgba(255,255,255,.45);
    font-size: 12px;
    margin-bottom: 6px;
}

.workshop-card h3 {
    margin: 0;
}

.workshop-meta {
    display: flex;
    gap: 15px;
    flex-wrap: wrap;
    margin-top: 20px;
    color: rgba(255,255,255,.55);
    font-size: 13px;
}

.workshop-actions {
    margin-top: 22px;
}

.profile-card {
    max-width: 800px;
    border-radius: 20px;
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.08);
    overflow: hidden;
}

.profile-row {
    display: flex;
    justify-content: space-between;
    gap: 30px;
    padding: 20px 24px;
    border-bottom: 1px solid rgba(255,255,255,.06);
}

.profile-row span {
    color: rgba(255,255,255,.55);
}

.profile-row strong {
    text-align: left;
    direction: ltr;
}

.loading-overlay {
    position: fixed;
    inset: 0;
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    background: rgba(5,8,18,.78);
    backdrop-filter: blur(9px);
}

.loading-box {
    width: min(
        420px,
        calc(100% - 32px)
    );
    padding: 30px;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 22px;
    text-align: center;
    background: rgba(13,19,36,.94);
    box-shadow: 0 30px 80px rgba(0,0,0,.4);
}

.loading-spinner {
    width: 46px;
    height: 46px;
    margin: 0 auto 17px;
    border: 3px solid rgba(255,255,255,.09);
    border-top-color: var(--blue);
    border-right-color: var(--purple);
    border-radius: 50%;
    animation: spin .8s linear infinite;
}

.loading-box h3 {
    margin: 0 0 8px;
    font-size: 17px;
}

.loading-box p {
    margin: 0;
    color: var(--text-muted);
    font-size: 11px;
    line-height: 1.9;
}

.dashboard-header {
    align-items: center;
    margin-bottom: 28px;
}

.dashboard-header h1 {
    margin: 8px 0;
    font-size: 32px;
}

.dashboard-header p {
    margin: 0;
    color: var(--text-soft);
}

.eyebrow {
    color: #8db0ff;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
}

.dashboard-section-title {
    margin: 0 0 18px;
    font-size: 22px;
    font-weight: 800;
}

.footer {
    padding: 25px 0 0;
    text-align: center;
    color: var(--text-muted);
    font-size: 10px;
}

.empty-box {
    text-align: center;
    padding: 18px 0 6px;
}

@keyframes spin {

    to {
        transform: rotate(360deg);
    }
}

@media (max-width: 820px) {

    .hero {
        padding: 45px 28px;
    }

    .status-flow {
        grid-template-columns: 1fr;
    }

    .spec-grid {
        grid-template-columns: 1fr;
    }

    .info-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .dashboard-header {
        align-items: flex-start;
        flex-direction: column;
    }

}

@media (max-width: 700px) {

    .hero-box {
        padding: 45px 20px;
    }

    .hero-box h1 {
        font-size: 36px;
    }

    .hero-features {
        grid-template-columns: 1fr;
    }

    .profile-row {
        flex-direction: column;
        gap: 8px;
    }

}

@media (max-width: 600px) {

    .page {
        width: calc(100% - 18px);
        padding-top: 12px;
    }

    .header-status {
        display: none;
    }

    .hero {
        padding: 34px 21px;
        border-radius: 21px;
    }

    .hero h1 {
        font-size: 30px;
    }

    .hero-box h1 {
        font-size: 30px;
    }

    .card {
        padding: 21px;
        border-radius: 20px;
    }

    .result-header,
    .section-head,
    .input-footer,
    .spec-main {
        flex-direction: column;
    }

    .info-grid {
        grid-template-columns: 1fr;
    }

    .actions,
    .workshop-actions,
    .dashboard-actions {
        width: 100%;
    }

    .button,
    .primary-btn,
    .secondary-btn,
    .danger-btn {
        width: 100%;
    }

}
"""


# =========================================================
# HTML Shell
# =========================================================

def make_page(
    content: str = "",
    page_title: str = "Nova Bot Builder",
) -> str:

    shell = """
<!DOCTYPE html>

<html lang="fa" dir="rtl">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>__TITLE__</title>

    <style>
__STYLE__
    </style>

</head>

<body>

<div
    class="loading-overlay"
    id="loadingOverlay"
>

    <div class="loading-box">

        <div class="loading-spinner"></div>

        <h3>
            در حال پردازش...
        </h3>

        <p>
            Agent در حال انجام درخواست است.
            <br>
            لطفاً تا آماده شدن نتیجه صفحه را نبندید.
        </p>

    </div>

</div>


<div class="page">


<header class="header">
    <a class="brand" href="/">
        <div class="brand-logo">
            <img src="/assets/logo.svg" alt="Nova">
        </div>

        <div class="brand-info">
            <div class="brand-name">
                Nova Bot Builder
            </div>

            <div class="brand-subtitle">
                Agent-powered bot studio
            </div>
        </div>
    </a>

    <div class="header-status">
        <span class="online-dot"></span>
        <span>سیستم فعال است</span>
    </div>
</header>



__CONTENT__


<footer class="footer">

    Nova Bot Builder · ساخت و مدیریت بات با Agent

</footer>

</div>


<script>

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const forms =
            document.querySelectorAll("form");

        forms.forEach(
            function (form) {

                form.addEventListener(
                    "submit",
                    function () {

                        const button =
                            form.querySelector(
                                "button[type='submit']"
                            );

                        if (button) {

                            button.disabled = true;
                            button.style.opacity = "0.7";
                            button.style.cursor = "wait";

                        }

                        const loading =
                            document.getElementById(
                                "loadingOverlay"
                            );

                        if (loading) {

                            loading.style.display = "flex";

                        }

                    }
                );

            }
        );

    }
);

</script>

</body>

</html>
"""

    return (
        shell
        .replace(
            "__TITLE__",
            escape(page_title),
        )
        .replace(
            "__STYLE__",
            BASE_STYLE,
        )
        .replace(
            "__CONTENT__",
            content,
        )
    )


# =========================================================
# Public Home
# =========================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def landing_page(request: Request):
    user = get_current_user(request)

    if user:
        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )

    return RedirectResponse(
        "/login",
        status_code=303,
    )

# =========================================================
# Builder Page
# =========================================================

@app.get(
    "/builder",
    response_class=HTMLResponse,
)
def builder_page(
    request: Request,
):

    user = require_user(
        request
    )

    if not user:

        return RedirectResponse(
            "/login",
            status_code=303,
        )

    return make_page(
        """
        <section class="hero">

            <div class="hero-badge">
                🧠 AI BOT BUILDER
            </div>

            <h1>
                بات جدیدت را
                <span>توصیف کن.</span>
            </h1>

            <p>
                توضیح بده بات باید چه کاری انجام دهد.
                Agent اطلاعات لازم را استخراج می‌کند
                و در صورت نیاز از تو سؤال می‌پرسد.
            </p>

        </section>


        <section class="card">

            <div class="section-head">

                <div>

                    <h2 class="section-title">
                        ساخت بات جدید
                    </h2>

                    <p class="section-description">
                        درخواستت را با زبان طبیعی بنویس.
                    </p>

                </div>

                <div class="section-icon">
                    🤖
                </div>

            </div>


            <form
                method="post"
                action="/analyze"
            >

            
<div class="form-group">
    <label for="bot_name">نام بات یا کارگاه</label>
    <input
        id="bot_name"
        type="text"
        name="bot_name"
        placeholder="مثلاً بات رزرو کارگاه خطاطی"
        maxlength="100"
    >
</div>


                <div class="form-group">

                    <label for="request">
                        باتی که می‌خواهی بسازی
                    </label>

                    <textarea
                        id="request"
                        name="user_request"
                        placeholder="مثلاً یک بات تلگرامی برای رزرو کارگاه خطاطی می‌خواهم که ظرفیت مشخص داشته باشد و کاربران بتوانند رزرو، لغو رزرو و مشاهده ظرفیت انجام دهند."
                        required
                    ></textarea>

                </div>


                <div class="spec-grid">

                    <div class="form-group">

                        <label for="event_date">
                            تاریخ برگزاری
                        </label>

                        <input
                            id="event_date"
                            type="text"
                            name="event_date"
                            placeholder="مثلاً ۱۴۰۵/۰۷/۲۵"
                        >

                    </div>


                    <div class="form-group">

                        <label for="event_time">
                            ساعت شروع
                        </label>

                        <input
                            id="event_time"
                            type="time"
                            name="event_time"
                        >

                    </div>


                    <div class="form-group">

                        <label for="event_end_time">
                            ساعت پایان
                        </label>

                        <input
                            id="event_end_time"
                            type="time"
                            name="event_end_time"
                        >

                    </div>

                </div>


                <div class="actions top-gap">

                    <button
                        class="primary-btn"
                        type="submit"
                    >
                        🧠 تحلیل درخواست
                    </button>

                    <a
                        class="secondary-btn"
                        href="/dashboard"
                    >
                        ← بازگشت به پنل
                    </a>

                </div>

            </form>

        </section>
        """,
        "ساخت بات | Nova",
    )



# =========================================================
# Analyze
# =========================================================

def translate_question(question: str) -> str:
    translations = {
        "capacity": "ظرفیت کارگاه چند نفر است؟",
        "date/time": "تاریخ و ساعت برگزاری کارگاه چیست؟",
        "date": "تاریخ برگزاری کارگاه چه روزی است؟",
        "time": "ساعت شروع و پایان کارگاه چه زمانی است؟",
        "event_date": "تاریخ برگزاری کارگاه چه روزی است؟",
        "event_time": "ساعت شروع کارگاه چه زمانی است؟",
        "event_end_time": "ساعت پایان کارگاه چه زمانی است؟",
    }

    key = str(question).strip()
    return translations.get(key, key)


@app.post(
    "/analyze",
    response_class=HTMLResponse,
)
def analyze(
    http_request: Request,
    user_request: str = Form(...),
    bot_name: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    event_end_time: str = Form(""),
):
    user = require_user(http_request)

    if not user:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    try:
        result = agent.invoke(
            {
                "user_request": user_request,
                "bot_spec": None,
                "response": "",
            }
        )

        raw_spec = (
            result.get("bot_spec")
            if isinstance(result, dict)
            else None
        )

        if raw_spec is None:
            raise RuntimeError(
                "Agent مشخصات کارگاه را برنگرداند."
            )

        spec = model_to_dict(raw_spec)

        spec = apply_event_fields(
            spec,
            event_date,
            event_time,
            event_end_time,
        )

    except Exception as exc:
        return render_error_page(
            "خطا | Nova",
            "خطا در تحلیل درخواست",
            error_message(exc),
            "/builder",
            "← بازگشت به Builder",
        )

    # سؤال‌ها را نرمال‌سازی کن.
    questions = normalize_questions(
        spec.get("missing_information", [])
    )

    # اگر تاریخ و ساعت از قبل وارد شده‌اند،
    # دیگر آن‌ها را دوباره سؤال نکن.
    date_provided = bool(clean_text(event_date))
    start_time_provided = bool(clean_text(event_time))
    end_time_provided = bool(clean_text(event_end_time))

    filtered_questions = []

    for question in questions:
        key = str(question).strip().lower()

        if key in ("date", "event_date") and date_provided:
            continue

        if key == "time" and start_time_provided and end_time_provided:
            continue

        if key == "date/time" and date_provided and start_time_provided:
            continue

        if key == "event_time" and start_time_provided:
            continue

        if key == "event_end_time" and end_time_provided:
            continue

        filtered_questions.append(question)

    questions = filtered_questions

    request_value = escape(
        user_request,
        quote=True,
    )

    event_date_value = escape(
        clean_text(event_date),
        quote=True,
    )

    event_time_value = escape(
        clean_text(event_time),
        quote=True,
    )

    event_end_time_value = escape(
        clean_text(event_end_time),
        quote=True,
    )

    # اگر سؤال دیگری باقی نمانده، مستقیم به ساخت بات برو.
    if not questions:
        content = f"""
        <section class="hero">
            <div class="hero-badge">
                ✅ اطلاعات کامل است
            </div>

            <h1>
                اطلاعات آماده است،
                <span>بات را بساز.</span>
            </h1>

            <p>
                اطلاعات موردنیاز دریافت شده است.
                می‌توانی ساخت بات را شروع کنی.
            </p>
        </section>

        <section class="card success-card">
            <div class="result-header">
                <div class="result-title">
                    <div class="result-check">✓</div>
                    <div>
                        <h1>آماده ساخت</h1>
                        <p>بدون سؤال اضافه</p>
                    </div>
                </div>

                {status_badge(spec)}
            </div>

            {spec_card(spec)}

            <form method="post" action="/finalize">
                <input
    type="hidden"
    name="bot_name"
    value="{escape(clean_text(bot_name), quote=True)}"
>

                <input type="hidden" name="questions" value="">

                <input type="hidden" name="event_date"
                       value="{event_date_value}">

                <input type="hidden" name="event_time"
                       value="{event_time_value}">

                <input type="hidden" name="event_end_time"
                       value="{event_end_time_value}">

                <div class="actions top-gap">
                    <button class="primary-btn" type="submit">
                        🚀 ساخت بات
                    </button>

                    <a class="secondary-btn" href="/dashboard">
                        ← بازگشت به پنل
                    </a>
                </div>
            </form>
        </section>
        """

        return make_page(content, "ساخت بات | Nova")

    # ساخت فرم سؤال‌ها با متن فارسی
    question_html = []

    for index, question in enumerate(questions, 1):
        question_text = escape(
            translate_question(question)
        )

        question_html.append(
            f"""
            <section class="card">
                <div class="section-head">
                    <div>
                        <h2 class="section-title">
                            سؤال {index}
                        </h2>

                        <p class="section-description">
                            برای ساخت دقیق‌تر بات به این مورد نیاز داریم.
                        </p>
                    </div>

                    <div class="section-icon">❓</div>
                </div>

                <strong
                    style="
                        display:block;
                        margin-bottom:10px;
                        font-size:13px;
                    "
                >
                    {question_text}
                </strong>

                <textarea
                    name="answer_{index}"
                    form="answers_form"
                    placeholder="پاسخ خود را بنویسید..."
                    required
                ></textarea>
            </section>
            """
        )

    questions_value = escape(
        "||".join(questions),
        quote=True,
    )

    content = f"""
    <section class="hero">
        <div class="hero-badge">🧠 Agent</div>

        <h1>
            چند سؤال کوتاه،
            <span>و بعد ساخت بات.</span>
        </h1>

        <p>
            درخواست شما تحلیل شد.
            فقط به سؤال‌های زیر پاسخ بده.
        </p>
    </section>

    <form
        id="answers_form"
        method="post"
        action="/finalize"
    >
        <input type="hidden" name="user_request"
               value="{request_value}">

        <input type="hidden" name="questions"
               value="{questions_value}">

        <input type="hidden" name="event_date"
               value="{event_date_value}">

        <input type="hidden" name="event_time"
               value="{event_time_value}">

        <input type="hidden" name="event_end_time"
               value="{event_end_time_value}">

        {''.join(question_html)}

        <section class="card">
            <div class="actions">
                <button class="primary-btn" type="submit">
                    🚀 ساخت بات
                </button>

                <a class="secondary-btn" href="/dashboard">
                    ← بازگشت به پنل
                </a>
            </div>
        </section>
    </form>
    """

    return make_page(
        content,
        "تکمیل اطلاعات | Nova",
    )




# =========================================================
# Finalize / Create
# =========================================================

@app.post(
    "/finalize",
    response_class=HTMLResponse,
)
async def finalize(
    http_request: Request,
    user_request: str = Form(...),
    questions: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    event_end_time: str = Form(""),
):

    user = require_user(
        http_request
    )

    if not user:

        return RedirectResponse(
            "/login",
            status_code=303,
        )

    try:

        form = await http_request.form()

        question_list = normalize_questions(
            questions.split("||")
            if questions
            else []
        )

        answers = []

        for index, question in enumerate(
            question_list,
            1,
        ):

            user_answer = clean_text(
                form.get(
                    f"answer_{index}",
                    "",
                )
            )

            answers.append(
                f"سؤال: {question}\n"
                f"پاسخ: {user_answer}"
            )


        result = build_bot(
            user_request,
            "\n".join(answers),
        )

        spec = model_to_dict(
            result
        )

        spec = apply_event_fields(
            spec,
            event_date,
            event_time,
            event_end_time,
        )


        # -------------------------------------------------
        # Generate
        # -------------------------------------------------

        generate_bot_code(
            spec
        )


        # -------------------------------------------------
        # Sandbox
        # -------------------------------------------------

        sandbox_result = run_sandbox(
            spec
        )

        if not sandbox_result.get(
            "passed",
            False,
        ):

            return render_error_page(
                "Sandbox | Nova",
                "بات در Sandbox رد شد",
                failed_tests_text(
                    sandbox_result
                ),
                "/builder",
                "← بازگشت به Builder",
            )


        # -------------------------------------------------
        # User Location
        # -------------------------------------------------

        ip = get_client_ip(
            http_request
        )

        location = lookup_ip(
            ip
        )

        # -------------------------------------------------
        # Save Workshop
        # -------------------------------------------------

        workshop = add_workshop(
            spec,
            owner_user_id=user["id"],
            creator_ip=location.get(
                "ip",
                ip,
            ),
            creator_country=location.get(
                "country",
                "",
            ),
            creator_city=location.get(
                "city",
                "",
            ),
        )


        # -------------------------------------------------
        # Activity Log
        # -------------------------------------------------

        try:

            record_workshop_created(
                workshop_id=workshop["id"],
                user=user,
                ip=ip,
            )

            log_action(
                user=user,
                action="workshop_created",
                workshop_id=workshop["id"],
                ip=ip,
            )

        except Exception:

            pass


        # -------------------------------------------------
        # Restart
        # -------------------------------------------------

        try:

            bot_result = (
                bot_manager.restart_bot()
            )

        except Exception as restart_error:

            return render_error_page(
                "خطا در اجرا | Nova",
                "کارگاه ذخیره شد اما بات اجرا نشد",
                error_message(
                    restart_error
                ),
                "/dashboard",
                "📚 بازگشت به پنل",
            )


        saved_spec = effective_spec(
            workshop
        )

        workshop_name = saved_spec.get(
            "bot_name",
            "کارگاه جدید",
        )


        content = f"""
        <section class="hero">

            <div class="hero-badge">
                🎉 ساخت موفق
            </div>

            <h1>

                <span>
                    {escape(str(workshop_name))}
                </span>

                با موفقیت ساخته شد.

            </h1>

            <p>
                نسخه اجرایی ساخته شد،
                Sandbox پاس شد
                و بات منتشر شد.
            </p>

        </section>


        <section class="card success-card">

            <div class="status-flow">

                <div class="status-step">

                    <div class="status-step-icon">
                        🧠
                    </div>

                    <div>

                        <strong>
                            Agent
                        </strong>

                        <span>
                            مشخصات را ساخت
                        </span>

                    </div>

                </div>


                <div class="status-step">

                    <div class="status-step-icon">
                        🧪
                    </div>

                    <div>

                        <strong>
                            Sandbox
                        </strong>

                        <span>
                            تست موفق
                        </span>

                    </div>

                </div>


                <div class="status-step">

                    <div class="status-step-icon">
                        🚀
                    </div>

                    <div>

                        <strong>
                            Publish
                        </strong>

                        <span>
                            نسخه فعال شد
                        </span>

                    </div>

                </div>

            </div>


            {spec_card(saved_spec)}


            <div class="actions top-gap">

                <a
                    class="primary-btn"
                    href="/workshop/{workshop['id']}/edit"
                >
                    ✏️ ویرایش همین کارگاه
                </a>


                <a
                    class="button button-telegram"
                    href="https://web.telegram.org/k/#@Novazmit_Bot"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    🚀 باز کردن Telegram
                </a>


                <a
                    class="secondary-btn"
                    href="/dashboard"
                >
                    📚 بازگشت به پنل
                </a>

            </div>


            <p
                class="muted"
                style="margin-top:15px;"
            >

                وضعیت اجرا:

                {escape(
                    str(
                        bot_result.get(
                            "message",
                            "",
                        )
                    )
                )}

            </p>

        </section>
        """

        return make_page(
            content,
            "بات ساخته شد | Nova",
        )


    except Exception as exc:

        return render_error_page(
            "خطا | Nova",
            "خطا در ساخت بات",
            error_message(exc),
            "/builder",
            "← بازگشت به Builder",
        )


# =========================================================
# Workshop Edit - GET
# =========================================================

@app.get(
    "/workshop/{workshop_id}/edit",
    response_class=HTMLResponse,
)
def edit_workshop_page(
    workshop_id: int,
    request: Request,
):
    user = require_user(request)

    if not user:
        return RedirectResponse("/login", status_code=303)

    workshop = get_workshop(workshop_id)

    if not workshop:
        return render_error_page(
            "کارگاه پیدا نشد | Nova",
            "کارگاه پیدا نشد",
            "این کارگاه وجود ندارد یا قبلاً حذف شده است.",
            "/dashboard",
            "← بازگشت به پنل",
        )

    if not can_user_manage_workshop(user, workshop_id):
        return render_error_page(
            "دسترسی غیرمجاز | Nova",
            "دسترسی غیرمجاز",
            "شما اجازه ویرایش این کارگاه را ندارید.",
            "/dashboard",
            "← بازگشت به پنل",
        )

    spec = effective_spec(workshop)

    name = escape(
        str(spec_value(spec, "bot_name", "بات رزرو کارگاه")),
        quote=True,
    )

    event_date = escape(
        clean_text(str(spec.get("event_date", "") or "")),
        quote=True,
    )

    event_time = escape(
        normalize_datetime_for_form(
            spec.get("event_time", "") or ""
        ),
        quote=True,
    )

    event_end_time = escape(
        normalize_datetime_for_form(
            spec.get("event_end_time", "") or ""
        ),
        quote=True,
    )

    content = f"""
    <section class="hero">
        <div class="hero-badge">✏️ ویرایش بات</div>

        <h1>
            ویرایش
            <span>{name}</span>
        </h1>

        <p>
            نام بات و زمان برگزاری کارگاه را تغییر بده.
            تغییرات روی همین کارگاه ذخیره می‌شوند.
        </p>
    </section>

    <section class="card">
        <div class="section-head">
            <div>
                <h2 class="section-title">مشخصات فعلی</h2>
                <p class="section-description">
                    اطلاعات فعلی همین بات
                </p>
            </div>
            <div class="section-icon">📋</div>
        </div>

        {spec_card(spec)}
    </section>

    <section class="card">
        <div class="section-head">
            <div>
                <h2 class="section-title">ویرایش مشخصات</h2>
                <p class="section-description">
                    نام، تاریخ و ساعت را تغییر بده.
                </p>
            </div>
            <div class="section-icon">⚙️</div>
        </div>

        <form method="post" action="/workshop/{workshop_id}/edit">
            <div class="form-group">
                <label for="bot_name">نام بات یا کارگاه</label>
                <input
                    id="bot_name"
                    type="text"
                    name="bot_name"
                    value="{name}"
                    maxlength="100"
                    required
                    placeholder="مثلاً بات رزرو کارگاه خطاطی"
                >
            </div>

            <div class="spec-grid">
                <div class="form-group">
                    <label for="event_date">تاریخ برگزاری</label>
                    <input
                        id="event_date"
                        type="text"
                        name="event_date"
                        value="{event_date}"
                        placeholder="مثلاً ۱۴۰۵/۰۸/۲۰"
                    >
                </div>

                <div class="form-group">
                    <label for="event_time">ساعت شروع</label>
                    <input
                        id="event_time"
                        type="time"
                        name="event_time"
                        value="{event_time}"
                    >
                </div>

                <div class="form-group">
                    <label for="event_end_time">ساعت پایان</label>
                    <input
                        id="event_end_time"
                        type="time"
                        name="event_end_time"
                        value="{event_end_time}"
                    >
                </div>
            </div>

            <div class="input-footer">
                <span class="helper-text">
                    💡 تغییرات را ذخیره کن تا در مشخصات همین کارگاه ثبت شوند.
                </span>

                <div class="actions">
                    <button class="primary-btn" type="submit">
                        💾 ذخیره تغییرات
                    </button>

                    <a class="secondary-btn" href="/dashboard">
                        ← انصراف
                    </a>
                </div>
            </div>
        </form>
    </section>
    """

    return make_page(
        content,
        f"ویرایش {name} | Nova",
    )


# =========================================================
# Workshop Edit - POST
# =========================================================

@app.post(
    "/workshop/{workshop_id}/edit",
    response_class=HTMLResponse,
)
def edit_workshop(
    workshop_id: int,
    request: Request,
    bot_name: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    event_end_time: str = Form(""),
):
    user = require_user(request)

    if not user:
        return RedirectResponse("/login", status_code=303)

    workshop = get_workshop(workshop_id)

    if not workshop:
        return render_error_page(
            "کارگاه پیدا نشد | Nova",
            "کارگاه پیدا نشد",
            "این کارگاه وجود ندارد یا قبلاً حذف شده است.",
            "/dashboard",
            "← بازگشت به پنل",
        )

    if not can_user_manage_workshop(user, workshop_id):
        return render_error_page(
            "دسترسی غیرمجاز | Nova",
            "دسترسی غیرمجاز",
            "شما اجازه ویرایش این کارگاه را ندارید.",
            "/dashboard",
            "← بازگشت به پنل",
        )

    # مشخصات فعلی کارگاه
    current_spec = effective_spec(workshop)

    # تبدیل مشخصات به دیکشنری قابل ویرایش
    if hasattr(current_spec, "model_dump"):
        current_spec = current_spec.model_dump()
    elif hasattr(current_spec, "dict"):
        current_spec = current_spec.dict()
    else:
        current_spec = dict(current_spec)

    # -------------------------
    # اعتبارسنجی نام
    # -------------------------
    bot_name = clean_text(bot_name)

    if not bot_name:
        bot_name = str(
            current_spec.get(
                "bot_name",
                "بات رزرو کارگاه",
            )
        )

    if len(bot_name) > 100:
        return render_error_page(
            "نام نامعتبر | Nova",
            "نام بیش از حد طولانی است",
            "نام بات باید حداکثر ۱۰۰ کاراکتر باشد.",
            f"/workshop/{workshop_id}/edit",
            "← بازگشت به ویرایش",
        )

    current_spec["bot_name"] = bot_name

    # -------------------------
    # تاریخ و ساعت
    # اگر فیلد خالی باشد، مقدار قبلی حفظ می‌شود.
    # -------------------------
    event_date = clean_text(event_date)
    event_time = clean_text(event_time)
    event_end_time = clean_text(event_end_time)

    if event_date:
        current_spec["event_date"] = event_date

    if event_time:
        current_spec["event_time"] = event_time

    if event_end_time:
        current_spec["event_end_time"] = event_end_time

    # -------------------------
    # ذخیره تغییرات در فایل کارگاه‌ها
    # -------------------------
    try:
        updated_workshop = update_workshop(
            workshop_id,
            current_spec,
        )

        if not updated_workshop:
            return render_error_page(
                "ذخیره ناموفق | Nova",
                "تغییرات ذخیره نشد",
                "کارگاه به‌روزرسانی نشد. دوباره تلاش کن.",
                f"/workshop/{workshop_id}/edit",
                "← بازگشت به ویرایش",
            )

    except Exception as exc:
        return render_error_page(
            "خطا در ذخیره | Nova",
            "ذخیره تغییرات با خطا مواجه شد",
            escape(str(exc)),
            f"/workshop/{workshop_id}/edit",
            "← بازگشت به ویرایش",
        )

    # خواندن دوباره اطلاعات ذخیره‌شده
    updated_workshop = get_workshop(workshop_id)

    if not updated_workshop:
        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )

    updated_spec = effective_spec(updated_workshop)

    if hasattr(updated_spec, "model_dump"):
        updated_spec = updated_spec.model_dump()
    elif hasattr(updated_spec, "dict"):
        updated_spec = updated_spec.dict()

    saved_name = escape(
        str(
            spec_value(
                updated_spec,
                "bot_name",
                bot_name,
            )
        ),
        quote=True,
    )

    content = f"""
    <section class="hero">
        <div class="hero-badge">✅ تغییرات ذخیره شد</div>

        <h1>
            ویرایش با موفقیت انجام شد
        </h1>

        <p>
            مشخصات بات
            <strong>{saved_name}</strong>
            ذخیره شد.
        </p>
    </section>

    <section class="card">
        <h2 class="section-title">مشخصات به‌روزشده</h2>
        {spec_card(updated_spec)}

        <div class="actions" style="margin-top:20px;">
            <a
                class="primary-btn"
                href="/workshop/{workshop_id}/edit"
            >
                ✏️ ویرایش دوباره
            </a>

            <a class="secondary-btn" href="/dashboard">
                بازگشت به داشبورد ←
            </a>
        </div>
    </section>
    """

    return make_page(
        content,
        f"ویرایش {saved_name} | Nova",
    )



    # -----------------------------------------------------
    # Agent Modification
    # -----------------------------------------------------

    if change:

        try:

            result = modify_workshop(
                current_spec,
                change,
            )

            new_spec = model_to_dict(
                result
            )

        except Exception as exc:

            return render_error_page(
                "خطا در ویرایش | Nova",
                "تغییر انجام نشد",
                error_message(exc),
                f"/workshop/{workshop_id}/edit",
                "← بازگشت به ویرایش",
            )

    else:

        new_spec = dict(
            current_spec
        )


    # -----------------------------------------------------
    # Event Fields
    # -----------------------------------------------------

    new_event_date = (
        clean_text(event_date)
        if clean_text(event_date)
        else current_spec.get(
            "event_date",
            "",
        )
    )

    new_event_time = (
        clean_text(event_time)
        if clean_text(event_time)
        else current_spec.get(
            "event_time",
            "",
        )
    )

    new_event_end_time = (
        clean_text(event_end_time)
        if clean_text(event_end_time)
        else current_spec.get(
            "event_end_time",
            "",
        )
    )


    new_spec = apply_event_fields(
        new_spec,
        new_event_date,
        new_event_time,
        new_event_end_time,
    )


    # -----------------------------------------------------
    # Preserve Important Fields
    # -----------------------------------------------------

    for key in (
        "bot_name",
        "purpose",
        "capacity",
        "features",
        "missing_information",
    ):

        if (
            key not in new_spec
            or new_spec.get(key) is None
        ):

            new_spec[key] = current_spec.get(
                key
            )


    # -----------------------------------------------------
    # Generate
    # -----------------------------------------------------

    try:

        generate_bot_code(
            new_spec
        )

    except Exception as exc:

        return render_error_page(
            "خطا | Nova",
            "خطا در بازسازی بات",
            error_message(exc),
            f"/workshop/{workshop_id}/edit",
            "← بازگشت",
        )


    # -----------------------------------------------------
    # Sandbox
    # -----------------------------------------------------

    try:

        sandbox_result = run_sandbox(
            new_spec
        )

    except Exception as exc:

        sandbox_result = {
            "passed": False,
            "tests": [
                {
                    "name": "Sandbox",
                    "passed": False,
                    "message": error_message(exc),
                }
            ],
        }


    if not sandbox_result.get(
        "passed",
        False,
    ):

        try:

            generate_bot_code(
                current_spec
            )

        except Exception:

            pass


        return render_error_page(
            "Sandbox | Nova",
            "تغییر تأیید نشد",
            failed_tests_text(
                sandbox_result
            ),
            f"/workshop/{workshop_id}/edit",
            "← بازگشت به ویرایش",
        )


    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    updated = update_workshop(
        workshop_id,
        new_spec,
    )


    if not updated:

        try:

            generate_bot_code(
                current_spec
            )

        except Exception:

            pass


        return render_error_page(
            "خطا | Nova",
            "ذخیره تغییرات ناموفق بود",
            "اطلاعات کارگاه ذخیره نشد.",
            f"/workshop/{workshop_id}/edit",
            "← بازگشت",
        )


    # -----------------------------------------------------
    # Restart
    # -----------------------------------------------------

    try:

        bot_result = (
            bot_manager.restart_bot()
        )

    except Exception as exc:

        return render_error_page(
            "خطا در اجرا | Nova",
            "تغییر ذخیره شد اما بات Restart نشد",
            error_message(exc),
            "/dashboard",
            "📚 بازگشت به پنل",
        )


    # -----------------------------------------------------
    # Activity Log
    # -----------------------------------------------------

    try:

        client_ip = get_client_ip(
            request
        )

        touch_workshop(
            workshop_id=workshop_id,
            user=user,
            ip=client_ip,
        )

        log_action(
            user=user,
            action="workshop_updated",
            workshop_id=workshop_id,
            ip=client_ip,
        )

    except Exception:

        pass


    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    updated_workshop = (
        get_workshop(
            workshop_id
        )
        or {}
    )

    updated_spec = effective_spec(
        updated_workshop
    )


    content = f"""
    <section class="hero">

        <div class="hero-badge">
            ✅ ویرایش موفق
        </div>

        <h1>

            <span>
                {escape(
                    str(
                        updated_spec.get(
                            "bot_name",
                            "کارگاه",
                        )
                    )
                )}
            </span>

            به‌روزرسانی شد.

        </h1>

        <p>
            تغییرات اعمال شد،
            Sandbox تأیید کرد
            و نسخه جدید بات منتشر شد.
        </p>

    </section>


    <section class="card success-card">

        {status_badge(updated_spec)}

        {spec_card(updated_spec)}


        <div class="actions top-gap">

            <a
                class="primary-btn"
                href="/dashboard"
            >
                📚 بازگشت به پنل
            </a>

            <a
                class="secondary-btn"
                href="/workshop/{workshop_id}/edit"
            >
                ✏️ ویرایش دوباره
            </a>

        </div>


        <p
            class="muted"
            style="margin-top:15px;"
        >

            وضعیت اجرا:

            {escape(
                str(
                    bot_result.get(
                        "message",
                        "",
                    )
                )
            )}

        </p>

    </section>
    """

    return make_page(
        content,
        "ویرایش موفق | Nova",
    )


# =========================================================
# Workshop Delete
# =========================================================

@app.post(
    "/workshop/{workshop_id}/delete",
    response_class=HTMLResponse,
)
def delete_workshop_route(
    workshop_id: int,
    request: Request,
):

    user = require_user(
        request
    )

    if not user:

        return RedirectResponse(
            "/login",
            status_code=303,
        )


    workshop = get_workshop(
        workshop_id
    )

    if not workshop:

        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )


    if not can_user_manage_workshop(
        user,
        workshop_id,
    ):

        return render_error_page(
            "دسترسی غیرمجاز | Nova",
            "دسترسی غیرمجاز",
            "شما اجازه حذف این کارگاه را ندارید.",
            "/dashboard",
            "← بازگشت به پنل",
        )


    previous_workshops = load_workshops()


    deleted = delete_workshop(
        workshop_id
    )


    if not deleted:

        return render_error_page(
            "خطا در حذف | Nova",
            "حذف انجام نشد",
            "حذف کارگاه انجام نشد.",
            "/dashboard",
            "← بازگشت به پنل",
        )


    remaining = load_workshops()


    if remaining:

        rebuild_spec = effective_spec(
            remaining[0]
        )

    else:

        rebuild_spec = {
            "bot_name": "Nova Multi Workshop Bot",
            "purpose": "مدیریت چند کارگاه",
            "capacity": 1,
            "features": [],
            "missing_information": [],
            "event_date": "",
            "event_time": "",
            "event_end_time": "",
        }


    # -----------------------------------------------------
    # Rebuild and Test
    # -----------------------------------------------------

    try:

        generate_bot_code(
            rebuild_spec
        )

        sandbox_result = run_sandbox(
            rebuild_spec
        )

        if not sandbox_result.get(
            "passed",
            False,
        ):

            raise RuntimeError(
                failed_tests_text(
                    sandbox_result
                )
            )

    except Exception as exc:

        try:

            save_workshops(
                previous_workshops
            )

        except Exception:

            pass


        try:

            if previous_workshops:

                restore_spec = effective_spec(
                    previous_workshops[0]
                )

                generate_bot_code(
                    restore_spec
                )

        except Exception:

            pass


        return render_error_page(
            "حذف ناموفق | Nova",
            "حذف تأیید نشد",
            (
                "نسخه جدید پس از حذف "
                "در Sandbox تأیید نشد و "
                "اطلاعات به وضعیت قبلی برگشت.\n\n"
                + error_message(exc)
            ),
            "/dashboard",
            "← بازگشت به پنل",
        )


    # -----------------------------------------------------
    # Restart
    # -----------------------------------------------------

    try:

        bot_result = (
            bot_manager.restart_bot()
        )

    except Exception as exc:

        try:

            save_workshops(
                previous_workshops
            )

        except Exception:

            pass


        try:

            if previous_workshops:

                restore_spec = effective_spec(
                    previous_workshops[0]
                )

                generate_bot_code(
                    restore_spec
                )

        except Exception:

            pass


        return render_error_page(
            "خطا در اجرا | Nova",
            "حذف انجام نشد",
            (
                "بات بعد از حذف Restart نشد "
                "و اطلاعات به وضعیت قبلی برگشت.\n\n"
                + error_message(exc)
            ),
            "/dashboard",
            "📚 بازگشت به پنل",
        )


    # -----------------------------------------------------
    # Activity Log
    # -----------------------------------------------------

    try:

        client_ip = get_client_ip(
            request
        )

        log_action(
            user=user,
            action="workshop_deleted",
            workshop_id=workshop_id,
            ip=client_ip,
        )

    except Exception:

        pass


    workshop_name = (
        effective_spec(
            workshop
        ).get(
            "bot_name",
            "کارگاه",
        )
    )


    content = f"""
    <section class="hero">

        <div class="hero-badge">
            🗑️ حذف انجام شد
        </div>

        <h1>

            <span>
                {escape(str(workshop_name))}
            </span>

            حذف شد.

        </h1>

        <p>
            این کارگاه از سیستم حذف شد
            و نسخه جدید بات منتشر شد.
        </p>

    </section>


    <section class="card success-card">

        <div class="result-header">

            <div class="result-title">

                <div class="result-check">
                    ✓
                </div>

                <div>

                    <h1>
                        {len(remaining)}
                        کارگاه باقی مانده
                    </h1>

                    <p>
                        لیست Telegram نیز به‌روزرسانی شد.
                    </p>

                </div>

            </div>


            <div class="status-badge active">
                🟢 منتشر شد
            </div>

        </div>


        <div class="actions top-gap">

            <a
                class="primary-btn"
                href="/dashboard"
            >
                📚 بازگشت به پنل
            </a>

        </div>


        <p
            class="muted"
            style="margin-top:15px;"
        >

            وضعیت اجرا:

            {escape(
                str(
                    bot_result.get(
                        "message",
                        "",
                    )
                )
            )}

        </p>

    </section>
    """

    return make_page(
        content,
        "کارگاه حذف شد | Nova",
    )


# =========================================================
# Register
# =========================================================

@app.get(
    "/register",
    response_class=HTMLResponse,
)
def register_page(
    request: Request,
):

    if get_current_user(
        request
    ):

        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )


    return make_page(
        """
        <div class="auth-wrapper">

            <div class="auth-card">

                <div class="auth-logo">
                    NOVA
                </div>

                <h1>
                    ساخت حساب
                </h1>

                <p>
                 برای ساخت و مدیریت بات‌های خود
                 یک حساب ایجاد کنید.
                </p>

                <form
                    method="post"
                    action="/register"
                >

                    <label>
                        نام کاربری
                    </label>

                    <input
                        type="text"
                        name="username"
                        minlength="3"
                        maxlength="32"
                        required
                    />


                    <label>
                        رمز عبور
                    </label>

                    <input
                        type="password"
                        name="password"
                        minlength="8"
                        required
                    />


                    <label>
                        تکرار رمز عبور
                    </label>

                    <input
                        type="password"
                        name="password_confirm"
                        minlength="8"
                        required
                    />


                    <button
                        type="submit"
                        class="primary-btn full-btn"
                    >
                        ساخت حساب
                    </button>

                </form>


                <div class="auth-footer">

                    قبلاً حساب ساخته‌اید؟

                    <a href="/login">
                        وارد شوید
                    </a>

                </div>

            </div>

        </div>
        """,
        "ثبت‌نام | Nova",
    )


@app.post(
    "/register",
    response_class=HTMLResponse,
)
def register_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):

    if get_current_user(
        request
    ):

        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )


    username = username.strip()


    if password != password_confirm:

        return make_page(
            """
            <div class="auth-wrapper">

                <div class="auth-card">

                    <h1>
                        خطا
                    </h1>

                    <div class="error-box">
                        رمز عبور و تکرار آن یکسان نیستند.
                    </div>

                    <a
                        href="/register"
                        class="secondary-btn"
                    >
                        بازگشت
                    </a>

                </div>

            </div>
            """,
            "خطا | Nova",
        )


    try:

        user_id = create_user(
            username,
            password,
            role="user",
        )

    except ValueError as exc:

        return make_page(
            f"""
            <div class="auth-wrapper">

                <div class="auth-card">

                    <h1>
                        خطا در ثبت‌نام
                    </h1>

                    <div class="error-box">
                        {escape(str(exc))}
                    </div>

                    <a
                        href="/register"
                        class="secondary-btn"
                    >
                        بازگشت
                    </a>

                </div>

            </div>
            """,
            "خطا | Nova",
        )



    # -----------------------------------------------------
    # IP Location
    # -----------------------------------------------------

    ip = get_client_ip(request)
    location = {}

    try:
        result = lookup_ip(ip)

        if isinstance(result, dict):
            location = result

    except Exception as exc:
        print(
            f"[IP Location Error] "
            f"{type(exc).__name__}: {exc}"
        )

    # -----------------------------------------------------
    # Update Login Information
    # -----------------------------------------------------

    try:
        update_login_info(
            user_id,
            ip=location.get("ip") or ip,
            country=location.get("country") or "",
            city=location.get("city") or "",
            region=location.get("region") or "",
            timezone=location.get("timezone") or "",
        )

    except Exception as exc:
        print(
            f"[Login Info Error] "
            f"{type(exc).__name__}: {exc}"
        )

    # -----------------------------------------------------
    # Redirect and Session Cookie
    # -----------------------------------------------------

    response = RedirectResponse(
        url="/dashboard",
        status_code=303,
    )

    set_login_cookie(
    response,
    user_id,
)

    return response


# =========================================================
# Login
# =========================================================

@app.get(
    "/login",
    response_class=HTMLResponse,
)
def login_page(
    request: Request,
):

    if get_current_user(
        request
    ):

        return RedirectResponse(
            "/dashboard",
            status_code=303,
        )


    return make_page(
        """
        <div class="auth-wrapper">

            <div class="auth-card">

                <div class="auth-logo">
                    NOVA
                </div>

                <h1>
                    ورود به حساب
                </h1>

                <p>
                 برای ادامه وارد حساب کاربری خود شوید.
                </p>

            

                <form
                    method="post"
                    action="/login"
                >

                    <label>
                        نام کاربری
                    </label>

                    <input
                        type="text"
                        name="username"
                        required
                    />


                    <label>
                        رمز عبور
                    </label>

                    <input
                        type="password"
                        name="password"
                        required
                    />


                    <button
                        type="submit"
                        class="primary-btn full-btn"
                    >
                        ورود
                    </button>

                </form>


                <div class="auth-footer">

                    حساب ندارید؟

                    <a href="/register">
                        ثبت‌نام کنید
                    </a>

                </div>

            </div>

        </div>
        """,
        "ورود | Nova",
    )



@app.post(
    "/login",
    response_class=HTMLResponse,
)
def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate(
        username.strip(),
        password,
    )

    if not user:
        return make_page(
            """
            <div class="auth-wrapper">
                <div class="auth-card">
                    <h1>
                        ورود ناموفق
                    </h1>

                    <div class="error-box">
                        نام کاربری یا رمز عبور اشتباه است.
                    </div>

                    <a
                        href="/login"
                        class="secondary-btn"
                    >
                        تلاش دوباره
                    </a>
                </div>
            </div>
            """,
            "ورود ناموفق | Nova",
        )

    # دریافت IP و اطلاعات مکانی
    ip = get_client_ip(request)
    location = {}

    try:
        result = lookup_ip(ip)

        if isinstance(result, dict):
            location = result

    except Exception as exc:
        print(
            f"[IP Location Error] "
            f"{type(exc).__name__}: {exc}"
        )

    # ذخیره اطلاعات آخرین ورود
    try:
        update_login_info(
            user["id"],
            ip=location.get("ip") or ip,
            country=location.get("country") or "",
            city=location.get("city") or "",
            region=location.get("region") or "",
            timezone=location.get("timezone") or "",
        )

    except Exception as exc:
        print(
            f"[Login Info Error] "
            f"{type(exc).__name__}: {exc}"
        )

    # انتقال به داشبورد و تنظیم کوکی
    response = RedirectResponse(
        url="/dashboard",
        status_code=303,
    )

    set_login_cookie(
        response,
        user["id"],
    )

    return response


# =========================================================
# Logout
# =========================================================

@app.post(
    "/logout"
)
def logout():

    response = RedirectResponse(
        "/",
        status_code=303,
    )

    response.delete_cookie(
        "nova_session"
    )

    return response


# =========================================================
# Dashboard
# =========================================================

@app.get(
    "/dashboard",
    response_class=HTMLResponse,
)
def dashboard(
    request: Request,
):

    user = require_user(
        request
    )

    if not user:

        return RedirectResponse(
            "/login",
            status_code=303,
        )


    all_workshops = load_workshops()


    my_workshops = []

    for item in all_workshops:

        owner_id = item.get(
            "owner_user_id"
        )

        if owner_id is None:
            continue

        try:

            if (
                int(owner_id)
                == int(user["id"])
            ):

                my_workshops.append(
                    item
                )

        except (
            TypeError,
            ValueError,
        ):

            continue


    cards = ""


    if not my_workshops:

        cards = """
        <div class="empty-state">

            <div class="empty-icon">
                +
            </div>

            <h2>
                هنوز باتی نساخته‌اید
            </h2>

            <p>
                اولین بات خودتان را بسازید و
                آن را از همین پنل مدیریت کنید.
            </p>

            <a
                href="/builder"
                class="primary-btn"
            >
                ساخت بات جدید
            </a>

        </div>
        """

    else:

        for workshop in reversed(
            my_workshops
        ):

            spec = effective_spec(
                workshop
            )

            name = escape(
                str(
                    spec_value(
                        spec,
                        "bot_name",
                        "بات بدون نام",
                    )
                )
            )

            capacity = escape(
                str(
                    spec_value(
                        spec,
                        "capacity",
                        "-",
                    )
                )
            )

            workshop_id = int(
                workshop["id"]
            )


            cards += f"""
            <div class="workshop-card">

                <div class="workshop-top">

                    <div>

                        <div class="workshop-label">
                            بات شما
                        </div>

                        <h3>
                            {name}
                        </h3>

                    </div>

                    {status_badge(spec)}

                </div>


                <div class="workshop-meta">

                    <span>
                        ظرفیت: {capacity}
                    </span>

                    <span>
                        شناسه: #{workshop_id}
                    </span>

                </div>


                <div class="workshop-actions">

                    <a
                        href="/workshop/{workshop_id}/edit"
                        class="secondary-btn"
                    >
                        ✏️ ویرایش
                    </a>


                    <form
                        method="post"
                        action="/workshop/{workshop_id}/delete"
                        onsubmit="
                            return confirm(
                                'آیا از حذف این بات مطمئن هستید؟'
                            );
                        "
                    >

                        <button
                            type="submit"
                            class="danger-btn"
                        >
                            🗑 حذف
                        </button>

                    </form>

                </div>

            </div>
            """


    admin_button = ""

    if user.get(
        "role"
    ) == "admin":

        admin_button = """
        <a
            href="/admin"
            class="secondary-btn"
        >
            ⚙️ مدیریت
        </a>
        """


    return make_page(
        f"""
        <div class="dashboard-header">

            <div>

                <div class="eyebrow">
                    NOVA DASHBOARD
                </div>

                <h1>
                    سلام {escape(str(user["username"]))} 👋
                </h1>

                <p>
                    بات‌های خود را از اینجا مدیریت کنید.
                </p>

            </div>


            <div class="dashboard-actions">

                <a
                    href="/builder"
                    class="primary-btn"
                >
                    + ساخت بات جدید
                </a>

                <a
                    href="/profile"
                    class="secondary-btn"
                >
                    پروفایل
                </a>

                {admin_button}

                <form
                    method="post"
                    action="/logout"
                >

                    <button
                        class="secondary-btn"
                        type="submit"
                    >
                        خروج
                    </button>

                </form>

            </div>

        </div>


        <div class="dashboard-section-title">
            بات‌های من
        </div>


        <div class="workshops-grid">
            {cards}
        </div>
        """,
        "داشبورد | Nova",
    )


# =========================================================
# Profile
# =========================================================

@app.get(
    "/profile",
    response_class=HTMLResponse,
)
def profile(
    request: Request,
):
    user = require_user(request)

    if not user:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    username = escape(
        str(user.get("username") or "-")
    )

    role = (
        "مدیر"
        if user.get("role") == "admin"
        else "کاربر"
    )

    last_login = escape(
        str(user.get("last_login_at") or "نامشخص")
    )

    created_at = escape(
        str(user.get("created_at") or "نامشخص")
    )

    body = f"""
    <div class="dashboard-header">
        <div>
            <div class="eyebrow">
                ACCOUNT
            </div>

            <h1>
                پروفایل من
            </h1>

            <p>
                اطلاعات حساب کاربری شما
            </p>
        </div>

        <a
            href="/dashboard"
            class="secondary-btn"
        >
            بازگشت به پنل
        </a>
    </div>

    <div class="profile-card">
        <div class="profile-row">
            <span>نام کاربری</span>
            <strong>{username}</strong>
        </div>

        <div class="profile-row">
            <span>نقش</span>
            <strong>{escape(role)}</strong>
        </div>

        <div class="profile-row">
            <span>تاریخ ثبت‌نام</span>
            <strong>{created_at}</strong>
        </div>

        <div class="profile-row">
            <span>آخرین ورود</span>
            <strong>{last_login}</strong>
        </div>
    </div>
    """

    return make_page(
        body,
        "پروفایل | Nova",
    )


# =========================================================
# Run Directly
# =========================================================

if __name__ == "__main__":

    import threading
    import webbrowser
    import uvicorn

    print()
    print("=" * 55)
    print("Nova Bot Builder")
    print("Web dashboard is starting...")
    print("Open: http://127.0.0.1:8000")
    print("=" * 55)
    print()

    def open_browser():
        webbrowser.open(
            "http://127.0.0.1:8000"
        )

    threading.Timer(
        1.5,
        open_browser,
    ).start()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )