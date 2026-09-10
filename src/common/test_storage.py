import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv(
    "SEAWEED_S3_ENDPOINT",
    "http://localhost:8333",
)

bucket = os.getenv(
    "SEAWEED_S3_BUCKET",
    "f1-raw",
)

access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

print(f"Connecting to SeaweedFS: {endpoint}")

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name="us-east-1",
    config=Config(
        s3={"addressing_style": "path"}
    ),
)

response = s3.list_buckets()

existing_buckets = [
    item["Name"]
    for item in response.get("Buckets", [])
]

print("Existing buckets:", existing_buckets)

if bucket not in existing_buckets:
    print(f"Creating bucket: {bucket}")
    s3.create_bucket(Bucket=bucket)

response = s3.list_buckets()

print("\nBuckets:")

for item in response.get("Buckets", []):
    print(f" - {item['Name']}")

print(f"\nBucket ready: {bucket}")
print("SeaweedFS S3 connection successful.")
