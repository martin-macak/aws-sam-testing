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

            # Verify build output exists even though source was missing
            assert build_dir.exists()
            assert (build_dir / "template.yaml").exists()
            # The function directory might not exist or be empty due to missing source
            # This is expected behavior from SAM CLI
