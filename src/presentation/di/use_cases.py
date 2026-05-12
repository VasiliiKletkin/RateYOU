from dishka import Provider, Scope, provide

from src.application.discovery.get_next_profile import GetNextProfileForRatingUseCase
from src.application.discovery.search_preferences import (
    GetSearchPreferencesUseCase,
    UpdateGenderPreferenceUseCase,
    UpdateMinRatingUseCase,
)
from src.application.discovery.skip_profile import SkipProfileUseCase
from src.application.identity.get_user import GetUserByTelegramIdUseCase
from src.application.identity.register_user import RegisterUserUseCase
from src.application.identity.update_language import UpdateUserLanguageUseCase
from src.application.payment.confirm_payment import ConfirmPaymentUseCase
from src.application.payment.create_invoice import CreatePremiumInvoiceUseCase
from src.application.payment.refund_payment import RefundPaymentUseCase
from src.application.profile.create_profile import CreateProfileUseCase
from src.application.profile.edit_profile import EditProfileUseCase
from src.application.profile.get_profile import GetMyProfileUseCase
from src.application.profile.visibility import HideProfileUseCase, ShowProfileUseCase
from src.application.rating.get_profile_score import GetProfileScoreUseCase
from src.application.rating.list_incoming_ratings import ListIncomingRatingsUseCase
from src.application.rating.rate_user import RateUserUseCase
from src.application.rating.withdraw_rating import WithdrawRatingUseCase
from src.application.subscription.activate_premium import ActivatePremiumUseCase
from src.application.subscription.get_premium import GetMyPremiumUseCase
from src.application.subscription.list_tiers import ListTiersUseCase
from src.application.subscription.revoke_premium import RevokePremiumUseCase


class UseCaseProvider(Provider):
    """Wires every use case at REQUEST scope.

    Dishka resolves each use case's constructor dependencies (repos, gateways,
    UoW) automatically from other providers.
    """

    scope = Scope.REQUEST

    # Identity
    register_user = provide(RegisterUserUseCase)
    get_user_by_telegram_id = provide(GetUserByTelegramIdUseCase)
    update_user_language = provide(UpdateUserLanguageUseCase)

    # Profile
    create_profile = provide(CreateProfileUseCase)
    edit_profile = provide(EditProfileUseCase)
    hide_profile = provide(HideProfileUseCase)
    show_profile = provide(ShowProfileUseCase)
    get_my_profile = provide(GetMyProfileUseCase)

    # Rating
    rate_user = provide(RateUserUseCase)
    withdraw_rating = provide(WithdrawRatingUseCase)
    get_profile_score = provide(GetProfileScoreUseCase)
    list_incoming_ratings = provide(ListIncomingRatingsUseCase)

    # Discovery
    get_next_profile = provide(GetNextProfileForRatingUseCase)
    skip_profile = provide(SkipProfileUseCase)
    get_search_preferences = provide(GetSearchPreferencesUseCase)
    update_gender_preference = provide(UpdateGenderPreferenceUseCase)
    update_min_rating = provide(UpdateMinRatingUseCase)

    # Subscription
    activate_premium = provide(ActivatePremiumUseCase)
    revoke_premium = provide(RevokePremiumUseCase)
    get_my_premium = provide(GetMyPremiumUseCase)
    list_tiers = provide(ListTiersUseCase)

    # Payment
    create_premium_invoice = provide(CreatePremiumInvoiceUseCase)
    confirm_payment = provide(ConfirmPaymentUseCase)
    refund_payment = provide(RefundPaymentUseCase)
