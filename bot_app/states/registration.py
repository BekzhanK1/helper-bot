from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    city = State()
    role = State()
