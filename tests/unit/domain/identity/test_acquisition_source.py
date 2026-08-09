import pytest

from src.domain.identity.exceptions import InvalidAcquisitionSource
from src.domain.identity.value_objects import AcquisitionSource


def test_source_is_lowercased() -> None:
    """Same channel typed two ways must not split the funnel report."""
    assert AcquisitionSource("Habr").value == AcquisitionSource("habr").value


@pytest.mark.parametrize("raw", ["habr", "tiktok_jan", "chat-msk-1", "a", "9" * 64])
def test_accepts_telegram_payload_charset(raw: str) -> None:
    assert AcquisitionSource(raw).value == raw.lower()


@pytest.mark.parametrize(
    "raw",
    [
        "",  # empty
        "a" * 65,  # over Telegram's 64-char payload cap
        "has space",
        "dots.not.allowed",
        "юникод",
    ],
)
def test_rejects_what_telegram_could_never_deliver(raw: str) -> None:
    with pytest.raises(InvalidAcquisitionSource):
        AcquisitionSource(raw)
