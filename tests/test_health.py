import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from helpdesk.config import Settings
from helpdesk.main import create_app


def test_health_endpoint_returns_ok() -> None:
    app = create_app(settings=Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_defaults_are_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "APP_NAME",
        "APP_ENV",
        "APP_HOST",
        "APP_PORT",
        "LOG_LEVEL",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "Helpdesk Tickets App"
    assert settings.app_env == "development"
    assert settings.app_port == 8000
    assert settings.openai_api_key is None


def test_settings_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_port=70000)


def test_settings_rejects_invalid_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="staging")  # type: ignore[arg-type]
