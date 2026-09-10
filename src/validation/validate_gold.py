import os
import sys

from trino.dbapi import connect


host = os.getenv(
    "TRINO_HOST",
    "localhost",
)

port = int(
    os.getenv(
        "TRINO_PORT",
        "8081",
    )
)


conn = connect(
    host=host,
    port=port,
    user="f1_validation",
    catalog="iceberg",
    schema="gold",
    http_scheme="http",
)

cursor = conn.cursor()


checks = {

    "race_driver_performance":
        """
        SELECT COUNT(*)
        FROM iceberg.gold.race_driver_performance
        """,

    "lap_telemetry_metrics":
        """
        SELECT COUNT(*)
        FROM iceberg.gold.lap_telemetry_metrics
        """,
}


failed = False


print()
print("=" * 70)
print("GOLD LAYER VALIDATION")
print("=" * 70)


for table, query in checks.items():

    cursor.execute(query)

    count = cursor.fetchone()[0]

    print(
        f"{table:<35} "
        f"{count:>10,} rows"
    )

    if count <= 0:
        failed = True


if failed:

    print()
    print("VALIDATION FAILED")

    sys.exit(1)


print()
print("GOLD LAYER VALIDATION PASSED")
