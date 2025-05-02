import os
import logging
import csv
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ContentType
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
BANK_NAME = os.getenv("BANK_NAME")

bot = Bot(token=TOKEN)
dp = Dispatcher()

products = {
    "🗑 Один пакет мусора": 100,
    "🧹 2-3 пакета мусора": 200,
    "🪵 Крупный мусор": 400
}

class OrderStates(StatesGroup):
    waiting_for_address = State()
    waiting_for_photo = State()
    waiting_for_time = State()
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
        "Приветствуем в сервисе уборки мусора! ♻️\n\nВыберите услугу:",
        reply_markup=keyboard
    )
    await state.clear()

@dp.callback_query(F.data.startswith("choose_"))
async def choose_product(callback: types.CallbackQuery, state: FSMContext):
    product_name = callback.data.split("_", 1)[1]
    await state.update_data(product=product_name)
    await callback.message.answer(
        "📍 Укажите точный адрес, включая:\n"
        "- улицу\n- дом, корпус\n- подъезд\n- код домофона\n- этаж\n- квартиру"
    )
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

    # Выбор времени с учётом занятости
    time_slots = [f"{h}:00" for h in range(8, 21)]
    slot_limit = 15
    slot_counts = {slot: 0 for slot in time_slots}

    # Подсчёт существующих заказов
    try:
        with open("orders.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            for row in rows[1:]:
                if row and row[4] in slot_counts:
                    slot_counts[row[4]] += 1
    except FileNotFoundError:
        pass

    # Оставляем только незаполненные слоты
    available_slots = [slot for slot, count in slot_counts.items() if count < slot_limit]

    if not available_slots:
        await message.answer("❌ Все временные интервалы на сегодня заняты. Попробуйте позже.")
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=slot, callback_data=f"time_{slot}")]
            for slot in available_slots
        ]
    )
    await message.answer("🕐 Выберите удобное время уборки (по МСК):", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_time)
@dp.callback_query(F.data.startswith("time_"))
async def choose_time(callback: types.CallbackQuery, state: FSMContext):
    time_chosen = callback.data.split("_", 1)[1]
    await state.update_data(time=time_chosen)
    data = await state.get_data()
    product = data["product"]
    price = products[product]

    await callback.message.answer(
        f"💳 Переведите <b>{price}₽</b> на номер <b>{PHONE_NUMBER}</b> ({BANK_NAME})\n"
        "После перевода отправьте чек или скриншот подтверждения.",
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.waiting_for_payment_proof)
    await callback.answer()

@dp.message(OrderStates.waiting_for_payment_proof, F.photo)
async def payment_proof_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user

    order_id = datetime.now().strftime("%Y%m%d%H%M%S")
    row = {
        "order_id": order_id,
        "user": f"@{user.username or user.first_name}",
        "product": data["product"],
        "address": data["address"],
        "time": data["time"]
    }

    with open("orders.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if f.tell() == 0:
            writer.writeheader()
        writer.writerow(row)

    caption = (
        f"🧾 ПОДТВЕРЖДЕНИЕ ОПЛАТЫ\n"
        f"Номер заказа: {order_id}\n"
        f"Услуга: {data['product']}\n"
        f"Адрес: {data['address']}\n"
        f"Время: {data['time']}\n"
        f"Пользователь: @{user.username or user.first_name}\n"
        "Подтвердите выполнение заказа?"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user.id}")]
        ]
    )
    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
    await message.answer("✅ Чек отправлен. Ожидайте подтверждения администратора.")

@dp.callback_query(F.data.startswith("approve_"))
async def confirm_order(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(chat_id=user_id, text="✅ Оплата подтверждена! Курьер приедет в указанное время.")
    await callback.answer("Пользователь уведомлён.")

# Отчёт каждый день в 21:30 по МСК
async def send_daily_report():
    try:
        with open("orders.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) <= 1:
                await bot.send_message(chat_id=ADMIN_ID, text="📊 За сегодня заказов не было.")
                return

            today = datetime.now(pytz.timezone("Europe/Moscow")).date()
            filtered = [row for row in rows[1:] if row and row[0][:8] == today.strftime("%Y%m%d")]

            if not filtered:
                await bot.send_message(chat_id=ADMIN_ID, text="📊 За сегодня заказов не было.")
                return

            report = f"📋 Отчёт за {today.strftime('%d.%m.%Y')}\n\n"
            for row in filtered:
                report += (
                    f"📦 Заказ #{row[0]}\n"
                    f"Пользователь: {row[1]}\n"
                    f"Услуга: {row[2]}\n"
                    f"Адрес: {row[3]}\n"
                    f"Время: {row[4]}\n\n"
                )

            await bot.send_message(chat_id=ADMIN_ID, text=report.strip())
    except Exception as e:
        logging.error(f"Ошибка при создании отчёта: {e}")

def setup_scheduler():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_report, "cron", hour=21, minute=30)
    scheduler.start()

# Webhook
async def handle_webhook(request):
    body = await request.read()
    update = types.Update.model_validate_json(body.decode())
    await dp.feed_update(bot, update)
    return web.Response()

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    setup_scheduler()

app = web.Application()
app.router.add_post("/", handle_webhook)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, port=10000)