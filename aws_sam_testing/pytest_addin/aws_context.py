from typing import Generator

import boto3
import pytest


@pytest.fixture
def mock_aws_session() -> Generator[boto3.Session, None, None]:
    from moto import mock_aws

    with mock_aws():
        yield boto3.Session()
