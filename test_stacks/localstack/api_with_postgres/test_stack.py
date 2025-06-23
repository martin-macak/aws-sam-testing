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

    @pytest.fixture(scope="session")
    def stack(
        self,
        request: pytest.FixtureRequest,
    ) -> LocalStack:
        import shutil
        from pathlib import Path

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
            return localstack

    def test_run_local_api_with_moto_isolation_resources(
        self,
        tmp_path,
        request,
        stack,
    ):
        pass
