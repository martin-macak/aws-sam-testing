import datetime
import decimal
import json
import os
import uuid
from typing import Any, Dict

import boto3
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import Response
from aws_lambda_powertools.utilities.typing import LambdaContext

app = APIGatewayRestResolver()
dynamodb = boto3.resource("dynamodb")


class SafeJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


@app.get("/users")
def get_users() -> Response:
    table_name = os.environ.get("USERS_TABLE_NAME")

    if not table_name:
        return Response(status_code=500, body=json.dumps({"error": "USERS_TABLE_NAME environment variable not set"}), headers={"Content-Type": "application/json"})

    try:
        table = dynamodb.Table(table_name)
        response = table.scan()

        users = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            users.extend(response.get("Items", []))

        return Response(status_code=200, body=json.dumps({"users": users, "count": len(users)}, cls=SafeJsonEncoder), headers={"Content-Type": "application/json"})

    except Exception as e:
        return Response(status_code=500, body=json.dumps({"error": str(e)}), headers={"Content-Type": "application/json"})


@app.post("/users")
def create_user() -> Response:
    table_name = os.environ.get("USERS_TABLE_NAME")

    if not table_name:
        return Response(status_code=500, body=json.dumps({"error": "USERS_TABLE_NAME environment variable not set"}), headers={"Content-Type": "application/json"})

    try:
        body: Dict[str, Any] = app.current_event.json_body

        if not body:
            return Response(status_code=400, body=json.dumps({"error": "Request body is required"}), headers={"Content-Type": "application/json"})

        user_id = str(uuid.uuid4())
        user_item = {"userId": user_id, **body}

        table = dynamodb.Table(table_name)
        table.put_item(Item=user_item)

        return Response(status_code=201, body=json.dumps({"message": "User created successfully", "user": user_item}, cls=SafeJsonEncoder), headers={"Content-Type": "application/json"})

    except json.JSONDecodeError:
        return Response(status_code=400, body=json.dumps({"error": "Invalid JSON in request body"}), headers={"Content-Type": "application/json"})
    except Exception as e:
        return Response(status_code=500, body=json.dumps({"error": str(e)}), headers={"Content-Type": "application/json"})


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    return app.resolve(event, context)
