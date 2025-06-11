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


def test_route_put_item(
    mock_aws_lambda_context,
    mock_aws_resources,
):
    from api_handler.app import lambda_handler

    with mock_aws_resources.set_environment(lambda_function_logical_name="ApiHandler"):
        got = lambda_handler(
            {
                "path": "/items",
                "httpMethod": "POST",
                "requestContext": {
                    "resourcePath": "/items",
                    "httpMethod": "POST",
                },
            },
            mock_aws_lambda_context,
        )

        assert got["statusCode"] == 200

        queue = mock_aws_resources.get_resource("MySQSQueue")
        messages = queue.receive_messages()
        assert len(messages) == 1
        message = messages[0]
        assert message.body == "Hello, World!"

        table = mock_aws_resources.get_resource("MyDynamoDBTable")
        items = table.scan()["Items"]
        assert len(items) == 1
        item = items[0]
        assert item["id"] is not None
