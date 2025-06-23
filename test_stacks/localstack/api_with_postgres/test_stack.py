import pytest

from aws_sam_testing.localstack import LocalStack


class TestSimpleApiMotoIsolationResources:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        monkeypatch.setattr(
            "samcli.lib.utils.file_observer.FileObserver.start",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "samcli.lib.utils.file_observer.FileObserver.stop",
            lambda *args, **kwargs: None,
        )
        yield

    @pytest.fixture(autouse=True, scope="session")
    def setup_requirements(self):
        import re
        from pathlib import Path

        # check available python packages for psycopg2-binary and get the version
        import psycopg2

        print(psycopg2.__version__)
        semver_pattern = r"^(\d+)\.(\d+)\.(\d+).*"
        match = re.match(semver_pattern, psycopg2.__version__)
        if match:
            major, minor, patch = match.groups()
            psycopg2_version = f"{major}.{minor}.{patch}"
        else:
            raise ValueError(f"Invalid psycopg2 version: {psycopg2.__version__}")

        # create requirements.txt file in the current directory
        with open(Path(__file__).parent / "api_handler" / "requirements.txt", "w") as f:
            f.write(f"psycopg2-binary>={psycopg2_version}")

        with open(Path(__file__).parent / "migration" / "requirements.txt", "w") as f:
            f.write(f"psycopg2-binary>={psycopg2_version}")

    @pytest.fixture(scope="session")
    def stack(
        self,
        request: pytest.FixtureRequest,
    ) -> LocalStack:
        import json
        import shutil
        from pathlib import Path

        import boto3

        from aws_sam_testing.aws_sam import AWSSAMToolkit
        from aws_sam_testing.database import PostgresDatabase
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

        with PostgresDatabase() as postgres_database:

            def finalize_db():
                postgres_database.stop()

            request.addfinalizer(finalize_db)

            postgres_database.wait_for_start()
            postgres_database.create_database("test_db")
            connection_string = postgres_database.get_connection_string("test_db")
            connection_string = connection_string.replace("localhost", "host.docker.internal")

            with localstack_toolkit.run_localstack(
                build_dir=localstack_processed_build_path,
                template_path=localstack_processed_build_path / "template.yaml",
                pytest_request_context=request,
                parameters={
                    "DatabaseConnectionString": connection_string,
                },
            ) as localstack:
                with localstack.environment():
                    lambda_ = boto3.client("lambda")
                    invoke_response = lambda_.invoke(
                        FunctionName="Migration",
                        Payload=json.dumps({"RequestType": "Migrate"}),
                    )
                    assert invoke_response["StatusCode"] == 200, invoke_response
                    if invoke_response.get("FunctionError"):
                        invoke_response_payload = invoke_response["Payload"].read()
                        print(invoke_response_payload)
                        assert False, "Migration failed"

                    assert invoke_response.get("FunctionError") is None, invoke_response
                    invoke_response_payload = invoke_response["Payload"].read()
                    invoke_response_data = json.loads(invoke_response_payload)
                    assert invoke_response_data["Message"] == "Database migration completed successfully"

            return localstack

    def test_run_local_api_with_moto_isolation_resources(
        self,
        tmp_path,
        request,
        stack,
    ):
        pass
