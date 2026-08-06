"""Lambda handler: deletes a task by task_id from DynamoDB."""
import json
import os

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    task_id = path_params.get("id")

    if not task_id:
        return _response(400, {"message": "'id' path parameter is required"})

    try:
        table.delete_item(
            Key={"task_id": task_id},
            ConditionExpression="attribute_exists(task_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _response(404, {"message": f"Task '{task_id}' not found"})
        raise

    return _response(204, {})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if body else "",
    }
