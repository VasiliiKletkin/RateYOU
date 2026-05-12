from aiogram import Bot
from aiogram.types import BotCommand


def _en_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="create", description="Create your profile"),
        BotCommand(command="edit", description="Edit your profile"),
        BotCommand(command="feed", description="Rate other profiles"),
        BotCommand(command="settings", description="Rating preferences"),
        BotCommand(command="premium", description="Premium subscription"),
        BotCommand(command="my_ratings", description="Who rated me (premium)"),
        BotCommand(command="refer", description="Invite friends and earn premium"),
        BotCommand(command="cancel", description="Cancel current action"),
    ]


def _ru_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="create", description="Создать анкету"),
        BotCommand(command="edit", description="Редактировать анкету"),
        BotCommand(command="feed", description="Оценивать анкеты"),
        BotCommand(command="settings", description="Настройки оценок"),
        BotCommand(command="premium", description="Премиум-подписка"),
        BotCommand(command="my_ratings", description="Кто меня оценил (премиум)"),
        BotCommand(command="refer", description="Пригласить друзей и получить премиум"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ]


async def register_commands(bot: Bot) -> None:
    """Registers bot commands shown in Telegram's `/` menu.

    The English list is the default; Russian Telegram clients see the
    `language_code="ru"` variant. Idempotent — safe to call on every startup.

    `/skip` is NOT listed because it's only valid inside FSM states (e.g.
    "skip bio" when collecting the profile). It's prompted contextually
    rather than via the menu.
    """
    await bot.set_my_commands(_en_commands())
    await bot.set_my_commands(_ru_commands(), language_code="ru")
