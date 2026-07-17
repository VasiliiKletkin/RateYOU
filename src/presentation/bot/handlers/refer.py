# ruff: noqa: RUF001  -- Russian-only handler; Cyrillic look-alikes are intended.
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.referral.get_stats import GetReferralStatsUseCase

router = Router(name="refer")


@router.message(Command("refer"))
async def on_refer(
    message: Message,
    bot: Bot,
    register_user: FromDishka[RegisterUserUseCase],
    stats_uc: FromDishka[GetReferralStatsUseCase],
) -> None:
    """Shows the user's invite link and current referral stats.

    Russian-only by product decision. The link uses the user's own
    `telegram_id` as the start payload; the inviting deep link looks like
    `https://t.me/<bot>?start=<telegram_id>`.
    """
    if message.from_user is None:
        return

    # `RegisterUserUseCase` is idempotent — calling it here makes /refer
    # work even before the user has run /start.
    user = await register_user.execute(RegisterUserRequest(telegram_id=message.from_user.id))
    stats = await stats_uc.execute(user.id)
    me = await bot.me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"

    await message.answer(
        "🎉 <b>Приглашайте друзей и получайте награды!</b>\n"
        "\n"
        "🎁 За каждую регистрацию: +1 день 💎 Premium\n"
        "\n"
        f"📊 Приглашений: <b>{stats.invitations}</b>\n"
        f"✅ Регистраций: <b>{stats.registrations}</b>\n"
        f"⏭️ До следующего бонуса: ещё "
        f"<b>{stats.referrals_until_next_milestone}</b> "
        f"{_plural_invites(stats.referrals_until_next_milestone)}\n"
        "\n"
        "🔗 Ваша персональная ссылка:\n"
        f"{link}"
    )


def _plural_invites(n: int) -> str:
    """Russian pluralisation for «приглашение»."""
    n_abs = abs(n) % 100
    last = n_abs % 10
    if 11 <= n_abs <= 14:
        return "приглашений"
    if last == 1:
        return "приглашение"
    if 2 <= last <= 4:
        return "приглашения"
    return "приглашений"
