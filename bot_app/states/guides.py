from aiogram.fsm.state import State, StatesGroup


class GuidesState(StatesGroup):
    category = State()
    topic_selection = State()
    guide_content = State()
