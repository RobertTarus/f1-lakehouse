from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import race_schedule


def test_slugify_event():
    assert (
        race_schedule.slugify_event(
            "Canadian Grand Prix"
        )
        == "canadian-grand-prix"
    )

    assert (
        race_schedule.slugify_event(
            "Belgian Grand Prix"
        )
        == "belgian-grand-prix"
    )


def test_slugify_event_normalizes_spacing_and_punctuation():
    result = race_schedule.slugify_event(
        "  São Paulo Grand Prix!  "
    )

    assert result
    assert result == result.lower()
    assert " " not in result


def test_race_start_utc_finds_race_session():
    row = pd.Series(
        {
            "Session1": "Practice 1",
            "Session1DateUtc": pd.Timestamp(
                "2026-06-12T15:00:00Z"
            ),
            "Session2": "Practice 2",
            "Session2DateUtc": pd.Timestamp(
                "2026-06-13T15:00:00Z"
            ),
            "Session3": "Qualifying",
            "Session3DateUtc": pd.Timestamp(
                "2026-06-14T18:00:00Z"
            ),
            "Session4": "Race",
            "Session4DateUtc": pd.Timestamp(
                "2026-06-15T18:00:00Z"
            ),
            "Session5": None,
            "Session5DateUtc": pd.NaT,
        }
    )

    result = race_schedule._race_start_utc(
        row
    )

    assert result == datetime(
        2026,
        6,
        15,
        18,
        0,
        tzinfo=timezone.utc,
    )


def test_race_start_utc_returns_none_without_race():
    row = pd.Series(
        {
            "Session1": "Practice 1",
            "Session1DateUtc": pd.Timestamp(
                "2026-06-12T15:00:00Z"
            ),
            "Session2": "Qualifying",
            "Session2DateUtc": pd.Timestamp(
                "2026-06-13T15:00:00Z"
            ),
            "Session3": None,
            "Session3DateUtc": pd.NaT,
            "Session4": None,
            "Session4DateUtc": pd.NaT,
            "Session5": None,
            "Session5DateUtc": pd.NaT,
        }
    )

    assert (
        race_schedule._race_start_utc(
            row
        )
        is None
    )
