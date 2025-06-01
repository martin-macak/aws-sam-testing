import pytest
from sam_mocks.cfn import CloudFormationTemplateProcessor, load_yaml, RefTag, GetAttTag


def test_find_resources_by_type_single_match():
    """Test finding resources by type with a single match."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          FunctionName: my-function
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    # Find S3 buckets
    buckets = processor.find_resources_by_type("AWS::S3::Bucket")
    assert len(buckets) == 1
    assert buckets[0]["LogicalId"] == "MyBucket"
    assert buckets[0]["Type"] == "AWS::S3::Bucket"
    assert buckets[0]["Properties"]["BucketName"] == "my-bucket"

    # Find Lambda functions
    functions = processor.find_resources_by_type("AWS::Lambda::Function")
    assert len(functions) == 1
    assert functions[0]["LogicalId"] == "MyFunction"
    assert functions[0]["Type"] == "AWS::Lambda::Function"
    assert functions[0]["Properties"]["FunctionName"] == "my-function"


def test_find_resources_by_type_multiple_matches():
    """Test finding resources by type with multiple matches."""
    yaml_content = """
    Resources:
      Bucket1:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: bucket-1
      Bucket2:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: bucket-2
      Function1:
        Type: AWS::Lambda::Function
        Properties:
          FunctionName: function-1
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    # Find all S3 buckets
    buckets = processor.find_resources_by_type("AWS::S3::Bucket")
    assert len(buckets) == 2

    # Check logical IDs
    logical_ids = {bucket["LogicalId"] for bucket in buckets}
    assert logical_ids == {"Bucket1", "Bucket2"}

    # Check properties
    bucket_names = {bucket["Properties"]["BucketName"] for bucket in buckets}
    assert bucket_names == {"bucket-1", "bucket-2"}


def test_find_resources_by_type_no_matches():
    """Test finding resources by type with no matches."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    # Try to find Lambda functions (none exist)
    functions = processor.find_resources_by_type("AWS::Lambda::Function")
    assert len(functions) == 0


def test_find_resources_by_type_with_all_fields():
    """Test finding resources that have all optional fields."""
    yaml_content = """
    Resources:
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          FunctionName: my-function
        Metadata:
          BuildMethod: go1.x
        DependsOn:
          - MyRole
          - MyBucket
        Condition: IsProduction
        DeletionPolicy: Retain
        UpdateReplacePolicy: Delete
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    functions = processor.find_resources_by_type("AWS::Lambda::Function")
    assert len(functions) == 1

    func = functions[0]
    assert func["LogicalId"] == "MyFunction"
    assert func["Type"] == "AWS::Lambda::Function"
    assert func["Properties"]["FunctionName"] == "my-function"
    assert func["Metadata"]["BuildMethod"] == "go1.x"
    assert func["DependsOn"] == ["MyRole", "MyBucket"]
    assert func["Condition"] == "IsProduction"
    assert func["DeletionPolicy"] == "Retain"
    assert func["UpdateReplacePolicy"] == "Delete"


def test_find_resources_by_type_empty_template():
    """Test finding resources in an empty template."""
    processor = CloudFormationTemplateProcessor({})
    resources = processor.find_resources_by_type("AWS::S3::Bucket")
    assert resources == []


def test_find_resources_by_type_no_resources_section():
    """Test finding resources when Resources section is missing."""
    template = {"Parameters": {"Test": {"Type": "String"}}}
    processor = CloudFormationTemplateProcessor(template)
    resources = processor.find_resources_by_type("AWS::S3::Bucket")
    assert resources == []


def test_find_resource_by_logical_id_found():
    """Test finding a resource by logical ID when it exists."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
        Metadata:
          Documentation: Test bucket
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    bucket = processor.find_resource_by_logical_id("MyBucket")
    assert bucket["LogicalId"] == "MyBucket"
    assert bucket["Type"] == "AWS::S3::Bucket"
    assert bucket["Properties"]["BucketName"] == "my-bucket"
    assert bucket["Metadata"]["Documentation"] == "Test bucket"


def test_find_resource_by_logical_id_not_found():
    """Test finding a resource by logical ID when it doesn't exist."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    resource = processor.find_resource_by_logical_id("NonExistentResource")
    assert resource == {}


def test_find_resource_by_logical_id_with_all_fields():
    """Test finding a resource that has all optional fields."""
    yaml_content = """
    Resources:
      MyDatabase:
        Type: AWS::RDS::DBInstance
        Properties:
          DBInstanceIdentifier: my-database
        Metadata:
          Version: "1.0"
        DependsOn: MySecurityGroup
        Condition: IsProduction
        DeletionPolicy: Snapshot
        UpdateReplacePolicy: Retain
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    db = processor.find_resource_by_logical_id("MyDatabase")
    assert db["LogicalId"] == "MyDatabase"
    assert db["Type"] == "AWS::RDS::DBInstance"
    assert db["Properties"]["DBInstanceIdentifier"] == "my-database"
    assert db["Metadata"]["Version"] == "1.0"
    assert db["DependsOn"] == "MySecurityGroup"
    assert db["Condition"] == "IsProduction"
    assert db["DeletionPolicy"] == "Snapshot"
    assert db["UpdateReplacePolicy"] == "Retain"


def test_find_resource_by_logical_id_empty_template():
    """Test finding a resource in an empty template."""
    processor = CloudFormationTemplateProcessor({})
    resource = processor.find_resource_by_logical_id("MyBucket")
    assert resource == {}


def test_find_resource_by_logical_id_no_resources_section():
    """Test finding a resource when Resources section is missing."""
    template = {"Parameters": {"Test": {"Type": "String"}}}
    processor = CloudFormationTemplateProcessor(template)
    resource = processor.find_resource_by_logical_id("MyBucket")
    assert resource == {}


def test_find_resource_by_logical_id_invalid_resource():
    """Test finding a resource that exists but has invalid structure."""
    template = {"Resources": {"InvalidResource": "This is not a valid resource dict"}}
    processor = CloudFormationTemplateProcessor(template)
    resource = processor.find_resource_by_logical_id("InvalidResource")
    assert resource == {}


def test_find_resource_by_logical_id_missing_type():
    """Test finding a resource that exists but has no Type field."""
    template = {"Resources": {"InvalidResource": {"Properties": {"Name": "test"}}}}
    processor = CloudFormationTemplateProcessor(template)
    resource = processor.find_resource_by_logical_id("InvalidResource")
    assert resource == {}


def test_find_resources_by_type_with_tags():
    """Test finding resources that contain CloudFormation tags in properties."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Ref BucketNameParam
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_ARN: !GetAtt
                - MyBucket
                - Arn
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    # Find S3 bucket with Ref tag
    buckets = processor.find_resources_by_type("AWS::S3::Bucket")
    assert len(buckets) == 1
    assert isinstance(buckets[0]["Properties"]["BucketName"], RefTag)
    assert buckets[0]["Properties"]["BucketName"].value == "BucketNameParam"

    # Find Lambda function with GetAtt tag
    functions = processor.find_resources_by_type("AWS::Lambda::Function")
    assert len(functions) == 1
    env_vars = functions[0]["Properties"]["Environment"]["Variables"]
    assert isinstance(env_vars["BUCKET_ARN"], GetAttTag)
    assert env_vars["BUCKET_ARN"].value == ["MyBucket", "Arn"]


def test_find_resources_by_type_serverless_function():
    """Test finding AWS::Serverless::Function resources."""
    yaml_content = """
    Resources:
      MyServerlessFunction:
        Type: AWS::Serverless::Function
        Properties:
          Handler: index.handler
          Runtime: python3.9
      MyLambdaFunction:
        Type: AWS::Lambda::Function
        Properties:
          Handler: main.handler
          Runtime: python3.9
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    # Find serverless functions
    serverless_funcs = processor.find_resources_by_type("AWS::Serverless::Function")
    assert len(serverless_funcs) == 1
    assert serverless_funcs[0]["LogicalId"] == "MyServerlessFunction"

    # Find lambda functions (different type)
    lambda_funcs = processor.find_resources_by_type("AWS::Lambda::Function")
    assert len(lambda_funcs) == 1
    assert lambda_funcs[0]["LogicalId"] == "MyLambdaFunction"


def test_find_resources_case_sensitive():
    """Test that resource type matching is case-sensitive."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
    """
    template = load_yaml(yaml_content)
    processor = CloudFormationTemplateProcessor(template)

    # Correct case
    buckets = processor.find_resources_by_type("AWS::S3::Bucket")
    assert len(buckets) == 1

    # Wrong case
    buckets_lower = processor.find_resources_by_type("aws::s3::bucket")
    assert len(buckets_lower) == 0
