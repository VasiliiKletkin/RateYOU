from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import ngettext
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.payment.confirm_payment import ConfirmPaymentUseCase
from src.application.payment.create_invoice import CreatePremiumInvoiceUseCase
from src.application.payment.dto import (
    ConfirmPaymentRequest,
    CreatePremiumInvoiceRequest,
)
from src.application.subscription.get_premium import GetMyPremiumUseCase
from src.application.subscription.list_tiers import ListTiersUseCase
from src.domain.payment.exceptions import (
    InvalidStatusTransition,
    TransactionNotFound,
)
from src.domain.subscription.exceptions import InvalidTier
from src.presentation.bot.i18n import normalize_language
from src.presentation.bot.keyboards import tiers_keyboard

router = Router(name="premium")


def _expires_phrase(days: int) -> str:
    """Pluralised 'Expires in N day(s)' — `ngettext` picks the right form."""
    return ngettext(
        "Expires in {days} day.",
        "Expires in {days} days.",
        days,
    ).format(days=days)


@router.message(Command("premium"))
async def cmd_premium(
    message: Message,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_premium: FromDishka[GetMyPremiumUseCase],
    list_tiers: FromDishka[ListTiersUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
        )
    )

    current = await get_my_premium.execute(user.id)
    tiers = await list_tiers.execute()

    if current is not None:
        header = _(
            "<b>Your premium: {tier}</b>\n"
            "{expires}\n"
            "Set your minimum rating filter via /settings.\n\n"
            "Pick a tier to renew or upgrade:"
        ).format(
            tier=current.tier.upper(),
            expires=_expires_phrase(current.days_remaining),
        )
    else:
        header = _(
            "<b>Premium</b> unlocks the minimum-rating filter "
            "in /settings.\n\n"
            "Pick a tier:"
        )

    await message.answer(header, reply_markup=tiers_keyboard(tiers))


@router.callback_query(F.data.startswith("buy:"))
async def on_buy(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
    create_invoice: FromDishka[CreatePremiumInvoiceUseCase],
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    tier = callback.data.removeprefix("buy:")

    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )

    try:
        await create_invoice.execute(
            CreatePremiumInvoiceRequest(
                payer_id=user.id,
                payer_telegram_id=callback.from_user.id,
                tier=tier,
            )
        )
    except (InvalidTier, ValueError):
        await callback.answer(_("Unknown tier"), show_alert=True)
        return

    await callback.answer(_("Invoice sent — pay in the chat"))


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(
    message: Message,
    confirm_payment: FromDishka[ConfirmPaymentUseCase],
    register_user: FromDishka[RegisterUserUseCase],
    get_my_premium: FromDishka[GetMyPremiumUseCase],
) -> None:
    payment = message.successful_payment
    if payment is None or message.from_user is None:
        return

    try:
        transaction_id = UUID(payment.invoice_payload)
    except ValueError:
        await message.answer(_("Unknown payment payload."))
        return

    try:
        await confirm_payment.execute(
            ConfirmPaymentRequest(
                transaction_id=transaction_id,
                external_id=payment.telegram_payment_charge_id,
            )
        )
    except TransactionNotFound:
        await message.answer(_("This payment is not in our records."))
        return
    except InvalidStatusTransition:
        pass

    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
        )
    )
    premium = await get_my_premium.execute(user.id)

    if premium is None:
        await message.answer(_("✅ Payment confirmed."))
        return

    await message.answer(
        _(
            "<b>✅ Premium activated!</b>\n"
            "Tier: {tier}\n"
            "{expires}\n"
            "Pick your minimum rating filter in /settings."
        ).format(
            tier=premium.tier.upper(),
            expires=_expires_phrase(premium.days_remaining),
        )
    )
