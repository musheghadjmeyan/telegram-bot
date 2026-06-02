print("--- [ЛОГ] ГЛОБАЛЬНЫЙ СТАРТ ФАЙЛА MAIN.PY ---")

import asyncio
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    LabeledPrice, 
    PreCheckoutQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)
from aiogram.filters import CommandStart

print("--- [ЛОГ] Стандартные библиотеки и aiogram импортированы ---")

dp = Dispatcher()
bot = None  

# ---------------- START ----------------
@dp.message(CommandStart())
async def start(msg: Message):
    text = (
        "Привет! Выбери вариант подписки для доступа к ПРИВАТКЕ:\n\n"
        "🔞 30 дней — 250 ⭐\n"
        "🔞 90 дней — 500 ⭐\n"
        "🔞 Навсегда — 750 ⭐"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить 30 дней (250 ⭐)", callback_data="buy_30")],
        [InlineKeyboardButton(text="Купить 90 дней (500 ⭐)", callback_data="buy_90")],
        [InlineKeyboardButton(text="Купить Навсегда (750 ⭐)", callback_data="buy_forever")]
    ])
    await msg.answer(text, reply_markup=kb)


# ---------------- PAYMENT ----------------
async def send_invoice(chat_id: int, title: str, amount: int, payload: str):
    prices = [LabeledPrice(label=title, amount=amount)]
    try:
        await bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description="Доступ к приватке",
            payload=payload,
            provider_token="",  
            currency="XTR",     
            prices=prices
        )
    except Exception as e:
        print(f"[ОШИБКА] Не удалось отправить инвойс: {e}", file=sys.stderr)


@dp.callback_query(F.data == "buy_30")
async def process_buy_30(callback: CallbackQuery):
    await send_invoice(callback.message.chat.id, "30 дней", 250, "sub_30")
    await callback.answer()


@dp.callback_query(F.data == "buy_90")
async def process_buy_90(callback: CallbackQuery):
    await send_invoice(callback.message.chat.id, "90 дней", 500, "sub_90")
    await callback.answer()


@dp.callback_query(F.data == "buy_forever")
async def process_buy_forever(callback: CallbackQuery):
    await send_invoice(callback.message.chat.id, "Навсегда", 750, "sub_forever")
    await callback.answer()


# ---------------- SUCCESS PAYMENT ----------------
@dp.pre_checkout_query()
async def checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def success(msg: Message):
    # Ошибка №1 исправлена: импортируем add_sub строго из database
    from database import add_sub  
    from config import CHANNEL_ID
    from config import ADMIN_ID

    payload = msg.successful_payment.invoice_payload
    user_id = msg.from_user.id
    first_name = msg.from_user.first_name
    # username = msg.from_user.username
    # username_text = f"{username}" if username else "ОТСУТСТВУЕТ (не задан в настройках ТГ)"
    

    if payload == "sub_30":
        await add_sub(user_id, 30, "30_days")
    elif payload == "sub_90":
        await add_sub(user_id, 90, "90_days")
    else:
        await add_sub(user_id, None, "forever")

    try:
        await bot.unban_chat_member(CHANNEL_ID, user_id)
        link = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
        await msg.answer(f"🎉 Оплата прошла успешно! Ссылка на канал:\n{link.invite_link}")
        tariff_name = "30 дней" if payload == "sub_30" else "90 дней" if payload == "sub_90" else "Навсегда"
        amount = 250 if payload == "sub_30" else 500 if payload == "sub_90" else 750

        try:
            admin_text = (
                "💰 НОВАЯ ПОКУПКА! 💰\n\n"
                f"👤 Пользователь: {first_name} (ID: {user_id})\n"
                # f"🔗 Телега: {username}\n"
                f"📦 Тариф: {tariff_name}\n"
                f"⭐️ Оплачено: {amount} Telegram Stars"
            )
            
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
            print(f"[ИНФО] Уведомление о покупке от пользователя {user_id} отправлено админу.")
        except Exception as admin_err:
            print(f"[ОШИБКА] Не удалось отправить уведомление админу: {admin_err}", file=sys.stderr)
    except Exception as e:
        print(f"[ОШИБКА] Не удалось создать ссылку: {e}", file=sys.stderr)


# ---------------- CLEANER ----------------
async def cleaner():
    # Импортируем get_expired и новую функцию delete_sub
    from database import get_expired, delete_sub  
    from config import CHANNEL_ID

    while True:
        try:
            expired = await get_expired()
            for (user_id,) in expired:
                try:
                    # 1. СНАЧАЛА ОТПРАВЛЯЕМ ПРЕДУПРЕЖДЕНИЕ В ЛИЧКУ:
                    try:
                        await bot.send_message(
                            chat_id=user_id, 
                            text="⚠️ Ваша подписка на приватку истекла. Вы были удалены. Чтобы вернуться, оплатите подписку снова через команду /start !"
                        )
                    except Exception as msg_error:
                        print(f"[ЛОГ] Не удалось отправить сообщение в личку {user_id}: {msg_error}")

                    # 2. ПОСЛЕ ЭТОГО КИКАЕМ ИЗ КАНАЛА:
                    await bot.ban_chat_member(CHANNEL_ID, user_id)
                    print(f"[ИНФО] Пользователь {user_id} удален из канала (подписка кончилась).")
                    
                    # 3. КРИТИЧЕСКИ ВАЖНО: Удаляем из базы, чтобы больше не спамить!
                    await delete_sub(user_id)
                    print(f"[ИНФО] Пользователь {user_id} успешно удален из базы данных.")
                    
                except Exception as ex:
                    print(f"[ЛОГ] Не удалось кикнуть {user_id}: {ex}")
        except Exception as e:
            print(f"[ОШИБКА ОЧИСТИТЕЛЯ] {e}", file=sys.stderr)
            
        await asyncio.sleep(10)  # Твой интервал для теста

# ---------------- MAIN ----------------
async def main():
    global bot
    try:
        print("--- [ШАГ 1] Чтение конфигурации... ---")
        from config import BOT_TOKEN
        # Ошибка №3 исправлена: импорт init_db строго из database
        from database import init_db

        if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER":
            print("[КРИТИЧЕСКАЯ ОШИБКА]: Забыл указать BOT_TOKEN в config.py!")
            return

        print(f"--- [ШАГ 2] Инициализация бота... ---")
        bot = Bot(token=BOT_TOKEN)
        
        print("--- [ШАГ 3] Инициализация базы данных... ---")
        await init_db()
        
        print("--- [ШАГ 4] Запуск очистителя... ---")
        asyncio.create_task(cleaner())
        
        print("--- [ШАГ 5] Сброс старых обновлений... ---")
        await bot.delete_webhook(drop_pending_updates=True)
        
        print("--- [УСПЕХ] Бот запущен! ---")
        await dp.start_polling(bot)
        
    except Exception as e:
        import traceback
        print("\n[КРИТИЧЕСКАЯ ОШИБКА]:")
        print(traceback.format_exc())



if __name__ == "__main__":
    print("--- [ЛОГ] Точка входа main сработала ---")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")


# import asyncio
# import sys
# from aiogram import Bot, Dispatcher, F
# from aiogram.types import Message
# from aiogram.filters import Command

# # ТОКЕН НОВОГО БОТА (вставь сюда токен от @BotFather)
# TOKEN = "8953871596:AAFQsU6vvGOqRlltlJk3VG7X-QEavXNKETY"

# bot = Bot(token=TOKEN)
# dp = Dispatcher()

# @dp.message(Command("start"))
# async def start_cmd(msg: Message):
#     await msg.answer("Привет! Напиши мне любое сообщение, и я выведу твой ID и юзернейм.")

# @dp.message()
# async def check_user(msg: Message):
#     user_id = msg.from_user.id
#     username = msg.from_user.username
#     first_name = msg.from_user.first_name
#     username_text = f"@{username}" if username else "ОТСУТСТВУЕТ (не задан в настройках ТГ)"
#     # Формируем красивый текст
#     text = (
#         f"📋 Данные твоего аккаунта:\n\n"
#         f"👤 Имя: {first_name}\n"
#         f"🆔 ID: {user_id}\n"
#         f"🔗 Юзернейм: {username_text}"
#     )
#     await msg.answer(text)
#     # Отправляем пользователю в чат
#     # await msg.answer(text, parse_mode="Markdown")
    
#     # Выводим в консоль сервера
#     print(f"\n[ТЕСТ] Имя: {first_name} | ID: {user_id} | Юзернейм: {username}")

# async def main():
#     print("[СТАРТ] Бот-тестер запущен и готов к работе...")
#     await dp.start_polling(bot)

# if __name__ == "__main__":
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#     asyncio.run(main())