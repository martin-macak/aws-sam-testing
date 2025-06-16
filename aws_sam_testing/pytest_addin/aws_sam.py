import pytest


@pytest.fixture(scope="session")
def aws_sam(request):
    from aws_sam_testing.aws_sam import AWSSAMToolkit
    from aws_sam_testing.util import find_project_root

    project_root = find_project_root(request.node.fspath.dirname)
    template_path = project_root / "template.yaml"

    toolkit = AWSSAMToolkit(
        working_dir=project_root,
        template_path=template_path,
    )

    yield toolkit
