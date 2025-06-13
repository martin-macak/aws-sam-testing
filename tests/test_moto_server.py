class TestMotoServer:
    def test_start_stop(self):
        import boto3

        from aws_sam_testing.moto_server import MotoServer

        with MotoServer() as moto_server:
            assert moto_server.is_running
            moto_server.start()
            moto_server.wait_for_start()

            s3 = boto3.client("s3", endpoint_url=f"http://127.0.0.1:{moto_server.port}")
            s3.create_bucket(Bucket="test-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
            s3.put_object(Bucket="test-bucket", Key="test-key", Body=b"test-body")
            response = s3.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"].read() == b"test-body"

            moto_server.stop()
            assert not moto_server.is_running
