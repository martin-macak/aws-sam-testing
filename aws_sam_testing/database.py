from abc import ABC, abstractmethod
from typing import Any


class Database(ABC):
    def __init__(
        self,
    ):
        pass

    @abstractmethod
    def get_connection_string(self, database_name: str | None = None) -> str:
        raise NotImplementedError

    def wait_for_start(self) -> None:
        raise NotImplementedError


class PostgresDatabase(Database):
    def __init__(
        self,
    ):
        super().__init__()
        self._is_running = False
        self._container: Any | None = None  # docker.models.containers.Container
        self._port: int | None = None

    def __enter__(self) -> "PostgresDatabase":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def start(self) -> None:
        if self._is_running:
            return
        self._do_start()
        self.wait_for_start()
        self._is_running = True

    def stop(self) -> None:
        if not self._is_running:
            return
        self._do_stop()
        self._is_running = False

    def _do_start(self) -> None:
        import docker

        from aws_sam_testing.util import find_free_port

        self._port = find_free_port()
        docker_client = docker.from_env()

        container = docker_client.containers.run(
            "postgres:16",
            detach=True,
            ports={"5432/tcp": self._port},
            environment={"POSTGRES_PASSWORD": "password"},
        )
        self._container = container

    def _do_stop(self) -> None:
        if self._container is None:
            return
        self._container.stop()
        self._container.remove()
        self._container = None

    def wait_for_start(self) -> None:
        if not self._port:
            return

        # First wait for port to be accessible
        import socket
        import time

        start_time = time.monotonic()
        while time.monotonic() - start_time < 60:
            try:
                with socket.create_connection(("localhost", self._port), timeout=0.1):
                    break
            except (socket.timeout, ConnectionRefusedError):
                time.sleep(0.1)
        else:
            raise TimeoutError("Postgres container failed to start")

        # Then wait for PostgreSQL to be ready to accept connections
        import psycopg2

        while time.monotonic() - start_time < 60:
            try:
                conn = psycopg2.connect(
                    host="localhost",
                    port=self._port,
                    user="postgres",
                    password="password",
                    database="postgres",
                    connect_timeout=1,
                )
                conn.close()
                return
            except psycopg2.OperationalError:
                time.sleep(0.1)
        raise TimeoutError("Postgres is not ready to accept connections")

    def get_connection_string(
        self,
        database_name: str | None = None,
    ) -> str:
        if not self._port:
            raise RuntimeError("Database not started")
        db_name = database_name or "postgres"
        return f"postgresql://postgres:password@localhost:{self._port}/{db_name}"

    def create_database(self, database_name: str) -> None:
        if not self._is_running:
            raise RuntimeError("Database not started")

        import psycopg2
        from psycopg2 import sql

        # Connect to the default postgres database to create the new database
        conn = psycopg2.connect(
            host="localhost",
            port=self._port,
            user="postgres",
            password="password",
            database="postgres",
        )
        conn.autocommit = True  # Required for CREATE DATABASE

        try:
            cursor = conn.cursor()
            # Use sql.Identifier to safely escape the database name
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
            cursor.close()
        finally:
            conn.close()


class DatabaseToolkit:
    def __init__(self):
        pass
