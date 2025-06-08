def test_mock_aws_context(mock_aws_lambda_context):
    assert mock_aws_lambda_context.function_name == "test-function"
