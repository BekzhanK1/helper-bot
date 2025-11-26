from aiogram.fsm.state import State, StatesGroup


class SearchState(StatesGroup):
    category = State()
    results = State()
