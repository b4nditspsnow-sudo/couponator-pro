import asyncio, os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from .db import init_db
from .user import router as user_router
from .admin import router as admin_router

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(user_router)
dp.include_router(admin_router)

async def setup_commands():
    cmds = [
        BotCommand(command="promos", description="Категории скидок"),
        BotCommand(command="earn", description="Заработать с ботом"),
        BotCommand(command="admin", description="Админ-меню"),
    ]
    await bot.set_my_commands(cmds)

async def main():
    await init_db()
    await setup_commands()
    await dp.start_polling(bot)
