from unittest.mock import MagicMock, Mock, patch

import psycopg2
import pytest

from aws_sam_testing.database import Database, DatabaseToolkit, PostgresDatabase


class TestDatabase:
    def test_database_is_abstract(self):
        with pytest.raises(TypeError):
            Database()

    def test_database_get_connection_string_not_implemented(self):
        class ConcreteDatabase(Database):
            def get_connection_string(self):
                return super().get_connection_string()

        db = ConcreteDatabase()
        with pytest.raises(NotImplementedError):
            db.get_connection_string()

    def test_database_wait_for_start_not_implemented(self):
        class ConcreteDatabase(Database):
            def get_connection_string(self):
                return "test"

        db = ConcreteDatabase()
        with pytest.raises(NotImplementedError):
            db.wait_for_start()


class TestPostgresDatabase:
    def test_initialization(self):
        db = PostgresDatabase()
        assert db._is_running is False
        assert db._container is None
        assert db._port is None

    def test_get_connection_string_without_start(self):
        db = PostgresDatabase()
        with pytest.raises(RuntimeError, match="Database not started"):
            db.get_connection_string()

    def test_get_connection_string_with_port(self):
        db = PostgresDatabase()
        db._port = 12345
        assert db.get_connection_string() == "postgresql://postgres:password@localhost:12345/postgres"
        assert db.get_connection_string("mydb") == "postgresql://postgres:password@localhost:12345/mydb"

    @patch("aws_sam_testing.database.PostgresDatabase._do_start")
    @patch("aws_sam_testing.database.PostgresDatabase.wait_for_start")
    def test_start_when_not_running(self, mock_wait, mock_do_start):
        db = PostgresDatabase()
        db.start()
        mock_do_start.assert_called_once()
        mock_wait.assert_called_once()
        assert db._is_running is True

    @patch("aws_sam_testing.database.PostgresDatabase._do_start")
    @patch("aws_sam_testing.database.PostgresDatabase.wait_for_start")
    def test_start_when_already_running(self, mock_wait, mock_do_start):
        db = PostgresDatabase()
        db._is_running = True
        db.start()
        mock_do_start.assert_not_called()
        mock_wait.assert_not_called()

    @patch("aws_sam_testing.database.PostgresDatabase._do_stop")
    def test_stop_when_running(self, mock_do_stop):
        db = PostgresDatabase()
        db._is_running = True
        db.stop()
        mock_do_stop.assert_called_once()
        assert db._is_running is False

    @patch("aws_sam_testing.database.PostgresDatabase._do_stop")
    def test_stop_when_not_running(self, mock_do_stop):
        db = PostgresDatabase()
        db.stop()
        mock_do_stop.assert_not_called()

    @patch("docker.from_env")
    @patch("aws_sam_testing.util.find_free_port")
    def test_do_start(self, mock_find_port, mock_docker_from_env):
        mock_find_port.return_value = 54321
        mock_container = Mock()
        mock_docker_client = Mock()
        mock_docker_client.containers.run.return_value = mock_container
        mock_docker_from_env.return_value = mock_docker_client

        db = PostgresDatabase()
        db._do_start()

        assert db._port == 54321
        assert db._container == mock_container
        mock_docker_client.containers.run.assert_called_once_with(
            "postgres:16",
            detach=True,
            ports={"5432/tcp": 54321},
            environment={"POSTGRES_PASSWORD": "password"},
        )

    def test_do_stop_with_container(self):
        mock_container = Mock()
        db = PostgresDatabase()
        db._container = mock_container

        db._do_stop()

        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()
        assert db._container is None

    def test_do_stop_without_container(self):
        db = PostgresDatabase()
        db._do_stop()  # Should not raise any exception

    @patch("psycopg2.connect")
    @patch("socket.create_connection")
    @patch("time.monotonic")
    @patch("time.sleep")
    def test_wait_for_start_success(self, mock_sleep, mock_monotonic, mock_create_connection, mock_psycopg_connect):
        mock_monotonic.side_effect = [0, 0.1, 0.2]
        mock_socket = Mock()
        mock_create_connection.return_value.__enter__ = Mock(return_value=mock_socket)
        mock_create_connection.return_value.__exit__ = Mock(return_value=None)
        mock_conn = Mock()
        mock_psycopg_connect.return_value = mock_conn

        db = PostgresDatabase()
        db._port = 5432
        db.wait_for_start()

        mock_create_connection.assert_called_once_with(("localhost", 5432), timeout=0.1)
        mock_psycopg_connect.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("psycopg2.connect")
    @patch("socket.create_connection")
    @patch("time.monotonic")
    @patch("time.sleep")
    def test_wait_for_start_retry(self, mock_sleep, mock_monotonic, mock_create_connection, mock_psycopg_connect):
        mock_monotonic.side_effect = [0, 0.1, 0.2, 0.3, 0.4]
        mock_create_connection.side_effect = [
            ConnectionRefusedError(),
            MagicMock(__enter__=Mock(), __exit__=Mock()),
        ]
        mock_psycopg_connect.side_effect = [psycopg2.OperationalError(), Mock(close=Mock())]

        db = PostgresDatabase()
        db._port = 5432
        db.wait_for_start()

        assert mock_create_connection.call_count == 2
        assert mock_psycopg_connect.call_count == 2
        assert mock_sleep.call_count == 2

    @patch("socket.create_connection")
    @patch("time.monotonic")
    @patch("time.sleep")
    def test_wait_for_start_timeout(self, mock_sleep, mock_monotonic, mock_create_connection):
        mock_monotonic.side_effect = [0, 30, 61]
        mock_create_connection.side_effect = ConnectionRefusedError()

        db = PostgresDatabase()
        db._port = 5432

        with pytest.raises(TimeoutError, match="Postgres container failed to start"):
            db.wait_for_start()

    def test_wait_for_start_no_port(self):
        db = PostgresDatabase()
        db.wait_for_start()  # Should return without doing anything

    @patch("aws_sam_testing.database.PostgresDatabase.start")
    @patch("aws_sam_testing.database.PostgresDatabase.stop")
    def test_context_manager_success(self, mock_stop, mock_start):
        with PostgresDatabase() as db:
            mock_start.assert_called_once()
            assert isinstance(db, PostgresDatabase)
        mock_stop.assert_called_once()

    @patch("aws_sam_testing.database.PostgresDatabase.start")
    @patch("aws_sam_testing.database.PostgresDatabase.stop")
    def test_context_manager_with_exception(self, mock_stop, mock_start):
        with pytest.raises(ValueError):
            with PostgresDatabase():
                mock_start.assert_called_once()
                raise ValueError("Test error")
        mock_stop.assert_called_once()

    def test_create_database_not_started(self):
        db = PostgresDatabase()
        with pytest.raises(RuntimeError, match="Database not started"):
            db.create_database("testdb")

    @patch("psycopg2.connect")
    def test_create_database_success(self, mock_connect):
        mock_cursor = Mock()
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = PostgresDatabase()
        db._is_running = True
        db._port = 5432
        db.create_database("testdb")

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5432,
            user="postgres",
            password="password",
            database="postgres",
        )
        assert mock_conn.autocommit is True
        mock_cursor.execute.assert_called_once()
        # Check that SQL was called with proper escaping
        call_args = mock_cursor.execute.call_args[0][0]
        assert "CREATE DATABASE" in str(call_args)
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("psycopg2.connect")
    def test_create_database_with_exception(self, mock_connect):
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = psycopg2.Error("Database already exists")
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = PostgresDatabase()
        db._is_running = True
        db._port = 5432

        with pytest.raises(psycopg2.Error):
            db.create_database("testdb")

        mock_conn.close.assert_called_once()


class TestDatabaseToolkit:
    def test_initialization(self):
        toolkit = DatabaseToolkit()
        assert toolkit is not None


@pytest.mark.slow
class TestPostgresDatabaseIntegration:
    def test_comprehensive_postgres_functionality(self):
        """Test all PostgresDatabase functionality in a single test to minimize container startup time."""
        psycopg2 = pytest.importorskip("psycopg2")

        # Test 1: Basic start/stop functionality
        db = PostgresDatabase()
        db.start()
        try:
            assert db._is_running is True
            assert db._port is not None
            assert db._container is not None
            conn_string = db.get_connection_string()
            assert conn_string.startswith("postgresql://postgres:password@localhost:")
            assert conn_string.endswith("/postgres")
        finally:
            db.stop()
            assert db._is_running is False
            assert db._container is None

        # Test 2: Context manager and psycopg2 operations
        with PostgresDatabase() as db:
            # Verify context manager works
            assert db._is_running is True
            assert db._port is not None
            assert db._container is not None

            # Test psycopg2 connection
            conn_string = db.get_connection_string()
            conn = psycopg2.connect(conn_string)
            try:
                cursor = conn.cursor()

                # Test basic query
                cursor.execute("SELECT version()")
                result = cursor.fetchone()
                assert result is not None
                assert "PostgreSQL" in result[0]

                # Test table creation and data operations
                cursor.execute("""
                    CREATE TABLE test_table (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100),
                        value INTEGER
                    )
                """)
                conn.commit()

                # Insert data
                cursor.execute("INSERT INTO test_table (name, value) VALUES (%s, %s)", ("test_name", 42))
                conn.commit()

                # Query data
                cursor.execute("SELECT name, value FROM test_table WHERE name = %s", ("test_name",))
                result = cursor.fetchone()
                assert result == ("test_name", 42)

                # Check count
                cursor.execute("SELECT COUNT(*) FROM test_table")
                count = cursor.fetchone()[0]
                assert count == 1

                # Test transaction rollback
                cursor.execute("""
                    CREATE TABLE test_rollback (
                        id SERIAL PRIMARY KEY,
                        data VARCHAR(50)
                    )
                """)
                conn.commit()

                # Insert and rollback
                cursor.execute("INSERT INTO test_rollback (data) VALUES (%s)", ("should_rollback",))
                conn.rollback()

                # Check that data was not inserted
                cursor.execute("SELECT COUNT(*) FROM test_rollback")
                count = cursor.fetchone()[0]
                assert count == 0

                cursor.close()
            finally:
                conn.close()

            # Test create_database functionality
            db.create_database("test_custom_db")

            # Connect to the new database
            custom_conn_string = db.get_connection_string("test_custom_db")
            custom_conn = psycopg2.connect(custom_conn_string)
            try:
                cursor = custom_conn.cursor()

                # Create a table in the new database
                cursor.execute("""
                    CREATE TABLE custom_table (
                        id SERIAL PRIMARY KEY,
                        data VARCHAR(100)
                    )
                """)
                custom_conn.commit()

                # Insert and query data
                cursor.execute("INSERT INTO custom_table (data) VALUES (%s)", ("custom_data",))
                custom_conn.commit()

                cursor.execute("SELECT data FROM custom_table")
                result = cursor.fetchone()
                assert result[0] == "custom_data"

                cursor.close()
            finally:
                custom_conn.close()

        # Test 3: Multiple databases with different ports
        db1 = PostgresDatabase()
        db2 = PostgresDatabase()
        try:
            db1.start()
            db2.start()
            assert db1._port != db2._port
            assert db1._container != db2._container
        finally:
            db1.stop()
            db2.stop()
