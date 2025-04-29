import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ContentType
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice
)
from aiohttp import web

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

products = {
    "Уборка 1 пакет": {
        "description": "Вынос одного пакета бытового мусора.",
        "price": 10000
    },
    "Уборка 2-3 пакета": {
        "description": "Вынос двух или трёх пакетов мусора.",
        "price": 20000
    },
    "Крупный мусор": {
        "description": "Вынос мебели и строительного мусора.",
        "price": 40000
    }
}

user_data = {}

class OrderForm(StatesGroup):
    waiting_for_address = State()
    waiting_for_photo = State()
    waiting_for_time = State()
    waiting_for_product = State()

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await message.answer("👋 Добро пожаловать!\n\n📍 Пожалуйста, укажите точный адрес для вывоза мусора.")
    await state.set_state(OrderForm.waiting_for_address)

@dp.message(OrderForm.waiting_for_address)
async def address_step(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("📸 Теперь отправьте фото мусора.")
    await state.set_state(OrderForm.waiting_for_photo)

@dp.message(OrderForm.waiting_for_photo, F.photo)
async def photo_step(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await message.answer("🕐 Укажите удобное время для выноса (например, 'в течение 30 минут' или 'после 18:00').")
    await state.set_state(OrderForm.waiting_for_time)

@dp.message(OrderForm.waiting_for_time)
async def time_step(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"choose_{name}")]
            for name in products.keys()
        ]
    )

    await message.answer("✅ Спасибо! Теперь выберите услугу:", reply_markup=keyboard)
    await state.set_state(OrderForm.waiting_for_product)

@dp.callback_query(F.data.startswith("choose_"))
async def choose_service(callback_query: types.CallbackQuery, state: FSMContext):
    product_name = callback_query.data.split("_", 1)[1]
    await state.update_data(product=product_name)
    data = await state.get_data()
    product = products[product_name]

    await bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title=product_name,
        description=product["description"],
        payload=product_name,
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=product_name, amount=product["price"])],
        start_parameter="clean_order"
    )
    await callback_query.answer()

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_name = data.get("product")
    address = data.get("address")
    photo_id = data.get("photo")
    time = data.get("time")

    await message.answer("✅ Спасибо за заказ! Курьер приедет в указанное время.")

    text = (
        f"🧾 Новый заказ!\n"
        f"📍 Адрес: {address}\n"
        f"🕐 Время: {time}\n"
        f"🛍 Услуга: {product_name}\n"
        f"👤 @{message.from_user.username or 'без username'}"
    )
    await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=text)

    await state.clear()

async def handle_webhook(request):
    body = await request.read()
    update = types.Update.model_validate_json(body.decode())
    await dp.feed_update(bot, update)
    return web.Response()

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

app = web.Application()
app.router.add_post("/", handle_webhook)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, port=10000)