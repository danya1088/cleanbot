import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ContentType
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
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

user_order = {}

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("🔥 Добро пожаловать в сервис!\n\nНажмите кнопку ниже, чтобы выбрать услугу:")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Перейти в каталог", callback_data="open_catalog")]
        ]
    )
    await message.answer("👇 Выберите действие:", reply_markup=keyboard)

@dp.callback_query(F.data == "open_catalog")
async def open_catalog(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"choose_{name}")]
            for name in products.keys()
        ]
    )
    await callback_query.message.answer("🛒 Выберите услугу:", reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("choose_"))
async def choose_service(callback_query: types.CallbackQuery):
    product_name = callback_query.data.split("_", 1)[1]
    user_order[callback_query.from_user.id] = {"product": product_name}
    if product_name == "Крупный мусор":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Маленький объём", callback_data="volume_1")],
                [InlineKeyboardButton(text="Средний объём", callback_data="volume_2")],
                [InlineKeyboardButton(text="Большой объём", callback_data="volume_3")]
            ]
        )
        await callback_query.message.answer("📦 Укажите объём крупного мусора:", reply_markup=keyboard)
    else:
        await create_invoice(callback_query, quantity=1)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("volume_"))
async def choose_volume(callback_query: types.CallbackQuery):
    qty = int(callback_query.data.split("_")[1])
    await create_invoice(callback_query, quantity=qty)
    await callback_query.answer()

async def create_invoice(callback_query: types.CallbackQuery, quantity: int):
    order = user_order.get(callback_query.from_user.id)
    if not order:
        await callback_query.answer("Ошибка. Попробуйте снова /start.", show_alert=True)
        return
    product_name = order["product"]
    product = products[product_name]
    total_price = product["price"] * quantity
    await bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title=product_name,
        description=product["description"],
        payload=f"{product_name}|{quantity}",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=f"{product_name} × {quantity}", amount=total_price)],
        start_parameter="order"
    )

@dp.message(lambda message: message.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    product_name, qty = payload.split("|")
    await message.answer("✅ Заказ оплачен. Курьер свяжется с вами в течение 20 минут.")
    await bot.send_message(ADMIN_ID, f"Новый заказ: {product_name} × {qty} от @{message.from_user.username}")

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