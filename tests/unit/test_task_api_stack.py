"""
Unit tests for TaskApiStack.

These tests synthesize the CDK stack into a CloudFormation template
(in memory, no AWS calls) and assert on its structure — resource
counts, key configuration, and IAM policy scoping. This lets us
catch infrastructure mistakes (e.g. an overly broad IAM policy)
before ever running `cdk deploy`.
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from infra.task_api_stack import TaskApiStack


@pytest.fixture(scope="module")
def template():
    """Synthesize the stack once and reuse the resulting template across tests."""
    app = cdk.App()
    stack = TaskApiStack(app, "TestTaskApiStack")
    return Template.from_stack(stack)


def test_dynamodb_table_created_with_correct_key(template):
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "KeySchema": [
                {"AttributeName": "task_id", "KeyType": "HASH"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )


def test_five_lambda_functions_created(template):
    # 5 CRUD handlers. (API Gateway's account-level CloudWatch role
    # setup can add extra Lambda-adjacent resources in some CDK
    # versions, so we assert "at least 5" via a resource properties
    # check instead of a strict count if that ever becomes flaky.)
    template.resource_count_is("AWS::Lambda::Function", 5)


def test_lambda_functions_use_python312_runtime(template):
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "handler.handler",
        },
    )


def test_api_gateway_rest_api_created(template):
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)


def test_expected_http_methods_present(template):
    # Collection-level: POST /tasks, GET /tasks
    template.has_resource_properties(
        "AWS::ApiGateway::Method", {"HttpMethod": "POST"}
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Method", {"HttpMethod": "GET"}
    )
    # Item-level: PUT /tasks/{id}, DELETE /tasks/{id}
    template.has_resource_properties(
        "AWS::ApiGateway::Method", {"HttpMethod": "PUT"}
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Method", {"HttpMethod": "DELETE"}
    )


def test_delete_task_policy_is_scoped_not_wildcard(template):
    """
    The core least-privilege assertion: the delete_task function's IAM
    policy should grant exactly dynamodb:DeleteItem, and must NOT
    contain a wildcard ("dynamodb:*") or unrelated write actions like
    PutItem. This is the test that would fail if someone "simplified"
    the code later by swapping in table.grant_write_data() for delete.
    """
    policies = template.find_resources("AWS::IAM::Policy")

    delete_policy_found = False
    for policy_id, policy in policies.items():
        if "DeleteTaskFn" not in policy_id:
            continue
        statements = (
            policy["Properties"]["PolicyDocument"]["Statement"]
        )
        for statement in statements:
            actions = statement.get("Action")
            if actions is None:
                continue
            # Action can be a single string or a list
            actions_list = actions if isinstance(actions, list) else [actions]

            if "dynamodb:DeleteItem" in actions_list:
                delete_policy_found = True
                # Must NOT be a wildcard grant
                assert "dynamodb:*" not in actions_list
                # Must NOT also carry write actions this function doesn't need
                assert "dynamodb:PutItem" not in actions_list

    assert delete_policy_found, "Expected a policy statement granting dynamodb:DeleteItem"


@pytest.mark.parametrize(
    "fn_logical_prefix,expected_action",
    [
        ("CreateTaskFn", "dynamodb:PutItem"),
        ("ListTasksFn", "dynamodb:Scan"),
        ("GetTaskFn", "dynamodb:GetItem"),
        ("UpdateTaskFn", "dynamodb:UpdateItem"),
        ("DeleteTaskFn", "dynamodb:DeleteItem"),
    ],
)
def test_each_lambda_policy_grants_exact_dynamodb_action(
    template, fn_logical_prefix, expected_action
):
    """
    Verify action-level least privilege across all 5 CRUD functions:
    each Lambda's IAM policy must grant ONLY the single DynamoDB action
    it actually calls.
    """
    policies = template.find_resources("AWS::IAM::Policy")

    matched_actions = []
    for policy_id, policy in policies.items():
        if fn_logical_prefix not in policy_id:
            continue
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        for statement in statements:
            actions = statement.get("Action")
            if actions is None:
                continue
            actions_list = actions if isinstance(actions, list) else [actions]
            matched_actions.extend(actions_list)

    assert matched_actions == [expected_action]


def test_no_iam_policy_uses_wildcard_dynamodb_actions(template):
    """
    Broader safety net: across ALL IAM policies in the stack, none
    should grant a blanket 'dynamodb:*' action.
    """
    policies = template.find_resources("AWS::IAM::Policy")

    for _, policy in policies.items():
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        for statement in statements:
            actions = statement.get("Action")
            if actions is None:
                continue
            actions_list = actions if isinstance(actions, list) else [actions]
            assert "dynamodb:*" not in actions_list


def test_stack_has_expected_outputs(template):
    template.has_output("ApiUrl", {})
    template.has_output("TableName", {})
