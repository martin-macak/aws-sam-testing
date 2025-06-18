import pytest


class TestLocalstackSimpleApi:
    @pytest.fixture(scope="session", autouse=True)
    def setup_session(self):
        pass

    @pytest.fixture(scope="function", autouse=True)
    def setup_test(self):
        pass

    def test_localstack_simple_api(self, request, monkeypatch):
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
            localstack.wait_for_localstack_to_be_ready()

            apis = localstack.get_apis()
            assert apis is not None
