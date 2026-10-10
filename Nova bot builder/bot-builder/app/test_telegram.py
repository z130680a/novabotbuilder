import asyncio

from telegram import Bot
from config import TELEGRAM_BOT_TOKEN


async def main():
    print("در حال تست اتصال به Telegram...")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    me = await bot.get_me()

    print("✅ اتصال به Telegram موفق بود.")
    print(f"نام بات: {me.first_name}")
    print(f"Username: @{me.username}")


if __name__ == "__main__":
    asyncio.run(main())