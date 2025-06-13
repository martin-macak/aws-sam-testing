import pytest


@pytest.fixture(scope="function", autouse=True)
def isolated_aws(monkeypatch):
    import os

    from moto import mock_aws

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

    monkeypatch.setenv("AWS_REGION", region)
    monkeypatch.setenv("AWS_DEFAULT_REGION", region)
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
            region_name=region,
        )

        yield session
