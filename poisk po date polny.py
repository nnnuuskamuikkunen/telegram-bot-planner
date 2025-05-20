import asyncio
import logging
from datetime import datetime, timedelta, date
import calendar
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import init_db, add_note, get_user_notes, delete_note, get_notes_for_reminders, mark_reminder_sent, \
    get_note_by_id, get_upcoming_notes, get_notes_by_date
from config import BOT_TOKEN, DATABASE_NAME

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# Состояния FSM
class AddNoteStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_hour = State()
    waiting_for_minute = State()
    waiting_for_date = State()


class SearchStates(StatesGroup):
    waiting_for_search_date = State()


# Генерация календаря
def generate_calendar(year=None, month=None):
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    kb = InlineKeyboardBuilder()

    # Заголовок с навигацией
    kb.row(
        InlineKeyboardButton(text="◀", callback_data=f"prev_month_{year}_{month}"),
        InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton(text="▶", callback_data=f"next_month_{year}_{month}")
    )

    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    # Дни месяца
    month_days = calendar.monthcalendar(year, month)
    today = now.date()

    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                day_date = date(year, month, day)
                if day_date < today:
                    row.append(InlineKeyboardButton(text="✖", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"select_day_{year}_{month}_{day}"
                    ))
        kb.row(*row)

    # Кнопки быстрого выбора
    kb.row(
        InlineKeyboardButton(text="Сегодня", callback_data=f"today_{year}_{month}"),
        InlineKeyboardButton(text="Завтра", callback_data=f"tomorrow_{year}_{month}")
    )

    return kb.as_markup()


# Генерация клавиатуры часов
def generate_hours_keyboard():
    kb = InlineKeyboardBuilder()

    for hour in range(0, 24, 6):
        row = []
        for h in range(hour, hour + 6):
            row.append(InlineKeyboardButton(
                text=f"{h:02d}",
                callback_data=f"select_hour_{h}"
            ))
        kb.row(*row)

    return kb.as_markup()


# Генерация клавиатуры минут
def generate_minutes_keyboard():
    kb = InlineKeyboardBuilder()

    for minute in range(0, 60, 15):
        row = []
        for m in range(minute, minute + 15, 5):
            row.append(InlineKeyboardButton(
                text=f"{m:02d}",
                callback_data=f"select_minute_{m}"
            ))
        kb.row(*row)

    return kb.as_markup()


"""Хендлеры команд"""


@router.message(CommandStart())
async def command_start_handler(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить заметку", callback_data="add_note")],
        [InlineKeyboardButton(text="Мои заметки", callback_data="list_notes")],
        [InlineKeyboardButton(text="Ближайшие 10 заметок", callback_data="show_upcoming")],
        [InlineKeyboardButton(text="Поиск по дате", callback_data="show_by_date")],
        [InlineKeyboardButton(text="Помощь", callback_data="show_help")]
    ])

    await message.answer(
        "Бот для управления заметками с напоминаниями\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "show_help")
async def show_help_handler(callback: types.CallbackQuery):
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
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить заметку", callback_data="add_note")],
        [InlineKeyboardButton(text="Мои заметки", callback_data="list_notes")],
        [InlineKeyboardButton(text="Ближайшие 10 заметок", callback_data="show_upcoming")],
        [InlineKeyboardButton(text="Поиск по дате", callback_data="show_by_date")],
        [InlineKeyboardButton(text="Помощь", callback_data="show_help")]
    ])
    await callback.message.edit_text("Главное меню", reply_markup=keyboard)
    await callback.answer()


"""Добавление заметок"""


@router.callback_query(F.data == "add_note")
async def add_note_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddNoteStates.waiting_for_text)
    await callback.message.edit_text(
        "Введите текст заметки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="back_to_main")]
        ])
    )
    await callback.answer()


@router.message(AddNoteStates.waiting_for_text)
async def process_note_text(message: types.Message, state: FSMContext):
    await state.update_data(note_text=message.text)
    await state.set_state(AddNoteStates.waiting_for_hour)
    await message.answer(
        "🕒 Выберите час:",
        reply_markup=generate_hours_keyboard()
    )


@router.callback_query(F.data.startswith("select_hour_"), AddNoteStates.waiting_for_hour)
async def process_hour_selection(callback: types.CallbackQuery, state: FSMContext):
    hour = int(callback.data.split("_")[2])
    await state.update_data(selected_hour=hour)
    await state.set_state(AddNoteStates.waiting_for_minute)
    await callback.message.edit_text(
        "🕒 Выберите минуты:",
        reply_markup=generate_minutes_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("select_minute_"), AddNoteStates.waiting_for_minute)
async def process_minute_selection(callback: types.CallbackQuery, state: FSMContext):
    minute = int(callback.data.split("_")[2])
    await state.update_data(selected_minute=minute)
    await state.set_state(AddNoteStates.waiting_for_date)
    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=generate_calendar()
    )
    await callback.answer()


@router.callback_query(F.data.startswith(("prev_month_", "next_month_", "select_day_", "today_", "tomorrow_")),
                       AddNoteStates.waiting_for_date)
async def process_calendar_selection(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data.split("_")

    if data[0] == "select":
        year, month, day = int(data[2]), int(data[3]), int(data[4])
        selected_date = date(year, month, day)
        user_data = await state.get_data()

        await add_note(
            DATABASE_NAME,
            callback.from_user.id,
            user_data["note_text"],
            selected_date.strftime("%Y-%m-%d"),
            f"{user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
            [InlineKeyboardButton(text="Добавить еще", callback_data="add_note")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])

        await callback.message.edit_text(
            f"Заметка добавлена:\n<b>{selected_date.strftime('%Y-%m-%d')} {user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}</b>\n{user_data['note_text']}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.clear()
    elif data[0] in ["today", "tomorrow"]:
        if data[0] == "today":
            selected_date = datetime.now().date()
        else:
            selected_date = datetime.now().date() + timedelta(days=1)

        user_data = await state.get_data()

        await add_note(
            DATABASE_NAME,
            callback.from_user.id,
            user_data["note_text"],
            selected_date.strftime("%Y-%m-%d"),
            f"{user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
            [InlineKeyboardButton(text="Добавить еще", callback_data="add_note")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])

        await callback.message.edit_text(
            f"Заметка добавлена:\n<b>{selected_date.strftime('%Y-%m-%d')} {user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}</b>\n{user_data['note_text']}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.clear()
    elif data[0] == "prev":
        year, month = int(data[2]), int(data[3])
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        await callback.message.edit_reply_markup(reply_markup=generate_calendar(year, month))
    elif data[0] == "next":
        year, month = int(data[2]), int(data[3])
        month += 1
        if month > 12:
            month = 1
            year += 1
        await callback.message.edit_reply_markup(reply_markup=generate_calendar(year, month))

    await callback.answer()


"""Просмотр и управление заметками"""


@router.callback_query(F.data == "list_notes")
async def list_notes_handler(callback: types.CallbackQuery):
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
    note_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    deleted = await delete_note(DATABASE_NAME, note_id, user_id)

    if deleted:
        await callback.answer("Заметка удалена")
        await list_notes_handler(callback)
    else:
        await callback.answer("Не удалось удалить заметку", show_alert=True)


@router.callback_query(F.data.startswith("view_"))
async def view_note_handler(callback: types.CallbackQuery):
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


@router.callback_query(F.data == "show_upcoming")
async def show_upcoming_notes_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    notes = await get_upcoming_notes(DATABASE_NAME, user_id)

    if not notes:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить заметку", callback_data="add_note")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(
            "У вас нет предстоящих заметок",
            reply_markup=keyboard
        )
        await callback.answer()
        return

    message_text = "Ваши ближайшие заметки:\n\n"
    for note in notes:
        message_text += f"📅 {note['note_date']} ⏰ {note['note_time']}\n{note['note_text']}\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
        [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
    ])

    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )
    await callback.answer()


"""Поиск по дате через календарь"""


@router.callback_query(F.data == "show_by_date")
async def ask_date_for_notes_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_search_date)
    await callback.message.edit_text(
        "Выберите дату для поиска заметок:",
        reply_markup=generate_calendar()
    )
    await callback.answer()


@router.callback_query(F.data.startswith(("prev_month_", "next_month_", "select_day_", "today_", "tomorrow_")),
                       SearchStates.waiting_for_search_date)
async def process_search_date_selection(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data.split("_")

    if data[0] == "select":
        year, month, day = int(data[2]), int(data[3]), int(data[4])
        search_date = date(year, month, day)
        await show_notes_for_date(callback, search_date)
        await state.clear()
    elif data[0] == "today":
        search_date = datetime.now().date()
        await show_notes_for_date(callback, search_date)
        await state.clear()
    elif data[0] == "tomorrow":
        search_date = datetime.now().date() + timedelta(days=1)
        await show_notes_for_date(callback, search_date)
        await state.clear()
    elif data[0] == "prev":
        year, month = int(data[2]), int(data[3])
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        await callback.message.edit_reply_markup(reply_markup=generate_calendar(year, month))
    elif data[0] == "next":
        year, month = int(data[2]), int(data[3])
        month += 1
        if month > 12:
            month = 1
            year += 1
        await callback.message.edit_reply_markup(reply_markup=generate_calendar(year, month))

    await callback.answer()


async def show_notes_for_date(callback: types.CallbackQuery, search_date: date):
    user_id = callback.from_user.id
    notes = await get_notes_by_date(DATABASE_NAME, user_id, search_date.strftime("%Y-%m-%d"))

    if not notes:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать другую дату", callback_data="show_by_date")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(
            f"На {search_date.strftime('%Y-%m-%d')} заметок не найдено",
            reply_markup=keyboard
        )
        return

    message_text = f"Заметки на {search_date.strftime('%Y-%m-%d')}:\n\n"
    for note in notes:
        message_text += f"⏰ {note['note_time']} - {note['note_text']}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
        [InlineKeyboardButton(text="Искать другую дату", callback_data="show_by_date")],
        [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
    ])

    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )


"""Напоминания"""


async def check_reminders(bot: Bot):
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
                continue

            time_diff = note_datetime - now

            if not note['reminder_24h_sent'] and time_diff <= timedelta(days=1) and time_diff > timedelta(hours=1):
                try:
                    await bot.send_message(user_id,
                                           f"🔔 Напоминание (24 часа): \"{note_text}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '24h')
                    logging.info(f"Отправлено напоминание 24h для заметки ID {note_id} пользователю {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка отправки 24h напоминания для заметки ID {note_id}: {e}")

            elif not note['reminder_1h_sent'] and time_diff <= timedelta(hours=1) and time_diff > timedelta(minutes=0):
                try:
                    await bot.send_message(user_id,
                                           f"🔔 Напоминание (1 час): \"{note_text}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '1h')
                    logging.info(f"Отправлено напоминание 1h для заметки ID {note_id} пользователю {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка отправки 1h напоминания для заметки ID {note_id}: {e}")

        await asyncio.sleep(60)


"""Основные команды для запуска"""


async def main():
    await init_db(DATABASE_NAME)
    asyncio.create_task(check_reminders(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен вручную.")
    except Exception as e:
        logging.exception(f"Произошла ошибка при запуске бота: {e}")