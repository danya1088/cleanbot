
import asyncio
import os
import csv
from datetime import datetime, timedelta
import pytz
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "0000000000")
BANK_NAME = os.getenv("BANK_NAME", "Тинькофф")

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

class OrderStates(StatesGroup):
    waiting_for_product = State()
    waiting_for_transfer = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_address = State()
    waiting_for_photo = State()
    waiting_for_payment_proof = State()

products = {
    "🧺 Один пакет мусора": 100,
    "🗑️ 2-3 пакета мусора": 200,
    "🛢 Крупный мусор": 400
}

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="new_order")],
            [InlineKeyboardButton(text="📄 Показать инструкцию", callback_data="show_instruction")],
            [InlineKeyboardButton(text="📞 Связаться с администратором", url="https://t.me/YOUR_ADMIN_USERNAME")]
        ]
    )
    await message.answer("📍 Добро пожаловать в сервис уборки мусора!")

    await message.answer("Выберите действие:", reply_markup=keyboard)
    await state.clear()
    
@dp.callback_query(F.data == "show_instruction")
async def show_instruction(callback: CallbackQuery):
    instruction_text = (
        "🚀 Как мы работаем:\n\n"
        "1️⃣ Вы оставляете заявку через наш бот:\n"
        "- Нажимаете кнопку '📝 Оставить заявку'.\n"
        "- Выбираете тип мусора (один пакет, несколько пакетов или крупный мусор).\n\n"
        "2️⃣ Вы выбираете способ передачи мусора:\n"
        "- ✅ Мусор выставлен за дверь — курьер просто заберёт его.\n"
        "- 🚪 Курьер поднимется и заберёт лично — клиент должен быть дома.\n\n"
        "3️⃣ Вы выбираете дату выполнения заявки:\n"
        "- ✅ Сегодня — курьер заберёт мусор в ближайшее время.\n"
        "- 📅 Завтра — заявка будет выполнена на следующий день.\n\n"
        "4️⃣ Указываете точный адрес:\n"
        "- Улица, дом, корпус, подъезд, этаж, квартира, код от домофона.\n\n"
        "5️⃣ Отправляете фото мусора:\n"
        "- Фото обязательно для любого типа мусора.\n"
        "- Общий вес крупного мусора — до 30 кг.\n"
        "- Для крупного мусора обязательна связь с администратором.\n\n"
        "6️⃣ Оплачиваете услугу:\n"
        "- Мы укажем номер телефона для перевода.\n"
        "- После перевода отправьте фото чека.\n\n"
        "7️⃣ Курьер забирает и выбрасывает мусор:\n"
        "- Курьер заберёт мусор в указанное время.\n"
        "- Вы получите уведомления: ✅ 'Мусор забран.' и 🚮 'Мусор выброшен.'"
    )
    await callback.message.answer(instruction_text)
    await callback.answer()

@dp.callback_query(F.data == "new_order")
async def new_order(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=product, callback_data=f"product_{product}")]
            for product in products.keys()
        ]
    )
    await callback.message.answer("🗑️ Выберите тип мусора:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_product)

@dp.callback_query(F.data.startswith("product_"))
async def choose_product(callback: CallbackQuery, state: FSMContext):
    product = callback.data.split("_", 1)[1]
    await state.update_data(product=product)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выставить за дверь", callback_data="transfer_door"),
                InlineKeyboardButton(text="🚪 Курьер поднимется", callback_data="transfer_up")
            ]
        ]
    )
    await callback.message.answer("Выберите способ передачи мусора:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_transfer)

@dp.callback_query(F.data.startswith("transfer_"))
async def choose_transfer(callback: CallbackQuery, state: FSMContext):
    transfer_method = "Выставлен за дверь" if "door" in callback.data else "Курьер поднимется"
    await state.update_data(transfer=transfer_method)

    today = datetime.now().strftime("%d.%m.%Y")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Сегодня ({today})", callback_data=f"date_{today}")],
            [InlineKeyboardButton(text=f"📅 Завтра ({tomorrow})", callback_data=f"date_{tomorrow}")]
        ]
    )
    await callback.message.answer("Выберите дату выполнения заявки:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_date)

@dp.callback_query(F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    chosen_date = callback.data.split("_", 1)[1]
    await state.update_data(date=chosen_date)

    now = datetime.now(pytz.timezone("Europe/Moscow"))
    today = now.strftime("%d.%m.%Y")

    if chosen_date == today:
        current_hour = now.hour
        time_slots = [f"{h}:00" for h in range(max(8, current_hour + 1), 21)]
    else:
        time_slots = [f"{h}:00" for h in range(8, 21)]

    slot_counts = {slot: 0 for slot in time_slots}
    try:
        with open("orders.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            for row in rows[1:]:
                if row and row[4] in slot_counts and row[3] == chosen_date:
                    slot_counts[row[4]] += 1
    except FileNotFoundError:
        pass

    available_slots = [slot for slot, count in slot_counts.items() if count < 15]
    if not available_slots:
        await callback.message.answer(f"❌ Все временные интервалы на {chosen_date} заняты. Попробуйте другую дату.")
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=slot, callback_data=f"time_{slot}")] for slot in available_slots
        ]
    )
    await callback.message.answer("🕐 Выберите удобное время уборки:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_time)

@dp.callback_query(F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    time_chosen = callback.data.split("_", 1)[1]
    await state.update_data(time=time_chosen)
    await callback.message.answer("📍 Укажите точный адрес (улица, дом, подъезд, этаж, код, квартира):")
    await state.set_state(OrderStates.waiting_for_address)

@dp.message(OrderStates.waiting_for_address)
async def get_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("📷 Пожалуйста, отправьте фото мусора:")
    await state.set_state(OrderStates.waiting_for_photo)

@dp.message(OrderStates.waiting_for_photo, F.photo)
async def photo_step(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    data = await state.get_data()
    product = data.get("product")
    price = products.get(product, 0)

    await message.answer(
    f"""💳 Оплата: <b>{price}</b> руб.
Перевод на номер <b>{PHONE_NUMBER}</b> ({BANK_NAME}).
📸 После оплаты отправьте фото чека для подтверждения.""",
    parse_mode="HTML"
)
    await state.set_state(OrderStates.waiting_for_payment_proof)

@dp.message(OrderStates.waiting_for_payment_proof, F.photo)
async def payment_proof(message: Message, state: FSMContext):
    proof_id = message.photo[-1].file_id
    data = await state.get_data()

    caption = (
        f"📦 Новый заказ:\n"
        f"🧾 Услуга: {data.get('product')}\n"
        f"📅 Дата: {data.get('date')}\n"
        f"⏰ Время: {data.get('time')}\n"
        f"📍 Адрес: {data.get('address')}\n"
        f"💳 Оплата подтверждена"
    )

    await bot.send_photo(GROUP_CHAT_ID, photo=proof_id, caption=caption)
    await message.answer("✅ Спасибо! Курьер в ближайшее время заберёт мусор.")
    await state.clear()

# 📌 Настройки Webhook
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# 📩 Обработка входящих запросов от Telegram
async def webhook_handler(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

# 🔄 Действия при запуске приложения
async def on_startup(app):
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)

# 🏗️ Инициализация aiohttp-приложения
app = web.Application()
app.router.add_post("/webhook", webhook_handler)
app.on_startup.append(on_startup)

# 🚀 Запуск приложения
if __name__ == "__main__":
    web.run_app(app, port=PORT)
