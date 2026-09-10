import os

from dotenv import load_dotenv
from pyiceberg.catalog.rest import RestCatalog


load_dotenv()


catalog = RestCatalog(
    name="f1",

    uri=os.getenv(
        "ICEBERG_CATALOG_URI",
        "http://localhost:8181",
    ),

    warehouse=(
        "s3://"
        + os.getenv(
            "SEAWEED_TABLE_BUCKET",
            "f1-iceberg",
        )
    ),

    credential=(
        f"{os.getenv('AWS_ACCESS_KEY_ID')}:"
        f"{os.getenv('AWS_SECRET_ACCESS_KEY')}"
    ),

    **{
        "s3.endpoint": os.getenv(
            "SEAWEED_S3_ENDPOINT",
            "http://localhost:8333",
        ),

        "s3.access-key-id":
            os.getenv("AWS_ACCESS_KEY_ID"),

        "s3.secret-access-key":
            os.getenv("AWS_SECRET_ACCESS_KEY"),

        "s3.path-style-access": "true",

        "s3.region": "us-east-1",
    },
)


print()
print("=" * 70)
print("F1 ICEBERG CATALOG")
print("=" * 70)


for namespace in catalog.list_namespaces():

    print()
    print(
        "Namespace:",
        ".".join(namespace),
    )

    tables = catalog.list_tables(
        namespace
    )

    for table_id in tables:

        identifier = ".".join(table_id)

        table = catalog.load_table(
            table_id
        )

        count = table.scan().to_arrow().num_rows

        snapshot = table.current_snapshot()

        print()
        print(f"  Table:    {identifier}")
        print(f"  Rows:     {count:,}")

        if snapshot:
            print(
                f"  Snapshot: {snapshot.snapshot_id}"
            )
