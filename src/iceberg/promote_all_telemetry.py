import argparse
import io
import os
import subprocess
import sys

import boto3
import pandas as pd
import pyarrow.parquet as pq

from botocore.config import Config
from dotenv import load_dotenv


load_dotenv()


def get_s3():

    return boto3.client(
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


def slugify(value):

    import re

    value = value.lower().strip()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    return value.strip("-")


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

    prefix = (
        f"season={args.year}/"
        f"event={slugify(args.event)}/"
        f"session={args.session}/"
        f"telemetry/"
    )

    manifest_key = (
        prefix
        + "_manifest.parquet"
    )

    print()
    print("=" * 70)
    print("READ TELEMETRY MANIFEST")
    print("=" * 70)

    response = get_s3().get_object(
        Bucket=bucket,
        Key=manifest_key,
    )

    payload = response["Body"].read()

    manifest = pq.read_table(
        io.BytesIO(payload)
    ).to_pandas()

    print(
        manifest[
            ["driver", "rows", "size_mb"]
        ].to_string(index=False)
    )

    print()
    print("=" * 70)
    print("PROMOTING DRIVERS")
    print("=" * 70)

    successes = 0
    failures = []

    for number, driver in enumerate(
        manifest["driver"],
        start=1,
    ):

        print()
        print(
            f"[{number}/{len(manifest)}] "
            f"{driver}"
        )

        command = [
            sys.executable,
            "src/iceberg/promote_telemetry.py",

            "--year",
            str(args.year),

            "--event",
            args.event,

            "--session",
            args.session,

            "--driver",
            driver,
        ]

        result = subprocess.run(
            command,
            check=False,
        )

        if result.returncode == 0:

            successes += 1

        else:

            failures.append(
                driver
            )

    print()
    print("=" * 70)
    print("PROMOTION SUMMARY")
    print("=" * 70)

    print(
        f"Successful: "
        f"{successes}/{len(manifest)}"
    )

    if failures:

        print(
            "Failed:",
            ", ".join(failures),
        )

        raise SystemExit(1)

    print()
    print(
        "FULL-RACE ICEBERG "
        "PROMOTION COMPLETE"
    )


if __name__ == "__main__":
    main()
