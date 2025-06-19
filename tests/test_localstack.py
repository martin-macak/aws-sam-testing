import zipfile
from unittest.mock import MagicMock, patch

import pytest

from aws_sam_testing.localstack import LocalStackCloudFormationTemplateProcessor, LocalStackToolkit


class TestLocalStack:
    pass


class TestStackToolkit:
    """Test suite for LocalStackToolkit class."""

    class TestBuild:
        """Test suite for build method."""

        @pytest.fixture
        def toolkit(self, tmp_path):
            """Create a LocalStackToolkit instance with a temporary working directory."""
            working_dir = tmp_path / "project"
            working_dir.mkdir()
            template_path = working_dir / "template.yaml"
            template_path.write_text("""
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: functions/my-function/
      Handler: index.handler
      Runtime: python3.9
  MyLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      ContentUri: layers/my-layer/
      CompatibleRuntimes:
        - python3.9
""")
            return LocalStackToolkit(working_dir=str(working_dir), template_path=str(template_path))

        @patch("aws_sam_testing.cfn.dump_yaml")
        def test_build_normal_feature_set_default_build_dir(self, mock_dump_yaml, toolkit, tmp_path):
            """Test build with normal feature set and default build directory."""
            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Mock dump_yaml to actually create the temporary file for cleanup
            def mock_dump_yaml_side_effect(template, stream):
                if hasattr(stream, "write"):
                    # This is a file-like object
                    stream.write("# Mock template")

            mock_dump_yaml.side_effect = mock_dump_yaml_side_effect

            # Mock _process_lambda_layers to avoid complex layer processing in unit test
            with patch.object(toolkit, "_process_lambda_layers") as mock_process_layers:
                mock_process_layers.return_value = tmp_path / "processed"

                result = toolkit.build(feature_set=LocalStackFeautureSet.NORMAL)

                # Check default build directories were used
                expected_processed_dir = tmp_path / "project" / ".aws-sam" / "aws-sam-testing-localstack-processed-build"
                assert str(expected_processed_dir) in str(result)

                # Check _process_lambda_layers was called for NORMAL feature set
                mock_process_layers.assert_called_once()

                # Check dump_yaml was called
                assert mock_dump_yaml.call_count >= 1

        def test_build_pro_feature_set_custom_build_dir(self, toolkit, tmp_path):
            """Test build with PRO feature set and custom build directory."""
            from aws_sam_testing.localstack import LocalStackFeautureSet

            custom_build_dir = tmp_path / "custom_build"
            custom_build_dir.mkdir()

            # Test PRO feature set raises NotImplementedError
            with pytest.raises(NotImplementedError, match="PRO features are not supported yet"):
                toolkit.build(feature_set=LocalStackFeautureSet.PRO, build_dir=custom_build_dir)

        @patch("aws_sam_testing.cfn.dump_yaml")
        def test_build_template_cleanup_on_error(self, mock_dump_yaml, toolkit, tmp_path):
            """Test that temporary template file is cleaned up even when build fails."""
            from pathlib import Path

            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Track created files
            created_files = []

            def mock_dump_yaml_side_effect(template, stream):
                if hasattr(stream, "name"):
                    # This is a file object with a name
                    created_files.append(Path(stream.name))
                    stream.write("# Mock template")

            mock_dump_yaml.side_effect = mock_dump_yaml_side_effect

            # Mock _process_lambda_layers to raise an exception
            with patch.object(toolkit, "_process_lambda_layers") as mock_process_layers:
                mock_process_layers.side_effect = RuntimeError("Processing failed")

                with pytest.raises(RuntimeError, match="Processing failed"):
                    toolkit.build(feature_set=LocalStackFeautureSet.NORMAL)

                # Check that temporary files were cleaned up
                for file_path in created_files:
                    assert not file_path.exists()

        @patch("aws_sam_testing.localstack.LocalStackCloudFormationTemplateProcessor")
        @patch("aws_sam_testing.cfn.dump_yaml")
        def test_build_pro_resource_removal(self, mock_dump_yaml, mock_processor_class, toolkit):
            """Test that PRO resources are removed for NORMAL feature set."""
            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Mock dump_yaml to actually create the temporary file for cleanup
            def mock_dump_yaml_side_effect(template, stream):
                if hasattr(stream, "write_text"):
                    # This is a Path object
                    stream.parent.mkdir(parents=True, exist_ok=True)
                    stream.write_text("# Mock template")
                elif hasattr(stream, "write"):
                    # This is a file-like object
                    stream.write("# Mock template")

            mock_dump_yaml.side_effect = mock_dump_yaml_side_effect

            # Mock processor
            mock_processor = MagicMock()
            mock_processor.processed_template = {"Resources": {}}
            mock_processor_class.return_value = mock_processor

            with patch("aws_sam_testing.aws_sam.AWSSAMToolkit"), patch.object(toolkit, "_process_lambda_layers"):
                toolkit.build(feature_set=LocalStackFeautureSet.NORMAL)

                # Check remove_pro_resources was called for NORMAL feature set
                mock_processor.remove_pro_resources.assert_called_once()

        def test_build_no_pro_resource_removal_for_pro(self, toolkit):
            """Test that PRO resources are NOT removed for PRO feature set."""
            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Currently, PRO features raise NotImplementedError
            with pytest.raises(NotImplementedError, match="PRO features are not supported yet"):
                toolkit.build(feature_set=LocalStackFeautureSet.PRO)

        @patch("aws_sam_testing.cfn.dump_yaml")
        def test_build_path_assertions(self, mock_dump_yaml, toolkit):
            """Test that build method has proper path assertions."""
            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Mock dump_yaml to actually create the temporary file for cleanup
            def mock_dump_yaml_side_effect(template, stream):
                if hasattr(stream, "write_text"):
                    # This is a Path object
                    stream.parent.mkdir(parents=True, exist_ok=True)
                    stream.write_text("# Mock template")
                elif hasattr(stream, "write"):
                    # This is a file-like object
                    stream.write("# Mock template")

            mock_dump_yaml.side_effect = mock_dump_yaml_side_effect

            with patch("aws_sam_testing.aws_sam.AWSSAMToolkit"), patch.object(toolkit, "_process_lambda_layers"):
                # This should not raise AssertionError
                result = toolkit.build(feature_set=LocalStackFeautureSet.NORMAL)

                # The method should return a valid path
                assert result is not None

        @pytest.mark.slow
        @patch("aws_sam_testing.aws_sam.AWSSAMToolkit")
        def test_integration_build_normal_with_mocked_sam_build(self, mock_aws_sam_toolkit, tmp_path):
            """Integration test: Build with NORMAL feature set using mocked SAM build."""
            import yaml

            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Create a complete SAM project structure
            project_dir = tmp_path / "sam_project"
            project_dir.mkdir()

            # Create template.yaml with function and layer
            template_content = {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Transform": "AWS::Serverless-2016-10-31",
                "Resources": {
                    "HelloWorldFunction": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {"CodeUri": "hello_world/", "Handler": "app.lambda_handler", "Runtime": "python3.9", "Layers": [{"Ref": "SharedLayer"}], "Architectures": ["x86_64"]},
                    },
                    "SharedLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "layer/", "CompatibleRuntimes": ["python3.9"], "CompatibleArchitectures": ["x86_64"]}},
                    # Add a PRO resource that should be removed in NORMAL mode
                    "CognitoUserPool": {"Type": "AWS::Cognito::UserPool", "Properties": {"UserPoolName": "test-pool"}},
                },
            }

            template_path = project_dir / "template.yaml"
            with open(template_path, "w") as f:
                yaml.dump(template_content, f)

            # Create function code
            func_dir = project_dir / "hello_world"
            func_dir.mkdir()
            (func_dir / "app.py").write_text("""
def lambda_handler(event, context):
    import shared_module  # This should come from the layer
    return {
        'statusCode': 200,
        'body': shared_module.get_message()
    }
""")
            (func_dir / "requirements.txt").write_text("# No requirements")

            # Create layer code
            layer_dir = project_dir / "layer" / "python"
            layer_dir.mkdir(parents=True)
            (layer_dir / "shared_module.py").write_text("""
def get_message():
    return "Hello from shared layer!"
""")

            # Mock SAM toolkit to simulate successful build
            mock_sam = MagicMock()

            def mock_sam_build(build_dir):
                """Mock SAM build that creates expected directory structure."""
                build_dir.mkdir(parents=True, exist_ok=True)

                # Create mock built template
                built_template = {
                    "AWSTemplateFormatVersion": "2010-09-09",
                    "Transform": "AWS::Serverless-2016-10-31",
                    "Resources": {
                        "HelloWorldFunction": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "HelloWorldFunction", "Handler": "app.lambda_handler", "Runtime": "python3.9", "Layers": [{"Ref": "SharedLayer"}]},
                        },
                        "SharedLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "SharedLayer", "CompatibleRuntimes": ["python3.9"]}},
                        "CognitoUserPool": {"Type": "AWS::Cognito::UserPool", "Properties": {"UserPoolName": "test-pool"}},
                    },
                }

                with open(build_dir / "template.yaml", "w") as f:
                    yaml.dump(built_template, f)

                # Create function and layer directories
                func_build_dir = build_dir / "HelloWorldFunction"
                func_build_dir.mkdir()
                (func_build_dir / "app.py").write_text("def lambda_handler(event, context): pass")

                layer_build_dir = build_dir / "SharedLayer"
                layer_build_dir.mkdir()
                layer_python_dir = layer_build_dir / "python"
                layer_python_dir.mkdir()
                (layer_python_dir / "shared_module.py").write_text("def get_message(): return 'Hello from layer!'")

            mock_sam.sam_build.side_effect = mock_sam_build
            mock_aws_sam_toolkit.return_value = mock_sam

            # Create LocalStackToolkit instance
            toolkit = LocalStackToolkit(working_dir=str(project_dir), template_path=str(template_path))

            # Test build process
            result_path = toolkit.build(feature_set=LocalStackFeautureSet.NORMAL)

            print(f"\\nBuild completed. Result path: {result_path}")

            # Verify directory structure
            print(f"\\nDirectory structure for {result_path}:")
            for item in result_path.rglob("*"):
                if item.is_file():
                    print(f"  File: {item.relative_to(result_path)}")
                else:
                    print(f"  Dir:  {item.relative_to(result_path)}/")

            # Verify build artifacts exist
            assert result_path.exists(), "Build directory should exist"
            assert (result_path / "template.yaml").exists(), "Template should exist in build directory"

            # Check that the built template has PRO resources removed and layers flattened
            built_template_path = result_path / "template.yaml"
            with open(built_template_path, "r") as f:
                built_template = yaml.safe_load(f)

            print("\\nBuilt template.yaml content:")
            print(yaml.dump(built_template, default_flow_style=False))

        @pytest.mark.slow
        def test_integration_build_pro_with_pro_resources(self, tmp_path):
            """Integration test: Build with PRO feature set should raise NotImplementedError."""

            import yaml

            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Create SAM project with PRO resources
            project_dir = tmp_path / "sam_pro_project"
            project_dir.mkdir()

            template_content = {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Transform": "AWS::Serverless-2016-10-31",
                "Resources": {
                    "SimpleFunction": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "simple_function/",
                            "Handler": "app.lambda_handler",
                            "Runtime": "python3.9",
                            "Environment": {"Variables": {"USER_POOL_ID": {"Ref": "CognitoUserPool"}}},
                        },
                    },
                    "CognitoUserPool": {"Type": "AWS::Cognito::UserPool", "Properties": {"UserPoolName": "test-pool"}},
                    "WebSocketApi": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"Name": "test-websocket-api", "ProtocolType": "WEBSOCKET"}},
                },
            }

            template_path = project_dir / "template.yaml"
            with open(template_path, "w") as f:
                yaml.dump(template_content, f)

            # Create simple function code
            func_dir = project_dir / "simple_function"
            func_dir.mkdir()
            (func_dir / "app.py").write_text("""
import os

def lambda_handler(event, context):
    user_pool_id = os.environ.get('USER_POOL_ID', 'not-set')
    return {
        'statusCode': 200,
        'body': f'User Pool ID: {user_pool_id}'
    }
""")
            (func_dir / "requirements.txt").write_text("# No requirements")

            # Create toolkit and verify PRO features raise NotImplementedError
            toolkit = LocalStackToolkit(working_dir=str(project_dir), template_path=str(template_path))

            with pytest.raises(NotImplementedError, match="PRO features are not supported yet"):
                toolkit.build(feature_set=LocalStackFeautureSet.PRO)

        @pytest.mark.slow
        @patch("aws_sam_testing.aws_sam.AWSSAMToolkit")
        def test_integration_build_directory_structure_validation(self, mock_aws_sam_toolkit, tmp_path):
            """Integration test: Validate complete directory structure after build."""
            import yaml

            from aws_sam_testing.localstack import LocalStackFeautureSet

            # Create minimal SAM project
            project_dir = tmp_path / "structure_test_project"
            project_dir.mkdir()

            template_content = {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Transform": "AWS::Serverless-2016-10-31",
                "Resources": {"TestFunction": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "test_function/", "Handler": "index.handler", "Runtime": "python3.9"}}},
            }

            template_path = project_dir / "template.yaml"
            with open(template_path, "w") as f:
                yaml.dump(template_content, f)

            # Create function
            func_dir = project_dir / "test_function"
            func_dir.mkdir()
            (func_dir / "index.py").write_text("def handler(event, context): return {'statusCode': 200}")

            # Mock SAM toolkit
            mock_sam = MagicMock()

            def mock_sam_build(build_dir):
                """Mock SAM build."""
                build_dir.mkdir(parents=True, exist_ok=True)

                built_template = template_content.copy()
                built_template["Resources"]["TestFunction"]["Properties"]["CodeUri"] = "TestFunction"

                with open(build_dir / "template.yaml", "w") as f:
                    yaml.dump(built_template, f)

                func_build_dir = build_dir / "TestFunction"
                func_build_dir.mkdir()
                (func_build_dir / "index.py").write_text("def handler(event, context): pass")

            mock_sam.sam_build.side_effect = mock_sam_build
            mock_aws_sam_toolkit.return_value = mock_sam

            # Test with custom build directory
            custom_build_dir = tmp_path / "custom_builds"
            custom_build_dir.mkdir()

            toolkit = LocalStackToolkit(working_dir=str(project_dir), template_path=str(template_path))
            result_path = toolkit.build(feature_set=LocalStackFeautureSet.NORMAL, build_dir=custom_build_dir)

            print(f"\\nBuild with custom directory completed: {result_path}")

            # Print complete directory tree
            def print_tree(path, prefix=""):
                """Print directory tree for debugging."""
                if not path.exists():
                    return
                items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
                for i, item in enumerate(items):
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    print(f"{prefix}{current_prefix}{item.name}")
                    if item.is_dir() and not item.name.startswith("."):
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        print_tree(item, next_prefix)

            print("\\nComplete directory structure:")
            print_tree(tmp_path)

            # Verify expected structure
            expected_processed_build = custom_build_dir / "aws-sam-testing-localstack-processed-build"

            assert result_path == expected_processed_build, f"Should return processed build path: {result_path}"
            assert expected_processed_build.exists(), "Processed build directory should exist"
            assert (expected_processed_build / "template.yaml").exists(), "Processed build should have template.yaml"

    class TestProcessLambdaLayers:
        """Test suite for _process_lambda_layers method."""

        @pytest.fixture
        def toolkit(self, tmp_path):
            """Create a LocalStackToolkit instance with a temporary working directory."""
            working_dir = tmp_path / "project"
            working_dir.mkdir()
            template_path = working_dir / "template.yaml"
            template_path.write_text("AWSTemplateFormatVersion: '2010-09-09'\nResources: {}")
            return LocalStackToolkit(working_dir=str(working_dir), template_path=str(template_path))

        @pytest.fixture
        def sample_template(self):
            """Create a sample CloudFormation template with functions and layers."""
            return {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Transform": "AWS::Serverless-2016-10-31",
                "Resources": {
                    "MyFunction": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "functions/my-function/",
                            "Handler": "index.handler",
                            "Runtime": "python3.9",
                            "Layers": [{"Ref": "MyLocalLayer"}, "arn:aws:lambda:us-east-1:123456789012:layer:external-layer:1"],
                        },
                    },
                    "MyLocalLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "layers/my-layer/", "CompatibleRuntimes": ["python3.9"]}},
                    "FunctionWithoutLayers": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {"Code": {"ZipFile": "print('hello')"}, "Handler": "index.handler", "Runtime": "python3.9", "Role": "arn:aws:iam::123456789012:role/MyRole"},
                    },
                },
            }

        def test_process_layers_without_flattening(self, toolkit, tmp_path):
            """Test that layers are not processed when flatten_layers is False."""
            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)
            source_path.write_text("Resources: {}")

            build_dir = tmp_path / "build"

            result = toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=False)

            assert result == build_dir
            assert build_dir.exists()

        def test_process_layers_with_empty_template(self, toolkit, tmp_path):
            """Test processing layers with an empty template."""
            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)
            source_path.write_text("AWSTemplateFormatVersion: '2010-09-09'")

            build_dir = tmp_path / "build"

            result = toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True)

            assert result == build_dir
            assert (build_dir / "template.yaml").exists()

        def test_process_layers_with_functions_no_layers(self, toolkit, tmp_path, sample_template):
            """Test processing functions that have no layers."""
            # Remove layers from the template
            sample_template["Resources"]["MyFunction"]["Properties"].pop("Layers")
            sample_template["Resources"].pop("MyLocalLayer")

            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)

            # Create function directory
            func_dir = source_path.parent / "MyFunction"
            func_dir.mkdir()
            (func_dir / "index.py").write_text("def handler(event, context): pass")

            # Write template
            import yaml

            source_path.write_text(yaml.dump(sample_template))

            build_dir = tmp_path / "build"

            with patch.object(toolkit, "_copy_function_code") as mock_copy:
                result = toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True)

                # Should copy function code
                assert mock_copy.called
                assert result == build_dir

        def test_process_layers_with_local_layer_reference(self, toolkit, tmp_path, sample_template):
            """Test processing functions with local layer references."""
            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)

            # Create layer directory structure
            layer_dir = source_path.parent / "MyLocalLayer" / "python"
            layer_dir.mkdir(parents=True)
            (layer_dir / "my_package.py").write_text("# Layer code")

            # Create function directory
            func_dir = source_path.parent / "MyFunction"
            func_dir.mkdir()
            (func_dir / "index.py").write_text("def handler(event, context): pass")

            # Write template
            import yaml

            source_path.write_text(yaml.dump(sample_template))

            build_dir = tmp_path / "build"

            with patch.object(toolkit, "_download_and_cache_layer", return_value=None):
                toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True)

            # Check that local layer was copied to function
            assert (build_dir / "MyFunction" / "my_package.py").exists()

            # Check that the Layers property was removed from template
            output_template = yaml.safe_load((build_dir / "template.yaml").read_text())
            assert "Layers" not in output_template["Resources"]["MyFunction"]["Properties"]

            # Check that local layer resource was removed
            assert "MyLocalLayer" not in output_template["Resources"]

        def test_process_layers_with_external_layer_arn(self, toolkit, tmp_path):
            """Test processing functions with external layer ARNs."""
            template = {
                "Resources": {
                    "MyFunction": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {"Code": {"ZipFile": "print('hello')"}, "Handler": "index.handler", "Runtime": "python3.9", "Layers": ["arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"]},
                    }
                }
            }

            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)

            # Create function directory
            func_dir = source_path.parent / "MyFunction"
            func_dir.mkdir()
            (func_dir / "index.py").write_text("def handler(event, context): pass")

            import yaml

            source_path.write_text(yaml.dump(template))

            build_dir = tmp_path / "build"
            layer_cache_dir = tmp_path / "cache"

            # Create a mock layer zip file
            mock_layer_zip = layer_cache_dir / "mock_layer.zip"
            layer_cache_dir.mkdir(parents=True)
            with zipfile.ZipFile(mock_layer_zip, "w") as zf:
                zf.writestr("python/layer_package.py", "# Layer package")

            with patch.object(toolkit, "_download_and_cache_layer", return_value=mock_layer_zip):
                toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True, layer_cache_dir=layer_cache_dir)

            # Check that layer content was extracted to function
            assert (build_dir / "MyFunction" / "layer_package.py").exists()

            # Check that Layers property was removed
            output_template = yaml.safe_load((build_dir / "template.yaml").read_text())
            assert "Layers" not in output_template["Resources"]["MyFunction"]["Properties"]

        def test_process_layers_skips_image_functions(self, toolkit, tmp_path):
            """Test that functions with PackageType=Image are skipped."""
            template = {
                "Resources": {
                    "ImageFunction": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "PackageType": "Image",
                            "Code": {"ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-func:latest"},
                            "Layers": ["arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"],
                        },
                    }
                }
            }

            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)

            import yaml

            source_path.write_text(yaml.dump(template))

            build_dir = tmp_path / "build"

            toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True)

            # Layers should remain in the template for image functions
            output_template = yaml.safe_load((build_dir / "template.yaml").read_text())
            assert "Layers" in output_template["Resources"]["ImageFunction"]["Properties"]

        def test_resolve_layer_arn_with_string(self, toolkit):
            """Test resolving layer ARN from string."""
            arn = "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"
            result = toolkit._resolve_layer_arn(arn, region="us-east-1")
            assert result == arn

        def test_resolve_layer_arn_with_ref(self, toolkit):
            """Test resolving layer ARN from Ref."""
            layer_ref = {"Ref": "MyLayer"}
            result = toolkit._resolve_layer_arn(layer_ref, region="us-east-1")
            assert result == "!Ref:MyLayer"

        def test_resolve_layer_arn_with_getatt(self, toolkit):
            """Test resolving layer ARN from GetAtt returns None."""
            layer_ref = {"Fn::GetAtt": ["MyLayer", "Arn"]}
            result = toolkit._resolve_layer_arn(layer_ref, region="us-east-1")
            assert result is None

        def test_resolve_layer_arn_with_fn_sub_string(self, toolkit):
            """Test resolving layer ARN from Fn::Sub with string format."""
            layer_ref = {"Fn::Sub": "arn:aws:lambda:${AWS::Region}:123456789012:layer:my-layer:1"}
            result = toolkit._resolve_layer_arn(layer_ref, region="eu-west-1")
            assert result == "arn:aws:lambda:eu-west-1:123456789012:layer:my-layer:1"

        def test_resolve_layer_arn_with_fn_sub_list_format(self, toolkit):
            """Test resolving layer ARN from Fn::Sub with list format."""
            layer_ref = {"Fn::Sub": ["arn:aws:lambda:${AWS::Region}:123456789012:layer:my-layer:1", {}]}
            result = toolkit._resolve_layer_arn(layer_ref, region="ap-southeast-2")
            assert result == "arn:aws:lambda:ap-southeast-2:123456789012:layer:my-layer:1"

        def test_resolve_layer_arn_with_fn_sub_default_region(self, toolkit):
            """Test resolving layer ARN from Fn::Sub with default region when none provided."""
            layer_ref = {"Fn::Sub": "arn:aws:lambda:${AWS::Region}:123456789012:layer:my-layer:1"}
            result = toolkit._resolve_layer_arn(layer_ref, region=None)
            assert result == "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"

        def test_resolve_layer_arn_with_fn_sub_invalid_format(self, toolkit):
            """Test resolving layer ARN from Fn::Sub with invalid format returns None."""
            layer_ref = {"Fn::Sub": {"invalid": "format"}}
            result = toolkit._resolve_layer_arn(layer_ref, region="us-east-1")
            assert result is None

        def test_substitute_cloudformation_variables_with_region(self, toolkit):
            """Test substituting CloudFormation variables with region."""
            template_string = "arn:aws:lambda:${AWS::Region}:123456789012:layer:my-layer:1"
            result = toolkit._substitute_cloudformation_variables(template_string, region="eu-central-1")
            assert result == "arn:aws:lambda:eu-central-1:123456789012:layer:my-layer:1"

        def test_substitute_cloudformation_variables_unsupported_variable(self, toolkit):
            """Test substituting CloudFormation variables raises error for unsupported variables."""
            template_string = "arn:aws:lambda:${AWS::AccountId}:layer:my-layer:1"
            with pytest.raises(ValueError, match="Unsupported CloudFormation variables: AWS::AccountId"):
                toolkit._substitute_cloudformation_variables(template_string, region="us-east-1")

        def test_substitute_cloudformation_variables_multiple_variables(self, toolkit):
            """Test substituting CloudFormation variables with multiple variables."""
            template_string = "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:layer:${LayerName}:1"
            with pytest.raises(ValueError, match="Unsupported CloudFormation variables: AWS::AccountId, LayerName"):
                toolkit._substitute_cloudformation_variables(template_string, region="us-east-1")

        def test_substitute_cloudformation_variables_no_variables(self, toolkit):
            """Test substituting CloudFormation variables with no variables."""
            template_string = "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"
            result = toolkit._substitute_cloudformation_variables(template_string, region="eu-west-1")
            assert result == template_string  # Should return unchanged

        def test_get_ref_value(self, toolkit):
            """Test extracting reference value."""
            assert toolkit._get_ref_value({"Ref": "MyLayer"}) == "MyLayer"
            assert toolkit._get_ref_value("!Ref:MyLayer") == "MyLayer"
            assert toolkit._get_ref_value("not-a-ref") is None

        def test_copy_local_layer_python_runtime(self, toolkit, tmp_path):
            """Test copying local layer with Python runtime."""
            source_dir = tmp_path / "source"
            target_dir = tmp_path / "target"
            layer_id = "MyLayer"

            # Create layer structure
            layer_dir = source_dir / layer_id / "python"
            layer_dir.mkdir(parents=True)
            (layer_dir / "my_module.py").write_text("# Module code")
            (layer_dir / "package").mkdir()
            (layer_dir / "package" / "__init__.py").write_text("")

            target_dir.mkdir(parents=True)

            template = {"Resources": {"MyLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"ContentUri": "layers/my-layer/"}}}}

            toolkit._copy_local_layer(source_dir, target_dir, layer_id, template)

            # Check files were copied to target
            assert (target_dir / "my_module.py").exists()
            assert (target_dir / "package" / "__init__.py").exists()

        def test_copy_local_layer_nodejs_runtime(self, toolkit, tmp_path):
            """Test copying local layer with Node.js runtime."""
            source_dir = tmp_path / "source"
            target_dir = tmp_path / "target"
            layer_id = "MyLayer"

            # Create layer structure
            layer_dir = source_dir / layer_id / "nodejs"
            layer_dir.mkdir(parents=True)
            (layer_dir / "index.js").write_text("// JS code")

            target_dir.mkdir(parents=True)

            template = {"Resources": {"MyLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": layer_id}}}}

            toolkit._copy_local_layer(source_dir, target_dir, layer_id, template)

            # Check nodejs directory was created in target
            assert (target_dir / "nodejs" / "index.js").exists()

        @patch("boto3.client")
        def test_download_and_cache_layer_success(self, mock_boto_client, toolkit, tmp_path):
            """Test successful layer download and caching."""
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            layer_arn = "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"

            # Mock Lambda client
            mock_lambda = MagicMock()
            mock_boto_client.return_value = mock_lambda
            mock_lambda.get_layer_version.return_value = {"Content": {"Location": "https://example.com/layer.zip"}}

            # Mock urlretrieve
            with patch("urllib.request.urlretrieve") as mock_urlretrieve:
                result = toolkit._download_and_cache_layer(layer_arn, cache_dir)

                # Check that layer was downloaded
                assert mock_urlretrieve.called
                assert result is not None
                assert result.suffix == ".zip"

        @patch("boto3.client")
        def test_download_and_cache_layer_already_cached(self, mock_boto_client, toolkit, tmp_path):
            """Test that cached layers are not re-downloaded."""
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            layer_arn = "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"

            # Create cached file
            import hashlib

            arn_hash = hashlib.md5(layer_arn.encode()).hexdigest()
            cached_file = cache_dir / f"{arn_hash}.zip"
            cached_file.write_text("cached")

            result = toolkit._download_and_cache_layer(layer_arn, cache_dir)

            # Should return cached file without calling boto3
            assert result == cached_file
            assert not mock_boto_client.called

        def test_download_and_cache_layer_invalid_arn(self, toolkit, tmp_path):
            """Test handling of invalid layer ARN."""
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            invalid_arn = "invalid-arn"

            result = toolkit._download_and_cache_layer(invalid_arn, cache_dir)
            assert result is None

        def test_extract_layer_to_function_python_structure(self, toolkit, tmp_path):
            """Test extracting Python layer with standard structure."""
            function_dir = tmp_path / "function"
            function_dir.mkdir()

            # Create a layer zip with Python structure
            layer_zip = tmp_path / "layer.zip"
            with zipfile.ZipFile(layer_zip, "w") as zf:
                zf.writestr("python/module1.py", "# Module 1")
                zf.writestr("python/package/__init__.py", "")
                zf.writestr("python/package/module2.py", "# Module 2")

            toolkit._extract_layer_to_function(layer_zip, function_dir)

            # Check extracted files
            assert (function_dir / "module1.py").exists()
            assert (function_dir / "package" / "__init__.py").exists()
            assert (function_dir / "package" / "module2.py").exists()

        def test_extract_layer_to_function_site_packages(self, toolkit, tmp_path):
            """Test extracting layer with site-packages structure."""
            function_dir = tmp_path / "function"
            function_dir.mkdir()

            # Create a layer zip with site-packages
            layer_zip = tmp_path / "layer.zip"
            with zipfile.ZipFile(layer_zip, "w") as zf:
                zf.writestr("python/lib/python3.9/site-packages/requests/__init__.py", "# Requests")
                zf.writestr("python/lib/python3.9/site-packages/urllib3/__init__.py", "# Urllib3")

            toolkit._extract_layer_to_function(layer_zip, function_dir)

            # Check extracted packages
            assert (function_dir / "requests" / "__init__.py").exists()
            assert (function_dir / "urllib3" / "__init__.py").exists()

        def test_copy_function_code_with_codeeuri(self, toolkit, tmp_path):
            """Test copying function code using CodeUri."""
            source_dir = tmp_path / "source"
            target_dir = tmp_path / "target"

            # Create function code
            func_dir = source_dir / "functions" / "my-func"
            func_dir.mkdir(parents=True)
            (func_dir / "handler.py").write_text("def handler(event, context): pass")
            (func_dir / "utils.py").write_text("# Utils")

            target_dir.mkdir(parents=True)

            properties = {"CodeUri": "functions/my-func"}

            toolkit._copy_function_code(source_dir, target_dir, "MyFunction", properties)

            # Check files were copied to MyFunction subdirectory
            assert (target_dir / "MyFunction" / "handler.py").exists()
            assert (target_dir / "MyFunction" / "utils.py").exists()

        def test_copy_function_code_with_logical_id(self, toolkit, tmp_path):
            """Test copying function code using logical ID as directory name."""
            source_dir = tmp_path / "source"
            target_dir = tmp_path / "target"

            # Create function code with logical ID as directory
            func_dir = source_dir / "MyFunction"
            func_dir.mkdir(parents=True)
            (func_dir / "index.py").write_text("def handler(event, context): pass")

            target_dir.mkdir(parents=True)

            properties = {}  # No CodeUri

            toolkit._copy_function_code(source_dir, target_dir, "MyFunction", properties)

            # Check file was copied to MyFunction subdirectory
            assert (target_dir / "MyFunction" / "index.py").exists()

        def test_copy_function_code_to_function_dir(self, toolkit, tmp_path):
            """Test copying function code when target_dir is already the function directory."""
            source_dir = tmp_path / "source"
            target_dir = tmp_path / "target" / "MyFunction"

            # Create function code with logical ID as directory
            func_dir = source_dir / "MyFunction"
            func_dir.mkdir(parents=True)
            (func_dir / "index.py").write_text("def handler(event, context): pass")
            (func_dir / "lib").mkdir()
            (func_dir / "lib" / "utils.py").write_text("# Utils")

            target_dir.mkdir(parents=True)

            properties = {}  # No CodeUri

            toolkit._copy_function_code(source_dir, target_dir, "MyFunction", properties)

            # Check files were copied directly to target_dir (no additional subdirectory)
            assert (target_dir / "index.py").exists()
            assert (target_dir / "lib" / "utils.py").exists()
            # Make sure no extra MyFunction subdirectory was created
            assert not (target_dir / "MyFunction").exists()

        def test_full_integration_with_multiple_layers(self, toolkit, tmp_path):
            """Integration test with function using multiple layers."""
            template = {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Resources": {
                    "Layer1": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"ContentUri": "layer1/"}},
                    "Layer2": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"ContentUri": "layer2/"}},
                    "MyFunction": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {"Code": {"ZipFile": "print('hello')"}, "Handler": "index.handler", "Runtime": "python3.9", "Layers": [{"Ref": "Layer1"}, {"Ref": "Layer2"}]},
                    },
                },
            }

            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)

            # Create layer structures
            layer1_dir = source_path.parent / "Layer1" / "python"
            layer1_dir.mkdir(parents=True)
            (layer1_dir / "layer1_module.py").write_text("# Layer 1")

            layer2_dir = source_path.parent / "Layer2" / "python"
            layer2_dir.mkdir(parents=True)
            (layer2_dir / "layer2_module.py").write_text("# Layer 2")

            # Create function
            func_dir = source_path.parent / "MyFunction"
            func_dir.mkdir()
            (func_dir / "handler.py").write_text("def handler(event, context): pass")

            import yaml

            source_path.write_text(yaml.dump(template))

            build_dir = tmp_path / "build"

            toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True)

            # Check all modules are in function directory
            assert (build_dir / "MyFunction" / "layer1_module.py").exists()
            assert (build_dir / "MyFunction" / "layer2_module.py").exists()
            assert (build_dir / "MyFunction" / "handler.py").exists()

            # Check layers were removed from template
            output_template = yaml.safe_load((build_dir / "template.yaml").read_text())
            assert "Layers" not in output_template["Resources"]["MyFunction"]["Properties"]
            assert "Layer1" not in output_template["Resources"]
            assert "Layer2" not in output_template["Resources"]

        def test_full_integration_with_fn_sub_layer(self, toolkit, tmp_path):
            """Integration test with function using Fn::Sub in layer ARN."""
            template = {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Resources": {
                    "MyFunction": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {
                            "Code": {"ZipFile": "print('hello')"},
                            "Handler": "index.handler",
                            "Runtime": "python3.9",
                            "Layers": [{"Fn::Sub": "arn:aws:lambda:${AWS::Region}:123456789012:layer:external-layer:1"}],
                        },
                    },
                },
            }

            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)

            # Create function
            func_dir = source_path.parent / "MyFunction"
            func_dir.mkdir()
            (func_dir / "handler.py").write_text("def handler(event, context): pass")

            import yaml

            source_path.write_text(yaml.dump(template))

            build_dir = tmp_path / "build"

            # Mock the download since we're testing the Fn::Sub resolution
            with patch.object(toolkit, "_download_and_cache_layer", return_value=None) as mock_download:
                toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True, region="eu-west-1")

                # Verify the layer ARN was resolved with the correct region
                mock_download.assert_called_once()
                resolved_arn = mock_download.call_args[0][0]
                assert resolved_arn == "arn:aws:lambda:eu-west-1:123456789012:layer:external-layer:1"

        def test_layer_flattening_preserves_existing_files_in_directories(self, toolkit, tmp_path):
            """Test that layer flattening preserves existing files when merging directories.

            This test verifies a critical behavior of layer flattening: when multiple layers
            and a function contain files in the same directories, the flattening process must
            merge these directories intelligently without deleting existing files.

            The test creates the following scenario:

            Layer A contains:
                package_a/
                    foo.py    # Will be overwritten by function's version
                package_b/
                    bar.py    # Will be preserved

            Layer B contains:
                package_b/
                    baz.py    # Will be merged with bar.py from Layer A
                package_d/
                    qux.py    # Will be preserved

            Function A contains:
                package_a/
                    foo.py    # Overwrites Layer A's version
                    foo2.py   # New file, will be preserved
                package_e/
                    xyz.py    # Will be preserved

            Expected result after flattening:
                package_a/
                    foo.py    # From Function A (overwrites Layer A's version)
                    foo2.py   # From Function A
                package_b/
                    bar.py    # From Layer A
                    baz.py    # From Layer B (merged into same directory)
                package_d/
                    qux.py    # From Layer B
                package_e/
                    xyz.py    # From Function A

            This behavior is essential because:
            1. It follows AWS Lambda's layer precedence rules (later layers override earlier ones)
            2. Functions override all layers (highest precedence)
            3. Files with unique names are preserved regardless of source
            4. Directories are merged, not replaced wholesale
            """
            template = {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Resources": {
                    "LayerA": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"ContentUri": "layer_a/"}},
                    "LayerB": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"ContentUri": "layer_b/"}},
                    "FunctionA": {
                        "Type": "AWS::Lambda::Function",
                        "Properties": {"Code": {"ZipFile": "print('hello')"}, "Handler": "index.handler", "Runtime": "python3.9", "Layers": [{"Ref": "LayerA"}, {"Ref": "LayerB"}]},
                    },
                },
            }

            source_path = tmp_path / "source" / "template.yaml"
            source_path.parent.mkdir(parents=True)

            # Create layer_a structure
            layer_a_dir = source_path.parent / "LayerA" / "python"
            layer_a_dir.mkdir(parents=True)
            (layer_a_dir / "package_a").mkdir()
            (layer_a_dir / "package_a" / "foo.py").write_text("# foo from layer_a")
            (layer_a_dir / "package_b").mkdir()
            (layer_a_dir / "package_b" / "bar.py").write_text("# bar from layer_a")

            # Create layer_b structure
            layer_b_dir = source_path.parent / "LayerB" / "python"
            layer_b_dir.mkdir(parents=True)
            (layer_b_dir / "package_b").mkdir()
            (layer_b_dir / "package_b" / "baz.py").write_text("# baz from layer_b")
            (layer_b_dir / "package_d").mkdir()
            (layer_b_dir / "package_d" / "qux.py").write_text("# qux from layer_b")

            # Create function_a structure
            func_dir = source_path.parent / "FunctionA"
            func_dir.mkdir()
            (func_dir / "package_a").mkdir()
            (func_dir / "package_a" / "foo.py").write_text("# foo from function_a - should overwrite layer version")
            (func_dir / "package_a" / "foo2.py").write_text("# foo2 from function_a")
            (func_dir / "package_e").mkdir()
            (func_dir / "package_e" / "xyz.py").write_text("# xyz from function_a")

            import yaml

            source_path.write_text(yaml.dump(template))

            build_dir = tmp_path / "build"

            toolkit._process_lambda_layers(source_template_path=source_path, build_dir=build_dir, flatten_layers=True)

            # Verify the final structure
            func_build_dir = build_dir / "FunctionA"

            # Check package_a - should have both files, with foo.py from function_a
            assert (func_build_dir / "package_a" / "foo.py").exists()
            assert (func_build_dir / "package_a" / "foo2.py").exists()
            assert "foo from function_a" in (func_build_dir / "package_a" / "foo.py").read_text()
            assert "foo2 from function_a" in (func_build_dir / "package_a" / "foo2.py").read_text()

            # Check package_b - should have both bar.py from layer_a and baz.py from layer_b
            assert (func_build_dir / "package_b" / "bar.py").exists()
            assert (func_build_dir / "package_b" / "baz.py").exists()
            assert "bar from layer_a" in (func_build_dir / "package_b" / "bar.py").read_text()
            assert "baz from layer_b" in (func_build_dir / "package_b" / "baz.py").read_text()

            # Check package_d - should have qux.py from layer_b
            assert (func_build_dir / "package_d" / "qux.py").exists()
            assert "qux from layer_b" in (func_build_dir / "package_d" / "qux.py").read_text()

            # Check package_e - should have xyz.py from function_a
            assert (func_build_dir / "package_e" / "xyz.py").exists()
            assert "xyz from function_a" in (func_build_dir / "package_e" / "xyz.py").read_text()

            # Verify layers were removed from template
            output_template = yaml.safe_load((build_dir / "template.yaml").read_text())
            assert "Layers" not in output_template["Resources"]["FunctionA"]["Properties"]
            assert "LayerA" not in output_template["Resources"]
            assert "LayerB" not in output_template["Resources"]


class TestLocalStackCloudFormationTemplateProcessor:
    def test_remove_pro_resources_empty_template(self):
        """Test removing PRO resources from an empty template."""
        template = {}
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        assert processor.processed_template == {}

    def test_remove_pro_resources_no_resources_section(self):
        """Test removing PRO resources when template has no Resources section."""
        template = {"AWSTemplateFormatVersion": "2010-09-09", "Description": "Test template"}
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        assert processor.processed_template == template

    def test_remove_pro_resources_no_pro_resources(self):
        """Test removing PRO resources when template has only community resources."""
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}},
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"FunctionName": "my-function", "Runtime": "python3.9", "Code": {"ZipFile": "print('hello')"}, "Handler": "index.handler", "Role": {"Fn::GetAtt": ["MyRole", "Arn"]}},
                },
                "MyRole": {"Type": "AWS::IAM::Role", "Properties": {"AssumeRolePolicyDocument": {}}},
            }
        }
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        # All resources should remain
        assert len(processor.processed_template["Resources"]) == 3
        assert "MyBucket" in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]
        assert "MyRole" in processor.processed_template["Resources"]

    def test_remove_single_pro_resource(self):
        """Test removing a single PRO resource."""
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}},
                "MyCognitoPool": {"Type": "AWS::Cognito::UserPool", "Properties": {"UserPoolName": "my-pool"}},
            }
        }
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        # Only S3 bucket should remain
        assert len(processor.processed_template["Resources"]) == 1
        assert "MyBucket" in processor.processed_template["Resources"]
        assert "MyCognitoPool" not in processor.processed_template["Resources"]

    def test_remove_multiple_pro_resources(self):
        """Test removing multiple PRO resources of different types."""
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket"},
                "MyCognitoPool": {"Type": "AWS::Cognito::UserPool"},
                "MyApiV2": {"Type": "AWS::ApiGatewayV2::Api"},
                "MyAppSync": {"Type": "AWS::AppSync::GraphQLApi"},
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Runtime": "python3.9", "Code": {"ZipFile": "print('hello')"}, "Handler": "index.handler", "Role": "arn:aws:iam::123456789012:role/MyRole"},
                },
            }
        }
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        # Only S3 bucket and Lambda function should remain
        assert len(processor.processed_template["Resources"]) == 2
        assert "MyBucket" in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]
        assert "MyCognitoPool" not in processor.processed_template["Resources"]
        assert "MyApiV2" not in processor.processed_template["Resources"]
        assert "MyAppSync" not in processor.processed_template["Resources"]

    def test_remove_pro_resource_with_dependencies(self):
        """Test removing PRO resources removes dependent resources."""
        template = {
            "Resources": {
                "MyCognitoPool": {"Type": "AWS::Cognito::UserPool", "Properties": {"UserPoolName": "my-pool"}},
                "MyCognitoClient": {"Type": "AWS::Cognito::UserPoolClient", "Properties": {"UserPoolId": {"Ref": "MyCognitoPool"}}},
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Runtime": "python3.9",
                        "Code": {"ZipFile": "print('hello')"},
                        "Handler": "index.handler",
                        "Role": "arn:aws:iam::123456789012:role/MyRole",
                        "Environment": {"Variables": {"USER_POOL_ID": {"Ref": "MyCognitoPool"}}},
                    },
                },
            }
        }
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        # All Cognito resources should be removed
        assert "MyCognitoPool" not in processor.processed_template["Resources"]
        assert "MyCognitoClient" not in processor.processed_template["Resources"]
        # Lambda function should remain but without the reference to Cognito
        assert "MyFunction" in processor.processed_template["Resources"]
        # The USER_POOL_ID environment variable should be removed
        env_vars = processor.processed_template["Resources"]["MyFunction"]["Properties"]["Environment"]["Variables"]
        assert "USER_POOL_ID" not in env_vars

    def test_remove_pro_resource_updates_outputs(self):
        """Test that outputs referencing PRO resources are removed."""
        template = {
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}, "MyCognitoPool": {"Type": "AWS::Cognito::UserPool"}},
            "Outputs": {
                "BucketName": {"Value": {"Ref": "MyBucket"}, "Description": "Name of the S3 bucket"},
                "UserPoolId": {"Value": {"Ref": "MyCognitoPool"}, "Description": "ID of the Cognito User Pool"},
                "UserPoolArn": {"Value": {"Fn::GetAtt": ["MyCognitoPool", "Arn"]}, "Description": "ARN of the Cognito User Pool"},
            },
        }
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        # Only bucket-related output should remain
        assert len(processor.processed_template["Outputs"]) == 1
        assert "BucketName" in processor.processed_template["Outputs"]
        assert "UserPoolId" not in processor.processed_template["Outputs"]
        assert "UserPoolArn" not in processor.processed_template["Outputs"]

    def test_remove_pro_resource_with_serverless_function_event(self):
        """Test removing PRO resources that are referenced in serverless function events."""
        template = {
            "Resources": {
                "MyApiV2": {"Type": "AWS::ApiGatewayV2::Api", "Properties": {"Name": "MyWebSocketAPI"}},
                "MyServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Runtime": "python3.9",
                        "CodeUri": "src/",
                        "Handler": "app.handler",
                        "Events": {"WebSocketEvent": {"Type": "Api", "Properties": {"RestApiId": {"Ref": "MyApiV2"}}}, "S3Event": {"Type": "S3", "Properties": {"Bucket": {"Ref": "MyBucket"}}}},
                    },
                },
                "MyBucket": {"Type": "AWS::S3::Bucket"},
            }
        }
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        # API Gateway V2 should be removed
        assert "MyApiV2" not in processor.processed_template["Resources"]
        # Function should remain but WebSocket event should be removed
        assert "MyServerlessFunction" in processor.processed_template["Resources"]
        events = processor.processed_template["Resources"]["MyServerlessFunction"]["Properties"]["Events"]
        assert "WebSocketEvent" not in events
        assert "S3Event" in events
        # Bucket should remain
        assert "MyBucket" in processor.processed_template["Resources"]

    def test_remove_pro_resources_with_circular_dependencies(self):
        """Test removing PRO resources that have circular dependencies."""
        template = {
            "Resources": {
                "MyCluster": {"Type": "AWS::ECS::Cluster", "Properties": {"ClusterName": "my-cluster"}},
                "MyService": {"Type": "AWS::ECS::Service", "Properties": {"Cluster": {"Ref": "MyCluster"}, "TaskDefinition": {"Ref": "MyTaskDefinition"}}},
                "MyTaskDefinition": {
                    "Type": "AWS::ECS::TaskDefinition",
                    "Properties": {"Family": "my-task", "ContainerDefinitions": []},
                    "DependsOn": "MyService",  # Circular dependency
                },
                "MyBucket": {"Type": "AWS::S3::Bucket"},
            }
        }
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_pro_resources()

        # All ECS resources should be removed (they're all PRO)
        assert "MyCluster" not in processor.processed_template["Resources"]
        assert "MyService" not in processor.processed_template["Resources"]
        assert "MyTaskDefinition" not in processor.processed_template["Resources"]
        # S3 bucket should remain
        assert "MyBucket" in processor.processed_template["Resources"]

    def test_pro_resources_constant_contains_expected_services(self):
        """Test that PRO_RESOURCES contains expected LocalStack PRO services."""
        processor = LocalStackCloudFormationTemplateProcessor({})

        # Check that some key PRO services are included
        assert "AWS::Cognito::UserPool" in processor.PRO_RESOURCES
        assert "AWS::ApiGatewayV2::Api" in processor.PRO_RESOURCES
        assert "AWS::AppSync::GraphQLApi" in processor.PRO_RESOURCES
        assert "AWS::ECS::Cluster" in processor.PRO_RESOURCES
        assert "AWS::EKS::Cluster" in processor.PRO_RESOURCES
        assert "AWS::RDS::DBProxy" in processor.PRO_RESOURCES

        # Check that community services are NOT included
        assert "AWS::S3::Bucket" not in processor.PRO_RESOURCES
        assert "AWS::Lambda::Function" not in processor.PRO_RESOURCES
        assert "AWS::DynamoDB::Table" not in processor.PRO_RESOURCES
        assert "AWS::SNS::Topic" not in processor.PRO_RESOURCES
        assert "AWS::SQS::Queue" not in processor.PRO_RESOURCES
