import pytest

from aws_sam_testing.database import PostgresDatabase


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

    @pytest.fixture(scope="session")
    def test_database(
        self,
        db_postgres,
    ) -> tuple[PostgresDatabase, str]:
        import psycopg2

        db_postgres.wait_for_start()
        db_postgres.create_database("test_db")

        connection_string = db_postgres.get_connection_string("test_db")

        # create new schema app
        with psycopg2.connect(connection_string) as conn:
            with conn.cursor() as cursor:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS app")
                cursor.execute("SET search_path TO app")
                cursor.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255))")

        return db_postgres, connection_string

    def test_run_local_api_with_moto_isolation_resources(
        self,
        tmp_path,
        request,
        test_database,
    ):
        from pathlib import Path

        import requests

        from aws_sam_testing.aws_sam import AWSSAMToolkit, IsolationLevel

        _, test_database_connection_string = test_database
        docker_connection_string = test_database_connection_string.replace("localhost", "host.docker.internal")

        toolkit = AWSSAMToolkit(
            working_dir=Path(__file__).parent,
            template_path=Path(__file__).parent / "template.yaml",
        )

        toolkit.sam_build(build_dir=tmp_path)

        with toolkit.run_local_api(
            isolation_level=IsolationLevel.MOTO,
            pytest_request_context=request,
            parameters={
                "DbConnectionString": docker_connection_string,
                "SubnetIds": "subnet-00000000000000000,subnet-00000000000000001",
                "VpcId": "vpc-00000000000000000",
                "LambdaSecurityGroupId": "sg-00000000000000000",
            },
        ) as apis:
            assert len(apis) == 1

            api = apis[0]

            assert api.api_logical_id == "MyApi"
            assert api.port is not None
            assert api.host is not None

            api.wait_for_api_to_be_ready()

            for api in apis:
                assert api.is_running

            pass

            response = requests.get(f"http://{api.host}:{api.port}/list-users")
            assert response is not None
            assert response.status_code == 200, response.text

            response = requests.post(f"http://{api.host}:{api.port}/create-user", json={"name": "test"})
            assert response is not None
            assert response.status_code == 201, response.text

            response = requests.get(f"http://{api.host}:{api.port}/list-users")
            assert response is not None
            assert response.status_code == 200, response.text
            assert response.json() == [{"id": 1, "name": "test"}]
