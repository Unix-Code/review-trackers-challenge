from concurrent.futures import Executor, Future
from unittest import mock

import pytest
import responses


@pytest.fixture(scope="session")
def test_app():
    from app import app

    app.TESTING = True

    with app.app_context():
        yield app


@pytest.fixture(scope="session")
def test_client(test_app):
    with test_app.test_client() as client:
        yield client


@pytest.fixture
def load_fixture():
    def _load_fixture(filename):
        with open(f"tests/fixtures/{filename}.html", "r") as f:
            return f.read()

    return _load_fixture


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


class MockExecutor(Executor):
    BATCH_SIZE = 3

    def __init__(self, *args, **kwargs):
        self._max_workers = self.BATCH_SIZE

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            result = fn(*args, **kwargs)
        except BaseException as e:
            future.set_exception(e)
        else:
            future.set_result(result)
        return future


@pytest.fixture(autouse=True)
def mocked_threadpoolexecutor():
    with mock.patch("scraper.ThreadPoolExecutor", MockExecutor):
        yield


@pytest.fixture
def mocked_threadpoolexecutor_batch_size():
    return MockExecutor.BATCH_SIZE
