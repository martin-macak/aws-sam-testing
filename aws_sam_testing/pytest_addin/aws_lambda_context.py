from dataclasses import dataclass

import pytest


@dataclass
class AWSLambdaContext:
    function_name: str
    function_version: str
    invoked_function_arn: str
    memory_limit_in_mb: int
    aws_request_id: str
    log_group_name: str
    log_stream_name: str
    identity: dict
    client_context: dict

    def get_remaining_time_in_millis(self) -> int:
        return 100


@pytest.fixture
def mock_aws_lambda_context(aws_region) -> AWSLambdaContext:
    """Procides mocked AWS Lambda context for testing

    Returns:
        AWSLambdaContext: Mocked AWS Lambda context
    """
    return AWSLambdaContext(
        function_name="test-function",
        function_version="$LATEST",
        invoked_function_arn=f"arn:aws:lambda:{aws_region}:123456789012:function:test-function",
        memory_limit_in_mb=128,
        aws_request_id="1234567890",
        log_group_name="/aws/lambda/test-function",
        log_stream_name="2021/01/01/[$LATEST]12345678901234567890123456789012",
        identity={},
        client_context={},
    )
