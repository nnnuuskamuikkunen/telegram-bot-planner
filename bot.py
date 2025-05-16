import asyncio
import logging
from datetime import datetime, timedelta
import re

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import init_db, add_note, get_user_notes, delete_note, get_notes_for_reminders, mark_reminder_sent
from config import BOT_TOKEN, DATABASE_NAME # Импортируем из config.py

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router() # Используем Router для лучшей организации хэндлеров
dp.include_router(router)

# --- Хэндлеры команд ---

@router.message(CommandStart())
async def command_start_handler(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "Привет! Я бот для заметок с напоминаниями.\n\n"
        "Чтобы добавить заметку, отправь сообщение в формате:\n"
        "```\nЧЧ:ММ, ГГГГ-ММ-ДД, Текст заметки\n```\n"
        "Например: `18:00, 2023-12-31, Заказать новогодний торт`\n\n"
        "Команды:\n"
        "/notes - Посмотреть мои заметки\n"
        "/help - Показать это сообщение снова"
    )

@router.message(Command("help"))
async def command_help_handler(message: types.Message):
    """Обработчик команды /help"""
    await command_start_handler(message) # Просто повторяем сообщение команды /start

@router.message(Command("notes"))
async def command_notes_handler(message: types.Message):
    """Обработчик команды /notes: показывает заметки пользователя."""
    user_id = message.from_user.id
    notes = await get_user_notes(DATABASE_NAME, user_id)

    if not notes:
        await message.answer("У вас пока нет заметок.")
        return

    response = "Ваши заметки:\n\n"
    keyboard_buttons = []
    for note in notes:
        # Используем ID заметки для кнопки удаления
        response += f"#{note['id']}: {note['note_date']} {note['note_time']} - {note['note_text']}\n"
        keyboard_buttons.append(
            [InlineKeyboardButton(text=f"Удалить #{note['id']}", callback_data=f"delete_{note['id']}")]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(response, reply_markup=keyboard)


# --- Хэндлер для добавления заметок ---

# Паттерн для ожидаемого формата: ЧЧ:ММ, ГГГГ-ММ-ДД, Текст
NOTE_FORMAT_PATTERN = re.compile(r'^(\d{2}:\d{2}),\s*(\d{4}-\d{2}-\d{2}),\s*(.+)$')

@router.message() # Обрабатываем текстовые сообщения, которые не являются командами
async def handle_note_input(message: types.Message):
    """Обрабатывает входящие текстовые сообщения как попытку добавить заметку."""
    user_id = message.from_user.id
    text = message.text.strip()

    match = NOTE_FORMAT_PATTERN.match(text)

    if not match:
        # Если формат не соответствует, возможно, это просто обычное сообщение
        # Можно проигнорировать или добавить хэндлер для "свободного" текста,
        # но по условию ожидается конкретный формат.
        # Для простоты, если не совпадает с форматом заметки, не реагируем.
        # Или можно сообщить пользователю о неправильном формате, если это нежелательное поведение.
        await message.answer("Неверный формат заметки. Используйте: ЧЧ:ММ, ГГГГ-ММ-ДД, Текст")
        return

    time_str, date_str, note_text = match.groups()

    try:
        # Проверяем корректность даты и времени
        note_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        # Опционально: проверить, что дата и время в будущем
        if note_datetime < datetime.now() - timedelta(minutes=1): # Небольшой запас на парсинг
             await message.answer("Не могу добавить заметку в прошлое. Пожалуйста, укажите будущую дату и время.")
             return

    except ValueError:
        await message.answer("Неверный формат даты или времени. Используйте: ЧЧ:ММ, ГГГГ-ММ-ДД")
        return

    # Сохраняем заметку в базу данных
    await add_note(DATABASE_NAME, user_id, note_text, date_str, time_str)

    await message.answer(f"Заметка добавлена: {date_str} {time_str} - \"{note_text}\"")


# --- Хэндлер для кнопок удаления заметок ---

@router.callback_query(F.data.startswith("delete_"))
async def callback_delete_note(callback_query: types.CallbackQuery):
    """Обрабатывает нажатия на кнопки "Удалить заметку"."""
    note_id_str = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id

    try:
        note_id = int(note_id_str)
    except ValueError:
        await callback_query.answer("Ошибка: некорректный ID заметки.", show_alert=True)
        return

    deleted = await delete_note(DATABASE_NAME, note_id, user_id)

    if deleted:
        await callback_query.answer(f"Заметка #{note_id} удалена.", show_alert=True)
        # Опционально: обновить сообщение со списком заметок
        # Для простоты сейчас просто отвечаем всплывающим окном
        # Можно вызвать command_notes_handler(callback_query.message)
        # или обновить текст существующего сообщения callback_query.message.edit_text(...)
    else:
        await callback_query.answer(f"Ошибка при удалении заметки #{note_id}. Возможно, она уже была удалена или не существует.", show_alert=True)

    await callback_query.message.edit_reply_markup(reply_markup=None) # Убираем кнопки после удаления
    await callback_query.answer() # Важно ответить на callback Query


# --- Задача для проверки напоминаний ---

async def check_reminders(bot: Bot):
    """Фоновая задача для проверки и отправки напоминаний."""
    while True:
        logging.info("Проверка напоминаний...")
        now = datetime.now()
        notes_to_check = await get_notes_for_reminders(DATABASE_NAME)

        for note in notes_to_check:
            note_id = note['id']
            user_id = note['user_id']
            note_text = note['note_text']
            note_date_str = note['note_date']
            note_time_str = note['note_time']

            try:
                note_datetime = datetime.strptime(f"{note_date_str} {note_time_str}", "%Y-%m-%d %H:%M")
            except ValueError:
                logging.error(f"Неверный формат даты/времени для заметки ID {note_id}: {note_date_str} {note_time_str}")
                continue # Пропускаем эту заметку

            time_diff = note_datetime - now

            # Напоминание за 24 часа
            if not note['reminder_24h_sent'] and time_diff <= timedelta(days=1) and time_diff > timedelta(hours=1):
                try:
                    await bot.send_message(user_id, f"🕒 Напоминание (24 часа): \"{note_text}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '24h')
                    logging.info(f"Отправлено напоминание 24h для заметки ID {note_id} пользователю {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка отправки 24h напоминания для заметки ID {note_id}: {e}")

            # Напоминание за 1 час
            elif not note['reminder_1h_sent'] and time_diff <= timedelta(hours=1) and time_diff > timedelta(minutes=0):
                 try:
                    await bot.send_message(user_id, f"⏰ Напоминание (1 час): \"{note_text}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '1h')
                    logging.info(f"Отправлено напоминание 1h для заметки ID {note_id} пользователю {user_id}")
                 except Exception as e:
                    logging.error(f"Ошибка отправки 1h напоминания для заметки ID {note_id}: {e}")

            # Опционально: удалить заметку, если её время прошло и оба напоминания отправлены
            # if note['reminder_24h_sent'] and note['reminder_1h_sent'] and note_datetime <= now:
            #     await delete_note(DATABASE_NAME, note_id, user_id)
            #     logging.info(f"Заметка ID {note_id} удалена после отправки напоминаний.")


        await asyncio.sleep(60) # Проверяем напоминания каждую минуту

# --- Главная функция запуска ---

async def main():
    """Главная функция для запуска бота и фоновой задачи."""
    # Инициализируем базу данных перед запуском бота
    await init_db(DATABASE_NAME)

    # Создаем фоновую задачу для проверки напоминаний
    asyncio.create_task(check_reminders(bot))

    # Запускаем опрос обновлений бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен вручную.")
    except Exception as e:
        logging.exception(f"Произошла ошибка при запуске бота: {e}")
