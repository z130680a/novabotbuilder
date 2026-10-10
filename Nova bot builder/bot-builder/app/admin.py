import csv
import io
from html import escape
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)

import os

from auth import (
    authenticate,
    clear_login_cookie,
    get_current_user,
    register_account,
    set_login_cookie,
    list_auth_users,
    count_auth_users,
    create_user,
    update_user_role,
    update_user_password,
    delete_user,
)

from database import (
    get_participants,
    get_workshop_meta,
    get_workshop_participant_stats,
    log_action,
    get_admin_logs,
)

from ip_location import (
    get_client_ip as get_trusted_client_ip,
)

from workshop_store import (
    add_workshop,
    get_workshop,
    load_workshops,
    save_workshops,
    update_workshop,
    delete_workshop,
)


router = APIRouter(
    prefix="/admin"
)


# =========================================================
# Helpers
# =========================================================

def get_client_ip(
    request: Request,
) -> str:
    return get_trusted_client_ip(request)


def redirect_login():
    return RedirectResponse(
        "/admin/login",
        status_code=303,
    )


def require_user(
    request: Request,
):
    user = get_current_user(request)

    if not user:
        return None

    return user


def require_admin(
    request: Request,
):
    user = get_current_user(request)

    if not user:
        return None

    if user["role"] != "admin":
        return False

    return user


def is_workshop_active(
    workshop: dict,
) -> bool:

    return workshop.get(
        "active",
        True,
    ) is not False


def set_workshop_active(
    workshop_id: int,
    active: bool,
) -> bool:

    workshops = load_workshops()

    for workshop in workshops:

        try:
            current_id = int(
                workshop.get("id")
            )
        except (TypeError, ValueError):
            continue

        if current_id != int(workshop_id):
            continue

        workshop["active"] = bool(active)

        save_workshops(
            workshops
        )

        return True

    return False


def can_manage_workshop(
    user: dict[str, Any],
    workshop_id: int,
) -> bool:

    if user["role"] == "admin":
        return True

    workshop = get_workshop(workshop_id)

    if not workshop:
        return False

    owner_user_id = workshop.get("owner_user_id")
    user_id = user.get("id")

    if owner_user_id is None or user_id is None:
        return False

    try:
        return int(owner_user_id) == int(user_id)
    except (TypeError, ValueError):
        return False


def page(
    title: str,
    body: str,
    user: dict[str, Any] | None = None,
) -> HTMLResponse:

    username = (
        escape(user["username"])
        if user
        else ""
    )

    role = (
        "مدیر"
        if user and user["role"] == "admin"
        else "کاربر"
    )

    nav = ""

    if user:
        nav = f"""
        <div class="nav">

            <div>

                <a href="/admin">
                    داشبورد
                </a>

                <a href="/admin/workshops">
                     مدیریت کارگاه‌ها
                </a>

                {
                    "<a href='/admin/users'>مدیریت کاربران</a>"
                    if user["role"] == "admin"
                    else ""
                }

            </div>

            <div>

                <span>
                    {username}
                    ·
                    {role}
                </span>

                <a href="/admin/logout">
                    خروج
                </a>

            </div>

        </div>
        """

    html = f"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">

<head>

    <meta charset="UTF-8">

    <meta
        http-equiv="Content-Type"
        content="text/html; charset=UTF-8"
    >

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>{escape(title)}</title>

    <style>

        * {{
            box-sizing: border-box;
        }}

        html {{
            direction: rtl;
            unicode-bidi: plaintext;
        }}

        body {{
            margin: 0;
            min-height: 100vh;

            background:
                radial-gradient(
                    circle at 10% 10%,
                    rgba(91,140,255,.12),
                    transparent 30%
                ),
                #070b16;

            color: #f8fafc;

            font-family:
                Tahoma,
                Arial,
                sans-serif;

            direction: rtl;

            text-rendering: optimizeLegibility;
        }}

        a {{
            color: inherit;
            text-decoration: none;
        }}

        .container {{
            width: min(
                1180px,
                calc(100% - 28px)
            );

            margin: auto;
            padding: 24px 0 60px;
        }}

        .nav {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;

            margin-bottom: 24px;
            padding: 14px 18px;

            border: 1px solid
                rgba(255,255,255,.08);

            border-radius: 16px;

            background:
                rgba(15,23,42,.84);
        }}

        .nav > div {{
            display: flex;
            align-items: center;
            gap: 15px;

            flex-wrap: wrap;
        }}

        .nav a {{
            color: #cbd5e1;
        }}

        .nav a:hover {{
            color: white;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;

            margin-bottom: 28px;
        }}

        .brand img {{
            width: 48px;
            height: 48px;

            border-radius: 14px;
        }}

        h1 {{
            margin: 0 0 9px;
            font-size: 31px;
        }}

        h2 {{
            margin: 0 0 8px;
            font-size: 21px;
        }}

        p {{
            color: #9ca3af;
            line-height: 2;
        }}

        .grid {{
            display: grid;

            grid-template-columns:
                repeat(4, 1fr);

            gap: 14px;

            margin: 22px 0;
        }}

        .stat {{
            padding: 20px;

            border: 1px solid
                rgba(255,255,255,.08);

            border-radius: 18px;

            background:
                rgba(17,24,39,.82);
        }}

        .stat-label {{
            color: #94a3b8;
            font-size: 12px;
        }}

        .stat-value {{
            margin-top: 10px;

            font-size: 30px;
            font-weight: 800;
        }}

        .card {{
            padding: 22px;

            margin-bottom: 15px;

            border: 1px solid
                rgba(255,255,255,.08);

            border-radius: 20px;

            background:
                rgba(17,24,39,.82);
        }}

        .card-head {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 15px;
        }}

        .muted {{
            color: #7d889c;
            font-size: 12px;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;

            padding: 7px 11px;

            border-radius: 999px;

            font-size: 11px;
        }}

        .active {{
            color: #bbf7d0;

            background:
                rgba(34,197,94,.10);

            border: 1px solid
                rgba(34,197,94,.18);
        }}

        .inactive {{
            color: #fecaca;

            background:
                rgba(239,68,68,.10);

            border: 1px solid
                rgba(239,68,68,.18);
        }}

        .buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 9px;

            margin-top: 18px;
        }}

        .button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;

            padding: 11px 15px;

            border-radius: 12px;

            border: 1px solid
                rgba(255,255,255,.08);

            color: white;

            background:
                rgba(255,255,255,.05);

            cursor: pointer;

            font-family:
                Tahoma,
                Arial,
                sans-serif;
        }}

        .button.primary {{
            background:
                linear-gradient(
                    135deg,
                    #4f7cff,
                    #7658f6
                );

            border: none;
        }}

        .button.danger {{
            color: #fecaca;

            background:
                rgba(239,68,68,.08);

            border-color:
                rgba(239,68,68,.18);
        }}

        form {{
            margin: 0;
        }}

        .form-group {{
            margin-bottom: 15px;
        }}

        label {{
            display: block;
            margin-bottom: 8px;

            font-size: 12px;
            color: #cbd5e1;
        }}

        input {{
            width: 100%;
            height: 46px;

            padding: 0 13px;

            border-radius: 12px;

            border: 1px solid
                rgba(255,255,255,.09);

            outline: none;

            color: white;

            background:
                rgba(255,255,255,.03);

            font-family:
                Tahoma,
                Arial,
                sans-serif;

            direction: rtl;
            text-align: right;
        }}

        textarea,
select {{
    display: block;
    width: 100%;
    padding: 12px 13px;
    margin-bottom: 15px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,.09);
    outline: none;
    color: white;
    background: #111827;
    font-family: Tahoma, Arial, sans-serif;
    font-size: 13px;
    direction: rtl;
    text-align: right;
}}

textarea {{
    min-height: 100px;
    resize: vertical;
    line-height: 1.8;
}}

        select option {{
            color: white;
            background: #111827;
        }}

                .form-group input,
        .form-group textarea,
        .form-group select {{
            margin-bottom: 0;
        }}

        .auth {{
            width: min(
                440px,
                100%
            );

            margin: 70px auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            padding: 12px 10px;

            text-align: right;

            border-bottom: 1px solid
                rgba(255,255,255,.06);

            font-size: 12px;
        }}

        th {{
            color: #94a3b8;
        }}

        .error {{
            padding: 12px 14px;

            margin-bottom: 15px;

            border-radius: 12px;

            color: #fecaca;

            background:
                rgba(239,68,68,.08);

            border: 1px solid
                rgba(239,68,68,.16);
        }}

        @media (
            max-width: 850px
        ) {{
            .grid {{
                grid-template-columns:
                    repeat(2, 1fr);
            }}
        }}

        @media (
            max-width: 560px
        ) {{
            .grid {{
                grid-template-columns: 1fr;
            }}

            .nav {{
                align-items: flex-start;
            }}

            table {{
                display: block;
                overflow-x: auto;
            }}
        }}

    </style>

</head>

<body>

<div class="container">

    <div class="brand">

        <img
            src="/assets/logo.svg"
            alt="Nova"
        >

        <div>

            <strong>
                Nova Bot
            </strong>

            <div class="muted">
                پنل مدیریت
            </div>

        </div>

    </div>

    {nav}

    {body}

</div>

</body>

</html>
"""

    # ارسال قطعی HTML با UTF-8
    response = HTMLResponse(
        content=html.encode("utf-8"),
        media_type="text/html",
    )

    response.headers["Content-Type"] = (
        "text/html; charset=utf-8"
    )

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    return response


# =========================================================
# Register - Disabled
# =========================================================

@router.get("/register")
def register_page():
    return RedirectResponse(
        "/admin/login",
        status_code=303,
    )


@router.post("/register")
def register_submit():
    return RedirectResponse(
        "/admin/login",
        status_code=303,
    )


# =========================================================
# Login
# =========================================================

@router.get(
    "/login",
    response_class=HTMLResponse,
)
def login_page(
    registered: str = "",
    error: str = "",
):

    registered_message = ""

    if registered == "1":

        registered_message = """
        <div
            class="error"
            style="
                color:#bbf7d0;
                background:rgba(34,197,94,.08);
                border-color:rgba(34,197,94,.16);
            "
        >
            ثبت‌نام با موفقیت انجام شد.
            اکنون وارد شوید.
        </div>
        """

    error_message = ""

    if error == "1":

        error_message = """
        <div class="error">
            نام کاربری یا رمز عبور صحیح نیست.
        </div>
        """


    body = f"""
    <div class="auth card">

        <h1>
            ورود به پنل
        </h1>

        <p>
            برای ورود نام کاربری و رمز عبور را وارد کنید.
        </p>

        {registered_message}

        {error_message}

        <form
            method="post"
            action="/admin/login"
        >

            <div class="form-group">

                <label>
                    نام کاربری
                </label>

                <input
                    type="text"
                    name="username"
                    required
                    autocomplete="username"
                >

            </div>

            <div class="form-group">

                <label>
                    رمز عبور
                </label>

                <input
                    type="password"
                    name="password"
                    required
                    autocomplete="current-password"
                >

            </div>

            <button
                class="button primary"
                type="submit"
            >
                ورود
            </button>

        </form>

    """

    return page(
        "ورود | Nova",
        body,
    )

@router.post(
    "/login",
)
def login_submit(
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate(
        username=username.strip(),
        password=password,
    )

    if not user:
        return RedirectResponse(
            "/admin/login?error=1",
            status_code=303,
        )

    response = RedirectResponse(
        "/admin/",
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

@router.get(
    "/logout",
)
def logout():

    response = RedirectResponse(
        "/admin/login",
        status_code=303,
    )

    clear_login_cookie(
        response
    )

    return response


# =========================================================
# Dashboard
# =========================================================

@router.get(
    "",
    response_class=HTMLResponse,
)
@router.get(
    "/",
    response_class=HTMLResponse,
)
def dashboard(
    request: Request,
):

    user = require_user(request)

    if not user:
        return redirect_login()

    workshops = load_workshops()

    if user["role"] != "admin":

        filtered = []

        for workshop in workshops:

            if can_manage_workshop(
                user,
                workshop["id"],
            ):
                filtered.append(
                    workshop
                )

        workshops = filtered

    active_count = sum(
        1
        for workshop in workshops
        if is_workshop_active(workshop)
    )

    participant_count = sum(
        get_workshop_participant_stats(
            workshop["id"]
        )["registered"]
        for workshop in workshops
    )

    cards = []

    for workshop in workshops:

        workshop_id = workshop["id"]

        spec = workshop.get(
            "spec",
            workshop,
        )

        name = escape(
            str(
                spec.get(
                    "bot_name",
                    "کارگاه",
                )
            )
        )

        capacity = spec.get(
            "capacity",
            "-",
        )

        stats = (
            get_workshop_participant_stats(
                workshop_id
            )
        )

        active = is_workshop_active(
            workshop
        )

        meta = get_workshop_meta(
            workshop_id
        )

        creator = (
            meta.get(
                "creator_username",
                "نامشخص",
            )
            if meta
            else "نامشخص"
        )

        ip = (
            meta.get(
                "creator_ip",
                "نامشخص",
            )
            if meta
            else "نامشخص"
        )

        state_class = (
            "active"
            if active
            else "inactive"
        )

        state_text = (
            "فعال"
            if active
            else "غیرفعال"
        )

        cards.append(
            f"""
            <div class="card">

                <div class="card-head">

                    <div>

                        <h2>
                            {name}
                        </h2>

                        <div class="muted">
                            ظرفیت:
                            {escape(str(capacity))}
                            نفر
                        </div>

                    </div>

                    <span class="badge {state_class}">
                        {state_text}
                    </span>

                </div>

                <p>

                    ثبت‌نام:
                    <strong>
                        {stats["registered"]}
                    </strong>
                    /
                    {escape(str(capacity))}

                    <br>

                    لیست انتظار:
                    {stats["waitlist"]}

                    <br>

                    سازنده:
                    {escape(str(creator))}

                    <br>

                    IP ایجاد:
                    {escape(str(ip))}

                </p>

                <div class="buttons">

                    <a
                        class="button primary"
                        href="/admin/workshop/{workshop_id}/participants"
                    >
                        شرکت‌کنندگان
                    </a>

                    <form
                        method="post"
                        action="/admin/workshop/{workshop_id}/toggle"
                    >

                        <button
                            class="button"
                            type="submit"
                        >
                            {
                                "غیرفعال کردن"
                                if active
                                else
                                "فعال کردن"
                            }
                        </button>

                    </form>

                    <a
                        class="button"
                        href="/admin/workshops/{workshop_id}/edit"
                        >
                     ویرایش
                    </a>

                </div>

            </div>
            """
        )

    body = f"""
    <h1>
        داشبورد مدیریت
    </h1>

    <p>
        مدیریت کارگاه‌ها، وضعیت ثبت‌نام و شرکت‌کنندگان.
    </p>

    <div class="grid">

        <div class="stat">

            <div class="stat-label">
                تعداد کارگاه‌ها
            </div>

            <div class="stat-value">
                {len(workshops)}
            </div>

        </div>

        <div class="stat">

            <div class="stat-label">
                کارگاه‌های فعال
            </div>

            <div class="stat-value">
                {active_count}
            </div>

        </div>

        <div class="stat">

            <div class="stat-label">
                ثبت‌نام فعال
            </div>

            <div class="stat-value">
                {participant_count}
            </div>

        </div>

        <div class="stat">

            <div class="stat-label">
                کاربران پنل
            </div>

            <div class="stat-value">
                {count_auth_users()}
            </div>

        </div>

    </div>

    <h2>
        کارگاه‌ها
    </h2>

    {
        ''.join(cards)
        or
        '''
        <div class="card">

            <p>
                هنوز کارگاهی برای این حساب ثبت نشده است.
            </p>

        </div>
        '''
    }
    """

    return page(
        "داشبورد | Nova",
        body,
        user,
    )


# =========================================================
# Participants
# =========================================================

@router.get(
    "/workshop/{workshop_id}/participants",
    response_class=HTMLResponse,
)
def participants_page(
    workshop_id: int,
    request: Request,
):

    user = require_user(request)

    if not user:
        return redirect_login()

    workshop = get_workshop(
        workshop_id
    )

    if not workshop:

        return HTMLResponse(
            "کارگاه پیدا نشد.",
            status_code=404,
        )

    if not can_manage_workshop(
        user,
        workshop_id,
    ):

        return HTMLResponse(
            "دسترسی غیرمجاز.",
            status_code=403,
        )

    spec = workshop.get(
        "spec",
        workshop,
    )

    name = escape(
        str(
            spec.get(
                "bot_name",
                "کارگاه",
            )
        )
    )

    capacity = spec.get(
        "capacity",
        "-",
    )

    stats = get_workshop_participant_stats(
        workshop_id
    )

    participants = get_participants(
        workshop_id
    )

    rows = []

    for item in participants:

        full_name = " ".join(
            x
            for x in [
                item.get("first_name"),
                item.get("last_name"),
            ]
            if x
        ).strip()

        if not full_name:
            full_name = "-"

        username = (
            item.get("username")
            or "-"
        )

        status_map = {
            "registered": "ثبت‌نام قطعی",
            "waitlist": "لیست انتظار",
            "cancelled": "لغوشده",
        }

        status = status_map.get(
            item.get("status"),
            item.get("status"),
        )

        rows.append(
            f"""
            <tr>

                <td>
                    {escape(full_name)}
                </td>

                <td>
                    {escape(str(username))}
                </td>

                <td>
                    {escape(
                        str(
                            item.get(
                                "telegram_user_id"
                            )
                        )
                    )}
                </td>

                <td>
                    {escape(
                        str(
                            item.get("phone")
                            or "-"
                        )
                    )}
                </td>

                <td>
                    {escape(str(status))}
                </td>

                <td>
                    {escape(
                        str(
                            item.get(
                                "reserved_at"
                            )
                            or
                            item.get(
                                "waitlisted_at"
                            )
                            or
                            item.get(
                                "cancelled_at"
                            )
                            or
                            "-"
                        )
                    )}
                </td>

            </tr>
            """
        )

    body = f"""
    <h1>
        {name}
    </h1>

    <p>

        ظرفیت:
        {escape(str(capacity))}
        نفر

        ·

        ثبت‌نام:
        {stats["registered"]}

        ·

        انتظار:
        {stats["waitlist"]}

        ·

        لغوشده:
        {stats["cancelled"]}

    </p>

    <div class="buttons">

        <a
            class="button"
            href="/admin"
        >
            ← داشبورد
        </a>

        <a
            class="button primary"
            href="/admin/workshop/{workshop_id}/export.csv"
        >
            خروجی اکسل
        </a>

    </div>

    <div class="card">

        <table>

            <thead>

                <tr>

                    <th>
                        نام
                    </th>

                    <th>
                        Username
                    </th>

                    <th>
                        Telegram ID
                    </th>

                    <th>
                        شماره
                    </th>

                    <th>
                        وضعیت
                    </th>

                    <th>
                        زمان
                    </th>

                </tr>

            </thead>

            <tbody>

                {
                    ''.join(rows)
                    or
                    '''
                    <tr>

                        <td colspan="6">
                            هنوز شرکت‌کننده‌ای ثبت نشده است.
                        </td>

                    </tr>
                    '''
                }

            </tbody>

        </table>

    </div>
    """

    return page(
        f"شرکت‌کنندگان | {name}",
        body,
        user,
    )


# =========================================================
# CSV export
# =========================================================

@router.get(
    "/workshop/{workshop_id}/export.csv",
)
def export_participants(
    workshop_id: int,
    request: Request,
):

    user = require_user(request)

    if not user:
        return redirect_login()

    if not can_manage_workshop(
        user,
        workshop_id,
    ):

        return HTMLResponse(
            "دسترسی غیرمجاز.",
            status_code=403,
        )

    participants = get_participants(
        workshop_id
    )

    output = io.StringIO(
        newline=""
    )

    writer = csv.writer(
        output
    )

    writer.writerow(
        [
            "name",
            "username",
            "telegram_user_id",
            "phone",
            "status",
            "reserved_at",
            "waitlisted_at",
            "cancelled_at",
        ]
    )

    for item in participants:

        name = " ".join(
            x
            for x in [
                item.get("first_name"),
                item.get("last_name"),
            ]
            if x
        )

        writer.writerow(
            [
                name,
                item.get("username") or "",
                item.get("telegram_user_id") or "",
                item.get("phone") or "",
                item.get("status") or "",
                item.get("reserved_at") or "",
                item.get("waitlisted_at") or "",
                item.get("cancelled_at") or "",
            ]
        )

    content = (
        "\ufeff"
        + output.getvalue()
    ).encode(
        "utf-8-sig"
    )

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="workshop_{workshop_id}_participants.csv"'
        },
    )


# =========================================================
# Toggle active / inactive
# =========================================================

@router.post(
    "/workshop/{workshop_id}/toggle",
)
def toggle_workshop(
    workshop_id: int,
    request: Request,
):

    user = require_user(request)

    if not user:
        return redirect_login()

    if not can_manage_workshop(
        user,
        workshop_id,
    ):

        return HTMLResponse(
            "دسترسی غیرمجاز.",
            status_code=403,
        )

    workshop = get_workshop(
        workshop_id
    )

    if not workshop:

        return HTMLResponse(
            "کارگاه پیدا نشد.",
            status_code=404,
        )

    new_state = not is_workshop_active(
        workshop
    )

    set_workshop_active(
        workshop_id,
        new_state,
    )

    log_action(
        user=user,
        action=(
            "workshop_activated"
            if new_state
            else
            "workshop_deactivated"
        ),
        workshop_id=workshop_id,
        ip=get_client_ip(request),
    )

    return RedirectResponse(
        "/admin",
        status_code=303,
    )



# =========================================================
# Workshops - Admin
# =========================================================

def _workshop_admin_form(actor, workshop=None, error=""):
    is_edit = workshop is not None

    if is_edit:
        raw_spec = workshop.get("spec")
        spec = raw_spec if isinstance(raw_spec, dict) else workshop
        workshop_id = int(workshop["id"])
        action = f"/admin/workshops/{workshop_id}/edit"
        heading = "ویرایش کارگاه"
        submit_label = "ذخیره تغییرات"
    else:
        spec = {}
        workshop_id = None
        action = "/admin/workshops/create"
        heading = "افزودن کارگاه جدید"
        submit_label = "ساخت کارگاه"

    def val(key, default=""):
        value = spec.get(key, default)
        if value is None:
            value = default
        return escape(str(value), quote=True)

    name = val(
        "bot_name",
        workshop.get("bot_name", "") if is_edit else "",
    )
    purpose = val(
        "purpose",
        workshop.get("purpose", "") if is_edit else "",
    )
    capacity = val(
        "capacity",
        workshop.get("capacity", 1) if is_edit else 1,
    )
    event_date = val("event_date")
    event_time = val("event_time")
    event_end_time = val("event_end_time")

    features = spec.get(
        "features",
        workshop.get("features", []) if is_edit else [],
    )
    if not isinstance(features, list):
        features = []

    features_text = escape("\n".join(
        str(item) for item in features
    ))

    users = list_auth_users()
    current_owner = (
        str(workshop.get("owner_user_id", ""))
        if is_edit else ""
    )

    owner_options = []
    for user in users:
        user_id = str(user.get("id", ""))
        username = str(user.get("username", "نامشخص"))
        selected = " selected" if user_id == current_owner else ""

        owner_options.append(
            f'<option value="{escape(user_id, quote=True)}"'
            f'{selected}>'
            f'{escape(username)} (شناسه {escape(user_id)})'
            f'</option>'
        )

    error_html = (
        f'<p style="color:#dc2626">{escape(error)}</p>'
        if error else ""
    )

    back_link = (
        '<p><a href="/admin/workshops">بازگشت به فهرست کارگاه‌ها</a></p>'
    )

    body = f"""
        <h1>{heading}</h1>
        {error_html}

        <div class="card">
            <form method="post" action="{action}">
                <label>نام کارگاه</label>
                <input
                    type="text"
                    name="bot_name"
                    value="{name}"
                    required
                    maxlength="200"
                >

                <label>توضیحات و هدف کارگاه</label>
                <textarea
                    name="purpose"
                    rows="4"
                    required
                >{purpose}</textarea>

                <label>ظرفیت</label>
                <input
                    type="number"
                    name="capacity"
                    value="{capacity}"
                    min="1"
                    required
                >

                <label>امکانات کارگاه</label>
                <textarea
                    name="features"
                    rows="5"
                    placeholder="هر امکان را در یک خط وارد کنید"
                >{features_text}</textarea>

                <label>تاریخ برگزاری</label>
                <input
                    type="text"
                    name="event_date"
                    value="{event_date}"
                    placeholder="مثلاً 1405/07/16"
                >

                <label>ساعت شروع</label>
                <input
                    type="text"
                    name="event_time"
                    value="{event_time}"
                    placeholder="مثلاً 10:00"
                >

                <label>ساعت پایان</label>
                <input
                    type="text"
                    name="event_end_time"
                    value="{event_end_time}"
                    placeholder="مثلاً 12:00"
                >

                <label>مالک کارگاه</label>
                <select name="owner_user_id" required>
                    <option value="">انتخاب کاربر</option>
                    {''.join(owner_options)}
                </select>

                <button type="submit" class="button primary">
                  {submit_label}
                </button>

            </form>
            {back_link}
        </div>
    """

    title = (
        f"ویرایش کارگاه {workshop_id} | Nova"
        if is_edit else "افزودن کارگاه | Nova"
    )
    return page(title, body, actor)


@router.get(
    "/workshops",
    response_class=HTMLResponse,
)
def manage_workshops_page(request: Request):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse(
            "دسترسی غیرمجاز.",
            status_code=403,
        )

    users_by_id = {
        str(user["id"]): user
        for user in list_auth_users()
    }

    workshops = load_workshops()
    rows = []

    for workshop in workshops:
        workshop_id = workshop.get("id", "-")
        spec = workshop.get("spec")
        if not isinstance(spec, dict):
            spec = {}

        name = (
            workshop.get("bot_name")
            or spec.get("bot_name")
            or workshop.get("name")
            or f"کارگاه شماره {workshop_id}"
        )

        owner_id = workshop.get("owner_user_id")
        owner = (
            users_by_id.get(str(owner_id))
            if owner_id is not None else None
        )
        username = (
            owner.get("username", "نامشخص")
            if owner else "نامشخص"
        )

        safe_id = escape(str(workshop_id))

       
        rows.append(f"""
            <tr>
                <td>{escape(str(workshop_id))}</td>
                <td>{escape(str(name))}</td>
                <td>{escape(str(username))}</td>
                <td>{escape(str(owner_id if owner_id is not None else "-"))}</td>
                <td>
                    <div class="buttons" style="margin-top:0">
                        <a
                            href="/admin/workshops/{safe_id}/edit"
                            class="button"
                        >ویرایش</a>

                        <form
                            method="post"
                            action="/admin/workshops/{safe_id}/delete"
                            style="display:inline; margin:0"
                            onsubmit="return confirm('از حذف این کارگاه مطمئن هستید؟');"
                        >
                            <button type="submit" class="button danger">
                                حذف
                            </button>
                        </form>
                    </div>
                </td>
            </tr>
        """)

    body = f"""
        <h1>مدیریت کارگاه‌ها</h1>
        <p>مشاهده، ساخت، ویرایش و حذف کارگاه‌ها.</p>

        <a href="/admin/workshops/new" class="button primary">
    + افزودن کارگاه جدید
        </a>

        <div class="card" style="overflow-x:auto">
            <p>
                تعداد کل کارگاه‌ها:
                <strong>{len(workshops)}</strong>
            </p>

            <table>
                <thead>
                    <tr>
                        <th>شناسه</th>
                        <th>نام کارگاه</th>
                        <th>مالک</th>
                        <th>شناسه مالک</th>
                        <th>عملیات</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows) or '''
                        <tr>
                            <td colspan="5">
                                هنوز کارگاهی ثبت نشده است.
                            </td>
                        </tr>
                    '''}
                </tbody>
            </table>
        </div>
    """

    return page(
        "مدیریت کارگاه‌ها | Nova",
        body,
        actor,
    )


@router.get(
    "/workshops/new",
    response_class=HTMLResponse,
)
def new_workshop_page(request: Request):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    return _workshop_admin_form(actor)


@router.post("/workshops/create")
def create_workshop_admin(
    request: Request,
    bot_name: str = Form(""),
    purpose: str = Form(""),
    capacity: str = Form(""),
    features: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    event_end_time: str = Form(""),
    owner_user_id: str = Form(""),
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    try:
        capacity_value = int(capacity)
    except (TypeError, ValueError):
        return _workshop_admin_form(
            actor, error="ظرفیت باید یک عدد صحیح باشد."
        )

    if not bot_name.strip() or not purpose.strip():
        return _workshop_admin_form(
            actor, error="نام و توضیحات کارگاه الزامی است."
        )

    if capacity_value < 1:
        return _workshop_admin_form(
            actor, error="ظرفیت باید حداقل یک نفر باشد."
        )

    valid_owner_ids = {
        str(user.get("id"))
        for user in list_auth_users()
    }

    if owner_user_id not in valid_owner_ids:
        return _workshop_admin_form(
            actor, error="مالک انتخاب‌شده معتبر نیست."
        )

    feature_list = [
        item.strip()
        for line in features.splitlines()
        for item in line.split(",")
        if item.strip()
    ]

    spec = {
        "bot_name": bot_name.strip(),
        "purpose": purpose.strip(),
        "capacity": capacity_value,
        "features": feature_list,
        "missing_information": [],
        "event_date": event_date.strip(),
        "event_time": event_time.strip(),
        "event_end_time": event_end_time.strip(),
    }

    created = add_workshop(
        {**spec, "spec": spec},
        owner_user_id=int(owner_user_id),
    )

    log_action(
        actor,
        "workshop_created",
        workshop_id=int(created["id"]),
        details=f"ساخت کارگاه: {spec['bot_name']}",
    )

    return RedirectResponse(
        "/admin/workshops",
        status_code=303,
    )


@router.get(
    "/workshops/{workshop_id}/edit",
    response_class=HTMLResponse,
)
def edit_workshop_page(
    request: Request,
    workshop_id: int,
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    workshop = get_workshop(workshop_id)

    if workshop is None:
        return HTMLResponse(
            "کارگاه موردنظر پیدا نشد.",
            status_code=404,
        )

    return _workshop_admin_form(actor, workshop=workshop)


@router.post("/workshops/{workshop_id}/edit")
def update_workshop_admin(
    request: Request,
    workshop_id: int,
    bot_name: str = Form(""),
    purpose: str = Form(""),
    capacity: str = Form(""),
    features: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    event_end_time: str = Form(""),
    owner_user_id: str = Form(""),
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    workshop = get_workshop(workshop_id)

    if workshop is None:
        return HTMLResponse(
            "کارگاه موردنظر پیدا نشد.",
            status_code=404,
        )

    try:
        capacity_value = int(capacity)
    except (TypeError, ValueError):
        return _workshop_admin_form(
            actor,
            workshop=workshop,
            error="ظرفیت باید یک عدد صحیح باشد.",
        )

    if not bot_name.strip() or not purpose.strip():
        return _workshop_admin_form(
            actor,
            workshop=workshop,
            error="نام و توضیحات کارگاه الزامی است.",
        )

    if capacity_value < 1:
        return _workshop_admin_form(
            actor,
            workshop=workshop,
            error="ظرفیت باید حداقل یک نفر باشد.",
        )

    valid_owner_ids = {
        str(user.get("id"))
        for user in list_auth_users()
    }

    if owner_user_id not in valid_owner_ids:
        return _workshop_admin_form(
            actor,
            workshop=workshop,
            error="مالک انتخاب‌شده معتبر نیست.",
        )

    feature_list = [
        item.strip()
        for line in features.splitlines()
        for item in line.split(",")
        if item.strip()
    ]

    old_spec = workshop.get("spec")
    if not isinstance(old_spec, dict):
        old_spec = {}

    # فیلدهای ناشناخته و اطلاعات تکمیلی قبلی حفظ می‌شوند.
    spec = dict(old_spec)
    spec.update({
        "bot_name": bot_name.strip(),
        "purpose": purpose.strip(),
        "capacity": capacity_value,
        "features": feature_list,
        "event_date": event_date.strip(),
        "event_time": event_time.strip(),
        "event_end_time": event_end_time.strip(),
    })

    if "missing_information" not in spec:
        spec["missing_information"] = workshop.get(
            "missing_information", []
        )

    update_workshop(
        workshop_id,
        {**spec, "spec": spec},
    )

    # تغییر مالک فقط از طریق انتخاب صریح مدیر انجام می‌شود.
    all_workshops = load_workshops()
    for item in all_workshops:
        if int(item.get("id", 0)) == workshop_id:
            item["owner_user_id"] = int(owner_user_id)
            break
    save_workshops(all_workshops)

    log_action(
        actor,
        "workshop_updated",
        workshop_id=workshop_id,
        details=f"ویرایش کارگاه: {spec['bot_name']}",
    )

    return RedirectResponse(
        "/admin/workshops",
        status_code=303,
    )


@router.post("/workshops/{workshop_id}/delete")
def delete_workshop_admin(
    request: Request,
    workshop_id: int,
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    workshop = get_workshop(workshop_id)

    if workshop is None:
        return HTMLResponse(
            "کارگاه موردنظر پیدا نشد.",
            status_code=404,
        )

    name = (
        workshop.get("bot_name")
        or f"کارگاه شماره {workshop_id}"
    )

    deleted = delete_workshop(workshop_id)

    if not deleted:
        return HTMLResponse(
            "حذف کارگاه انجام نشد.",
            status_code=500,
        )

    log_action(
        actor,
        "workshop_deleted",
        workshop_id=workshop_id,
        details=f"حذف کارگاه: {name}",
    )

    return RedirectResponse(
        "/admin/workshops",
        status_code=303,
    )

# =========================================================
# Users
# =========================================================

@router.get(
    "/users",
    response_class=HTMLResponse,
)
def users_page(
    request: Request,
):
    user = require_admin(request)

    if user is None:
        return redirect_login()

    if user is False:
        return HTMLResponse(
            "دسترسی غیرمجاز.",
            status_code=403,
        )

    users = list_auth_users()
    logs = get_admin_logs(limit=500)

    action_labels = {
        "workshop_created": "ساخت کارگاه",
        "workshop_updated": "ویرایش کارگاه",
        "workshop_deleted": "حذف کارگاه",
        "workshop_activated": "فعال‌سازی کارگاه",
        "workshop_deactivated": "غیرفعال‌سازی کارگاه",
    }

    # گزارش‌ها به ترتیب جدیدترین رکورد مرتب شده‌اند.
    # بنابراین اولین رکورد هر کاربر، آخرین اقدام اوست.
    latest_activity = {}

    for entry in logs:
        username = str(
            entry.get("username") or ""
        ).strip()

        if username and username not in latest_activity:
            latest_activity[username] = entry

    rows = []

    for item in users:
        username = str(
            item.get("username") or "-"
        )

        role = (
            "مدیر"
            if item.get("role") == "admin"
            else "کاربر"
        )

        location_parts = [
            str(item.get("city") or "").strip(),
            str(item.get("region") or "").strip(),
            str(item.get("country") or "").strip(),
        ]

        location = "، ".join(
            part
            for part in location_parts
            if part
        ) or "نامشخص"

        activity = latest_activity.get(username)

        if activity:
            raw_action = str(
                activity.get("action") or ""
            )

            last_action = action_labels.get(
                raw_action,
                raw_action or "نامشخص",
            )

            action_time = str(
                activity.get("created_at") or "-"
            )

            action_ip = str(
                activity.get("ip") or "-"
            )
        else:
            last_action = "اقدامی ثبت نشده است"
            action_time = "-"
            action_ip = "-"

        last_login = str(
            item.get("last_login_at") or "-"
        )

        last_ip = str(
            item.get("last_ip") or "-"
        )

        created_at = str(
            item.get("created_at") or "-"
        )

        rows.append(
            f"""
            <tr>
                <td>
                    {escape(username)}
                </td>

                <td>
                    {escape(role)}
                </td>

                <td>
                    {escape(created_at)}
                </td>

                <td>
                    {escape(last_login)}
                </td>

                <td>
                    {escape(last_ip)}
                </td>

                <td>
                    {escape(location)}
                </td>

                <td>
                    {escape(last_action)}
                </td>

                <td>
                    {escape(action_time)}
                </td>

                <td>
                    {escape(action_ip)}
                </td>
            </tr>
            """
        )

    body = f"""
    <h1>
        کاربران و فعالیت‌ها
    </h1>

    <p>
        اطلاعات ورود، موقعیت تقریبی و آخرین
        اقدامات ثبت‌شده کاربران.
    </p>

    <p class="muted">
        موقعیت مکانی از روی IP تخمین زده می‌شود
        و ممکن است دقیق نباشد. این اطلاعات
        موقعیت لحظه‌ای GPS نیست.
        اقدامات نمایش‌داده‌شده نیز فقط اقداماتی
        هستند که برنامه ثبت کرده است.
    </p>

    <div class="card">
        <table>
            <thead>
                <tr>
                    <th>نام کاربری</th>
                    <th>نقش</th>
                    <th>تاریخ ثبت‌نام</th>
                    <th>آخرین ورود</th>
                    <th>IP آخرین ورود</th>
                    <th>موقعیت تقریبی</th>
                    <th>آخرین اقدام ثبت‌شده</th>
                    <th>زمان اقدام</th>
                    <th>IP اقدام</th>
                </tr>
            </thead>

            <tbody>
                {
                    ''.join(rows)
                    or '''
                    <tr>
                        <td colspan="9">
                            هنوز کاربری ثبت نشده است.
                        </td>
                    </tr>
                    '''
                }
            </tbody>
        </table>
    </div>
    """

    return page(
        "کاربران و فعالیت‌ها | Nova",
        body,
        user,
    )


# =========================================================
# User account management
# =========================================================

def user_management_error(request: Request, message: str):
    user = require_admin(request)

    if user is None:
        return redirect_login()

    if user is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    body = f"""
    <div class="card">
        <h2>عملیات انجام نشد</h2>
        <p>{escape(message)}</p>
        <a class="button primary" href="/admin/users/manage">
            بازگشت به مدیریت کاربران
        </a>
    </div>
    """
    return page("خطا | مدیریت کاربران", body, user)


@router.get("/users/manage", response_class=HTMLResponse)
def manage_users_page(request: Request):
    user = require_admin(request)

    if user is None:
        return redirect_login()

    if user is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    users = list_auth_users()
    rows = []

    for item in users:
        uid = int(item["id"])
        username = str(item.get("username") or "")
        role = str(item.get("role") or "user")
        role_label = "مدیر" if role == "admin" else "کاربر"

        rows.append(f"""
        <tr>
            <td>{uid}</td>
            <td>{escape(username)}</td>
            <td>{role_label}</td>
            <td>{escape(str(item.get("created_at") or "-"))}</td>
            <td>{escape(str(item.get("last_login_at") or "-"))}</td>
            <td>{escape(str(item.get("last_ip") or "-"))}</td>
            <td>
                <form method="post"
                      action="/admin/users/{uid}/role"
                      class="user-action-form">
                    <select name="role" required>
                        <option value="user" {"selected" if role == "user" else ""}>
                            کاربر
                        </option>
                        <option value="admin" {"selected" if role == "admin" else ""}>
                            مدیر
                        </option>
                    </select>
                    <button class="button" type="submit">تغییر نقش</button>
                </form>

                <form method="post"
                      action="/admin/users/{uid}/password"
                      class="user-action-form">
                    <input type="password"
                           name="password"
                           minlength="8"
                           placeholder="رمز جدید"
                           autocomplete="new-password"
                           required>
                    <button class="button" type="submit">تغییر رمز</button>
                </form>

                <form method="post"
                      action="/admin/users/{uid}/delete"
                      onsubmit="return confirm('حذف این حساب قطعی است؟');">
                    <button class="button danger" type="submit">حذف حساب</button>
                </form>
            </td>
        </tr>
        """)

    body = f"""
    <h1>مدیریت حساب‌های کاربری</h1>
    <p>ساخت حساب، تغییر نقش، تغییر رمز عبور و حذف حساب‌ها.</p>

    <div class="card">
        <h2>ساخت حساب جدید</h2>
        <form method="post" action="/admin/users/create">
            <div class="form-group">
                <label>نام کاربری</label>
                <input name="username" minlength="3" maxlength="32"
                       autocomplete="off" required>
            </div>
            <div class="form-group">
                <label>رمز عبور (حداقل ۸ کاراکتر)</label>
                <input type="password" name="password" minlength="8"
                       autocomplete="new-password" required>
            </div>
            <div class="form-group">
                <label>نقش حساب</label>
                <select name="role">
                    <option value="user">کاربر</option>
                    <option value="admin">مدیر</option>
                </select>
            </div>
            <button class="button primary" type="submit">ساخت حساب</button>
        </form>
    </div>

    <div class="card" style="overflow-x:auto">
        <h2>حساب‌های ثبت‌شده ({len(users)})</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>نام کاربری</th>
                    <th>نقش</th>
                    <th>تاریخ ثبت‌نام</th>
                    <th>آخرین ورود</th>
                    <th>IP آخرین ورود</th>
                    <th>عملیات</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows) or '<tr><td colspan="7">کاربری وجود ندارد.</td></tr>'}
            </tbody>
        </table>
    </div>

    <p><a class="button" href="/admin/users">بازگشت به گزارش فعالیت‌ها</a></p>
    """

    return page("مدیریت حساب‌ها | Nova", body, user)


@router.post("/users/create")
def create_managed_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    try:
        if role not in {"user", "admin"}:
            raise ValueError("نقش انتخاب‌شده معتبر نیست.")

        new_id = create_user(username, password, role)

        log_action(
            user=actor,
            action="user_created",
            ip=get_client_ip(request),
            details=f"Created account id={new_id}, username={username.strip()}, role={role}",
        )

    except (ValueError, Exception) as exc:
        return user_management_error(request, str(exc))

    return RedirectResponse("/admin/users/manage", status_code=303)


@router.post("/users/{user_id}/role")
def change_managed_user_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    try:
        if role not in {"user", "admin"}:
            raise ValueError("نقش انتخاب‌شده معتبر نیست.")

        target = next(
            (item for item in list_auth_users()
             if int(item["id"]) == user_id),
            None,
        )

        if target is None:
            raise ValueError("کاربر پیدا نشد.")

        if user_id == int(actor["id"]) and role != "admin":
            raise ValueError("نمی‌توانی نقش حساب مدیر فعلی را از این صفحه کاهش دهی.")

        if target.get("role") == "admin" and role != "admin":
            admin_count = sum(
                1 for item in list_auth_users()
                if item.get("role") == "admin"
            )
            if admin_count <= 1:
                raise ValueError("تغییر نقش آخرین مدیر سیستم مجاز نیست.")

        update_user_role(user_id, role)

        log_action(
            user=actor,
            action="user_role_changed",
            ip=get_client_ip(request),
            details=f"Changed role for user id={user_id} to {role}",
        )

    except Exception as exc:
        return user_management_error(request, str(exc))

    return RedirectResponse("/admin/users/manage", status_code=303)


@router.post("/users/{user_id}/password")
def change_managed_user_password(
    request: Request,
    user_id: int,
    password: str = Form(...),
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    try:
        if not any(int(item["id"]) == user_id for item in list_auth_users()):
            raise ValueError("کاربر پیدا نشد.")

        update_user_password(user_id, password)

        log_action(
            user=actor,
            action="user_password_changed",
            ip=get_client_ip(request),
            details=f"Changed password for user id={user_id}",
        )

    except Exception as exc:
        return user_management_error(request, str(exc))

    return RedirectResponse("/admin/users/manage", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_managed_user(
    request: Request,
    user_id: int,
):
    actor = require_admin(request)

    if actor is None:
        return redirect_login()

    if actor is False:
        return HTMLResponse("دسترسی غیرمجاز.", status_code=403)

    try:
        if user_id == int(actor["id"]):
            raise ValueError("نمی‌توانی حسابی را که با آن وارد شده‌ای حذف کنی.")

        target = next(
            (item for item in list_auth_users()
             if int(item["id"]) == user_id),
            None,
        )

        if target is None:
            raise ValueError("کاربر پیدا نشد.")

        target_username = str(target.get("username") or "")
        delete_user(user_id)

        log_action(
            user=actor,
            action="user_deleted",
            ip=get_client_ip(request),
            details=f"Deleted account id={user_id}, username={target_username}",
        )

    except Exception as exc:
        return user_management_error(request, str(exc))

    return RedirectResponse("/admin/users/manage", status_code=303)