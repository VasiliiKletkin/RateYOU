class PremiumRequired(Exception):
    """Raised by a use case when the action it performs is gated on the caller
    having an active premium subscription.

    Lives in `domain/shared/` because it's a cross-context contract: the
    Subscription domain authoritatively defines what "premium" means, but
    the exception is raised from any use case that *requires* premium
    (currently `ListIncomingRatingsUseCase` in Rating; more may follow).
    Handlers in the presentation layer catch it to render a localized
    upsell message — they should never need to import from a specific
    bounded context just for this signal.
    """
