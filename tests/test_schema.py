"""Схема ClickHouse: миграции применены и соответствуют docs/data-model.md."""

from datetime import date, datetime

import pytest
from clickhouse_connect.driver.client import Client

TABLES = {
    "prediction_changes": "MergeTree",
    "arrivals": "MergeTree",
    "errors": "ReplacingMergeTree",
    "positions": "MergeTree",
}

# таблицы с ограниченным сроком хранения — политика в docs/data-model.md
WITH_TTL = {"prediction_changes", "positions"}


@pytest.fixture(scope="session")
def tables(ch: Client) -> dict[str, tuple[str, str, str]]:
    rows = ch.query(
        "SELECT name, engine, partition_key, create_table_query "
        "FROM system.tables WHERE database = currentDatabase()"
    ).result_rows
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def test_все_таблицы_созданы(tables: dict[str, tuple[str, str, str]]) -> None:
    assert TABLES.keys() <= tables.keys()


@pytest.mark.parametrize(("name", "engine"), TABLES.items())
def test_движок(tables: dict[str, tuple[str, str, str]], name: str, engine: str) -> None:
    assert tables[name][0] == engine


@pytest.mark.parametrize("name", TABLES)
def test_партиционирование_задано(tables: dict[str, tuple[str, str, str]], name: str) -> None:
    assert tables[name][1] != ""


@pytest.mark.parametrize("name", TABLES)
def test_ttl(tables: dict[str, tuple[str, str, str]], name: str) -> None:
    есть_ttl = "TTL " in tables[name][2]
    assert есть_ttl is (name in WITH_TTL)


def test_запись_и_чтение(ch: Client) -> None:
    """Вставка проходит и читается обратно — типы колонок совместимы."""
    строка = [
        "test",
        "550",
        0,
        date(2026, 1, 1),
        "12:00:00",
        "1234",
        datetime(2026, 1, 1, 12, 1),
        datetime(2026, 1, 1, 12, 2),
        "feed",
    ]
    ch.insert(
        "arrivals",
        [строка],
        column_names=[
            "city",
            "route_id",
            "direction_id",
            "start_date",
            "start_time",
            "stop_id",
            "arrival_time",
            "observed_at",
            "source",
        ],
    )
    try:
        rows = ch.query("SELECT source FROM arrivals WHERE city = 'test'").result_rows
        assert rows == [("feed",)]
    finally:
        ch.command("ALTER TABLE arrivals DELETE WHERE city = 'test'")
