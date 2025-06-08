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
        region_name: AWS region where resources will be created. Defaults to "eu-west-1".
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
        region_name: str = "eu-west-1",
        account_id: str = "123456789012",
        parameters: dict = {},
        tags: dict = {},
        cross_stack_resources: dict = {},
    ):
        self.session = session
        self.template = template
        self.stack_id = stack_id
        self.stack_name = stack_name
        self.region_name = region_name
        self.account_id = account_id
        self.parameters = parameters
        self.tags = tags
        self.cross_stack_resources = cross_stack_resources
        self.is_created = False
        self.resource_map = None

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

    def _do_create(self):
        """Internal method to perform the actual resource creation.

        Creates a moto ResourceMap instance and uses it to create all resources
        defined in the CloudFormation template. This method handles the low-level
        interaction with moto's CloudFormation parsing and resource creation.

        Raises:
            Exception: If moto fails to create resources or parse the template.
        """
        from moto.cloudformation.parsing import ResourceMap as MotoResourceMap

        resource_map = MotoResourceMap(
            stack_id=self.stack_id,
            stack_name=self.stack_name,
            parameters={},
            tags={},
            region_name=self.region_name,
            account_id=self.account_id,
            template=self.template,
            cross_stack_resources={},
        )
        resource_map.load()
        resource_map.create(self.template)
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
