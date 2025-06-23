import psycopg2


def migrate_database(connection: psycopg2.extensions.connection):
    with connection.cursor() as cursor:
        cursor.execute("SET search_path TO app")
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255))")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS app")
