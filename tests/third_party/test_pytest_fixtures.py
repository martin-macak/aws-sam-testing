from typing import Generator

import pytest


class Scoped:
    def __init__(self):
        self.scope = None

    def set_scope(self, scope: str):
        self.scope = scope


@pytest.fixture(scope="session", autouse=True)
def _prepare_scoped(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    request.session._scoped = Scoped()
    yield


@pytest.fixture(scope="session")
def my_test_session_fixture(
    request: pytest.FixtureRequest,
    _prepare_scoped: Scoped,
) -> Generator[Scoped, None, None]:
    scoped = Scoped()
    request.session._scoped = scoped
    yield scoped


@pytest.fixture(scope="function")
def my_test_function_fixture(request, my_test_session_fixture) -> Generator[Scoped, None, None]:
    scoped = request.session._scoped if hasattr(request.session, "_scoped") else None
    return scoped


class TestPytestFixtureDefaltValue:
    def test_fixture_scopes(self, my_test_function_fixture):
        assert my_test_function_fixture.scope is None


class TestPytestFixtures:
    @pytest.fixture(autouse=True)
    def setup(self, my_test_function_fixture):
        my_test_function_fixture.set_scope("test_a")

    def test_fixture_scopes(self, my_test_function_fixture):
        assert my_test_function_fixture.scope == "test_a"


class TestPytestFixturesMulti:
    @pytest.fixture(autouse=True)
    def setup(self, my_test_function_fixture):
        my_test_function_fixture.set_scope("test_a")

    def test_fixture_scopes(self, my_test_function_fixture):
        assert my_test_function_fixture.scope == "test_a"

    def test_fixture_scopes_2(self, my_test_function_fixture):
        assert my_test_function_fixture.scope == "test_a"
