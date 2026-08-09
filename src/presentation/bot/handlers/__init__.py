from aiogram import Router

from src.presentation.bot.handlers import (
    browse_onboarding,
    create_profile,
    edit_profile,
    feed,
    my_rating,
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
        my_rating.router,
        refer.router,
        settings.router,
        # Last: its in-state catch-all must not shadow other routers' commands
        # (/feed, /settings, …) typed while the onboarding picker is open.
        browse_onboarding.router,
    ]
