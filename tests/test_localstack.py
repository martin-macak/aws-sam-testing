from aws_sam_testing.localstack import LocalStackCloudFormationTemplateProcessor


class TestLocalStack:
    pass


class TestLocalStackCloudFormationTemplateProcessor:
    def test_remove_non_pro_resources_empty_template(self):
        """Test removing PRO resources from an empty template."""
        template = {}
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_non_pro_resources()

        assert processor.processed_template == {}

    def test_remove_non_pro_resources_no_resources_section(self):
        """Test removing PRO resources when template has no Resources section."""
        template = {"AWSTemplateFormatVersion": "2010-09-09", "Description": "Test template"}
        processor = LocalStackCloudFormationTemplateProcessor(template)
        processor.remove_non_pro_resources()

        assert processor.processed_template == template

    def test_remove_non_pro_resources_no_pro_resources(self):
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
        processor.remove_non_pro_resources()

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
        processor.remove_non_pro_resources()

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
        processor.remove_non_pro_resources()

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
        processor.remove_non_pro_resources()

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
        processor.remove_non_pro_resources()

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
        processor.remove_non_pro_resources()

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
        processor.remove_non_pro_resources()

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
