import logging

import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.contrib.sqla import Admin

from src.infrastructure.config import get_settings
from src.infrastructure.db.models import (
    ProfileORM,
    ProfilePhotoORM,
    ProfileScoreSummaryORM,
    RatingORM,
    SubscriptionORM,
    TransactionORM,
    UserORM,
)
from src.presentation.admin.auth import AdminAuthProvider
from src.presentation.admin.views import (
    ProfileAdmin,
    ProfilePhotoAdmin,
    ProfileScoreSummaryAdmin,
    RatingAdmin,
    SubscriptionAdmin,
    TransactionAdmin,
    UserAdmin,
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RateMe Admin")

    engine = create_async_engine(settings.postgres.dsn)

    admin = Admin(
        engine,
        title="RateMe Admin",
        auth_provider=AdminAuthProvider(settings.admin),
        middlewares=[
            Middleware(
                SessionMiddleware,
                secret_key=settings.admin.secret_key.get_secret_value(),
            ),
        ],
    )

    admin.add_view(UserAdmin(UserORM))
    admin.add_view(ProfileAdmin(ProfileORM))
    admin.add_view(ProfilePhotoAdmin(ProfilePhotoORM))
    admin.add_view(RatingAdmin(RatingORM))
    admin.add_view(ProfileScoreSummaryAdmin(ProfileScoreSummaryORM))
    admin.add_view(SubscriptionAdmin(SubscriptionORM))
    admin.add_view(TransactionAdmin(TransactionORM))

    admin.mount_to(app)

    return app


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.value)
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
