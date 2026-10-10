from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BOT_SPEC = json.loads(
    r"""{"bot_name": "بات رزرو کارگاه", "purpose": "بات تلگرام مدیریت ثبت‌نام و رزرو کارگاه.\nدرخواست کاربر: یک بات تلگرام برای رزرو کارگاه می‌خواهم. ظرفیت کارگاه فقط ۲ نفر باشد. هر کاربر فقط یک بار بتواند ثبت‌نام کند. وقتی ظرفیت پر شد، ثبت‌نام جدید انجام نشود و پیام «ظرفیت کارگاه تکمیل شده است» نمایش داده شود. اطلاعات ثبت‌نام‌کنندگان ذخیره شود.\nپاسخ‌های تکمیلی: سؤال: تاریخ برگزاری کارگاه چیست؟\nپاسخ: 1405/08/01\nسؤال: ساعت شروع کارگاه چه زمانی است؟\nپاسخ: 10 صبح\nسؤال: آیا شرکت‌کننده می‌تواند رزرو خود را لغو کند؟\nپاسخ: بله، کاربر بتواند رزرو را لغو کند\nسؤال: اگر ظرفیت تکمیل شد، لیست انتظار فعال باشد؟\nپاسخ: بله، پس از تکمیل ظرفیت فعال شود", "capacity": 2, "features": ["ثبت نام", "رزرو", "لغو رزرو", "نمایش ظرفیت", "لیست انتظار"], "missing_information": [], "event_date": "", "event_time": "", "event_end_time": "", "active": true}"""
)

from app.bot_runtime import (
    ReservationEngine,
    main,
)


if __name__ == "__main__":
    main()
