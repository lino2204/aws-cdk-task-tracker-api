"""
Top-level CDK stack for the Task Tracker API.

Wires the reusable ApiLambdaDynamoConstruct with the specific routes,
Lambda handlers, and IAM grants for the "tasks" resource. All
domain-specific config lives here; the construct itself stays generic.
"""
import os

from aws_cdk import CfnOutput, Stack
from constructs import Construct

from infra.constructs.api_lambda_dynamo_construct import (
    ApiLambdaDynamoConstruct,
    RouteConfig,
)

LAMBDA_ROOT = os.path.join(os.path.dirname(__file__), "..", "lambda")


class TaskApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        routes = [
            # POST /tasks -> create_task
            # Only needs PutItem to insert a new task.
            RouteConfig(
                method="POST",
                path_part=None,  # collection-level route: /tasks
                handler_name="create_task",
                lambda_dir=os.path.join(LAMBDA_ROOT, "create_task"),
                grant=lambda table, fn: table.grant(fn, "dynamodb:PutItem"),
            ),
            # GET /tasks -> list_tasks
            # Only needs Scan to list tasks in the table.
            RouteConfig(
                method="GET",
                path_part=None,  # collection-level route: /tasks
                handler_name="list_tasks",
                lambda_dir=os.path.join(LAMBDA_ROOT, "list_tasks"),
                grant=lambda table, fn: table.grant(fn, "dynamodb:Scan"),
            ),
            # GET /tasks/{id} -> get_task
            # Only needs GetItem to fetch a single task by key.
            RouteConfig(
                method="GET",
                path_part="id",  # item-level route: /tasks/{id}
                handler_name="get_task",
                lambda_dir=os.path.join(LAMBDA_ROOT, "get_task"),
                grant=lambda table, fn: table.grant(fn, "dynamodb:GetItem"),
            ),
            # PUT /tasks/{id} -> update_task
            # Only needs UpdateItem (which evaluates ConditionExpression and
            # returns ALL_NEW attributes within the single UpdateItem call).
            RouteConfig(
                method="PUT",
                path_part="id",  # item-level route: /tasks/{id}
                handler_name="update_task",
                lambda_dir=os.path.join(LAMBDA_ROOT, "update_task"),
                grant=lambda table, fn: table.grant(fn, "dynamodb:UpdateItem"),
            ),
            # DELETE /tasks/{id} -> delete_task
            # Only needs DeleteItem to remove a task by key.
            RouteConfig(
                method="DELETE",
                path_part="id",  # item-level route: /tasks/{id}
                handler_name="delete_task",
                lambda_dir=os.path.join(LAMBDA_ROOT, "delete_task"),
                grant=lambda table, fn: table.grant(fn, "dynamodb:DeleteItem"),
            ),
        ]

        self.task_api = ApiLambdaDynamoConstruct(
            self,
            "TaskApi",
            table_name="tasks",
            partition_key_name="task_id",
            resource_path="tasks",
            routes=routes,
        )

        CfnOutput(
            self,
            "ApiUrl",
            value=self.task_api.api.url,
            description="Base URL of the Task Tracker API",
        )
        CfnOutput(
            self,
            "TableName",
            value=self.task_api.table.table_name,
            description="Name of the DynamoDB tasks table",
        )
