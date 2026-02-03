import os
import clickhouse_connect
import pandas as pd


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


CLICKHOUSE_HOST = _env("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_HTTP_PORT = int(_env("CLICKHOUSE_HTTP_PORT", "8123"))
CLICKHOUSE_DATABASE = _env("CLICKHOUSE_DATABASE", "airline_data")
CLICKHOUSE_USER = _env("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = _env("CLICKHOUSE_PASSWORD", "")


def get_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_HTTP_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


def query_df(sql: str, parameters: dict | None = None) -> pd.DataFrame:
    client = get_client()
    return client.query_df(sql, parameters=parameters)
