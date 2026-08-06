"""Lambda handler: creates a new task in DynamoDB."""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"message": "Invalid JSON body"})

    title = body.get("title")
    if not title:
        return _response(400, {"message": "'title' is required"})

    item = {
        "task_id": str(uuid.uuid4()),
        "title": title,
        "status": body.get("status", "pending"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    table.put_item(Item=item)

    return _response(201, item)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
