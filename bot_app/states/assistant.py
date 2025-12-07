from aiogram.fsm.state import State, StatesGroup


class AssistantState(StatesGroup):
    chatting = State()
