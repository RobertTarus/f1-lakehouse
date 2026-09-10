import argparse
import io
import os
import re
from datetime import datetime, timezone

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from botocore.config import Config
from dotenv import load_dotenv
from pyiceberg.catalog.rest import RestCatalog


load_dotenv()


# =========================================================
# Configuration
# =========================================================

RAW_BUCKET = os.getenv(
    "SEAWEED_S3_BUCKET",
    "f1-raw",
)

TABLE_BUCKET = os.getenv(
    "SEAWEED_TABLE_BUCKET",
    "f1-iceberg",
)

S3_ENDPOINT = os.getenv(
    "SEAWEED_S3_ENDPOINT",
    "http://localhost:8333",
)

CATALOG_URI = os.getenv(
    "ICEBERG_CATALOG_URI",
    "http://localhost:8181",
)

ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")


# =========================================================
# Infrastructure
# =========================================================

def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"}
        ),
    )


def get_catalog():
    return RestCatalog(
        name="f1",
        uri=CATALOG_URI,
        warehouse=f"s3://{TABLE_BUCKET}",
        credential=f"{ACCESS_KEY}:{SECRET_KEY}",
        **{
            "s3.endpoint": S3_ENDPOINT,
            "s3.access-key-id": ACCESS_KEY,
            "s3.secret-access-key": SECRET_KEY,
            "s3.path-style-access": "true",
            "s3.region": "us-east-1",
        },
    )


# =========================================================
# Conversion helpers
# =========================================================

def duration_to_ms(series: pd.Series) -> pd.Series:
    values = pd.to_timedelta(
        series,
        errors="coerce",
    )

    return (
        values.dt.total_seconds() * 1000
    ).round().astype("Int64")


def float_column(df, name):
    return pd.to_numeric(
        df[name],
        errors="coerce",
    ).astype("float64")


def int_column(df, name):
    return (
        pd.to_numeric(
            df[name],
            errors="coerce",
        )
        .round()
        .astype("Int32")
    )


# =========================================================
# Raw read
# =========================================================

def read_raw(
    year: int,
    event: str,
    session: str,
    driver: str,
) -> pd.DataFrame:

    event_slug = slugify(event)

    key = (
        f"season={year}/"
        f"event={event_slug}/"
        f"session={session}/"
        f"telemetry/"
        f"driver={driver}/"
        f"telemetry.parquet"
    )

    print()
    print("=" * 70)
    print("RAW TELEMETRY READ")
    print("=" * 70)
    print(f"s3://{RAW_BUCKET}/{key}")

    response = get_s3().get_object(
        Bucket=RAW_BUCKET,
        Key=key,
    )

    payload = response["Body"].read()

    table = pq.read_table(
        io.BytesIO(payload)
    )

    print(f"Rows:    {table.num_rows:,}")
    print(f"Columns: {table.num_columns}")

    return table.to_pandas()


# =========================================================
# Normalization
# =========================================================

def normalize(
    df: pd.DataFrame,
    year: int,
    event: str,
    session: str,
    driver: str,
) -> pa.Table:

    print()
    print("=" * 70)
    print("NORMALIZE TELEMETRY")
    print("=" * 70)

    event_slug = slugify(event)

    bronze = pd.DataFrame()

    # -----------------------------------------------------
    # Partition / event metadata
    # -----------------------------------------------------

    bronze["season"] = pd.Series(
        [year] * len(df),
        dtype="int32",
    )

    bronze["event_name"] = pd.Series(
        [event] * len(df),
        dtype="string",
    )

    bronze["event_slug"] = pd.Series(
        [event_slug] * len(df),
        dtype="string",
    )

    bronze["session_type"] = pd.Series(
        [session] * len(df),
        dtype="string",
    )

    bronze["driver_code"] = pd.Series(
        [driver] * len(df),
        dtype="string",
    )

    # -----------------------------------------------------
    # Driver
    # -----------------------------------------------------

    bronze["driver_number"] = (
        df["DriverNumber"]
        .astype("string")
    )

    bronze["team_name"] = (
        df["Team"]
        .astype("string")
    )

    bronze["lap_number"] = int_column(
        df,
        "LapNumber",
    )

    # -----------------------------------------------------
    # Timing
    # -----------------------------------------------------

    bronze["sample_timestamp_utc"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
        utc=True,
    )

    bronze["session_time_ms"] = duration_to_ms(
        df["SessionTime"]
    )

    bronze["sample_time_ms"] = duration_to_ms(
        df["Time"]
    )

    # -----------------------------------------------------
    # Car telemetry
    # -----------------------------------------------------

    bronze["rpm"] = float_column(
        df,
        "RPM",
    )

    bronze["speed_kph"] = float_column(
        df,
        "Speed",
    )

    bronze["gear"] = int_column(
        df,
        "nGear",
    )

    bronze["throttle_pct"] = float_column(
        df,
        "Throttle",
    )

    bronze["brake"] = (
        df["Brake"]
        .astype("boolean")
    )

    bronze["drs"] = int_column(
        df,
        "DRS",
    )

    # -----------------------------------------------------
    # Track position
    # -----------------------------------------------------

    bronze["x"] = float_column(
        df,
        "X",
    )

    bronze["y"] = float_column(
        df,
        "Y",
    )

    bronze["z"] = float_column(
        df,
        "Z",
    )

    bronze["distance"] = float_column(
        df,
        "Distance",
    )

    bronze["relative_distance"] = float_column(
        df,
        "RelativeDistance",
    )

    # -----------------------------------------------------
    # Traffic/context
    # -----------------------------------------------------

    bronze["driver_ahead"] = (
        df["DriverAhead"]
        .astype("string")
    )

    bronze["distance_to_driver_ahead"] = float_column(
        df,
        "DistanceToDriverAhead",
    )

    bronze["source"] = (
        df["Source"]
        .astype("string")
    )

    bronze["status"] = (
        df["Status"]
        .astype("string")
    )

    # -----------------------------------------------------
    # Lineage
    # -----------------------------------------------------

    bronze["source_system"] = pd.Series(
        ["FastF1"] * len(df),
        dtype="string",
    )

    ingestion_time = datetime.now(
        timezone.utc
    )

    bronze["ingested_at"] = pd.Series(
        [ingestion_time] * len(df),
    )

    # -----------------------------------------------------
    # Explicit Arrow schema
    # -----------------------------------------------------

    schema = pa.schema([

        pa.field("season", pa.int32()),
        pa.field("event_name", pa.string()),
        pa.field("event_slug", pa.string()),
        pa.field("session_type", pa.string()),

        pa.field("driver_code", pa.string()),
        pa.field("driver_number", pa.string()),
        pa.field("team_name", pa.string()),
        pa.field("lap_number", pa.int32()),

        pa.field(
            "sample_timestamp_utc",
            pa.timestamp("us", tz="UTC"),
        ),

        pa.field("session_time_ms", pa.int64()),
        pa.field("sample_time_ms", pa.int64()),

        pa.field("rpm", pa.float64()),
        pa.field("speed_kph", pa.float64()),
        pa.field("gear", pa.int32()),
        pa.field("throttle_pct", pa.float64()),
        pa.field("brake", pa.bool_()),
        pa.field("drs", pa.int32()),

        pa.field("x", pa.float64()),
        pa.field("y", pa.float64()),
        pa.field("z", pa.float64()),

        pa.field("distance", pa.float64()),
        pa.field("relative_distance", pa.float64()),

        pa.field("driver_ahead", pa.string()),
        pa.field(
            "distance_to_driver_ahead",
            pa.float64(),
        ),

        pa.field("source", pa.string()),
        pa.field("status", pa.string()),

        pa.field("source_system", pa.string()),

        pa.field(
            "ingested_at",
            pa.timestamp("us", tz="UTC"),
        ),
    ])

    arrow_table = pa.Table.from_pandas(
        bronze,
        schema=schema,
        preserve_index=False,
    )

    print(f"Rows:    {arrow_table.num_rows:,}")
    print(f"Columns: {arrow_table.num_columns}")

    print()
    print(arrow_table.schema)

    return arrow_table


# =========================================================
# Iceberg write
# =========================================================

def write_iceberg(data: pa.Table):

    catalog = get_catalog()

    catalog.create_namespace_if_not_exists(
        "bronze"
    )

    identifier = "bronze.telemetry"

    print()
    print("=" * 70)
    print("ICEBERG WRITE")
    print("=" * 70)

    if not catalog.table_exists(identifier):

        print(
            f"Creating Iceberg table: {identifier}"
        )

        with catalog.create_table_transaction(
            identifier=identifier,
            schema=data.schema,
        ) as transaction:

            with transaction.update_spec() as spec:

                spec.add_identity("season")
                spec.add_identity("event_slug")
                spec.add_identity("session_type")
                spec.add_identity("driver_code")

    table = catalog.load_table(
        identifier
    )

    print(
        f"Writing {data.num_rows:,} telemetry rows..."
    )

    table.dynamic_partition_overwrite(
        data,
        snapshot_properties={
            "pipeline": "telemetry-promotion",
            "source": "FastF1",
        },
    )

    print("Iceberg commit successful.")

    return table


# =========================================================
# Validation
# =========================================================

def validate(table):

    print()
    print("=" * 70)
    print("ICEBERG VALIDATION")
    print("=" * 70)

    snapshot = table.current_snapshot()

    print(f"Table: {'.'.join(table.name())}")

    if snapshot is not None:
        print(
            f"Snapshot ID: {snapshot.snapshot_id}"
        )

    print()
    print("Partition spec:")
    print(table.spec())

    print()
    print("Schema:")
    print(table.schema())


# =========================================================
# CLI
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Promote FastF1 raw telemetry "
            "into Bronze Iceberg."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--event",
        required=True,
    )

    parser.add_argument(
        "--session",
        default="R",
    )

    parser.add_argument(
        "--driver",
        required=True,
    )

    args = parser.parse_args()

    raw = read_raw(
        args.year,
        args.event,
        args.session,
        args.driver,
    )

    data = normalize(
        raw,
        args.year,
        args.event,
        args.session,
        args.driver,
    )

    table = write_iceberg(
        data
    )

    validate(
        table
    )

    print()
    print("=" * 70)
    print("TELEMETRY PROMOTION COMPLETE")
    print("=" * 70)

    print("Table: bronze.telemetry")


if __name__ == "__main__":
    main()
