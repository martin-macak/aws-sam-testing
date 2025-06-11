import functools
import os
import uuid

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver()


@app.get("/hello")
@tracer.capture_method
def get_hello():
    return {"message": "Hello, World!"}


@app.post("/items")
@tracer.capture_method
def put_item():
    table = get_table()
    queue = get_queue()
    table.put_item(Item={"id": str(uuid.uuid4())})
    queue.send_message(MessageBody="Hello, World!")


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)


@functools.cache
def get_table() -> boto3.resource:
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def get_queue() -> boto3.resource:
    return boto3.resource("sqs").Queue(os.environ["QUEUE_NAME"])
