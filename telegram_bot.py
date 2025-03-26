import asyncio
from aiogram import Bot, Dispatcher
from app.handlers import router
from app.timing import router_time
from app.get_users_id import router_users_id
from app.contact import router_contact
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
import os
from dotenv import load_dotenv


load_dotenv('token.env')  # Загружаем переменные окружения из .env файла
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Создаем асинхронную функцию


async def set_main_menu(bot: Bot):
    # Создаем список с командами и их описанием для кнопки menu
    main_menu_commands = [
        BotCommand(command='/start',
                   description='Меню бота'),
        BotCommand(command='/url',
                   description='Ссылка на файл'),
        BotCommand(command='/help',
                   description='Поддержка')
    ]

    await bot.set_my_commands(main_menu_commands)


storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
dp.include_router(router)
dp.include_router(router_time)
dp.include_router(router_users_id)
dp.include_router(router_contact)

async def main():
    dp.startup.register(set_main_menu)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
