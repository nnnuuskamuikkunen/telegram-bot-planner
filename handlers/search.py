from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.states import SearchStates, AddNoteStates
from keyboards.calendar import generate_calendar
from database import get_notes_by_date, get_notes_by_type
from datetime import datetime, date, timedelta
from config import DATABASE_NAME

router = Router()


@router.callback_query(F.data == "show_notes")
async def show_notes_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Поиск заметок:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Поиск по категории", callback_data="show_by_type"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Поиск по дате", callback_data="show_by_date"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Назад", callback_data="back_to_main"
                    )
                ],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "show_by_type")
async def ask_type_for_notes_handler(
    callback: types.CallbackQuery, state: FSMContext
):
    await callback.message.edit_text(
        "Введите категорию задач:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Отмена", callback_data="back_to_main"
                    )
                ]
            ]
        ),
        parse_mode="HTML",
    )
    await state.set_state(AddNoteStates.type_input.strip())
    await callback.answer()


@router.message(AddNoteStates.type_input, F.text)
async def handle_type_search(message: types.Message, state: FSMContext):
    search_type = message.text.strip()
    user_id = message.from_user.id
    notes = await get_notes_by_type(DATABASE_NAME, user_id, search_type)

    if not notes:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Попробовать другую категорию",
                        callback_data="show_by_type",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="В главное меню", callback_data="back_to_main"
                    )
                ],
            ]
        )
        await message.answer(
            f"В категории {search_type} заметок не найдено",
            reply_markup=keyboard,
        )
        return

    message_text = f"Заметки в категории {search_type}:\n\n"
    for note in notes:
        message_text += f"{note['note_date']} - {note['note_time']} - {note['note_text']}\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Посмотреть все заметки", callback_data="list_notes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Искать другую категорию",
                    callback_data="show_by_type",
                )
            ],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data="back_to_main"
                )
            ],
        ]
    )

    await message.answer(message_text, reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data == "show_by_date")
async def ask_date_for_notes_handler(
    callback: types.CallbackQuery, state: FSMContext
):
    await state.set_state(SearchStates.waiting_for_search_date)
    await callback.message.edit_text(
        "Выберите дату для поиска заметок:", reply_markup=generate_calendar()
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith(
        ("prev_month_", "next_month_", "select_day_", "today_", "tomorrow_")
    ),
    SearchStates.waiting_for_search_date,
)
async def process_search_date_selection(
    callback: types.CallbackQuery, state: FSMContext
):
    data = callback.data.split("_")

    if data[0] == "select":
        year, month, day = int(data[2]), int(data[3]), int(data[4])
        search_date = date(year, month, day)
        await handle_date_search(callback, search_date)
        await state.clear()
    elif data[0] == "today":
        search_date = datetime.now().date()
        await handle_date_search(callback, search_date)
        await state.clear()
    elif data[0] == "tomorrow":
        search_date = datetime.now().date() + timedelta(days=1)
        await handle_date_search(callback, search_date)
        await state.clear()
    elif data[0] == "prev":
        year, month = int(data[2]), int(data[3])
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        await callback.message.edit_reply_markup(
            reply_markup=generate_calendar(year, month)
        )
    elif data[0] == "next":
        year, month = int(data[2]), int(data[3])
        month += 1
        if month > 12:
            month = 1
            year += 1
        await callback.message.edit_reply_markup(
            reply_markup=generate_calendar(year, month)
        )

    await callback.answer()


async def handle_date_search(callback: types.CallbackQuery, search_date: date):
    user_id = callback.from_user.id
    notes = await get_notes_by_date(
        DATABASE_NAME, user_id, search_date.strftime("%d-%m-%Y")
    )

    if not notes:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Попробовать другую дату",
                        callback_data="show_by_date",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="В главное меню", callback_data="back_to_main"
                    )
                ],
            ]
        )
        await callback.message.edit_text(
            f"На {search_date.strftime('%d-%m-%Y')} заметок не найдено",
            reply_markup=keyboard,
        )
        return

    message_text = f"Заметки на {search_date.strftime('%d-%m-%Y')}:\n\n"
    for note in notes:
        message_text += f"{note['note_time']} - {note['note_text']} в категории \"{note['note_type']}\"\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Посмотреть все заметки", callback_data="list_notes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Искать другую дату", callback_data="show_by_date"
                )
            ],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data="back_to_main"
                )
            ],
        ]
    )

    await callback.message.edit_text(message_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("synchronize_"))
async def synchronize(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(note_id=int(callback.data.split("_")[1]))
    await callback.message.edit_text(
        "Введите вашу почту с доменом @gmail.com:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Отмена", callback_data="back_to_main"
                    )
                ]
            ]
        ),
        parse_mode="HTML",
    )
    await state.set_state(AddNoteStates.synchronize)
    await callback.answer()


@router.message(
    F.text.regexp(r"[a-z]+([\.-]*[a-z]*)*@gmail.com"),
    AddNoteStates.synchronize,
)
async def process_note_text(message: types.Message, state: FSMContext):
    mail = message.text.strip().lower()
    user_data = await state.get_data()
    note = await get_note_by_id(
        DATABASE_NAME, user_data["note_id"], message.from_user.id
    )
    date_time = f'{note["note_date"]} {note["note_time"]}'
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Посмотреть все заметки", callback_data="list_notes"
                )
            ],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data="back_to_main"
                )
            ],
        ]
    )

    await message.answer(
        f"Вам на почту придет ссылка, по которой надо перейти для синхронизации.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
