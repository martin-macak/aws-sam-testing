import json
import os
from typing import Any, Dict

import psycopg2
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.api_gateway import Response
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize API Gateway resolver
app = APIGatewayRestResolver()

# Get database connection parameters from environment variables
db_connection_string = os.environ["DB_CONNECTION_STRING"]

# Connect using direct keyword arguments
conn = psycopg2.connect(db_connection_string)


@app.get("/users")
def list_users() -> Response:
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET search_path TO app")
            cursor.execute("SELECT id, name FROM users")
            users = cursor.fetchall()
            users_list = [{"id": user[0], "name": user[1]} for user in users]
            return Response(
                status_code=200,
                body=json.dumps(users_list),
                headers={"Content-Type": "application/json"},
            )
    except Exception as e:
        return Response(
            status_code=500,
            body=json.dumps({"error": str(e)}),
            headers={"Content-Type": "application/json"},
        )


@app.post("/users")
def create_user() -> Response:
    try:
        body: Dict[str, Any] = app.current_event.json_body

        if not body:
            return Response(
                status_code=400,
                body=json.dumps({"error": "Request body is required"}),
                headers={"Content-Type": "application/json"},
            )

        name = body.get("name")
        if not name:
            return Response(
                status_code=400,
                body=json.dumps({"error": "Name is required"}),
                headers={"Content-Type": "application/json"},
            )

        with conn.cursor() as cursor:
            cursor.execute("SET search_path TO app")
            cursor.execute("INSERT INTO users (name) VALUES (%s) RETURNING id", (name,))
            user_id = cursor.fetchone()[0]
            conn.commit()
            return Response(
                status_code=201,
                body=json.dumps({"id": user_id, "name": name}),
                headers={"Content-Type": "application/json"},
            )
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            body=json.dumps({"error": "Invalid JSON in request body"}),
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        return Response(
            status_code=500,
            body=json.dumps({"error": str(e)}),
            headers={"Content-Type": "application/json"},
        )


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    return app.resolve(event, context)
