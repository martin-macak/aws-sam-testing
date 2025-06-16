from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest
from docker.models.containers import Container


@contextmanager
def set_environment(
    **kwargs,
):
    import os

    current_environment = os.environ.copy()
    new_environment = {
        **current_environment,
        **kwargs,
    }
    old_environment = current_environment.copy()

    try:
        os.environ.update(new_environment)
        yield
    finally:
        # iterate over current os.environ and remove keys that are not present in old_environment
        for key in os.environ:
            if key not in old_environment:
                os.environ.pop(key)
        os.environ.update(old_environment)


class TestLocalStackDeploy:
    class LocalStack:
        def __init__(
            self,
            container: Container,
            host: str,
            port: int,
            package_bucket_name: str = "package-bucket",
        ):
            self.container = container
            self.host = host
            self.port = port
            self.package_bucket_name = package_bucket_name

    @pytest.fixture(autouse=True, scope="session")
    def localstack(self, request) -> Generator["TestLocalStackDeploy.LocalStack", None, None]:
        import socket
        import time

        import boto3
        import docker

        from aws_sam_testing.util import find_free_port

        port = find_free_port()

        docker_client = docker.from_env()
        container = docker_client.containers.run(
            "localstack/localstack:latest",
            ports={"4566/tcp": port},
            environment={"SERVICES": "s3,sqs,sns,lambda,cloudformation,dynamodb,iam"},
            detach=True,
            privileged=True,
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
        )

        host = "localhost"

        localstack = TestLocalStackDeploy.LocalStack(
            container=container,
            host=host,
            port=port,
        )

        def _finalize():
            container.stop()
            container.remove()

        request.addfinalizer(_finalize)

        max_attempts = 20
        for attempt in range(max_attempts):
            try:
                with socket.create_connection((localstack.host, localstack.port), timeout=2):
                    break
            except (OSError, ConnectionRefusedError):
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"LocalStack did not start on {host}:{port} after {max_attempts} seconds")
                time.sleep(1)

        # Additional check: use boto3 to verify S3 is available
        for attempt in range(max_attempts):
            try:
                with set_environment(
                    AWS_ENDPOINT_URL=f"http://{localstack.host}:{localstack.port}",
                ):
                    s3 = boto3.client(
                        "s3",
                        region_name="us-east-1",
                    )
                    buckets = s3.list_buckets()
                    print(buckets)

                    s3.create_bucket(Bucket=localstack.package_bucket_name)
                    buckets = s3.list_buckets()
                    assert localstack.package_bucket_name in [bucket["Name"] for bucket in buckets["Buckets"]]
                break
            except Exception:
                if attempt == max_attempts - 1:
                    raise RuntimeError("LocalStack S3 API did not become available after port was reachable.")
                time.sleep(1)

        with set_environment(
            AWS_ENDPOINT_URL=f"http://{localstack.host}:{localstack.port}",
        ):
            yield localstack

    @pytest.fixture(autouse=True)
    def project(self, tmp_path: Path) -> Generator[Path, None, None]:
        """
        This test fixture prepares sample test project with SAM project.
        It contains template.yaml that contains:
          - s3 bucket with name data-bucket
          - dynamodb table with name data-table
          - lambda function that uses the bucket for read, it's also triggered by PutObject into the bucket. it writes to dynamodb table
            storing the object key and the timestamp of the put operation.
          - AWS::Serverless::Function is used for lambda functions

        """
        # Create SAM project structure
        project_path = tmp_path / "sam-project"
        project_path.mkdir()

        # Create template.yaml
        template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Test SAM project for LocalStack deployment

Globals:
  Function:
    Timeout: 60
    Runtime: python3.12
    Environment:
      Variables:
        DYNAMODB_TABLE: !Ref DataTable

Resources:
  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: data-bucket

  DataTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: data-table
      AttributeDefinitions:
        - AttributeName: object_key
          AttributeType: S
      KeySchema:
        - AttributeName: object_key
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

  Role:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: Admin
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - "*"
                Resource: "*"

  ProcessS3EventsFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: app.lambda_handler
      Events:
        S3Event:
          Type: S3
          Properties:
            Bucket: !Ref DataBucket
            Events: s3:ObjectCreated:*
      Role: !GetAtt Role.Arn
"""

        template_path = project_path / "template.yaml"
        template_path.write_text(template_content)

        # Create source directory for Lambda function
        src_dir = project_path / "src"
        src_dir.mkdir()

        # Create Lambda function code
        lambda_code = """import json
import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE', 'data-table')

def lambda_handler(event, context):
    table = dynamodb.Table(table_name)
    
    # Process S3 events
    for record in event.get('Records', []):
        if record.get('eventSource') == 'aws:s3':
            bucket_name = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']
            event_time = record['eventTime']
            
            # Store the object key and timestamp in DynamoDB
            table.put_item(
                Item={
                    'object_key': object_key,
                    'bucket_name': bucket_name,
                    'event_time': event_time,
                    'processed_at': datetime.utcnow().isoformat()
                }
            )
            
            print(f"Processed S3 event: {bucket_name}/{object_key} at {event_time}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed S3 events')
    }
"""

        lambda_path = src_dir / "app.py"
        lambda_path.write_text(lambda_code)

        # Create requirements.txt for Lambda dependencies
        requirements_content = """boto3
"""
        requirements_path = src_dir / "requirements.txt"
        requirements_path.write_text(requirements_content)

        yield project_path

    @pytest.mark.slow()
    def test_localstack_deploy(
        self,
        localstack: LocalStack,
        project: Path,
    ):
        import os
        from tempfile import TemporaryDirectory

        from samcli.commands.build.build_context import BuildContext
        from samcli.commands.deploy.deploy_context import DeployContext
        from samcli.commands.package.package_context import PackageContext

        build_dir = project / ".aws-sam" / "build"
        working_dir = project
        template_path = project / "template.yaml"

        with TemporaryDirectory() as cache_dir:
            with BuildContext(
                resource_identifier=None,
                template_file=str(template_path),
                base_dir=str(working_dir),
                build_dir=str(build_dir),
                cache_dir=cache_dir,
                parallel=True,
                mode="build",
                cached=False,
                clean=True,
                use_container=False,
                aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            ) as ctx:
                ctx.run()

            packaged_template_path = build_dir / "packaged.yaml"

            with PackageContext(
                template_file=str(template_path),
                s3_bucket=localstack.package_bucket_name,
                s3_prefix="test/",
                output_template_file=str(packaged_template_path),
                kms_key_id=None,
                use_json=False,
                force_upload=True,
                no_progressbar=True,
                on_deploy=False,
                region="us-east-1",
                metadata=None,
                profile="default",
                image_repository=None,
                image_repositories=None,
            ) as package_context:
                package_context.run()

            # Print the packaged template
            print("Packaged template:")
            print(packaged_template_path.read_text())

            with DeployContext(
                template_file=str(packaged_template_path),
                stack_name="test-stack",
                s3_bucket=localstack.package_bucket_name,
                force_upload=False,
                no_progressbar=True,
                s3_prefix="test/",
                kms_key_id=None,
                no_execute_changeset=False,
                role_arn="arn:aws:iam::000000000000:role/test-role",
                notification_arns=[],
                fail_on_empty_changeset=True,
                tags={},
                region="us-east-1",
                profile="default",
                confirm_changeset=False,
                use_changeset=False,
                disable_rollback=False,
                poll_delay=1,
                image_repositories=None,
                image_repository=None,
                capabilities=[
                    "CAPABILITY_IAM",
                    "CAPABILITY_AUTO_EXPAND",
                    "CAPABILITY_NAMED_IAM",
                ],
                signing_profiles=None,
                parameter_overrides={},
                max_wait_duration=20,
                on_failure="DELETE",
            ) as deploy_context:
                deploy_context.run()
