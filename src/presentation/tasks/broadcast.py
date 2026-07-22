import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.utils.i18n import gettext as _
from dishka.integrations.taskiq import FromDishka, inject
from redis.asyncio import Redis

from src.application.discovery.dto import BroadcastRecipient
from src.application.discovery.notify_new_profiles import NotifyAboutNewProfilesUseCase
from src.presentation.bot.i18n import i18n
from src.presentation.tasks.broker import broker

log = logging.getLogger(__name__)

# Marks how far the previous run got. Kept in Redis rather than the DB: it is
# operational bookkeeping, not domain state.
_WATERMARK_KEY = "broadcast:new_profiles:last_run_at"

# With no watermark (first ever run, or Redis was wiped) look back a day
# instead of announcing every profile ever created.
_FIRST_RUN_LOOKBACK = timedelta(hours=24)

# Someone who rated within this window is still using the feed and would see
# the new profiles anyway — nudging them would be noise.
_DORMANT_AFTER = timedelta(days=7)

# Hard ceiling per person, independent of the dormancy rule: a permanently
# inactive user would otherwise qualify every single day. Set on claim rather
# than after a successful send — if the run dies mid-way, a retry must not
# message the first half twice.
_NUDGE_COOLDOWN_KEY = "broadcast:new_profiles:nudged:{user_id}"
_NUDGE_COOLDOWN_SECONDS = 7 * 24 * 3600

# Telegram allows ~30 messages/second to different chats; stay under it.
_MESSAGES_PER_SECOND = 25


@broker.task(
    task_name="broadcast_new_profiles",
    # Once a day, early evening UTC. Frequent enough to feel alive, rare
    # enough not to read as spam.
    schedule=[{"cron": "0 18 * * *"}],
)
# patch_module=True is the non-deprecated dishka behaviour; without it the
# integration emits a DeprecationWarning on import.
@inject(patch_module=True)
async def broadcast_new_profiles(
    bot: FromDishka[Bot],
    redis: FromDishka[Redis],
    notify: FromDishka[NotifyAboutNewProfilesUseCase],
) -> None:
    """Pulls lapsed users back when profiles they haven't seen have appeared.

    Silent when nothing new showed up — an empty nudge trains users to
    ignore the bot.
    """
    # Stamped before the query: profiles created while this run is in flight
    # must belong to the next window, not fall through the crack.
    started_at = datetime.now(UTC)
    since = await _read_watermark(redis)

    broadcast = await notify.execute(since, dormant_before=started_at - _DORMANT_AFTER)
    if not broadcast.recipients:
        log.info(f"Nothing to announce since {since.isoformat()}")
        await _write_watermark(redis, started_at)
        return

    sent, failed, skipped = await _send_all(bot, redis, broadcast.recipients)
    await _write_watermark(redis, started_at)
    log.info(
        f"New-profile broadcast finished: sent={sent} failed={failed} skipped_by_cooldown={skipped}"
    )


async def _send_all(
    bot: Bot,
    redis: Redis,
    recipients: tuple[BroadcastRecipient, ...],
) -> tuple[int, int, int]:
    sent = 0
    failed = 0
    skipped = 0
    for index, recipient in enumerate(recipients):
        if not await _claim_cooldown(redis, recipient.user_id):
            skipped += 1
            continue
        # Each message renders in that user's stored language, not the
        # locale of whoever happened to trigger the run.
        with i18n.use_locale(recipient.language):
            text = _("✨ New profiles have appeared.\nOpen /feed to rate them.")
        if await _send_one(bot, recipient.telegram_id, text):
            sent += 1
        else:
            failed += 1
        if (index + 1) % _MESSAGES_PER_SECOND == 0:
            await asyncio.sleep(1)
    return sent, failed, skipped


async def _claim_cooldown(redis: Redis, user_id: UUID) -> bool:
    """Reserves this user's weekly slot. False means they were nudged recently.

    SET NX EX in one round trip, so two workers racing the same recipient
    can't both win.
    """
    claimed = await redis.set(
        _NUDGE_COOLDOWN_KEY.format(user_id=user_id),
        "1",
        ex=_NUDGE_COOLDOWN_SECONDS,
        nx=True,
    )
    return bool(claimed)


async def _send_one(bot: Bot, telegram_id: int, text: str) -> bool:
    try:
        await bot.send_message(telegram_id, text)
        return True
    except TelegramRetryAfter as exc:
        # Flood control: wait exactly as long as Telegram asked, then retry once.
        await asyncio.sleep(exc.retry_after)
        try:
            await bot.send_message(telegram_id, text)
            return True
        except TelegramAPIError as retry_exc:
            log.warning(f"Broadcast to {telegram_id} failed after retry: {retry_exc}")
            return False
    except TelegramForbiddenError:
        # Blocked the bot or deleted the account — expected, not worth a warning.
        return False
    except TelegramAPIError as exc:
        log.warning(f"Broadcast to {telegram_id} failed: {exc}")
        return False


async def _read_watermark(redis: Redis) -> datetime:
    raw = await redis.get(_WATERMARK_KEY)
    if raw is None:
        return datetime.now(UTC) - _FIRST_RUN_LOOKBACK
    try:
        return datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
    except ValueError:
        log.warning(f"Unreadable broadcast watermark {raw!r}; falling back to lookback")
        return datetime.now(UTC) - _FIRST_RUN_LOOKBACK


async def _write_watermark(redis: Redis, moment: datetime) -> None:
    await redis.set(_WATERMARK_KEY, moment.isoformat())
