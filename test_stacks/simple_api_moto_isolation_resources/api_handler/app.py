import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")


def lambda_handler(event, context):
    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        return {"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": "TABLE_NAME environment variable is not set"})}

    table = dynamodb.Table(table_name)
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")

    if path == "/list-users" and http_method == "GET":
        try:
            response = table.scan()
            users = response.get("Items", [])
            return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"users": users})}
        except Exception as e:
            return {"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": str(e)})}
    elif path == "/create-user" and http_method == "POST":
        try:
            response = table.put_item(Item=json.loads(event.get("body", "{}")))
            return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"message": "User created"})}
        except Exception as e:
            return {"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": str(e)})}
    else:
        return {"statusCode": 404, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": "Not found"})}
