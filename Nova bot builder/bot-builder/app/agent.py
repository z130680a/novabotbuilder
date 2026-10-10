
import json
import re
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END

try:
    from .llm import llm
    from .schemas import BotSpec
except ImportError:
    from llm import llm
    from schemas import BotSpec


class AgentState(TypedDict):
    user_request: str
    bot_spec: Optional[dict]
    response: str


DEFAULT_FEATURES = [
    "ثبت نام",
    "رزرو",
    "لغو رزرو",
    "نمایش ظرفیت",
    "لیست انتظار",
]


def fallback_spec(user_request: str) -> dict:
    """ساخت مشخصات اولیه بدون وابستگی به سرویس هوش مصنوعی."""

    request = user_request.strip()
    lower_request = request.lower()

    # استخراج ظرفیت در صورت ذکر آن در درخواست
    capacity = 30
    capacity_match = re.search(
        r"(?:ظرفیت|حداکثر|تعداد\s*(?:نفر|شرکت‌کننده))"
        r"\s*(?:کارگاه\s*)?(?:برابر\s*با\s*)?"
        r"\s*[:：]?\s*(\d+)",
        request,
    )

    if capacity_match:
        capacity = max(1, int(capacity_match.group(1)))
    else:
        reverse_match = re.search(
            r"(\d+)\s*(?:نفر|شرکت‌کننده)",
            request,
        )
        if reverse_match:
            capacity = max(1, int(reverse_match.group(1)))

    # استخراج نام احتمالی کارگاه
    name_match = re.search(
        r"(?:نام\s*(?:بات|ربات|کارگاه)|"
        r"(?:بات|ربات)\s+(?:به\s+نام|با\s+نام))"
        r"\s*[:：]?\s*[«\"']?([^،\n.!؟\"»']{2,100})",
        request,
        re.IGNORECASE,
    )

    bot_name = (
        name_match.group(1).strip()
        if name_match
        else "بات رزرو کارگاه"
    )

    questions = []

    # فقط اطلاعاتی را بپرس که در متن مشخص نیستند.
    has_date = bool(
        re.search(
            r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"
            r"|امروز|فردا|پس‌فردا|"
            r"شنبه|یکشنبه|دوشنبه|سه‌شنبه|"
            r"چهارشنبه|پنجشنبه|جمعه",
            request,
        )
    )

    has_time = bool(
        re.search(
            r"\b\d{1,2}[:٫]\d{2}\b"
            r"|\bساعت\s*\d{1,2}\b",
            request,
        )
    )

    if not has_date:
        questions.append("تاریخ برگزاری کارگاه چیست؟")

    if not has_time:
        questions.append("ساعت شروع کارگاه چه زمانی است؟")

    if not capacity_match and not re.search(
        r"\d+\s*نفر",
        request,
    ):
        questions.append("ظرفیت کارگاه چند نفر است؟")

    if not re.search(
        r"لغو\s*(?:رزرو|ثبت.?نام)|"
        r"قانون\s*لغو|"
        r"استرداد",
        lower_request,
    ):
        questions.append(
            "آیا شرکت‌کننده می‌تواند رزرو خود را لغو کند؟"
        )

    if not re.search(
        r"لیست\s*انتظار|صف\s*انتظار|جایگزین",
        request,
    ):
        questions.append(
            "اگر ظرفیت تکمیل شد، لیست انتظار فعال باشد؟"
        )

    spec = {
        "bot_name": bot_name,
        "purpose": (
            "بات تلگرام برای ثبت‌نام و مدیریت رزرو کارگاه. "
            f"درخواست کاربر: {request[:1000]}"
        ),
        "capacity": capacity,
        "features": DEFAULT_FEATURES.copy(),
        "missing_information": questions[:5],
        "event_date": "",
        "event_time": "",
        "event_end_time": "",
    }

    return BotSpec.model_validate(spec).model_dump()


def parse_model_output(content) -> dict:
    """استخراج و اعتبارسنجی JSON خروجی مدل."""

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        content = "\n".join(parts)

    if not isinstance(content, str) or not content.strip():
        raise ValueError("خروجی مدل خالی یا غیرمتنی است.")

    text = content.strip()

    # حذف حصار Markdown در صورت وجود
    text = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s*```\s*$", "", text)

    # ابتدا JSON کامل؛ سپس تلاش برای یافتن شیء JSON داخل متن
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("مدل JSON معتبر برنگرداند.")
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("خروجی مدل باید یک شیء JSON باشد.")

    return BotSpec.model_validate(data).model_dump()


def analyze_request(state: AgentState):
    user_request = state["user_request"].strip()

    if not user_request:
        raise ValueError("لطفاً درخواست ساخت بات را وارد کنید.")

    prompt = f"""
تو تحلیلگر درخواست ساخت بات تلگرام برای رزرو کارگاه هستی.

درخواست کاربر:
{user_request}

قابلیت‌های نسخه اول:
- ثبت نام
- رزرو
- لغو رزرو
- نمایش ظرفیت
- لیست انتظار

قوانین:
- اطلاعاتی را که کاربر گفته دوباره نپرس.
- حداکثر ۵ سؤال کوتاه درباره اطلاعات واقعاً نامشخص بپرس.
- سؤال فنی درباره کدنویسی، سرور، API یا دیتابیس نپرس.
- ظرفیت را از متن استخراج کن؛ اگر نامشخص بود، مقدار موقت ۳۰ بگذار
  و درباره ظرفیت سؤال کن.
- اگر تاریخ یا ساعت نامشخص بود، درباره آن سؤال کن.
- نام مناسب برای بات انتخاب کن اگر نامی ارائه نشده است.
- فقط JSON معتبر برگردان؛ بدون Markdown یا توضیح اضافی.

ساختار:
{{
  "bot_name": "نام بات",
  "purpose": "هدف بات",
  "capacity": 30,
  "features": ["ثبت نام", "رزرو", "لغو رزرو",
               "نمایش ظرفیت", "لیست انتظار"],
  "missing_information": []
}}
"""

    try:
        result = llm.invoke(prompt)
        spec = parse_model_output(result.content)

        return {
            "bot_spec": spec,
            "response": "درخواست با هوش مصنوعی تحلیل شد.",
        }

    except Exception as exc:
        # مسیر جایگزین برای خطای سرویس، 403 یا خروجی نامعتبر
        spec = fallback_spec(user_request)

        return {
            "bot_spec": spec,
            "response": (
                "مشخصات اولیه با روش جایگزین ساخته شد. "
                "تحلیل هوش مصنوعی در دسترس نبود."
            ),
        }


graph = StateGraph(AgentState)
graph.add_node("analyze", analyze_request)
graph.set_entry_point("analyze")
graph.add_edge("analyze", END)

agent = graph.compile()
