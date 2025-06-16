from pathlib import Path
from typing import Generator

import boto3
import pytest

from aws_sam_testing.aws_sam import IsolationLevel


class AWSTestContext:
    def __init__(
        self,
        pytest_request_context: pytest.FixtureRequest,
    ):
        self.pytest_request_context: pytest.FixtureRequest = pytest_request_context
        self.project_root: Path | None = None
        self.template_name: str = "template.yaml"
        self.isolation_level: IsolationLevel = IsolationLevel.NONE

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

    def get_template_path(self) -> Path:
        return self.get_project_root() / self.template_name

    def set_api_isolation_level(self, isolation_level: IsolationLevel) -> None:
        self.isolation_level = isolation_level

    def get_api_isolation_level(self) -> IsolationLevel:
        return self.isolation_level


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
