import json
import os

import psycopg2

connection_string = os.environ["DB_CONNECTION_STRING"]
conn = psycopg2.connect(connection_string)

# The database was created with the following commands:
# CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255))
# CREATE SCHEMA IF NOT EXISTS app


def lambda_handler(event, context):
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")

    try:
        if path == "/list-users" and http_method == "GET":
            with conn.cursor() as cursor:
                cursor.execute("SET search_path TO app")
                cursor.execute("SELECT id, name FROM users")
                users = cursor.fetchall()
                users_list = [{"id": user[0], "name": user[1]} for user in users]
                return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(users_list)}
        elif path == "/create-user" and http_method == "POST":
            try:
                body = json.loads(event.get("body", "{}"))
                name = body.get("name")
                if not name:
                    return {"statusCode": 400, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": "Name is required"})}

                with conn.cursor() as cursor:
                    cursor.execute("SET search_path TO app")
                    cursor.execute("INSERT INTO users (name) VALUES (%s) RETURNING id", (name,))
                    user_id = cursor.fetchone()[0]
                    conn.commit()
                    return {"statusCode": 201, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"id": user_id, "name": name})}
            except json.JSONDecodeError:
                return {"statusCode": 400, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": "Invalid JSON"})}
        else:
            return {"statusCode": 404, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": "Not found"})}
    except Exception as e:
        return {"statusCode": 500, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": str(e)})}
