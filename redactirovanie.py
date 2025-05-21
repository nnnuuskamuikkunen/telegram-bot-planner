# редактирование задач
@router.callback_query(F.data.startswith("edit_"))
async def handle_edit_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Редактировать'"""
    await state.set_state(AddNoteStates.waiting_for_edit)
    await state.update_data(note_id=int(callback.data.split('_')[1]))
    await callback.message.edit_text(
        "Введите новый текст заметки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@router.message(AddNoteStates.waiting_for_edit)
async def process_edit(message: types.Message, state: FSMContext):
    """Обрабатывает текст заметки и сохраняет изменения"""
    await state.update_data(new_text=message.text)
    user_data = await state.get_data()
    await edit_notes(DATABASE_NAME, message.from_user.id, user_data["note_id"], user_data["new_text"])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])

    await message.answer(
            f"Заметка успешно изменена!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    await state.clear()

# отметка как выполненное
@router.callback_query(F.data.startswith("complete_"))
async def save_as_complete(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Отметить как выполненное'"""
    
    note_id=int(callback.data.split('_')[1])
    note_data = await get_note_by_id(DATABASE_NAME, note_id, callback.from_user.id)
    new_text = f"{note_data["note_text"]} ✅"
    await edit_notes(DATABASE_NAME, callback.from_user.id, note_id, new_text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть все заметки", callback_data="list_notes")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_to_main")]
        ])

    await callback.message.edit_text(
            f"Заметка отмечена как выполненная!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )



