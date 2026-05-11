from aiogram import Bot
from dishka import Provider, Scope, provide

from src.domain.payment.gateway import IPaymentGateway, IPaymentGatewayRegistry
from src.infrastructure.payment.gateway_registry import PaymentGatewayRegistry
from src.infrastructure.payment.telegram_stars import TelegramStarsGateway


class PaymentProvider(Provider):
    """Builds the gateway registry. When more providers are added, list them here."""

    scope = Scope.APP

    @provide
    def telegram_stars_gateway(self, bot: Bot) -> TelegramStarsGateway:
        return TelegramStarsGateway(bot=bot)

    @provide
    def gateway_registry(
        self,
        tg_stars: TelegramStarsGateway,
    ) -> IPaymentGatewayRegistry:
        gateways: list[IPaymentGateway] = [tg_stars]
        return PaymentGatewayRegistry(gateways=gateways)
