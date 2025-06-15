from typing import Generator

import boto3
import pytest


@pytest.fixture
def aws_region():
    import os

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "fake-default-region"
    yield region


@pytest.fixture
def mock_aws_session() -> Generator[boto3.Session, None, None]:
    from moto import mock_aws

    with mock_aws():
        yield boto3.Session()
