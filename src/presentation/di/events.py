from dishka import Provider, Scope, provide

from src.application.rating.handlers import OnRatingGiven, OnRatingWithdrawn
from src.application.subscription.handlers import OnPaymentConfirmed, OnPaymentRefunded
from src.domain.payment.events import PaymentConfirmed, PaymentRefunded
from src.domain.rating.events import RatingGiven, RatingWithdrawn
from src.domain.shared.event_bus import IEventBus
from src.infrastructure.events.in_memory_bus import InMemoryEventBus


class EventsProvider(Provider):
    """Wires the synchronous event bus and its handlers.

    REQUEST scope so each Telegram update / HTTP request gets a bus whose
    handlers hold REQUEST-scope repositories on the same AsyncSession as the
    publishing use case. Handler writes therefore commit (or rollback) with
    the same UoW.
    """

    scope = Scope.REQUEST

    on_rating_given = provide(OnRatingGiven)
    on_rating_withdrawn = provide(OnRatingWithdrawn)
    on_payment_confirmed = provide(OnPaymentConfirmed)
    on_payment_refunded = provide(OnPaymentRefunded)

    @provide
    def event_bus(
        self,
        rating_given: OnRatingGiven,
        rating_withdrawn: OnRatingWithdrawn,
        payment_confirmed: OnPaymentConfirmed,
        payment_refunded: OnPaymentRefunded,
    ) -> IEventBus:
        bus = InMemoryEventBus()
        bus.subscribe(RatingGiven, rating_given.handle)
        bus.subscribe(RatingWithdrawn, rating_withdrawn.handle)
        bus.subscribe(PaymentConfirmed, payment_confirmed.handle)
        bus.subscribe(PaymentRefunded, payment_refunded.handle)
        return bus
