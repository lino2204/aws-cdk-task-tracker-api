#!/usr/bin/env python3
"""CDK app entrypoint — instantiates the TaskApiStack."""
import aws_cdk as cdk

from infra.task_api_stack import TaskApiStack

app = cdk.App()

TaskApiStack(
    app,
    "TaskApiStack",
    description="Serverless CRUD task tracker API (API Gateway + Lambda + DynamoDB)",
    # env=cdk.Environment(account="<ACCOUNT_ID>", region="us-east-1"),
)

app.synth()
