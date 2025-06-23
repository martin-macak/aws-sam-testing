import functools
import logging
import re
import threading
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Generator

import pytest

from aws_sam_testing.cfn import CloudFormationTemplateProcessor
from aws_sam_testing.core import CloudFormationTool

logger = logging.getLogger(__name__)

localstack_logger = logging.getLogger("aws_sam_testing.localstack_logger")


class LocalStackFeautureSet(Enum):
    NORMAL = "normal"
    PRO = "pro"


class LocalStackApi:
    def __init__(
        self,
        api_id: str,
        api_gateway_stage_name: str,
        base_url: str,
    ):
        self.api_id = api_id
        self.api_gateway_stage_name = api_gateway_stage_name
        self.base_url = base_url


class LocalStack:
    def __init__(
        self,
        region: str = "us-east-1",
        pytest_request_context: pytest.FixtureRequest | None = None,
    ):
        from docker.models.containers import Container

        self.region = region
        self.is_running = False
        self.moto_server = None
        self.pytest_request_context = pytest_request_context
        self.host: str | None = None
        self.port: int | None = None
        self.container: Container | None = None
        self._log_thread: threading.Thread | None = None
        self._stop_logging = threading.Event()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self):
        if self.is_running:
            return

        if self.pytest_request_context is not None:
            self.pytest_request_context.addfinalizer(self.stop)

        self._do_start()
        self.is_running = True

    def stop(self):
        if not self.is_running:
            return

        self._do_stop()
        self.is_running = False

    def restart(self):
        self.stop()
        self.start()

    @contextmanager
    def environment(self):
        from aws_sam_testing.util import set_environment

        with set_environment(
            AWS_ENDPOINT_URL=f"http://{self.host}:{self.port}",
        ):
            yield

    def _do_start(self):
        from docker import DockerClient

        from aws_sam_testing.util import find_free_port

        port = find_free_port()
        self.host = "localhost"
        self.port = port

        docker_client = DockerClient.from_env()
        container = docker_client.containers.run(
            "localstack/localstack:latest",
            ports={"4566/tcp": port},
            detach=True,
            privileged=True,
            environment={
                "AWS_REGION": self.region,
                "AWS_DEFAULT_REGION": self.region,
            },
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
        )
        self.container = container
        self._start_logging()
        self.wait_for_localstack_to_be_ready()

    def _start_logging(self):
        container = self.container
        if container is None:
            return

        def _log_stream_worker():
            """Worker thread that streams and processes container logs."""
            try:
                # Stream logs from the container
                log_stream = container.logs(stream=True, follow=True, timestamps=False)

                # Regular expression to parse LocalStack log format
                # Example: 2025-06-19T05:48:12.906  INFO --- [et.reactor-0] localstack.request.aws     : AWS s3.ListBuckets => 200
                log_pattern = re.compile(
                    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\s+"  # timestamp
                    r"(\w+)\s+"  # log level (INFO, DEBUG, WARNING, ERROR, etc.)
                    r"---\s+"  # separator
                    r"\[([^\]]+)\]\s+"  # thread/context in brackets
                    r"([^\s]+)\s*:\s*"  # logger name
                    r"(.*)$"  # message
                )

                for line in log_stream:
                    # Check if we should stop
                    if self._stop_logging.is_set():
                        break

                    try:
                        # Decode the log line
                        if isinstance(line, bytes):
                            line = line.decode("utf-8", errors="replace")
                        line = line.strip()

                        if not line:
                            continue

                        # Try to parse the LocalStack log format
                        match = log_pattern.match(line)
                        if match:
                            timestamp, level, thread, logger_name, message = match.groups()

                            # Map LocalStack log levels to Python logging levels
                            level_mapping = {
                                "DEBUG": logging.DEBUG,
                                "INFO": logging.INFO,
                                "WARN": logging.WARNING,
                                "WARNING": logging.WARNING,
                                "ERROR": logging.ERROR,
                                "CRITICAL": logging.CRITICAL,
                                "FATAL": logging.CRITICAL,
                            }

                            log_level = level_mapping.get(level.upper(), logging.INFO)

                            # Log the message with appropriate level
                            localstack_logger.log(
                                log_level,
                                f"[{thread}] {logger_name}: {message}",
                                extra={"localstack_timestamp": timestamp},
                            )
                        else:
                            # If the line doesn't match the expected format, log it as-is at INFO level
                            localstack_logger.info(line)

                    except Exception as e:
                        # Log any parsing errors but continue processing
                        logger.error(f"Error parsing LocalStack log line: {e}")

            except Exception as e:
                # Log any errors in the streaming itself
                logger.error(f"Error streaming LocalStack logs: {e}")
            finally:
                logger.debug("LocalStack log streaming stopped")

        # Start the logging thread
        self._log_thread = threading.Thread(
            target=_log_stream_worker,
            name="localstack-log-stream",
            daemon=True,  # Daemon thread will automatically stop when main program exits
        )
        self._log_thread.start()
        logger.debug("Started LocalStack log streaming thread")

    def _do_stop(self):
        # Stop the logging thread first
        if self._log_thread is not None:
            try:
                self._stop_logging.set()
                self._log_thread.join(timeout=5)  # Wait up to 5 seconds for thread to stop
                self._log_thread = None
                self._stop_logging.clear()
            except Exception as e:
                logger.error(f"Error stopping LocalStack log streaming thread: {e}")

        if self.container is not None:
            try:
                self.container.stop()
                self.container.remove()
            except Exception as e:
                logger.error(f"Error stopping LocalStack container: {e}")

    def wait_for_localstack_to_be_ready(self):
        import socket
        import time

        import boto3

        from aws_sam_testing.util import set_environment

        if self.host is None or self.port is None:
            raise RuntimeError("LocalStack is not running")

        max_attempts = 20
        for attempt in range(max_attempts):
            try:
                with socket.create_connection((self.host, self.port), timeout=2):
                    break
            except (OSError, ConnectionRefusedError):
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"LocalStack did not start on {self.host}:{self.port} after {max_attempts} seconds")
                time.sleep(1)

        # Additional check: use boto3 to verify S3 is available
        for attempt in range(max_attempts):
            try:
                with set_environment(
                    AWS_ENDPOINT_URL=f"http://{self.host}:{self.port}",
                ):
                    s3 = boto3.client(
                        "s3",
                        region_name=self.region,
                    )
                    s3.list_buckets()
                break
            except Exception:
                if attempt == max_attempts - 1:
                    raise RuntimeError("LocalStack S3 API did not become available after port was reachable.")
                time.sleep(1)

    @functools.cache
    def get_apis(self) -> list[LocalStackApi]:
        import boto3

        from aws_sam_testing.util import set_environment

        with set_environment(
            AWS_ENDPOINT_URL=f"http://{self.host}:{self.port}",
        ):
            apigateway = boto3.client(
                "apigateway",
                region_name=self.region,
            )

            api_gateway_response = apigateway.get_rest_apis()
            api_gateway_apis = api_gateway_response["items"]

            apis: list[LocalStackApi] = []

            for api_gateway_api in api_gateway_apis:
                api_id = api_gateway_api["id"]  # type: ignore
                api_gateway_stages_response = apigateway.get_stages(restApiId=api_id)  # type: ignore
                api_gateway_stages = api_gateway_stages_response["item"]
                for api_gateway_stage in api_gateway_stages:
                    api_gateway_stage_name = api_gateway_stage["stageName"]  # type: ignore

                    api = LocalStackApi(
                        api_id=api_id,
                        api_gateway_stage_name=api_gateway_stage_name,
                        base_url=f"http://{self.host}:{self.port}/_aws/execute-api/{api_id}/{api_gateway_stage_name}",
                    )
                    apis.append(api)

            return apis


class LocalStackToolkit(CloudFormationTool):
    """
    This CloudFormationTool should be established in the directory that contains the AWS SAM build.

    Args:
        CloudFormationTool (_type_): _description_
    """

    def build(
        self,
        feature_set: LocalStackFeautureSet = LocalStackFeautureSet.NORMAL,
        build_dir: Path | None = None,
        region: str | None = None,
    ) -> Path:
        """
        Creates a new AWS SAM build that can be executed in localstack.

        If feature_set is LocalStackFeautureSet.NORMAL, the build will be executed in localstack without PRO features.
        If feature_set is LocalStackFeautureSet.PRO, the build will be executed in localstack with PRO features.

        First the source template is used to create regular AWS SAM build.
        Then the AWS sam build is processed according to the feature set.
        Then the localstack is started and the processed build is deployed via SAM deploy to localstack.

        This function creates two builds:
        - base build: the base build that is used to create the processed build
        - processed build: the processed build that is used to deploy to localstack
        The base build will be created in build_dir/aws-sam-testing-localstack-base-build
        The processed build will be created in build_dir/aws-sam-testing-localstack-processed-build
        If the build dir is not provided, then the default <project_root>/.aws-sam/ base dir is used.
        For example:
            <project_root>/.aws-sam/aws-sam-testing-localstack-base-build
            <project_root>/.aws-sam/aws-sam-testing-localstack-processed-build

        Args:
            feature_set (LocalStackFeautureSet, optional): _description_. Defaults to LocalStackFeautureSet.NORMAL.
            build_dir (Path | None, optional): _description_. Defaults to None.

        Returns:
            Path: The path to the processed build directory.
        """
        import os

        from aws_sam_testing.cfn import dump_yaml

        if region is None:
            region = os.environ.get("AWS_REGION", "us-east-1")

        # localstack_base_build_dir is the directory where the base build is stored
        # localstack_processed_build_dir is the directory where the processed build is stored
        # processed_build is valid AWS SAM build with certain changes that match the supported localstack features

        if build_dir is None:
            build_dir = Path(self.working_dir) / ".aws-sam"
            localstack_processed_build_dir = Path(self.working_dir) / ".aws-sam" / "aws-sam-testing-localstack-processed-build"
        else:
            localstack_processed_build_dir = build_dir / "aws-sam-testing-localstack-processed-build"

        assert localstack_processed_build_dir is not None

        processed_template_path = self.template_path.parent / "template.localstack.yaml"
        if feature_set == LocalStackFeautureSet.NORMAL:
            processor = LocalStackCloudFormationTemplateProcessor(
                template=self.template,
            )
            processor.remove_pro_resources()
            processed_template = processor.processed_template
            dump_yaml(processed_template, stream=processed_template_path.open("w"))

            try:
                # process the lambda layers
                # this creates new AWS SAM build with flattened layers
                self._process_lambda_layers(
                    source_template_path=processed_template_path,
                    build_dir=localstack_processed_build_dir,
                    flatten_layers=True,
                    layer_cache_dir=build_dir / "tmp" / "aws-sam-testing-localstack-layers",
                    region=region,
                )
            finally:
                processed_template_path.unlink()
        else:
            raise NotImplementedError("PRO features are not supported yet")

        return localstack_processed_build_dir

    @contextmanager
    def run_localstack(
        self,
        build_dir: Path,
        template_path: Path | None,
        region: str | None = None,
        pytest_request_context: pytest.FixtureRequest | None = None,
        parameters: dict[str, str] = {},
    ) -> Generator[LocalStack, None, None]:
        import os

        from aws_sam_testing.aws_sam import AWSSAMToolkit
        from aws_sam_testing.util import set_environment

        if template_path is None:
            template_path = self.template_path
        else:
            template_path = Path(template_path)
        assert template_path is not None
        if not template_path.exists():
            raise ValueError(f"Template path {template_path} does not exist")

        if region is None:
            region = os.environ.get("AWS_REGION", "us-east-1")

        with LocalStack(
            region=region,
            pytest_request_context=pytest_request_context,
        ) as localstack:
            localstack.start()
            localstack.wait_for_localstack_to_be_ready()

            with set_environment(
                AWS_ENDPOINT_URL=f"http://{localstack.host}:{localstack.port}",
            ):
                sam_toolkit = AWSSAMToolkit(
                    working_dir=build_dir,
                    template_path=template_path,
                )
                sam_toolkit.sam_deploy(
                    build_dir=build_dir,
                    template_path=template_path,
                    region=localstack.region,
                    parameter_overrides=parameters or {},
                )

            yield localstack

    def _process_lambda_layers(
        self,
        source_template_path: Path,
        build_dir: Path,
        flatten_layers: bool = True,
        layer_cache_dir: Path | None = None,
        region: str | None = None,
    ) -> Path:
        """
        Processes the AWS SAM build directory so it can be executed safely in localstack.
        Localstack without PRO features does not support AWS Lambda layers.
        This can be solved by downloading all lambda layers referenced in the template and then packing all packages
        in correct order in each function.
        This works exactly as the layered file system. So all files and packages are incrementally merged into the final
        directory.

        For example:
        Lambda function SomeFunction has a layers layer_a and layer_b.
        The layer_a has a package package_a
        The layer_b has a package package_b.
        The function also packages package_c.

        After the processing, if flatten_layers is True, the function will have a directory with the following structure:
        SomeFunction/
            package_a/
            package_b/
            package_c/

        If flatten_layers is False, the function will have a directory with the following structure:
        SomeFunction/
            package_c/


        Also if flatten_layers was performed, all flattened layers are removed from the template
        For example:
        SomeFunction:
            Type: AWS::Serverless::Function
            Properties:
                Layers:
                    - !Ref LayerA
                    - !Ref LayerB
                PackageType: Zip
                CodeUri: SomeFunction/

        After the processing, the template will have the following structure:
        SomeFunction:
            Type: AWS::Serverless::Function
            Properties:
                PackageType: Zip
                CodeUri: SomeFunction/

        Flattening is performed in the directory given by the source_template_path. The algorithm reads
        all lambda functions in the template and then for each function it reads the layers and packages.
        It then processes them into new directory given in build_dir.

        The source_template_path is not modified as well as the lambda functions in the source template.
        New build is created in the build_dir. This build is valid AWS SAM build that can be executed in localstack.

        Layers are downloaded from AWS so valid AWS session is required when this function is called.
        Layers are downloaded only once and then cached in the layer_cache_dir.

        Args:
            source_template_path (Path): The source directory with input SAM build that will be processed.
            build_dir (Path): The destination directory where the SAM build with processed build.
            flatten_layers (bool, optional): _description_. Defaults to True.
            layer_cache_dir (Path, optional): The directory where the layers will be cached. Defaults to None.

        Returns:
            Path: The path to the new build directory.
        """
        import shutil

        # If not flattening layers, just copy the source to the build dir
        if not flatten_layers:
            if source_template_path.parent != build_dir:
                shutil.copytree(source_template_path.parent, build_dir, dirs_exist_ok=True)
            return build_dir

        # Set up layer cache directory
        if layer_cache_dir is None:
            layer_cache_dir = build_dir / ".layer-cache"
        layer_cache_dir.mkdir(parents=True, exist_ok=True)

        # Load the template
        from aws_sam_testing.cfn import dump_yaml, load_yaml_file

        template = load_yaml_file(str(source_template_path))
        processor = CloudFormationTemplateProcessor(template)
        template = processor.processed_template

        # Create build directory structure
        build_dir.mkdir(parents=True, exist_ok=True)

        # Find all Lambda and Serverless functions
        lambda_functions = processor.find_resources_by_type("AWS::Lambda::Function")
        serverless_functions = processor.find_resources_by_type("AWS::Serverless::Function")
        all_functions = lambda_functions + serverless_functions

        # Track which layers we've processed
        processed_layers = {}
        layers_to_remove = set()

        # Process each function
        for logical_id, function_data in all_functions:
            properties = function_data.get("Properties", {})

            # Skip if not a Zip package type
            if properties.get("PackageType") == "Image":
                continue

            # Get layers for this function
            layers = properties.get("Layers", [])
            if not layers:
                # No layers to process, just copy the function code
                self._copy_function_code(
                    source_template_path.parent,
                    build_dir,
                    logical_id,
                    properties,
                )
                continue

            # Create function directory in build
            function_build_dir = build_dir / logical_id
            function_build_dir.mkdir(parents=True, exist_ok=True)

            # Process layers in order (they are applied in order)
            for layer_ref in layers:
                layer_arn = self._resolve_layer_arn(layer_ref, region)
                if not layer_arn:
                    continue

                # Check if this is a local layer reference
                if layer_arn.startswith("!"):
                    # This is a local layer reference, handle it differently
                    local_layer_id = self._get_ref_value(layer_ref)
                    if local_layer_id:
                        self._copy_local_layer(
                            source_template_path.parent,
                            function_build_dir,
                            local_layer_id,
                            template,
                        )
                        layers_to_remove.add(local_layer_id)
                else:
                    # Download and cache the layer if needed
                    if layer_arn not in processed_layers:
                        layer_path = self._download_and_cache_layer(layer_arn, layer_cache_dir)
                        processed_layers[layer_arn] = layer_path

                    # Extract layer contents to function directory
                    if processed_layers[layer_arn]:
                        self._extract_layer_to_function(processed_layers[layer_arn], function_build_dir)

            # Copy the function's own code on top of layers
            self._copy_function_code(
                source_template_path.parent,
                function_build_dir,
                logical_id,
                properties,
            )

            # Remove Layers property from the function
            if "Layers" in processor.processed_template["Resources"][logical_id]["Properties"]:
                del processor.processed_template["Resources"][logical_id]["Properties"]["Layers"]

        # Remove layer resources that were flattened
        for layer_id in layers_to_remove:
            if layer_id in processor.processed_template.get("Resources", {}):
                processor.remove_resource(layer_id, auto_remove_dependencies=False)

        # Save the modified template
        output_template_path = build_dir / "template.yaml"
        dump_yaml(processor.processed_template, stream=output_template_path.open("w"))

        return build_dir

    def _substitute_cloudformation_variables(self, template_string: str, region: str | None = None) -> str:
        """Substitute CloudFormation variables in a string.

        This method substitutes CloudFormation variables (${variableName}) in a string
        with their actual values. Currently only supports AWS::Region variable.

        Args:
            template_string: The string containing variables to substitute
            region: The AWS region to use for substitution. If None, uses 'us-east-1' as default.

        Returns:
            str: The string with variables substituted

        Raises:
            ValueError: If the string contains unsupported variables

        Supported variables:
            - ${AWS::Region}: Replaced with the provided region

        Examples:
            >>> toolkit._substitute_cloudformation_variables("arn:aws:lambda:${AWS::Region}:123:layer:my-layer:1", "eu-west-1")
            'arn:aws:lambda:eu-west-1:123:layer:my-layer:1'
        """
        import re

        # Find all variables in the string
        variable_pattern = re.compile(r"\$\{([^}]+)\}")
        variables = variable_pattern.findall(template_string)

        # Check for unsupported variables
        supported_variables = {"AWS::Region"}
        unsupported = set(variables) - supported_variables
        if unsupported:
            raise ValueError(f"Unsupported CloudFormation variables: {', '.join(sorted(unsupported))}")

        # Substitute variables
        result = template_string
        if "AWS::Region" in variables:
            # Use provided region or default
            if region is None:
                region = "us-east-1"
            result = result.replace("${AWS::Region}", region)

        return result

    def _resolve_layer_arn(self, layer_ref: Any, region: str | None = None) -> str | None:
        """Resolve a layer reference to its ARN or a special reference identifier.

        This method handles different types of layer references that can appear in
        CloudFormation templates:

        1. Direct ARN strings: "arn:aws:lambda:region:account:layer:name:version"
        2. CloudFormation Ref: {"Ref": "LayerLogicalId"}
        3. CloudFormation GetAtt: {"Fn::GetAtt": ["LayerLogicalId", "Arn"]}
        4. CloudFormation Sub: {"Fn::Sub": "arn:aws:lambda:${AWS::Region}:..."}

        Args:
            layer_ref: The layer reference from the template. Can be:
                - str: Direct ARN string
                - dict: CloudFormation intrinsic function (Ref, GetAtt, Sub, etc.)
            region: The AWS region to use for variable substitution in Fn::Sub

        Returns:
            str | None:
                - For direct ARNs: returns the ARN string as-is
                - For Ref: returns "!Ref:LogicalId" to indicate a local reference
                - For Sub: returns the substituted string
                - For GetAtt: returns None (not currently supported)
                - For other types: returns None

        Examples:
            >>> toolkit._resolve_layer_arn("arn:aws:lambda:us-east-1:123:layer:my-layer:1")
            'arn:aws:lambda:us-east-1:123:layer:my-layer:1'

            >>> toolkit._resolve_layer_arn({"Ref": "MyLayer"})
            '!Ref:MyLayer'

            >>> toolkit._resolve_layer_arn({"Fn::Sub": "arn:aws:lambda:${AWS::Region}:123:layer:my-layer:1"}, "eu-west-1")
            'arn:aws:lambda:eu-west-1:123:layer:my-layer:1'
        """
        if isinstance(layer_ref, str):
            return layer_ref
        elif isinstance(layer_ref, dict):
            if "Ref" in layer_ref:
                # Local layer reference
                return f"!Ref:{layer_ref['Ref']}"
            elif "Fn::Sub" in layer_ref:
                # Handle Fn::Sub
                sub_value = layer_ref["Fn::Sub"]
                if isinstance(sub_value, str):
                    # Simple string substitution
                    return self._substitute_cloudformation_variables(sub_value, region)
                elif isinstance(sub_value, list) and len(sub_value) == 2:
                    # Format: [template_string, {var: value}]
                    # For now, we don't support custom variables in the second parameter
                    template_string = sub_value[0]
                    return self._substitute_cloudformation_variables(template_string, region)
                else:
                    return None
            elif "Fn::GetAtt" in layer_ref:
                # GetAtt reference
                return None  # Not supported for now
        return None

    def _get_ref_value(self, layer_ref: Any) -> str | None:
        """Extract the logical ID from a CloudFormation Ref.

        This method extracts the logical ID from various forms of CloudFormation
        references, supporting both standard CloudFormation syntax and our internal
        representation.

        Args:
            layer_ref: The layer reference to extract from. Can be:
                - dict: {"Ref": "LogicalId"} - Standard CloudFormation Ref
                - str: "!Ref:LogicalId" - Internal representation from _resolve_layer_arn
                - Any other type returns None

        Returns:
            str | None: The logical ID if found, None otherwise

        Examples:
            >>> toolkit._get_ref_value({"Ref": "MyLayer"})
            'MyLayer'

            >>> toolkit._get_ref_value("!Ref:MyLayer")
            'MyLayer'

            >>> toolkit._get_ref_value("not-a-ref")
            None
        """
        if isinstance(layer_ref, dict) and "Ref" in layer_ref:
            return layer_ref["Ref"]
        elif isinstance(layer_ref, str) and layer_ref.startswith("!Ref:"):
            return layer_ref[5:]  # Remove "!Ref:" prefix
        return None

    def _copy_local_layer(self, source_dir: Path, target_dir: Path, layer_id: str, template: dict) -> None:
        """Copy a local Lambda layer's contents to the target directory.

        This method handles copying layers that are defined within the same CloudFormation
        template (as opposed to external layers referenced by ARN). It follows AWS Lambda's
        layer directory structure conventions for different runtimes.

        The method looks for the layer in two locations:
        1. A directory named after the layer's logical ID
        2. The path specified in the layer's ContentUri property

        For Python layers, the contents of the 'python/' directory are copied directly
        to the target (following Lambda's behavior). For other runtimes, the runtime
        directory structure is preserved.

        Args:
            source_dir: The base directory containing the SAM build output
            target_dir: The target directory (usually the function's build directory)
            layer_id: The logical ID of the layer in the CloudFormation template
            template: The CloudFormation template containing the layer definition

        Layer Structure Examples:
            Python layer source:
                LayerLogicalId/
                    python/
                        my_module.py
                        my_package/
                            __init__.py

            Result in target:
                my_module.py
                my_package/
                    __init__.py

            Node.js layer source:
                LayerLogicalId/
                    nodejs/
                        node_modules/
                            express/

            Result in target:
                nodejs/
                    node_modules/
                        express/
        """
        import shutil

        # Find the layer resource
        if "Resources" not in template or layer_id not in template["Resources"]:
            return

        layer_resource = template["Resources"][layer_id]
        if layer_resource.get("Type") not in [
            "AWS::Lambda::LayerVersion",
            "AWS::Serverless::LayerVersion",
        ]:
            return

        properties = layer_resource.get("Properties", {})
        content_uri = properties.get("ContentUri", "")

        if not content_uri:
            return

        # Source layer directory
        layer_source = source_dir / layer_id
        if not layer_source.exists():
            # Try the ContentUri directly
            layer_source = source_dir / content_uri
            if not layer_source.exists():
                return

        # Copy layer contents following Lambda layer structure
        # Layers are extracted to /opt in Lambda, so we follow the same structure
        for runtime_dir in ["python", "nodejs", "ruby", "java"]:
            src_runtime = layer_source / runtime_dir
            if src_runtime.exists():
                dst_runtime = target_dir
                # For Python, contents go directly to the function directory
                if runtime_dir == "python":
                    # Copy all contents from python/ to the function root
                    for item in src_runtime.iterdir():
                        if item.is_dir():
                            shutil.copytree(item, dst_runtime / item.name, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, dst_runtime)
                else:
                    # For other runtimes, maintain the structure
                    shutil.copytree(src_runtime, dst_runtime / runtime_dir, dirs_exist_ok=True)

    def _download_and_cache_layer(self, layer_arn: str, cache_dir: Path) -> Path | None:
        """Download a Lambda layer from AWS and cache it locally.

        This method handles downloading external Lambda layers (those referenced by ARN)
        from AWS. Downloaded layers are cached to avoid repeated downloads.

        The cache uses an MD5 hash of the layer ARN as the filename to ensure
        uniqueness while maintaining a flat cache structure.

        Args:
            layer_arn: The full ARN of the Lambda layer version to download.
                Format: arn:aws:lambda:region:account:layer:layer-name:version
            cache_dir: Directory where downloaded layers should be cached

        Returns:
            Path | None: Path to the cached layer zip file if successful, None if:
                - The layer ARN is invalid
                - The layer cannot be accessed (permissions, doesn't exist, etc.)
                - Any error occurs during download

        Cache Behavior:
            - If a layer is already cached, it returns immediately without downloading
            - Cache files are named as: {md5_hash_of_arn}.zip
            - No cache expiration is implemented; layers are assumed immutable

        Error Handling:
            - Returns None for any errors rather than raising exceptions
            - This allows layer processing to continue even if some layers fail

        Example:
            >>> arn = "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:42"
            >>> path = toolkit._download_and_cache_layer(arn, Path("/tmp/cache"))
            >>> # Returns: Path("/tmp/cache/a1b2c3d4e5f6.zip") or None
        """
        import hashlib

        import boto3
        from botocore.exceptions import ClientError

        # Create a safe filename from the ARN
        arn_hash = hashlib.md5(layer_arn.encode()).hexdigest()
        cached_layer_path = cache_dir / f"{arn_hash}.zip"

        # Check if already cached
        if cached_layer_path.exists():
            return cached_layer_path

        try:
            # Parse the ARN to get layer name and version
            # Format: arn:aws:lambda:region:account:layer:layer-name:version
            arn_parts = layer_arn.split(":")
            if len(arn_parts) < 8 or arn_parts[5] != "layer":
                return None

            region = arn_parts[3]

            # Create Lambda client for the specific region
            lambda_client = boto3.client("lambda", region_name=region)

            # Get layer version info
            response = lambda_client.get_layer_version_by_arn(Arn=layer_arn)

            # Download the layer
            import urllib.request

            content = response.get("Content", {})
            download_url = content.get("Location")
            if not download_url:
                return None
            urllib.request.urlretrieve(download_url, cached_layer_path)

            return cached_layer_path

        except (ClientError, ValueError, KeyError) as e:
            logger.error(f"Error downloading layer {layer_arn}: {e}")
            raise

    def _extract_layer_to_function(self, layer_path: Path, function_dir: Path) -> None:
        """Extract layer zip contents to the function directory.

        This method extracts a downloaded Lambda layer and merges its contents with
        the function's code directory. It handles the standard Lambda layer directory
        structures for different runtimes.

        Lambda layers follow specific directory structures:
        - Python: python/ or python/lib/pythonX.Y/site-packages/
        - Node.js: nodejs/node_modules/
        - Ruby: ruby/gems/X.Y.0/
        - Java: java/lib/

        For Python (the most common case), this method:
        1. Extracts contents from python/ directly to the function root
        2. Also checks for site-packages in versioned Python paths
        3. Merges directories without deleting existing files

        Args:
            layer_path: Path to the layer zip file to extract
            function_dir: Target directory where layer contents should be extracted

        File Handling:
            - Uses dirs_exist_ok=True to merge directories
            - Existing files with the same name are overwritten
            - Files with unique names are preserved
            - Temporary extraction directory is always cleaned up

        Example:
            Layer zip structure:
                python/
                    requests/
                    urllib3/
                python/lib/python3.9/site-packages/
                    boto3/

            Result in function_dir:
                requests/
                urllib3/
                boto3/
                (existing function files preserved)
        """
        import shutil
        import zipfile

        if not layer_path.exists() or not zipfile.is_zipfile(layer_path):
            return

        with zipfile.ZipFile(layer_path, "r") as zip_ref:
            # Lambda layers are extracted to /opt, but we need to merge with function
            # Extract to a temporary directory first
            temp_extract = function_dir / ".temp_layer"
            temp_extract.mkdir(exist_ok=True)

            try:
                zip_ref.extractall(temp_extract)

                # Copy contents based on runtime structure
                # Python layers usually have python/ or python/lib/python*/site-packages/
                python_dir = temp_extract / "python"
                if python_dir.exists():
                    # Copy all contents from python/ to function root
                    for item in python_dir.iterdir():
                        if item.is_dir():
                            shutil.copytree(item, function_dir / item.name, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, function_dir)

                # Also check for direct site-packages
                for py_version in [
                    "python3.8",
                    "python3.9",
                    "python3.10",
                    "python3.11",
                    "python3.12",
                ]:
                    site_packages = temp_extract / "python" / "lib" / py_version / "site-packages"
                    if site_packages.exists():
                        for item in site_packages.iterdir():
                            if item.is_dir():
                                shutil.copytree(item, function_dir / item.name, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item, function_dir)

            finally:
                # Clean up temp directory
                shutil.rmtree(temp_extract, ignore_errors=True)

    def _copy_function_code(
        self,
        source_dir: Path,
        target_dir: Path,
        function_id: str,
        properties: dict,
    ) -> None:
        """Copy function code from source to target directory.

        This method copies the Lambda function's own code (not layer code) from the
        SAM build output to the target directory. It handles both explicit CodeUri
        paths and the default convention of using the function's logical ID as the
        directory name.

        The method looks for function code in two locations:
        1. A directory named after the function's logical ID
        2. The path specified in the function's CodeUri property

        Args:
            source_dir: The base directory containing the SAM build output
            target_dir: The target directory where function code should be copied
            function_id: The logical ID of the function in the CloudFormation template
            properties: The Properties section of the function resource, which may
                contain a CodeUri field

        File Handling:
            - All files and directories are copied recursively
            - Uses dirs_exist_ok=True to merge with existing directories
            - Files with the same name are overwritten (function code has precedence)

        Example:
            Given:
                source_dir: /build
                function_id: "MyFunction"
                properties: {"CodeUri": "src/functions/my-func"}

            Will check:
                1. /build/MyFunction/
                2. /build/src/functions/my-func/

            And copy all contents to target_dir
        """
        import shutil

        # Get CodeUri from properties
        code_uri = properties.get("CodeUri", function_id)

        # Source function directory
        func_source = source_dir / function_id
        if not func_source.exists() and code_uri:
            # Try CodeUri
            func_source = source_dir / code_uri

        if func_source.exists() and func_source.is_dir():
            # Check if target_dir already includes the function_id in its path
            # This happens when processing functions with layers
            if target_dir.name == function_id:
                # Target dir is already the function directory, copy directly
                for item in func_source.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, target_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target_dir / item.name)
            else:
                # Target dir is the build dir, need to create function subdirectory
                func_target = target_dir / function_id
                func_target.mkdir(parents=True, exist_ok=True)
                for item in func_source.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, func_target / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, func_target / item.name)


class LocalStackCloudFormationTemplateProcessor(CloudFormationTemplateProcessor):
    # List of AWS resource types that require LocalStack PRO
    # Based on LocalStack documentation
    PRO_RESOURCES = [
        # API Gateway v2 (WebSocket APIs)
        "AWS::ApiGatewayV2::Api",
        "AWS::ApiGatewayV2::ApiMapping",
        "AWS::ApiGatewayV2::Authorizer",
        "AWS::ApiGatewayV2::Deployment",
        "AWS::ApiGatewayV2::DomainName",
        "AWS::ApiGatewayV2::Integration",
        "AWS::ApiGatewayV2::IntegrationResponse",
        "AWS::ApiGatewayV2::Model",
        "AWS::ApiGatewayV2::Route",
        "AWS::ApiGatewayV2::RouteResponse",
        "AWS::ApiGatewayV2::Stage",
        "AWS::ApiGatewayV2::VpcLink",
        # AppSync
        "AWS::AppSync::ApiCache",
        "AWS::AppSync::ApiKey",
        "AWS::AppSync::DataSource",
        "AWS::AppSync::FunctionConfiguration",
        "AWS::AppSync::GraphQLApi",
        "AWS::AppSync::GraphQLSchema",
        "AWS::AppSync::Resolver",
        # Athena
        "AWS::Athena::DataCatalog",
        "AWS::Athena::NamedQuery",
        "AWS::Athena::WorkGroup",
        # Backup
        "AWS::Backup::BackupPlan",
        "AWS::Backup::BackupSelection",
        "AWS::Backup::BackupVault",
        # CloudFront
        "AWS::CloudFront::CachePolicy",
        "AWS::CloudFront::CloudFrontOriginAccessIdentity",
        "AWS::CloudFront::Distribution",
        "AWS::CloudFront::Function",
        "AWS::CloudFront::KeyGroup",
        "AWS::CloudFront::OriginRequestPolicy",
        "AWS::CloudFront::PublicKey",
        "AWS::CloudFront::RealtimeLogConfig",
        "AWS::CloudFront::ResponseHeadersPolicy",
        # Cognito Identity Provider
        "AWS::Cognito::IdentityPool",
        "AWS::Cognito::IdentityPoolRoleAttachment",
        "AWS::Cognito::UserPool",
        "AWS::Cognito::UserPoolClient",
        "AWS::Cognito::UserPoolDomain",
        "AWS::Cognito::UserPoolGroup",
        "AWS::Cognito::UserPoolIdentityProvider",
        "AWS::Cognito::UserPoolResourceServer",
        "AWS::Cognito::UserPoolRiskConfigurationAttachment",
        "AWS::Cognito::UserPoolUICustomizationAttachment",
        "AWS::Cognito::UserPoolUser",
        "AWS::Cognito::UserPoolUserToGroupAttachment",
        # DocumentDB
        "AWS::DocDB::DBCluster",
        "AWS::DocDB::DBClusterParameterGroup",
        "AWS::DocDB::DBInstance",
        "AWS::DocDB::DBSubnetGroup",
        # ECS
        "AWS::ECS::CapacityProvider",
        "AWS::ECS::Cluster",
        "AWS::ECS::ClusterCapacityProviderAssociations",
        "AWS::ECS::PrimaryTaskSet",
        "AWS::ECS::Service",
        "AWS::ECS::TaskDefinition",
        "AWS::ECS::TaskSet",
        # EKS
        "AWS::EKS::Addon",
        "AWS::EKS::Cluster",
        "AWS::EKS::FargateProfile",
        "AWS::EKS::Nodegroup",
        # ElastiCache
        "AWS::ElastiCache::CacheCluster",
        "AWS::ElastiCache::ParameterGroup",
        "AWS::ElastiCache::ReplicationGroup",
        "AWS::ElastiCache::SecurityGroup",
        "AWS::ElastiCache::SecurityGroupIngress",
        "AWS::ElastiCache::SubnetGroup",
        "AWS::ElastiCache::User",
        "AWS::ElastiCache::UserGroup",
        # Elasticsearch/OpenSearch
        "AWS::Elasticsearch::Domain",
        "AWS::OpenSearchService::Domain",
        # EMR
        "AWS::EMR::Cluster",
        "AWS::EMR::InstanceFleetConfig",
        "AWS::EMR::InstanceGroupConfig",
        "AWS::EMR::SecurityConfiguration",
        "AWS::EMR::Step",
        # Glue
        "AWS::Glue::Classifier",
        "AWS::Glue::Connection",
        "AWS::Glue::Crawler",
        "AWS::Glue::Database",
        "AWS::Glue::DataCatalogEncryptionSettings",
        "AWS::Glue::DevEndpoint",
        "AWS::Glue::Job",
        "AWS::Glue::MLTransform",
        "AWS::Glue::Partition",
        "AWS::Glue::Registry",
        "AWS::Glue::Schema",
        "AWS::Glue::SchemaVersion",
        "AWS::Glue::SchemaVersionMetadata",
        "AWS::Glue::SecurityConfiguration",
        "AWS::Glue::Table",
        "AWS::Glue::Trigger",
        "AWS::Glue::Workflow",
        # IoT
        "AWS::IoT::AccountAuditConfiguration",
        "AWS::IoT::Authorizer",
        "AWS::IoT::Certificate",
        "AWS::IoT::CustomMetric",
        "AWS::IoT::Dimension",
        "AWS::IoT::DomainConfiguration",
        "AWS::IoT::FleetMetric",
        "AWS::IoT::JobTemplate",
        "AWS::IoT::MitigationAction",
        "AWS::IoT::Policy",
        "AWS::IoT::PolicyPrincipalAttachment",
        "AWS::IoT::ProvisioningTemplate",
        "AWS::IoT::RoleAlias",
        "AWS::IoT::ScheduledAudit",
        "AWS::IoT::SecurityProfile",
        "AWS::IoT::Thing",
        "AWS::IoT::ThingGroup",
        "AWS::IoT::ThingPrincipalAttachment",
        "AWS::IoT::ThingType",
        "AWS::IoT::TopicRule",
        "AWS::IoT::TopicRuleDestination",
        # Managed Blockchain
        "AWS::ManagedBlockchain::Member",
        "AWS::ManagedBlockchain::Node",
        # MSK
        "AWS::MSK::Cluster",
        # Neptune
        "AWS::Neptune::DBCluster",
        "AWS::Neptune::DBClusterParameterGroup",
        "AWS::Neptune::DBInstance",
        "AWS::Neptune::DBParameterGroup",
        "AWS::Neptune::DBSubnetGroup",
        # QLDB
        "AWS::QLDB::Ledger",
        "AWS::QLDB::Stream",
        # RDS (certain features)
        "AWS::RDS::DBProxy",
        "AWS::RDS::DBProxyEndpoint",
        "AWS::RDS::DBProxyTargetGroup",
        "AWS::RDS::GlobalCluster",
        # Route53
        "AWS::Route53::DNSSEC",
        "AWS::Route53::HealthCheck",
        "AWS::Route53::HostedZone",
        "AWS::Route53::KeySigningKey",
        "AWS::Route53::RecordSet",
        "AWS::Route53::RecordSetGroup",
        # SageMaker
        "AWS::SageMaker::App",
        "AWS::SageMaker::AppImageConfig",
        "AWS::SageMaker::CodeRepository",
        "AWS::SageMaker::DataQualityJobDefinition",
        "AWS::SageMaker::Device",
        "AWS::SageMaker::DeviceFleet",
        "AWS::SageMaker::Domain",
        "AWS::SageMaker::Endpoint",
        "AWS::SageMaker::EndpointConfig",
        "AWS::SageMaker::FeatureGroup",
        "AWS::SageMaker::Image",
        "AWS::SageMaker::ImageVersion",
        "AWS::SageMaker::Model",
        "AWS::SageMaker::ModelBiasJobDefinition",
        "AWS::SageMaker::ModelExplainabilityJobDefinition",
        "AWS::SageMaker::ModelPackage",
        "AWS::SageMaker::ModelPackageGroup",
        "AWS::SageMaker::ModelQualityJobDefinition",
        "AWS::SageMaker::MonitoringSchedule",
        "AWS::SageMaker::NotebookInstance",
        "AWS::SageMaker::NotebookInstanceLifecycleConfig",
        "AWS::SageMaker::Pipeline",
        "AWS::SageMaker::Project",
        "AWS::SageMaker::UserProfile",
        "AWS::SageMaker::Workteam",
        # Transfer
        "AWS::Transfer::Server",
        "AWS::Transfer::User",
        "AWS::Transfer::Workflow",
        # XRay
        "AWS::XRay::Group",
        "AWS::XRay::SamplingRule",
    ]

    def remove_pro_resources(self):
        """
        Remove all resources that require LocalStack PRO from the template.
        This includes removing the resources and all their dependencies.
        """
        resources_to_remove = []

        # Find all PRO resources in the template
        for resource_type in self.PRO_RESOURCES:
            pro_resources = self.find_resources_by_type(resource_type)
            for logical_id, _ in pro_resources:
                resources_to_remove.append(logical_id)

        # Remove each PRO resource (remove_resource will handle dependencies and references)
        for resource_id in resources_to_remove:
            self.remove_resource(resource_id, auto_remove_dependencies=False)

        # Clean up outputs that no longer have values
        self._clean_invalid_outputs()

        return self

    def _clean_invalid_outputs(self):
        """Remove outputs that don't have a Value field."""
        if "Outputs" not in self.processed_template:
            return

        outputs_to_remove = []
        for output_name, output_value in self.processed_template["Outputs"].items():
            if isinstance(output_value, dict) and "Value" not in output_value:
                outputs_to_remove.append(output_name)

        for output_name in outputs_to_remove:
            del self.processed_template["Outputs"][output_name]
