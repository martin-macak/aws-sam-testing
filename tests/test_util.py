import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aws_sam_testing.util import find_free_port, find_project_root


class TestFindFreePort:
    """Test find_free_port function."""

    def test_returns_valid_port(self):
        """Test that find_free_port returns a valid port number."""
        port = find_free_port()
        assert isinstance(port, int)
        assert 1 <= port <= 65535

    def test_returned_port_is_free(self):
        """Test that the returned port is actually free."""
        port = find_free_port()

        # Try to bind to the returned port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                # If we can bind, the port is free
                assert True
            except OSError:
                # Port is already in use, which shouldn't happen
                pytest.fail(f"Port {port} returned by find_free_port is already in use")

    def test_different_ports_on_multiple_calls(self):
        """Test that multiple calls return different ports."""
        ports = [find_free_port() for _ in range(5)]
        # While not guaranteed, it's highly likely we get different ports
        assert len(set(ports)) > 1

    @patch("socket.socket")
    def test_socket_mock(self, mock_socket_class):
        """Test with mocked socket to ensure proper usage."""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        mock_socket.getsockname.return_value = ("127.0.0.1", 12345)

        port = find_free_port()

        assert port == 12345
        mock_socket.bind.assert_called_once_with(("", 0))
        mock_socket.getsockname.assert_called_once()


class TestFindProjectRoot:
    """Test find_project_root function."""

    def test_finds_template_in_current_directory(self, tmp_path):
        """Test finding template in the current directory."""
        template_file = tmp_path / "template.yaml"
        template_file.write_text("test")

        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_finds_template_in_parent_directory(self, tmp_path):
        """Test finding template in a parent directory."""
        template_file = tmp_path / "template.yaml"
        template_file.write_text("test")

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = find_project_root(subdir)
        assert result == tmp_path

    def test_finds_template_multiple_levels_up(self, tmp_path):
        """Test finding template multiple directory levels up."""
        template_file = tmp_path / "template.yaml"
        template_file.write_text("test")

        deep_dir = tmp_path / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)

        result = find_project_root(deep_dir)
        assert result == tmp_path

    def test_custom_template_name(self, tmp_path):
        """Test finding a custom template name."""
        custom_template = tmp_path / "custom.yaml"
        custom_template.write_text("test")

        result = find_project_root(tmp_path, template_name="custom.yaml")
        assert result == tmp_path

    def test_raises_when_template_not_found(self, tmp_path):
        """Test that FileNotFoundError is raised when template is not found."""
        # Create a directory without template.yaml
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with pytest.raises(FileNotFoundError) as exc_info:
            find_project_root(subdir)

        assert "Could not find template.yaml in any parent directory" in str(exc_info.value)

    def test_raises_with_custom_template_name(self, tmp_path):
        """Test error message includes custom template name."""
        with pytest.raises(FileNotFoundError) as exc_info:
            find_project_root(tmp_path, template_name="custom.yaml")

        assert "Could not find custom.yaml in any parent directory" in str(exc_info.value)

    def test_stops_at_root_directory(self):
        """Test that search stops at filesystem root."""
        # Use root directory which definitely won't have template.yaml
        with pytest.raises(FileNotFoundError):
            find_project_root(Path("/"))

    def test_with_pathlib_path_object(self, tmp_path):
        """Test that function works with Path objects."""
        template_file = tmp_path / "template.yaml"
        template_file.write_text("test")

        result = find_project_root(Path(tmp_path))
        assert result == tmp_path
        assert isinstance(result, Path)

    def test_preserves_path_type(self, tmp_path):
        """Test that return type matches input type."""
        template_file = tmp_path / "template.yaml"
        template_file.write_text("test")

        result = find_project_root(tmp_path)
        assert type(result) is type(tmp_path)
