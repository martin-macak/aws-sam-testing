"""AWS SAM toolkit for managing local SAM API operations.

This module provides utilities for running and managing AWS SAM applications locally,
including API Gateway emulation and CloudFormation template handling.
"""

import logging
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union, cast

import pytest
from samcli.commands.local.cli_common.invoke_context import InvokeContext

from aws_sam_testing.cfn import CloudFormationTemplateProcessor
from aws_sam_testing.core import CloudFormationTool

logger = logging.getLogger(__name__)


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
    MOTO = "moto"


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
        pytest_request_context: pytest.FixtureRequest | None = None,
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
        self.server_pid: int | None = None
        self.pytest_request_context = pytest_request_context

    def __enter__(self) -> "LocalApi":
        self.ctx.__enter__()
        self.start()

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()
        self.ctx.__exit__(exc_type, exc_value, traceback)

    def start(self) -> None:
        if self.is_running:
            return

        if self.pytest_request_context is not None:

            def _finalize_local_api() -> None:
                self.stop()

            self.pytest_request_context.addfinalizer(_finalize_local_api)

        if self.port is None:
            from aws_sam_testing.util import find_free_port

            self.port = find_free_port()

        if self.host is None:
            self.host = "127.0.0.1"

        self._start_local_api()

        self.is_running = True

    def wait_for_api_to_be_ready(self) -> None:
        import socket
        import time

        max_retries = 20
        retry_count = 0
        connected = False

        while retry_count < max_retries and not connected:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex((self.host, self.port))
                if result == 0:
                    connected = True
                    sock.close()
                    break
            except Exception:
                pass
            finally:
                if sock is not None:
                    sock.close()

            retry_count += 1
            time.sleep(1)

        if not connected:
            raise RuntimeError(f"Failed to connect to local API at http://{self.host}:{self.port}")

    def _start_local_api(self) -> None:
        import os
        from tempfile import TemporaryDirectory

        from samcli.commands.local.lib.local_api_service import LocalApiService
        from samcli.local.docker.exceptions import ProcessSigTermException

        with TemporaryDirectory() as static_dir:
            service = LocalApiService(
                lambda_invoke_context=self.ctx,
                static_dir=str(static_dir),
                port=self.port,
                host=self.host,
                disable_authorizer=True,
                ssl_context=None,
            )

            pid = os.fork()
            if pid == 0:
                logger.info(f"Starting local API server at http://{self.host}:{self.port}")
                try:
                    service.start()
                except ProcessSigTermException:
                    pass
            else:
                self.server_pid = pid

    def stop(self) -> None:
        import os
        import signal

        if not self.is_running:
            return

        if self.server_pid is not None:
            try:
                os.kill(self.server_pid, signal.SIGKILL)
                os.waitpid(self.server_pid, 0)
            except Exception:
                logger.warning("Failed to kill server process", exc_info=True)

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
        import shutil
        from tempfile import TemporaryDirectory

        from samcli.commands.build.build_context import BuildContext

        if build_dir is None:
            build_dir = Path(self.working_dir) / ".aws-sam" / "aws-sam-testing-build"
        elif isinstance(build_dir, str):
            build_dir = Path(build_dir)

        # Remove the build directory and all its contents
        if build_dir.exists():
            shutil.rmtree(build_dir)

        if not build_dir.exists():
            build_dir.mkdir(parents=True, exist_ok=True)

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

    def sam_deploy(
        self,
        stack_name: str | None = None,
        s3_bucket: str | None = None,
        s3_prefix: str | None = None,
        image_repository: str | None = None,
        image_repositories: dict[str, str] | None = None,
        capabilities: list[str] | None = None,
        parameter_overrides: dict[str, str] | None = None,
        role_arn: str | None = None,
        notification_arns: list[str] | None = None,
        tags: dict[str, str] | None = None,
        kms_key_id: str | None = None,
        no_execute_changeset: bool = False,
        no_progressbar: bool = True,
        fail_on_empty_changeset: bool = False,
        confirm_changeset: bool = False,
        disable_rollback: bool = False,
        on_failure: str | None = None,
        force_upload: bool = False,
        signing_profiles: dict[str, str] | None = None,
        region: str | None = None,
        profile: str | None = None,
        use_json: bool = False,
        metadata: dict[str, str] | None = None,
        poll_delay: float = 5.0,
        max_wait_duration: int = 60,
        boto3_session: Any | None = None,
    ) -> None:
        """
        Deploy the SAM stack using direct API calls.

        This method packages and deploys the SAM application to AWS CloudFormation.
        Environment variables are modified only within the scope of this function.

        Args:
            stack_name: Name of the CloudFormation stack (defaults to "aws-sam-testing-stack")
            s3_bucket: S3 bucket for uploading artifacts (defaults to "aws-sam-testing-package", created if needed)
            s3_prefix: S3 prefix for uploaded artifacts
            image_repository: ECR repository URI for images
            image_repositories: Mapping of function logical ID to ECR repository URI
            capabilities: List of capabilities (e.g., CAPABILITY_IAM)
            parameter_overrides: Parameter overrides for the stack
            role_arn: IAM role ARN for CloudFormation to assume
            notification_arns: SNS topic ARNs for stack notifications
            tags: Tags to apply to the stack
            kms_key_id: KMS key ID for S3 encryption
            no_execute_changeset: If True, create changeset but don't execute it
            no_progressbar: If True, disable progress bars
            fail_on_empty_changeset: If True, fail when changeset is empty
            confirm_changeset: If True, prompt for changeset confirmation
            disable_rollback: If True, disable rollback on failure
            on_failure: Action on failure (ROLLBACK, DELETE, or DO_NOTHING)
            force_upload: If True, force re-upload of artifacts
            signing_profiles: Code signing profiles
            region: AWS region (defaults to environment variable or "us-east-1")
            profile: AWS profile (defaults to environment variable)
            use_json: If True, use JSON for template format
            metadata: Metadata to attach to uploaded artifacts
            poll_delay: Delay in seconds between CloudFormation stack status checks
            max_wait_duration: Maximum time in minutes to wait for deployment
            boto3_session: Optional boto3 Session to use for AWS API calls
        """
        import os
        from contextlib import contextmanager

        import boto3
        from botocore.exceptions import ClientError
        from samcli.commands.deploy.deploy_context import DeployContext
        from samcli.commands.package.package_context import PackageContext
        from samcli.lib.utils import osutils

        # Use values from samconfig if not provided
        final_stack_name = stack_name or "aws-sam-testing-stack"
        final_parameter_overrides = parameter_overrides or {}
        final_region = region or os.environ.get("AWS_REGION", "us-east-1")
        final_profile = profile or os.environ.get("AWS_PROFILE")
        final_capabilities = capabilities or ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]
        final_s3_bucket = s3_bucket or "aws-sam-testing-package"

        # Create a context manager to handle environment variables
        @contextmanager
        def environment_variables():
            """Context manager to temporarily set environment variables."""
            original_env = {}
            env_vars = {}

            if final_region:
                env_vars["AWS_DEFAULT_REGION"] = final_region
            if final_profile:
                env_vars["AWS_PROFILE"] = final_profile

            # Set SAM_CLI_POLL_DELAY if different from default
            if poll_delay != 5.0:
                env_vars["SAM_CLI_POLL_DELAY"] = str(poll_delay)

            # Save original values and set new ones
            for key, value in env_vars.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

            try:
                yield
            finally:
                # Restore original values
                for key, original_value in original_env.items():
                    if original_value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = original_value

        # Get the template file path
        template_file = str(self.template_path)

        # Check if we should use the build directory template
        build_template = Path(self.working_dir) / ".aws-sam" / "aws-sam-testing-build" / "template.yaml"
        if build_template.exists():
            template_file = str(build_template)

        # Ensure the template exists
        if not os.path.exists(template_file):
            raise FileNotFoundError(f"Template file not found: {template_file}")

        # Create S3 client using provided session or default
        if boto3_session:
            s3_client = boto3_session.client("s3", region_name=final_region)
        else:
            s3_client = boto3.client("s3", region_name=final_region)

        # Create S3 bucket if it doesn't exist and we're using the default bucket
        if not s3_bucket:  # Using default bucket
            try:
                # Check if bucket exists
                s3_client.head_bucket(Bucket=final_s3_bucket)
                logger.info(f"Using existing S3 bucket: {final_s3_bucket}")
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "404":
                    # Bucket doesn't exist, create it
                    logger.info(f"Creating S3 bucket: {final_s3_bucket}")
                    try:
                        if final_region == "us-east-1":
                            # us-east-1 doesn't accept LocationConstraint
                            s3_client.create_bucket(Bucket=final_s3_bucket)
                        else:
                            s3_client.create_bucket(
                                Bucket=final_s3_bucket,
                                CreateBucketConfiguration={"LocationConstraint": final_region},  # type: ignore
                            )
                        logger.info(f"S3 bucket created successfully: {final_s3_bucket}")
                    except ClientError as create_error:
                        logger.error(f"Failed to create S3 bucket: {create_error}")
                        raise
                else:
                    # Some other error occurred
                    logger.error(f"Error checking S3 bucket: {e}")
                    raise

        with environment_variables():
            # Package and deploy within a temporary file context
            with osutils.tempfile_platform_independent() as output_template_file:
                # Package the template
                with PackageContext(
                    template_file=template_file,
                    s3_bucket=final_s3_bucket,
                    s3_prefix=s3_prefix,
                    image_repository=image_repository,
                    image_repositories=image_repositories,
                    output_template_file=output_template_file.name,
                    kms_key_id=kms_key_id,
                    use_json=use_json,
                    force_upload=force_upload,
                    no_progressbar=no_progressbar,
                    metadata=metadata,
                    on_deploy=True,
                    region=final_region,
                    profile=final_profile,
                    signing_profiles=signing_profiles,
                    parameter_overrides=final_parameter_overrides,
                ) as package_context:
                    package_context.run()

                # Deploy the packaged template
                with DeployContext(
                    template_file=output_template_file.name,
                    stack_name=final_stack_name,
                    s3_bucket=final_s3_bucket,
                    image_repository=image_repository,
                    image_repositories=image_repositories,
                    force_upload=force_upload,
                    no_progressbar=no_progressbar,
                    s3_prefix=s3_prefix,
                    kms_key_id=kms_key_id,
                    parameter_overrides=final_parameter_overrides,
                    capabilities=final_capabilities,
                    no_execute_changeset=no_execute_changeset,
                    role_arn=role_arn,
                    notification_arns=notification_arns or [],
                    fail_on_empty_changeset=fail_on_empty_changeset,
                    tags=tags or {},
                    region=final_region,
                    profile=final_profile,
                    confirm_changeset=confirm_changeset,
                    signing_profiles=signing_profiles,
                    use_changeset=True,
                    disable_rollback=disable_rollback,
                    poll_delay=poll_delay,
                    on_failure=on_failure,
                    max_wait_duration=max_wait_duration,
                ) as deploy_context:
                    deploy_context.run()

    @contextmanager
    def run_local_api(
        self,
        isolation_level: IsolationLevel = IsolationLevel.NONE,
        parameters: Optional[Dict[str, Any]] = None,
        port: Optional[int] = None,
        host: Optional[str] = None,
        pytest_request_context: pytest.FixtureRequest | None = None,
    ) -> Generator[list[LocalApi], None, None]:
        """Run a local API Gateway instance for testing.

        This context manager starts a local API Gateway emulator for the specified
        API resource and ensures proper cleanup after use.

        This stack uses AWS SAM local to run the local API.
        The SAM local has a limitation which starts the first API resource in the template.
        To work around this, the template is inspected and broken into multiple stacks,
        each containing a single API resource.
        The stacks are then built and run locally, resulting in multiple API Gateway instances
        running in parallel on different ports.

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
        import os

        # import docker
        from contextlib import ExitStack

        from moto.cloudformation.parsing import ResourceMap
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        from aws_sam_testing.cfn import dump_yaml
        from aws_sam_testing.moto_server import MotoServer

        # Validate parameters
        if port is not None and (port < 1 or port > 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")

        if host is not None and not host.strip():
            raise ValueError("Host cannot be empty")

        # docker_client = docker.from_env()

        cfn_processor = CloudFormationTemplateProcessor(self.template)

        # Find API resources
        apis = cfn_processor.find_resources_by_type("AWS::Serverless::Api")
        if not apis:
            # At least one API resource is required
            raise ValueError("No API resources found in template")

        api_handlers = []
        context_resources = []

        if pytest_request_context is not None:

            def _finalize_context_resources() -> None:
                for resource in context_resources:
                    if isinstance(resource, MotoServer):
                        resource.stop()
                    elif isinstance(resource, LocalApi):
                        resource.stop()

            pytest_request_context.addfinalizer(_finalize_context_resources)

        if isolation_level == IsolationLevel.MOTO:
            moto_server = MotoServer()
            moto_server.start()
            context_resources.append(moto_server)
            moto_server.wait_for_start()

            resource_map = ResourceMap(
                stack_id="test-stack",
                stack_name="test-stack",
                parameters={},
                tags={},
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
                account_id="123456789012",
                template=self.template,
                cross_stack_resources={},
            )
            resource_map.load()
            resource_map.create(self.template)

            # I am not sure if setting this as env var using SAM CLI toolkit works, check tests/third_party/test_sam_cli.py
            # I was not able to see env vars in the container and its lambda functions.
            cfn_processor.update_template(
                {
                    "Globals": {
                        "Function": {
                            "Environment": {
                                "Variables": {
                                    "AWS_ENDPOINT_URL": f"http://host.docker.internal:{moto_server.port}",
                                },
                            },
                        },
                    }
                }
            )

        for api in apis:
            # Each API is processed in a separate stack, so we need to create a new template for each API.
            api_logical_id = api[0]
            api_data = api[1]

            # Now we need to remove the API resources and their dependencies, because sam local start-api can
            # safely execute only stacks with a single API resource.
            apis_to_remove = [api for api in apis if api[0] != api_logical_id]
            api_stack_cfn_processor = CloudFormationTemplateProcessor(cfn_processor.processed_template)

            if apis_to_remove:
                # First, remove all other API resources
                for api in apis_to_remove:
                    api_stack_cfn_processor.remove_resource(api[0])
                api_stack_template = cast(Dict[str, Any], api_stack_cfn_processor.processed_template.copy())
            else:
                api_stack_template = cast(Dict[str, Any], api_stack_cfn_processor.processed_template.copy())

            # We need to create a new template and build it so we can run the API locally
            # The file is created in the same directory as the original template so all the relative paths are correct
            # We also need to create this template at the exact spot where the original template is, so we don't have to relocate
            # all paths in the template.
            api_stack_template_path = Path(self.template_path.parent) / f"template-{api_logical_id}.temp.yaml"
            api_stack_template_debug_path = Path(self.template_path.parent) / ".aws-sam" / "aws-sam-testing-build" / f"api-stack-{api_logical_id}" / "template.yaml"

            # Create the debug directory and the template file
            api_stack_template_debug_path.parent.mkdir(parents=True, exist_ok=True)
            with open(api_stack_template_debug_path, "w") as f:
                dump_yaml(api_stack_template, f)

            try:
                with open(api_stack_template_path, "w") as f:
                    dump_yaml(api_stack_template, f)

                api_stack_tool = AWSSAMToolkit(
                    working_dir=self.working_dir,
                    template_path=api_stack_template_path,
                )

                # Build the stack for the API template.
                api_stack_build_dir = api_stack_tool.sam_build(
                    build_dir=Path(self.working_dir) / ".aws-sam" / "aws-sam-testing-build" / f"api-stack-{api_logical_id}",
                )

                log_file = Path(self.working_dir) / ".aws-sam" / "aws-sam-testing-build" / f"api-stack-{api_logical_id}" / "log.txt"

                match isolation_level:
                    case IsolationLevel.NONE | IsolationLevel.MOTO:
                        invoke_ctx = InvokeContext(
                            template_file=str(api_stack_build_dir / "template.yaml"),
                            function_identifier=None,
                            env_vars_file=None,
                            docker_volume_basedir=str(api_stack_build_dir),
                            docker_network=None,
                            container_host_interface="127.0.0.1",
                            container_host="localhost",
                            layer_cache_basedir=str(api_stack_build_dir),
                            force_image_build=False,
                            skip_pull_image=False,
                            log_file=str(log_file),
                            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
                            aws_profile=os.environ.get("AWS_PROFILE"),
                            warm_container_initialization_mode="EAGER",
                        )

                        # Run the API locally.
                        local_api = LocalApi(
                            ctx=invoke_ctx,
                            toolkit=self,
                            api_logical_id=api_logical_id,
                            api_data=api_data,
                            parameters=parameters,
                            isolation_level=isolation_level,
                            port=port,
                            host=host,
                            pytest_request_context=pytest_request_context,
                        )
                        context_resources.append(local_api)
            finally:
                # Remove the temporary template
                api_stack_template_path.unlink(missing_ok=True)

            api_handlers.append(local_api)

        # Run APIs in managed context.
        with ExitStack() as stack:
            stack_resources = [stack.enter_context(context_resource) for context_resource in context_resources]

            yield [context_resource for context_resource in stack_resources if isinstance(context_resource, LocalApi)]
