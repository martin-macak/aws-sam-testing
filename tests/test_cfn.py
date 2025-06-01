import pytest
from sam_mocks.cfn import (
    load_yaml,
    RefTag,
    GetAttTag,
    SubTag,
    JoinTag,
    SplitTag,
    SelectTag,
    FindInMapTag,
    Base64Tag,
    CidrTag,
    ImportValueTag,
    GetAZsTag,
)

# Test data for valid YAML inputs
VALID_YAML_TESTS = [
    # Ref tag tests
    (
        """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Ref MyBucketName
        """,
        {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": RefTag("MyBucketName")}}}},
    ),
    # GetAtt tag tests
    (
        """
        Resources:
          MyInstance:
            Type: AWS::EC2::Instance
            Properties:
              UserData: !GetAtt 
                - MyInstance
                - PublicDnsName
        """,
        {"Resources": {"MyInstance": {"Type": "AWS::EC2::Instance", "Properties": {"UserData": GetAttTag(["MyInstance", "PublicDnsName"])}}}},
    ),
    # Sub tag tests
    (
        """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Sub ${AWS::StackName}-my-bucket
        """,
        {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": SubTag(["${AWS::StackName}-my-bucket"])}}}},
    ),
    # Join tag tests
    (
        """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Join 
                - '-'
                - - !Ref AWS::StackName
                  - my-bucket
        """,
        {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": JoinTag(["-", [RefTag("AWS::StackName"), "my-bucket"]])}}}},
    ),
    # Split tag tests
    (
        """
        Resources:
          MyFunction:
            Type: AWS::Lambda::Function
            Properties:
              Handler: !Split 
                - '.'
                - index.handler
        """,
        {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Handler": SplitTag([".", "index.handler"])}}}},
    ),
    # Select tag tests
    (
        """
        Resources:
          MyFunction:
            Type: AWS::Lambda::Function
            Properties:
              Runtime: !Select 
                - 0
                - - python3.9
                  - python3.8
        """,
        {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Runtime": SelectTag([0, ["python3.9", "python3.8"]])}}}},
    ),
    # FindInMap tag tests
    (
        """
        Resources:
          MyInstance:
            Type: AWS::EC2::Instance
            Properties:
              InstanceType: !FindInMap 
                - RegionMap
                - !Ref AWS::Region
                - InstanceType
        """,
        {"Resources": {"MyInstance": {"Type": "AWS::EC2::Instance", "Properties": {"InstanceType": FindInMapTag(["RegionMap", RefTag("AWS::Region"), "InstanceType"])}}}},
    ),
    # Base64 tag tests
    (
        """
        Resources:
          MyFunction:
            Type: AWS::Lambda::Function
            Properties:
              Code: !Base64 |
                def handler(event, context):
                    return {'statusCode': 200}
        """,
        {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Code": Base64Tag("def handler(event, context):\n    return {'statusCode': 200}\n")}}}},
    ),
    # Cidr tag tests
    (
        """
        Resources:
          MyVPC:
            Type: AWS::EC2::VPC
            Properties:
              CidrBlock: !Cidr 
                - 10.0.0.0/16
                - 8
                - 8
        """,
        {"Resources": {"MyVPC": {"Type": "AWS::EC2::VPC", "Properties": {"CidrBlock": CidrTag(["10.0.0.0/16", 8, 8])}}}},
    ),
    # ImportValue tag tests
    (
        """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !ImportValue MyExportedBucketName
        """,
        {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": ImportValueTag("MyExportedBucketName")}}}},
    ),
    # GetAZs tag tests
    (
        """
        Resources:
          MyVPC:
            Type: AWS::EC2::VPC
            Properties:
              AvailabilityZones: !GetAZs us-east-1
        """,
        {"Resources": {"MyVPC": {"Type": "AWS::EC2::VPC", "Properties": {"AvailabilityZones": GetAZsTag("us-east-1")}}}},
    ),
]

# Test data for invalid YAML inputs
INVALID_YAML_TESTS = [
    # Invalid Ref tag (missing value)
    """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Ref
    """,
    # Invalid GetAtt tag (wrong number of arguments)
    """
    Resources:
      MyInstance:
        Type: AWS::EC2::Instance
        Properties:
          UserData: !GetAtt MyInstance
    """,
    # Invalid Sub tag (missing value)
    """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Sub
    """,
    # Invalid Join tag (missing delimiter)
    """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Join
            - my-bucket
    """,
    # Invalid Split tag (missing delimiter)
    """
    Resources:
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Handler: !Split index.handler
    """,
    # Invalid Select tag (wrong index type)
    """
    Resources:
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Runtime: !Select 
            - "0"
            - - python3.9
              - python3.8
    """,
    # Invalid FindInMap tag (missing arguments)
    """
    Resources:
      MyInstance:
        Type: AWS::EC2::Instance
        Properties:
          InstanceType: !FindInMap RegionMap
    """,
    # Invalid Cidr tag (wrong number of arguments)
    """
    Resources:
      MyVPC:
        Type: AWS::EC2::VPC
        Properties:
          CidrBlock: !Cidr 10.0.0.0/16
    """,
]


@pytest.mark.parametrize("yaml_content,expected", VALID_YAML_TESTS)
def test_valid_yaml_parsing(yaml_content, expected):
    """Test parsing of valid YAML content with CloudFormation tags."""
    result = load_yaml(yaml_content)
    assert result == expected


@pytest.mark.parametrize("yaml_content", INVALID_YAML_TESTS)
def test_invalid_yaml_parsing(yaml_content):
    """Test that invalid YAML content raises appropriate exceptions."""
    with pytest.raises(Exception):
        load_yaml(yaml_content)


def test_nested_tags():
    """Test parsing of nested CloudFormation tags."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Join 
            - '-'
            - - !Ref AWS::StackName
              - !Sub ${Environment}-bucket
    """
    result = load_yaml(yaml_content)
    assert isinstance(result["Resources"]["MyBucket"]["Properties"]["BucketName"], JoinTag)
    join_tag = result["Resources"]["MyBucket"]["Properties"]["BucketName"]
    assert join_tag.value[0] == "-"
    assert isinstance(join_tag.value[1][0], RefTag)
    assert isinstance(join_tag.value[1][1], SubTag)


def test_empty_yaml():
    """Test parsing of empty YAML content."""
    result = load_yaml("")
    assert result is None


def test_yaml_without_tags():
    """Test parsing of YAML content without CloudFormation tags."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
    """
    result = load_yaml(yaml_content)
    assert result["Resources"]["MyBucket"]["Properties"]["BucketName"] == "my-bucket"


def test_yaml_with_comments():
    """Test parsing of YAML content with comments."""
    yaml_content = """
    # This is a comment
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          # Another comment
          BucketName: !Ref MyBucketName
    """
    result = load_yaml(yaml_content)
    assert isinstance(result["Resources"]["MyBucket"]["Properties"]["BucketName"], RefTag)
    assert result["Resources"]["MyBucket"]["Properties"]["BucketName"].value == "MyBucketName"


# Tests for CloudFormationTemplateProcessor
from sam_mocks.cfn import CloudFormationTemplateProcessor, load_yaml


def test_remove_dependencies_simple_ref():
    """Test removing dependencies with simple !Ref."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME: !Ref MyBucket
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyBucket should be removed as it's only referenced by MyFunction
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_multiple_references():
    """Test removing dependencies when resource is referenced by multiple resources."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction1:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME: !Ref MyBucket
      MyFunction2:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME: !Ref MyBucket
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction1")

    # MyBucket should NOT be removed as it's still referenced by MyFunction2
    assert "MyBucket" in processor.processed_template["Resources"]
    assert "MyFunction1" not in processor.processed_template["Resources"]
    assert "MyFunction2" in processor.processed_template["Resources"]


def test_remove_dependencies_transitive():
    """Test removing transitive dependencies."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyBucketPolicy:
        Type: AWS::S3::BucketPolicy
        Properties:
          Bucket: !Ref MyBucket
          PolicyDocument: {}
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_POLICY: !Ref MyBucketPolicy
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # Both MyBucketPolicy and MyBucket should be removed (transitive)
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyBucketPolicy" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_with_outputs():
    """Test that resources referenced in Outputs are not removed."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME: !Ref MyBucket
    Outputs:
      BucketName:
        Value: !Ref MyBucket
        Export:
          Name: MyBucketName
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyBucket should NOT be removed as it's referenced in Outputs
    assert "MyBucket" in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_get_att():
    """Test removing dependencies with !GetAtt."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
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
    processor.remove_resource("MyFunction")

    # MyBucket should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_sub_tag():
    """Test removing dependencies with !Sub tag."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_REF: !Sub "${MyBucket}-suffix"
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyBucket should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_fn_ref():
    """Test removing dependencies with Fn::Ref (dict style)."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME:
                Ref: MyBucket
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyBucket should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_fn_get_att():
    """Test removing dependencies with Fn::GetAtt (dict style)."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_ARN:
                Fn::GetAtt:
                  - MyBucket
                  - Arn
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyBucket should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_nested_tags():
    """Test removing dependencies with nested CloudFormation tags."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyRole:
        Type: AWS::IAM::Role
        Properties:
          AssumeRolePolicyDocument: {}
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              RESOURCE_ARN: !Join
                - ':'
                - - arn:aws:s3
                  - ''
                  - ''
                  - !GetAtt
                    - MyBucket
                    - Arn
                  - !Ref MyRole
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # Both MyBucket and MyRole should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyRole" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_circular():
    """Test removing dependencies with circular references."""
    yaml_content = """
    Resources:
      ResourceA:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Ref ResourceB
      ResourceB:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Ref ResourceA
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME: !Ref ResourceA
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # ResourceA and ResourceB should both be removed despite circular reference
    assert "ResourceA" not in processor.processed_template["Resources"]
    assert "ResourceB" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_in_conditions():
    """Test that resources referenced in Conditions are not removed."""
    yaml_content = """
    Resources:
      MyParameter:
        Type: AWS::SSM::Parameter
        Properties:
          Value: test
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              PARAM_NAME: !Ref MyParameter
    Conditions:
      IsProduction:
        Fn::Equals:
          - !Ref MyParameter
          - prod
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyParameter should NOT be removed as it's referenced in Conditions
    assert "MyParameter" in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_no_auto_remove():
    """Test remove_resource with auto_remove_dependencies=False."""
    template = {
        "Resources": {
            "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}},
            "MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Environment": {"Variables": {"BUCKET_NAME": RefTag("MyBucket")}}}},
        }
    }

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction", auto_remove_dependencies=False)

    # MyBucket should NOT be removed when auto_remove_dependencies=False
    assert "MyBucket" in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_complex_sub():
    """Test removing dependencies with complex !Sub tag with variable mapping."""
    template = {
        "Resources": {
            "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}},
            "MyRole": {"Type": "AWS::IAM::Role", "Properties": {"AssumeRolePolicyDocument": {}}},
            "MyFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Environment": {"Variables": {"RESOURCE_ARN": SubTag(["arn:aws:s3:::${BucketName}/${RoleName}", {"BucketName": RefTag("MyBucket"), "RoleName": RefTag("MyRole")}])}}},
            },
        }
    }

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # Both MyBucket and MyRole should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyRole" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_find_in_map():
    """Test removing dependencies with !FindInMap containing references."""
    template = {
        "Resources": {
            "MyParameter": {"Type": "AWS::SSM::Parameter", "Properties": {"Value": "test"}},
            "MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"InstanceType": FindInMapTag(["RegionMap", RefTag("MyParameter"), "InstanceType"])}},
        }
    }

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyParameter should be removed
    assert "MyParameter" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_ref_and_fn_ref():
    """Test removing dependencies with both !Ref and Fn::Ref."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction1:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME: !Ref MyBucket
      MyFunction2:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_NAME:
                Ref: MyBucket
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction1")
    processor.remove_resource("MyFunction2")

    # MyBucket should be removed after both functions are removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction1" not in processor.processed_template["Resources"]
    assert "MyFunction2" not in processor.processed_template["Resources"]


def test_remove_dependencies_getatt_and_fn_getatt():
    """Test removing dependencies with both !GetAtt and Fn::GetAtt."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction1:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_ARN: !GetAtt
                - MyBucket
                - Arn
      MyFunction2:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_ARN:
                Fn::GetAtt:
                  - MyBucket
                  - Arn
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction1")

    # MyBucket should NOT be removed as it's still referenced by MyFunction2
    assert "MyBucket" in processor.processed_template["Resources"]
    assert "MyFunction1" not in processor.processed_template["Resources"]
    assert "MyFunction2" in processor.processed_template["Resources"]


def test_remove_dependencies_sub_and_fn_sub():
    """Test removing dependencies with both !Sub and Fn::Sub."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction1:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_REF: !Sub "${MyBucket}-suffix"
      MyFunction2:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_REF:
                Fn::Sub: "${MyBucket}-suffix"
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction1")
    processor.remove_resource("MyFunction2")

    # MyBucket should be removed after both functions are removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction1" not in processor.processed_template["Resources"]
    assert "MyFunction2" not in processor.processed_template["Resources"]


def test_remove_dependencies_sub_with_exclamation():
    """Test removing dependencies with !Sub containing ${!ResourceName}."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              BUCKET_ARN: !Sub "arn:aws:s3:::${!MyBucket}"
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # MyBucket should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]


def test_remove_dependencies_multiple_refs_in_value():
    """Test removing dependencies when a single value contains multiple references."""
    yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
      MyRole:
        Type: AWS::IAM::Role
        Properties:
          AssumeRolePolicyDocument: {}
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              COMBINED: !Sub "${MyBucket}:${MyRole}"
    """
    template = load_yaml(yaml_content)

    processor = CloudFormationTemplateProcessor(template)
    processor.remove_resource("MyFunction")

    # Both MyBucket and MyRole should be removed
    assert "MyBucket" not in processor.processed_template["Resources"]
    assert "MyRole" not in processor.processed_template["Resources"]
    assert "MyFunction" not in processor.processed_template["Resources"]
