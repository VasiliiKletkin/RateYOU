from uuid import UUID

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.i18n import gettext as _

from src.application.subscription.dto import TierInfoResponse


def share_location_keyboard(label: str) -> ReplyKeyboardMarkup:
    """Reply keyboard with a single 'request_location' button.

    Telegram only allows location sharing via reply (not inline) keyboards.
    `one_time_keyboard=True` makes the keyboard hide after the user taps,
    matching the one-shot nature of the location step.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label, request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=_("♂️ Male"), callback_data="gender:male"),
                InlineKeyboardButton(
                    text=_("♀️ Female"), callback_data="gender:female"
                ),
            ],
        ]
    )


def gender_preference_keyboard(prefix: str = "genderpref") -> InlineKeyboardMarkup:
    """Three-way preference picker: men / women / everyone.

    `prefix` lets callers disambiguate their callback namespace — /create
    uses the default "genderpref" and /settings uses "setpref" so the two
    handlers can coexist without state filters.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("♂️ Men"), callback_data=f"{prefix}:male"
                ),
                InlineKeyboardButton(
                    text=_("♀️ Women"), callback_data=f"{prefix}:female"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=_("👥 Everyone"), callback_data=f"{prefix}:any"
                ),
            ],
        ]
    )


def settings_main_keyboard(
    *,
    gender_label: str,
    rating_label: str,
    language_label: str,
    gender_action: str = "openpref",
    rating_action: str = "openrating",
    language_action: str = "openlang",
) -> InlineKeyboardMarkup:
    """Top-level /settings menu: one button per editable setting.

    Each button's label embeds the current value (e.g. "👤 Show me: Men")
    so the user reads the state from the buttons themselves. Tapping a
    button swaps the keyboard for the corresponding picker; the picker
    handler restores this view after the user picks.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=gender_label, callback_data=gender_action
                )
            ],
            [
                InlineKeyboardButton(
                    text=rating_label, callback_data=rating_action
                )
            ],
            [
                InlineKeyboardButton(
                    text=language_label, callback_data=language_action
                )
            ],
        ]
    )


def rating_picker_keyboard(prefix: str = "setrating") -> InlineKeyboardMarkup:
    """5-preset min-rating picker for /settings."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("Any"), callback_data=f"{prefix}:0"
                ),
                InlineKeyboardButton(
                    text="6+", callback_data=f"{prefix}:6"
                ),
                InlineKeyboardButton(
                    text="7+", callback_data=f"{prefix}:7"
                ),
                InlineKeyboardButton(
                    text="8+", callback_data=f"{prefix}:8"
                ),
                InlineKeyboardButton(
                    text="9+", callback_data=f"{prefix}:9"
                ),
            ]
        ]
    )


def language_keyboard(
    languages: tuple[str, ...],
    native_names: dict[str, str],
    *,
    prefix: str = "setlang",
    columns: int = 2,
) -> InlineKeyboardMarkup:
    """Grid picker for the /settings language selection.

    Native labels keep the button readable regardless of the user's current
    UI locale. `columns=2` keeps each button wide enough on mobile while the
    full list of 22 supported languages stays within Telegram's height budget.
    """
    buttons = [
        InlineKeyboardButton(
            text=native_names.get(code, code), callback_data=f"{prefix}:{code}"
        )
        for code in languages
    ]
    rows = [buttons[i : i + columns] for i in range(0, len(buttons), columns)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rating_keyboard(rated_user_id: UUID) -> InlineKeyboardMarkup:
    """Buttons 0..10 (split into two rows) plus a Skip button.

    Callback data fits in Telegram's 64-byte limit:
        "rate:" + uuid(36) + ":" + "10"  = 44 bytes max
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(i), callback_data=f"rate:{rated_user_id}:{i}"
                )
                for i in range(0, 6)
            ],
            [
                InlineKeyboardButton(
                    text=str(i), callback_data=f"rate:{rated_user_id}:{i}"
                )
                for i in range(6, 11)
            ],
            [
                InlineKeyboardButton(
                    text=_("⏭ Skip"), callback_data=f"skip:{rated_user_id}"
                ),
            ],
        ]
    )


def edit_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("Name"), callback_data="edit_field:name")],
            [InlineKeyboardButton(text=_("Age"), callback_data="edit_field:age")],
            [
                InlineKeyboardButton(
                    text=_("Gender"), callback_data="edit_field:gender"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_("Location"), callback_data="edit_field:location"
                )
            ],
            [InlineKeyboardButton(text=_("Bio"), callback_data="edit_field:bio")],
            [InlineKeyboardButton(text=_("Photo"), callback_data="edit_field:photo")],
            [
                InlineKeyboardButton(
                    text=_("✅ Done"), callback_data="edit_field:done"
                )
            ],
        ]
    )


def tiers_keyboard(tiers: list[TierInfoResponse]) -> InlineKeyboardMarkup:
    """One button per tier: 'Bronze - 100 ⭐ / 7d'.

    Tier names (`display_name`) stay as-is — they're product proper-nouns.
    Only the surrounding template gets localized.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("{name} — {price} ⭐ / {days}d").format(
                        name=tier.display_name,
                        price=tier.stars_price,
                        days=tier.duration_days,
                    ),
                    callback_data=f"buy:{tier.tier}",
                )
            ]
            for tier in tiers
        ]
    )
