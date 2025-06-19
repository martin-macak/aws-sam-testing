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
        import shutil
        from pathlib import Path

        import requests

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

            apis = localstack.get_apis()
            assert apis is not None

            prod_api = next(api for api in apis if api.api_gateway_stage_name.lower() == "prod")
            assert prod_api is not None

            response = requests.get(prod_api.base_url + "/users")
            assert response.status_code == 200
            assert response.json() == {"users": [], "count": 0}

            # Create a user
            user_data = {"name": "John Doe", "email": "john.doe@example.com", "age": 30}
            create_response = requests.post(prod_api.base_url + "/users", json=user_data)
            assert create_response.status_code == 201, create_response.text
            created_user = create_response.json()
            assert created_user["message"] == "User created successfully"
            assert "user" in created_user
            assert "userId" in created_user["user"]
            assert created_user["user"]["name"] == "John Doe"
            assert created_user["user"]["email"] == "john.doe@example.com"
            assert created_user["user"]["age"] == 30

            # List users again and verify the created user is present
            list_response = requests.get(prod_api.base_url + "/users")
            assert list_response.status_code == 200, list_response.text
            users_data = list_response.json()
            assert users_data["count"] == 1
            assert len(users_data["users"]) == 1

            # Verify the user details
            retrieved_user = users_data["users"][0]
            assert retrieved_user["userId"] == created_user["user"]["userId"]
            assert retrieved_user["name"] == "John Doe"
            assert retrieved_user["email"] == "john.doe@example.com"
            assert retrieved_user["age"] == 30
