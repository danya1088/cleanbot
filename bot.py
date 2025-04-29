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

class OrderFlow(StatesGroup):
    waiting_for_address = State()
    waiting_for_photo = State()
    waiting_for_payment = State()

user_data = {}

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"choose_{name}")]
            for name in products
        ]
    )
    await message.answer("Добро пожаловать!")

Выберите услугу:", reply_markup=keyboard)
    await state.clear()

@dp.callback_query(F.data.startswith("choose_"))
async def choose_product(callback: types.CallbackQuery, state: FSMContext):
    product_name = callback.data.split("_", 1)[1]
    await state.update_data(product=product_name)
    await callback.message.answer("Введите адрес, куда нужно подъехать:")
    await state.set_state(OrderFlow.waiting_for_address)
    await callback.answer()

@dp.message(OrderFlow.waiting_for_address)
async def get_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("Теперь отправьте фото мусора:")
    await state.set_state(OrderFlow.waiting_for_photo)

@dp.message(OrderFlow.waiting_for_photo, F.photo)
async def get_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    data = await state.get_data()
    product_name = data["product"]
    product = products[product_name]

    await bot.send_invoice(
        chat_id=message.chat.id,
        title=product_name,
        description=product["description"],
        payload=product_name,
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=product_name, amount=product["price"])],
        start_parameter="clean_order"
    )
    await state.set_state(OrderFlow.waiting_for_payment)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def payment_success(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product = data.get("product")
    address = data.get("address")
    photo_id = data.get("photo")
    user = message.from_user

    text = (
        f"Новый заказ!

"
        f"Услуга: {product}
"
        f"Адрес: {address}
"
        f"Пользователь: @{user.username or user.first_name}"
    )

    await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=text)
    await message.answer("Заказ принят! Курьер приедет в течение 20 минут.")
    await state.clear()

# Webhook
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