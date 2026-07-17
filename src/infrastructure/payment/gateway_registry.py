from dataclasses import dataclass

from src.domain.payment.exceptions import UnsupportedProvider
from src.domain.payment.gateway import IPaymentGateway
from src.domain.payment.value_objects import Provider


@dataclass
class PaymentGatewayRegistry:
    """Dispatches to the right gateway by provider.

    Constructed at composition root with all available gateways; the use case
    asks for one by `Provider` enum.
    """

    gateways: list[IPaymentGateway]

    def __post_init__(self) -> None:
        self._by_provider: dict[Provider, IPaymentGateway] = {g.provider: g for g in self.gateways}

    def get(self, provider: Provider) -> IPaymentGateway:
        try:
            return self._by_provider[provider]
        except KeyError as exc:
            raise UnsupportedProvider(f"No gateway registered for {provider}") from exc
