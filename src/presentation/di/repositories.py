from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.discovery.repositories import (
    IDiscoveryRepository,
    ISearchPreferencesRepository,
)
from src.domain.identity.repositories import IUserRepository
from src.domain.payment.repositories import ITransactionRepository
from src.domain.profile.repositories import IProfileRepository
from src.domain.rating.repositories import (
    IProfileScoreSummaryRepository,
    IRatingRepository,
)
from src.domain.referral.repositories import IReferralRepository
from src.domain.subscription.repositories import ISubscriptionRepository
from src.infrastructure.db.repositories.discovery import DiscoveryRepository
from src.infrastructure.db.repositories.payment import TransactionRepository
from src.infrastructure.db.repositories.profile import ProfileRepository
from src.infrastructure.db.repositories.rating import (
    ProfileScoreSummaryRepository,
    RatingRepository,
)
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.search_preferences import (
    SearchPreferencesRepository,
)
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository


class RepositoryProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def user_repo(self, session: AsyncSession) -> IUserRepository:
        return UserRepository(session=session)

    @provide
    def profile_repo(self, session: AsyncSession) -> IProfileRepository:
        return ProfileRepository(session=session)

    @provide
    def rating_repo(self, session: AsyncSession) -> IRatingRepository:
        return RatingRepository(session=session)

    @provide
    def summary_repo(
        self,
        session: AsyncSession,
    ) -> IProfileScoreSummaryRepository:
        return ProfileScoreSummaryRepository(session=session)

    @provide
    def discovery_repo(self, session: AsyncSession) -> IDiscoveryRepository:
        return DiscoveryRepository(session=session)

    @provide
    def search_preferences_repo(self, session: AsyncSession) -> ISearchPreferencesRepository:
        return SearchPreferencesRepository(session=session)

    @provide
    def subscription_repo(
        self,
        session: AsyncSession,
    ) -> ISubscriptionRepository:
        return SubscriptionRepository(session=session)

    @provide
    def transaction_repo(self, session: AsyncSession) -> ITransactionRepository:
        return TransactionRepository(session=session)

    @provide
    def referral_repo(self, session: AsyncSession) -> IReferralRepository:
        return ReferralRepository(session=session)
