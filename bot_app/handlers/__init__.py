from aiogram import Router

from .start import router as start_router


def get_bot_router() -> Router:
    root_router = Router()
    root_router.include_router(start_router)
    return root_router
