from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import boto3
import pytest
from boto3.resources.base import ServiceResource


class ResourceManager:
    def __init__(
        self,
        session: boto3.Session,
        working_dir: Path | None,
        template_name: str = "template.yaml",
        template: dict | None = None,
        region_name: str | None = None,
    ):
        from aws_sam_testing.aws_resources import AWSResourceManager
        from aws_sam_testing.cfn import load_yaml_file
        from aws_sam_testing.util import find_project_root

        if template is not None:
            self.template = template
        else:
            if working_dir is None:
                working_dir = Path(__file__).parent

            project_root = find_project_root(working_dir)
            template = load_yaml_file(str(project_root / template_name))
            self.template = template

        self.session = session
        self.manager = AWSResourceManager(
            session=session,
            template=self.template,
            region_name=region_name,
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

    def get_resource(self, resource_name: str) -> ServiceResource:
        import boto3
        from moto.core.common_models import CloudFormationModel

        resource_def = self.manager.get_cfn_resource_by_name(resource_name)
        if not isinstance(resource_def, CloudFormationModel):
            raise ValueError(f"Resource {resource_name} is not a CloudFormation model")

        if not hasattr(resource_def, "name"):
            raise ValueError(f"Resource {resource_name} has no name")

        assert hasattr(resource_def, "name")
        resource_name = resource_def.name

        match resource_def.cloudformation_type():
            case "AWS::SQS::Queue":
                return boto3.resource("sqs").Queue(resource_name)
            case "AWS::DynamoDB::Table":
                return boto3.resource("dynamodb").Table(resource_name)
            case "AWS::S3::Bucket":
                return boto3.resource("s3").Bucket(resource_name)
            case _:
                raise ValueError(f"Unsupported resource type: {resource_def.cloudformation_type()}")


@pytest.fixture
def mock_aws_resources(
    request,
    mock_aws_session: boto3.Session,
    aws_region,
) -> Generator[ResourceManager, None, None]:
    working_dir = Path(request.node.fspath.dirname)
    assert working_dir.exists()

    with ResourceManager(
        session=mock_aws_session,
        working_dir=working_dir,
        region_name=aws_region,
    ) as manager:
        yield manager
