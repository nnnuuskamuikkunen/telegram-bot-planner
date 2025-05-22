from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.builders import main_menu_kb

router = Router()


@router.message(CommandStart())
async def command_start_handler(message: types.Message):
    await message.answer(
        "<b>Добро пожаловать в наш бот</b>!\n\nОн поможет вам управляться с организацией дел легко и просто: вам нужно записать задачу в бот и выбрать время, когда она должна быть выполнена. Бот напомнит о ней за <u>24</u> и <u>1</u> час до дедлайна. \n\n"
        "Для начала работы с заметками <b>выберите действие</b>:",
        reply_markup=main_menu_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data == "show_help")
async def show_help_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "<u>Справка по работе с ботом:</u>\n\n"
        "• Для создания новой заметки нажмите <b>Добавить заметку</b>\n"
        "• Для просмотра заметок нажмите <b>Добавить заметки</b>\n"
        "• С заметкой можно делать следующие действия:\n"
        "Внести заметку в гугл-календарь можно с помощью кнопки <b>Синхронизировать с гугл-календарем</b>\n"
        "Также заметку можно редактировать, удалить или отметить как выполненную\n"
        "• Поиск заметок можно делать с помощью кнопок <b>Поиск по категории</b> и <b>Поиск по дате</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Назад", callback_data="back_to_main"
                    )
                ]
            ]
        ), parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "<b>Добро пожаловать в наш бот</b>!\n\nОн поможет вам управляться с организацией дел легко и просто: вам нужно записать задачу в бот и выбрать время, когда она должна быть выполнена. Бот напомнит о ней за <u>24</u> и <u>1</u> час до дедлайна. \n\n"
        "Для начала работы с заметками <b>выберите действие</b>:", reply_markup=main_menu_kb(), parse_mode="HTML"
    )
