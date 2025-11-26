from aiogram import Router

from .common import router as common_router
from .review import router as review_router
from .search import router as search_router
from .start import router as start_router


def get_bot_router() -> Router:
    root_router = Router()
    root_router.include_router(common_router)
    root_router.include_router(start_router)
    root_router.include_router(review_router)
    root_router.include_router(search_router)
    return root_router
