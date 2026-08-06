"""
Reusable CDK construct that wires together:
  API Gateway (REST API) -> Lambda functions -> DynamoDB table

Designed to be generic: pass in a table config and a list of routes,
each route mapped to its own Lambda handler with only the DynamoDB
permissions it actually needs (least privilege).
"""
from dataclasses import dataclass
from typing import Callable, List, Optional

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


@dataclass
class RouteConfig:
    """Describes a single API route and the Lambda that serves it."""

    method: str  # e.g. "GET", "POST", "PUT", "DELETE"
    path_part: Optional[str]  # e.g. "{id}" or None for the resource root
    handler_name: str  # e.g. "create_task" -> lambda/create_task/handler.py
    lambda_dir: str  # filesystem path to the handler's folder
    # Callable(table, function) -> None. Grants exactly the DynamoDB
    # permissions this function needs (e.g. table.grant_write_data).
    grant: Callable[[dynamodb.Table, _lambda.Function], None]


class ApiLambdaDynamoConstruct(Construct):
    """
    Provisions one DynamoDB table, one Lambda function per RouteConfig,
    and one API Gateway REST API wiring each route to its Lambda.

    This construct is intentionally generic — it doesn't know anything
    about "tasks" specifically. All domain-specific config (table name,
    partition key, routes, handlers) is passed in by the caller, so the
    same construct could be reused for a different resource entirely.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table_name: str,
        partition_key_name: str,
        resource_path: str,
        routes: List[RouteConfig],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- DynamoDB table ---
        self.table = dynamodb.Table(
            self,
            "Table",
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name=partition_key_name, type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # DESTROY is fine for a demo project; production would use RETAIN.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- API Gateway REST API ---
        self.api = apigateway.RestApi(
            self,
            "Api",
            rest_api_name=f"{construct_id}Api",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
        )

        collection_resource = self.api.root.add_resource(resource_path)
        item_resource = collection_resource.add_resource("{id}")

        # --- One Lambda per route, with scoped IAM permissions ---
        self.functions = {}
        for route in routes:
            fn = _lambda.Function(
                self,
                f"{route.handler_name.title().replace('_', '')}Fn",
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="handler.handler",
                code=_lambda.Code.from_asset(route.lambda_dir),
                timeout=Duration.seconds(10),
                memory_size=128,
                environment={"TABLE_NAME": self.table.table_name},
            )

            # Least privilege: each function only gets the DynamoDB
            # actions it actually performs (e.g. PutItem for create,
            # not DeleteItem). Defined per-route by the caller.
            route.grant(self.table, fn)

            target_resource = item_resource if route.path_part else collection_resource
            target_resource.add_method(
                route.method, apigateway.LambdaIntegration(fn)
            )

            self.functions[route.handler_name] = fn
