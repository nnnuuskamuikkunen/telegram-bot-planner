import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, DATABASE_NAME
from database import init_db
from handlers import router
from utils.scheduler import check_reminders


async def main():
    await init_db(DATABASE_NAME)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    asyncio.create_task(check_reminders(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")