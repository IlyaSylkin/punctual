import os

import clickhouse_connect
import pytest
from clickhouse_connect.driver.client import Client
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def ch() -> Client:
    """Подключение к ClickHouse, поднятому через docker compose."""
    return clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "punctual"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        database=os.environ.get("CLICKHOUSE_DB", "punctual"),
    )
