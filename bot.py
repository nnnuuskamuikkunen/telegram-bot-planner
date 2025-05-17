import asyncio
import logging
from datetime import datetime, timedelta
import re

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import init_db, add_note, get_user_notes, delete_note, get_notes_for_reminders, mark_reminder_sent, get_note_by_id
from config import BOT_TOKEN, DATABASE_NAME # Импортируем из config.py

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router() # Используем Router для лучшей организации хэндлеров
dp.include_router(router)



"""хендлеры команд"""

@router.message(CommandStart())
async def command_start_handler(message: types.Message):
    """Обработчик команды /start с кнопками для управления заметками"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить заметку", callback_data="add_note")],
        [InlineKeyboardButton(text="Мои заметки", callback_data="list_notes")],
        [InlineKeyboardButton(text="Помощь", callback_data="show_help")]
    ])
    
    await message.answer(
        "Бот для управления заметками с напоминаниями\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "show_help")
async def show_help_handler(callback: types.CallbackQuery):
    """Показывает справку"""
    await callback.message.edit_text(
        "Справка по работе с ботом:\n\n"
        "1. Для добавления заметки нажмите 'Добавить заметку'\n"
        "2. Для просмотра списка заметок нажмите 'Мои заметки'\n"
        "3. Удалять заметки можно прямо из списка\n\n"
        "Бот автоматически напомнит о заметке в указанное время!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: types.CallbackQuery):
    """Возвращает в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить заметку", callback_data="add_note")],
        [InlineKeyboardButton(text="Мои заметки", callback_data="list_notes")],
        [InlineKeyboardButton(text="Помощь", callback_data="show_help")]
    ])
    await callback.message.edit_text("главное меню", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "add_note")
async def add_note_handler(callback: types.CallbackQuery):
    """Начинает процесс добавления заметки"""
    await callback.message.edit_text(
        "Введите данные заметки в формате:\n\n"
        "<b>ЧЧ:ММ, ГГГГ-ММ-ДД, Текст заметки</b>\n\n"
        "Пример: <code>18:00, 2023-12-31, Заказать торт</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="back_to_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()



"""добавление заметок"""

NOTE_FORMAT_PATTERN = re.compile(r'^(\d{2}:\d{2}),\s*(\d{4}-\d{2}-\d{2}),\s*(.+)$')

@router.message(F.text)
async def handle_note_input(message: types.Message):
    """Обрабатывает ввод заметки после нажатия кнопки добавления"""
    # Проверяем, что пользователь начал процесс добавления заметки
    # (можно добавить флаг в БД или кэш, что пользователь в процессе добавления)
    
    text = message.text.strip()
    match = NOTE_FORMAT_PATTERN.match(text)

    if not match:
        await message.answer(
            "Неверный формат. Используйте: ЧЧ:ММ, ГГГГ-ММ-ДД, Текст\n\n"
            "Пример: <code>18:00, 2023-12-31, Заказать торт</code>",
            parse_mode="HTML"
        )
        return

    time_str, date_str, note_text = match.groups()

    try:
        note_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if note_datetime < datetime.now():
            await message.answer("Нельзя добавить заметку в прошлом времени!")
            return

        await add_note(DATABASE_NAME, message.from_user.id, note_text, date_str, time_str)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
            [InlineKeyboardButton(text="Добавить еще", callback_data="add_note")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])
        
        await message.answer(
            f"Заметка добавлена:\n<b>{date_str} {time_str}</b>\n{note_text}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("Неверный формат даты или времени!")

@router.callback_query(F.data == "list_notes")
async def list_notes_handler(callback: types.CallbackQuery):
    """Показывает список заметок с кнопками управления"""
    user_id = callback.from_user.id
    notes = await get_user_notes(DATABASE_NAME, user_id)

    if not notes:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить заметку", callback_data="add_note")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(
            "У вас пока нет заметок",
            reply_markup=keyboard
        )
        await callback.answer()
        return

    keyboard_buttons = []
    for note in notes:
        note_text_short = note['note_text'][:25] + "..." if len(note['note_text']) > 25 else note['note_text']
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{note['note_date']}, {note['note_time']} - {note_text_short}",
                callback_data=f"view_{note['id']}"
            )
        ])
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="Редактировать",
                callback_data=f"edit_{note['id']}"
            ),
            InlineKeyboardButton(
                text="Удалить",
                callback_data=f"delete_{note['id']}"
            )
        ])

    keyboard_buttons.append([
        InlineKeyboardButton(text="Добавить новую заметку", callback_data="add_note"),
        InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")
    ])

    await callback.message.edit_text(
        "Ваши заметки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_"))
async def delete_note_handler(callback: types.CallbackQuery):
    """Удаляет заметку"""
    note_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    deleted = await delete_note(DATABASE_NAME, note_id, user_id)
    
    if deleted:
        await callback.answer("Заметка удалена")
        # Обновляем список заметок
        await list_notes_handler(callback)
    else:
        await callback.answer("Не удалось удалить заметку", show_alert=True)


@router.callback_query(F.data.startswith("view_"))
async def view_note_handler(callback: types.CallbackQuery):
    """Показывает полный текст заметки"""
    note_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    note = await get_note_by_id(DATABASE_NAME, note_id, user_id)
    
    if not note:
        await callback.answer("Заметка не найдена", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать", callback_data=f"edit_{note_id}")],
        [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{note_id}")],
        [InlineKeyboardButton(text="Назад к списку", callback_data="list_notes")]
    ])
    
    await callback.message.edit_text(
        f"Заметка от {note['note_date']} {note['note_time']}:\n\n"
        f"{note['note_text']}",
        reply_markup=keyboard
    )
    await callback.answer()



"""напоминания"""

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
                    await bot.send_message(user_id, f"Напоминание (24 часа): \"{note_text}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '24h')
                    logging.info(f"Отправлено напоминание 24h для заметки ID {note_id} пользователю {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка отправки 24h напоминания для заметки ID {note_id}: {e}")

            # Напоминание за 1 час
            elif not note['reminder_1h_sent'] and time_diff <= timedelta(hours=1) and time_diff > timedelta(minutes=0):
                 try:
                    await bot.send_message(user_id, f"Напоминание (1 час): \"{note_text}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '1h')
                    logging.info(f"Отправлено напоминание 1h для заметки ID {note_id} пользователю {user_id}")
                 except Exception as e:
                    logging.error(f"Ошибка отправки 1h напоминания для заметки ID {note_id}: {e}")

            # Опционально: удалить заметку, если её время прошло и оба напоминания отправлены
            # if note['reminder_24h_sent'] and note['reminder_1h_sent'] and note_datetime <= now:
            #     await delete_note(DATABASE_NAME, note_id, user_id)
            #     logging.info(f"Заметка ID {note_id} удалена после отправки напоминаний.")


        await asyncio.sleep(60) # Проверяем напоминания каждую минуту



"""основные команды для запуска""" 

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