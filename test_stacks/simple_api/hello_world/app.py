import json


def lambda_handler(event, context):
    """Sample Lambda function handler"""
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Hello World!",
            }
        ),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    }
