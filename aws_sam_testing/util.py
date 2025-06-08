import socket
from pathlib import Path


def find_free_port() -> int:
    """Find a free port on the system.

    Returns:
        int: The free port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def find_project_root(
    start_path: Path = Path.cwd(),
    template_name: str = "template.yaml",
) -> Path:
    """Find the project root directory.

    Args:
        start_path: The path to start searching from.
        template_name: The name of the template file to search for.

    Returns:
        Path: The project root directory.
    """

    if (start_path / template_name).exists():
        return start_path

    parent = start_path.parent
    if parent == start_path:  # Reached root directory
        raise FileNotFoundError(f"Could not find {template_name} in any parent directory")

    return find_project_root(parent, template_name)
