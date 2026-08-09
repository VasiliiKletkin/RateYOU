"""The `/start` payload carries two different things in one slot.

Numeric means a referral link (`/refer` hands out `?start=<telegram_id>`),
anything else is an acquisition tag (`?start=habr`). These tests pin the
split so a future change can't make one swallow the other.
"""

import pytest

from src.presentation.bot.handlers.start import (
    _extract_acquisition_source,
    _extract_referrer_telegram_id,
)


@pytest.mark.parametrize(
    ("payload", "referrer", "source"),
    [
        ("123456789", 123456789, None),  # referral link
        ("habr", None, "habr"),  # channel tag
        ("tiktok_jan", None, "tiktok_jan"),
        (None, None, None),  # bare /start
        ("", None, None),
        # Numeric-but-unusable payloads are broken referral links, not tags —
        # they must not leak into the funnel as channels named "-1" and "0".
        ("-1", None, None),
        ("0", None, None),
    ],
)
def test_payload_splits_between_referral_and_source(
    payload: str | None,
    referrer: int | None,
    source: str | None,
) -> None:
    assert _extract_referrer_telegram_id(payload) == referrer
    assert _extract_acquisition_source(payload) == source
