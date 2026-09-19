# Модель данных

Выход стадии проектирования. Выводится из [event-contract.md](event-contract.md)
и [requirements.md](requirements.md).

DDL — черновик, на живой базе не проверялся.

---

## Связи

```
                    prediction_changes ──┐
                                         ├──► errors ──► реестр прогонов
                    arrivals ────────────┘       ▲
                        │                        │
                        ├──► segment_profiles ───┤  v0
                        │                        │
              errors ───┴──► bias_table ─────────┘  v1

positions ──► перекрёстная проверка прибытия, карта (не на критическом пути)

Postgres: расписание GTFS static ──► порядок остановок, плановые времена
```

---

## ClickHouse

### `prediction_changes` — изменения прогнозов агентства

Строка появляется, только когда предсказанное время изменилось. Прогноз на
любой момент восстанавливается как последняя запись с `published_at ≤ момент`.

```sql
CREATE TABLE prediction_changes (
    city                  LowCardinality(String),
    route_id              LowCardinality(String),
    direction_id          UInt8,
    start_date            Date,
    start_time            String,           -- строка: бывает > 24:00:00
    stop_id               String,
    published_at          DateTime,
    predicted_arrival     Nullable(DateTime),   -- NULL = прогноз исчез
    predicted_departure   Nullable(DateTime),
    uncertainty           Nullable(UInt16),
    schedule_relationship LowCardinality(String),
    ingested_at           DateTime
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(published_at)
ORDER BY (city, route_id, direction_id, start_date, start_time, stop_id, published_at)
TTL published_at + INTERVAL 3 MONTH;
```

**Ключ сортировки** начинается с ключа рейса и остановки, потому что главный
запрос резолвера — «вся история по этой паре». Префикс должен совпадать с
условием этого запроса, иначе он превратится в скан.

**`start_time` строкой**, а не временем: ночной рейс имеет отправление вида
`25:30:00`, и стандартный тип его не примет.

**`predicted_arrival = NULL`** означает не «нет данных», а событие «прогноз
исчез». Без этой записи не отличить «не менялся» от «больше не публикуется».

Объём: ~154 млн строк в месяц.

### `arrivals` — факты прибытия

Все наблюдения, включая правки. Устоявшееся значение определяется **при
чтении**: последнее наблюдение для пары, если оно старше двух минут.

```sql
CREATE TABLE arrivals (
    city         LowCardinality(String),
    route_id     LowCardinality(String),
    direction_id UInt8,
    start_date   Date,
    start_time   String,
    stop_id      String,
    arrival_time DateTime,
    observed_at  DateTime,
    source       Enum8('feed' = 1, 'stopped_at' = 2, 'geofence' = 3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(arrival_time)
ORDER BY (city, route_id, direction_id, start_date, start_time, stop_id, observed_at);
```

**Хранится бессрочно.** Это самая дешёвая и самая ценная таблица: 20 млн строк
в месяц, около 5–10 ГБ за два года после сжатия. Из неё строятся профили
перегонов (v0), на ней считается MAE, и она же нужна для любого пересчёта при
изменении логики агрегации.

**`source`** нужен, потому что определений прибытия несколько: факт из фида
(`uncertainty = 0`), момент `STOPPED_AT` из фида позиций и, для городов без
факта в фиде, геозона. Расхождение между ними — измеряемая величина.

Объём: ~20 млн строк в месяц.

### `errors` — результат резолвера

Корзины — колонки, а не строки: иначе 14 млн строк в сутки вместо 3.5 млн.
Новая модель добавляет строки, схема не меняется.

```sql
CREATE TABLE errors (
    city          LowCardinality(String),
    route_id      LowCardinality(String),
    direction_id  UInt8,
    start_date    Date,
    start_time    String,
    stop_id       String,
    arrival_time  DateTime,
    model         LowCardinality(String),   -- agency | sched | v0 | v1 | v2
    model_version LowCardinality(String),
    err_0_3       Nullable(Int32),          -- секунды СО ЗНАКОМ
    err_3_6       Nullable(Int32),
    err_6_10      Nullable(Int32),
    err_10_15     Nullable(Int32),
    err_15_30     Nullable(Int32),
    err_30p       Nullable(Int32),
    resolved_at   DateTime,
    hour          UInt8 MATERIALIZED toHour(arrival_time),
    day_type      UInt8 MATERIALIZED if(toDayOfWeek(arrival_time) < 6, 0, 1)
)
ENGINE = ReplacingMergeTree(resolved_at)
PARTITION BY toYYYYMM(arrival_time)
ORDER BY (city, model, model_version, route_id, arrival_time, stop_id);
```

**Знак ошибки сохраняется**, модуль берётся при подсчёте MAE: допуски
несимметричны, и «пришёл раньше» надо отличать от «пришёл позже».

**`NULL` в колонке корзины** означает «модель не дала прогноза на этом
горизонте» — это покрытие, а не отсутствующие данные.

**`ReplacingMergeTree`** по `resolved_at`: пересчёт той же версии модели
заменяет строку, новая версия добавляет свои. Это же закрывает дубликаты от
гарантии at-least-once.

**Материализованные `hour` и `day_type`** — чтобы разбивка не пересчитывала
функции от даты на каждой строке.

Объём: ~105 млн строк в месяц при четырёх моделях.

### `positions` — позиции машин

Не на критическом пути: метрика считается без них. Нужны для перекрёстной
проверки определения прибытия и для карты.

```sql
CREATE TABLE positions (
    city           LowCardinality(String),
    route_id       LowCardinality(String),
    direction_id   UInt8,
    start_date     Date,
    start_time     String,
    trip_id        Nullable(String),
    vehicle_id     String,
    ts             DateTime,
    ingested_at    DateTime,
    lat            Float64,
    lon            Float64,
    bearing        Nullable(Float32),
    speed          Nullable(Float32),
    stop_id        Nullable(String),
    stop_sequence  Nullable(UInt16),
    current_status Nullable(Enum8('INCOMING_AT'=0,'STOPPED_AT'=1,'IN_TRANSIT_TO'=2))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ts)
ORDER BY (city, route_id, direction_id, start_date, start_time, ts)
TTL ts + INTERVAL 3 WEEK;
```

Самая объёмная таблица — 167 млн строк в месяц, половина всего объёма, — и при
этом наименее нужная. Отсюда короткий TTL.

---

## Артефакты моделей

Датированные: прогноз на момент T использует артефакт, построенный на данных
строго до суток, содержащих T. Это правило одновременно обеспечивает
воспроизводимость и запрещает заглядывание в будущее.

### `segment_profiles` — основа v0

```sql
CREATE TABLE segment_profiles (
    valid_from   Date,              -- дата артефакта
    city         LowCardinality(String),
    route_id     LowCardinality(String),
    direction_id UInt8,
    from_stop    String,
    to_stop      String,
    time_band    LowCardinality(String),  -- ночь | утр.пик | день | веч.пик | вечер | поздний
    day_type     UInt8,
    median_sec   UInt32,
    p90_sec      UInt32,
    n            UInt32
)
ENGINE = ReplacingMergeTree
ORDER BY (valid_from, city, route_id, direction_id, from_stop, to_stop, time_band, day_type);
```

**Полосы времени вместо часов** — вынужденно: при 24 часах на ячейку приходится
7 наблюдений в неделю, при шести полосах — 28.

**Почему обычные медианы, а не состояния агрегатов.** Медианы не складываются:
профиль за неделю нельзя получить из семи дневных медиан. Из этого раньше
следовало, что надо хранить состояния квантилей и сливать их по окну.

Но это верно **только при выбрасывании сырья**. Прибытия хранятся бессрочно,
поэтому профиль за любое окно считается прямым сканом — точно и без аддитивности.
Состояния агрегатов остаются **оптимизацией на будущее**: понадобятся, если скан
сотен миллионов строк на каждый прогон гипотезы H4 окажется медленным.

### `bias_table` — основа v1

```sql
CREATE TABLE bias_table (
    valid_from     Date,
    city           LowCardinality(String),
    route_id       LowCardinality(String),
    direction_id   UInt8,
    hour           UInt8,
    day_type       UInt8,
    bucket         LowCardinality(String),
    correction_sec Int32,           -- медиана(факт − прогноз)
    n              UInt32,
    level          LowCardinality(String)  -- уровень иерархического отката
)
ENGINE = ReplacingMergeTree
ORDER BY (valid_from, city, route_id, direction_id, hour, day_type, bucket);
```

**`level`** записывает, с какого уровня отката взята поправка: полная ячейка,
маршрут без часа, маршрут целиком или город. Без этой колонки нельзя отличить
точную поправку от грубой заглушки.

Поправка — **медиана**, не среднее: у ошибок длинный хвост, p90 вдвое больше
медианы.

### `runs` — реестр прогонов

```sql
CREATE TABLE runs (
    run_id        String,
    started_at    DateTime,
    model         LowCardinality(String),
    model_version String,
    artifact_date Date,
    test_set_id   String,
    code_commit   String,
    n_arrivals    UInt32,
    result        String            -- JSON: кривая MAE, покрытие, доля в допуске
)
ENGINE = MergeTree
ORDER BY (started_at);
```

Без этой таблицы результат невоспроизводим: через месяц не сказать, какой
версией модели и на каком наборе получена цифра.

### Тестовый набор

Не таблица со списком событий, а **определение**: город, период, правило отбора.

```
test_set_id = "hsl-2026-10"
   city        = hsl
   period      = [2026-10-01, 2026-11-01)
   отбор       = все прибытия с фактом source='feed',
                 устоявшимся на момент фиксации набора
   зафиксирован = 2026-11-02
```

Определение детерминировано: все наблюдения фактов хранятся, поэтому
«устоявшееся на момент T» вычисляется одинаково при любом пересчёте.

---

## Postgres — расписание и справочники

Стандартный GTFS static плюс версионирование.

```sql
CREATE TABLE gtfs_versions (
    id          serial PRIMARY KEY,
    city        text NOT NULL,
    loaded_at   timestamptz NOT NULL,
    source_url  text NOT NULL,
    checksum    text NOT NULL,
    is_active   boolean NOT NULL DEFAULT false
);

-- routes, stops, trips, stop_times — по спецификации GTFS,
-- каждая с колонкой version_id и внешним ключом на gtfs_versions
```

Производная таблица, ради которой всё это нужно:

```sql
CREATE TABLE trip_stop_order (
    version_id   int REFERENCES gtfs_versions(id),
    city         text,
    route_id     text,
    direction_id smallint,
    start_time   text,
    stop_id      text,
    stop_seq     smallint,
    scheduled_arrival interval,     -- может быть > 24 часов
    PRIMARY KEY (version_id, city, route_id, direction_id, start_time, stop_id)
);
```

Закрывает две дыры в данных HSL: отсутствующий `stop_sequence` и отсутствующий
`arrival.delay` — плановое время берётся отсюда.

`scheduled_arrival` типом `interval`, а не `time`: ночные рейсы имеют плановые
времена вида `25:30:00`.

---

## Политика хранения

| Таблица | Срок | Почему |
|---|---|---|
| `positions` | 3 недели | не на критическом пути, половина объёма |
| `prediction_changes` | 3 месяца | нужны для пересчёта и проверки отдельного случая |
| `arrivals` | **бессрочно** | основа профилей и всех пересчётов; дёшево — 5–10 ГБ за 2 года |
| `errors` | бессрочно | это и есть результат проекта |
| артефакты моделей | бессрочно | воспроизводимость |
| `runs` | бессрочно | мало строк |

Итого при полном заполнении: около 25–30 ГБ на четыре месяца. Диск 100 ГБ.

---

## Открытые вопросы

- **Срок хранения `prediction_changes`.** Три месяца — предположение. Зависит от
  того, как часто будут нужны пересчёты за старое. Это единственная таблица, где
  срок реально ограничивает возможности: без неё нельзя переиграть прогнозы
  агентства и нельзя показать историю прогнозов по старому прибытию.
- **Границы полос времени** в `segment_profiles` — подбираются на данных.
- **Порог `n`** для иерархического отката в `bias_table` — сейчас предполагается
  30, проверить на реальном распределении.
- **Дедупликация в `errors`** — `ReplacingMergeTree` схлопывает при слиянии, то
  есть не сразу. Проверить, влияет ли это на агрегаты.
