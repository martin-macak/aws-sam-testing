import socket
from contextlib import contextmanager
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


@contextmanager
def set_environment(
    **kwargs,
):
    """Set environment variables for the duration of the context.

    Args:
        **kwargs: The environment variables to set.

    Returns:
        Generator[None, None, None]: A generator that yields the context.
    """
    import os

    current_environment = os.environ.copy()
    new_environment = {
        **current_environment,
        **kwargs,
    }
    old_environment = current_environment.copy()

    try:
        os.environ.update(new_environment)
        yield
    finally:
        # iterate over current os.environ and remove keys that are not present in old_environment
        for key in os.environ:
            if key not in old_environment:
                os.environ.pop(key)
        os.environ.update(old_environment)
