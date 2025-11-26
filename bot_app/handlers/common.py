from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_app.keyboards.main import main_menu_keyboard
from bot_app.keyboards.navigation import NAV_MENU_BUTTON

router = Router()


@router.message(StateFilter("*"), F.text == NAV_MENU_BUTTON)
async def go_to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard())
