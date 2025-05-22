from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить заметку", callback_data="add_note")],
        [InlineKeyboardButton(text="Мои заметки", callback_data="list_notes")],
        [InlineKeyboardButton(text="Поиск заметок", callback_data="show_notes")],
        [InlineKeyboardButton(text="Помощь", callback_data="show_help")]
    ])