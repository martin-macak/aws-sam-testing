# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python library that provides testing and mocking utilities for AWS SAM (Serverless Application Model) CLI. The project builds abstractions around AWS SAM CLI functionality to facilitate local testing of SAM applications.

Key capabilities:
- Running SAM APIs locally for testing
- CloudFormation template processing and manipulation
- Programmatic SAM build automation
- Resource dependency tracking and circular reference detection

## Technology Stack

- **Python 3.13+**
- **uv** for dependency management
- **aws-sam-cli** (>=1.139.0) as core dependency
- **pytest** for testing
- **ruff** for linting and formatting
- **pyright** for type checking
- **moto** for AWS service mocking

## Key Commands

### Development Setup
```bash
make init  # Initialize development environment (removes old packages, syncs dependencies)
```

### Building
```bash
make build  # Build the package (runs init first)
uv build    # Direct build command
```

### Testing
```bash
make test       # Run all tests
uv run pytest tests/  # Direct pytest command
uv run pytest tests/test_specific.py  # Run specific test file
uv run pytest -k "test_name"  # Run specific test by name
```

### Code Quality
```bash
make format     # Format code with ruff
make pyright    # Run type checking
uv run ruff format  # Direct format command
uv run pyright      # Direct type check command
```

### Publishing
```bash
make publish  # Build and publish to PyPI
```

### Cleanup
```bash
make clean  # Remove all build artifacts, caches, and compiled files
```

## Architecture

### Core Components

1. **`aws_sam_testing/core.py`**
   - `CloudFormationTool`: Base class for CloudFormation operations
   - Template discovery and validation

2. **`aws_sam_testing/cfn.py`**
   - `CloudFormationTemplateProcessor`: Advanced template manipulation
   - Custom YAML tag support (!Ref, !GetAtt, !Sub, etc.)
   - Dependency tracking and resource removal
   - Circular reference detection

3. **`aws_sam_testing/aws_sam.py`**
   - `AWSSAMToolkit`: Main interface for SAM operations
   - `LocalApi`: Context manager for local API Gateway instances
   - SAM build automation via `sam_build()` method

4. **`aws_sam_testing/util.py`**
   - Utility functions (port management)

### Key Design Patterns

- Context managers for resource lifecycle (LocalApi)
- Inheritance hierarchy: CloudFormationTool → AWSSAMToolkit
- Direct integration with SAM CLI internals (samcli.commands.*)
- Recursive dependency resolution for CloudFormation resources

## Development Notes

- **Dynamic versioning**: Version is derived from git tags via `uv-dynamic-versioning`
- **Line length**: Ruff configured for 200 characters
- **Type annotations**: Required for all public methods
- **Docstrings**: Use Google style docstrings
- **Test isolation**: Tests use temporary directories and cleanup
- **Warning suppression**: `datetime.utcnow()` deprecation warnings filtered in pytest

## Working with the Codebase

### Adding New Features
1. New CloudFormation operations belong in `cfn.py`
2. SAM-specific functionality goes in `aws_sam.py`
3. Always add corresponding tests
4. Run `make format` and `make pyright` before committing

### Testing Guidelines
- Tests directly interact with SAM CLI internals
- Use pytest fixtures for common setup
- Test both success and failure paths
- Validate CloudFormation template manipulations

### Common Tasks

**Running a local API for testing:**
```python
from aws_sam_testing import AWSSAMToolkit

toolkit = AWSSAMToolkit()
with toolkit.local_api() as api:
    # api.url contains the local API endpoint
    pass
```

**Processing CloudFormation templates:**
```python
from aws_sam_testing.cfn import CloudFormationTemplateProcessor

processor = CloudFormationTemplateProcessor("template.yaml")
processor.remove_resource("MyResource")
processor.save()
```