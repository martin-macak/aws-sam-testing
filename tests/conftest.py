import pytest


@pytest.fixture(scope="function", autouse=True)
def isolated_aws(monkeypatch, aws_region):
    from moto import mock_aws

    monkeypatch.setenv("MOTO_ALLOW_NONEXISTENT_REGION", "true")
    monkeypatch.setenv("AWS_REGION", aws_region)
    monkeypatch.setenv("AWS_DEFAULT_REGION", aws_region)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "test")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "test")

    with mock_aws():
        import boto3

        session = boto3.Session()
        boto3.setup_default_session(
            aws_access_key_id="test",
            aws_secret_access_key="test",
            aws_session_token="test",
            region_name=aws_region,
        )

        yield session
