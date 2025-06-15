import pytest


class TestTwoApis:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.start", lambda *args, **kwargs: None)
        monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.stop", lambda *args, **kwargs: None)
        yield

    def test_build_with_toolkit(
        self,
    ):
        from pathlib import Path

        from aws_sam_testing.aws_sam import AWSSAMToolkit

        toolkit = AWSSAMToolkit(
            working_dir=Path(__file__).parent,
            template_path=Path(__file__).parent / "template.yaml",
        )

        toolkit.sam_build()

        p_built_template = Path(__file__).parent / ".aws-sam" / "aws-sam-testing-build" / "template.yaml"
        assert p_built_template.exists()
