from dishka import Provider

from src.presentation.di.bot import BotProvider
from src.presentation.di.db import DbProvider
from src.presentation.di.discovery import DiscoveryProvider
from src.presentation.di.events import EventsProvider
from src.presentation.di.geocoding import GeocodingProvider
from src.presentation.di.payment import PaymentProvider
from src.presentation.di.redis import RedisProvider
from src.presentation.di.repositories import RepositoryProvider
from src.presentation.di.services import DomainServiceProvider
from src.presentation.di.settings import SettingsProvider
from src.presentation.di.uow import UoWProvider
from src.presentation.di.use_cases import UseCaseProvider


def all_providers() -> list[Provider]:
    """Every dishka provider for the whole application."""
    return [
        SettingsProvider(),
        DbProvider(),
        RedisProvider(),
        UoWProvider(),
        RepositoryProvider(),
        BotProvider(),
        PaymentProvider(),
        DiscoveryProvider(),
        GeocodingProvider(),
        DomainServiceProvider(),
        EventsProvider(),
        UseCaseProvider(),
    ]
