
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
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
    waiting_for_large_description = State()
    waiting_for_large_photos = State()


products = {
    "🧺 Один пакет мусора": 100,
    "🗑️ 2–3 пакета мусора": 200,
    "🛢 Крупный мусор": 500
}

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="new_order")],
            [InlineKeyboardButton(text="📄 Показать инструкцию", callback_data="show_instruction")],
            [InlineKeyboardButton(text="📞 Связаться с администратором", url="https://t.me/danya1088")]
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
        "- Выбираете тип мусора:\n"
        "    • 🧺 Один пакет — 100 ₽\n"
        "    • 🗑️ 2–3 пакета — 200 ₽\n"
        "    • 🛢 Крупный мусор (до 30 кг) — 500 ₽\n"
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

    continue_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Продолжить", callback_data="new_order")]
        ]
    )

    await callback.message.answer(instruction_text, reply_markup=continue_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "new_order")
async def new_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧺 Один пакет мусора — 100 ₽", callback_data="product_🧺 Один пакет мусора")],
            [InlineKeyboardButton(text="🗑️ 2–3 пакета мусора — 200 ₽", callback_data="product_🗑️ 2–3 пакета мусора")],
            [InlineKeyboardButton(text="🛢 Крупный мусор (до 30 кг) — 500 ₽", callback_data="product_🛢 Крупный мусор")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_start")]
        ]
    )
    await callback.message.answer("Выберите тип мусора:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "📋 Для оформления новой заявки нажмите кнопку:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="new_order")],
                [InlineKeyboardButton(text="📄 Показать инструкцию", callback_data="show_instruction")]
            ]
        )
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("product_"))
async def choose_product(callback: CallbackQuery, state: FSMContext):
    product = callback.data.split("_", 1)[1]

    if product == "🛢 Крупный мусор":
        await state.update_data(product=product)
        await callback.message.answer("❗ Пожалуйста, опишите, что именно вы хотите вынести (тип предметов, размер, вес):")
        await state.set_state(OrderStates.waiting_for_large_description)
        return  # <== ОЧЕНЬ ВАЖНО: дальше код НЕ ДОЛЖЕН выполняться

    # Все остальные продукты — обычный порядок
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

@dp.message(OrderStates.waiting_for_large_description)
async def get_large_description(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 10:
        await message.answer("❗ Пожалуйста, опишите подробнее. Минимум 10 символов.")
        return

    await state.update_data(large_description=text, photos=[])
    await message.answer("✅ Описание сохранено.\n📷 Теперь отправьте минимум 2 фото крупного мусора.")
    await state.set_state(OrderStates.waiting_for_photo)

@dp.callback_query(F.data.startswith("transfer_"))
async def choose_transfer(callback: CallbackQuery, state: FSMContext):
    transfer_method = "Выставлен за дверь" if "door" in callback.data else "Курьер поднимется"
    await state.update_data(transfer=transfer_method, contact_method=transfer_method)
    await callback.answer()

    today = datetime.now().strftime("%d.%m.%Y")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Сегодня ({today})", callback_data=f"date_{today}")],
            [InlineKeyboardButton(text=f"📅 Завтра ({tomorrow})", callback_data=f"date_{tomorrow}")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_product")]
        ]
    )

    await callback.message.answer("Выберите дату выполнения заявки:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_date)

@dp.callback_query(F.data == "back_to_product")
async def back_to_product(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Выберите тип мусора:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🧺 Один пакет мусора — 100 ₽", callback_data="product_🧺 Один пакет мусора")],
                [InlineKeyboardButton(text="🗑️ 2–3 пакета мусора — 200 ₽", callback_data="product_🗑️ 2–3 пакета мусора")],
                [InlineKeyboardButton(text="🛢 Крупный мусор (до 30 кг) — 500 ₽", callback_data="product_🛢 Крупный мусор")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_start")]
            ]
        )
    )
    await callback.answer()

    # 🔵 А уже потом отправляем сообщение
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
    await state.update_data(time_slot=time_chosen)
    await callback.message.answer("📍 Укажите точный адрес (улица, дом, подъезд, этаж, код, квартира):")
    await state.set_state(OrderStates.waiting_for_address)
    await callback.answer()

from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

today = datetime.now().strftime("%d.%m.%Y")
tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Сегодня ({today})", callback_data=f"date_{today}")],
        [InlineKeyboardButton(text=f"📅 Завтра ({tomorrow})", callback_data=f"date_{tomorrow}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_product")]
    ]
)

@dp.message(OrderStates.waiting_for_address)
async def get_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if len(address) < 5:
        await message.answer("❗ Пожалуйста, укажите корректный адрес.")
        return

    await state.update_data(address=address)

    await message.answer("📷 Пожалуйста, отправьте фото мусора.")
    await state.set_state(OrderStates.waiting_for_photo)

@dp.message(OrderStates.waiting_for_photo)
async def photo_step(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("❗ Пожалуйста, отправьте как минимум 2 фото мусора.")
        return

    data = await state.get_data()
    product = data.get("product")
    photos = data.get("photos", [])

    if not product or product not in products:
        await message.answer("❗ Ошибка: не удалось определить услугу. Пожалуйста, начните заявку заново.")
        await state.clear()
        return

    # Добавляем новое фото
    photo_id = message.photo[-1].file_id
    photos.append(photo_id)
    await state.update_data(photos=photos)

    if product == "🛢 Крупный мусор":
        if len(photos) < 2:
            await message.answer(f"📷 Получено {len(photos)} фото. Добавьте ещё минимум {2 - len(photos)}.")
            return

        desc = data.get("large_description", "—")
        caption = (
            f"🛢 <b>Заявка на крупный мусор</b>\n"
            f"👤 Пользователь: @{message.from_user.username or 'Без ника'}\n"
            f"📝 Описание: {desc}\n"
            f"🕐 Заявка без автоматической оплаты — требуется ручная обработка."
        )

        media = [types.InputMediaPhoto(media=pid) for pid in photos[:10]]
        if media:
            media[0].caption = caption
            media[0].parse_mode = "HTML"
            await bot.send_media_group(chat_id=GROUP_CHAT_ID, media=media)
        else:
            await bot.send_message(GROUP_CHAT_ID, caption, parse_mode="HTML")

        await message.answer("📨 Заявка отправлена администратору. Ожидайте связи.")
        await state.clear()
        return

    # обычный порядок
    price = products[product]
    await state.update_data(price=price)

    await message.answer(
        f"💳 Оплата: <b>{price} ₽</b>\n"
        f"Перевод на номер <b>{PHONE_NUMBER}</b> ({BANK_NAME}).\n"
        "📸 После оплаты отправьте фото чека.",
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.waiting_for_payment_proof)

@dp.message(F.photo, StateFilter(FSMFillForm.waiting_for_receipt))
async def process_receipt(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        admin_chat_id = int(os.getenv("GROUP_CHAT_ID", "-1001234567890"))  # Замените ID на свой

        # Сохраняем файл
        file_id = message.photo[-1].file_id
        await state.update_data(receipt_photo=file_id)

        # Отправляем админу
        caption = (
            f"🧾 Новый чек об оплате\n"
            f"🆔 Заявка: {data.get('order_id', '❓')}\n"
            f"💳 Сумма: {data.get('price', 'не указана')} ₽\n"
            f"👤 Пользователь: @{message.from_user.username or message.from_user.full_name}"
        )
        await bot.send_photo(chat_id=admin_chat_id, photo=file_id, caption=caption)

        # Сообщаем клиенту
        await message.answer("✅ Чек получен. Ожидайте подтверждения от администратора.")
        await state.set_state(FSMFillForm.waiting_for_admin_confirmation)

    except Exception as e:
        print(f"Ошибка при обработке чека: {e}")
        await message.answer("❗ Произошла ошибка. Попробуйте снова или обратитесь к администратору.")

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

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "✅ Оплата подтверждена. Курьер в ближайшее время заберёт мусор.")
    await callback.answer("Оплата подтверждена.")

    # Кнопки для статуса
    status_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Мусор забрали", callback_data=f"pickedup_{user_id}")],
            [InlineKeyboardButton(text="🚮 Мусор выброшен", callback_data=f"dumped_{user_id}")]
        ]
    )

    await callback.message.answer("📦 Отслеживание заявки:", reply_markup=status_keyboard)

@dp.callback_query(F.data.startswith("pickedup_"))
async def picked_up(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "✅ Курьер забрал мусор.")
    await callback.answer("Клиенту отправлено: мусор забрали.")

@dp.callback_query(F.data.startswith("dumped_"))
async def dumped(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "🚮 Мусор выброшен. Спасибо, что пользуетесь нашим сервисом!")
    await callback.answer("Клиенту отправлено: мусор выброшен.")

# 🚀 Запуск приложения
if __name__ == "__main__":
    web.run_app(app, port=PORT)
