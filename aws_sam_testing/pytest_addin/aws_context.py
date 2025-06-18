from pathlib import Path
from typing import Generator

import boto3
import pytest

from aws_sam_testing.aws_sam import IsolationLevel
from aws_sam_testing.localstack import LocalStackFeautureSet


class AWSTestContext:
    def __init__(
        self,
        pytest_request_context: pytest.FixtureRequest,
    ):
        self._pytest_request_context: pytest.FixtureRequest = pytest_request_context
        self._project_root: Path | None = None
        self._template_name: str = "template.yaml"
        self._isolation_level: IsolationLevel = IsolationLevel.NONE
        self._build_dir: Path | None = None
        self._localstack_runs_build: bool = False
        self._localstack_feature_set: LocalStackFeautureSet = LocalStackFeautureSet.NORMAL

    def get_project_root(self) -> Path:
        from aws_sam_testing.util import find_project_root

        if self._project_root is None:
            self._project_root = find_project_root(
                start_path=Path(self._pytest_request_context.node.fspath.dirname),
                template_name=self._template_name,
            )
        return self._project_root

    def set_project_root(self, path: Path) -> None:
        self._project_root = path

    def get_template_name(self) -> str:
        return self._template_name

    def set_template_name(self, template_name: str) -> None:
        self._template_name = template_name

    def get_build_dir(self) -> Path:
        if self._build_dir is None:
            self._build_dir = self.get_project_root() / ".aws-sam" / "build"
        return self._build_dir

    def set_build_dir(self, build_dir: Path) -> None:
        self._build_dir = build_dir

    def get_template_path(self) -> Path:
        return self.get_project_root() / self._template_name

    def get_api_isolation_level(self) -> IsolationLevel:
        return self._isolation_level

    def set_api_isolation_level(self, isolation_level: IsolationLevel) -> None:
        self._isolation_level = isolation_level

    def get_localstack_runs_build(self) -> bool:
        return self._localstack_runs_build

    def set_localstack_runs_build(self, localstack_runs_build: bool) -> None:
        self._localstack_runs_build = localstack_runs_build

    def get_localstack_feature_set(self) -> LocalStackFeautureSet:
        return self._localstack_feature_set

    def set_localstack_feature_set(self, localstack_feature_set: LocalStackFeautureSet) -> None:
        self._localstack_feature_set = localstack_feature_set


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
