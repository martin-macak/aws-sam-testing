"""
Tests that all fixtures are registered and working.
"""


def test_mock_aws_session(mock_aws_session):
    assert mock_aws_session is not None


def test_mock_aws_lambda_context(mock_aws_lambda_context):
    assert mock_aws_lambda_context is not None


def test_mock_aws_resources(mock_aws_resources):
    assert mock_aws_resources is not None
