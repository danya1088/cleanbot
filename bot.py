import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ContentType
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("8076919458:AAGpogsbimGR7_GcLQ2HK8FoAo-wmqPaK78")
ADMIN_ID = int(os.getenv("1774333684"))
WEBHOOK_URL = os.getenv("https://cleanbot-1.onrender.com/")
PHONE_NUMBER = os.getenv("+79877579144")
BANK_NAME = os.getenv("Озон банк")

bot = Bot(token=TOKEN)
dp = Dispatcher()

products = {
    "🛍 Уборка 1 пакет": 100,
    "🧺 Уборка 2-3 пакета": 200,
    "🛒 Крупный мусор": 400
}

class OrderStates(StatesGroup):
    waiting_for_address = State()
    waiting_for_photo = State()
    waiting_for_payment_proof = State()

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"choose_{name}")]
            for name in products
        ]
    )
    await message.answer(
        "Добро пожаловать! 👋\n\nВыберите услугу, которую нужно выполнить:",
        reply_markup=keyboard
    )
    await state.clear()

@dp.callback_query(F.data.startswith("choose_"))
async def choose_product(callback: types.CallbackQuery, state: FSMContext):
    product_name = callback.data.split("_", 1)[1]
    await state.update_data(product=product_name)
    await callback.message.answer("📍 Введите адрес, куда нужно подъехать:")
    await state.set_state(OrderStates.waiting_for_address)
    await callback.answer()

@dp.message(OrderStates.waiting_for_address)
async def address_step(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("📸 Теперь отправьте фото мусора:")
    await state.set_state(OrderStates.waiting_for_photo)

@dp.message(OrderStates.waiting_for_photo, F.photo)
async def photo_step(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    data = await state.get_data()
    product = data["product"]
    price = products[product]

    await message.answer(
        f"💳 Для завершения заказа переведите <b>{price}₽</b> на номер <b>{PHONE_NUMBER}</b> ({BANK_NAME})\n"
        "После перевода отправьте чек или скриншот подтверждения.",
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.waiting_for_payment_proof)

@dp.message(OrderStates.waiting_for_payment_proof, F.photo)
async def payment_proof_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user

    caption = f"""ПОДТВЕРЖДЕНИЕ ОПЛАТЫ

Услуга: {data['product']}
Адрес: {data['address']}
Пользователь: @{user.username or user.first_name}
Подтвердите выполнение заказа?"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user.id}")]
        ]
    )

    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
    await message.answer("✅ Чек отправлен. Ожидайте подтверждения от администратора.")

@dp.callback_query(F.data.startswith("approve_"))
async def confirm_order(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(chat_id=user_id, text="✅ Оплата подтверждена! Курьер уже в пути.")
    await callback.answer("Пользователь уведомлён.")

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