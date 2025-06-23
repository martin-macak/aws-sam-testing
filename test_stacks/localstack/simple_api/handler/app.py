import datetime
import decimal
import json
import os
import uuid

import boto3

dynamodb = boto3.resource("dynamodb")


def lambda_handler(event, context):
    table_name = os.environ.get("USERS_TABLE_NAME")

    if not table_name:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "USERS_TABLE_NAME environment variable not set"}),
        }

    http_method = event.get("httpMethod", "GET")

    if http_method == "GET":
        return get_users(table_name)
    elif http_method == "POST":
        return create_user(table_name, event)
    else:
        return {"statusCode": 405, "body": json.dumps({"error": "Method not allowed"})}


def get_users(table_name):
    try:
        table = dynamodb.Table(table_name)
        response = table.scan()

        users = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            users.extend(response.get("Items", []))

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"users": users, "count": len(users)}, cls=SafeJsonEncoder),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def create_user(table_name, event):
    try:
        body = json.loads(event.get("body", "{}"))

        if not body:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Request body is required"}),
            }

        user_id = str(uuid.uuid4())

        user_item = {"userId": user_id, **body}

        table = dynamodb.Table(table_name)
        table.put_item(Item=user_item)

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "User created successfully", "user": user_item}),
        }

    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON in request body"}),
        }
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


class SafeJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)
