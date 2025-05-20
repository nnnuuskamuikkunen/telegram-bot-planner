class SearchStates(StatesGroup):
    waiting_for_search_date = State()

@router.callback_query(F.data == "show_by_date")
async def ask_date_for_notes_handler(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает дату для поиска заметок через календарь"""
    await state.set_state(SearchStates.waiting_for_search_date)
    await callback.message.edit_text(
        "Выберите дату для поиска заметок:",
        reply_markup=generate_calendar()
    )
    await callback.answer()


@router.callback_query(F.data.startswith(("prev_month_", "next_month_", "select_day_", "today_", "tomorrow_")),
                       SearchStates.waiting_for_search_date)
async def process_search_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор даты из календаря для поиска"""
    data = callback.data.split("_")

    if data[0] == "select":
        # Выбран день
        year, month, day = int(data[2]), int(data[3]), int(data[4])
        search_date = date(year, month, day)
        await show_notes_for_date(callback, search_date)
        await state.clear()
    elif data[0] == "today":
        # Сегодня
        search_date = datetime.now().date()
        await show_notes_for_date(callback, search_date)
        await state.clear()
    elif data[0] == "tomorrow":
        # Завтра
        search_date = datetime.now().date() + timedelta(days=1)
        await show_notes_for_date(callback, search_date)
        await state.clear()
    elif data[0] == "prev":
        # Переход к предыдущему месяцу
        year, month = int(data[2]), int(data[3])
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        await callback.message.edit_reply_markup(reply_markup=generate_calendar(year, month))
    elif data[0] == "next":
        # Переход к следующему месяцу
        year, month = int(data[2]), int(data[3])
        month += 1
        if month > 12:
            month = 1
            year += 1
        await callback.message.edit_reply_markup(reply_markup=generate_calendar(year, month))

    await callback.answer()


async def show_notes_for_date(callback: types.CallbackQuery, search_date: date):
    """Показывает заметки для выбранной даты"""
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