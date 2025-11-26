from aiogram.fsm.state import State, StatesGroup


class ProfileState(StatesGroup):
    waiting_for_city = State()
