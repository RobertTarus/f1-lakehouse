from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone

import fastf1
import pandas as pd


def slugify_event(name: str) -> str:
    """Convert an F1 event name to the slug format used in the lakehouse."""
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _race_start_utc(row) -> datetime | None:
    """
    Find the Race session in a FastF1 schedule row and return its UTC start time.

    This does not assume that Race is always stored in a particular
    Session1..Session5 slot.
    """
    for number in range(1, 6):
        session_name = row.get(f"Session{number}")

        if str(session_name).strip().lower() != "race":
            continue

        value = row.get(f"Session{number}DateUtc")

        if value is None or pd.isna(value):
            return None

        timestamp = pd.Timestamp(value)

        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")

        return timestamp.to_pydatetime()

    return None


def get_completed_races(
    year: int,
    availability_delay_hours: int = 6,
) -> list[dict]:
    """
    Return championship races whose race sessions should already be available.

    A small delay is applied after the scheduled race start so the pipeline
    does not attempt ingestion immediately when a race begins.
    """
    schedule = fastf1.get_event_schedule(year)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=availability_delay_hours)

    races: list[dict] = []

    for _, row in schedule.iterrows():
        round_number = int(row.get("RoundNumber", 0) or 0)

        # Skip testing and non-championship schedule entries.
        if round_number <= 0:
            continue

        event_name = str(row["EventName"])
        race_start = _race_start_utc(row)

        if race_start is None:
            continue

        if race_start > cutoff:
            continue

        races.append(
            {
                "year": year,
                "round": round_number,
                "event": event_name,
                "event_slug": slugify_event(event_name),
                "session": "R",
                "race_start_utc": race_start.isoformat(),
            }
        )

    return sorted(races, key=lambda race: race["round"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover completed Formula 1 races."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--availability-delay-hours",
        type=int,
        default=6,
    )

    args = parser.parse_args()

    races = get_completed_races(
        args.year,
        availability_delay_hours=args.availability_delay_hours,
    )

    print()
    print(f"Completed races discovered for {args.year}: {len(races)}")
    print()

    for race in races:
        print(
            f"Round {race['round']:>2}: "
            f"{race['event']:<30} "
            f"{race['event_slug']}"
        )


if __name__ == "__main__":
    main()
