from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import boto3
import pytest


class ResourceManager:
    def __init__(
        self,
        session: boto3.Session,
        working_dir: Path | None,
        template_name: str = "template.yaml",
    ):
        from aws_sam_testing.aws_resources import AWSResourceManager
        from aws_sam_testing.cfn import load_yaml_file
        from aws_sam_testing.util import find_project_root

        if working_dir is None:
            working_dir = Path(__file__).parent

        project_root = find_project_root(working_dir)
        template = load_yaml_file(str(project_root / template_name))

        self.session = session
        self.manager = AWSResourceManager(
            session=session,
            template=template,
        )

    def __enter__(self):
        self.manager.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.manager.__exit__(exc_type, exc_value, traceback)

    @contextmanager
    def set_environment(
        self,
        lambda_function_logical_name: str,
        additional_environment: dict = {},
    ):
        with self.manager.set_environment(lambda_function_logical_name, additional_environment):
            yield self


@pytest.fixture
def mock_aws_resources(
    request,
    mock_aws_session: boto3.Session,
) -> Generator[ResourceManager, None, None]:
    working_dir = Path(request.node.fspath.dirname)
    assert working_dir.exists()

    with ResourceManager(
        session=mock_aws_session,
        working_dir=working_dir,
    ) as manager:
        yield manager
