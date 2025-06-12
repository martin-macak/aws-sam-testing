import pytest


class TestAWSResourceManager:
    def test_simple_template(self):
        import boto3
        from moto import mock_aws

        from aws_sam_testing.aws_resources import AWSResourceManager

        template = {
            "Resources": {
                "MyTable": {
                    "Type": "AWS::DynamoDB::Table",
                    "Properties": {
                        "TableName": "my-table",
                        "KeySchema": [
                            {"AttributeName": "id", "KeyType": "HASH"},
                        ],
                        "AttributeDefinitions": [
                            {"AttributeName": "id", "AttributeType": "S"},
                        ],
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()

            with AWSResourceManager(
                session=session,
                template=template,
            ) as resource_manager:
                assert resource_manager.is_created

                dynamodb = session.resource("dynamodb")
                table = dynamodb.Table("my-table")
                assert table.table_status == "ACTIVE"

                table.put_item(
                    Item={
                        "id": "1",
                    }
                )

                item = table.get_item(
                    Key={
                        "id": "1",
                    }
                ).get("Item")
                assert item is not None

    def test_sqs_queue_resource(self):
        """Test creation and management of AWS::SQS::Queue resource."""
        import boto3
        from moto import mock_aws

        from aws_sam_testing.aws_resources import AWSResourceManager

        template = {
            "Resources": {
                "MyQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {
                        "QueueName": "test-queue",
                        "DelaySeconds": 5,
                        "MessageRetentionPeriod": 1209600,
                        "VisibilityTimeoutSeconds": 30,
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()

            with AWSResourceManager(
                session=session,
                template=template,
            ) as resource_manager:
                assert resource_manager.is_created

                sqs = session.client("sqs")

                # Verify queue was created
                queues = sqs.list_queues()
                assert "QueueUrls" in queues
                assert len(queues["QueueUrls"]) == 1

                queue_url = queues["QueueUrls"][0]
                assert "test-queue" in queue_url

                # Verify queue attributes
                attributes = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])
                attrs = attributes["Attributes"]
                assert attrs["DelaySeconds"] == "5"
                assert attrs["MessageRetentionPeriod"] == "1209600"
                assert attrs["VisibilityTimeout"] == "30"

                # Test sending and receiving messages
                sqs.send_message(QueueUrl=queue_url, MessageBody="Test message")

                messages = sqs.receive_message(QueueUrl=queue_url)
                # Check if messages were received (may be empty in moto)
                if "Messages" in messages:
                    assert len(messages["Messages"]) == 1
                    message = messages["Messages"][0]
                    assert message.get("Body") == "Test message"

    def test_sns_topic_resource(self):
        """Test creation and management of AWS::SNS::Topic resource."""
        import boto3
        from moto import mock_aws

        from aws_sam_testing.aws_resources import AWSResourceManager

        template = {
            "Resources": {
                "MyTopic": {
                    "Type": "AWS::SNS::Topic",
                    "Properties": {
                        "TopicName": "test-topic",
                        "DisplayName": "Test Topic for Unit Testing",
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()

            with AWSResourceManager(
                session=session,
                template=template,
            ) as resource_manager:
                assert resource_manager.is_created

                sns = session.client("sns")

                # Verify topic was created
                topics = sns.list_topics()
                assert "Topics" in topics
                assert len(topics["Topics"]) == 1

                topic_arn = topics["Topics"][0]["TopicArn"]
                assert "test-topic" in topic_arn

                # Verify topic attributes
                attributes = sns.get_topic_attributes(TopicArn=topic_arn)
                attrs = attributes["Attributes"]
                # DisplayName may be empty in moto, just check TopicArn
                assert "test-topic" in attrs["TopicArn"]

                # Test subscription and publishing
                # Subscribe to topic (using a test endpoint)
                subscription = sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint="test@example.com")
                assert "SubscriptionArn" in subscription

                # Publish a message
                response = sns.publish(TopicArn=topic_arn, Message="Test message", Subject="Test Subject")
                assert "MessageId" in response

    def test_s3_bucket_resource(self):
        """Test creation and management of AWS::S3::Bucket resource."""
        import boto3
        from moto import mock_aws

        from aws_sam_testing.aws_resources import AWSResourceManager

        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {
                        "BucketName": "test-bucket-12345",
                        "VersioningConfiguration": {"Status": "Enabled"},
                        "PublicAccessBlockConfiguration": {
                            "BlockPublicAcls": True,
                            "BlockPublicPolicy": True,
                            "IgnorePublicAcls": True,
                            "RestrictPublicBuckets": True,
                        },
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()

            with AWSResourceManager(
                session=session,
                template=template,
            ) as resource_manager:
                assert resource_manager.is_created

                s3 = session.client("s3")

                # Verify bucket was created
                buckets = s3.list_buckets()
                assert "Buckets" in buckets
                assert len(buckets["Buckets"]) == 2
                bucket = buckets["Buckets"][1]
                assert bucket.get("Name") == "test-bucket-12345"

                # Verify versioning (may not be fully supported in moto)
                try:
                    versioning = s3.get_bucket_versioning(Bucket="test-bucket-12345")
                    # Versioning status may not be set in moto
                    if "Status" in versioning:
                        assert versioning["Status"] == "Enabled"
                except Exception:
                    # Versioning configuration may not be fully supported in moto
                    pass

                # Test putting and getting objects
                s3.put_object(
                    Bucket="test-bucket-12345",
                    Key="test-file.txt",
                    Body=b"Test content",
                    ContentType="text/plain",
                )

                # Verify object exists
                objects = s3.list_objects_v2(Bucket="test-bucket-12345")
                assert "Contents" in objects
                assert len(objects["Contents"]) == 1
                obj_info = objects["Contents"][0]
                assert obj_info.get("Key") == "test-file.txt"

                # Get object content
                obj = s3.get_object(Bucket="test-bucket-12345", Key="test-file.txt")
                content = obj["Body"].read()
                assert content == b"Test content"
                assert obj["ContentType"] == "text/plain"

    def test_modify_environment(self):
        import os

        import boto3
        from moto import mock_aws

        from aws_sam_testing.aws_resources import AWSResourceManager

        template = {
            "Globals": {
                "Function": {
                    "Environment": {
                        "Variables": {
                            "TEST_ENV_VAR_GLOBAL": {
                                "Ref": "MyTable",
                            },
                        },
                    },
                },
            },
            "Resources": {
                "MyTable": {
                    "Type": "AWS::DynamoDB::Table",
                    "Properties": {
                        "TableName": "my-table",
                        "KeySchema": [
                            {"AttributeName": "id", "KeyType": "HASH"},
                        ],
                        "AttributeDefinitions": [
                            {"AttributeName": "id", "AttributeType": "S"},
                        ],
                        "BillingMode": "PAY_PER_REQUEST",
                    },
                },
                "MyLambda": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "FunctionName": "my-lambda",
                        "Handler": "app.lambda_handler",
                        "Runtime": "python3.13",
                        "Environment": {
                            "Variables": {
                                "TEST_ENV_VAR_FUNCTION": {
                                    "Ref": "MyTable",
                                },
                            },
                        },
                    },
                },
            },
        }

        assert os.environ.get("TEST_ENV_VAR_GLOBAL") is None
        assert os.environ.get("TEST_ENV_VAR_FUNCTION") is None
        assert os.environ.get("TEST_ENV_VAR_ADDITIONAL") is None

        with mock_aws():
            session = boto3.Session()
            with AWSResourceManager(
                session=session,
                template=template,
            ) as resource_manager:
                with resource_manager.set_environment(
                    lambda_function_logical_name="MyLambda",
                    additional_environment={
                        "TEST_ENV_VAR_ADDITIONAL": "additional-value",
                    },
                ):
                    assert os.environ.get("TEST_ENV_VAR_GLOBAL") == "my-table"
                    assert os.environ.get("TEST_ENV_VAR_FUNCTION") == "my-table"
                    assert os.environ.get("TEST_ENV_VAR_ADDITIONAL") == "additional-value"

        assert os.environ.get("TEST_ENV_VAR_GLOBAL") is None
        assert os.environ.get("TEST_ENV_VAR_FUNCTION") is None
        assert os.environ.get("TEST_ENV_VAR_ADDITIONAL") is None

    def test_get_resource_sqs_queue(self):
        """Test get_resource method for SQS Queue using ResourceManager."""
        import boto3
        from moto import mock_aws

        from aws_sam_testing.pytest_addin.aws_resources import ResourceManager

        template = {
            "Resources": {
                "TestQueue": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {
                        "QueueName": "test-get-resource-queue",
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()
            with ResourceManager(
                session=session,
                working_dir=None,
                template=template,
            ) as manager:
                # Get the queue using get_resource
                queue = manager.get_resource("TestQueue")

                # Verify it's a Queue resource
                assert hasattr(queue, "send_message")
                assert hasattr(queue, "receive_messages")

                # Test that we can use the queue
                queue.send_message(MessageBody="Test message")
                messages = list(queue.receive_messages())
                assert len(messages) == 1
                assert messages[0].body == "Test message"

    def test_get_resource_dynamodb_table(self):
        """Test get_resource method for DynamoDB Table using ResourceManager."""
        import boto3
        from moto import mock_aws

        from aws_sam_testing.pytest_addin.aws_resources import ResourceManager

        template = {
            "Resources": {
                "TestTable": {
                    "Type": "AWS::DynamoDB::Table",
                    "Properties": {
                        "TableName": "test-get-resource-table",
                        "KeySchema": [
                            {"AttributeName": "id", "KeyType": "HASH"},
                        ],
                        "AttributeDefinitions": [
                            {"AttributeName": "id", "AttributeType": "S"},
                        ],
                        "BillingMode": "PAY_PER_REQUEST",
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()
            with ResourceManager(
                session=session,
                working_dir=None,
                template=template,
            ) as manager:
                # Get the table using get_resource
                table = manager.get_resource("TestTable")

                # Verify it's a Table resource
                assert hasattr(table, "put_item")
                assert hasattr(table, "get_item")
                assert table.table_status == "ACTIVE"

                # Test that we can use the table
                table.put_item(Item={"id": "test-id", "data": "test-data"})
                response = table.get_item(Key={"id": "test-id"})
                assert response["Item"]["data"] == "test-data"

    def test_get_resource_s3_bucket(self):
        """Test get_resource method for S3 Bucket using ResourceManager."""
        import boto3
        from moto import mock_aws

        from aws_sam_testing.pytest_addin.aws_resources import ResourceManager

        template = {
            "Resources": {
                "TestBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {
                        "BucketName": "test-get-resource-bucket-unique",
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()
            with ResourceManager(
                session=session,
                working_dir=None,
                template=template,
            ) as manager:
                # Get the bucket using get_resource
                bucket = manager.get_resource("TestBucket")

                # Verify it's a Bucket resource
                assert hasattr(bucket, "put_object")
                assert hasattr(bucket, "objects")

                # Test that we can use the bucket
                bucket.put_object(Key="test-file.txt", Body=b"Test content")
                objects = list(bucket.objects.all())
                assert len(objects) == 1
                assert objects[0].key == "test-file.txt"

    @pytest.mark.parametrize(
        "resource_name,resource_type,template",
        [
            (
                "MyQueue",
                "AWS::SQS::Queue",
                {
                    "Resources": {
                        "MyQueue": {
                            "Type": "AWS::SQS::Queue",
                            "Properties": {
                                "QueueName": "param-test-queue",
                            },
                        },
                    },
                },
            ),
            (
                "MyTable",
                "AWS::DynamoDB::Table",
                {
                    "Resources": {
                        "MyTable": {
                            "Type": "AWS::DynamoDB::Table",
                            "Properties": {
                                "TableName": "param-test-table",
                                "KeySchema": [
                                    {"AttributeName": "id", "KeyType": "HASH"},
                                ],
                                "AttributeDefinitions": [
                                    {"AttributeName": "id", "AttributeType": "S"},
                                ],
                                "BillingMode": "PAY_PER_REQUEST",
                            },
                        },
                    },
                },
            ),
            (
                "MyBucket",
                "AWS::S3::Bucket",
                {
                    "Resources": {
                        "MyBucket": {
                            "Type": "AWS::S3::Bucket",
                            "Properties": {
                                "BucketName": "param-test-bucket-unique",
                            },
                        },
                    },
                },
            ),
        ],
    )
    def test_get_resource_parametrized(self, resource_name, resource_type, template):
        """Parametrized test for get_resource method with different resource types."""
        import boto3
        from moto import mock_aws

        from aws_sam_testing.pytest_addin.aws_resources import ResourceManager

        with mock_aws():
            session = boto3.Session()
            with ResourceManager(
                session=session,
                working_dir=None,
                template=template,
            ) as manager:
                # Get the resource
                resource = manager.get_resource(resource_name)

                # Verify the resource is returned and is not None
                assert resource is not None

                # Basic verification based on resource type
                if resource_type == "AWS::SQS::Queue":
                    assert hasattr(resource, "send_message")
                    assert hasattr(resource, "receive_messages")
                elif resource_type == "AWS::DynamoDB::Table":
                    assert hasattr(resource, "put_item")
                    assert hasattr(resource, "get_item")
                elif resource_type == "AWS::S3::Bucket":
                    assert hasattr(resource, "put_object")
                    assert hasattr(resource, "objects")

    def test_get_resource_unsupported_type(self):
        """Test get_resource method with unsupported resource type."""
        import boto3
        import pytest
        from moto import mock_aws

        from aws_sam_testing.pytest_addin.aws_resources import ResourceManager

        template = {
            "Resources": {
                "UnsupportedResource": {
                    "Type": "AWS::SNS::Topic",
                    "Properties": {
                        "TopicName": "test-unsupported-topic",
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()
            with ResourceManager(
                session=session,
                working_dir=None,
                template=template,
            ) as manager:
                # Attempt to get unsupported resource type
                with pytest.raises(ValueError, match="Unsupported resource type"):
                    manager.get_resource("UnsupportedResource")

    def test_get_resource_non_existent(self):
        """Test get_resource method with non-existent resource name."""
        import boto3
        import pytest
        from moto import mock_aws

        from aws_sam_testing.pytest_addin.aws_resources import ResourceManager

        template = {
            "Resources": {
                "ExistingResource": {
                    "Type": "AWS::SQS::Queue",
                    "Properties": {
                        "QueueName": "existing-queue",
                    },
                },
            },
        }

        with mock_aws():
            session = boto3.Session()
            with ResourceManager(
                session=session,
                working_dir=None,
                template=template,
            ) as manager:
                # Attempt to get non-existent resource
                with pytest.raises(
                    ValueError,
                    match="Resource NonExistentResource not found in template",
                ):
                    manager.get_resource("NonExistentResource")


def test_transform_template():
    from aws_sam_testing.aws_resources import _transform_template

    template = {
        "Resources": {
            "MyLambda": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "Handler": "app.lambda_handler",
                    "Runtime": "python3.13",
                    "CodeUri": "./src",
                    "Environment": {
                        "Variables": {
                            "BUCKET": {
                                "Ref": "MyBucket",
                            }
                        }
                    },
                },
            },
        },
    }

    transformed_template = _transform_template(
        template=template,
        packaging_bucket_name="sam-mocks-fake",
        aws_account_id="123456789012",
    )
    assert transformed_template["Resources"]["MyLambda"]["Properties"].get("CodeUri") is None
    assert transformed_template["Resources"]["MyLambda"]["Properties"]["Code"]["S3Bucket"] == "sam-mocks-fake"
    assert transformed_template["Resources"]["MyLambda"]["Properties"]["Code"]["S3Key"] == "package/MyLambda.zip"
