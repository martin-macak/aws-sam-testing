import json
import logging
import os

import psycopg2
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()


def migrate_database(connection):
    with connection.cursor() as cursor:
        cursor.execute("CREATE SCHEMA IF NOT EXISTS app")
        cursor.execute("SET search_path TO app")
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255))")


def send_response(event, context, response_status, response_data, physical_resource_id=None, reason=None):
    response_url = event["ResponseURL"]

    response_body = {
        "Status": response_status,
        "Reason": reason or f"See the details in CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": physical_resource_id or context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": response_data,
    }

    json_response_body = json.dumps(response_body)

    headers = {"content-type": "", "content-length": str(len(json_response_body))}

    try:
        response = http.request("PUT", response_url, body=json_response_body, headers=headers)
        logger.info(f"Status code: {response.status}")
    except Exception as e:
        logger.error(f"send_response failed: {e}")


def lambda_handler(event, context):
    logger.info(f"Request: {json.dumps(event)}")
    is_cloudformation_event = event.get("StackId") is not None

    try:
        request_type = event["RequestType"]

        if request_type in ["Create", "Update", "Migrate"]:
            connection_string = os.environ["DB_CONNECTION_STRING"]

            # Connect to database
            connection = psycopg2.connect(connection_string)
            connection.autocommit = True

            try:
                # Run migration
                migrate_database(connection)
                logger.info("Database migration completed successfully")

                if is_cloudformation_event:
                    send_response(event, context, "SUCCESS", {"Message": "Database migration completed successfully"}, f"migration-{event['StackId']}")
                else:
                    return {
                        "Message": "Database migration completed successfully",
                    }

            finally:
                connection.close()

        elif request_type == "Delete":
            # Nothing to do on delete
            logger.info("Delete request - no action needed")
            send_response(event, context, "SUCCESS", {"Message": "Delete completed successfully"}, f"migration-{event['StackId']}")
        else:
            raise ValueError(f"Unknown request type: {request_type}")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        if is_cloudformation_event:
            send_response(event, context, "FAILED", {}, physical_resource_id=f"migration-{event.get('StackId', 'unknown')}", reason=str(e))
        else:
            raise e
