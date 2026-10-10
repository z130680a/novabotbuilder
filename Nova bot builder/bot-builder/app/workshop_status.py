from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


APP_TIMEZONE = ZoneInfo("Asia/Tehran")


# =========================================================
# Digits / Text
# =========================================================

PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹",
    "0123456789",
)

ARABIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789",
)


def normalize_digits(value: str) -> str:
    value = str(value or "")
    value = value.translate(PERSIAN_DIGITS)
    value = value.translate(ARABIC_DIGITS)
    return value


# =========================================================
# Jalali -> Gregorian
# =========================================================

def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """
    تبدیل تاریخ شمسی به میلادی بدون نیاز به پکیج خارجی.
    """

    jy += 1595

    days = (
        -355668
        + (365 * jy)
        + ((jy // 33) * 8)
        + (((jy % 33) + 3) // 4)
        + jd
    )

    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 1) * 30) + 6

    gy = 400 * (days // 146097)
    days %= 146097

    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524

        if days >= 365:
            days += 1

    gy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gd = days + 1

    leap = (
        (gy % 4 == 0 and gy % 100 != 0)
        or (gy % 400 == 0)
    )

    month_lengths = [
        31,
        29 if leap else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]

    gm = 1

    while gd > month_lengths[gm - 1]:
        gd -= month_lengths[gm - 1]
        gm += 1

    return date(gy, gm, gd)


# =========================================================
# Date / Time Parsing
# =========================================================

def parse_event_date(value: str) -> date | None:
    value = normalize_digits(value).strip()

    if not value:
        return None

    value = value.replace("-", "/")
    value = value.replace(".", "/")

    parts = value.split("/")

    if len(parts) != 3:
        return None

    try:
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
    except ValueError:
        return None

    try:
        # تاریخ‌های شمسی معمول پروژه
        if 1200 <= year <= 1600:
            return jalali_to_gregorian(
                year,
                month,
                day,
            )

        # در صورت وارد کردن تاریخ میلادی
        return date(
            year,
            month,
            day,
        )

    except ValueError:
        return None


def parse_event_time(value: str) -> time | None:
    value = normalize_digits(value).strip()

    if not value:
        return None

    try:
        parts = value.split(":")

        if len(parts) < 2:
            return None

        hour = int(parts[0])
        minute = int(parts[1])

        if not (0 <= hour <= 23):
            return None

        if not (0 <= minute <= 59):
            return None

        return time(
            hour=hour,
            minute=minute,
        )

    except ValueError:
        return None


# =========================================================
# Workshop Status
# =========================================================

def get_workshop_status(
    spec: dict,
    now: datetime | None = None,
) -> dict:
    """
    وضعیت فعلی کارگاه را محاسبه می‌کند.

    خروجی:
        code:
            active
            ongoing
            ended
            invalid

        label:
            فعال
            در حال برگزاری
            غیرفعال
            زمان نامعتبر

        can_reserve:
            آیا رزرو جدید مجاز است یا خیر
    """

    event_date_raw = str(
        spec.get("event_date") or ""
    ).strip()

    event_time_raw = str(
        spec.get("event_time") or ""
    ).strip()

    event_end_time_raw = str(
        spec.get("event_end_time") or ""
    ).strip()

    # -----------------------------------------------------
    # بدون تاریخ = فعال
    # -----------------------------------------------------

    if not event_date_raw:
        return {
            "code": "active",
            "label": "فعال",
            "can_reserve": True,
            "message": "زمان برگزاری هنوز تعیین نشده است.",
        }

    event_date = parse_event_date(event_date_raw)

    if event_date is None:
        return {
            "code": "invalid",
            "label": "زمان نامعتبر",
            "can_reserve": False,
            "message": "فرمت تاریخ برگزاری معتبر نیست.",
        }

    if now is None:
        now = datetime.now(APP_TIMEZONE)

    if now.tzinfo is None:
        now = now.replace(
            tzinfo=APP_TIMEZONE
        )

    now = now.astimezone(APP_TIMEZONE)

    # -----------------------------------------------------
    # فقط تاریخ، بدون ساعت
    # -----------------------------------------------------

    event_time = parse_event_time(
        event_time_raw
    )

    if event_time is None:

        if now.date() < event_date:
            return {
                "code": "active",
                "label": "فعال",
                "can_reserve": True,
                "message": "هنوز زمان برگزاری نرسیده است.",
            }

        if now.date() == event_date:
            return {
                "code": "active",
                "label": "فعال",
                "can_reserve": True,
                "message": "کارگاه امروز برگزار می‌شود.",
            }

        return {
            "code": "ended",
            "label": "غیرفعال",
            "can_reserve": False,
            "message": "زمان برگزاری کارگاه گذشته است.",
        }

    # -----------------------------------------------------
    # تاریخ + ساعت شروع
    # -----------------------------------------------------

    start_datetime = datetime.combine(
        event_date,
        event_time,
    ).replace(
        tzinfo=APP_TIMEZONE
    )

    # -----------------------------------------------------
    # ساعت پایان
    # -----------------------------------------------------

    event_end_time = parse_event_time(
        event_end_time_raw
    )

    end_datetime = None

    if event_end_time is not None:
        end_datetime = datetime.combine(
            event_date,
            event_end_time,
        ).replace(
            tzinfo=APP_TIMEZONE
        )

        # اگر پایان از شروع کمتر بود،
        # فرض می‌کنیم کارگاه تا روز بعد ادامه دارد.
        if end_datetime <= start_datetime:
            end_datetime += timedelta(days=1)

    # -----------------------------------------------------
    # قبل از شروع
    # -----------------------------------------------------

    if now < start_datetime:
        return {
            "code": "active",
            "label": "فعال",
            "can_reserve": True,
            "message": "هنوز زمان شروع نرسیده است.",
        }

    # -----------------------------------------------------
    # بعد از شروع و دارای زمان پایان
    # -----------------------------------------------------

    if end_datetime is not None:

        if now < end_datetime:
            return {
                "code": "ongoing",
                "label": "در حال برگزاری",
                "can_reserve": False,
                "message": "کارگاه در حال برگزاری است.",
            }

        return {
            "code": "ended",
            "label": "غیرفعال",
            "can_reserve": False,
            "message": "زمان برگزاری کارگاه تمام شده است.",
        }

    # -----------------------------------------------------
    # شروع شده ولی پایان مشخص نیست
    # -----------------------------------------------------

    return {
        "code": "ongoing",
        "label": "در حال برگزاری",
        "can_reserve": False,
        "message": "زمان شروع گذشته است.",
    }