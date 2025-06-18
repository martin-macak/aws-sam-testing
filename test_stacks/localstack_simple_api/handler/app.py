import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")


def lambda_handler(event, context):
    table_name = os.environ.get("USERS_TABLE_NAME")

    if not table_name:
        return {"statusCode": 500, "body": json.dumps({"error": "USERS_TABLE_NAME environment variable not set"})}

    try:
        table = dynamodb.Table(table_name)
        response = table.scan()

        users = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            users.extend(response.get("Items", []))

        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"users": users, "count": len(users)})}

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
