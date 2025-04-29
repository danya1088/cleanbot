import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from aiogram.filters import CommandStart
from aiogram.enums import ContentType

TOKEN = os.getenv("TOKEN")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

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
await message.answer("🔥 Добро пожаловать в сервис!")
Нажмите /start чтобы выбрать услугу.")

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
        await callback_query.message.answer("📦 Вы выбрали крупный мусор. Укажите объём:", reply_markup=keyboard)
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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())