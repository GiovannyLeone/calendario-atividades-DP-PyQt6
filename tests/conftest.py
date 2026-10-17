import pytest

from server.app import create_app
from server.repository import ActivityRepository


@pytest.fixture
def app(tmp_path):
    ActivityRepository.reset()
    application = create_app(tmp_path / "activities.json")
    yield application
    ActivityRepository.reset()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def facade(app):
    return app.config["FACADE"]


def meeting_data(**overrides):
    data = {
        "kind": "meeting",
        "title": "Reunião de teste",
        "start": "2026-10-08T10:00",
        "end": "2026-10-08T11:00",
        "category": "Trabalho/Reuniões",
        "location": "Sala 1",
        "attendees": ["Ana", "Bia"],
    }
    data.update(overrides)
    return data
