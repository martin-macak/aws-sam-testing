import logging
from typing import Generator

import pytest

from aws_sam_testing.aws_sam import LocalApi
from aws_sam_testing.pytest_addin.aws_context import AWSTestContext

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def aws_local_api(
    request,
    aws_context: AWSTestContext,
) -> Generator[list[LocalApi], None, None]:
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

    from aws_sam_testing.aws_sam import AWSSAMToolkit

    project_root = aws_context.get_project_root()
    template_path = aws_context.get_template_path()

    toolkit = AWSSAMToolkit(
        working_dir=project_root,
        template_path=template_path,
    )

    build_dir = toolkit.sam_build()
    logger.info(f"Build directory: {build_dir}")

    isolation_level = aws_context.get_api_isolation_level()

    with toolkit.run_local_api(
        isolation_level=isolation_level,
        pytest_request_context=request,
    ) as local_apis:
        yield local_apis
