"""Lambda handler: updates an existing task's title and/or status."""
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
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"message": "Invalid JSON body"})

    update_fields = {k: v for k, v in body.items() if k in ("title", "status")}
    if not update_fields:
        return _response(400, {"message": "Provide at least 'title' or 'status' to update"})

    expr_names = {f"#{k}": k for k in update_fields}
    expr_values = {f":{k}": v for k, v in update_fields.items()}
    update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in update_fields)

    try:
        result = table.update_item(
            Key={"task_id": task_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ConditionExpression="attribute_exists(task_id)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _response(404, {"message": f"Task '{task_id}' not found"})
        raise

    return _response(200, result["Attributes"])


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
