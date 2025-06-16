"""Tests for the AWSSAMToolkit class."""

from pathlib import Path

import pytest

from aws_sam_testing.aws_sam import AWSSAMToolkit


class TestAWSSAMToolkit:
    """Test cases for AWSSAMToolkit class."""

    @staticmethod
    def print_directory_tree(path: Path, prefix: str = "", is_last: bool = True) -> None:
        """Print directory structure in ASCII tree format.

        Args:
            path: The directory path to print
            prefix: Prefix for the current line (used for recursion)
            is_last: Whether this is the last item in the current directory
        """
        if not path.exists():
            print(f"{prefix}[Directory does not exist: {path}]")
            return

        # Print the current item
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{path.name}")

        # If it's a directory, print its contents
        if path.is_dir():
            # Get sorted list of items
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))

            # Calculate the new prefix for children
            extension = "    " if is_last else "│   "

            # Print each child
            for i, item in enumerate(items):
                TestAWSSAMToolkit.print_directory_tree(item, prefix + extension, i == len(items) - 1)

    class TestBuild:
        """Test cases for sam_build method."""

        def test_sam_build_success(self, tmp_path: Path):
            """Test successful SAM build with a valid template."""
            # Create a simple valid SAM template
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: app.lambda_handler
      Runtime: python3.13
      MemorySize: 128
      Timeout: 3
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Create source directory and handler file
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            handler_file = src_dir / "app.py"
            handler_file.write_text("""
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello World!'
    }
""")

            # Initialize toolkit and build
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))
            build_dir = toolkit.sam_build()

            # Print build directory structure
            print("\nBuild directory structure:")
            TestAWSSAMToolkit.print_directory_tree(build_dir)

            # Print the built template
            built_template_path = build_dir / "template.yaml"
            if built_template_path.exists():
                print("\nBuilt template.yaml:")
                print(built_template_path.read_text())

            # Verify build output
            assert build_dir.exists()
            assert build_dir.is_dir()
            assert (build_dir / "template.yaml").exists()
            assert (build_dir / "HelloWorldFunction").exists()

        def test_sam_build_custom_build_dir(self, tmp_path: Path):
            """Test SAM build with custom build directory."""
            # Create a simple valid SAM template
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  TestFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: index.handler
      Runtime: python3.13
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Create source directory and handler file
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            handler_file = src_dir / "index.py"
            handler_file.write_text("""
def handler(event, context):
    return {'statusCode': 200}
""")

            # Custom build directory
            custom_build_dir = tmp_path / "my-custom-build"

            # Initialize toolkit and build
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))
            build_dir = toolkit.sam_build(build_dir=custom_build_dir)

            # Print build directory structure
            print("\nBuild directory structure:")
            TestAWSSAMToolkit.print_directory_tree(build_dir)

            # Print the built template
            built_template_path = build_dir / "template.yaml"
            if built_template_path.exists():
                print("\nBuilt template.yaml:")
                print(built_template_path.read_text())

            # Verify build output
            assert build_dir == custom_build_dir
            assert build_dir.exists()
            assert (build_dir / "template.yaml").exists()

        def test_sam_build_invalid_template(self, tmp_path: Path):
            """Test SAM build with an invalid template."""
            # Create an invalid SAM template (missing required properties)
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  InvalidFunction:
    Type: AWS::Serverless::Function
    Properties:
      # Missing required properties like CodeUri, Handler, Runtime
      MemorySize: 128
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Build should raise an exception due to invalid template
            with pytest.raises(Exception):
                toolkit.sam_build()

        def test_sam_build_missing_source_code(self, tmp_path: Path):
            """Test SAM build when source code directory is missing."""
            # Create a SAM template pointing to non-existent source
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  MissingCodeFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: missing-src/
      Handler: app.handler
      Runtime: python3.13
"""

            # Create template file but don't create the source directory
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Build should succeed but with warnings (SAM doesn't fail on missing source)
            build_dir = toolkit.sam_build()

            # Print build directory structure
            print("\nBuild directory structure:")
            TestAWSSAMToolkit.print_directory_tree(build_dir)

            # Print the built template
            built_template_path = build_dir / "template.yaml"
            if built_template_path.exists():
                print("\nBuilt template.yaml:")
                print(built_template_path.read_text())

            # Verify build output exists even though source was missing
            assert build_dir.exists()
            assert (build_dir / "template.yaml").exists()
            # The function directory might not exist or be empty due to missing source
            # This is expected behavior from SAM CLI

    class TestRunLocalApi:
        """Test cases for run_local_api method."""

        @pytest.fixture(autouse=True)
        def setup(self, monkeypatch):
            monkeypatch.setattr("aws_sam_testing.aws_sam.LocalApi._start_local_api", lambda self: None)
            monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.start", lambda *args, **kwargs: None)
            monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.stop", lambda *args, **kwargs: None)
            yield

        @pytest.mark.slow
        def test_run_local_api_no_api(self, tmp_path: Path, request):
            """Test run_local_api when template has no API resources."""
            # Create a template without any API resources
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: app.handler
      Runtime: python3.13
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Create source directory and handler file
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            handler_file = src_dir / "app.py"
            handler_file.write_text("""
def handler(event, context):
    return {'statusCode': 200, 'body': 'Hello World'}
""")

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Should raise ValueError when no API resources found
            with pytest.raises(ValueError, match="No API resources found in template"):
                with toolkit.run_local_api(pytest_request_context=request):
                    pass

        @pytest.mark.slow
        def test_run_local_api_single_api(self, tmp_path: Path, request):
            """Test run_local_api with a single API resource."""
            # Create a template with one API resource
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  MyApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: dev
      Cors:
        AllowMethods: "'*'"
        AllowHeaders: "'*'"
        AllowOrigin: "'*'"
  
  HelloFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: app.handler
      Runtime: python3.13
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref MyApi
            Path: /hello
            Method: get
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Create source directory and handler file
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            handler_file = src_dir / "app.py"
            handler_file.write_text("""
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello from single API!'
    }
""")

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Build the stack first
            build_dir = toolkit.sam_build()

            # Print build directory structure
            print("\nBuild directory structure for single API test:")
            TestAWSSAMToolkit.print_directory_tree(build_dir)

            # Print the built template
            built_template_path = build_dir / "template.yaml"
            if built_template_path.exists():
                print("\nBuilt template.yaml:")
                print(built_template_path.read_text())

            # Run local API
            with toolkit.run_local_api(pytest_request_context=request) as apis:
                # Should have exactly one API
                assert len(apis) == 1
                api = apis[0]

                # Check API properties
                assert api.api_logical_id == "MyApi"
                assert api.port is not None
                assert api.host is not None

        @pytest.mark.slow
        def test_run_local_api_multiple_apis(self, tmp_path: Path, request):
            """Test run_local_api with multiple API resources."""
            # Create a template with multiple API resources
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  PublicApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      Cors:
        AllowMethods: "'*'"
        AllowHeaders: "'*'"
        AllowOrigin: "'*'"
  
  InternalApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: internal
      EndpointConfiguration:
        Type: PRIVATE
  
  AdminApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: admin
      Auth:
        ApiKeyRequired: true
  
  PublicFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: public.handler
      Runtime: python3.13
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref PublicApi
            Path: /public
            Method: get
  
  InternalFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: internal.handler
      Runtime: python3.13
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref InternalApi
            Path: /internal
            Method: get
  
  AdminFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: admin.handler
      Runtime: python3.13
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref AdminApi
            Path: /admin
            Method: get
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Create source directory and handler files
            src_dir = tmp_path / "src"
            src_dir.mkdir()

            # Public handler
            public_handler = src_dir / "public.py"
            public_handler.write_text("""
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Public API response'
    }
""")

            # Internal handler
            internal_handler = src_dir / "internal.py"
            internal_handler.write_text("""
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Internal API response'
    }
""")

            # Admin handler
            admin_handler = src_dir / "admin.py"
            admin_handler.write_text("""
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Admin API response'
    }
""")

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Build the stack first
            build_dir = toolkit.sam_build()

            # Print build directory structure
            print("\nBuild directory structure for multiple APIs test:")
            TestAWSSAMToolkit.print_directory_tree(build_dir)

            # Print the built template
            built_template_path = build_dir / "template.yaml"
            if built_template_path.exists():
                print("\nBuilt template.yaml:")
                print(built_template_path.read_text())

            # Run local APIs
            with toolkit.run_local_api(pytest_request_context=request) as apis:
                # Should have exactly three APIs
                assert len(apis) == 3

                # Check that we have all expected APIs
                api_ids = {api.api_logical_id for api in apis}
                assert api_ids == {"PublicApi", "InternalApi", "AdminApi"}

                # Check that each API has unique port
                ports = [api.port for api in apis]
                assert len(ports) == len(set(ports)), "Each API should have a unique port"

                # Verify each API is properly configured
                for api in apis:
                    assert api.port is not None
                    assert api.host is not None

                    # Print intermediate build directories for each API
                    api_build_dir = Path(tmp_path) / ".aws-sam" / "aws-sam-testing-build" / f"api-stack-{api.api_logical_id}"
                    if api_build_dir.exists():
                        print(f"\nBuild directory for {api.api_logical_id}:")
                        TestAWSSAMToolkit.print_directory_tree(api_build_dir)

                        # Print the API-specific template
                        api_template_path = api_build_dir / "template.yaml"
                        if api_template_path.exists():
                            print(f"\nTemplate for {api.api_logical_id}:")
                            print(api_template_path.read_text())

        @pytest.mark.slow
        def test_run_local_api_with_parameters(self, tmp_path: Path, request):
            """Test run_local_api with CloudFormation parameters."""
            # Create a template with parameters
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Parameters:
  StageName:
    Type: String
    Default: dev
  
  ApiName:
    Type: String
    Default: MyAPI

Resources:
  ParameterizedApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: !Ref StageName
      Name: !Ref ApiName
  
  TestFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: app.handler
      Runtime: python3.13
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref ParameterizedApi
            Path: /test
            Method: get
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Create source directory and handler file
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            handler_file = src_dir / "app.py"
            handler_file.write_text("""
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Parameterized API response'
    }
""")

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Build the stack first
            build_dir = toolkit.sam_build()

            # Print build directory structure
            print("\nBuild directory structure for parameterized API test:")
            TestAWSSAMToolkit.print_directory_tree(build_dir)

            # Print the built template
            built_template_path = build_dir / "template.yaml"
            if built_template_path.exists():
                print("\nBuilt template.yaml:")
                print(built_template_path.read_text())

            # Run local API with parameters
            parameters = {"StageName": "production", "ApiName": "ProductionAPI"}

            with toolkit.run_local_api(parameters=parameters, pytest_request_context=request) as apis:
                # Should have exactly one API
                assert len(apis) == 1
                api = apis[0]

                # Check API properties
                assert api.api_logical_id == "ParameterizedApi"
                assert api.parameters == parameters

        @pytest.mark.slow
        def test_run_local_api_custom_port_host(self, tmp_path: Path, request):
            """Test run_local_api with custom port and host."""
            # Create a simple template with one API
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  CustomApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: test
  
  TestFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: app.handler
      Runtime: python3.13
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref CustomApi
            Path: /test
            Method: get
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Create source directory and handler file
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            handler_file = src_dir / "app.py"
            handler_file.write_text("""
def handler(event, context):
    return {'statusCode': 200, 'body': 'Custom port/host API'}
""")

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Build the stack first
            toolkit.sam_build()

            # Test with custom port and host
            custom_port = 8080
            custom_host = "127.0.0.1"

            with toolkit.run_local_api(port=custom_port, host=custom_host, pytest_request_context=request) as apis:
                # Should have exactly one API
                assert len(apis) == 1
                api = apis[0]

                # Check that custom port and host are used
                assert api.port == custom_port
                assert api.host == custom_host

        @pytest.mark.slow
        def test_run_local_api_invalid_port(self, tmp_path: Path, request):
            """Test run_local_api with invalid port values."""
            # Create a minimal template
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  TestApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: test
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Test with port < 1
            with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
                with toolkit.run_local_api(port=0, pytest_request_context=request):
                    pass

            # Test with port > 65535
            with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
                with toolkit.run_local_api(port=70000, pytest_request_context=request):
                    pass

        @pytest.mark.slow
        def test_run_local_api_empty_host(self, tmp_path: Path, request):
            """Test run_local_api with empty host string."""
            # Create a minimal template
            template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  TestApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: test
"""

            # Create template file
            template_path = tmp_path / "template.yaml"
            template_path.write_text(template_content)

            # Initialize toolkit
            toolkit = AWSSAMToolkit(working_dir=str(tmp_path), template_path=str(template_path))

            # Test with empty host
            with pytest.raises(ValueError, match="Host cannot be empty"):
                with toolkit.run_local_api(host="", pytest_request_context=request):
                    pass

            # Test with whitespace-only host
            with pytest.raises(ValueError, match="Host cannot be empty"):
                with toolkit.run_local_api(host="   ", pytest_request_context=request):
                    pass
