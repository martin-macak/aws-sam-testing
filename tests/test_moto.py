from aws_sam_testing.cfn import load_yaml


def test_cloudformation_load():
    template_str = """
Parameters:
    BucketName:
        Type: String
        Default: my-bucket

Resources:
    MyBucket:
        Type: AWS::S3::Bucket
        Properties:
            BucketName: 
                Ref: BucketName
    """

    import moto
    from moto.cloudformation.parsing import ResourceMap

    template = load_yaml(template_str)

    with moto.mock_aws():
        resource_map = ResourceMap(
            stack_id="stack-123",
            stack_name="my-stack",
            parameters={},
            tags={},
            region_name="us-east-1",
            account_id="123",
            template=template,
            cross_stack_resources={},
        )

        resource_map.load()

    assert resource_map.resources is not None
    assert "MyBucket" in resource_map.resources
    assert resource_map["MyBucket"] is not None
    assert resource_map["MyBucket"].physical_resource_id == "my-bucket"
