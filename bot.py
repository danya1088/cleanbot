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
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
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
    user_id = message.from_user.id
    user_data = await state.get_data()
    
    # Проверяем, является ли пользователь новым (нет данных в state)
    if not user_data.get("is_old_user"):
        await state.update_data(is_old_user=True)
        await show_instruction(message)
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="new_order")],
                [InlineKeyboardButton(text="📘 Показать инструкцию", callback_data="show_instruction")],
                [InlineKeyboardButton(text="📞 Связаться с администратором", url="https://t.me/YOUR_ADMIN_USERNAME")]
            ]
        )
        await message.answer(
            "Добро пожаловать в сервис уборки мусора! ♻️\n\nВыберите действие:",
            reply_markup=keyboard
        )
    await state.clear()


async def show_instruction(message: types.Message):
    instruction_text = (
        "🚀 Как мы работаем:\n\n"
        "1️⃣ Вы оставляете заявку через наш бот:\n"
        "- Нажимаете кнопку '📝 Оставить заявку'.\n"
        "- Выбираете тип мусора (один пакет, несколько пакетов или крупный мусор).\n\n"
        "2️⃣ Указываете точный адрес:\n"
        "- Улица, дом, корпус.\n"
        "- Подъезд, этаж, квартира.\n"
        "- Код от домофона, если есть.\n\n"
        "3️⃣ Отправляете фото мусора:\n"
        "- Фото обязательно для любого типа мусора.\n"
        "- Для крупного или строительного мусора (мебель, техника, строительные отходы) — максимальный общий вес мусора до 30 кг.\n"
        "- Для оформления заявки на крупный мусор обязательна связь с администратором.\n\n"
        "4️⃣ Оплачиваете услугу:\n"
        "- Мы укажем вам номер телефона для перевода.\n"
        "- Переведите сумму и отправьте фото чека.\n\n"
        "5️⃣ Курьер забирает и выбрасывает мусор:\n"
        "- Курьер заберёт мусор в указанное время.\n"
        "- Вы получите уведомления: ✅ 'Мусор забран.' и 🚮 'Мусор выброшен.'"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Продолжить", callback_data="start_order")]
        ]
    )

    await message.answer(instruction_text, reply_markup=keyboard)


@dp.callback_query(F.data == "show_instruction")
async def show_instruction_callback(callback: types.CallbackQuery):
    await show_instruction(callback.message)


@dp.callback_query(F.data == "start_order")
async def start_order(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Один пакет", callback_data="choose_Один пакет")],
            [InlineKeyboardButton(text="🧹 2-3 пакета", callback_data="choose_2-3 пакета")],
            [InlineKeyboardButton(text="🪵 Крупный или строительный мусор", callback_data="choose_Крупный мусор")]
        ]
    )
    await callback.message.answer("Выберите услугу:", reply_markup=keyboard)
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

    # Текущее время по МСК
    now = datetime.now(pytz.timezone("Europe/Moscow"))
    current_hour = now.hour

    # Временные слоты с фильтрацией по текущему времени
    time_slots = [f"{h}:00" for h in range(max(8, current_hour + 1), 21)]
    slot_limit = 15
    slot_counts = {slot: 0 for slot in time_slots}

    try:
        with open("orders.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            for row in rows[1:]:
                if row and row[4] in slot_counts:
                    slot_counts[row[4]] += 1
    except FileNotFoundError:
        pass

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
    data["order_id"] = order_id
    data["status"] = "Ожидает подтверждения оплаты"

    await bot.send_photo(
        chat_id=GROUP_CHAT_ID,
        photo=message.photo[-1].file_id,
        caption=(
            f"🧾 Новый заказ #{order_id}\n"
            f"Услуга: {data['product']}\n"
            f"Адрес: {data['address']}\n\n"
            "Подтвердите выполнение:"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{order_id}")],
                [InlineKeyboardButton("✅ Мусор забрали", callback_data=f"status_taken_{order_id}")],
                [InlineKeyboardButton("🚮 Мусор выбросили", callback_data=f"status_disposed_{order_id}")],
                [InlineKeyboardButton("📞 Связаться с администратором", url="https://t.me/danya1088")]
            ]
        )
    )

    await message.answer("✅ Заказ оформлен! Ожидайте, курьер заберет мусор в ближайшее время.")

@dp.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]
    await callback.message.edit_caption(f"✅ Оплата подтверждена (заказ #{order_id})")
    await bot.send_message(callback.from_user.id, f"✅ Оплата подтверждена! Ваш заказ #{order_id} принят.")

@dp.callback_query(F.data.startswith("status_taken_"))
async def status_taken(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]
    await callback.message.edit_caption(f"✅ Мусор забран (заказ #{order_id})")
    await bot.send_message(callback.from_user.id, f"✅ Мусор забран по вашему заказу #{order_id}.")

@dp.callback_query(F.data.startswith("status_disposed_"))
async def status_disposed(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]
    await callback.message.edit_caption(f"🚮 Мусор выброшен (заказ #{order_id})")
    await bot.send_message(callback.from_user.id, f"🚮 Мусор выброшен по вашему заказу #{order_id}.")

# Ежедневный отчёт
async def send_daily_report():
    try:
        with open("orders.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) <= 1:
                await bot.send_message(chat_id=GROUP_CHAT_ID, text="📊 За сегодня заказов не было.")
                return

            today = datetime.now(pytz.timezone("Europe/Moscow")).date()
            filtered = [row for row in rows[1:] if row and row[0][:8] == today.strftime("%Y%m%d")]

            if not filtered:
                await bot.send_message(chat_id=GROUP_CHAT_ID, text="📊 За сегодня заказов не было.")
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

            await bot.send_message(chat_id=GROUP_CHAT_ID, text=report.strip())
    except Exception as e:
        logging.error(f"Ошибка при создании отчёта: {e}")

def setup_scheduler():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_report, "cron", hour=21, minute=30)
    scheduler.start()

# Webhook и запуск
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
