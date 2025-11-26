from aiogram.fsm.state import State, StatesGroup


class AddReviewState(StatesGroup):
    place_name = State()
    place_selection = State()
    address = State()
    category = State()
    rating = State()
    text = State()
    photos = State()
