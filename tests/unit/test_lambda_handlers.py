"""
Unit tests for the CRUD Lambda handlers in lambda/.

Uses moto's @mock_aws to emulate DynamoDB in memory so each handler's
request validation, DynamoDB interaction, and HTTP response formatting
can be verified quickly without deploying to AWS.
"""
import importlib.util
import json
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "tasks"
LAMBDA_ROOT = Path(__file__).resolve().parents[2] / "lambda"


def _load_handler(handler_name: str):
    """Dynamically load lambda/<handler_name>/handler.py as a module."""
    handler_path = LAMBDA_ROOT / handler_name / "handler.py"
    spec = importlib.util.spec_from_file_location(
        f"lambda_{handler_name}_handler", handler_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def dynamo_env(monkeypatch):
    """Set up an in-memory mocked DynamoDB 'tasks' table per test."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("TABLE_NAME", TABLE_NAME)

    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "task_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "task_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


def test_create_task_success_defaults_status_to_pending(dynamo_env):
    mod = _load_handler("create_task")
    event = {"body": json.dumps({"title": "Write unit tests"})}

    response = mod.handler(event, None)

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["title"] == "Write unit tests"
    assert body["status"] == "pending"
    assert "task_id" in body
    assert "created_at" in body

    # Verify item was persisted in DynamoDB
    stored = dynamo_env.get_item(Key={"task_id": body["task_id"]}).get("Item")
    assert stored == body


def test_create_task_with_custom_status(dynamo_env):
    mod = _load_handler("create_task")
    event = {"body": json.dumps({"title": "Ship release", "status": "done"})}

    response = mod.handler(event, None)

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["status"] == "done"


def test_create_task_missing_title_returns_400(dynamo_env):
    mod = _load_handler("create_task")
    event = {"body": json.dumps({"status": "pending"})}

    response = mod.handler(event, None)

    assert response["statusCode"] == 400
    assert "'title' is required" in json.loads(response["body"])["message"]


def test_create_task_invalid_json_returns_400(dynamo_env):
    mod = _load_handler("create_task")
    event = {"body": "{not-valid-json"}

    response = mod.handler(event, None)

    assert response["statusCode"] == 400
    assert "Invalid JSON body" in json.loads(response["body"])["message"]


# ---------------------------------------------------------------------------
# get_task
# ---------------------------------------------------------------------------


def test_get_task_returns_existing_item(dynamo_env):
    item = {
        "task_id": "task-123",
        "title": "Read docs",
        "status": "pending",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    dynamo_env.put_item(Item=item)

    mod = _load_handler("get_task")
    response = mod.handler({"pathParameters": {"id": "task-123"}}, None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == item


def test_get_task_not_found_returns_404(dynamo_env):
    mod = _load_handler("get_task")
    response = mod.handler({"pathParameters": {"id": "nonexistent"}}, None)

    assert response["statusCode"] == 404
    assert "not found" in json.loads(response["body"])["message"]


def test_get_task_missing_id_param_returns_400(dynamo_env):
    mod = _load_handler("get_task")
    response = mod.handler({"pathParameters": None}, None)

    assert response["statusCode"] == 400
    assert "'id' path parameter is required" in json.loads(response["body"])["message"]


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


def test_list_tasks_empty_table(dynamo_env):
    mod = _load_handler("list_tasks")
    response = mod.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body == {"tasks": [], "count": 0}


def test_list_tasks_returns_all_items(dynamo_env):
    dynamo_env.put_item(
        Item={"task_id": "1", "title": "First", "status": "pending"}
    )
    dynamo_env.put_item(
        Item={"task_id": "2", "title": "Second", "status": "done"}
    )

    mod = _load_handler("list_tasks")
    response = mod.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["count"] == 2
    task_ids = {t["task_id"] for t in body["tasks"]}
    assert task_ids == {"1", "2"}


# ---------------------------------------------------------------------------
# update_task
# ---------------------------------------------------------------------------


def test_update_task_updates_title_and_status(dynamo_env):
    dynamo_env.put_item(
        Item={
            "task_id": "task-456",
            "title": "Old title",
            "status": "pending",
        }
    )

    mod = _load_handler("update_task")
    event = {
        "pathParameters": {"id": "task-456"},
        "body": json.dumps({"title": "New title", "status": "done"}),
    }
    response = mod.handler(event, None)

    assert response["statusCode"] == 200
    updated = json.loads(response["body"])
    assert updated["task_id"] == "task-456"
    assert updated["title"] == "New title"
    assert updated["status"] == "done"


def test_update_task_nonexistent_returns_404(dynamo_env):
    mod = _load_handler("update_task")
    event = {
        "pathParameters": {"id": "missing-id"},
        "body": json.dumps({"status": "done"}),
    }
    response = mod.handler(event, None)

    assert response["statusCode"] == 404
    assert "not found" in json.loads(response["body"])["message"]


def test_update_task_missing_updatable_fields_returns_400(dynamo_env):
    mod = _load_handler("update_task")
    event = {
        "pathParameters": {"id": "task-456"},
        "body": json.dumps({"other_field": "ignored"}),
    }
    response = mod.handler(event, None)

    assert response["statusCode"] == 400
    assert (
        "Provide at least 'title' or 'status'"
        in json.loads(response["body"])["message"]
    )


def test_update_task_invalid_json_returns_400(dynamo_env):
    mod = _load_handler("update_task")
    event = {
        "pathParameters": {"id": "task-456"},
        "body": "not-json",
    }
    response = mod.handler(event, None)

    assert response["statusCode"] == 400
    assert "Invalid JSON body" in json.loads(response["body"])["message"]


def test_update_task_missing_id_returns_400(dynamo_env):
    mod = _load_handler("update_task")
    event = {"pathParameters": {}, "body": json.dumps({"status": "done"})}
    response = mod.handler(event, None)

    assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# delete_task
# ---------------------------------------------------------------------------


def test_delete_task_removes_existing_item(dynamo_env):
    dynamo_env.put_item(
        Item={"task_id": "task-789", "title": "Remove me", "status": "pending"}
    )

    mod = _load_handler("delete_task")
    response = mod.handler({"pathParameters": {"id": "task-789"}}, None)

    assert response["statusCode"] == 204
    assert response["body"] == ""
    assert dynamo_env.get_item(Key={"task_id": "task-789"}).get("Item") is None


def test_delete_task_nonexistent_returns_404(dynamo_env):
    mod = _load_handler("delete_task")
    response = mod.handler({"pathParameters": {"id": "ghost-id"}}, None)

    assert response["statusCode"] == 404
    assert "not found" in json.loads(response["body"])["message"]


def test_delete_task_missing_id_returns_400(dynamo_env):
    mod = _load_handler("delete_task")
    response = mod.handler({"pathParameters": {}}, None)

    assert response["statusCode"] == 400
    assert "'id' path parameter is required" in json.loads(response["body"])["message"]
