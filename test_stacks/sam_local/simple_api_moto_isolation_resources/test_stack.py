import pytest


class TestSimpleApiMotoIsolationResources:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.start", lambda *args, **kwargs: None)
        monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.stop", lambda *args, **kwargs: None)
        yield

    def test_build_with_toolkit(self, tmp_path):
        from pathlib import Path

        from aws_sam_testing.aws_sam import AWSSAMToolkit

        toolkit = AWSSAMToolkit(
            working_dir=Path(__file__).parent,
            template_path=Path(__file__).parent / "template.yaml",
        )

        toolkit.sam_build(build_dir=tmp_path)
        p_built_template = tmp_path / "template.yaml"
        assert p_built_template.exists()

    def test_run_local_api_with_moto_isolation_resources(self, tmp_path, request):
        from pathlib import Path

        import requests

        from aws_sam_testing.aws_sam import AWSSAMToolkit, IsolationLevel

        toolkit = AWSSAMToolkit(
            working_dir=Path(__file__).parent,
            template_path=Path(__file__).parent / "template.yaml",
        )

        toolkit.sam_build(build_dir=tmp_path)

        with toolkit.run_local_api(isolation_level=IsolationLevel.MOTO, pytest_request_context=request) as apis:
            assert len(apis) == 1

            api = apis[0]

            assert api.api_logical_id == "MyApi"
            assert api.port is not None
            assert api.host is not None

            api.wait_for_api_to_be_ready()

            for api in apis:
                assert api.is_running

            response = requests.get(f"http://{api.host}:{api.port}/list-users")
            assert response is not None
            assert response.status_code == 200

            users = response.json()["users"]
            assert len(users) == 0

            response = requests.post(f"http://{api.host}:{api.port}/create-user", json={"id": "1", "name": "John Doe"})
            assert response is not None
            assert response.status_code == 200, response.text

            response = requests.get(f"http://{api.host}:{api.port}/list-users")
            assert response is not None
            assert response.status_code == 200

            users = response.json()["users"]
            assert len(users) == 1
            assert users[0]["id"] == "1"
            assert users[0]["name"] == "John Doe"
