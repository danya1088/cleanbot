import os
import logging
import csv
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.session.middlewares.request_logging import logger_middleware

from datetime import datetime, timedelta
import asyncio
import logging
import csv
import os
import pytz

# Инициализация логгирования и переменных окружения
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
BANK_NAME = os.getenv("BANK_NAME")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Роутер
router = Router()
dp.include_router(router)

# Состояния
class OrderStates(StatesGroup):
    waiting_for_product = State()
    waiting_for_transfer = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_address = State()
    waiting_for_photo = State()
    waiting_for_payment_proof = State()

products = {
    "👋 Один пакет мусора": 100,
    "🧵 2-3 пакета мусора": 200,
    "🛋️ Крупный мусор": 400
}

# Обработчик команды /start
@dp.message(Command("start"))
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
                [InlineKeyboardButton(text="📄 Оставить заявку", callback_data="new_order")],
                [InlineKeyboardButton(text="🔹 Показать инструкцию", callback_data="show_instruction")],
                [InlineKeyboardButton(text="📞 Связаться с администратором", url="https://t.me/danya1088")]
            ]
        )
        await message.answer(
            "📍 Добро пожаловать в сервис уборки мусора!\n\nВыберите действие:",
            reply_markup=keyboard
        )
    await state.clear()

# Показ инструкции
async def show_instruction(message: types.Message):
    instruction_text = (
        "🚀 Как мы работаем:\n\n"
        "1⃣️ Вы оставляете заявку через наш бот:\n"
        "- Нажимаете кнопку '📝 Оставить заявку'.\n"
        "- Выбираете тип мусора (1 пакет, 2-3 пакета, крупный).\n\n"
        "2⃣️ Вы выбираете способ передачи:\n"
        "- ✅ Выставить за дверь.\n"
        "- 🛋️ Курьер поднимется и заберёт.\n\n"
        "3⃣️ Выбираете дату:\n"
        "- ✅ Сегодня.\n"
        "- 🗓️ Завтра.\n\n"
        "4⃣️ Указываете точный адрес:\n"
        "- Улица, дом, корпус.\n"
        "- Подъезд, этаж, квартира.\n"
        "- Код от домофона.\n\n"
        "5⃣️ Отправляете фото:\n"
        "- Обязательно для всех.\n"
        "- Для крупного до 30 кг, связь с админом.\n\n"
        "6⃣️ Оплата:\n"
        "- Перевод на номер.\n"
        "- Скрин чека.\n\n"
        "7⃣️ Курьер:\n"
        "- Заберёт.\n"
        "- Уведомления: ✅ 'Забрал.' 🚽 'Выброшен.'"
    )
    await message.answer(instruction_text)

# Продолжение основного кода Telegram-бота

# Хендлер после выбора способа передачи мусора
@dp.callback_query(F.data.startswith("transfer_"))
async def choose_transfer(callback: types.CallbackQuery, state: FSMContext):
    transfer_method = "Выставлен за дверь" if "door" in callback.data else "Курьер поднимется"
    await state.update_data(transfer=transfer_method)

    # Выбор даты
    today = datetime.now().strftime("%d.%m.%Y")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Сегодня ({today})", callback_data=f"date_{today}")],
            [InlineKeyboardButton(text=f"📅 Завтра ({tomorrow})", callback_data=f"date_{tomorrow}")]
        ]
    )
    await callback.message.answer("Выберите дату выполнения заявки:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("date_"))
async def choose_date(callback: types.CallbackQuery, state: FSMContext):
    chosen_date = callback.data.split("_", 1)[1]
    await state.update_data(date=chosen_date)

    now = datetime.now(pytz.timezone("Europe/Moscow"))
    today = now.strftime("%d.%m.%Y")
    tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")

    # Формируем временные интервалы
    if chosen_date == today:
        current_hour = now.hour
        time_slots = [f"{h}:00" for h in range(max(8, current_hour + 1), 21)]
    else:
        time_slots = [f"{h}:00" for h in range(8, 21)]

    slot_limit = 15
    slot_counts = {slot: 0 for slot in time_slots}

    try:
        with open("orders.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            for row in rows[1:]:
                if row and row[4] in slot_counts and row[3] == chosen_date:
                    slot_counts[row[4]] += 1
    except FileNotFoundError:
        pass

    available_slots = [slot for slot, count in slot_counts.items() if count < slot_limit]

    if not available_slots:
        await callback.message.answer(f"❌ Все временные интервалы на {chosen_date} заняты. Попробуйте другую дату.")
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=slot, callback_data=f"time_{slot}")]
            for slot in available_slots
        ]
    )
    await callback.message.answer("🕐 Выберите удобное время уборки:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_time)


@dp.callback_query(F.data.startswith("time_"))
async def choose_time(callback: types.CallbackQuery, state: FSMContext):
    time_chosen = callback.data.split("_", 1)[1]
    await state.update_data(time=time_chosen)

    await callback.message.answer(
        "📍 Укажите точный адрес, включая:\n"
        "- улицу\n- дом, корпус\n- подъезд\n- код домофона\n- этаж\n- квартиру"
    )
    await state.set_state(OrderStates.waiting_for_address)

# Продолжение: обработка ввода фото и платежей

@dp.message(OrderStates.waiting_for_photo, F.photo)
async def photo_step(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)

    data = await state.get_data()
    product = data.get("product")

    if product == "🔹 Крупный мусор":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📞 Связаться с администратором", url="https://t.me/danya1088")]
            ]
        )
        await message.answer(
            "⚠️ Для оформления заявки на крупный мусор обязательна связь с администратором!",
            reply_markup=keyboard
        )

    price = products[product]
await message.answer(
    f"🧾 Оплата: <b>{price}</b> руб.\n"
    f"Перевод на номер <b>{PHONE_NUMBER}</b> ({BANK_NAME}).\n\n"
    "💬 После оплаты отправьте фото чека для подтверждения.",
    parse_mode="HTML"
)

@dp.message(OrderStates.waiting_for_payment_proof, F.photo)
async def payment_proof(message: types.Message, state: FSMContext):
    proof_id = message.photo[-1].file_id
    data = await state.get_data()

    # Отправка в чат админа
    caption = (
        "📅 <b>Новый заказ</b>\n"
        f"Товар: {data.get('product')}\n"
        f"Дата: {data.get('date')}\n"
        f"Время: {data.get('time')}\n"
        f"Адрес: {data.get('address')}\n"
        f"<b>Оплата подтверждена</b>"
    )
    await bot.send_photo(GROUP_CHAT_ID, photo=proof_id, caption=caption, parse_mode="HTML")

    await message.answer(
        "🚚 Спасибо! Оплата получена. \nКурьер в скором времени заберёт мусор."
    )
    await state.clear()


@dp.message(OrderStates.waiting_for_address, F.text)
async def get_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("📷 Пожалуйста, отправьте фото мусора:")
    await state.set_state(OrderStates.waiting_for_photo)

# Добавим статусы заявок для администратора
@dp.callback_query(F.data.startswith("status_taken_"))
async def status_taken(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    await bot.send_message(user_id, "✅ Курьер забрал мусор. Спасибо!")
    await callback.answer("Пользователю отправлено уведомление: мусор забран")

@dp.callback_query(F.data.startswith("status_disposed_"))
async def status_disposed(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    await bot.send_message(user_id, "🚮 Мусор утилизирован. Спасибо, что пользуетесь нашим сервисом!")
    await callback.answer("Пользователю отправлено уведомление: мусор выброшен")

# Планировщик для ежедневного отчета
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
scheduler.start()

@scheduler.scheduled_job("cron", hour=21, minute=30)
async def send_daily_report():
    try:
        if os.path.exists("orders.csv"):
            with open("orders.csv", "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > 1:
                report_text = "📊 Ежедневный отчет:\n\n" + "\n".join(lines[1:])
            else:
                report_text = "ℹ️ Заявок за сегодня не было."
        else:
            report_text = "⚠️ Файл orders.csv не найден."
        await bot.send_message(GROUP_CHAT_ID, report_text)
    except Exception as e:
        logging.error(f"Ошибка при отправке отчета: {e}")
