import io
import os

import boto3
import pyarrow.parquet as pq

from botocore.config import Config
from dotenv import load_dotenv


load_dotenv()


bucket = os.getenv(
    "SEAWEED_S3_BUCKET",
    "f1-raw",
)

key = (
    "season=2026/"
    "event=italian-grand-prix/"
    "session=R/"
    "telemetry/"
    "driver=HAM/"
    "telemetry.parquet"
)


s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv(
        "SEAWEED_S3_ENDPOINT",
        "http://localhost:8333",
    ),
    aws_access_key_id=os.getenv(
        "AWS_ACCESS_KEY_ID"
    ),
    aws_secret_access_key=os.getenv(
        "AWS_SECRET_ACCESS_KEY"
    ),
    region_name="us-east-1",
    config=Config(
        s3={"addressing_style": "path"}
    ),
)


response = s3.get_object(
    Bucket=bucket,
    Key=key,
)

payload = response["Body"].read()

parquet_file = pq.ParquetFile(
    io.BytesIO(payload)
)


print()
print("=" * 80)
print("TELEMETRY PARQUET")
print("=" * 80)

print(
    f"Rows:       "
    f"{parquet_file.metadata.num_rows:,}"
)

print(
    f"Columns:    "
    f"{parquet_file.metadata.num_columns}"
)

print(
    f"Row groups: "
    f"{parquet_file.metadata.num_row_groups}"
)

print(
    f"Size:       "
    f"{len(payload) / 1024 / 1024:.2f} MB"
)

print()
print("SCHEMA")
print("-" * 80)

print(
    parquet_file.schema_arrow
)
