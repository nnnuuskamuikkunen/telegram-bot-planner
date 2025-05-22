import calendar
from datetime import datetime, date
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def generate_calendar(year=None, month=None):
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    kb = InlineKeyboardBuilder()

    kb.row(
        InlineKeyboardButton(text="◀", callback_data=f"prev_month_{year}_{month}"),
        InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton(text="▶", callback_data=f"next_month_{year}_{month}")
    )

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

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

    kb.row(
        InlineKeyboardButton(text="Сегодня", callback_data=f"today_{year}_{month}"),
        InlineKeyboardButton(text="Завтра", callback_data=f"tomorrow_{year}_{month}")
    )

    return kb.as_markup()