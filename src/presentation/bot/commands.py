from aiogram import Bot
from aiogram.types import BotCommand
from aiogram.utils.i18n import I18n
from aiogram.utils.i18n import gettext as _

from src.domain.identity.value_objects import Language


def _build_commands() -> list[BotCommand]:
    """Renders the command list under the currently-active i18n locale.

    Must be called inside ``i18n.context() / i18n.use_locale(...)`` so
    the `_(...)` calls resolve to the right translation.
    """
    return [
        BotCommand(command="start", description=_("Start the bot")),
        BotCommand(command="create", description=_("Create your profile")),
        BotCommand(command="edit", description=_("Edit your profile")),
        BotCommand(command="feed", description=_("Rate other profiles")),
        BotCommand(command="settings", description=_("Rating preferences")),
        BotCommand(command="premium", description=_("Premium subscription")),
        BotCommand(command="my_rating", description=_("My rating & who rated me")),
        BotCommand(command="refer", description=_("Invite friends and earn premium")),
        BotCommand(command="cancel", description=_("Cancel current action")),
    ]


async def register_commands(bot: Bot, i18n: I18n) -> None:
    """Registers bot commands shown in Telegram's `/` menu, per language.

    English is the default (no ``language_code``). For every other supported
    `Language`, descriptions are rendered under that locale and registered
    via ``set_my_commands(..., language_code=...)``. Idempotent — Telegram
    overwrites the previous list on each call.

    `/skip` is NOT listed because it's only valid inside FSM states (e.g.
    "skip bio" when collecting the profile). It's prompted contextually
    rather than via the menu.
    """
    # Default (English) — used by any client whose locale isn't in our list.
    with i18n.context(), i18n.use_locale(Language.EN.value):
        await bot.set_my_commands(_build_commands())

    for lang in Language:
        if lang is Language.EN:
            continue
        with i18n.context(), i18n.use_locale(lang.value):
            await bot.set_my_commands(_build_commands(), language_code=lang.value)
