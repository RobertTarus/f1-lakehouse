import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

bucket = os.getenv("SEAWEED_S3_BUCKET", "f1-raw")

s3 = boto3.client(
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

response = s3.list_objects_v2(
    Bucket=bucket
)

print(f"\ns3://{bucket}/\n")

for obj in response.get("Contents", []):
    size_mb = obj["Size"] / (1024 * 1024)

    print(
        f"{obj['Key']:<80} "
        f"{size_mb:>8.2f} MB"
    )
