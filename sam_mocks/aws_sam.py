"""AWS SAM toolkit for managing local SAM API operations.

This module provides utilities for running and managing AWS SAM applications locally,
including API Gateway emulation and CloudFormation template handling.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union
import os

from sam_mocks.core import CloudFormationTool

from enum import Enum


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
        toolkit: CloudFormationTool,
        api_logical_id: str,
        api_data: dict[str, Any],
        isolation_level: IsolationLevel,
        port: Optional[int] = None,
        host: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.toolkit = toolkit
        self.api_logical_id = api_logical_id
        self.api_data = api_data
        self.parameters = parameters
        self.isolation_level = isolation_level
        self.port = port
        self.host = host

    def __enter__(self) -> "LocalApi":
        if self.port is None:
            from sam_mocks.util import find_free_port

            self.port = find_free_port()

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        # TODO: Implement cleanup logic when API server functionality is added
        # For example: stop running server, cleanup temp files, etc.
        pass


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
        from samcli.commands.build.build_context import BuildContext
        from tempfile import TemporaryDirectory
        import os

        if build_dir is None:
            build_dir = Path(self.working_dir) / ".aws-sam" / "sam-mocks-build"
        elif isinstance(build_dir, str):
            build_dir = Path(build_dir)

        if not build_dir.exists():
            build_dir.mkdir(parents=True, exist_ok=True)

        # Remove all files in the build directory
        for file in build_dir.iterdir():
            file.unlink()

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
        api_logical_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        port: Optional[int] = None,
        host: Optional[str] = None,
    ) -> Generator[LocalApi, None, None]:
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
        # Validate parameters
        if port is not None and (port < 1 or port > 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")

        if host is not None and not host.strip():
            raise ValueError("Host cannot be empty")

        apis = self.cfn_processor.find_resources_by_type("AWS::Serverless::Api")
        if not apis:
            raise ValueError("No API resources found in template")

        if not api_logical_id and len(apis) > 1:
            raise ValueError("Multiple API resources found in template, please specify a logical ID")

        if api_logical_id:
            logical_id, api_data = self.cfn_processor.find_resource_by_logical_id(api_logical_id)
        elif len(apis) == 1:
            logical_id, api_data = apis[0]
        else:
            raise ValueError("Multiple API resources found in template, please specify a logical ID")

        if not api_data:
            raise ValueError(f"API resource with logical ID {api_logical_id} not found")

        if not api_data.get("Type") == "AWS::Serverless::Api":
            raise ValueError(f"Resource with logical ID {api_logical_id} is not an API resource")

        local_api = LocalApi(
            toolkit=self,
            api_logical_id=logical_id,
            api_data=api_data,
            parameters=parameters,
            isolation_level=isolation_level,
            port=port,
            host=host,
        )

        yield local_api
