from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import LabeledPrice

from src.domain.payment.entities import Transaction
from src.domain.payment.gateway import PaymentInitiation
from src.domain.payment.value_objects import Provider


@dataclass
class TelegramStarsGateway:
    """ACL between our Payment domain and the Telegram Bot API.

    Translates a clean domain `Transaction` into Telegram-flavored API calls
    (currency="XTR", empty provider token, `chat_id`). The `payer_telegram_id`
    is passed explicitly by the caller — domain `Transaction` no longer
    carries it.
    """

    provider = Provider.TELEGRAM_STARS
    bot: Bot

    async def initiate_payment(
        self,
        transaction: Transaction,
        payer_telegram_id: int,
        title: str,
        description: str,
    ) -> PaymentInitiation:
        await self.bot.send_invoice(
            chat_id=payer_telegram_id,
            title=title,
            description=description,
            payload=str(transaction.id.value),
            provider_token="",
            currency=transaction.amount.currency,
            prices=[LabeledPrice(label=title, amount=transaction.amount.amount)],
        )
        return PaymentInitiation(payment_url=None)

    async def refund(self, external_id: str, payer_telegram_id: int) -> None:
        await self.bot.refund_star_payment(
            user_id=payer_telegram_id,
            telegram_payment_charge_id=external_id,
        )
