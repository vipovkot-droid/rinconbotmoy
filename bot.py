import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import database as db
from config import BOT_TOKEN, BOT_NAME
from handlers import register_handlers, set_bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды бота установлены")

async def main():
    logger.info(f"Запуск {BOT_NAME}...")
    
    db.init_db()
    logger.info("База данных готова")
    
    bot = Bot(token=BOT_TOKEN)
    set_bot(bot)
    
    await set_commands(bot)
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    register_handlers(dp)
    logger.info("Хендлеры зарегистрированы")
    
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен! Ожидание команд...")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
