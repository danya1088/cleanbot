import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем переменные окружения
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Создание экземпляров бота и диспетчера
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Стартовое сообщение
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привет! Напиши что-нибудь в этот чат, и я пришлю тебе Chat ID.")

# Ответ с Chat ID
@dp.message()
async def get_chat_id(message: Message):
    await message.answer(f"🔎 Chat ID: <code>{message.chat.id}</code>", parse_mode="HTML")

# Обработка вебхука
async def handle_webhook(request):
    body = await request.read()
    update = types.Update.model_validate_json(body.decode())
    await dp.feed_update(bot, update)
    return web.Response()

# Установка вебхука при запуске
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

# Запуск веб-приложения
app = web.Application()
app.router.add_post("/", handle_webhook)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, port=10000)