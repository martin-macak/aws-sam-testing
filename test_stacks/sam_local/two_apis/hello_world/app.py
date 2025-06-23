import json


def lambda_handler(event, context):
    """Sample Lambda function handler"""
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Hello World!", "path": event.get("path", "/"), "method": event.get("httpMethod", "GET")}),
        "headers": {"Content-Type": "application/json"},
    }
