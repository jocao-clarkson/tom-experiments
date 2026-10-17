import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import Storage
from tests.fakes import FakeS3Client


@pytest.fixture
def s3():
    return FakeS3Client()


@pytest.fixture
def app(s3):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    return create_app(conn, Storage(client=s3))


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def note(app):
    return app.state.notes.create_note("u1", "Groceries", "milk")
