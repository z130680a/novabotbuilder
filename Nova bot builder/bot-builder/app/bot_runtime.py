from __future__ import annotations

import asyncio
import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest


# =========================================================
# Paths and imports
# =========================================================

BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import TELEGRAM_BOT_TOKEN
from app.database import init_db, upsert_participant
from app.workshop_store import (
    get_workshop,
    is_workshop_active,
    load_workshops,
)


WORKSHOP_DATA_DIR = BASE_DIR / "generated_bots" / "workshop_data"
WORKSHOP_DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =========================================================
# Workshop helpers
# =========================================================

def workshop_id_of(workshop: dict[str, Any]) -> int:
    """Extract the numeric ID from a workshop dictionary."""
    return int(workshop["id"])


def workshop_is_active(workshop: dict[str, Any]) -> bool:
    """Check workshop activity using its numeric ID."""
    return bool(is_workshop_active(workshop_id_of(workshop)))


def get_workshop_spec(workshop: dict[str, Any]) -> dict[str, Any]:
    spec = workshop.get("spec")
    return spec if isinstance(spec, dict) else workshop


# =========================================================
# Reservation engine
# =========================================================

class ReservationEngine:
    def __init__(
        self,
        capacity: int,
        data_file: str | Path | None = None,
        workshop_id: int | None = None,
    ):
        self.capacity = max(1, int(capacity))
        self.workshop_id = workshop_id
        self.data_file = Path(data_file) if data_file else None
        self.data: dict[str, Any] = {
            "reserved": [],
            "waitlist": [],
        }
        self._load()

    def _load(self) -> None:
        if not self.data_file:
            return

        if not self.data_file.exists():
            self._save()
            return

        try:
            loaded = json.loads(
                self.data_file.read_text(encoding="utf-8")
            )

            if not isinstance(loaded, dict):
                raise ValueError("Invalid reservation data")

            reserved = loaded.get("reserved", [])
            waitlist = loaded.get("waitlist", [])

            if not isinstance(reserved, list):
                raise ValueError("Invalid reserved list")

            if not isinstance(waitlist, list):
                raise ValueError("Invalid waitlist")

            self.data = {
                "reserved": reserved,
                "waitlist": waitlist,
            }

        except (OSError, ValueError, json.JSONDecodeError):
            logger.exception(
                "Could not load reservation file: %s",
                self.data_file,
            )
            self.data = {
                "reserved": [],
                "waitlist": [],
            }

    def _save(self) -> None:
        if not self.data_file:
            return

        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(
            json.dumps(
                self.data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def reserved_count(self) -> int:
        return len(self.data["reserved"])

    def waitlist_count(self) -> int:
        return len(self.data["waitlist"])

    def is_reserved(self, user_id: int | str) -> bool:
        uid = str(user_id)
        return any(
            str(item.get("user_id")) == uid
            for item in self.data["reserved"]
        )

    def is_waiting(self, user_id: int | str) -> bool:
        uid = str(user_id)
        return any(
            str(item.get("user_id")) == uid
            for item in self.data["waitlist"]
        )

    def _sync_database(
        self,
        user_id: int | str,
        user_data: dict[str, Any] | None,
        status: str,
    ) -> None:
        if self.workshop_id is None:
            return

        try:
            telegram_user_id = int(user_id)
        except (TypeError, ValueError):
            logger.warning("Invalid Telegram user ID: %s", user_id)
            return

        user_data = user_data or {}

        try:
            upsert_participant(
                workshop_id=self.workshop_id,
                telegram_user_id=telegram_user_id,
                username=user_data.get("username"),
                first_name=user_data.get("first_name"),
                last_name=user_data.get("last_name"),
                phone=user_data.get("phone"),
                status=status,
            )
        except Exception:
            logger.exception(
                "Could not sync participant %s with database",
                telegram_user_id,
            )

    def reserve(
        self,
        user_id: int | str,
        user_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        uid = str(user_id)

        if self.is_reserved(uid):
            return {
                "ok": False,
                "status": "already_registered",
            }

        if self.is_waiting(uid):
            return {
                "ok": False,
                "status": "already_waiting",
            }

        record = {
            "user_id": uid,
            "data": user_data or {},
        }

        if self.reserved_count() < self.capacity:
            self.data["reserved"].append(record)
            self._save()
            self._sync_database(uid, user_data, "registered")

            return {
                "ok": True,
                "status": "registered",
                "count": self.reserved_count(),
            }

        self.data["waitlist"].append(record)
        self._save()
        self._sync_database(uid, user_data, "waitlist")

        return {
            "ok": True,
            "status": "waitlist",
            "position": self.waitlist_count(),
        }

    def cancel(self, user_id: int | str) -> dict[str, Any]:
        uid = str(user_id)

        for index, item in enumerate(self.data["reserved"]):
            if str(item.get("user_id")) != uid:
                continue

            removed = self.data["reserved"].pop(index)
            promoted = None

            if self.data["waitlist"]:
                promoted = self.data["waitlist"].pop(0)
                self.data["reserved"].append(promoted)
                self._sync_database(
                    promoted["user_id"],
                    promoted.get("data", {}),
                    "registered",
                )

            self._save()
            self._sync_database(
                uid,
                removed.get("data", {}),
                "cancelled",
            )

            return {
                "ok": True,
                "status": "cancelled",
                "promoted": promoted,
                "count": self.reserved_count(),
            }

        for index, item in enumerate(self.data["waitlist"]):
            if str(item.get("user_id")) != uid:
                continue

            removed = self.data["waitlist"].pop(index)
            self._save()
            self._sync_database(
                uid,
                removed.get("data", {}),
                "cancelled",
            )

            return {
                "ok": True,
                "status": "waitlist_cancelled",
            }

        return {
            "ok": False,
            "status": "not_registered",
        }


ENGINE_CACHE: dict[int, ReservationEngine] = {}


def get_engine(workshop: dict[str, Any]) -> ReservationEngine:
    workshop_id = workshop_id_of(workshop)
    spec = get_workshop_spec(workshop)

    capacity = int(
        spec.get("capacity", workshop.get("capacity", 10))
    )

    existing = ENGINE_CACHE.get(workshop_id)
    if existing is not None and existing.capacity == capacity:
        return existing

    data_file = WORKSHOP_DATA_DIR / f"workshop_{workshop_id}.json"

    engine = ReservationEngine(
        capacity=capacity,
        data_file=data_file,
        workshop_id=workshop_id,
    )
    ENGINE_CACHE[workshop_id] = engine
    return engine


# =========================================================
# Keyboards
# =========================================================

def workshop_keyboard(
    workshop_id: int,
    active: bool,
) -> InlineKeyboardMarkup:
    rows = []

    if active:
        rows.append([
            InlineKeyboardButton(
                "📝 ثبت‌نام",
                callback_data=f"workshop_action:{workshop_id}:reserve",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "👥 ظرفیت و وضعیت",
            callback_data=f"workshop_action:{workshop_id}:capacity",
        ),
        InlineKeyboardButton(
            "↩️ بازگشت",
            callback_data="back_to_workshops",
        ),
    ])

    if not active:
        rows.insert(0, [
            InlineKeyboardButton(
                "🔴 این کارگاه غیرفعال است",
                callback_data=f"workshop_action:{workshop_id}:inactive",
            )
        ])

    return InlineKeyboardMarkup(rows)


def workshops_keyboard() -> InlineKeyboardMarkup:
    buttons = []

    try:
        workshops = load_workshops() or []
    except Exception:
        logger.exception("Could not load workshops")
        workshops = []

    for workshop in workshops:
        try:
            if not isinstance(workshop, dict) or "id" not in workshop:
                logger.warning("Skipping invalid workshop: %r", workshop)
                continue

            workshop_id = workshop_id_of(workshop)
            spec = get_workshop_spec(workshop)
            name = str(spec.get("bot_name", "کارگاه"))
            active = workshop_is_active(workshop)

            label = (
                f"🟢 {name}"
                if active
                else f"🔴 {name} | غیرفعال"
            )

            buttons.append([
                InlineKeyboardButton(
                    label,
                    callback_data=f"workshop_action:{workshop_id}:open",
                )
            ])

        except (KeyError, TypeError, ValueError):
            logger.exception(
                "Could not create button for workshop: %r",
                workshop,
            )

    if not buttons:
        buttons.append([
            InlineKeyboardButton(
                "هنوز کارگاهی ثبت نشده است",
                callback_data="no_workshops",
            )
        ])

    return InlineKeyboardMarkup(buttons)


async def send_workshops(target: Any) -> None:
    workshops = load_workshops() or []

    if not workshops:
        await target.edit_message_text(
            "در حال حاضر کارگاهی ثبت نشده است."
        )
        return

    await target.edit_message_text(
        "کارگاه موردنظر را انتخاب کنید:",
        reply_markup=workshops_keyboard(),
    )


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    if message is None:
        return

    user_id = (
        update.effective_user.id
        if update.effective_user
        else "نامشخص"
    )
    logger.info("Received /start from Telegram user %s", user_id)

    try:
        keyboard = workshops_keyboard()
        await message.reply_text(
            "سلام 👋\n\nیکی از کارگاه‌ها را انتخاب کنید:",
            reply_markup=keyboard,
        )

    except Exception:
        logger.exception("Could not respond to /start")
        await message.reply_text(
            "متأسفانه هنگام نمایش کارگاه‌ها خطایی رخ داد. "
            "لطفاً دوباره تلاش کنید."
        )


# =========================================================
# Callback handler
# =========================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None:
        return

    data = query.data or ""

    if data == "back_to_workshops":
        await query.answer()
        try:
            await send_workshops(query)
        except Exception:
            logger.exception("Could not return to workshop list")
            await query.message.reply_text(
                "نمایش فهرست کارگاه‌ها با خطا مواجه شد."
            )
        return

    if data == "no_workshops":
        await query.answer(
            "در حال حاضر کارگاهی ثبت نشده است.",
            show_alert=True,
        )
        return

    if not data.startswith("workshop_action:"):
        await query.answer()
        return

    try:
        _, workshop_id_text, action = data.split(":")
        workshop_id = int(workshop_id_text)
    except (ValueError, TypeError):
        await query.answer(
            "درخواست نامعتبر است.",
            show_alert=True,
        )
        return

    workshop = get_workshop(workshop_id)

    if not workshop:
        await query.answer()
        await query.edit_message_text(
            "این کارگاه دیگر وجود ندارد."
        )
        return

    spec = get_workshop_spec(workshop)
    name = str(spec.get("bot_name", "کارگاه"))
    capacity = int(spec.get("capacity", workshop.get("capacity", 10)))
    active = workshop_is_active(workshop)
    engine = get_engine(workshop)

    if action == "open":
        await query.answer()

        event_date = spec.get("event_date", "")
        event_time = spec.get("event_time", "")

        status_text = (
            "🟢 ثبت‌نام فعال است"
            if active
            else "🔴 ثبت‌نام جدید غیرفعال است"
        )

        message_text = (
            f"📚 {name}\n\n"
            f"{spec.get('purpose', '')}\n\n"
            f"ظرفیت: {capacity} نفر\n"
            f"ثبت‌نام‌شده: {engine.reserved_count()} نفر\n"
            f"فهرست انتظار: {engine.waitlist_count()} نفر"
        )

        if event_date:
            message_text += f"\n📅 تاریخ: {event_date}"

        if event_time:
            message_text += f"\n⏰ ساعت: {event_time}"

        message_text += f"\n\n{status_text}"

        await query.edit_message_text(
            message_text,
            reply_markup=workshop_keyboard(workshop_id, active),
        )
        return

    if action == "inactive":
        await query.answer(
            "این کارگاه غیرفعال است و ثبت‌نام جدید امکان‌پذیر نیست.",
            show_alert=True,
        )
        return

    if action == "capacity":
        await query.answer()
        await query.edit_message_text(
            f"📊 وضعیت {name}\n\n"
            f"ظرفیت کل: {capacity}\n"
            f"ثبت‌نام‌شده: {engine.reserved_count()}\n"
            f"فهرست انتظار: {engine.waitlist_count()}",
            reply_markup=workshop_keyboard(workshop_id, active),
        )
        return

    if action == "reserve":
        latest_workshop = get_workshop(workshop_id)

        if not latest_workshop:
            await query.answer(
                "این کارگاه حذف شده است.",
                show_alert=True,
            )
            return

        if not workshop_is_active(latest_workshop):
            await query.answer(
                "این کارگاه در حال حاضر غیرفعال است.",
                show_alert=True,
            )
            return

        context.user_data["pending_registration"] = {
            "workshop_id": workshop_id,
        }

        await query.answer()
        await query.message.reply_text(
            "برای ثبت‌نام، شماره تلفن خود را با استفاده از دکمه زیر ارسال کنید.",
            reply_markup=ReplyKeyboardMarkup(
                [[
                    KeyboardButton(
                        "📱 ارسال شماره تلفن",
                        request_contact=True,
                    )
                ]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return

    if action == "cancel":
        result = engine.cancel(query.from_user.id)

        if not result["ok"]:
            await query.answer(
                "برای شما ثبت‌نام فعالی پیدا نشد.",
                show_alert=True,
            )
            return

        await query.answer()
        await query.edit_message_text(
            f"✅ ثبت‌نام شما لغو شد.\n\nکارگاه: {name}",
            reply_markup=workshop_keyboard(workshop_id, active),
        )

        promoted = result.get("promoted")
        if promoted:
            try:
                await context.bot.send_message(
                    chat_id=int(promoted["user_id"]),
                    text=(
                        f"🎉 یک ظرفیت در کارگاه «{name}» باز شد.\n"
                        "ثبت‌نام شما از فهرست انتظار به ثبت‌نام قطعی منتقل شد."
                    ),
                )
            except (TelegramError, ValueError, TypeError):
                logger.exception(
                    "Could not notify promoted participant."
                )
        return

    await query.answer(
        "عملیات ناشناخته است.",
        show_alert=True,
    )


# =========================================================
# Contact handler
# =========================================================

async def contact_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user
    contact = message.contact if message else None
    pending = context.user_data.get("pending_registration")

    if not pending or not user or not contact or not message:
        return

    if contact.user_id != user.id:
        await message.reply_text(
            "لطفاً شماره تلفن خودتان را با دکمه تلگرام ارسال کنید."
        )
        return

    context.user_data.pop("pending_registration", None)

    try:
        workshop_id = int(pending["workshop_id"])
    except (KeyError, TypeError, ValueError):
        await message.reply_text(
            "مهلت ثبت‌نام به پایان رسیده است. لطفاً دوباره تلاش کنید.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    workshop = get_workshop(workshop_id)

    if not workshop or not workshop_is_active(workshop):
        await message.reply_text(
            "این کارگاه دیگر برای ثبت‌نام در دسترس نیست.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    engine = get_engine(workshop)

    if engine.is_reserved(user.id):
        await message.reply_text(
            "شما قبلاً در این کارگاه ثبت‌نام کرده‌اید.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if engine.is_waiting(user.id):
        await message.reply_text(
            "شما قبلاً در فهرست انتظار این کارگاه قرار گرفته‌اید.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    spec = get_workshop_spec(workshop)
    name = str(spec.get("bot_name", "کارگاه"))
    capacity = int(spec.get("capacity", workshop.get("capacity", 10)))

    result = engine.reserve(
        user_id=user.id,
        user_data={
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": contact.phone_number,
        },
    )

    if result["status"] == "registered":
        response_text = (
            f"✅ ثبت‌نام شما در کارگاه «{name}» با موفقیت انجام شد.\n"
            f"تعداد ثبت‌نام‌شده‌ها: {result['count']} از {capacity} نفر"
        )

    elif result["status"] == "waitlist":
        response_text = (
            f"ظرفیت کارگاه «{name}» تکمیل شده است.\n"
            "شما به فهرست انتظار اضافه شدید.\n"
            f"جایگاه شما در فهرست انتظار: {result['position']}"
        )

    elif result["status"] == "already_registered":
        response_text = "شما قبلاً در این کارگاه ثبت‌نام کرده‌اید."

    elif result["status"] == "already_waiting":
        response_text = "شما از قبل در فهرست انتظار این کارگاه هستید."

    else:
        response_text = "ثبت‌نام انجام نشد. لطفاً دوباره تلاش کنید."

    await message.reply_text(
        response_text,
        reply_markup=ReplyKeyboardRemove(),
    )


# =========================================================
# Error handling
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    error = context.error

    if error is not None:
        logger.error(
            "An error occurred while processing an update.",
            exc_info=(type(error), error, error.__traceback__),
        )


# =========================================================
# Startup
# =========================================================

def main() -> None:
    if sys.platform == "win32":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is empty. Check app/config.py."
        )

    init_db()

    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
    )

    updates_request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=40,
        write_timeout=30,
        pool_timeout=30,
    )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .get_updates_request(updates_request)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.CONTACT, contact_handler)
    )
    application.add_handler(
        CallbackQueryHandler(callback_handler)
    )
    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot...")

    application.run_polling(
        drop_pending_updates=False,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
