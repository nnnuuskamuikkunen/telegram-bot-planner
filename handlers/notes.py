from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from handlers.states import AddNoteStates
from keyboards.calendar import generate_calendar
from keyboards.time import generate_hours_keyboard, generate_minutes_keyboard
from database import (
    add_note,
    get_user_notes,
    delete_note,
    get_note_by_id,
    edit_notes,
)
from datetime import datetime, date, timedelta
import calendar
import logging
from config import DATABASE_NAME

router = Router()


@router.callback_query(F.data == "add_note")
async def add_note_handler(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления заметки"""
    await state.set_state(AddNoteStates.waiting_for_text)
    await callback.message.edit_text(
        "Введите текст заметки:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Отмена", callback_data="back_to_main"
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@router.message(AddNoteStates.waiting_for_text)
async def process_note_type(message: types.Message, state: FSMContext):
    """Обрабатывает текст заметки и запрашивает категорию"""
    await state.update_data(note_text=message.text)
    await state.set_state(AddNoteStates.waiting_for_type)
    await message.answer(
        "Введите категорию:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Отмена", callback_data="back_to_main"
                    )
                ]
            ]
        ),
    )


@router.message(AddNoteStates.waiting_for_type)
async def process_note_type(message: types.Message, state: FSMContext):
    """Обрабатывает категорию заметки и запрашивает часы"""
    await state.update_data(note_type=message.text)
    await state.set_state(AddNoteStates.waiting_for_hour)
    await message.answer(
        "Выберите час:", reply_markup=generate_hours_keyboard()
    )


@router.callback_query(
    F.data.startswith("select_hour_"), AddNoteStates.waiting_for_hour
)
async def process_hour_selection(
    callback: types.CallbackQuery, state: FSMContext
):
    """Обрабатывает выбор часа"""
    hour = int(callback.data.split("_")[2])
    await state.update_data(selected_hour=hour)
    await state.set_state(AddNoteStates.waiting_for_minute)
    await callback.message.edit_text(
        "Выберите минуты:", reply_markup=generate_minutes_keyboard()
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("select_minute_"), AddNoteStates.waiting_for_minute
)
async def process_minute_selection(
    callback: types.CallbackQuery, state: FSMContext
):
    """Обрабатывает выбор минут"""
    minute = int(callback.data.split("_")[2])
    await state.update_data(selected_minute=minute)
    await state.set_state(AddNoteStates.waiting_for_date)
    await callback.message.edit_text(
        "Выберите дату:", reply_markup=generate_calendar()
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith(
        ("prev_month_", "next_month_", "select_day_", "today_", "tomorrow_")
    ),
    AddNoteStates.waiting_for_date,
)
async def process_calendar_selection(
    callback: types.CallbackQuery, state: FSMContext
):
    """Обрабатывает выбор даты из календаря"""
    data = callback.data.split("_")

    if data[0] == "select":
        year, month, day = int(data[2]), int(data[3]), int(data[4])
        selected_date = date(year, month, day)
        user_data = await state.get_data()

        await add_note(
            DATABASE_NAME,
            callback.from_user.id,
            user_data["note_text"],
            user_data["note_type"],
            selected_date.strftime("%d-%m-%Y"),
            f"{user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}",
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Посмотреть все заметки",
                        callback_data="list_notes",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Добавить еще", callback_data="add_note"
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
            f"Заметка добавлена:\n<b>{selected_date.strftime('%d-%m-%Y')} {user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}</b>\n\"{user_data['note_text']}\" в категории \"{user_data['note_type']}\"",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()

    elif data[0] in ["today", "tomorrow"]:
        selected_date = (
            datetime.now().date()
            if data[0] == "today"
            else datetime.now().date() + timedelta(days=1)
        )
        user_data = await state.get_data()

        await add_note(
            DATABASE_NAME,
            callback.from_user.id,
            user_data["note_text"],
            user_data["note_type"],
            selected_date.strftime("%d-%m-%Y"),
            f"{user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}",
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Посмотреть все заметки",
                        callback_data="list_notes",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Добавить еще", callback_data="add_note"
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
            f"Заметка добавлена:\n<b>{selected_date.strftime('%d-%m-%Y')} {user_data['selected_hour']:02d}:{user_data['selected_minute']:02d}</b>\n{user_data['note_text']}, категория \"{user_data['note_type']}\"",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
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


@router.callback_query(F.data.startswith("list_notes"))
async def list_notes_handler(callback: types.CallbackQuery):
    """Показывает список заметок с пагинацией по 10 штук"""
    user_id = callback.from_user.id
    if callback.data != "list_notes":
        page = int(callback.data.split("_")[2])
    else:
        page = 0
    all_notes = await get_user_notes(DATABASE_NAME, user_id)

    if not all_notes:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Добавить заметку", callback_data="add_note"
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
            "У вас пока нет заметок", reply_markup=keyboard
        )
        await callback.answer()
        return

    total_pages = (len(all_notes) + 9) // 10
    notes_page = all_notes[page * 10 : (page + 1) * 10]

    keyboard_buttons = []
    for note in notes_page:
        note_text_short = (
            note["note_text"][:25] + "..."
            if len(note["note_text"]) > 25
            else note["note_text"]
        )
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{note['note_date']}, {note['note_time']} - {note_text_short}, категория: {note['note_type']}",
                    callback_data=f"view_{note['id']}",
                )
            ]
        )

    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"list_notes_{page - 1}"
            )
        )
    if page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text="Вперед ➡️", callback_data=f"list_notes_{page + 1}"
            )
        )

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    keyboard_buttons.append(
        [
            InlineKeyboardButton(
                text="Добавить новую заметку", callback_data="add_note"
            ),
            InlineKeyboardButton(
                text="В главное меню", callback_data="back_to_main"
            ),
        ]
    )

    await callback.message.edit_text(
        f"Ваши заметки (страница {page + 1} из {total_pages}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_"))
async def view_note_handler(callback: types.CallbackQuery):
    """Показывает полный текст заметки"""
    note_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    note = await get_note_by_id(DATABASE_NAME, note_id, user_id)

    if not note:
        await callback.answer("Заметка не найдена", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Синхронизировать с гугл-календарем",
                    callback_data=f"synchronize_{note_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Редактировать", callback_data=f"edit_{note_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отметить как выполненное",
                    callback_data=f"complete_{note_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Удалить", callback_data=f"delete_{note_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад к списку", callback_data="list_notes"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        f"Заметка от {note['note_type']} {note['note_time']} в категории \"{note['note_date']}\":\n\n"
        f"{note['note_text']}",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_"))
async def delete_note_handler(callback: types.CallbackQuery):
    """Удаляет заметку"""
    note_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    deleted = await delete_note(DATABASE_NAME, note_id, user_id)

    if deleted:
        await callback.message.edit_text("Заметка удалена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ]))
    else:
        await callback.message.edit_text("Не удалось удалить заметку",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ]))
        await callback.answer()


@router.callback_query(F.data.startswith("edit_"))
async def handle_edit_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Редактировать'"""
    await state.set_state(AddNoteStates.waiting_for_edit)
    await state.update_data(note_id=int(callback.data.split("_")[1]))
    await callback.message.edit_text(
        "Введите новый текст заметки:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Отмена", callback_data="back_to_main"
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@router.message(AddNoteStates.waiting_for_edit)
async def process_edit(message: types.Message, state: FSMContext):
    """Обрабатывает текст заметки и сохраняет изменения"""
    await state.update_data(new_text=message.text)
    user_data = await state.get_data()
    await edit_notes(
        DATABASE_NAME,
        message.from_user.id,
        user_data["note_id"],
        user_data["new_text"],
    )
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
        f"Заметка успешно изменена!", reply_markup=keyboard, parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("complete_"))
async def save_as_complete(callback: types.CallbackQuery):
     """Обработка нажатия кнопки 'Отметить как выполненное'"""
     note_id = int(callback.data.split("_")[1])
     note_data = await get_note_by_id(
        DATABASE_NAME, note_id, callback.from_user.id
    )
     new_text = f"{note_data['note_text']} ✅"
     await edit_notes(DATABASE_NAME, callback.from_user.id, note_id, new_text)
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

     await callback.message.edit_text(
        f"Заметка отмечена как выполненная!",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
