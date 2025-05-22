from aiogram.fsm.state import State, StatesGroup


class AddNoteStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_hour = State()
    waiting_for_minute = State()
    waiting_for_date = State()
    waiting_for_type = State()
    waiting_for_edit = State()
    type_input = State()
    hour_input = State()
    synchronize = State()


class SearchStates(StatesGroup):
    waiting_for_search_date = State()