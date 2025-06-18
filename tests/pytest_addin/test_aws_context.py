from pathlib import Path
from typing import Generator

import pytest

from aws_sam_testing.pytest_addin.aws_context import AWSTestContext


class TestAWSContext:
    """
    This test case shows how it's possible to modify the project root and the template name
    for the AWS context.

    All tests within given session will have the same project root and template name.
    """

    @pytest.fixture(scope="session")
    def prepare_filesystem(self) -> Generator[tuple[Path, Path], None, None]:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "template.custom.yaml").write_text("template: custom")
            yield tmp_path, tmp_path / "template.custom.yaml"

    @pytest.fixture(
        autouse=True,
        scope="session",
    )
    def setup(self, aws_context, prepare_filesystem):
        tmp_path, template_path = prepare_filesystem
        aws_context.set_template_name(template_path.name)
        aws_context.set_project_root(tmp_path)

    def test_aws_context(self, aws_context: AWSTestContext):
        project_root = aws_context.get_project_root()
        template_name = aws_context.get_template_name()
        assert project_root is not None
        assert template_name is not None
        assert project_root.exists()
        # check that the template.custom.yaml exists
        assert (project_root / template_name).exists()
