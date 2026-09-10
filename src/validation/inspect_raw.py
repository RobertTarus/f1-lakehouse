import argparse
import io
import os
import re

import boto3
import pyarrow.parquet as pq
from botocore.config import Config
from dotenv import load_dotenv


load_dotenv()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv(
            "SEAWEED_S3_ENDPOINT",
            "http://localhost:8333",
        ),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"}
        ),
    )


def inspect_parquet(s3, bucket: str, key: str):
    print()
    print("=" * 90)
    print(key)
    print("=" * 90)

    response = s3.get_object(
        Bucket=bucket,
        Key=key,
    )

    payload = response["Body"].read()

    parquet_file = pq.ParquetFile(
        io.BytesIO(payload)
    )

    print(f"Rows:       {parquet_file.metadata.num_rows:,}")
    print(f"Columns:    {parquet_file.metadata.num_columns}")
    print(f"Row groups: {parquet_file.metadata.num_row_groups}")
    print(
        f"Size:       {len(payload) / (1024 * 1024):.2f} MB"
    )

    print("\nArrow schema:")
    print(parquet_file.schema_arrow)

    table = parquet_file.read()

    print("\nFirst 3 rows:")
    print(
        table.slice(0, 3)
        .to_pandas()
        .to_string(index=False)
    )


def main():
    parser = argparse.ArgumentParser()

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

    args = parser.parse_args()

    bucket = os.getenv(
        "SEAWEED_S3_BUCKET",
        "f1-raw",
    )

    event_slug = slugify(args.event)

    prefix = (
        f"season={args.year}/"
        f"event={event_slug}/"
        f"session={args.session}"
    )

    datasets = [
        "laps",
        "results",
        "weather",
    ]

    s3 = get_s3_client()

    for dataset in datasets:
        key = f"{prefix}/{dataset}.parquet"

        inspect_parquet(
            s3,
            bucket,
            key,
        )


if __name__ == "__main__":
    main()
