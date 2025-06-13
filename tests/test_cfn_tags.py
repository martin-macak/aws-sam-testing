"""Tests for CloudFormation YAML tag support."""

import json

from aws_sam_testing.cfn import dump_yaml, load_yaml
from aws_sam_testing.cfn_tags import (
    CloudFormationObject,
    JSONFromYAMLEncoder,
)


class TestCloudFormationLoader:
    """Test CloudFormationLoader functionality."""

    def test_load_ref_tag(self):
        """Test loading !Ref tag."""
        yaml_content = "!Ref MyBucket"
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Ref"
        assert loaded.tag == "!Ref"
        assert loaded.data == "MyBucket"
        assert loaded.to_json() == {"Ref": "MyBucket"}

    def test_load_getatt_sequence(self):
        """Test loading !GetAtt tag with sequence syntax."""
        yaml_content = "!GetAtt [MyResource, Arn]"
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Fn::GetAtt"
        assert loaded.tag == "!GetAtt"
        assert loaded.data == ["MyResource", "Arn"]
        assert loaded.to_json() == {"Fn::GetAtt": ["MyResource", "Arn"]}

    def test_load_getatt_scalar(self):
        """Test loading !GetAtt tag with scalar (dot notation) syntax."""
        yaml_content = "!GetAtt MyResource.Arn"
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Fn::GetAtt"
        assert loaded.tag == "!GetAtt"
        assert loaded.data == "MyResource.Arn"
        # Should convert to array in JSON
        assert loaded.to_json() == {"Fn::GetAtt": ["MyResource", "Arn"]}

    def test_load_sub_scalar(self):
        """Test loading !Sub tag with scalar syntax."""
        yaml_content = "!Sub 'arn:aws:s3:::${BucketName}/*'"
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Fn::Sub"
        assert loaded.tag == "!Sub"
        assert loaded.data == "arn:aws:s3:::${BucketName}/*"
        assert loaded.to_json() == {"Fn::Sub": "arn:aws:s3:::${BucketName}/*"}

    def test_load_sub_sequence(self):
        """Test loading !Sub tag with sequence syntax (with variable mapping)."""
        yaml_content = """
!Sub
  - 'arn:aws:s3:::${BucketName}-${Suffix}/*'
  - BucketName: MyBucket
    Suffix: !Ref MySuffix
"""
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Fn::Sub"
        assert loaded.tag == "!Sub"
        assert isinstance(loaded.data, list)
        assert loaded.data[0] == "arn:aws:s3:::${BucketName}-${Suffix}/*"
        assert isinstance(loaded.data[1], dict)
        assert loaded.data[1]["BucketName"] == "MyBucket"
        assert isinstance(loaded.data[1]["Suffix"], CloudFormationObject)

    def test_load_join(self):
        """Test loading !Join tag."""
        yaml_content = """
!Join
  - ':'
  - - arn:aws:s3
    - ''
    - !Ref BucketName
"""
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Fn::Join"
        assert loaded.tag == "!Join"
        assert loaded.data[0] == ":"
        assert loaded.data[1][0] == "arn:aws:s3"
        assert loaded.data[1][1] == ""
        assert isinstance(loaded.data[1][2], CloudFormationObject)

    def test_load_if(self):
        """Test loading !If tag."""
        yaml_content = """
!If
  - CreateProdResources
  - !Ref ProdBucket
  - !Ref DevBucket
"""
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Fn::If"
        assert loaded.tag == "!If"
        assert loaded.data[0] == "CreateProdResources"
        assert isinstance(loaded.data[1], CloudFormationObject)
        assert isinstance(loaded.data[2], CloudFormationObject)

    def test_load_equals(self):
        """Test loading !Equals tag."""
        yaml_content = "!Equals [!Ref Environment, prod]"
        loaded = load_yaml(yaml_content)
        assert isinstance(loaded, CloudFormationObject)
        assert loaded.name == "Fn::Equals"
        assert loaded.tag == "!Equals"
        assert isinstance(loaded.data[0], CloudFormationObject)
        assert loaded.data[1] == "prod"

    def test_load_complex_template(self):
        """Test loading a complex CloudFormation template structure."""
        yaml_content = """
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${AWS::StackName}-bucket'
      Tags:
        - Key: Environment
          Value: !Ref Environment
        - Key: Application
          Value: !FindInMap [EnvironmentMap, !Ref Environment, AppName]
  MyRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Statement:
          - Effect: Allow
            Principal:
              Service: !Split [',', 'lambda.amazonaws.com,s3.amazonaws.com']
            Action: 'sts:AssumeRole'
      Policies:
        - PolicyName: S3Access
          PolicyDocument:
            Statement:
              - Effect: Allow
                Action: 's3:*'
                Resource: !GetAtt MyBucket.Arn
"""
        loaded = load_yaml(yaml_content)

        # Check bucket name has Sub
        bucket_name = loaded["Resources"]["MyBucket"]["Properties"]["BucketName"]
        assert isinstance(bucket_name, CloudFormationObject)
        assert bucket_name.name == "Fn::Sub"

        # Check tags have Ref and FindInMap
        tags = loaded["Resources"]["MyBucket"]["Properties"]["Tags"]
        assert isinstance(tags[0]["Value"], CloudFormationObject)
        assert tags[0]["Value"].name == "Ref"
        assert isinstance(tags[1]["Value"], CloudFormationObject)
        assert tags[1]["Value"].name == "Fn::FindInMap"

        # Check Split in principal service
        principal_service = loaded["Resources"]["MyRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]["Service"]
        assert isinstance(principal_service, CloudFormationObject)
        assert principal_service.name == "Fn::Split"

    def test_ref_with_dot_notation_converts_to_getatt(self):
        """Test that Ref with dot notation gets converted to GetAtt in JSON."""
        yaml_content = "!Ref MyResource.Property"
        loaded = load_yaml(yaml_content)
        assert loaded.name == "Ref"
        assert loaded.data == "MyResource.Property"
        # When converted to JSON, should become GetAtt
        assert loaded.to_json() == {"Fn::GetAtt": ["MyResource", "Property"]}

    def test_all_supported_functions(self):
        """Test that all supported CloudFormation functions can be loaded."""
        functions_to_test = [
            ("!And [!Equals [!Ref Env, prod], !Condition IsEast]", "Fn::And"),
            ("!Condition CreateProdResources", "Fn::Condition"),
            ("!Base64 'Hello World'", "Fn::Base64"),
            ("!GetAZs us-east-1", "Fn::GetAZs"),
            ("!ImportValue SharedBucketName", "Fn::ImportValue"),
            ("!Not [!Equals [!Ref Env, prod]]", "Fn::Not"),
            ("!Or [!Equals [!Ref Env, prod], !Equals [!Ref Env, staging]]", "Fn::Or"),
            ("!Select [0, !Ref MyList]", "Fn::Select"),
        ]

        for yaml_content, expected_name in functions_to_test:
            loaded = load_yaml(yaml_content)
            assert isinstance(loaded, CloudFormationObject)
            assert loaded.name == expected_name


class TestCloudFormationDumper:
    """Test CloudFormationDumper functionality."""

    def test_dump_ref_tag(self):
        """Test dumping Ref tag."""
        yaml_content = "!Ref MyBucket"
        loaded = load_yaml(yaml_content)

        # Dump it back
        dumped = dump_yaml(loaded)
        assert "!Ref" in dumped
        assert "MyBucket" in dumped

        # Re-load to verify
        reloaded = load_yaml(dumped)
        assert isinstance(reloaded, CloudFormationObject)
        assert reloaded.name == "Ref"
        assert reloaded.data == "MyBucket"

    def test_dump_getatt_sequence(self):
        """Test dumping GetAtt with sequence."""
        yaml_content = "!GetAtt [MyResource, Arn]"
        loaded = load_yaml(yaml_content)

        dumped = dump_yaml(loaded)
        assert "!GetAtt" in dumped

        reloaded = load_yaml(dumped)
        assert reloaded.name == "Fn::GetAtt"
        assert reloaded.data == ["MyResource", "Arn"]

    def test_dump_complex_structure(self):
        """Test dumping complex nested CloudFormation structures."""
        yaml_content = """
BucketPolicy:
  Type: AWS::S3::BucketPolicy
  Properties:
    Bucket: !Ref MyBucket
    PolicyDocument:
      Statement:
        - Effect: Allow
          Principal: '*'
          Action: 's3:GetObject'
          Resource: !Sub '${MyBucket.Arn}/*'
          Condition:
            StringEquals:
              's3:ExistingObjectTag/public': !If
                - IsProduction
                - 'false'
                - 'true'
"""
        loaded = load_yaml(yaml_content)
        dumped = dump_yaml(loaded)

        # Verify key tags are preserved
        assert "!Ref" in dumped and "MyBucket" in dumped
        assert "!Sub" in dumped
        assert "!If" in dumped

        # Re-load and compare
        reloaded = load_yaml(dumped)
        assert reloaded == loaded

    def test_dump_preserves_structure(self):
        """Test that dumping preserves the structure of lists and mappings."""
        yaml_content = """
Tags:
  - Key: Name
    Value: !Sub '${AWS::StackName}-instance'
  - Key: Environment
    Value: !Ref Environment
"""
        loaded = load_yaml(yaml_content)
        dumped = dump_yaml(loaded)
        reloaded = load_yaml(dumped)

        assert isinstance(reloaded["Tags"], list)
        assert len(reloaded["Tags"]) == 2
        assert isinstance(reloaded["Tags"][0]["Value"], CloudFormationObject)
        assert isinstance(reloaded["Tags"][1]["Value"], CloudFormationObject)

    def test_dump_all_function_types(self):
        """Test dumping all supported CloudFormation function types."""
        test_cases = [
            ("!And [!Ref Cond1, !Ref Cond2]", "Fn::And"),
            ("!Base64 'Hello World'", "Fn::Base64"),
            ("!Equals [value1, value2]", "Fn::Equals"),
            ("!FindInMap [MapName, TopKey, SecondKey]", "Fn::FindInMap"),
            ("!GetAZs us-east-1", "Fn::GetAZs"),
            ("!If [Condition, TrueValue, FalseValue]", "Fn::If"),
            ("!ImportValue ExportedValue", "Fn::ImportValue"),
            ("!Join [':', [a, b, c]]", "Fn::Join"),
            ("!Not [!Ref Condition]", "Fn::Not"),
            ("!Or [!Ref Cond1, !Ref Cond2]", "Fn::Or"),
            ("!Select [0, !Ref List]", "Fn::Select"),
            ("!Split [',', 'a,b,c']", "Fn::Split"),
            ("!Sub 'Hello ${World}'", "Fn::Sub"),
        ]

        for yaml_content, expected_name in test_cases:
            loaded = load_yaml(yaml_content)
            assert loaded.name == expected_name
            dumped = dump_yaml(loaded)
            reloaded = load_yaml(dumped)
            assert reloaded.name == expected_name


class TestIntegration:
    """Integration tests for CloudFormation tag support."""

    def test_load_dump_load_cycle(self):
        """Test that a template can be loaded, dumped, and loaded again without damage."""
        original_yaml = """
AWSTemplateFormatVersion: '2010-09-09'
Description: Test CloudFormation Template

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues:
      - dev
      - staging
      - prod

Mappings:
  EnvironmentMap:
    dev:
      InstanceType: t2.micro
    staging:
      InstanceType: t2.small
    prod:
      InstanceType: t2.medium

Conditions:
  IsProduction: !Equals [!Ref Environment, prod]
  IsNotDev: !Not [!Equals [!Ref Environment, dev]]
  IsProdOrStaging: !Or
    - !Equals [!Ref Environment, prod]
    - !Equals [!Ref Environment, staging]

Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Condition: IsProdOrStaging
    Properties:
      BucketName: !Sub '${AWS::StackName}-${Environment}-bucket'
      VersioningConfiguration:
        Status: !If [IsProduction, Enabled, Suspended]
      Tags:
        - Key: Environment
          Value: !Ref Environment
        - Key: Type
          Value: !FindInMap [EnvironmentMap, !Ref Environment, InstanceType]

  MyFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Join
        - '-'
        - - !Ref AWS::StackName
          - function
          - !Ref Environment
      Runtime: python3.9
      Handler: index.handler
      Code:
        ZipFile: !Base64 |
          def handler(event, context):
              return 'Hello World'
      Environment:
        Variables:
          BUCKET_NAME: !Ref MyBucket
          BUCKET_ARN: !GetAtt MyBucket.Arn
          REGIONS: !Join [',', !GetAZs '']

  MyRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Statement:
          - Effect: Allow
            Principal:
              Service: !Split
                - ','
                - !Sub 'lambda.amazonaws.com,s3.amazonaws.com'
            Action: 'sts:AssumeRole'
      Policies:
        - PolicyName: BucketAccess
          PolicyDocument:
            Statement:
              - Effect: !If [IsProduction, Deny, Allow]
                Action:
                  - 's3:*'
                Resource:
                  - !GetAtt MyBucket.Arn
                  - !Sub '${MyBucket.Arn}/*'

Outputs:
  BucketName:
    Value: !Ref MyBucket
    Export:
      Name: !Sub '${AWS::StackName}-bucket-name'
  BucketArn:
    Value: !GetAtt MyBucket.Arn
    Condition: IsProduction
  FunctionArn:
    Value: !GetAtt [MyFunction, Arn]
    Description: !Sub 'ARN for ${MyFunction}'
  ImportExample:
    Value: !ImportValue SharedResourceArn
"""

        # Load the original
        loaded = load_yaml(original_yaml)

        # Dump it
        dumped = dump_yaml(loaded)

        # Load it again
        reloaded = load_yaml(dumped)

        # Compare the structures
        assert reloaded == loaded

        # Verify specific elements maintained their types
        assert isinstance(reloaded["Conditions"]["IsProduction"], CloudFormationObject)
        assert isinstance(reloaded["Resources"]["MyBucket"]["Properties"]["BucketName"], CloudFormationObject)
        assert isinstance(reloaded["Resources"]["MyFunction"]["Properties"]["Environment"]["Variables"]["BUCKET_ARN"], CloudFormationObject)
        assert isinstance(reloaded["Outputs"]["ImportExample"]["Value"], CloudFormationObject)

    def test_json_encoding(self):
        """Test that CloudFormation objects can be encoded to JSON properly."""
        yaml_content = """
Resources:
  TestResource:
    Properties:
      Name: !Ref ResourceName
      Arn: !GetAtt Resource.Arn
      Value: !Sub '${AWS::Region}-${AWS::StackName}'
      Condition: !If [IsProduction, prod, dev]
      List: !Split [',', 'a,b,c']
      Encoded: !Base64 'data'
"""
        loaded = load_yaml(yaml_content)

        # Convert to JSON
        json_str = json.dumps(loaded, cls=JSONFromYAMLEncoder, indent=2)
        json_data = json.loads(json_str)

        # Verify JSON structure
        props = json_data["Resources"]["TestResource"]["Properties"]
        assert props["Name"] == {"Ref": "ResourceName"}
        assert props["Arn"] == {"Fn::GetAtt": ["Resource", "Arn"]}
        assert props["Value"] == {"Fn::Sub": "${AWS::Region}-${AWS::StackName}"}
        assert props["Condition"] == {"Fn::If": ["IsProduction", "prod", "dev"]}
        assert props["List"] == {"Fn::Split": [",", "a,b,c"]}
        assert props["Encoded"] == {"Fn::Base64": "data"}

    def test_mixed_content_preservation(self):
        """Test that mixed YAML content with and without tags is preserved."""
        yaml_content = """
Description: Simple test
Parameters:
  Param1:
    Type: String
    Default: value1
Resources:
  Resource1:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: my-bucket
      Tags:
        - Key: Name
          Value: !Ref Param1
        - Key: Static
          Value: static-value
Outputs:
  Output1:
    Value: !GetAtt Resource1.Arn
  Output2:
    Value: simple-string
"""
        loaded = load_yaml(yaml_content)
        dumped = dump_yaml(loaded)
        reloaded = load_yaml(dumped)

        # Check that both tagged and non-tagged values are preserved
        assert reloaded["Description"] == "Simple test"
        assert reloaded["Resources"]["Resource1"]["Properties"]["BucketName"] == "my-bucket"
        assert isinstance(reloaded["Resources"]["Resource1"]["Properties"]["Tags"][0]["Value"], CloudFormationObject)
        assert reloaded["Resources"]["Resource1"]["Properties"]["Tags"][1]["Value"] == "static-value"
        assert isinstance(reloaded["Outputs"]["Output1"]["Value"], CloudFormationObject)
        assert reloaded["Outputs"]["Output2"]["Value"] == "simple-string"

    def test_equality_operations(self):
        """Test CloudFormationObject equality operations."""
        yaml1 = "!Ref MyResource"
        yaml2 = "!Ref MyResource"
        yaml3 = "!Ref OtherResource"
        yaml4 = "!GetAtt MyResource.Arn"

        obj1 = load_yaml(yaml1)
        obj2 = load_yaml(yaml2)
        obj3 = load_yaml(yaml3)
        obj4 = load_yaml(yaml4)

        # Same tag and data should be equal
        assert obj1 == obj2

        # Different data should not be equal
        assert obj1 != obj3

        # Different tags should not be equal
        assert obj1 != obj4

    def test_string_representations(self):
        """Test string representations of CloudFormationObject."""
        yaml_content = "!Sub '${AWS::StackName}-bucket'"
        obj = load_yaml(yaml_content)

        # Test __str__
        str_repr = str(obj)
        assert "!Sub" in str_repr
        assert "${AWS::StackName}-bucket" in str_repr

        # Test __repr__
        repr_str = repr(obj)
        assert "Sub(" in repr_str
        assert "${AWS::StackName}-bucket" in repr_str
