import bcrypt
import pytest
from fastapi import HTTPException

from BackEnd.app.api import auth as auth_api
from BackEnd.app.database.sql_models import Login, Register, User
from BackEnd.app.service.auth_service import AuthService


class StubDatabase:
    def __init__(self, users: list[dict]) -> None:
        self.users = users
        self.inserted_user = None

    def select_user_by_name(self, user_name: str) -> list[dict]:
        return [user for user in self.users if user["user_name"] == user_name]

    def insert_user(self, user: User) -> None:
        self.inserted_user = user


def create_user(password: str = "correct-password") -> dict:
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    return {
        "user_id": "user-001",
        "user_name": "minh",
        "user_password": password_hash,
        "plan": "Free",
    }


def test_register_creates_free_user() -> None:
    database = StubDatabase([])
    service = AuthService(database=database)

    result = service.register(Register(user_name="minh", password="password"))

    assert database.inserted_user.plan == "Free"
    assert result["plan"] == "Free"


def test_login_returns_user_for_valid_credentials() -> None:
    service = AuthService(database=StubDatabase([create_user()]))

    result = service.login(
        Login(user_name="minh", password="correct-password")
    )

    assert result == {
        "user_id": "user-001",
        "user_name": "minh",
        "plan": "Free",
    }


def test_login_rejects_invalid_password() -> None:
    service = AuthService(database=StubDatabase([create_user()]))

    with pytest.raises(ValueError, match="Invalid username or password"):
        service.login(Login(user_name="minh", password="wrong-password"))


def test_login_rejects_unknown_user() -> None:
    service = AuthService(database=StubDatabase([]))

    with pytest.raises(ValueError, match="Invalid username or password"):
        service.login(Login(user_name="unknown", password="password"))


def test_login_route_is_registered() -> None:
    routes = {route.path: route.methods for route in auth_api.router.routes}

    assert routes["/auth/login"] == {"POST"}


def test_login_endpoint_returns_success(monkeypatch) -> None:
    service = AuthService(database=StubDatabase([create_user()]))
    monkeypatch.setattr(auth_api, "auth_service", service)

    response = auth_api.login(
        Login(user_name="minh", password="correct-password")
    )

    assert response == {
        "message": "Login successfully.",
        "data": {
            "user_id": "user-001",
            "user_name": "minh",
            "plan": "Free",
        },
    }


def test_login_endpoint_returns_401_for_invalid_credentials(monkeypatch) -> None:
    service = AuthService(database=StubDatabase([create_user()]))
    monkeypatch.setattr(auth_api, "auth_service", service)

    with pytest.raises(HTTPException) as error:
        auth_api.login(Login(user_name="minh", password="wrong-password"))

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid username or password"
