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

ICEBERG_CATALOG_URI = os.getenv(
    "ICEBERG_CATALOG_URI",
    "http://localhost:8181",
)

ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")


# =========================================================
# Helpers
# =========================================================

def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def get_s3_client():
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


def get_iceberg_catalog():
    return RestCatalog(
        name="f1",
        uri=ICEBERG_CATALOG_URI,
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


def timedelta_to_ms(series: pd.Series) -> pd.Series:
    values = pd.to_timedelta(
        series,
        errors="coerce",
    )

    return (
        values.dt.total_seconds() * 1000
    ).round().astype("Int64")


# =========================================================
# Raw extraction
# =========================================================

def read_raw_laps(
    year: int,
    event: str,
    session_type: str,
) -> pd.DataFrame:

    event_slug = slugify(event)

    key = (
        f"season={year}/"
        f"event={event_slug}/"
        f"session={session_type}/"
        f"laps.parquet"
    )

    print("=" * 70)
    print("READ RAW DATA")
    print("=" * 70)
    print(f"s3://{RAW_BUCKET}/{key}")

    s3 = get_s3_client()

    response = s3.get_object(
        Bucket=RAW_BUCKET,
        Key=key,
    )

    payload = response["Body"].read()

    table = pq.read_table(
        io.BytesIO(payload)
    )

    df = table.to_pandas()

    print(f"Raw rows:    {len(df):,}")
    print(f"Raw columns: {len(df.columns):,}")

    return df


# =========================================================
# Bronze normalization
# =========================================================

def normalize_laps(
    df: pd.DataFrame,
    year: int,
    event: str,
    session_type: str,
) -> pa.Table:

    print()
    print("=" * 70)
    print("NORMALIZE BRONZE SCHEMA")
    print("=" * 70)

    event_slug = slugify(event)

    bronze = pd.DataFrame()

    # -----------------------------------------------------
    # Pipeline metadata / partition columns
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
        [session_type] * len(df),
        dtype="string",
    )

    # -----------------------------------------------------
    # Driver information
    # -----------------------------------------------------

    bronze["driver_code"] = (
        df["Driver"]
        .astype("string")
    )

    bronze["driver_number"] = (
        df["DriverNumber"]
        .astype("string")
    )

    bronze["team_name"] = (
        df["Team"]
        .astype("string")
    )

    # -----------------------------------------------------
    # Lap identifiers
    # -----------------------------------------------------

    bronze["lap_number"] = (
        pd.to_numeric(
            df["LapNumber"],
            errors="coerce",
        )
        .round()
        .astype("Int32")
    )

    bronze["stint"] = (
        pd.to_numeric(
            df["Stint"],
            errors="coerce",
        )
        .round()
        .astype("Int32")
    )

    bronze["position"] = (
        pd.to_numeric(
            df["Position"],
            errors="coerce",
        )
        .round()
        .astype("Int32")
    )

    # -----------------------------------------------------
    # Timing
    # -----------------------------------------------------

    bronze["lap_time_ms"] = timedelta_to_ms(
        df["LapTime"]
    )

    bronze["sector_1_ms"] = timedelta_to_ms(
        df["Sector1Time"]
    )

    bronze["sector_2_ms"] = timedelta_to_ms(
        df["Sector2Time"]
    )

    bronze["sector_3_ms"] = timedelta_to_ms(
        df["Sector3Time"]
    )

    # -----------------------------------------------------
    # Speed traps
    # -----------------------------------------------------

    for source, target in [
        ("SpeedI1", "speed_i1"),
        ("SpeedI2", "speed_i2"),
        ("SpeedFL", "speed_fl"),
        ("SpeedST", "speed_st"),
    ]:
        bronze[target] = pd.to_numeric(
            df[source],
            errors="coerce",
        ).astype("float64")

    # -----------------------------------------------------
    # Tyres
    # -----------------------------------------------------

    bronze["compound"] = (
        df["Compound"]
        .astype("string")
    )

    bronze["tyre_life"] = pd.to_numeric(
        df["TyreLife"],
        errors="coerce",
    ).astype("float64")

    bronze["fresh_tyre"] = (
        df["FreshTyre"]
        .astype("boolean")
    )

    # -----------------------------------------------------
    # Race state
    # -----------------------------------------------------

    bronze["track_status"] = (
        df["TrackStatus"]
        .astype("string")
    )

    bronze["is_personal_best"] = (
        df["IsPersonalBest"]
        .astype("boolean")
    )

    bronze["is_accurate"] = (
        df["IsAccurate"]
        .astype("boolean")
    )

    bronze["deleted"] = (
        df["Deleted"]
        .astype("boolean")
    )

    bronze["deleted_reason"] = (
        df["DeletedReason"]
        .astype("string")
    )

    # -----------------------------------------------------
    # Timestamp
    # -----------------------------------------------------

    bronze["lap_start_date"] = pd.to_datetime(
        df["LapStartDate"],
        errors="coerce",
        utc=True,
    )

    # -----------------------------------------------------
    # Lineage metadata
    # -----------------------------------------------------

    bronze["source_system"] = pd.Series(
        ["FastF1"] * len(df),
        dtype="string",
    )

    ingestion_time = datetime.now(timezone.utc)

    bronze["ingested_at"] = pd.Series(
        [ingestion_time] * len(df),
    )

    # -----------------------------------------------------
    # Explicit Arrow contract
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
        pa.field("stint", pa.int32()),
        pa.field("position", pa.int32()),

        pa.field("lap_time_ms", pa.int64()),
        pa.field("sector_1_ms", pa.int64()),
        pa.field("sector_2_ms", pa.int64()),
        pa.field("sector_3_ms", pa.int64()),

        pa.field("speed_i1", pa.float64()),
        pa.field("speed_i2", pa.float64()),
        pa.field("speed_fl", pa.float64()),
        pa.field("speed_st", pa.float64()),

        pa.field("compound", pa.string()),
        pa.field("tyre_life", pa.float64()),
        pa.field("fresh_tyre", pa.bool_()),

        pa.field("track_status", pa.string()),

        pa.field("is_personal_best", pa.bool_()),
        pa.field("is_accurate", pa.bool_()),
        pa.field("deleted", pa.bool_()),
        pa.field("deleted_reason", pa.string()),

        pa.field(
            "lap_start_date",
            pa.timestamp("us", tz="UTC"),
        ),

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

    print(f"Bronze rows:    {arrow_table.num_rows:,}")
    print(f"Bronze columns: {arrow_table.num_columns:,}")

    print()
    print(arrow_table.schema)

    return arrow_table


# =========================================================
# Iceberg
# =========================================================

def promote_to_iceberg(
    data: pa.Table,
):

    print()
    print("=" * 70)
    print("ICEBERG WRITE")
    print("=" * 70)

    catalog = get_iceberg_catalog()

    catalog.create_namespace_if_not_exists(
        "bronze"
    )

    identifier = "bronze.laps"

    existing_tables = catalog.list_tables(
        "bronze"
    )

    table_exists = (
        ("bronze", "laps") in existing_tables
    )

    if not table_exists:

        print(
            "Creating Iceberg table: "
            f"{identifier}"
        )

        #
        # Create the table and establish the initial
        # partition specification by column name.
        #
        with catalog.create_table_transaction(
            identifier=identifier,
            schema=data.schema,
        ) as transaction:

            with transaction.update_spec() as spec:
                spec.add_identity("season")
                spec.add_identity("event_slug")
                spec.add_identity("session_type")

    table = catalog.load_table(
        identifier
    )

    print(
        "Writing partition with "
        "dynamic partition overwrite..."
    )

    #
    # This makes this ingestion idempotent at the
    # season/event/session partition level.
    #
    table.dynamic_partition_overwrite(
        data
    )

    print("Write committed.")

    return table


# =========================================================
# Validation
# =========================================================

def validate_table(table):

    print()
    print("=" * 70)
    print("ICEBERG READ-BACK")
    print("=" * 70)

    result = table.scan(
        selected_fields=(
            "season",
            "event_name",
            "session_type",
            "driver_code",
            "lap_number",
            "lap_time_ms",
            "compound",
            "position",
        )
    ).to_arrow()

    print(f"Total Iceberg rows: {result.num_rows:,}")

    print()
    print(
        result
        .slice(0, 10)
        .to_pandas()
        .to_string(index=False)
    )

    print()
    print("Table schema:")
    print(table.schema())

    snapshot = table.current_snapshot()

    if snapshot is not None:
        print()
        print(
            f"Current snapshot ID: "
            f"{snapshot.snapshot_id}"
        )


# =========================================================
# CLI
# =========================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Promote raw FastF1 laps "
            "into the Bronze Iceberg layer."
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

    return parser.parse_args()


def main():

    args = parse_args()

    raw = read_raw_laps(
        args.year,
        args.event,
        args.session,
    )

    bronze = normalize_laps(
        raw,
        args.year,
        args.event,
        args.session,
    )

    table = promote_to_iceberg(
        bronze
    )

    validate_table(
        table
    )

    print()
    print("=" * 70)
    print("BRONZE PROMOTION COMPLETE")
    print("=" * 70)
    print("Table: bronze.laps")


if __name__ == "__main__":
    main()
