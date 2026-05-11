from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import LoginFailed

from src.infrastructure.config import AdminConfig


class AdminAuthProvider(AuthProvider):
    """Single-user auth backed by ADMIN_USERNAME / ADMIN_PASSWORD env vars.

    Multi-admin / role-based access can be added later by switching the
    backend to query the `users` table for `role == ADMIN` instead.
    """

    def __init__(self, config: AdminConfig):
        super().__init__()
        self._config = config

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        if (
            username == self._config.username
            and password == self._config.password.get_secret_value()
        ):
            request.session["username"] = username
            return response
        raise LoginFailed("Invalid credentials")

    async def is_authenticated(self, request: Request) -> bool:
        return "username" in request.session

    def get_admin_user(self, request: Request) -> AdminUser | None:
        username = request.session.get("username")
        if username is None:
            return None
        return AdminUser(username=username)

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response
