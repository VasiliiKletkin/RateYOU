from dishka import Provider, Scope, provide

from src.infrastructure.config import Settings, get_settings


class SettingsProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return get_settings()
