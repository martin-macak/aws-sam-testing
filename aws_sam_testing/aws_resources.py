import json
import os
from contextlib import contextmanager

import boto3


class AWSResourceManager:
    """Manages the creation and deletion of AWS resources using moto for mock environments.

    This class provides a context manager interface for creating and managing AWS resources
    based on CloudFormation templates. It uses the moto library to create mock AWS resources
    for testing purposes, allowing developers to test their applications without incurring
    actual AWS costs or requiring real AWS infrastructure.

    The class supports CloudFormation template processing and can handle resource dependencies,
    stack parameters, tags, and cross-stack resource references.

    Args:
        session: The boto3 session to use for AWS operations.
        template: CloudFormation template dictionary containing resource definitions.
        stack_id: Unique identifier for the CloudFormation stack. Defaults to "stack-123".
        stack_name: Human-readable name for the stack. Defaults to "my-stack".
        region_name: AWS region where resources will be created. Defaults to AWS_REGION environment variable.
        account_id: AWS account ID for resource creation. Defaults to "123456789012".
        parameters: CloudFormation template parameters as key-value pairs. Defaults to empty dict.
        tags: Resource tags as key-value pairs. Defaults to empty dict.
        cross_stack_resources: Resources from other stacks that this stack depends on. Defaults to empty dict.

    Attributes:
        is_created: Boolean indicating whether resources have been created.
        resource_map: Internal moto ResourceMap instance for managing resources.

    Example:
        >>> import boto3
        >>> from moto import mock_aws
        >>>
        >>> template = {
        ...     "Resources": {
        ...         "MyQueue": {
        ...             "Type": "AWS::SQS::Queue",
        ...             "Properties": {"QueueName": "test-queue"}
        ...         }
        ...     }
        ... }
        >>>
        >>> with mock_aws():
        ...     session = boto3.Session()
        ...     with AWSResourceManager(session=session, template=template) as manager:
        ...         # Resources are created and available for testing
        ...         sqs = session.client('sqs')
        ...         queues = sqs.list_queues()
        ...         print(f"Created {len(queues.get('QueueUrls', []))} queues")
    """

    def __init__(
        self,
        session: boto3.Session,
        template: dict,
        stack_id: str = "stack-123",
        stack_name: str = "my-stack",
        region_name: str | None = None,
        account_id: str = "123456789012",
        parameters: dict = {},
        tags: dict = {},
        cross_stack_resources: dict = {},
    ):
        import uuid

        from moto.cloudformation.parsing import ResourceMap

        self.session = session
        self.template = template
        self.packaging_bucket_name = f"aws-mocks-sam-bucket-{uuid.uuid4()}"
        self.stack_id = stack_id
        self.stack_name = stack_name
        self.region_name = region_name or os.environ["AWS_REGION"]
        self.account_id = account_id
        self.parameters = parameters
        self.tags = tags
        self.cross_stack_resources = cross_stack_resources
        self.is_created = False
        self.resource_map: ResourceMap | None = None
        self.transformed_template = _transform_template(
            template=template,
            packaging_bucket_name=self.packaging_bucket_name,
            aws_account_id=self.account_id,
        )

    def __enter__(self) -> "AWSResourceManager":
        """Enter the context manager and create AWS resources.

        Returns:
            AWSResourceManager: Self instance with resources created.
        """
        self.create()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the context manager and clean up AWS resources.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_value: Exception value if an exception occurred.
            traceback: Exception traceback if an exception occurred.
        """
        self.delete()

    def create(self):
        """Create AWS resources from the CloudFormation template.

        This method is idempotent - calling it multiple times will not
        create duplicate resources. Resources are only created once.

        Raises:
            Exception: If resource creation fails due to template errors
                      or AWS service limitations.
        """
        if self.is_created:
            return

        self._do_create()
        self.is_created = True

    def delete(self):
        """Delete all created AWS resources.

        This method is idempotent - calling it multiple times will not
        cause errors. Resources are only deleted if they were previously created.

        Raises:
            Exception: If resource deletion fails due to dependency issues
                      or AWS service limitations.
        """
        if not self.is_created:
            return

        self._do_delete()
        self.is_created = False

    @contextmanager
    def set_environment(
        self,
        lambda_function_logical_name: str,
        additional_environment: dict = {},
    ):
        import os

        if self.resource_map is None:
            raise ValueError("Resources not created")

        resource_map = self.resource_map
        resources = resource_map.resources
        assert resources is not None
        if lambda_function_logical_name not in resources:
            raise ValueError(f"Lambda function {lambda_function_logical_name} not found in template")

        lambda_function = resource_map[lambda_function_logical_name]
        if lambda_function is None:
            raise ValueError(f"Lambda function {lambda_function_logical_name} not found in template")

        current_environment = os.environ.copy()
        new_environment = {
            **current_environment,
            **lambda_function.environment_vars,
            **additional_environment,
        }
        old_environment = current_environment.copy()

        try:
            os.environ.update(new_environment)
            yield
        finally:
            # iterate over current os.environ and remove keys that are not present in old_environment
            for key in os.environ:
                if key not in old_environment:
                    os.environ.pop(key)
            os.environ.update(old_environment)

    def get_cfn_resource_by_name(self, resource_name: str):
        if self.resource_map is None:
            raise ValueError("Resources not created")

        resource_map = self.resource_map

        if resource_name not in resource_map.resources:
            raise ValueError(f"Resource {resource_name} not found in template")

        return resource_map[resource_name]

    def _do_create(self):
        """Internal method to perform the actual resource creation.

        Creates a moto ResourceMap instance and uses it to create all resources
        defined in the CloudFormation template. This method handles the low-level
        interaction with moto's CloudFormation parsing and resource creation.

        Raises:
            Exception: If moto fails to create resources or parse the template.
        """
        from moto.cloudformation.parsing import ResourceMap

        s3 = self.session.client("s3")
        iam = self.session.client("iam")

        try:
            iam.create_role(
                RoleName="aws-mocks-lambda-role",
                AssumeRolePolicyDocument=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "lambda.amazonaws.com"},
                                "Action": "sts:AssumeRole",
                            }
                        ],
                    }
                ),
            )
        except Exception as e:
            if "EntityAlreadyExists" in str(e):
                pass
            else:
                raise e

        try:
            params = {} if self.region_name == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": self.region_name}}
            s3.create_bucket(
                Bucket=self.packaging_bucket_name,
                **params,  # type: ignore
            )
        except Exception as e:
            if "BucketAlreadyExists" in str(e):
                pass
            else:
                raise e

        resource_map = ResourceMap(
            stack_id=self.stack_id,
            stack_name=self.stack_name,
            parameters={},
            tags={},
            region_name=self.region_name,
            account_id=self.account_id,
            template=self.transformed_template,
            cross_stack_resources={},
        )
        resource_map.create(self.transformed_template)
        self.resource_map = resource_map

    def _do_delete(self):
        """Internal method to perform the actual resource deletion.

        Uses the stored ResourceMap instance to delete all created resources.
        This method handles the low-level interaction with moto's resource cleanup.

        Raises:
            Exception: If moto fails to delete resources due to dependencies
                      or other constraints.
        """
        if self.resource_map is not None:
            self.resource_map.delete()

        try:
            s3 = self.session.client("s3")
            s3.delete_bucket(Bucket=self.packaging_bucket_name)
        except Exception as e:
            if "NoSuchBucket" in str(e):
                pass
            else:
                raise e


def _transform_template(
    template: dict,
    aws_account_id: str,
    packaging_bucket_name: str,
) -> dict:
    from aws_sam_testing.cfn import CloudFormationTemplateProcessor

    transformed_template = (
        CloudFormationTemplateProcessor(
            template=template,
        )
        .transform_cfn_tags()
        .processed_template
    )

    globals = transformed_template.get("Globals", {})
    global_environment_variables = globals.get("Function", {}).get("Environment", {}).get("Variables", {})

    # Transform AWS::Serverless::Function to AWS::Lambda::Function
    if "Resources" in transformed_template:
        for resource_name, resource in transformed_template["Resources"].items():
            if resource.get("Type") == "AWS::Serverless::Function":
                # Change the type to Lambda Function
                resource["Type"] = "AWS::Lambda::Function"

                # Transform CodeUri to Code if present
                if "Properties" in resource:
                    props = resource["Properties"]
                    if "CodeUri" in props:
                        props.pop("CodeUri")
                    props["Code"] = {
                        "S3Bucket": packaging_bucket_name,
                        "S3Key": f"package/{resource_name}.zip",
                    }
                    props["Role"] = f"arn:aws:iam::{aws_account_id}:role/aws-mocks-lambda-role"
                    props["Environment"] = {
                        "Variables": {
                            **global_environment_variables,
                            **props.get("Environment", {}).get("Variables", {}),
                        },
                    }

    return transformed_template
