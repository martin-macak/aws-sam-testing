import logging
import sys

import pytest


class TestLocalstackSimpleApi:
    @pytest.fixture(scope="session", autouse=True)
    def setup_session(self):
        # Configure the localstack logger to output to stdout in debug mode
        localstack_logger = logging.getLogger("aws_sam_testing.localstack_logger")
        localstack_logger.setLevel(logging.DEBUG)

        # Create a handler for stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.WARNING)

        # Create a standard formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)

        # Add the handler to the logger
        localstack_logger.addHandler(handler)

        # Prevent propagation to avoid duplicate logs
        localstack_logger.propagate = False

    @pytest.fixture(scope="function", autouse=True)
    def setup_test(self):
        pass

    def test_localstack_simple_api(
        self,
        request,
    ):
        import json
        import shutil
        import time
        from pathlib import Path

        import boto3

        from aws_sam_testing.aws_sam import AWSSAMToolkit
        from aws_sam_testing.localstack import LocalStackFeautureSet, LocalStackToolkit

        working_dir = Path(__file__).parent

        aws_sam_build_path = working_dir / ".aws-sam"
        if aws_sam_build_path.exists():
            shutil.rmtree(aws_sam_build_path)

        aws_sam = AWSSAMToolkit(
            working_dir=working_dir,
            template_path=working_dir / "template.yaml",
        )

        build_path = aws_sam.sam_build()
        assert build_path.exists()

        localstack_toolkit = LocalStackToolkit(
            working_dir=working_dir,
            template_path=build_path / "template.yaml",
        )

        localstack_processed_build_path = localstack_toolkit.build(
            feature_set=LocalStackFeautureSet.NORMAL,
        )
        assert localstack_processed_build_path.exists()

        with localstack_toolkit.run_localstack(
            build_dir=localstack_processed_build_path,
            template_path=localstack_processed_build_path / "template.yaml",
            pytest_request_context=request,
        ) as localstack:
            localstack.wait_for_localstack_to_be_ready()

            with localstack.environment():
                sfn = boto3.client("stepfunctions")
                state_machines = sfn.list_state_machines()["stateMachines"]
                assert len(state_machines) == 1
                state_machine = state_machines[0]
                assert state_machine["name"] == "user-processing"

                execution = sfn.start_execution(
                    stateMachineArn=state_machine["stateMachineArn"],
                    input=json.dumps({"userId": "123", "username": "John Doe", "email": "john.doe@example.com"}),
                )
                assert execution["executionArn"] is not None

                # wait for execution to complete
                while True:
                    execution = sfn.describe_execution(executionArn=execution["executionArn"])
                    if execution["status"] == "SUCCEEDED":
                        break
                    elif execution["status"] == "FAILED":
                        raise Exception(f"Execution failed: {execution}")
                    time.sleep(1)

                assert execution["status"] == "SUCCEEDED"

                dynamodb = boto3.resource("dynamodb")
                users_table = dynamodb.Table("users")
                user_item = users_table.get_item(Key={"userId": "123"}).get("Item")
                assert user_item is not None
                assert user_item["userId"] == "123"
                assert user_item["username"] == "John Doe"
                assert user_item["email"] == "john.doe@example.com"
                assert user_item["createdAt"] is not None

                sqs = boto3.resource("sqs")
                queue = sqs.Queue("user-notifications")
                messages = queue.receive_messages(MaxNumberOfMessages=10)
                assert len(messages) == 1
