from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.builders import main_menu_kb

router = Router()

@router.message(CommandStart())
async def command_start_handler(message: types.Message):
    await message.answer(
        "Бот для управления заметками с напоминаниями\n\nВыберите действие:",
        reply_markup=main_menu_kb()
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

@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Главное меню",
        reply_markup=main_menu_kb()
    )