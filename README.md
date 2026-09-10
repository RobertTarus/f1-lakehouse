# 🏎️ F1 Lakehouse

An end-to-end open-source Formula 1 data platform built with **FastF1, SeaweedFS, Apache Iceberg, Trino, dbt, Apache Airflow, and Streamlit**.

The project treats Formula 1 data as a real data-engineering workload: race data is extracted from FastF1, landed as immutable Parquet in S3-compatible object storage, promoted into Iceberg tables, queried through Trino, transformed through Bronze/Silver/Gold layers with dbt, and orchestrated with Airflow.

## Architecture

```text
FastF1
   │
   ▼
Python ingestion
   │
   ▼
SeaweedFS ─────────────── Raw / landing zone
   │                     Parquet + JSON
   ▼
PyArrow / PyIceberg
   │
   ▼
Apache Iceberg ───────── Bronze tables
   │                     laps / results / weather / telemetry
   ▼
Trino
   │
   ▼
dbt ──────────────────── Silver + Gold transformations/tests
   │
   ▼
Streamlit

        Apache Airflow orchestrates the pipeline
```

## Stack

| Layer | Technology |
|---|---|
| Source | FastF1 |
| Ingestion | Python |
| Processing | Pandas / PyArrow |
| Object storage | SeaweedFS |
| File format | Parquet |
| Table format | Apache Iceberg |
| Iceberg client | PyIceberg |
| SQL query engine | Trino |
| Transformation | dbt Core + dbt-trino |
| Orchestration | Apache Airflow |
| Metadata database | PostgreSQL |
| Visualization | Streamlit |
| Containers | Podman / Compose |

## 1. S3-compatible storage with SeaweedFS

SeaweedFS provides the object-storage layer used for the raw landing zone and the Iceberg warehouse.

![SeaweedFS Admin](docs/screenshots/01-seaweedfs-admin.png)

Python connectivity is validated through `boto3` before ingestion begins.

![SeaweedFS S3 connection](docs/screenshots/02-s3-connection.png)

## 2. FastF1 ingestion

The ingestion layer extracts race/session data from FastF1 and writes Parquet plus metadata into a partitioned raw layout.

```text
f1-raw/
└── season=2026/
    └── event=italian-grand-prix/
        └── session=R/
            ├── laps.parquet
            ├── results.parquet
            ├── weather.parquet
            └── metadata.json
```

![FastF1 ingestion](docs/screenshots/03-fastf1-ingestion.png)

The resulting raw objects are visible directly in SeaweedFS.

![Raw Parquet objects](docs/screenshots/04-raw-parquet-objects.png)

## 3. Raw schema validation

Raw Parquet files are inspected before promotion so source types are understood before a Bronze contract is defined.

### Laps

![Laps schema](docs/screenshots/13-laps-parquet-schema.png)

### Results

![Results schema](docs/screenshots/14-results-parquet-schema.png)

### Weather

![Weather schema](docs/screenshots/15-weather-parquet-schema.png)

## 4. Apache Iceberg lakehouse layer

SeaweedFS exposes an Iceberg REST catalog and an Iceberg table bucket used by PyIceberg.

![Iceberg catalog connection](docs/screenshots/05-iceberg-catalog-connection.png)

Bronze tables normalize source-oriented FastF1 fields into explicit analytical contracts while preserving lineage.

![Bronze Iceberg table](docs/screenshots/06-iceberg-bronze-table.png)

Iceberg snapshots make table state and idempotent overwrite behavior visible.

![Iceberg snapshots](docs/screenshots/07-iceberg-snapshots.png)

Catalog inspection confirms the registered Bronze tables and row counts.

![Iceberg catalog inspection](docs/screenshots/08-iceberg-catalog-inspection.png)

## 5. Trino SQL layer

Trino provides the SQL compute layer over Iceberg while keeping compute separate from storage.

![Trino service](docs/screenshots/09-trino-ui.png)

Bronze data can be queried directly through Trino.

![Trino Bronze query](docs/screenshots/10-trino-bronze-query.png)

Iceberg metadata tables expose snapshots and physical Parquet files through SQL.

![Trino Iceberg metadata](docs/screenshots/11-trino-iceberg-metadata.png)

## 6. Medallion modeling with dbt

The project uses a Bronze → Silver → Gold design.

```text
BRONZE
  normalized source data
      │
      ▼
SILVER
  validated / deduplicated / analysis-ready
      │
      ▼
GOLD
  application-ready analytical marts
```

Current models include:

```text
bronze.laps
bronze.results
bronze.weather
bronze.telemetry

silver.silver_laps
silver.silver_results
silver.silver_weather
silver.silver_telemetry

gold.race_driver_performance
gold.lap_telemetry_metrics
```

The Gold race-performance mart combines classification, starting position, finishing position, race pace, fastest lap, tyre metrics, and weather context.

![Gold race driver performance](docs/screenshots/12-gold-race-driver-performance.png)

## 7. Idempotency

Iceberg writes use partition-level overwrite rather than blind append. Reprocessing the same event/session/driver therefore replaces the existing logical partition instead of duplicating data.

```text
Run 1 → N rows
Run 2 → N rows ✅

not

Run 1 → N rows
Run 2 → 2N rows ❌
```

This design is important for retries and Airflow-driven reprocessing.

## 8. Airflow orchestration

The pipeline is orchestrated as a parameterized Airflow DAG.

```text
                         ingest_session
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
         promote_laps   promote_results  promote_weather
                              │
                       ingest_telemetry
                              │
                              ▼
                      promote_telemetry
               └──────────────┬──────────────┘
                              ▼
                       dbt_source_tests
                              │
                              ▼
                          dbt_build
                              │
                              ▼
                        validate_gold
```

Runtime parameters allow the same DAG to process different seasons, Grands Prix, and session types.

> Airflow DAG screenshot will be added in the next documentation update.

## Engineering decisions

The project intentionally separates responsibilities:

```text
SeaweedFS      → object storage
Apache Iceberg → table format + snapshots + metadata
Trino          → SQL compute
PyIceberg      → programmatic table writes
 dbt           → transformations + tests
Airflow        → orchestration
Streamlit      → serving / visualization
```

Other deliberate choices include explicit PyArrow schemas, immutable raw storage, replayability, partition-aware writes, composite-key duplicate tests, and pre-aggregated Gold telemetry marts to avoid repeatedly scanning high-frequency telemetry.

## Repository layout

```text
f1-lakehouse/
├── airflow/
│   └── dags/
├── app/
├── configs/
│   ├── dbt/
│   └── trino/
├── dbt/
│   ├── macros/
│   ├── models/
│   │   ├── bronze/
│   │   ├── silver/
│   │   └── gold/
│   └── tests/
├── docker/
├── docs/
│   └── screenshots/
├── src/
│   ├── common/
│   ├── iceberg/
│   ├── ingestion/
│   └── validation/
├── compose.yaml
├── requirements.txt
└── README.md
```

## Current milestone

The platform currently demonstrates:

- FastF1 race/session ingestion
- SeaweedFS S3-compatible raw storage
- Parquet schema inspection
- Iceberg REST catalog integration
- Bronze Iceberg tables
- Iceberg snapshots and idempotent writes
- Trino SQL access and Iceberg metadata queries
- dbt Silver and Gold modeling
- telemetry ingestion and analytical aggregation
- Airflow orchestration
- Streamlit serving layer

## Next improvements

The next engineering iterations are full-season orchestration/backfills, Airflow dynamic task mapping, Iceberg maintenance/compaction, CI with GitHub Actions, richer automated testing, and observability with Prometheus/Grafana.

## Author

**Robert Tarus**  
Data Engineer
