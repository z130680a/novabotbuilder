import json
import re
from pathlib import Path

try:
    from .schemas import BotSpec
except ImportError:
    from schemas import BotSpec


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "generated_bots" / "bot_config.json"

DEFAULT_FEATURES = [
    "ثبت نام",
    "رزرو",
    "لغو رزرو",
    "نمایش ظرفیت",
    "لیست انتظار",
]


def extract_capacity(text: str) -> int:
    patterns = [
        r"(?:ظرفیت|حداکثر)\s*(?:کارگاه\s*)?(?:برابر\s*با\s*)?[:：]?\s*(\d+)",
        r"(\d+)\s*(?:نفر|شرکت‌کننده)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            if value > 0:
                return value

    return 30


def extract_answer(answers: str, *keywords: str) -> str:
    """پاسخ سؤال‌هایی را که با کلیدواژه مشخص شده‌اند استخراج می‌کند."""
    blocks = re.split(r"(?=سؤال\s*[:：])", answers)

    for block in blocks:
        question_match = re.search(
            r"سؤال\s*[:：]\s*(.*?)(?:\n|$)",
            block,
        )

        answer_match = re.search(
            r"پاسخ\s*[:：]\s*(.*?)(?=\nسؤال\s*[:：]|\Z)",
            block,
            re.DOTALL,
        )

        if not answer_match:
            continue

        question = question_match.group(1).strip() if question_match else ""
        if any(keyword in question.lower() for keyword in keywords):
            return answer_match.group(1).strip()

    return ""


def extract_bot_name(text: str) -> str:
    patterns = [
        r"(?:نام|اسم)\s*(?:بات|ربات|کارگاه)\s*[:：]?\s*[«\"']?([^،\n.!؟\"»']{2,100})",
        r"(?:بات|ربات|کارگاه)\s+(?:به\s+نام|با\s+نام)\s*[«\"']?([^،\n.!؟\"»']{2,100})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name:
                return name[:100]

    # اگر نام مشخص نشده، از نام عمومی قابل‌فهم استفاده کن.
    return "بات رزرو کارگاه"


def extract_date(text: str) -> str:
    patterns = [
        r"(?:تاریخ(?:\s+برگزاری(?:\s+کارگاه)?)?|روز\s+برگزاری)\s*[:：]?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
        r"\b(14\d{2}[/-]\d{1,2}[/-]\d{1,2})\b",
        r"\b(20\d{2}[/-]\d{1,2}[/-]\d{1,2})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace("-", "/")

    return ""


def extract_time(text: str, kind: str) -> str:
    if kind == "start":
        labels = r"(?:ساعت\s*شروع|شروع|از ساعت)"
    else:
        labels = r"(?:ساعت\s*پایان|پایان|تا ساعت)"

    match = re.search(
        labels + r"\s*[:：]?\s*(\d{1,2}:\d{2})",
        text,
    )

    if match:
        hour, minute = map(int, match.group(1).split(":"))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # ساعت‌هایی که به‌تنهایی داخل پاسخ سؤال آمده‌اند.
    if kind == "start":
        match = re.search(
            r"پاسخ\s*[:：]\s*(\d{1,2}:\d{2})",
            text,
        )
        if match:
            hour, minute = map(int, match.group(1).split(":"))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

    return ""


def build_bot(user_request: str, answers: str):
    user_request = (user_request or "").strip()
    answers = (answers or "").strip()

    if not user_request:
        raise ValueError("درخواست ساخت بات خالی است.")

    combined_text = f"{user_request}\n{answers}"

    capacity = extract_capacity(combined_text)
    bot_name = extract_bot_name(user_request)

    # اگر کاربر نام کارگاه را در پاسخ‌ها داده باشد، آن را هم بررسی کن.
    answer_name = extract_answer(
        answers,
        "نام",
        "اسم",
    )
    if answer_name and any(
        word in answer_name.lower()
        for word in ("کارگاه", "بات", "ربات")
    ):
        bot_name = answer_name[:100]

    event_date = extract_date(combined_text)

    event_time = extract_time(combined_text, "start")
    event_end_time = extract_time(combined_text, "end")

    # پاسخ سؤال‌های تاریخ و ساعت را هم بخوان.
    date_answer = extract_answer(
        answers,
        "تاریخ",
        "date",
    )
    if date_answer:
        found_date = extract_date(date_answer)
        if found_date:
            event_date = found_date

    start_answer = extract_answer(
        answers,
        "ساعت شروع",
        "event_time",
        "date/time",
    )
    if start_answer:
        found_time = extract_time(start_answer, "start")
        if found_time:
            event_time = found_time
        else:
            match = re.search(r"\b(\d{1,2}:\d{2})\b", start_answer)
            if match:
                event_time = match.group(1)

    end_answer = extract_answer(
        answers,
        "ساعت پایان",
        "event_end_time",
    )
    if end_answer:
        match = re.search(r"\b(\d{1,2}:\d{2})\b", end_answer)
        if match:
            event_end_time = match.group(1)

    purpose = (
        "بات تلگرام مدیریت ثبت‌نام و رزرو کارگاه.\n"
        f"درخواست کاربر: {user_request}\n"
        f"پاسخ‌های تکمیلی: {answers}"
    )

    spec = {
        "bot_name": bot_name,
        "purpose": purpose,
        "capacity": capacity,
        "features": DEFAULT_FEATURES.copy(),
        "missing_information": [],
        "event_date": event_date,
        "event_time": event_time,
        "event_end_time": event_end_time,
    }

    result = BotSpec.model_validate(spec)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(
            result.model_dump(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return result
