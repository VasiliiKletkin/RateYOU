from aiogram import Router

from src.presentation.bot.handlers import (
    create_profile,
    edit_profile,
    feed,
    my_ratings,
    premium,
    refer,
    settings,
    start,
)


def all_routers() -> list[Router]:
    return [
        start.router,
        create_profile.router,
        edit_profile.router,
        feed.router,
        premium.router,
        my_ratings.router,
        refer.router,
        settings.router,
    ]
