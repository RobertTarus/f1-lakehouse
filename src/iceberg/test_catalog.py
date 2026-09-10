import os

from dotenv import load_dotenv
from pyiceberg.catalog.rest import RestCatalog


load_dotenv()


access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

catalog_uri = os.getenv(
    "ICEBERG_CATALOG_URI",
    "http://localhost:8181",
)

warehouse = os.getenv(
    "SEAWEED_TABLE_BUCKET",
    "f1-iceberg",
)


catalog = RestCatalog(
    name="f1",
    uri=catalog_uri,
    warehouse=f"s3://{warehouse}",
    credential=f"{access_key}:{secret_key}",
    **{
        "s3.endpoint": os.getenv(
            "SEAWEED_S3_ENDPOINT",
            "http://localhost:8333",
        ),
        "s3.access-key-id": access_key,
        "s3.secret-access-key": secret_key,
        "s3.path-style-access": "true",
        "s3.region": "us-east-1",
    },
)


print("Connected to Iceberg catalog")
print(f"Catalog:   {catalog_uri}")
print(f"Warehouse: s3://{warehouse}")

print("\nExisting namespaces:")

namespaces = catalog.list_namespaces()

if not namespaces:
    print("  none")
else:
    for namespace in namespaces:
        print(f"  {namespace}")


catalog.create_namespace_if_not_exists("bronze")

print("\nNamespaces after setup:")

for namespace in catalog.list_namespaces():
    print(f"  {namespace}")

print("\nIceberg catalog connection successful.")
