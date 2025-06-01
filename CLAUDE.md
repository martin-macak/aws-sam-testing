# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project called `sam-mocks` that appears to be building testing/mocking utilities for AWS SAM (Serverless Application Model) CLI. The project uses:
- Python 3.13+
- `uv` for dependency management and virtual environment handling
- `aws-sam-cli` as a core dependency
- `pytest` for testing
- `ruff` for linting and formatting
- `pyright` for type checking

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

The project structure follows a standard Python package layout:

- **sam_mocks/**: Main package directory
  - `aws_sam.py`: Contains `AWSSAMToolkit` class for managing SAM local API operations
  - `core.py`: Contains `CloudFormationTool` class for handling CloudFormation templates
  
- **tests/**: Test directory using pytest
  - Tests directly interact with AWS SAM CLI internals (e.g., `samcli.commands.build.build_context`)

The codebase appears to be building abstractions around AWS SAM CLI functionality, providing context managers and utilities for testing SAM applications locally.

## Development Notes

- The project uses dynamic versioning from git tags via `uv-dynamic-versioning`
- Ruff is configured with line length of 200 and targets Python 3.10+
- The Makefile's `init` command specifically removes existing package installations before syncing, ensuring clean installs
- Test warnings about deprecated `datetime.utcnow()` are suppressed in pytest configuration

## Style Guidelines

- Use Google style docstrings
- Always use type annotations
- Always document class and instance variables