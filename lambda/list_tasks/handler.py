"""Lambda handler: lists all tasks in DynamoDB."""
import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def handler(event, context):
    # Note: table.scan() is fine for a small demo dataset.
    # For production scale, this would use a paginated Query
    # against a GSI instead of a full table Scan.
    result = table.scan()
    items = result.get("Items", [])

    return _response(200, {"tasks": items, "count": len(items)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
