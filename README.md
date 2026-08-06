# AWS CDK Task Tracker API

A serverless CRUD API for managing tasks, built with **AWS CDK (Python)**.
Demonstrates infrastructure-as-code best practices: reusable CDK constructs,
least-privilege IAM, automated infrastructure testing, and linting.

## Architecture

```
Client → API Gateway → Lambda (per operation) → DynamoDB
```

![Architecture Diagram](docs/architecture.png)

**Stack:**
- **Amazon API Gateway** — REST API entry point
- **AWS Lambda** — one function per CRUD operation (Python 3.12)
- **Amazon DynamoDB** — single-table storage for tasks
- **AWS CDK (Python)** — infrastructure defined as code, deployed via CloudFormation

## Why this project

This repo is a hands-on demonstration of:
- Writing **reusable CDK constructs** (not one flat stack) — see
  [`infra/constructs/api_lambda_dynamo_construct.py`](infra/constructs/api_lambda_dynamo_construct.py)
- **Least-privilege IAM** — each Lambda gets only the DynamoDB actions it needs
  (e.g. the `get_task` function can `GetItem` but not `DeleteItem`)
- **Infrastructure testing** with `pytest` and `aws_cdk.assertions`, asserting
  against the synthesized CloudFormation template
- Clean, linted Python (`flake8`) across both infra and Lambda code

## Project structure

```
.
├── app.py                          # CDK app entrypoint
├── infra/
│   ├── task_api_stack.py           # Top-level stack, wires constructs together
│   └── constructs/
│       └── api_lambda_dynamo_construct.py   # Reusable API+Lambda+DynamoDB construct
├── lambda/
│   ├── create_task/handler.py
│   ├── get_task/handler.py
│   ├── list_tasks/handler.py
│   ├── update_task/handler.py
│   └── delete_task/handler.py
├── tests/
│   ├── unit/                       # CDK template assertions
│   └── integration/                # Optional: tests against a deployed API
└── docs/
    └── architecture.png
```

## API endpoints

| Method | Path              | Description          |
|--------|-------------------|-----------------------|
| POST   | `/tasks`           | Create a task         |
| GET    | `/tasks`           | List all tasks        |
| GET    | `/tasks/{id}`      | Get a single task     |
| PUT    | `/tasks/{id}`      | Update a task         |
| DELETE | `/tasks/{id}`      | Delete a task         |

### Task item shape
```json
{
  "task_id": "uuid",
  "title": "string",
  "status": "pending | done",
  "created_at": "ISO-8601 timestamp"
}
```

## Prerequisites

- Python 3.12+
- Node.js 18+ (required by the CDK CLI)
- AWS CLI configured with credentials (`aws configure`)
- AWS CDK CLI: `npm install -g aws-cdk`

## Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/aws-cdk-task-tracker-api.git
cd aws-cdk-task-tracker-api

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Bootstrap your AWS environment (only needed once per account/region)
cdk bootstrap
```

## Useful commands

| Command                | Purpose                                              |
|-------------------------|-------------------------------------------------------|
| `cdk synth`             | Synthesize the CloudFormation template               |
| `cdk diff`               | Compare deployed stack with local changes            |
| `cdk deploy`            | Deploy the stack to AWS                               |
| `cdk destroy`           | Tear down all deployed resources                      |
| `pytest`                | Run unit tests                                        |
| `pytest --cov`          | Run tests with coverage report                        |
| `flake8 .`               | Lint infra and Lambda code                            |

## Testing

Infrastructure is tested by asserting against the **synthesized CloudFormation
template**, not by deploying — this makes tests fast and safe to run in CI.

```bash
pytest tests/unit -v
```

Example of what's covered:
- DynamoDB table has the correct partition key and billing mode
- Each Lambda function has an IAM role scoped to only the actions it needs
  (no wildcard `dynamodb:*` permissions)
- API Gateway routes are wired to the correct Lambda integrations

## Deployment

```bash
cdk deploy
```

After deployment, the API Gateway invoke URL will be printed as a stack output.

To remove all resources:
```bash
cdk destroy
```

## Design notes

- **One construct, reused** — `ApiLambdaDynamoConstruct` takes the DynamoDB
  table config and a dict of route → Lambda handler mappings as props, so it
  isn't hardcoded to this specific task-tracker API and could be reused for a
  different resource with different routes.
- **Least privilege IAM** — rather than granting each Lambda broad
  `dynamodb:*` access, each function is granted only the specific actions it
  performs (e.g. `create_task` gets `PutItem`, not `DeleteItem`).
- **Removal policy** — the DynamoDB table uses `RemovalPolicy.DESTROY` for
  easy teardown in this demo project; in production this would typically be
  `RETAIN`.

## License

MIT
