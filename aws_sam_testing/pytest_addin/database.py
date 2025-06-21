from typing import Generator

import pytest

from aws_sam_testing.database import PostgresDatabase


@pytest.fixture(scope="session")
def db_postgres(request: pytest.FixtureRequest) -> Generator[PostgresDatabase, None, None]:
    with PostgresDatabase() as db:

        def _finalize_db():
            db.stop()

        request.addfinalizer(_finalize_db)

        yield db
