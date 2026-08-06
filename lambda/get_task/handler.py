"""Lambda handler: fetches a single task by task_id from DynamoDB."""
import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    task_id = path_params.get("id")

    if not task_id:
        return _response(400, {"message": "'id' path parameter is required"})

    result = table.get_item(Key={"task_id": task_id})
    item = result.get("Item")

    if not item:
        return _response(404, {"message": f"Task '{task_id}' not found"})

    return _response(200, item)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
