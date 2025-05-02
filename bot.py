@dp.message()
async def catch_chat_id(message: types.Message):
    await message.answer(f"Chat ID: {message.chat.id}")
