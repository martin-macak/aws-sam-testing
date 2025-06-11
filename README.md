# AWS SAM Testing

[![CI](https://github.com/martin-macak/aws-sam-testing/actions/workflows/ci.yml/badge.svg)](https://github.com/martin-macak/aws-sam-testing/actions/workflows/ci.yml)
[![Test Build](https://github.com/martin-macak/aws-sam-testing/actions/workflows/test-build.yml/badge.svg)](https://github.com/martin-macak/aws-sam-testing/actions/workflows/test-build.yml)
[![PyPI version](https://badge.fury.io/py/aws-sam-testing.svg)](https://badge.fury.io/py/aws-sam-testing)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

A Python library that provides testing and mocking utilities for AWS SAM (Serverless Application Model) applications. This library builds abstractions around AWS SAM CLI functionality to facilitate local testing of SAM applications with proper AWS resource mocking and isolation.

## Features

- **Local API Gateway Testing**: Run SAM APIs locally for integration testing
- **CloudFormation Template Processing**: Advanced template manipulation and validation
- **AWS Resource Mocking**: Seamless integration with moto for AWS service mocking
- **Pytest Integration**: Built-in pytest fixtures for AWS contexts and resources
- **Dependency Management**: Automatic CloudFormation resource dependency tracking
- **SAM Build Automation**: Programmatic SAM build operations

## Installation

```bash
pip install aws-sam-testing
```

## Requirements

- Python 3.13+
- AWS SAM CLI (>=1.139.0)
- AWS SAM Translator (>=1.97.0)

## Quick Start

### Basic Usage

```python
from aws_sam_testing import AWSSAMToolkit

# Initialize the toolkit
toolkit = AWSSAMToolkit()

# Run a local API for testing
with toolkit.local_api() as api:
    # api.url contains the local API endpoint
    response = requests.get(f"{api.url}/hello")
    assert response.status_code == 200
```

### CloudFormation Template Processing

```python
from aws_sam_testing.cfn import CloudFormationTemplateProcessor

# Load and manipulate CloudFormation templates
processor = CloudFormationTemplateProcessor("template.yaml")
processor.remove_resource("MyResource")
processor.save()
```

### Pytest Integration

The library provides several pytest fixtures that automatically handle AWS resource mocking and Lambda context creation:

```python
def test_lambda_handler(mock_aws_lambda_context, mock_aws_resources):
    from my_app.app import lambda_handler
    
    # Set environment variables for Lambda function
    with mock_aws_resources.set_environment(lambda_function_logical_name="MyFunction"):
        result = lambda_handler(
            {"httpMethod": "GET", "path": "/hello"},
            mock_aws_lambda_context
        )
        
        assert result["statusCode"] == 200
        
        # Access mocked AWS resources
        table = mock_aws_resources.get_resource("MyDynamoDBTable")
        items = table.scan()["Items"]
        assert len(items) == 1
```

## Available Pytest Fixtures

The library automatically registers the following pytest fixtures:

- `mock_aws_lambda_context`: Provides a mock AWS Lambda context object
- `mock_aws_resources`: Manages mocked AWS resources based on your CloudFormation template
- `aws_context`: General AWS context management

## Architecture

### Core Components

- **`AWSSAMToolkit`**: Main interface for SAM operations and local API management
- **`CloudFormationTemplateProcessor`**: Advanced CloudFormation template manipulation with support for intrinsic functions (!Ref, !GetAtt, !Sub, etc.)
- **`AWSResourceManager`**: Manages AWS resource lifecycle and mocking
- **`LocalApi`**: Context manager for local API Gateway instances

### Design Patterns

- Context managers for resource lifecycle management
- Direct integration with SAM CLI internals
- Recursive dependency resolution for CloudFormation resources
- Automatic cleanup and isolation

## Examples

### Testing with DynamoDB and SQS

```python
def test_api_with_resources(mock_aws_lambda_context, mock_aws_resources):
    from api_handler.app import lambda_handler
    
    with mock_aws_resources.set_environment(lambda_function_logical_name="ApiHandler"):
        response = lambda_handler(
            {
                "path": "/items",
                "httpMethod": "POST",
                "requestContext": {
                    "resourcePath": "/items",
                    "httpMethod": "POST",
                },
            },
            mock_aws_lambda_context,
        )
        
        assert response["statusCode"] == 200
        
        # Verify SQS message was sent
        queue = mock_aws_resources.get_resource("MySQSQueue")
        messages = queue.receive_messages()
        assert len(messages) == 1
        
        # Verify DynamoDB item was created
        table = mock_aws_resources.get_resource("MyDynamoDBTable")
        items = table.scan()["Items"]
        assert len(items) == 1
```

### Running Local API Tests

```python
import requests
from aws_sam_testing import AWSSAMToolkit

def test_local_api():
    toolkit = AWSSAMToolkit()
    
    with toolkit.local_api(port=3000) as api:
        # Test GET endpoint
        response = requests.get(f"{api.url}/hello")
        assert response.status_code == 200
        assert response.json()["message"] == "Hello, World!"
        
        # Test POST endpoint
        response = requests.post(f"{api.url}/items")
        assert response.status_code == 200
```

## Configuration

The library uses your CloudFormation template (typically `template.yaml`) to understand your AWS resources and automatically configure mocking. No additional configuration is required in most cases.

### Template Structure

Your SAM template should follow standard CloudFormation/SAM syntax:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world/
      Handler: app.lambda_handler
      Runtime: python3.13
      Environment:
        Variables:
          TABLE_NAME: !Ref MyDynamoDBTable
          QUEUE_NAME: !Ref MySQSQueue
      Events:
        HelloWorld:
          Type: Api
          Properties:
            Path: /hello
            Method: get

  MyDynamoDBTable:
    Type: AWS::DynamoDB::Table
    Properties:
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

  MySQSQueue:
    Type: AWS::SQS::Queue
```

## Testing Best Practices

1. **Use Fixtures**: Leverage the provided pytest fixtures for consistent test setup
2. **Environment Variables**: Use `set_environment()` to properly configure Lambda environment variables
3. **Resource Access**: Access mocked AWS resources through `mock_aws_resources.get_resource()`
4. **Isolation**: Each test runs with isolated AWS resources
5. **Cleanup**: Resources are automatically cleaned up after each test

## Contributing

1. Clone the repository
2. Install dependencies: `make init`
3. Run tests: `make test`
4. Format code: `make format`
5. Type check: `make pyright`

## License

This project is licensed under the MIT License.