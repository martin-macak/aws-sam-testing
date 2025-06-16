from pathlib import Path
from typing import Generator

import boto3
import pytest


class AWSTestContext:
    def __init__(
        self,
        pytest_request_context: pytest.FixtureRequest,
    ):
        self.pytest_request_context: pytest.FixtureRequest = pytest_request_context
        self.project_root: Path | None = None
        self.template_name: str = "template.yaml"

    def set_project_root(self, path: Path) -> None:
        self.project_root = path

    def set_template_name(self, template_name: str) -> None:
        self.template_name = template_name

    def get_project_root(self) -> Path:
        from aws_sam_testing.util import find_project_root

        if self.project_root is None:
            self.project_root = find_project_root(
                start_path=Path(self.pytest_request_context.node.fspath.dirname),
                template_name=self.template_name,
            )
        return self.project_root


@pytest.fixture(scope="session", autouse=True)
def _prepare_aws_context(  # noqa
    request: pytest.FixtureRequest,
) -> Generator[AWSTestContext, None, None]:
    request.session._aws_context = AWSTestContext(  # type: ignore
        pytest_request_context=request,
    )
    yield request.session._aws_context  # type: ignore


@pytest.fixture(scope="session")
def aws_context(
    _prepare_aws_context,
) -> Generator[AWSTestContext, None, None]:
    yield _prepare_aws_context


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
