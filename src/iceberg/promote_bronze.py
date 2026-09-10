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


RAW_BUCKET = os.getenv("SEAWEED_S3_BUCKET", "f1-raw")
TABLE_BUCKET = os.getenv("SEAWEED_TABLE_BUCKET", "f1-iceberg")

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
# Raw read
# =========================================================

def read_raw(
    year: int,
    event: str,
    session: str,
    dataset: str,
) -> pd.DataFrame:

    event_slug = slugify(event)

    key = (
        f"season={year}/"
        f"event={event_slug}/"
        f"session={session}/"
        f"{dataset}.parquet"
    )

    print()
    print("=" * 70)
    print("RAW READ")
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
    print(f"Columns: {table.num_columns:,}")

    return table.to_pandas()


# =========================================================
# Conversion helpers
# =========================================================

def timedelta_to_ms(series: pd.Series) -> pd.Series:
    values = pd.to_timedelta(
        series,
        errors="coerce",
    )

    return (
        values.dt.total_seconds() * 1000
    ).round().astype("Int64")


def string_column(df, name):
    if name not in df.columns:
        return pd.Series(
            pd.NA,
            index=df.index,
            dtype="string",
        )

    return df[name].astype("string")


def float_column(df, name):
    if name not in df.columns:
        return pd.Series(
            float("nan"),
            index=df.index,
            dtype="float64",
        )

    return pd.to_numeric(
        df[name],
        errors="coerce",
    ).astype("float64")


def int_column(df, name):
    if name not in df.columns:
        return pd.Series(
            pd.NA,
            index=df.index,
            dtype="Int32",
        )

    return (
        pd.to_numeric(
            df[name],
            errors="coerce",
        )
        .round()
        .astype("Int32")
    )


def bool_column(df, name):
    if name not in df.columns:
        return pd.Series(
            pd.NA,
            index=df.index,
            dtype="boolean",
        )

    return df[name].astype("boolean")


def metadata_columns(
    frame,
    year,
    event,
    session,
):
    size = len(frame)

    return {
        "season": pd.Series(
            [year] * size,
            dtype="int32",
        ),
        "event_name": pd.Series(
            [event] * size,
            dtype="string",
        ),
        "event_slug": pd.Series(
            [slugify(event)] * size,
            dtype="string",
        ),
        "session_type": pd.Series(
            [session] * size,
            dtype="string",
        ),
    }


# =========================================================
# Results normalization
# =========================================================

def normalize_results(
    df,
    year,
    event,
    session,
):

    bronze = pd.DataFrame(
        metadata_columns(
            df,
            year,
            event,
            session,
        )
    )

    bronze["driver_number"] = string_column(
        df,
        "DriverNumber",
    )

    bronze["driver_code"] = string_column(
        df,
        "Abbreviation",
    )

    bronze["driver_id"] = string_column(
        df,
        "DriverId",
    )

    bronze["first_name"] = string_column(
        df,
        "FirstName",
    )

    bronze["last_name"] = string_column(
        df,
        "LastName",
    )

    bronze["full_name"] = string_column(
        df,
        "FullName",
    )

    bronze["country_code"] = string_column(
        df,
        "CountryCode",
    )

    bronze["team_name"] = string_column(
        df,
        "TeamName",
    )

    bronze["team_id"] = string_column(
        df,
        "TeamId",
    )

    bronze["position"] = int_column(
        df,
        "Position",
    )

    bronze["classified_position"] = string_column(
        df,
        "ClassifiedPosition",
    )

    bronze["grid_position"] = int_column(
        df,
        "GridPosition",
    )

    bronze["status"] = string_column(
        df,
        "Status",
    )

    bronze["points"] = float_column(
        df,
        "Points",
    )

    if "Time" in df.columns:
        bronze["result_time_ms"] = timedelta_to_ms(
            df["Time"]
        )
    else:
        bronze["result_time_ms"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Int64",
        )

    bronze["source_system"] = "FastF1"

    bronze["ingested_at"] = datetime.now(
        timezone.utc
    )

    schema = pa.schema([
        pa.field("season", pa.int32()),
        pa.field("event_name", pa.string()),
        pa.field("event_slug", pa.string()),
        pa.field("session_type", pa.string()),

        pa.field("driver_number", pa.string()),
        pa.field("driver_code", pa.string()),
        pa.field("driver_id", pa.string()),
        pa.field("first_name", pa.string()),
        pa.field("last_name", pa.string()),
        pa.field("full_name", pa.string()),
        pa.field("country_code", pa.string()),

        pa.field("team_name", pa.string()),
        pa.field("team_id", pa.string()),

        pa.field("position", pa.int32()),
        pa.field("classified_position", pa.string()),
        pa.field("grid_position", pa.int32()),

        pa.field("status", pa.string()),
        pa.field("points", pa.float64()),
        pa.field("result_time_ms", pa.int64()),

        pa.field("source_system", pa.string()),

        pa.field(
            "ingested_at",
            pa.timestamp("us", tz="UTC"),
        ),
    ])

    return pa.Table.from_pandas(
        bronze,
        schema=schema,
        preserve_index=False,
    )


# =========================================================
# Weather normalization
# =========================================================

def normalize_weather(
    df,
    year,
    event,
    session,
):

    bronze = pd.DataFrame(
        metadata_columns(
            df,
            year,
            event,
            session,
        )
    )

    if "Time" in df.columns:
        bronze["session_time_ms"] = timedelta_to_ms(
            df["Time"]
        )
    else:
        bronze["session_time_ms"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Int64",
        )

    bronze["air_temp_c"] = float_column(
        df,
        "AirTemp",
    )

    bronze["humidity_pct"] = float_column(
        df,
        "Humidity",
    )

    bronze["pressure_mbar"] = float_column(
        df,
        "Pressure",
    )

    bronze["rainfall"] = bool_column(
        df,
        "Rainfall",
    )

    bronze["track_temp_c"] = float_column(
        df,
        "TrackTemp",
    )

    bronze["wind_direction_deg"] = int_column(
        df,
        "WindDirection",
    )

    bronze["wind_speed"] = float_column(
        df,
        "WindSpeed",
    )

    bronze["source_system"] = "FastF1"

    bronze["ingested_at"] = datetime.now(
        timezone.utc
    )

    schema = pa.schema([
        pa.field("season", pa.int32()),
        pa.field("event_name", pa.string()),
        pa.field("event_slug", pa.string()),
        pa.field("session_type", pa.string()),

        pa.field("session_time_ms", pa.int64()),

        pa.field("air_temp_c", pa.float64()),
        pa.field("humidity_pct", pa.float64()),
        pa.field("pressure_mbar", pa.float64()),
        pa.field("rainfall", pa.bool_()),
        pa.field("track_temp_c", pa.float64()),
        pa.field("wind_direction_deg", pa.int32()),
        pa.field("wind_speed", pa.float64()),

        pa.field("source_system", pa.string()),

        pa.field(
            "ingested_at",
            pa.timestamp("us", tz="UTC"),
        ),
    ])

    return pa.Table.from_pandas(
        bronze,
        schema=schema,
        preserve_index=False,
    )


# =========================================================
# Iceberg write
# =========================================================

def write_iceberg(
    dataset,
    data,
):

    catalog = get_catalog()

    catalog.create_namespace_if_not_exists(
        "bronze"
    )

    identifier = f"bronze.{dataset}"

    print()
    print("=" * 70)
    print("ICEBERG")
    print("=" * 70)

    if not catalog.table_exists(identifier):

        print(f"Creating {identifier}")

        with catalog.create_table_transaction(
            identifier=identifier,
            schema=data.schema,
        ) as transaction:

            with transaction.update_spec() as spec:
                spec.add_identity("season")
                spec.add_identity("event_slug")
                spec.add_identity("session_type")

    table = catalog.load_table(identifier)

    print(
        f"Writing {data.num_rows:,} rows "
        "with dynamic partition overwrite..."
    )

    table.dynamic_partition_overwrite(data)

    print("Commit successful.")

    return table


# =========================================================
# Validation
# =========================================================

def validate(
    table,
    dataset,
):

    print()
    print("=" * 70)
    print("READ-BACK VALIDATION")
    print("=" * 70)

    result = table.scan().to_arrow()

    print(f"Table: {dataset}")
    print(f"Rows:  {result.num_rows:,}")

    print()

    print(
        result
        .slice(0, 5)
        .to_pandas()
        .to_string(index=False)
    )

    snapshot = table.current_snapshot()

    if snapshot:
        print()
        print(
            "Snapshot ID:",
            snapshot.snapshot_id,
        )


# =========================================================
# Main
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dataset",
        required=True,
        choices=[
            "results",
            "weather",
        ],
    )

    parser.add_argument(
        "--year",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--event",
        required=True,
    )

    parser.add_argument(
        "--session",
        default="R",
    )

    args = parser.parse_args()

    raw = read_raw(
        args.year,
        args.event,
        args.session,
        args.dataset,
    )

    print()
    print("=" * 70)
    print("NORMALIZATION")
    print("=" * 70)

    if args.dataset == "results":
        data = normalize_results(
            raw,
            args.year,
            args.event,
            args.session,
        )

    else:
        data = normalize_weather(
            raw,
            args.year,
            args.event,
            args.session,
        )

    print(
        f"Normalized rows:    {data.num_rows:,}"
    )

    print(
        f"Normalized columns: {data.num_columns}"
    )

    table = write_iceberg(
        args.dataset,
        data,
    )

    validate(
        table,
        args.dataset,
    )

    print()
    print("=" * 70)
    print("BRONZE PROMOTION COMPLETE")
    print("=" * 70)

    print(
        f"bronze.{args.dataset}"
    )


if __name__ == "__main__":
    main()
