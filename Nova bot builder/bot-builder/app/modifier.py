import json
import re
import time
from pathlib import Path

from llm import llm
from schemas import BotSpec


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "generated_bots" / "bot_config.json"


def _extract_text(response) -> str:
    """
    خروجی مدل را به متن تبدیل می‌کند.
    با AIMessage و خروجی رشته‌ای هر دو سازگار است.
    """
    if response is None:
        return ""

    if isinstance(response, str):
        return response.strip()

    content = getattr(response, "content", None)

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                text_value = item.get("text")
                if text_value:
                    parts.append(str(text_value))

            else:
                text_value = getattr(item, "text", None)
                if text_value:
                    parts.append(str(text_value))

        return "\n".join(parts).strip()

    return str(response).strip()


def _extract_json(text: str) -> dict:
    """
    JSON را حتی اگر مدل آن را داخل ```json ... ``` قرار داده باشد
    استخراج می‌کند.
    """
    if not text:
        raise ValueError("Agent خروجی خالی برگرداند.")

    cleaned = text.strip()

    # حذف code fence
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    # حالت عادی
    try:
        data = json.loads(cleaned)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    # اگر اطراف JSON متن اضافه وجود داشت
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]

        try:
            data = json.loads(candidate)

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

    raise ValueError("خروجی Agent JSON معتبر نبود.")


def _normalize_persian_digits(value):
    """
    اعداد فارسی و عربی را به انگلیسی تبدیل می‌کند.
    """
    if value is None:
        return value

    text = str(value)

    translation_table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return text.translate(translation_table)


def _try_simple_edit(current_spec: dict, change_request: str):
    """
    تغییرات ساده و مشخص را بدون فراخوانی LLM انجام می‌دهد.

    نمونه‌های پشتیبانی‌شده:

    - ظرفیت را 20 نفر کن
    - ظرفیت رو به 20 نفر تغییر بده
    - ظرفیت را از 5 نفر به 20 نفر تغییر بده
    - ظرفیت از 20 به 50 نفر افزایش پیدا کند
    - capacity را روی 30 بگذار
    - 20 نفر
    """

    if not change_request:
        return None

    request = _normalize_persian_digits(change_request).strip()

    updated = dict(current_spec)

    # ---------------------------------------------------------
    # تشخیص اینکه درخواست مربوط به ظرفیت است
    # ---------------------------------------------------------
    has_capacity_keyword = bool(
        re.search(
            r"(ظرفیت|capacity)",
            request,
            flags=re.IGNORECASE
        )
    )

    # ---------------------------------------------------------
    # حالت اول:
    # «ظرفیت را از 5 نفر به 20 نفر تغییر بده»
    #
    # بسیار مهم:
    # در این حالت باید عدد دوم یعنی 20 انتخاب شود.
    # ---------------------------------------------------------
    if has_capacity_keyword:

        change_to_pattern = re.search(
            r"(?:ظرفیت|capacity).*?"
            r"(?:به|روی|تا)\s*"
            r"(\d+)",
            request,
            flags=re.IGNORECASE
        )

        if change_to_pattern:
            try:
                new_capacity = int(
                    change_to_pattern.group(1)
                )

                if new_capacity > 0:
                    updated["capacity"] = new_capacity

                    return BotSpec.model_validate(updated)

            except (ValueError, TypeError):
                pass

        # -----------------------------------------------------
        # حالت دوم:
        # «ظرفیت را 20 نفر کن»
        #
        # در این حالت ممکن است عبارت «به» وجود نداشته باشد.
        # بنابراین آخرین عدد موجود را انتخاب می‌کنیم.
        # -----------------------------------------------------
        numbers = re.findall(
            r"\d+",
            request
        )

        if numbers:
            try:
                new_capacity = int(numbers[-1])

                if new_capacity > 0:
                    updated["capacity"] = new_capacity

                    return BotSpec.model_validate(updated)

            except (ValueError, TypeError):
                pass

    # ---------------------------------------------------------
    # حالت سوم:
    # «20 نفر»
    # ---------------------------------------------------------
    person_pattern = re.search(
        r"(\d+)\s*(?:نفر|person|people)\b",
        request,
        flags=re.IGNORECASE
    )

    if person_pattern:
        try:
            new_capacity = int(
                person_pattern.group(1)
            )

            if new_capacity > 0:
                updated["capacity"] = new_capacity

                return BotSpec.model_validate(updated)

        except (ValueError, TypeError):
            pass

    return None


def _invoke_with_retry(prompt: str, attempts: int = 2):
    """
    درخواست Agent را با تعداد محدودی تلاش مجدد اجرا می‌کند.
    """

    last_error = None

    for attempt in range(attempts):
        try:
            return llm.invoke(prompt)

        except Exception as exc:
            last_error = exc

            if attempt < attempts - 1:
                time.sleep(1)

    raise last_error


def modify_workshop(current_spec, change_request: str) -> BotSpec:
    """
    نسخه فعلی یک کارگاه را گرفته و بر اساس درخواست کاربر
    نسخه جدید BotSpec را تولید می‌کند.

    این تابع مستقیماً workshops.json را تغییر نمی‌دهد.
    ذخیره نهایی در web.py انجام می‌شود.
    """

    # ---------------------------------------------------------
    # تبدیل spec فعلی به dict
    # ---------------------------------------------------------
    if isinstance(current_spec, BotSpec):
        current_data = current_spec.model_dump()

    elif isinstance(current_spec, dict):
        current_data = dict(current_spec)

    else:
        raise TypeError(
            "current_spec باید dict یا BotSpec باشد."
        )

    change_request = str(
        change_request or ""
    ).strip()

    if not change_request:
        raise ValueError(
            "درخواست تغییر خالی است."
        )

    # ---------------------------------------------------------
    # اول تغییرات ساده را بدون LLM انجام بده
    # ---------------------------------------------------------
    simple_result = _try_simple_edit(
        current_data,
        change_request
    )

    if simple_result is not None:
        return simple_result

    # ---------------------------------------------------------
    # مشخص کردن فیلدهای مجاز BotSpec
    # ---------------------------------------------------------
    field_names = list(
        BotSpec.model_fields.keys()
    )

    fields_text = "\n".join(
        f"- {field_name}"
        for field_name in field_names
    )

    current_json = json.dumps(
        current_data,
        ensure_ascii=False,
        indent=2
    )

    # ---------------------------------------------------------
    # Prompt
    # ---------------------------------------------------------
    prompt = f"""
تو یک ویرایشگر حرفه‌ای برای مشخصات ربات تلگرام هستی.

مشخصات فعلی کارگاه:

{current_json}

فیلدهای مجاز مدل BotSpec:

{fields_text}

درخواست کاربر:

{change_request}

وظیفه تو:

1. فقط تغییراتی را اعمال کن که کاربر درخواست کرده است.
2. اطلاعاتی که کاربر درباره آنها چیزی نگفته را حفظ کن.
3. هیچ فیلد جدیدی خارج از BotSpec ایجاد نکن.
4. خروجی باید یک JSON کامل و معتبر باشد.
5. خروجی باید شامل تمام اطلاعات لازم برای BotSpec باشد.
6. هیچ توضیحی خارج از JSON ننویس.
7. اگر کاربر فقط ظرفیت را تغییر داد، فقط capacity را تغییر بده.
8. اگر کاربر نام، هدف، قابلیت‌ها یا اطلاعات دیگری را تغییر نداد، آنها را دست نزن.

فقط JSON نهایی را برگردان.
"""

    # ---------------------------------------------------------
    # فراخوانی Agent
    # ---------------------------------------------------------
    try:
        response = _invoke_with_retry(
            prompt,
            attempts=2
        )

    except Exception as exc:
        error_text = str(exc)

        if not error_text:
            error_text = exc.__class__.__name__

        raise RuntimeError(
            "زمان پاسخ Agent تمام شد یا اجرای مدل "
            f"با خطا مواجه شد: {error_text}"
        ) from exc

    # ---------------------------------------------------------
    # استخراج متن
    # ---------------------------------------------------------
    response_text = _extract_text(response)

    if not response_text:
        raise RuntimeError(
            "Agent هیچ خروجی قابل استفاده‌ای تولید نکرد."
        )

    # ---------------------------------------------------------
    # استخراج JSON
    # ---------------------------------------------------------
    try:
        data = _extract_json(response_text)

    except Exception as exc:
        raise RuntimeError(
            "Agent نسخه جدید را به صورت JSON معتبر تولید نکرد.\n\n"
            f"خروجی Agent:\n{response_text}"
        ) from exc

    # ---------------------------------------------------------
    # اعتبارسنجی BotSpec
    # ---------------------------------------------------------
    try:
        result = BotSpec.model_validate(data)

    except Exception as exc:
        raise RuntimeError(
            "نسخه جدید با ساختار BotSpec سازگار نیست.\n\n"
            f"خطای اعتبارسنجی:\n{exc}"
        ) from exc

    return result


def modify_bot(change_request: str):
    """
    نسخه قدیمی و عمومی ویرایش BotSpec.
    برای سازگاری با بخش‌های قبلی پروژه نگه داشته شده است.
    """

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"فایل تنظیمات پیدا نشد: {CONFIG_FILE}"
        )

    try:
        current = json.loads(
            CONFIG_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:
        raise RuntimeError(
            f"خواندن bot_config.json ناموفق بود: {exc}"
        ) from exc

    result = modify_workshop(
        current,
        change_request
    )

    CONFIG_FILE.write_text(
        json.dumps(
            result.model_dump(),
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return result


if __name__ == "__main__":
    print("modifier.py loaded successfully.")