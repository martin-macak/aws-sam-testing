import pytest


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

    def test_run_local_api_with_moto_isolation_resources(self, tmp_path, request):
        from pathlib import Path

        from aws_sam_testing.aws_sam import AWSSAMToolkit, IsolationLevel

        toolkit = AWSSAMToolkit(
            working_dir=Path(__file__).parent,
            template_path=Path(__file__).parent / "template.yaml",
        )

        toolkit.sam_build(build_dir=tmp_path)

        with toolkit.run_local_api(
            isolation_level=IsolationLevel.MOTO,
            pytest_request_context=request,
            parameters={
                "DatabaseConnectionString": "sqlite://",
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
