class TestMotoServer:
    def test_start_stop(self, aws_region):
        import boto3

        from aws_sam_testing.moto_server import MotoServer

        with MotoServer() as moto_server:
            assert moto_server.is_running
            moto_server.wait_for_start()

            s3 = boto3.client("s3", endpoint_url=f"http://127.0.0.1:{moto_server.port}")
            if aws_region == "us-east-1":
                s3.create_bucket(
                    Bucket="test-bucket",
                )
            else:
                s3.create_bucket(
                    Bucket="test-bucket",
                    CreateBucketConfiguration={"LocationConstraint": aws_region},
                )
            s3.put_object(Bucket="test-bucket", Key="test-key", Body=b"test-body")
            response = s3.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"].read() == b"test-body"

            moto_server.stop()
            assert not moto_server.is_running

    def test_moto_server_with_resource_map(self, aws_region):
        import boto3
        from moto.cloudformation.parsing import ResourceMap

        from aws_sam_testing.cfn import load_yaml
        from aws_sam_testing.moto_server import MotoServer

        template_str = """
Resources:
  S3Bucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: test-bucket
        """

        template = load_yaml(template_str)

        with MotoServer() as moto_server:
            moto_server.wait_for_start()

            resource_map = ResourceMap(
                stack_id="test-stack",
                stack_name="test-stack",
                parameters={},
                tags={},
                region_name=aws_region,
                account_id="123456789012",
                template=template,
                cross_stack_resources={},
            )
            resource_map.load()
            resource_map.create(template)

            s3 = boto3.client("s3", endpoint_url=f"http://127.0.0.1:{moto_server.port}")
            list_buckets = s3.list_buckets()
            assert len(list_buckets["Buckets"]) == 1
