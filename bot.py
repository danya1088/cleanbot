import os
import logging
import csv
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
import pytz

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
BANK_NAME = os.getenv("BANK_NAME")

bot = Bot(token=TOKEN)
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
    "🛠️ Один пакет мусора": 100,
    "🧵 2-3 пакета мусора": 200,
    "🛋️ Крупный мусор": 400,
}

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if not user_data.get("is_old_user"):
        await state.update_data(is_old_user=True)
        await show_instruction(message)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Оставить заявку", callback_data="new_order")],
            [InlineKeyboardButton(text="📄 Показать инструкцию", callback_data="show_instruction")],
            [InlineKeyboardButton(text="📞 Связаться с администратором", url="https://t.me/danya1088")],
        ])
        await message.answer(
            "📢 Добро пожаловать в сервис уборки мусора!\n\nВыберите действие:",
            reply_markup=keyboard
        )
        await state.clear()

@dp.callback_query(F.data == "new_order")
async def new_order(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ Один пакет мусора", callback_data="product_1")],
        [InlineKeyboardButton(text="🧵 2-3 пакета мусора", callback_data="product_2")],
        [InlineKeyboardButton(text="🛋️ Крупный мусор (до 30 кг)", callback_data="product_3")],
    ])
    await callback.message.answer("🌀 Выберите услугу:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_product)

@dp.callback_query(F.data.startswith("product_"))
async def select_product(callback: types.CallbackQuery, state: FSMContext):
    product_code = callback.data.split("_")[1]
    product_map = {"1": "🛠️ Один пакет мусора", "2": "🧵 2-3 пакета мусора", "3": "🛋️ Крупный мусор"}
    product_name = product_map[product_code]

    await state.update_data(product=product_name)
    await callback.message.answer(
        "🚪 Выберите способ передачи мусора:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выставлен за дверь", callback_data="transfer_door")],
            [InlineKeyboardButton(text="🚪 Курьер поднимется", callback_data="transfer_courier")]
        ])
    )
    await state.set_state(OrderStates.waiting_for_transfer)

@dp.callback_query(F.data.startswith("transfer_"))
async def select_transfer(callback: types.CallbackQuery, state: FSMContext):
    transfer_method = callback.data.split("_")[1]
    await state.update_data(transfer=transfer_method)

    now = datetime.now(pytz.timezone("Europe/Moscow"))
    today = now.strftime("%d.%m.%Y")
    tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗓️ Сегодня ({today})", callback_data=f"date_{today}")],
        [InlineKeyboardButton(text=f"📅 Завтра ({tomorrow})", callback_data=f"date_{tomorrow}")],
    ])
    await callback.message.answer("\n📆 Выберите дату исполнения заявки:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_date)

@dp.callback_query(F.data.startswith("date_"))
async def choose_date(callback: types.CallbackQuery, state: FSMContext):
    chosen_date = callback.data.split("_", 1)[1]
    await state.update_data(chosen_date=chosen_date)

    now = datetime.now(pytz.timezone("Europe/Moscow"))
    current_hour = now.hour

    time_slots = [f"{h}:00" for h in range(8, 21)]
    if chosen_date == now.strftime("%d.%m.%Y"):
        time_slots = [slot for slot in time_slots if int(slot.split(":"[0])) > current_hour]

    slot_counts = {slot: 0 for slot in time_slots}
    try:
        with open("orders.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            for row in rows[1:]:
                if len(row) >= 5 and row[3] == chosen_date and row[4] in slot_counts:
                    slot_counts[row[4]] += 1
    except FileNotFoundError:
        pass

    available_slots = [slot for slot, count in slot_counts.items() if count < 15]
    if not available_slots:
        await callback.message.answer("❌ Все временные интервалы на выбранную дату заняты. Попробуйте другую дату.")
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=slot, callback_data=f"time_{slot}")] for slot in available_slots]
    )
    await callback.message.answer("\n⏰ Выберите удобное время уборки (по МСК):", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_time)

async def show_instruction(message: types.Message):
    instruction_text = (
        "🚀 Как мы работаем:\n\n"
        "1️⃣ Вы оставляете заявку через наш бот:\n"
        "- Нажимаете кнопку '📝 Оставить заявку'.\n"
        "- Выбираете тип мусора (один пакет, несколько пакетов или крупный мусор).\n\n"
        "2️⃣ Вы выбираете способ передачи мусора:\n"
        "- ✅ Мусор выставлен за дверь — курьер просто заберёт его.\n"
        "- 🚪 Курьер поднимется и заберёт лично — клиент должен быть дома.\n\n"
        "3️⃣ Вы выбираете дату выполнения заявки:\n"
        "- ✅ Сегодня (текущая дата) — курьер заберёт мусор в ближайшее время.\n"
        "- 📅 Завтра (следующая дата) — заявка будет выполнена на следующий день.\n\n"
        "4️⃣ Указываете точный адрес:\n"
        "- Улица, дом, корпус.\n"
        "- Подъезд, этаж, квартира.\n"
        "- Код от домофона, если есть.\n\n"
        "5️⃣ Отправляете фото мусора:\n"
        "- Фото обязательно для любого типа мусора.\n"
        "- Для крупного или строительного мусора — максимальный общий вес до 30 кг.\n"
        "- Для оформления заявки на крупный мусор обязательна связь с администратором.\n\n"
        "6️⃣ Оплачиваете услугу:\n"
        "- Мы укажем вам номер телефона для перевода.\n"
        "- Переведите сумму и отправьте фото чека.\n\n"
        "7️⃣ Курьер забирает и выбрасывает мусор:\n"
        "- Курьер заберёт мусор в указанное время.\n"
        "- Вы получите уведомления: ✅ 'Мусор забран.' и 🚮 'Мусор выброшен.'"
    )

    await message.answer(instruction_text, parse_mode="HTML")
@dp.callback_query(F.data.startswith("time_"))
async def choose_time(callback: types.CallbackQuery, state: FSMContext):
    time_chosen = callback.data.split("_", 1)[1]
    await state.update_data(time_chosen=time_chosen)

    await callback.message.answer(
        "\ud83d\udccd Укажите точный адрес полностью:\n"
        "- Улица, дом, корпус\n"
        "- Подъезд, этаж, квартира\n"
        "- Код от домофона, если есть"
    )
    await state.set_state(OrderStates.waiting_for_address)

@dp.message(F.text, state=OrderStates.waiting_for_address)
async def get_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("\ud83d\udcf7 Пожалуйста, отправьте фото мусора:")
    await state.set_state(OrderStates.waiting_for_photo)

@dp.message(F.content_type == ContentType.PHOTO, state=OrderStates.waiting_for_photo)
async def get_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)

    data = await state.get_data()
    product = data.get("product")
    price = products[product]

    await message.answer(
        f"\ud83d\udcb3 Переведите <b>{price}₽</b> на номер <b>{PHONE_NUMBER}</b> ({BANK_NAME})\n"
        "После перевода отправьте чек или скриншот.",
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.waiting_for_payment_proof)

@dp.message(F.content_type == ContentType.PHOTO, state=OrderStates.waiting_for_payment_proof)
async def get_payment_proof(message: types.Message, state: FSMContext):
    payment_proof = message.photo[-1].file_id
    await state.update_data(payment_proof=payment_proof)

    data = await state.get_data()
    user_id = message.from_user.id
    address = data.get("address")
    photo_id = data.get("photo_id")
    chosen_date = data.get("chosen_date")
    time_chosen = data.get("time_chosen")
    product = data.get("product")

    # Сохраняем в CSV
    file_exists = os.path.isfile("orders.csv")
    with open("orders.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["user_id", "address", "photo_id", "date", "time", "product"])
        writer.writerow([user_id, address, photo_id, chosen_date, time_chosen, product])

    await message.answer("✅ Спасибо! Оплата получена. Курьер в скором времени заберёт мусор.")
    await bot.send_message(GROUP_CHAT_ID, f"📥 Новая заявка:\n\n<code>{product}</code>\nДата: {chosen_date} {time_chosen}\nАдрес: {address}", parse_mode="HTML")
    await state.clear()

    await message.answer(
    "✅ Спасибо! Оплата получена. Курьер в скором времени заберёт мусор.",
    reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Связаться с администратором", url="https://t.me/YOUR_ADMIN_USERNAME")]
        ]
    )
)

    # Отправляем администратору подтверждение и кнопки управления статусом
    status_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Мусор забран", callback_data=f"status_taken_{user_id}"),
            InlineKeyboardButton(text="🚮 Мусор выброшен", callback_data=f"status_disposed_{user_id}")
        ]
    ])
    await bot.send_message(
        GROUP_CHAT_ID,
        f"📥 Новая заявка:\n\n<code>{product}</code>\nДата: {chosen_date} {time_chosen}\nАдрес: {address}",
        parse_mode="HTML",
        reply_markup=status_keyboard
    )
    await state.clear()

@dp.callback_query(F.data.startswith("status_taken_"))
async def status_taken(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await bot.send_message(user_id, "✅ Курьер забрал мусор. Спасибо!")
    await callback.answer("Пользователю отправлено сообщение: мусор забран")

@dp.callback_query(F.data.startswith("status_disposed_"))
async def status_disposed(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await bot.send_message(user_id, "🚮 Мусор утилизирован. Спасибо, что пользуетесь нашим сервисом!")
    await callback.answer("Пользователю отправлено сообщение: мусор выброшен")


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
                report_text = "\U0001F4CB Ежедневный отчет по заявкам:\n\n" + "\n".join(lines[1:])
            else:
                report_text = "\u274C За сегодня заявок не было."
        else:
            report_text = "\u274C Файл заявок не найден."

        await bot.send_message(GROUP_CHAT_ID, report_text)
    except Exception as e:
        logging.error(f"Ошибка при отправке отчета: {e}")

