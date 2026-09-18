from __future__ import annotations

import argparse
import io
import os
import re
from pathlib import Path

import boto3
import fastf1
import pandas as pd

from botocore.config import Config
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

BUCKET = os.getenv(
    "SEAWEED_S3_BUCKET",
    "f1-raw",
)

S3_ENDPOINT = os.getenv(
    "SEAWEED_S3_ENDPOINT",
    "http://localhost:8333",
)

ACCESS_KEY = os.getenv(
    "AWS_ACCESS_KEY_ID"
)

SECRET_KEY = os.getenv(
    "AWS_SECRET_ACCESS_KEY"
)


# ============================================================
# FASTF1 CACHE
# ============================================================

CACHE_DIR = Path("data/cache")

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

fastf1.Cache.enable_cache(
    str(CACHE_DIR)
)


# ============================================================
# HELPERS
# ============================================================

def slugify(value: str) -> str:
    """
    Convert an event name into a stable path-safe slug.
    """

    value = value.lower().strip()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    return value.strip("-")


def get_s3():
    """
    Create SeaweedFS S3-compatible client.
    """

    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
        config=Config(
            s3={
                "addressing_style": "path"
            }
        ),
    )


def upload_dataframe(
    s3,
    df: pd.DataFrame,
    key: str,
) -> float:
    """
    Write a DataFrame to an in-memory Parquet file
    and upload it to SeaweedFS.
    """

    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        engine="pyarrow",
        compression="zstd",
        index=False,
    )

    size_mb = (
        buffer.getbuffer().nbytes
        / 1024
        / 1024
    )

    buffer.seek(0)

    s3.upload_fileobj(
        buffer,
        BUCKET,
        key,
    )

    return size_mb


# ============================================================
# DRIVER DISCOVERY
# ============================================================

def get_driver_records(
    session,
) -> list[dict]:
    """
    Build driver metadata from FastF1 session results.

    DriverNumber is used to select laps.
    Abbreviation is used as the canonical driver code.
    """

    records = []

    for _, row in session.results.iterrows():

        driver_number = row.get(
            "DriverNumber"
        )

        driver_code = row.get(
            "Abbreviation"
        )

        team_name = row.get(
            "TeamName"
        )

        result_laps = row.get(
            "Laps"
        )

        if pd.isna(driver_number):
            continue

        if pd.isna(driver_code):
            continue

        driver_number = str(
            driver_number
        ).strip()

        driver_code = str(
            driver_code
        ).strip().upper()

        if pd.isna(team_name):
            team_name = ""
        else:
            team_name = str(
                team_name
            ).strip()

        try:
            if pd.isna(result_laps):
                result_laps = 0
            else:
                result_laps = int(
                    float(result_laps)
                )

        except (
            TypeError,
            ValueError,
        ):
            result_laps = 0

        records.append(
            {
                "driver_number":
                    driver_number,

                "driver_code":
                    driver_code,

                "team_name":
                    team_name,

                "result_laps":
                    result_laps,
            }
        )

    return records


# ============================================================
# DRIVER TELEMETRY EXTRACTION
# ============================================================

def extract_driver(
    session,
    year: int,
    event: str,
    session_type: str,
    driver_number: str,
    driver_code: str,
    team_name: str,
):
    """
    Extract telemetry for an entire driver's race at once.

    IMPORTANT:
    We intentionally use:

        driver_laps.get_telemetry()

    instead of:

        lap.get_telemetry()

    because some individual Monaco laps fail inside FastF1
    with errors involving the Date telemetry column, while
    full-driver telemetry retrieval works correctly.
    """

    driver_laps = (
        session.laps.pick_drivers(
            driver_number
        )
    )

    if driver_laps.empty:

        print(
            f"{driver_code}: "
            "no laps found"
        )

        return None, {
            "laps_total": 0,
            "laps_written": 0,
            "laps_failed": 0,
        }

    # --------------------------------------------------------
    # Retrieve telemetry once for the entire driver
    # --------------------------------------------------------

    try:

        telemetry = (
            driver_laps
            .get_telemetry()
            .copy()
        )

    except Exception as exc:

        print(
            f"{driver_code}: "
            "driver telemetry retrieval failed"
        )

        print(
            f"Reason: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return None, {
            "laps_total":
                len(driver_laps),

            "laps_written":
                0,

            "laps_failed":
                len(driver_laps),
        }

    if telemetry.empty:

        print(
            f"{driver_code}: "
            "telemetry is empty"
        )

        return None, {
            "laps_total":
                len(driver_laps),

            "laps_written":
                0,

            "laps_failed":
                len(driver_laps),
        }

    # --------------------------------------------------------
    # Validate required timing column
    # --------------------------------------------------------

    if "SessionTime" not in telemetry.columns:

        raise RuntimeError(
            f"{driver_code}: "
            "SessionTime missing from telemetry. "
            f"Available columns: "
            f"{telemetry.columns.tolist()}"
        )

    # --------------------------------------------------------
    # Add lakehouse metadata
    # --------------------------------------------------------

    telemetry[
        "Season"
    ] = year

    telemetry[
        "EventName"
    ] = event

    telemetry[
        "EventSlug"
    ] = slugify(
        event
    )

    telemetry[
        "SessionType"
    ] = session_type

    telemetry[
        "Driver"
    ] = driver_code

    telemetry[
        "DriverNumber"
    ] = driver_number

    telemetry[
        "Team"
    ] = team_name

    telemetry[
        "LapNumber"
    ] = pd.NA

    # --------------------------------------------------------
    # Assign telemetry samples to laps
    # --------------------------------------------------------

    laps_total = 0
    laps_written = 0
    laps_failed = 0

    valid_laps = []

    for _, lap in driver_laps.iterlaps():

        lap_number = lap.get(
            "LapNumber"
        )

        lap_start = lap.get(
            "LapStartTime"
        )

        lap_end = lap.get(
            "Time"
        )

        if pd.isna(
            lap_number
        ):
            continue

        laps_total += 1

        if (
            pd.isna(lap_start)
            or pd.isna(lap_end)
        ):

            print(
                f"WARNING: "
                f"{driver_code} "
                f"lap {lap_number}: "
                "missing timing boundaries"
            )

            laps_failed += 1

            continue

        valid_laps.append(
            (
                int(lap_number),
                lap_start,
                lap_end,
            )
        )

    # --------------------------------------------------------
    # Map each valid lap onto driver telemetry
    #
    # Start inclusive, end exclusive prevents samples exactly
    # on a boundary from belonging to two laps.
    # The final lap includes its end boundary.
    # --------------------------------------------------------

    for index, (
        lap_number,
        lap_start,
        lap_end,
    ) in enumerate(valid_laps):

        is_last_lap = (
            index
            == len(valid_laps) - 1
        )

        if is_last_lap:

            mask = (
                (
                    telemetry["SessionTime"]
                    >= lap_start
                )
                &
                (
                    telemetry["SessionTime"]
                    <= lap_end
                )
            )

        else:

            mask = (
                (
                    telemetry["SessionTime"]
                    >= lap_start
                )
                &
                (
                    telemetry["SessionTime"]
                    < lap_end
                )
            )

        sample_count = int(
            mask.sum()
        )

        if sample_count == 0:

            print(
                f"WARNING: "
                f"{driver_code} "
                f"lap {lap_number}: "
                "no telemetry samples"
            )

            laps_failed += 1

            continue

        telemetry.loc[
            mask,
            "LapNumber",
        ] = lap_number

        laps_written += 1

    # --------------------------------------------------------
    # Keep only samples that belong to a known lap
    # --------------------------------------------------------

    telemetry = telemetry[
        telemetry[
            "LapNumber"
        ].notna()
    ].copy()

    if telemetry.empty:

        print(
            f"{driver_code}: "
            "no telemetry samples could be assigned "
            "to race laps"
        )

        return None, {
            "laps_total":
                laps_total,

            "laps_written":
                0,

            "laps_failed":
                laps_failed,
        }

    telemetry[
        "LapNumber"
    ] = (
        telemetry[
            "LapNumber"
        ]
        .astype(
            "int64"
        )
    )

    telemetry = (
        telemetry
        .sort_values(
            [
                "LapNumber",
                "SessionTime",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    stats = {
        "laps_total":
            laps_total,

        "laps_written":
            laps_written,

        "laps_failed":
            laps_failed,
    }

    return telemetry, stats


# ============================================================
# RACE INGESTION
# ============================================================

def ingest_race(
    year: int,
    event: str,
    session_type: str,
    selected_driver: str | None = None,
):
    """
    Ingest telemetry for every driver in one F1 session.
    """

    print()
    print("=" * 75)
    print(
        "FASTF1 FULL-RACE TELEMETRY INGESTION"
    )
    print("=" * 75)

    print(
        f"Season : {year}"
    )

    print(
        f"Event  : {event}"
    )

    print(
        f"Session: {session_type}"
    )

    print()
    print(
        "Loading FastF1 session once..."
    )

    session = fastf1.get_session(
        year,
        event,
        session_type,
    )

    session.load(
        telemetry=True,
        weather=False,
        messages=False,
    )

    print(
        "Session loaded."
    )

    # ========================================================
    # DRIVER DISCOVERY
    # ========================================================

    all_driver_records = (
        get_driver_records(
            session
        )
    )

    driver_records = (
        all_driver_records
    )

    if selected_driver:

        selected_driver = (
            selected_driver
            .strip()
            .upper()
        )

        driver_records = [
            record
            for record
            in all_driver_records
            if record[
                "driver_code"
            ] == selected_driver
        ]

        if not driver_records:

            available = [
                record[
                    "driver_code"
                ]
                for record
                in all_driver_records
            ]

            raise ValueError(
                f"Driver "
                f"'{selected_driver}' "
                f"not found. "
                f"Available drivers: "
                f"{available}"
            )

    if not driver_records:

        raise RuntimeError(
            "No drivers found in session results."
        )

    print()

    print(
        f"Drivers to process: "
        f"{len(driver_records)}"
    )

    print(
        ", ".join(
            record[
                "driver_code"
            ]
            for record
            in driver_records
        )
    )

    # ========================================================
    # S3
    # ========================================================

    s3 = get_s3()

    event_slug = slugify(
        event
    )

    # ========================================================
    # INGESTION COUNTERS
    # ========================================================

    total_rows = 0

    total_size = 0.0

    successful = 0

    total_failed_laps = 0

    summary = []

    failed_drivers = []

    # Drivers that are present in session results but have no
    # actual race laps in FastF1's session.laps dataset are not
    # eligible for telemetry and should not fail the race.
    skipped_no_laps = []

    # ========================================================
    # PROCESS EACH DRIVER
    # ========================================================

    for position, record in enumerate(
        driver_records,
        start=1,
    ):

        driver_number = record[
            "driver_number"
        ]

        driver_code = record[
            "driver_code"
        ]

        team_name = record[
            "team_name"
        ]

        result_laps = record[
            "result_laps"
        ]

        print()
        print("-" * 75)

        print(
            f"[{position}/"
            f"{len(driver_records)}] "
            f"Processing "
            f"{driver_code} "
            f"(#{driver_number})"
        )

        try:

            df, stats = (
                extract_driver(
                    session=session,
                    year=year,
                    event=event,
                    session_type=session_type,
                    driver_number=driver_number,
                    driver_code=driver_code,
                    team_name=team_name,
                )
            )

            total_failed_laps += (
                stats[
                    "laps_failed"
                ]
            )

            # ------------------------------------------------
            # No telemetry generated
            # ------------------------------------------------

            if (
                df is None
                or df.empty
            ):

                # A driver can appear in session.results while
                # having no rows in session.laps. Such a driver
                # has no telemetry-eligible race laps and is
                # therefore skipped rather than failed.
                if stats["laps_total"] == 0:

                    print(
                        f"{driver_code}: "
                        "SKIPPED_NO_LAPS"
                    )

                    skipped_no_laps.append(
                        {
                            "driver":
                                driver_code,

                            "driver_number":
                                driver_number,

                            "result_laps":
                                result_laps,
                        }
                    )

                    continue

                # If FastF1 contains actual lap rows for the
                # driver, telemetry is required. Producing zero
                # telemetry in that case is a genuine failure.
                print(
                    f"{driver_code}: "
                    "no telemetry produced"
                )

                failed_drivers.append(
                    {
                        "driver":
                            driver_code,

                        "driver_number":
                            driver_number,

                        "reason":
                            (
                                f"Driver has "
                                f"{stats['laps_total']} "
                                "FastF1 race lap(s) but "
                                "produced zero telemetry"
                            ),
                    }
                )

                continue

            # ------------------------------------------------
            # Raw object key
            # ------------------------------------------------

            key = (
                f"season={year}/"
                f"event={event_slug}/"
                f"session={session_type}/"
                f"telemetry/"
                f"driver={driver_code}/"
                f"telemetry.parquet"
            )

            # ------------------------------------------------
            # Upload
            # ------------------------------------------------

            size_mb = (
                upload_dataframe(
                    s3=s3,
                    df=df,
                    key=key,
                )
            )

            rows = len(
                df
            )

            print(
                f"{driver_code}: "
                f"{rows:,} rows | "
                f"{size_mb:.2f} MB"
            )

            print(
                f"Laps written: "
                f"{stats['laps_written']}/"
                f"{stats['laps_total']}"
            )

            if (
                stats[
                    "laps_failed"
                ]
                > 0
            ):

                print(
                    f"WARNING: "
                    f"{stats['laps_failed']} "
                    f"lap(s) could not "
                    f"be assigned telemetry"
                )

            print(
                f"s3://"
                f"{BUCKET}/"
                f"{key}"
            )

            total_rows += rows

            total_size += (
                size_mb
            )

            successful += 1

            summary.append(
                {
                    "driver":
                        driver_code,

                    "driver_number":
                        driver_number,

                    "team":
                        team_name,

                    "result_laps":
                        result_laps,

                    "laps_total":
                        stats[
                            "laps_total"
                        ],

                    "laps_written":
                        stats[
                            "laps_written"
                        ],

                    "laps_failed":
                        stats[
                            "laps_failed"
                        ],

                    "rows":
                        rows,

                    "size_mb":
                        round(
                            size_mb,
                            2,
                        ),

                    "object_key":
                        key,
                }
            )

        except Exception as exc:

            print(
                f"{driver_code}: FAILED"
            )

            print(
                f"Reason: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            failed_drivers.append(
                {
                    "driver":
                        driver_code,

                    "driver_number":
                        driver_number,

                    "reason":
                        (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                }
            )

    # ========================================================
    # MANIFEST
    # ========================================================

    if summary:

        manifest = pd.DataFrame(
            summary
        )

        manifest_key = (
            f"season={year}/"
            f"event={event_slug}/"
            f"session={session_type}/"
            f"telemetry/"
            f"_manifest.parquet"
        )

        upload_dataframe(
            s3=s3,
            df=manifest,
            key=manifest_key,
        )

        print()

        print(
            f"Manifest: "
            f"s3://"
            f"{BUCKET}/"
            f"{manifest_key}"
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    eligible_drivers = (
        len(driver_records)
        - len(skipped_no_laps)
    )

    print()
    print("=" * 75)
    print(
        "INGESTION SUMMARY"
    )
    print("=" * 75)

    print(
        f"Session drivers   : "
        f"{len(driver_records)}"
    )

    print(
        f"Eligible drivers  : "
        f"{eligible_drivers}"
    )

    print(
        f"Drivers processed : "
        f"{successful}/"
        f"{eligible_drivers}"
    )

    print(
        f"Skipped no laps   : "
        f"{len(skipped_no_laps)}"
    )

    print(
        f"Telemetry rows    : "
        f"{total_rows:,}"
    )

    print(
        f"Failed laps       : "
        f"{total_failed_laps}"
    )

    print(
        f"Stored data       : "
        f"{total_size:.2f} MB"
    )

    # ========================================================
    # SKIPPED DRIVERS
    # ========================================================

    if skipped_no_laps:

        print()
        print(
            "SKIPPED — NO RACE LAPS"
        )

        print("-" * 75)

        for skipped in skipped_no_laps:

            print(
                f"{skipped['driver']} "
                f"(#{skipped['driver_number']}): "
                "no telemetry-eligible race laps"
            )

    # ========================================================
    # FAILED DRIVERS
    # ========================================================

    if failed_drivers:

        print()
        print(
            "FAILED DRIVERS"
        )

        print("-" * 75)

        for failure in failed_drivers:

            print(
                f"{failure['driver']} "
                f"(#{failure['driver_number']}): "
                f"{failure['reason']}"
            )

    print()

    # ========================================================
    # QUALITY GATE
    # ========================================================

    # Drivers with zero FastF1 race laps are intentionally
    # excluded from the telemetry-eligible population.
    #
    # Every eligible driver must still produce telemetry.
    if failed_drivers:

        raise RuntimeError(
            f"Telemetry ingestion incomplete: "
            f"{len(failed_drivers)} "
            f"driver(s) failed."
        )

    if successful != eligible_drivers:

        raise RuntimeError(
            "Telemetry ingestion incomplete: "
            f"processed "
            f"{successful}/"
            f"{eligible_drivers} "
            f"eligible drivers."
        )

    print(
        "FULL-RACE TELEMETRY "
        "INGESTION COMPLETE"
    )


# ============================================================
# CLI
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Ingest full-race FastF1 telemetry "
            "into SeaweedFS."
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

    parser.add_argument(
        "--driver",
        default=None,
        help=(
            "Optional driver abbreviation "
            "for single-driver testing. "
            "Example: ANT"
        ),
    )

    args = parser.parse_args()

    ingest_race(
        year=args.year,
        event=args.event,
        session_type=args.session,
        selected_driver=args.driver,
    )


if __name__ == "__main__":
    main()
