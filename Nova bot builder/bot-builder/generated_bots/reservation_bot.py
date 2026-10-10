import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from app.config import TELEGRAM_BOT_TOKEN


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = BASE_DIR / "generated_bots" / "bot_config.json"
DATA_FILE = BASE_DIR / "generated_bots" / "data.json"


# =====================================
# Load bot configuration
# =====================================

def get_current_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================
# Data helpers
# =====================================

def load_data():
    if not DATA_FILE.exists():
        data = {
            "reservations": {},
            "waiting_list": []
        }

        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "reservations" not in data:
            data["reservations"] = {}

        if "waiting_list" not in data:
            data["waiting_list"] = []

        return data

    except (json.JSONDecodeError, OSError):
        data = {
            "reservations": {},
            "waiting_list": []
        }

        save_data(data)
        return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =====================================
# Telegram keyboard
# =====================================

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ رزرو",
                callback_data="reserve"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ لغو رزرو",
                callback_data="cancel"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 مشاهده ظرفیت",
                callback_data="capacity"
            )
        ],
    ])


# =====================================
# /start
# =====================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    current_config = get_current_config()
    current_capacity = int(
        current_config.get("capacity", 30)
    )

    bot_name = current_config.get(
        "bot_name",
        "بات رزرو"
    )

    await update.message.reply_text(
        f"سلام 👋\n\n"
        f"به {bot_name} خوش آمدید.\n\n"
        f"📍 مکان: اصفهان\n"
        f"📅 زمان: چهارشنبه ساعت 16\n"
        f"👥 ظرفیت: {current_capacity} نفر\n\n"
        f"یک گزینه را انتخاب کنید:",
        reply_markup=main_keyboard(),
    )


# =====================================
# Button handler
# =====================================

async def handle_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    # جلوگیری از خراب شدن بات به‌خاطر callback قدیمی
    try:
        await query.answer()
    except Exception as e:
        print(f"Callback warning: {e}")

    current_config = get_current_config()
    current_capacity = int(
        current_config.get("capacity", 30)
    )

    user = query.from_user
    user_id = str(user.id)
    user_name = user.full_name

    data = load_data()

    reservations = data["reservations"]
    waiting_list = data["waiting_list"]


    # =================================
    # Capacity
    # =================================

    if query.data == "capacity":

        remaining = max(
            current_capacity - len(reservations),
            0
        )

        await query.message.reply_text(
            f"📊 وضعیت کارگاه\n\n"
            f"ظرفیت کل: {current_capacity}\n"
            f"رزرو شده: {len(reservations)} نفر\n"
            f"ظرفیت باقی‌مانده: {remaining} نفر\n"
            f"⏳ لیست انتظار: {len(waiting_list)} نفر"
        )

        return


    # =================================
    # Reserve
    # =================================

    if query.data == "reserve":

        if user_id in reservations:

            await query.message.reply_text(
                "شما قبلاً رزرو کرده‌اید ✅"
            )

            return


        if user_id in waiting_list:

            position = waiting_list.index(user_id) + 1

            await query.message.reply_text(
                f"شما در لیست انتظار هستید ⏳\n"
                f"موقعیت شما: {position}"
            )

            return


        if len(reservations) < current_capacity:

            reservations[user_id] = {
                "name": user_name
            }

            save_data(data)

            remaining = (
                current_capacity - len(reservations)
            )

            await query.message.reply_text(
                f"✅ رزرو با موفقیت انجام شد.\n\n"
                f"نام: {user_name}\n"
                f"ظرفیت باقی‌مانده: {remaining} نفر"
            )

            return


        # ظرفیت تکمیل است
        waiting_list.append(user_id)

        save_data(data)

        position = len(waiting_list)

        await query.message.reply_text(
            f"❌ ظرفیت کارگاه تکمیل شده است.\n\n"
            f"شما به لیست انتظار اضافه شدید.\n"
            f"موقعیت شما: {position}"
        )

        return


    # =================================
    # Cancel
    # =================================

    if query.data == "cancel":

        if user_id not in reservations:

            await query.message.reply_text(
                "رزرو فعالی برای شما پیدا نشد."
            )

            return


        # حذف رزرو
        del reservations[user_id]

        message = "✅ رزرو شما با موفقیت لغو شد."


        # =================================
        # Move first waiting user
        # =================================

        if waiting_list:

            next_user_id = str(
                waiting_list.pop(0)
            )

            reservations[next_user_id] = {
                "name": f"کاربر {next_user_id}"
            }

            try:

                await context.bot.send_message(
                    chat_id=int(next_user_id),
                    text=(
                        "🎉 یک ظرفیت خالی شد.\n\n"
                        "رزرو شما از لیست انتظار "
                        "به‌صورت خودکار فعال شد. ✅"
                    )
                )

            except Exception as e:

                print(
                    f"Waiting-list notification warning: {e}"
                )

            message += (
                "\n\n"
                "🔄 اولین نفر لیست انتظار "
                "به‌صورت خودکار جایگزین شد."
            )


        save_data(data)

        await query.message.reply_text(message)

        return


# =====================================
# Error handler
# =====================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    print(
        f"Bot error: {context.error}"
    )


# =====================================
# Run bot
# =====================================

def main():

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(handle_button)
    )

    app.add_error_handler(error_handler)

    print(
        "Generated reservation bot is running..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()