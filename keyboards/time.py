from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

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