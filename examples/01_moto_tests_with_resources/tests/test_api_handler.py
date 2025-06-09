import json


def test_route_get_hello(
    mock_aws_lambda_context,
    mock_aws_resources,
):
    from api_handler.app import lambda_handler

    got = lambda_handler(
        {
            "path": "/hello",
            "httpMethod": "GET",
            "requestContext": {
                "resourcePath": "/hello",
                "httpMethod": "GET",
            },
        },
        mock_aws_lambda_context,
    )

    assert got["statusCode"] == 200
    assert got["body"] is not None
    body = json.loads(got["body"])
    assert body["message"] == "Hello, World!"
