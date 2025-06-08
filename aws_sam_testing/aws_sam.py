"""AWS SAM toolkit for managing local SAM API operations.

This module provides utilities for running and managing AWS SAM applications locally,
including API Gateway emulation and CloudFormation template handling.
"""

from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union

from samcli.commands.local.cli_common.invoke_context import InvokeContext

from aws_sam_testing.cfn import CloudFormationTemplateProcessor
from aws_sam_testing.core import CloudFormationTool


class IsolationLevel(Enum):
    """Enum representing different isolation levels for SAM API operations.

    This enum defines the possible isolation levels that can be used when running
    SAM API operations locally. Each level represents a different degree of
    isolation between API and the AWS resources.

    Attributes:
        NONE: No isolation between API resouses. Current AWS profile and session is used
            and the API will try to connect to the real AWS resources.
    """

    NONE = "none"


class LocalApi:
    """Represents a local API Gateway instance for SAM applications.

    This class manages the lifecycle and configuration of a locally running
    API Gateway emulator for testing SAM applications.

    Attributes:
        toolkit: The CloudFormationTool instance used for template operations.
        api_logical_id: The logical ID of the API Gateway resource in the template.
        api_data: Dictionary containing the API Gateway resource configuration.
        parameters: Optional dictionary of CloudFormation parameters for the API.
        isolation_level: The isolation level for API operations.
        port: Optional port number for the local API Gateway.
        host: Optional host address for the local API Gateway.
    """

    def __init__(
        self,
        ctx: InvokeContext,
        toolkit: CloudFormationTool,
        api_logical_id: str,
        api_data: dict[str, Any],
        isolation_level: IsolationLevel,
        port: Optional[int] = None,
        host: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.ctx = ctx
        self.toolkit = toolkit
        self.api_logical_id = api_logical_id
        self.api_data = api_data
        self.parameters = parameters
        self.isolation_level = isolation_level
        self.port = port
        self.host = host
        self.is_running = False

    def __enter__(self) -> "LocalApi":
        self.start()

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def start(self) -> None:
        if self.is_running:
            return

        if self.port is None:
            from aws_sam_testing.util import find_free_port

            self.port = find_free_port()

        self.is_running = True

    def stop(self) -> None:
        if not self.is_running:
            return

        self.is_running = False


class AWSSAMToolkit(CloudFormationTool):
    """Toolkit for managing AWS SAM applications locally.

    This class extends CloudFormationTool to provide SAM-specific functionality,
    including the ability to run local API Gateway instances for testing.

    Attributes:
        working_dir: The working directory for SAM operations (inherited from CloudFormationTool).
        template_path: Path to the SAM/CloudFormation template file (inherited from CloudFormationTool).

    Example:
        >>> toolkit = AWSSAMToolkit(working_dir="/path/to/project")
        >>> with toolkit.run_local_api("MyApiResource") as api:
        ...     # Use the local API instance
        ...     pass
    """

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the AWS SAM Toolkit.

        Args:
            *args: Positional arguments passed to CloudFormationTool.
            **kwargs: Keyword arguments passed to CloudFormationTool.
                working_dir: Optional working directory path.
                template_path: Optional path to SAM/CloudFormation template.
        """
        super().__init__(*args, **kwargs)

    def sam_build(
        self,
        build_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Build the SAM application.

        Args:
            build_dir (Optional[Union[str, Path]], optional): The path to the build directory.

        Returns:
            Path: The path to the build directory.
        """
        import os
        from tempfile import TemporaryDirectory

        from samcli.commands.build.build_context import BuildContext

        if build_dir is None:
            build_dir = Path(self.working_dir) / ".aws-sam" / "aws-sam-testing-build"
        elif isinstance(build_dir, str):
            build_dir = Path(build_dir)

        if not build_dir.exists():
            build_dir.mkdir(parents=True, exist_ok=True)

        # Remove all files in the build directory
        for file in build_dir.iterdir():
            file.unlink(missing_ok=True)

        # Call SAM build
        with TemporaryDirectory() as cache_dir:
            with BuildContext(
                resource_identifier=None,
                template_file=str(self.template_path),
                base_dir=str(self.working_dir),
                build_dir=str(build_dir),
                cache_dir=cache_dir,
                parallel=True,
                mode="build",
                cached=False,
                clean=True,
                use_container=False,
                aws_region=os.environ.get("AWS_REGION", "eu-west-1"),
            ) as ctx:
                ctx.run()

        # Return the build directory
        return build_dir

    @contextmanager
    def run_local_api(
        self,
        isolation_level: IsolationLevel = IsolationLevel.NONE,
        parameters: Optional[Dict[str, Any]] = None,
        port: Optional[int] = None,
        host: Optional[str] = None,
    ) -> Generator[list[LocalApi], None, None]:
        """Run a local API Gateway instance for testing.

        This context manager starts a local API Gateway emulator for the specified
        API resource and ensures proper cleanup after use.

        Args:
            isolation_level: The isolation level to use for the API.
            api_logical_id: The logical ID of the API resource in the SAM template.
                If None, attempts to use the default or first API resource found.
            parameters: Optional parameters to pass to the API.

        Yields:
            LocalApi: A LocalApi instance representing the running API Gateway.

        Example:
            >>> with toolkit.run_local_api("MyRestApi") as api:
            ...     # Make requests to the local API
            ...     pass
        """
        import yaml
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        # Validate parameters
        if port is not None and (port < 1 or port > 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")

        if host is not None and not host.strip():
            raise ValueError("Host cannot be empty")

        cfn_processor = CloudFormationTemplateProcessor(self.template)

        # Find API resources
        apis = cfn_processor.find_resources_by_type("AWS::Serverless::Api")
        if not apis:
            # At least one API resource is required
            raise ValueError("No API resources found in template")

        api_handers = []

        for api in apis:
            api_logical_id = api[0]
            api_data = api[1]

            # Now we need to remove the API resources and their dependencies, because sam local start-api can
            # safely execute only stacks with a single API resource.
            apis_to_remove = [api for api in apis if api[0] != api_logical_id]
            api_stack_cfn_processor = CloudFormationTemplateProcessor(self.template)
            if apis_to_remove:
                for api in apis_to_remove:
                    api_stack_cfn_processor.remove_resource(api[0])
                api_stack_template = api_stack_cfn_processor.processed_template.copy()
            else:
                api_stack_template = api_stack_cfn_processor.processed_template.copy()

            # We need to create a new template and build it so we can run the API locally
            # The file is created in the same directory as the original template so all the relative paths are correct
            # The built template must be removed so it does not stick around after the build is done:
            api_stack_template_path = Path(self.template_path.parent) / f"template-aws-sam-testing-{api_logical_id}.yaml"
            with open(api_stack_template_path, "w") as f:
                yaml.dump(api_stack_template, f)

            # Build the API stack template
            # Also delete the template after the build is done
            try:
                api_stack_tool = AWSSAMToolkit(
                    working_dir=self.working_dir,
                    template_path=api_stack_template_path,
                )
                api_stack_template_path = api_stack_tool.sam_build(
                    build_dir=Path(self.working_dir) / ".aws-sam" / "aws-sam-testing-build" / f"api-stack-{api_logical_id}",
                )
            finally:
                api_stack_template_path.unlink(missing_ok=True)

            with InvokeContext(
                template_file=str(api_stack_template_path),
                function_identifier=None,
                env_vars_file=None,
                docker_volume_basedir=None,
                docker_network=None,
            ) as ctx:
                local_api = LocalApi(
                    ctx=ctx,
                    toolkit=self,
                    api_logical_id=api_logical_id,
                    api_data=api_data,
                    parameters=parameters,
                    isolation_level=isolation_level,
                    port=port,
                    host=host,
                )

            api_handers.append(local_api)

        for api_handler in api_handers:
            api_handler.start()

        try:
            yield api_handers
        finally:
            for api_handler in api_handers:
                api_handler.stop()
