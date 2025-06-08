"""Core utilities for CloudFormation template handling.

This module provides the base functionality for working with CloudFormation
and SAM templates, including template loading, validation, and parsing.
"""

import os
from pathlib import Path
from typing import Any, Optional, Union


class CloudFormationTool:
    """Base class for CloudFormation template operations.

    This class provides core functionality for working with CloudFormation templates,
    including template discovery, loading, and validation. It serves as the foundation
    for more specialized tools like AWSSAMToolkit.

    Attributes:
        working_dir: The working directory for CloudFormation operations. Defaults to
            the current working directory if not specified.
        template_path: Path to the CloudFormation template file. Defaults to
            'template.yaml' in the working directory if not specified.

    Raises:
        FileNotFoundError: If the specified template file does not exist.

    Example:
        >>> tool = CloudFormationTool(working_dir="/my/project")
        >>> print(tool.template_path)
        /my/project/template.yaml
    """

    def __init__(
        self,
        working_dir: Optional[Union[str, Path]] = None,
        template_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize the CloudFormation tool.

        Args:
            working_dir: The working directory for operations. If None, uses the
                current working directory. Can be either a string path or Path object.
            template_path: Path to the CloudFormation template file. If None,
                defaults to 'template.yaml' in the working directory. Can be either
                a string path or Path object.

        Raises:
            FileNotFoundError: If the template file does not exist at the specified
                or default location.
        """
        if not working_dir:
            working_dir = Path(os.getcwd()).absolute()
        elif not isinstance(working_dir, Path):
            working_dir = Path(working_dir)

        self.working_dir: Path = working_dir

        if not template_path:
            template_path = Path.absolute(self.working_dir) / "template.yaml"
        elif not isinstance(template_path, Path):
            template_path = Path(template_path)

        self.template_path: Path = template_path

        if not self.template_path.exists():
            raise FileNotFoundError(f"Template file not found at {self.template_path}")

        self.template = _load_template(self.template_path)


def _load_template(template_path: str | Path) -> dict[str, Any]:
    """Load a CloudFormation template from a file.

    Args:
        template_path (str | Path): Path to the CloudFormation template file.

    Raises:
        FileNotFoundError: If the template file does not exist.

    Returns:
        dict[str, Any]: The loaded template.
    """

    if isinstance(template_path, str):
        template_path = Path(template_path)

    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found at {template_path}")

    from aws_sam_testing.cfn import load_yaml

    return load_yaml(template_path.read_text())
