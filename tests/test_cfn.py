from aws_sam_testing.cfn import (
    CloudFormationTemplateProcessor,
    load_yaml,
)
from aws_sam_testing.cfn_tags import CloudFormationObject


class TestCloudFormationTemplateProcessor:
    pass


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
        assert isinstance(bucket_data["Properties"]["BucketName"], CloudFormationObject)
        assert bucket_data["Properties"]["BucketName"].data == "BucketNameParam"

        # Find Lambda function with GetAtt tag
        functions = processor.find_resources_by_type("AWS::Lambda::Function")
        assert len(functions) == 1
        _, func_data = functions[0]
        env_vars = func_data["Properties"]["Environment"]["Variables"]
        assert isinstance(env_vars["BUCKET_ARN"], CloudFormationObject)
        assert env_vars["BUCKET_ARN"].data == ["MyBucket", "Arn"]

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


class TestRemoveResource:
    def test_remove_simple_resource(self):
        """Test removing a simple resource with no dependencies."""
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

        # Remove the bucket
        processor.remove_resource("MyBucket")

        # Verify bucket is removed
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]

    def test_remove_resource_with_ref_dependencies(self):
        """Test removing a resource that is referenced by other resources."""
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

        # Remove the bucket
        processor.remove_resource("MyBucket")

        # Verify bucket is removed and reference is cleaned up
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]
        # The Environment.Variables should be empty or removed
        func = processor.processed_template["Resources"]["MyFunction"]
        assert "Properties" not in func or "Environment" not in func["Properties"] or "Variables" not in func["Properties"]["Environment"] or not func["Properties"]["Environment"]["Variables"]

    def test_remove_resource_with_getatt_dependencies(self):
        """Test removing a resource that is referenced via GetAtt."""
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

        # Remove the bucket
        processor.remove_resource("MyBucket")

        # Verify bucket is removed and GetAtt reference is cleaned up
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]

    def test_remove_resource_with_depends_on(self):
        """Test removing a resource that is in DependsOn of other resources."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: my-bucket
          MyFunction:
            Type: AWS::Lambda::Function
            DependsOn: MyBucket
            Properties:
              FunctionName: my-function
          MyFunction2:
            Type: AWS::Lambda::Function
            DependsOn:
              - MyBucket
              - MyFunction
            Properties:
              FunctionName: my-function-2
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove the bucket
        processor.remove_resource("MyBucket")

        # Verify bucket is removed and DependsOn is updated
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]
        assert "MyFunction2" in processor.processed_template["Resources"]

        # MyFunction should have no DependsOn
        assert "DependsOn" not in processor.processed_template["Resources"]["MyFunction"]

        # MyFunction2 should only depend on MyFunction
        assert processor.processed_template["Resources"]["MyFunction2"]["DependsOn"] == ["MyFunction"]

    def test_remove_resource_referenced_in_outputs(self):
        """Test removing a resource that is referenced in Outputs."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: my-bucket
        Outputs:
          BucketName:
            Value: !Ref MyBucket
          BucketArn:
            Value: !GetAtt MyBucket.Arn
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove the bucket
        processor.remove_resource("MyBucket")

        # Verify bucket is removed and outputs are cleaned up
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert not processor.processed_template["Outputs"]

    def test_remove_serverless_function_event_references(self):
        """Test removing a resource that is referenced in serverless function events."""
        yaml_content = """
        Resources:
          MyApi:
            Type: AWS::ApiGateway::RestApi
            Properties:
              Name: MyApi
          MyFunction:
            Type: AWS::Serverless::Function
            Properties:
              Handler: index.handler
              Events:
                ApiEvent:
                  Type: Api
                  Properties:
                    RestApiId: !Ref MyApi
                    Path: /test
                    Method: GET
                S3Event:
                  Type: S3
                  Properties:
                    Bucket: my-bucket
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove the API
        processor.remove_resource("MyApi")

        # Verify API is removed and ApiEvent is removed
        assert "MyApi" not in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]

        events = processor.processed_template["Resources"]["MyFunction"]["Properties"]["Events"]
        assert "ApiEvent" not in events
        assert "S3Event" in events

    def test_remove_nonexistent_resource(self):
        """Test removing a resource that doesn't exist."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: my-bucket
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Try to remove non-existent resource
        processor.remove_resource("NonExistentResource")

        # Verify nothing changed
        assert "MyBucket" in processor.processed_template["Resources"]
        assert len(processor.processed_template["Resources"]) == 1

    def test_remove_resource_no_auto_dependencies(self):
        """Test removing a resource without auto-removing dependencies."""
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
              PolicyDocument:
                Statement:
                  - Effect: Allow
                    Principal: "*"
                    Action: "s3:GetObject"
                    Resource: !Sub "${MyBucket.Arn}/*"
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove the bucket without auto-removing dependencies
        processor.remove_resource("MyBucket", auto_remove_dependencies=False)

        # Verify bucket is removed but policy remains (though with broken references)
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyBucketPolicy" in processor.processed_template["Resources"]

    def test_remove_resource_with_json_intrinsic_functions(self):
        """Test removing a resource referenced with JSON-style intrinsic functions."""
        template = {
            "Resources": {
                "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}},
                "MyFunction": {"Type": "AWS::Lambda::Function", "Properties": {"Environment": {"Variables": {"BUCKET_NAME": {"Ref": "MyBucket"}, "BUCKET_ARN": {"Fn::GetAtt": ["MyBucket", "Arn"]}}}}},
            }
        }
        processor = CloudFormationTemplateProcessor(template)

        # Remove the bucket
        processor.remove_resource("MyBucket")

        # Verify bucket is removed and references are cleaned up
        assert "MyBucket" not in processor.processed_template["Resources"]
        assert "MyFunction" in processor.processed_template["Resources"]


class TestRemoveDependencies:
    def test_remove_circular_reference_island(self):
        """Test removing a circular reference island (resources that only reference each other)."""
        yaml_content = """
        Resources:
          # Main resource referenced by output
          MainBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: main-bucket
          
          # Circular reference island
          IslandBucket1:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Ref IslandBucket2
          IslandBucket2:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: island-bucket-2
              Tags:
                - Key: RelatedBucket
                  Value: !Ref IslandBucket1
                  
        Outputs:
          MainBucketName:
            Value: !Ref MainBucket
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove circular dependencies
        processor.remove_dependencies("")

        # Verify the island is removed but main bucket remains
        assert "MainBucket" in processor.processed_template["Resources"]
        assert "IslandBucket1" not in processor.processed_template["Resources"]
        assert "IslandBucket2" not in processor.processed_template["Resources"]

    def test_remove_self_referencing_resource(self):
        """Test removing a resource that references itself."""
        yaml_content = """
        Resources:
          MainFunction:
            Type: AWS::Lambda::Function
            Properties:
              FunctionName: main-function
              
          SelfReferencingFunction:
            Type: AWS::Lambda::Function
            Properties:
              FunctionName: self-ref
              Environment:
                Variables:
                  SELF_ARN: !GetAtt SelfReferencingFunction.Arn
                  
        Outputs:
          MainFunctionArn:
            Value: !GetAtt MainFunction.Arn
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove circular dependencies
        processor.remove_dependencies("")

        # Verify self-referencing resource is removed
        assert "MainFunction" in processor.processed_template["Resources"]
        assert "SelfReferencingFunction" not in processor.processed_template["Resources"]

    def test_remove_complex_circular_island(self):
        """Test removing a complex circular reference island with multiple resources."""
        yaml_content = """
        Resources:
          # Externally referenced resources
          MainApi:
            Type: AWS::ApiGateway::RestApi
            Properties:
              Name: main-api
              
          # Complex circular island
          IslandFunction1:
            Type: AWS::Lambda::Function
            Properties:
              FunctionName: island-func-1
              Environment:
                Variables:
                  ROLE_ARN: !GetAtt IslandRole.Arn
                  
          IslandFunction2:
            Type: AWS::Lambda::Function
            Properties:
              FunctionName: island-func-2
              Role: !GetAtt IslandRole.Arn
              Environment:
                Variables:
                  FUNC1_ARN: !GetAtt IslandFunction1.Arn
                  
          IslandRole:
            Type: AWS::IAM::Role
            Properties:
              RoleName: island-role
              Policies:
                - PolicyName: island-policy
                  PolicyDocument:
                    Statement:
                      - Effect: Allow
                        Action: lambda:InvokeFunction
                        Resource: 
                          - !GetAtt IslandFunction1.Arn
                          - !GetAtt IslandFunction2.Arn
                          
        Outputs:
          MainApiId:
            Value: !Ref MainApi
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove circular dependencies
        processor.remove_dependencies("")

        # Verify the entire island is removed
        assert "MainApi" in processor.processed_template["Resources"]
        assert "IslandFunction1" not in processor.processed_template["Resources"]
        assert "IslandFunction2" not in processor.processed_template["Resources"]
        assert "IslandRole" not in processor.processed_template["Resources"]

    def test_keep_resources_referenced_in_conditions(self):
        """Test that resources referenced in conditions are not removed."""
        yaml_content = """
        Parameters:
          Environment:
            Type: String
            Default: dev
            
        Conditions:
          IsProd: !Equals [!Ref Environment, "prod"]
          HasBucket: !Not [!Equals [!Ref ConditionalBucket, ""]]
          
        Resources:
          ConditionalBucket:
            Type: AWS::S3::Bucket
            Condition: IsProd
            Properties:
              BucketName: conditional-bucket
              
          UnreferencedBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: unreferenced-bucket
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove circular dependencies
        processor.remove_dependencies("")

        # Verify conditional bucket is kept (referenced in conditions)
        assert "ConditionalBucket" in processor.processed_template["Resources"]
        assert "UnreferencedBucket" not in processor.processed_template["Resources"]

    def test_keep_resources_with_depends_on_external(self):
        """Test that resources with DependsOn to external resources are kept."""
        yaml_content = """
        Resources:
          MainResource:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: main-bucket
              
          DependentResource:
            Type: AWS::S3::BucketPolicy
            DependsOn: MainResource
            Properties:
              Bucket: dependent-bucket
              PolicyDocument:
                Statement: []
                
          IslandResource:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: island-bucket
              
        Outputs:
          MainBucket:
            Value: !Ref MainResource
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove circular dependencies
        processor.remove_dependencies("")

        # Verify dependent resource is kept
        assert "MainResource" in processor.processed_template["Resources"]
        assert "DependentResource" in processor.processed_template["Resources"]
        assert "IslandResource" not in processor.processed_template["Resources"]

    def test_no_resources_removed_when_all_referenced(self):
        """Test that no resources are removed when all are externally referenced."""
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
              Tags:
                - Key: RelatedBucket
                  Value: !Ref Bucket1
                  
        Outputs:
          Bucket1Name:
            Value: !Ref Bucket1
          Bucket2Name:
            Value: !Ref Bucket2
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Remove circular dependencies
        processor.remove_dependencies("")

        # Verify no resources are removed
        assert "Bucket1" in processor.processed_template["Resources"]
        assert "Bucket2" in processor.processed_template["Resources"]

    def test_empty_template(self):
        """Test remove_dependencies on empty template."""
        processor = CloudFormationTemplateProcessor({})
        processor.remove_dependencies("")

        # Should not raise any errors
        assert processor.processed_template == {}

    def test_template_without_resources(self):
        """Test remove_dependencies on template without Resources section."""
        template = {"Parameters": {"Test": {"Type": "String"}}, "Outputs": {"TestOutput": {"Value": "test"}}}
        processor = CloudFormationTemplateProcessor(template)
        processor.remove_dependencies("")

        # Should not modify the template
        assert processor.processed_template == template


class TestTransformCfnTags:
    def test_transform_ref_tag(self):
        """Test transforming !Ref tags to JSON intrinsic functions."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Ref BucketNameParam
        Outputs:
          BucketRef:
            Value: !Ref MyBucket
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Transform tags
        processor.transform_cfn_tags()

        # Verify Ref tags are transformed
        bucket_props = processor.processed_template["Resources"]["MyBucket"]["Properties"]
        assert isinstance(bucket_props["BucketName"], dict)
        assert bucket_props["BucketName"] == {"Ref": "BucketNameParam"}

        output_value = processor.processed_template["Outputs"]["BucketRef"]["Value"]
        assert isinstance(output_value, dict)
        assert output_value == {"Ref": "MyBucket"}

    def test_transform_getatt_tag(self):
        """Test transforming !GetAtt tags to JSON intrinsic functions."""
        yaml_content = """
        Resources:
          MyFunction:
            Type: AWS::Lambda::Function
            Properties:
              Environment:
                Variables:
                  BUCKET_ARN: !GetAtt
                    - MyBucket
                    - Arn
                  ROLE_ARN: !GetAtt MyRole.Arn
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Transform tags
        processor.transform_cfn_tags()

        # Verify GetAtt tags are transformed
        env_vars = processor.processed_template["Resources"]["MyFunction"]["Properties"]["Environment"]["Variables"]

        # List format GetAtt
        assert isinstance(env_vars["BUCKET_ARN"], dict)
        assert env_vars["BUCKET_ARN"] == {"Fn::GetAtt": ["MyBucket", "Arn"]}

        # String format GetAtt (should be converted to list)
        assert isinstance(env_vars["ROLE_ARN"], dict)
        assert env_vars["ROLE_ARN"] == {"Fn::GetAtt": ["MyRole", "Arn"]}

    def test_transform_sub_tag(self):
        """Test transforming !Sub tags to JSON intrinsic functions."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Sub "my-bucket-${AWS::AccountId}"
              Tags:
                - Key: Name
                  Value: !Sub
                    - "${BucketPrefix}-bucket"
                    - BucketPrefix: !Ref BucketPrefixParam
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Transform tags
        processor.transform_cfn_tags()

        # Verify Sub tags are transformed
        bucket_props = processor.processed_template["Resources"]["MyBucket"]["Properties"]

        # Simple Sub
        assert isinstance(bucket_props["BucketName"], dict)
        assert bucket_props["BucketName"] == {"Fn::Sub": "my-bucket-${AWS::AccountId}"}

        # Sub with mapping
        tag_value = bucket_props["Tags"][0]["Value"]
        assert isinstance(tag_value, dict)
        assert "Fn::Sub" in tag_value
        assert isinstance(tag_value["Fn::Sub"], list)

    def test_transform_join_tag(self):
        """Test transforming !Join tags to JSON intrinsic functions."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Join
                - "-"
                - - !Ref BucketPrefix
                  - my-bucket
                  - !Ref AWS::AccountId
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Transform tags
        processor.transform_cfn_tags()

        # Verify Join tag is transformed
        bucket_name = processor.processed_template["Resources"]["MyBucket"]["Properties"]["BucketName"]
        assert isinstance(bucket_name, dict)
        assert "Fn::Join" in bucket_name
        assert bucket_name["Fn::Join"][0] == "-"
        assert isinstance(bucket_name["Fn::Join"][1], list)

    def test_transform_multiple_tag_types(self):
        """Test transforming multiple different tag types in one template."""
        yaml_content = """
        Resources:
          MyFunction:
            Type: AWS::Lambda::Function
            Properties:
              FunctionName: !Sub "${AWS::StackName}-function"
              Role: !GetAtt MyRole.Arn
              Environment:
                Variables:
                  BUCKET_NAME: !Ref MyBucket
                  TABLE_NAME: !Join ["-", [!Ref TablePrefix, "table"]]
                  BASE64_VALUE: !Base64 "Hello World"
                  SELECTED_AZ: !Select [0, !GetAZs ""]
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Transform tags
        processor.transform_cfn_tags()

        # Verify all tags are transformed
        props = processor.processed_template["Resources"]["MyFunction"]["Properties"]

        assert props["FunctionName"] == {"Fn::Sub": "${AWS::StackName}-function"}
        assert props["Role"] == {"Fn::GetAtt": ["MyRole", "Arn"]}

        env_vars = props["Environment"]["Variables"]
        assert env_vars["BUCKET_NAME"] == {"Ref": "MyBucket"}
        assert env_vars["TABLE_NAME"]["Fn::Join"][0] == "-"
        assert env_vars["BASE64_VALUE"] == {"Fn::Base64": "Hello World"}
        assert env_vars["SELECTED_AZ"]["Fn::Select"][0] == 0

    def test_transform_nested_tags(self):
        """Test transforming deeply nested CloudFormation tags."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Join
                - ""
                - - !Ref BucketPrefix
                  - !Sub "-${AWS::Region}-"
                  - !Select
                    - 0
                    - !Split
                      - "-"
                      - !Ref FullBucketName
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Transform tags
        processor.transform_cfn_tags()

        # Verify nested tags are all transformed
        bucket_name = processor.processed_template["Resources"]["MyBucket"]["Properties"]["BucketName"]
        assert isinstance(bucket_name, dict)
        assert "Fn::Join" in bucket_name

        # Check nested transformations
        join_values = bucket_name["Fn::Join"][1]
        assert isinstance(join_values[0], dict) and "Ref" in join_values[0]
        assert isinstance(join_values[1], dict) and "Fn::Sub" in join_values[1]
        assert isinstance(join_values[2], dict) and "Fn::Select" in join_values[2]

    def test_transform_preserves_non_tag_values(self):
        """Test that non-tag values are preserved during transformation."""
        yaml_content = """
        Resources:
          MyBucket:
            Type: AWS::S3::Bucket
            Properties:
              BucketName: !Ref BucketNameParam
              VersioningConfiguration:
                Status: Enabled
              Tags:
                - Key: Environment
                  Value: Production
                - Key: Owner
                  Value: !Ref OwnerParam
        """
        template = load_yaml(yaml_content)
        processor = CloudFormationTemplateProcessor(template)

        # Transform tags
        processor.transform_cfn_tags()

        # Verify non-tag values are preserved
        props = processor.processed_template["Resources"]["MyBucket"]["Properties"]
        assert props["BucketName"] == {"Ref": "BucketNameParam"}
        assert props["VersioningConfiguration"]["Status"] == "Enabled"
        assert props["Tags"][0]["Value"] == "Production"
        assert props["Tags"][1]["Value"] == {"Ref": "OwnerParam"}

    def test_transform_empty_template(self):
        """Test transforming empty template."""
        processor = CloudFormationTemplateProcessor({})
        processor.transform_cfn_tags()

        assert processor.processed_template == {}

    def test_transform_template_without_tags(self):
        """Test transforming template with no CloudFormation tags."""
        template = {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "my-bucket"}}}}
        processor = CloudFormationTemplateProcessor(template)
        processor.transform_cfn_tags()

        # Template should remain unchanged
        assert processor.processed_template == template
