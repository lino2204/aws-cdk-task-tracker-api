"""Lambda handler: updates an existing task's title and/or status."""
import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

VALID_STATUSES = ("pending", "done")


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    task_id = path_params.get("id")

    if not task_id:
        return _response(400, {"message": "'id' path parameter is required"})

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"message": "Invalid JSON body"})

    if not isinstance(body, dict):
        return _response(400, {"message": "JSON body must be an object"})

    update_fields = {k: v for k, v in body.items() if k in ("title", "status")}
    if not update_fields:
        return _response(400, {"message": "Provide at least 'title' or 'status' to update"})

    if "title" in update_fields:
        title = update_fields["title"]
        if not isinstance(title, str) or not title.strip():
            return _response(400, {"message": "'title' must be a non-empty string"})
        update_fields["title"] = title.strip()

    if "status" in update_fields and update_fields["status"] not in VALID_STATUSES:
        return _response(
            400, {"message": "'status' must be one of: pending, done"}
        )

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

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
