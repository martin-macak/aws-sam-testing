import copy

import pytest

from aws_sam_testing.cfn import (
    Base64Tag,
    CidrTag,
    CloudFormationTemplateProcessor,
    FindInMapTag,
    GetAttTag,
    GetAZsTag,
    ImportValueTag,
    JoinTag,
    RefTag,
    SelectTag,
    SplitTag,
    SubTag,
    load_yaml,
)


class TestCloudFormationLoader:
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
        # GetAtt tag tests - array notation
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
        # GetAtt tag tests - dot notation
        (
            """
          Resources:
            MyInstance:
              Type: AWS::EC2::Instance
              Properties:
                UserData: !GetAtt MyInstance.PublicDnsName
          """,
            {"Resources": {"MyInstance": {"Type": "AWS::EC2::Instance", "Properties": {"UserData": GetAttTag(["MyInstance", "PublicDnsName"])}}}},
        ),
        # GetAtt tag tests - dot notation with nested attributes
        (
            """
          Resources:
            MyFunction:
              Type: AWS::Lambda::Function
              Properties:
                Environment:
                  Variables:
                    ROLE_ARN: !GetAtt HelloWorldFunctionRole.Arn
          """,
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Environment": {"Variables": {"ROLE_ARN": GetAttTag(["HelloWorldFunctionRole", "Arn"])}}}}}},
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
        # Invalid GetAtt tag (array notation with wrong number of arguments)
        """
      Resources:
        MyInstance:
          Type: AWS::EC2::Instance
          Properties:
            UserData: !GetAtt 
              - MyInstance
      """,
        # Invalid GetAtt tag (dot notation without dot)
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
    def test_valid_yaml_parsing(self, yaml_content, expected):
        """Test parsing of valid YAML content with CloudFormation tags."""
        result = load_yaml(yaml_content)
        assert result == expected

    @pytest.mark.parametrize("yaml_content", INVALID_YAML_TESTS)
    def test_invalid_yaml_parsing(self, yaml_content):
        """Test that invalid YAML content raises appropriate exceptions."""
        with pytest.raises(Exception):
            load_yaml(yaml_content)

    def test_nested_tags(self):
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

    def test_empty_yaml(self):
        """Test parsing of empty YAML content."""
        result = load_yaml("")
        assert result is None

    def test_yaml_without_tags(self):
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

    def test_yaml_with_comments(self):
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


class TestCloudFormationTemplateProcessor:
    def test_remove_dependencies_simple_ref(self):
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

    def test_remove_dependencies_multiple_references(self):
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

    def test_remove_dependencies_transitive(self):
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

    def test_remove_dependencies_with_outputs(self):
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

    def test_remove_dependencies_get_att(self):
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

    def test_remove_dependencies_get_att_dot_notation(self):
        """Test removing dependencies with !GetAtt using dot notation."""
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
                BUCKET_ARN: !GetAtt MyBucket.Arn
      """
        template = load_yaml(yaml_content)

        processor = CloudFormationTemplateProcessor(template)
        processor.remove_resource("MyFunction")

        # MyBucket should be removed
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyFunction" not in processor.processed_template["Resources"]

    def test_remove_dependencies_sub_tag(self):
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

    def test_remove_dependencies_fn_ref(self):
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

    def test_remove_dependencies_fn_get_att(self):
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

    def test_remove_dependencies_nested_tags(self):
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

    def test_remove_dependencies_circular(self):
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

    def test_remove_dependencies_in_conditions(self):
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

    def test_remove_dependencies_no_auto_remove(self):
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

    def test_remove_dependencies_complex_sub(self):
        """Test removing dependencies with complex !Sub tag with variable mapping."""
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}},
                "MyRole": {"Type": "AWS::IAM::Role", "Properties": {"AssumeRolePolicyDocument": {}}},
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Environment": {"Variables": {"RESOURCE_ARN": SubTag(["arn:aws:s3:::${BucketName}/${RoleName}", {"BucketName": RefTag("MyBucket"), "RoleName": RefTag("MyRole")}])}}
                    },
                },
            }
        }

        processor = CloudFormationTemplateProcessor(template)
        processor.remove_resource("MyFunction")

        # Both MyBucket and MyRole should be removed
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyRole" not in processor.processed_template["Resources"]
        assert "MyFunction" not in processor.processed_template["Resources"]

    def test_remove_dependencies_find_in_map(self):
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

    def test_remove_dependencies_ref_and_fn_ref(self):
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

    def test_remove_dependencies_getatt_and_fn_getatt(self):
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

    def test_remove_dependencies_direct_call(self):
        """Test calling remove_dependencies directly to remove circular references."""
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
        ResourceC:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: my-bucket
      """
        template = load_yaml(yaml_content)

        processor = CloudFormationTemplateProcessor(template)
        # Call remove_dependencies directly - it should remove circular references
        processor.remove_dependencies("any_resource")

        # ResourceA and ResourceB form a circular reference island and should be removed
        assert "ResourceA" not in processor.processed_template["Resources"]
        assert "ResourceB" not in processor.processed_template["Resources"]
        # ResourceC is not part of any circular reference and should remain
        assert "ResourceC" in processor.processed_template["Resources"]

    def test_remove_dependencies_complex_island(self):
        """Test removing complex circular reference islands."""
        yaml_content = """
      Resources:
        ResourceA:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref ResourceB
        ResourceB:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref ResourceC
        ResourceC:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref ResourceA
        ResourceD:
          Type: AWS::Lambda::Function
          Properties:
            Environment:
              Variables:
                BUCKET: !Ref ResourceE
        ResourceE:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref ResourceD
      """
        template = load_yaml(yaml_content)

        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("dummy")

        # All resources form circular reference islands and should be removed
        assert "ResourceA" not in processor.processed_template["Resources"]
        assert "ResourceB" not in processor.processed_template["Resources"]
        assert "ResourceC" not in processor.processed_template["Resources"]
        assert "ResourceD" not in processor.processed_template["Resources"]
        assert "ResourceE" not in processor.processed_template["Resources"]

    def test_remove_dependencies_island_with_external_reference(self):
        """Test that circular reference islands referenced from outside are not removed."""
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
        ResourceC:
          Type: AWS::Lambda::Function
          Properties:
            Environment:
              Variables:
                BUCKET: !Ref ResourceA
      """
        template = load_yaml(yaml_content)

        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("dummy")

        # ResourceA and ResourceB form a circular reference but ResourceA is referenced by ResourceC
        # So they should NOT be removed
        assert "ResourceA" in processor.processed_template["Resources"]
        assert "ResourceB" in processor.processed_template["Resources"]
        assert "ResourceC" in processor.processed_template["Resources"]

    def test_remove_dependencies_mixed_scenarios(self):
        """Test mixed scenarios with both removable and non-removable islands."""
        yaml_content = """
      Resources:
        # Circular reference island that should be removed
        IslandA1:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref IslandA2
        IslandA2:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref IslandA1
        
        # Circular reference island referenced from Outputs - should NOT be removed
        IslandB1:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref IslandB2
        IslandB2:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref IslandB1
        
        # Regular resource
        RegularResource:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: regular-bucket
            
      Outputs:
        BucketRef:
          Value: !Ref IslandB1
      """
        template = load_yaml(yaml_content)

        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("dummy")

        # IslandA1 and IslandA2 should be removed
        assert "IslandA1" not in processor.processed_template["Resources"]
        assert "IslandA2" not in processor.processed_template["Resources"]

        # IslandB1 and IslandB2 should NOT be removed (referenced in Outputs)
        assert "IslandB1" in processor.processed_template["Resources"]
        assert "IslandB2" in processor.processed_template["Resources"]

        # RegularResource should remain
        assert "RegularResource" in processor.processed_template["Resources"]

    def test_remove_dependencies_with_fn_functions(self):
        """Test circular references using Fn:: style functions."""
        yaml_content = """
      Resources:
        ResourceA:
          Type: AWS::S3::Bucket
          Properties:
            BucketName:
              Ref: ResourceB
        ResourceB:
          Type: AWS::S3::Bucket
          Properties:
            BucketName:
              Fn::Sub: "${ResourceA}-suffix"
      """
        template = load_yaml(yaml_content)

        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("dummy")

        # ResourceA and ResourceB form a circular reference and should be removed
        assert "ResourceA" not in processor.processed_template["Resources"]
        assert "ResourceB" not in processor.processed_template["Resources"]

    def test_remove_dependencies_self_reference(self):
        """Test resources that reference themselves."""
        yaml_content = """
      Resources:
        SelfReference:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: !Ref SelfReference
        NormalResource:
          Type: AWS::S3::Bucket
          Properties:
            BucketName: normal-bucket
      """
        template = load_yaml(yaml_content)

        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("dummy")

        # SelfReference forms a single-node cycle and should be removed
        assert "SelfReference" not in processor.processed_template["Resources"]
        # NormalResource should remain
        assert "NormalResource" in processor.processed_template["Resources"]

    def test_remove_dependencies_empty_template(self):
        """Test remove_dependencies on empty template."""
        template = {}
        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("dummy")
        assert processor.processed_template == {}

    def test_remove_dependencies_no_resources(self):
        """Test remove_dependencies on template without Resources section."""
        template = {"Outputs": {"Test": {"Value": "test"}}}
        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("dummy")
        assert processor.processed_template == {"Outputs": {"Test": {"Value": "test"}}}

    def test_remove_dependencies_sub_and_fn_sub(self):
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

    def test_remove_dependencies_sub_with_exclamation(self):
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

    def test_remove_dependencies_multiple_refs_in_value(self):
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


class TestFindResources:
    def test_find_resources_by_type_single_match(self):
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
        logical_id, bucket_data = buckets[0]
        assert logical_id == "MyBucket"
        assert bucket_data["LogicalId"] == "MyBucket"
        assert bucket_data["Type"] == "AWS::S3::Bucket"
        assert bucket_data["Properties"]["BucketName"] == "my-bucket"

        # Find Lambda functions
        functions = processor.find_resources_by_type("AWS::Lambda::Function")
        assert len(functions) == 1
        logical_id, func_data = functions[0]
        assert logical_id == "MyFunction"
        assert func_data["LogicalId"] == "MyFunction"
        assert func_data["Type"] == "AWS::Lambda::Function"
        assert func_data["Properties"]["FunctionName"] == "my-function"

    def test_find_resources_by_type_multiple_matches(self):
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
        logical_ids = {logical_id for logical_id, _ in buckets}
        assert logical_ids == {"Bucket1", "Bucket2"}

        # Check properties
        bucket_names = {bucket_data["Properties"]["BucketName"] for _, bucket_data in buckets}
        assert bucket_names == {"bucket-1", "bucket-2"}

    def test_find_resources_by_type_no_matches(self):
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

    def test_find_resources_by_type_with_all_fields(self):
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

        logical_id, func_data = functions[0]
        assert logical_id == "MyFunction"
        assert func_data["LogicalId"] == "MyFunction"
        assert func_data["Type"] == "AWS::Lambda::Function"
        assert func_data["Properties"]["FunctionName"] == "my-function"
        assert func_data["Metadata"]["BuildMethod"] == "go1.x"
        assert func_data["DependsOn"] == ["MyRole", "MyBucket"]
        assert func_data["Condition"] == "IsProduction"
        assert func_data["DeletionPolicy"] == "Retain"
        assert func_data["UpdateReplacePolicy"] == "Delete"

    def test_find_resources_by_type_empty_template(self):
        """Test finding resources in an empty template."""
        processor = CloudFormationTemplateProcessor({})
        resources = processor.find_resources_by_type("AWS::S3::Bucket")
        assert resources == []

    def test_find_resources_by_type_no_resources_section(self):
        """Test finding resources when Resources section is missing."""
        template = {"Parameters": {"Test": {"Type": "String"}}}
        processor = CloudFormationTemplateProcessor(template)
        resources = processor.find_resources_by_type("AWS::S3::Bucket")
        assert resources == []

    def test_find_resource_by_logical_id_found(self):
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

        logical_id, bucket_data = processor.find_resource_by_logical_id("MyBucket")
        assert logical_id == "MyBucket"
        assert bucket_data["LogicalId"] == "MyBucket"
        assert bucket_data["Type"] == "AWS::S3::Bucket"
        assert bucket_data["Properties"]["BucketName"] == "my-bucket"
        assert bucket_data["Metadata"]["Documentation"] == "Test bucket"

    def test_find_resource_by_logical_id_not_found(self):
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

        logical_id, resource_data = processor.find_resource_by_logical_id("NonExistentResource")
        assert logical_id == ""
        assert resource_data == {}

    def test_find_resource_by_logical_id_with_all_fields(self):
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

        logical_id, db_data = processor.find_resource_by_logical_id("MyDatabase")
        assert logical_id == "MyDatabase"
        assert db_data["LogicalId"] == "MyDatabase"
        assert db_data["Type"] == "AWS::RDS::DBInstance"
        assert db_data["Properties"]["DBInstanceIdentifier"] == "my-database"
        assert db_data["Metadata"]["Version"] == "1.0"
        assert db_data["DependsOn"] == "MySecurityGroup"
        assert db_data["Condition"] == "IsProduction"
        assert db_data["DeletionPolicy"] == "Snapshot"
        assert db_data["UpdateReplacePolicy"] == "Retain"

    def test_find_resource_by_logical_id_empty_template(self):
        """Test finding a resource in an empty template."""
        processor = CloudFormationTemplateProcessor({})
        logical_id, resource_data = processor.find_resource_by_logical_id("MyBucket")
        assert logical_id == ""
        assert resource_data == {}

    def test_find_resource_by_logical_id_no_resources_section(self):
        """Test finding a resource when Resources section is missing."""
        template = {"Parameters": {"Test": {"Type": "String"}}}
        processor = CloudFormationTemplateProcessor(template)
        logical_id, resource_data = processor.find_resource_by_logical_id("MyBucket")
        assert logical_id == ""
        assert resource_data == {}

    def test_find_resource_by_logical_id_invalid_resource(self):
        """Test finding a resource that exists but has invalid structure."""
        template = {"Resources": {"InvalidResource": "This is not a valid resource dict"}}
        processor = CloudFormationTemplateProcessor(template)
        logical_id, resource_data = processor.find_resource_by_logical_id("InvalidResource")
        assert logical_id == ""
        assert resource_data == {}

    def test_find_resource_by_logical_id_missing_type(self):
        """Test finding a resource that exists but has no Type field."""
        template = {"Resources": {"InvalidResource": {"Properties": {"Name": "test"}}}}
        processor = CloudFormationTemplateProcessor(template)
        logical_id, resource_data = processor.find_resource_by_logical_id("InvalidResource")
        assert logical_id == ""
        assert resource_data == {}

    def test_find_resources_by_type_with_tags(self):
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
        _, bucket_data = buckets[0]
        assert isinstance(bucket_data["Properties"]["BucketName"], RefTag)
        assert bucket_data["Properties"]["BucketName"].value == "BucketNameParam"

        # Find Lambda function with GetAtt tag
        functions = processor.find_resources_by_type("AWS::Lambda::Function")
        assert len(functions) == 1
        _, func_data = functions[0]
        env_vars = func_data["Properties"]["Environment"]["Variables"]
        assert isinstance(env_vars["BUCKET_ARN"], GetAttTag)
        assert env_vars["BUCKET_ARN"].value == ["MyBucket", "Arn"]

    def test_find_resources_by_type_serverless_function(self):
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
        logical_id, _ = serverless_funcs[0]
        assert logical_id == "MyServerlessFunction"

        # Find lambda functions (different type)
        lambda_funcs = processor.find_resources_by_type("AWS::Lambda::Function")
        assert len(lambda_funcs) == 1
        logical_id, _ = lambda_funcs[0]
        assert logical_id == "MyLambdaFunction"

    def test_find_resources_case_sensitive(self):
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


class TestTransformCfnTags:
    # Test data for transform_cfn_tags parametrized tests
    TRANSFORM_TAG_TESTS = [
        # !Ref -> Ref
        (
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": RefTag("MyParameter")}}}},
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Ref": "MyParameter"}}}}},
            "!Ref tag transformation",
        ),
        # !GetAtt with array notation -> Fn::GetAtt (no change needed)
        (
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Role": GetAttTag(["MyRole", "Arn"])}}}},
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Role": {"Fn::GetAtt": ["MyRole", "Arn"]}}}}},
            "!GetAtt array notation transformation",
        ),
        # !GetAtt with dot notation (converted to array) -> Fn::GetAtt
        (
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Role": GetAttTag(["MyRole", "Arn"])}}}},
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Role": {"Fn::GetAtt": ["MyRole", "Arn"]}}}}},
            "!GetAtt dot notation transformation (already converted to array by parser)",
        ),
        # !Sub simple -> Fn::Sub
        (
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": SubTag(["${AWS::StackName}-bucket"])}}}},
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Fn::Sub": "${AWS::StackName}-bucket"}}}}},
            "!Sub simple transformation",
        ),
        # !Sub with variable mapping -> Fn::Sub
        (
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": SubTag(["${BucketPrefix}-bucket", {"BucketPrefix": RefTag("BucketParam")}])}}}},
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Fn::Sub": ["${BucketPrefix}-bucket", {"BucketPrefix": {"Ref": "BucketParam"}}]}}}}},
            "!Sub with variable mapping transformation",
        ),
        # !Join -> Fn::Join
        (
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": JoinTag(["-", ["prefix", RefTag("Suffix")]])}}}},
            {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Fn::Join": ["-", ["prefix", {"Ref": "Suffix"}]]}}}}},
            "!Join transformation with nested tags",
        ),
        # !Split -> Fn::Split
        (
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Handler": SplitTag([".", RefTag("HandlerParam")])}}}},
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Handler": {"Fn::Split": [".", {"Ref": "HandlerParam"}]}}}}},
            "!Split transformation with nested tag",
        ),
        # !Select -> Fn::Select
        (
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Runtime": SelectTag([0, RefTag("RuntimesList")])}}}},
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Runtime": {"Fn::Select": [0, {"Ref": "RuntimesList"}]}}}}},
            "!Select transformation with nested tag",
        ),
        # !FindInMap -> Fn::FindInMap
        (
            {"Resources": {"MyInstance": {"Type": "AWS::EC2::Instance", "Properties": {"InstanceType": FindInMapTag(["RegionMap", RefTag("AWS::Region"), "InstanceType"])}}}},
            {"Resources": {"MyInstance": {"Type": "AWS::EC2::Instance", "Properties": {"InstanceType": {"Fn::FindInMap": ["RegionMap", {"Ref": "AWS::Region"}, "InstanceType"]}}}}},
            "!FindInMap transformation with nested tag",
        ),
        # !Base64 -> Fn::Base64
        (
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Code": Base64Tag(SubTag(["echo ${Message}"]))}}}},
            {"Resources": {"MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Code": {"Fn::Base64": {"Fn::Sub": "echo ${Message}"}}}}}},
            "!Base64 transformation with nested tag",
        ),
        # !Cidr -> Fn::Cidr
        (
            {"Resources": {"MyVPC": {"Type": "AWS::EC2::VPC", "Properties": {"CidrBlock": CidrTag([RefTag("VPCCidr"), 8, 8])}}}},
            {"Resources": {"MyVPC": {"Type": "AWS::EC2::VPC", "Properties": {"CidrBlock": {"Fn::Cidr": [{"Ref": "VPCCidr"}, 8, 8]}}}}},
            "!Cidr transformation with nested tag",
        ),
        # !ImportValue -> Fn::ImportValue
        (
            {"Outputs": {"MyOutput": {"Value": ImportValueTag(SubTag(["${StackName}-export"]))}}},
            {"Outputs": {"MyOutput": {"Value": {"Fn::ImportValue": {"Fn::Sub": "${StackName}-export"}}}}},
            "!ImportValue transformation with nested tag",
        ),
        # !GetAZs -> Fn::GetAZs
        (
            {"Resources": {"MyVPC": {"Type": "AWS::EC2::VPC", "Properties": {"AvailabilityZones": GetAZsTag(RefTag("AWS::Region"))}}}},
            {"Resources": {"MyVPC": {"Type": "AWS::EC2::VPC", "Properties": {"AvailabilityZones": {"Fn::GetAZs": {"Ref": "AWS::Region"}}}}}},
            "!GetAZs transformation with nested tag",
        ),
    ]

    @pytest.mark.parametrize("input_template,expected_template,description", TRANSFORM_TAG_TESTS)
    def test_transform_single_tag(self, input_template, expected_template, description):
        """Test transformation of individual CloudFormation tags."""
        processor = CloudFormationTemplateProcessor(input_template)
        processor.transform_cfn_tags()
        assert processor.processed_template == expected_template, f"Failed: {description}"

    def test_transform_deeply_nested_tags(self):
        """Test transformation of deeply nested CloudFormation tags."""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Environment": {
                            "Variables": {
                                "COMPLEX_VAR": JoinTag(
                                    [
                                        ":",
                                        [
                                            SelectTag([0, SplitTag([",", RefTag("ListParam")])]),
                                            GetAttTag(["MyBucket", "Arn"]),
                                            SubTag(["${Prefix}-${Suffix}", {"Prefix": RefTag("PrefixParam"), "Suffix": RefTag("SuffixParam")}]),
                                        ],
                                    ]
                                )
                            }
                        }
                    },
                }
            }
        }

        expected = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Environment": {
                            "Variables": {
                                "COMPLEX_VAR": {
                                    "Fn::Join": [
                                        ":",
                                        [
                                            {"Fn::Select": [0, {"Fn::Split": [",", {"Ref": "ListParam"}]}]},
                                            {"Fn::GetAtt": ["MyBucket", "Arn"]},
                                            {"Fn::Sub": ["${Prefix}-${Suffix}", {"Prefix": {"Ref": "PrefixParam"}, "Suffix": {"Ref": "SuffixParam"}}]},
                                        ],
                                    ]
                                }
                            }
                        }
                    },
                }
            }
        }

        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()
        assert processor.processed_template == expected

    def test_transform_multiple_resources(self):
        """Test transformation across multiple resources."""
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": RefTag("BucketNameParam")}},
                "MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Environment": {"Variables": {"BUCKET_ARN": GetAttTag(["MyBucket", "Arn"]), "BUCKET_NAME": RefTag("BucketNameParam")}}}},
            },
            "Outputs": {"BucketArn": {"Value": GetAttTag(["MyBucket", "Arn"])}, "FunctionName": {"Value": RefTag("MyFunction")}},
        }

        expected = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Ref": "BucketNameParam"}}},
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Environment": {"Variables": {"BUCKET_ARN": {"Fn::GetAtt": ["MyBucket", "Arn"]}, "BUCKET_NAME": {"Ref": "BucketNameParam"}}}},
                },
            },
            "Outputs": {"BucketArn": {"Value": {"Fn::GetAtt": ["MyBucket", "Arn"]}}, "FunctionName": {"Value": {"Ref": "MyFunction"}}},
        }

        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()
        assert processor.processed_template == expected

    def test_transform_empty_template(self):
        """Test transformation on empty template."""
        processor = CloudFormationTemplateProcessor({})
        processor.transform_cfn_tags()
        assert processor.processed_template == {}

    def test_transform_no_tags(self):
        """Test transformation on template without any tags."""
        template = {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-static-bucket"}}}}
        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()
        assert processor.processed_template == template

    def test_transform_mixed_tags_and_intrinsic_functions(self):
        """Test transformation when template already has some intrinsic functions."""
        template = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {
                        "BucketName": RefTag("BucketParam"),
                        "Tags": [
                            {"Key": "Name", "Value": {"Ref": "NameParam"}},  # Already in intrinsic function format
                            {"Key": "Env", "Value": RefTag("EnvParam")},  # Tag format
                        ],
                    },
                }
            }
        }

        expected = {
            "Resources": {
                "MyBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": {"Ref": "BucketParam"}, "Tags": [{"Key": "Name", "Value": {"Ref": "NameParam"}}, {"Key": "Env", "Value": {"Ref": "EnvParam"}}]},
                }
            }
        }

        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()
        assert processor.processed_template == expected

    def test_transform_preserves_original_template(self):
        """Test that transform_cfn_tags doesn't modify the original template."""
        original_template = {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": RefTag("BucketParam")}}}}

        # Create a copy to verify original isn't modified
        template_copy = copy.deepcopy(original_template)

        processor = CloudFormationTemplateProcessor(original_template)
        processor.transform_cfn_tags()

        # Original template should remain unchanged
        assert original_template == template_copy
        # Processed template should be transformed
        assert processor.processed_template != original_template
        assert processor.processed_template == {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": {"Ref": "BucketParam"}}}}}

    def test_transform_with_lists_of_tags(self):
        """Test transformation of lists containing tags."""
        template = {
            "Resources": {
                "MySecurityGroup": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "SecurityGroupIngress": [
                            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "SourceSecurityGroupId": RefTag("WebSecurityGroup")},
                            {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "SourceSecurityGroupId": GetAttTag(["ALBSecurityGroup", "GroupId"])},
                        ]
                    },
                }
            }
        }

        expected = {
            "Resources": {
                "MySecurityGroup": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "SecurityGroupIngress": [
                            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "SourceSecurityGroupId": {"Ref": "WebSecurityGroup"}},
                            {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "SourceSecurityGroupId": {"Fn::GetAtt": ["ALBSecurityGroup", "GroupId"]}},
                        ]
                    },
                }
            }
        }

        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()
        assert processor.processed_template == expected

    def test_transform_all_sections(self):
        """Test transformation across all CloudFormation template sections."""
        template = {
            "Parameters": {"BucketParam": {"Type": "String", "Default": "my-bucket"}},
            "Conditions": {"IsProduction": {"Fn::Equals": [RefTag("Environment"), "prod"]}, "HasBucket": {"Fn::Not": [{"Fn::Equals": [RefTag("BucketParam"), ""]}]}},
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Condition": "HasBucket", "Properties": {"BucketName": RefTag("BucketParam")}}},
            "Outputs": {"BucketArn": {"Condition": "HasBucket", "Value": GetAttTag(["MyBucket", "Arn"]), "Export": {"Name": SubTag(["${AWS::StackName}-bucket-arn"])}}},
        }

        expected = {
            "Parameters": {"BucketParam": {"Type": "String", "Default": "my-bucket"}},
            "Conditions": {"IsProduction": {"Fn::Equals": [{"Ref": "Environment"}, "prod"]}, "HasBucket": {"Fn::Not": [{"Fn::Equals": [{"Ref": "BucketParam"}, ""]}]}},
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Condition": "HasBucket", "Properties": {"BucketName": {"Ref": "BucketParam"}}}},
            "Outputs": {"BucketArn": {"Condition": "HasBucket", "Value": {"Fn::GetAtt": ["MyBucket", "Arn"]}, "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-bucket-arn"}}}},
        }

        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()
        assert processor.processed_template == expected

    def test_transform_getatt_dot_notation_with_nested_attributes(self):
        """Test that GetAtt dot notation with nested attributes is correctly transformed."""
        # Note: The GetAtt parser already converts dot notation to array format,
        # so we test that the array format is preserved correctly
        yaml_content = """
        Resources:
          MyTable:
            Type: AWS::DynamoDB::Table
            Properties:
              TableName: my-table
          MyFunction:
            Type: AWS::Lambda::Function
            Properties:
              Environment:
                Variables:
                  # These would be parsed from YAML as GetAttTag(["MyTable", "StreamArn"])
                  STREAM_ARN: !GetAtt MyTable.StreamArn
                  TABLE_ARN: !GetAtt MyTable.Arn
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()

        # Verify the transformation
        env_vars = processor.processed_template["Resources"]["MyFunction"]["Properties"]["Environment"]["Variables"]
        assert env_vars["STREAM_ARN"] == {"Fn::GetAtt": ["MyTable", "StreamArn"]}
        assert env_vars["TABLE_ARN"] == {"Fn::GetAtt": ["MyTable", "Arn"]}


class TestResourceMap:
    def test_resource_map_get_resource(self):
        yaml_content = """
    Resources:
      MyBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-bucket
    """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)
        resource_map = processor.load_resource_map()

        my_bucket = resource_map.get_resource("MyBucket")
        assert my_bucket

        assert my_bucket.physical_resource_id == "my-bucket"
