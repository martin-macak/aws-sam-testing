import logging
from typing import Generator

import pytest

from aws_sam_testing.localstack import LocalStack
from aws_sam_testing.pytest_addin.aws_context import AWSTestContext

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def aws_localstack(
    request,
    aws_context: AWSTestContext,
) -> Generator[LocalStack, None, None]:
    """
    Pytest fixture that builds and runs a local AWS SAM API for the duration of the test session.

    This fixture:
      - Uses the current AWS test context (provided by the `aws_context` fixture) to determine
        the project root, template path, and API isolation level.
      - Builds the SAM application using the specified template and project root.
      - Starts the local API gateway(s) as defined in the SAM template, yielding a list of
        `LocalApi` objects representing the running local APIs.
      - Ensures the local APIs are properly shut down after the session.

    Usage:
      - Include `aws_local_api` as a fixture in your test to automatically build and run the local API.
      - To customize the behavior (such as project root, template name, or isolation level), use the
        `aws_context` fixture in your test or a session-scoped setup fixture, and call its setter methods
        before `aws_local_api` is used. For example:

            def setup(aws_context):
                aws_context.set_project_root(Path("/my/project"))
                aws_context.set_template_name("my_template.yaml")
                aws_context.set_api_isolation_level(IsolationLevel.PROCESS)

    Note:
      - The `aws_context` fixture should be used to configure the environment before `aws_local_api` is invoked.
      - All tests within a session will share the same configuration unless the context is modified in a session-scoped fixture.

    Yields:
        list[LocalApi]: A list of running LocalApi objects for interacting with the local AWS APIs.
    """

    from aws_sam_testing.localstack import LocalStackToolkit

    project_root = aws_context.get_project_root()
    template_path = aws_context.get_template_path()

    aws_sam_build = project_root / ".aws-sam" / "build"
    aws_sam_build_template = aws_sam_build / "template.yaml"

    if not aws_sam_build_template.exists():
        raise ValueError(f"AWS SAM build template {aws_sam_build_template} does not exist. Please run `sam build` first.")

    if not template_path.exists():
        raise ValueError(f"Template path {template_path} does not exist. Please run `sam build` first.")

    toolkit = LocalStackToolkit(
        working_dir=aws_sam_build,
        template_path=aws_sam_build_template,
    )

    if aws_context.get_localstack_runs_build():
        build_dir = toolkit.build(
            build_dir=aws_context.get_build_dir(),
            feature_set=aws_context.get_localstack_feature_set(),
        )
    else:
        build_dir = aws_context.get_build_dir()

    with toolkit.run_localstack(
        build_dir=build_dir,
        template_path=aws_sam_build_template,
        pytest_request_context=request,
    ) as localstack:
        yield localstack
