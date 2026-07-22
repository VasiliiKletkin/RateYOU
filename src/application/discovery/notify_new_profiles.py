from dataclasses import dataclass
from datetime import datetime

from src.application.discovery.dto import BroadcastRecipient, NewProfilesBroadcast
from src.domain.identity.repositories import IUserRepository
from src.domain.profile.repositories import IProfileRepository
from src.domain.rating.repositories import IRatingRepository


@dataclass
class NotifyAboutNewProfilesUseCase:
    """Builds the audience for a "there are new profiles" nudge.

    Deliberately returns the recipient list instead of sending anything —
    delivery is Telegram's problem and belongs to the presentation layer,
    which also keeps this testable without a Bot.

    Who gets it: people with a live profile (that's what /feed requires) who
    have gone quiet, minus banned users, minus anyone who switched broadcasts
    off in /settings, and minus anyone for whom every new profile is their own.

    The point is re-engagement, so anyone who rated since `dormant_before` is
    skipped: they are already in the feed and would see the new profiles
    without being told. Users who never rated at all count as dormant — they
    are exactly the people worth pulling in.

    Note the reason no per-user "has unrated candidates" check is needed: a
    profile created after `since` cannot have been rated by anyone yet, so
    its mere existence guarantees the recipient has something new to rate.
    """

    profile_repo: IProfileRepository
    user_repo: IUserRepository
    rating_repo: IRatingRepository

    async def execute(
        self,
        since: datetime,
        dormant_before: datetime,
    ) -> NewProfilesBroadcast:
        new_owner_ids = await self.profile_repo.list_owner_ids_created_after(since)
        if not new_owner_ids:
            return NewProfilesBroadcast(recipients=())

        audience_ids = await self.profile_repo.list_visible_owner_ids()
        users = await self.user_repo.list_by_ids(audience_ids)
        still_active = set(await self.rating_repo.list_rater_ids_active_since(dormant_before))

        total_new = len(new_owner_ids)
        recipients = []
        for user in users:
            if user.is_banned or not user.notifications_enabled:
                continue
            if user.id in still_active:
                continue
            # Their own freshly created profile isn't news to them.
            new_for_user = total_new - new_owner_ids.count(user.id)
            if new_for_user == 0:
                continue
            recipients.append(
                BroadcastRecipient(
                    user_id=user.id.value,
                    telegram_id=user.telegram_id.value,
                    language=user.language.value,
                )
            )
        return NewProfilesBroadcast(recipients=tuple(recipients))
