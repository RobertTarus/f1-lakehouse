from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import query_dataframe
from f1_style import get_driver_styles
from ui_theme import apply_app_theme

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Telemetry Duel | F1 Lakehouse",
    page_icon="🏁",
    layout="wide",
)

apply_app_theme()


# ============================================================
# HELPERS
# ============================================================

def sql_safe(value: str) -> str:
    return str(value).replace("'", "''")


def numeric(
    value,
    default=None,
):
    try:
        if pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def format_lap_time(seconds) -> str:
    value = numeric(seconds)

    if value is None:
        return "N/A"

    minutes = int(value // 60)
    remaining = value % 60

    return (
        f"{minutes}:"
        f"{remaining:06.3f}"
    )


def format_metric(
    value,
    suffix="",
    decimals=1,
) -> str:
    value = numeric(value)

    if value is None:
        return "N/A"

    return f"{value:.{decimals}f}{suffix}"


def fastest_lap_number(
    frame: pd.DataFrame,
) -> int:
    valid = frame.dropna(
        subset=["lap_time_seconds"]
    )

    if valid.empty:
        return int(
            frame["lap_number"].iloc[0]
        )

    idx = (
        pd.to_numeric(
            valid["lap_time_seconds"],
            errors="coerce",
        )
        .idxmin()
    )

    return int(
        valid.loc[
            idx,
            "lap_number",
        ]
    )


def build_lap_label(
    lap_number: int,
    frame: pd.DataFrame,
) -> str:
    row = frame[
        frame["lap_number"]
        == lap_number
    ]

    if row.empty:
        return f"Lap {lap_number}"

    lap_time = (
        row.iloc[0]["lap_time_seconds"]
    )

    return (
        f"Lap {lap_number} · "
        f"{format_lap_time(lap_time)}"
    )


def prepare_telemetry(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    df = frame.copy()

    numeric_columns = [
        "distance",
        "relative_distance",
        "speed_kph",
        "throttle_pct",
        "gear",
        "rpm",
        "drs",
        "x",
        "y",
        "sample_time_ms",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    df = df.dropna(
        subset=[
            "speed_kph",
            "sample_time_ms",
        ]
    )

    if df.empty:
        return df

    # --------------------------------------------
    # Normalize lap progress onto 0 → 1.
    # --------------------------------------------

    relative = df[
        "relative_distance"
    ].copy()

    if (
        relative.notna().sum() > 2
        and relative.max() > 0
    ):
        if relative.max() <= 1.5:
            progress = relative

        elif relative.max() <= 101:
            progress = relative / 100.0

        else:
            progress = (
                relative
                / relative.max()
            )

    else:
        distance = df["distance"]

        max_distance = distance.max()

        if (
            pd.notna(max_distance)
            and max_distance > 0
        ):
            progress = (
                distance
                / max_distance
            )

        else:
            progress = pd.Series(
                np.linspace(
                    0,
                    1,
                    len(df),
                ),
                index=df.index,
            )

    df["lap_progress"] = (
        progress
        .clip(
            lower=0,
            upper=1,
        )
    )

    df["lap_progress_pct"] = (
        df["lap_progress"]
        * 100
    )

    first_time = (
        df["sample_time_ms"]
        .dropna()
        .min()
    )

    df["elapsed_seconds"] = (
        df["sample_time_ms"]
        - first_time
    ) / 1000.0

    df = (
        df.sort_values(
            [
                "lap_progress",
                "sample_time_ms",
            ]
        )
        .drop_duplicates(
            subset=["lap_progress"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return df


def nearest_sample(
    df: pd.DataFrame,
    progress_pct: float,
):
    if df.empty:
        return None

    target = (
        float(progress_pct)
        / 100.0
    )

    idx = (
        df["lap_progress"]
        .sub(target)
        .abs()
        .idxmin()
    )

    return df.loc[idx]


def add_driver_trace(
    fig: go.Figure,
    df: pd.DataFrame,
    y_column: str,
    style: dict,
    y_hover_label: str,
    y_suffix: str = "",
):
    clean = df.dropna(
        subset=[
            "lap_progress_pct",
            y_column,
        ]
    )

    if clean.empty:
        return

    driver = style["driver"]
    team = style["team"]

    fig.add_trace(
        go.Scatter(
            x=clean[
                "lap_progress_pct"
            ],
            y=clean[y_column],
            mode="lines",
            name=(
                f"{style['glyph']} "
                f"{driver} · {team}"
            ),
            line={
                "color": (
                    style[
                        "plot_color"
                    ]
                ),
                "width": 3,
                "dash": (
                    style["dash"]
                ),
            },
            hovertemplate=(
                f"{driver}"
                "<br>Lap: %{x:.1f}%"
                f"<br>{y_hover_label}: "
                f"%{{y:.1f}}{y_suffix}"
                "<extra></extra>"
            ),
        )
    )

    # Add sparse markers so driver identity does not
    # depend on colour.
    marker_step = max(
        len(clean) // 24,
        1,
    )

    markers = clean.iloc[
        ::marker_step
    ]

    fig.add_trace(
        go.Scatter(
            x=markers[
                "lap_progress_pct"
            ],
            y=markers[y_column],
            mode="markers",
            showlegend=False,
            marker={
                "symbol": (
                    style["marker"]
                ),
                "size": 7,
                "color": (
                    style[
                        "plot_color"
                    ]
                ),
                "line": {
                    "width": 1,
                },
            },
            hoverinfo="skip",
        )
    )


def style_chart(
    fig: go.Figure,
    title: str,
    y_title: str,
):
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=420,
        margin={
            "l": 20,
            "r": 20,
            "t": 55,
            "b": 20,
        },
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )

    fig.update_xaxes(
        title="Lap progress (%)",
        range=[0, 100],
        showgrid=True,
    )

    fig.update_yaxes(
        title=y_title,
        showgrid=True,
    )


# ============================================================
# HEADER
# ============================================================

st.title("🏁 Telemetry Duel")

st.caption(
    "Compare two drivers at sample-level resolution. "
    "Team colour communicates team identity; line style, "
    "marker shape and direct labels communicate driver identity."
)


# ============================================================
# AVAILABLE EVENTS
# ============================================================

events = query_dataframe(
    """
    SELECT DISTINCT
        season,
        event_name,
        event_slug

    FROM iceberg.gold.race_driver_performance

    WHERE session_type = 'R'

    ORDER BY
        season DESC,
        event_name
    """
)


if events.empty:
    st.error(
        "No race data is available."
    )

    st.stop()


# ============================================================
# SELECTION CONTROLS
# ============================================================

selector_1, selector_2, selector_3 = (
    st.columns(
        [1, 2, 1]
    )
)


with selector_1:
    seasons = sorted(
        events["season"]
        .unique()
        .tolist(),
        reverse=True,
    )

    selected_season = st.selectbox(
        "Season",
        seasons,
    )


season_events = events[
    events["season"]
    == selected_season
].copy()


with selector_2:
    selected_event_name = st.selectbox(
        "Race",
        season_events[
            "event_name"
        ].tolist(),
    )


selected_event_slug = (
    season_events.loc[
        season_events[
            "event_name"
        ]
        == selected_event_name,
        "event_slug",
    ]
    .iloc[0]
)


with selector_3:
    high_contrast = st.toggle(
        "High-contrast charts",
        value=False,
        help=(
            "Team colours remain visible in labels, "
            "while chart traces use a high-contrast "
            "colour-blind-friendly palette."
        ),
    )


safe_event = sql_safe(
    selected_event_slug
)


# ============================================================
# DRIVER ROSTER
# ============================================================

drivers = query_dataframe(
    f"""
    SELECT DISTINCT
        driver_code,
        full_name,
        team_name

    FROM iceberg.gold.race_driver_performance

    WHERE season = {int(selected_season)}
      AND event_slug = '{safe_event}'
      AND session_type = 'R'

    ORDER BY driver_code
    """
)


if len(drivers) < 2:
    st.warning(
        "At least two drivers are required "
        "for Telemetry Duel."
    )

    st.stop()


driver_lookup = (
    drivers.set_index(
        "driver_code"
    )
    .to_dict(
        orient="index"
    )
)


driver_codes = (
    drivers["driver_code"]
    .tolist()
)


driver_col_a, driver_col_b = (
    st.columns(2)
)


with driver_col_a:
    driver_a = st.selectbox(
        "Driver A",
        driver_codes,
        index=0,
        format_func=lambda code: (
            f"{code} · "
            f"{driver_lookup[code]['team_name']}"
        ),
    )


driver_b_options = [
    code
    for code in driver_codes
    if code != driver_a
]


with driver_col_b:
    driver_b = st.selectbox(
        "Driver B",
        driver_b_options,
        index=0,
        format_func=lambda code: (
            f"{code} · "
            f"{driver_lookup[code]['team_name']}"
        ),
    )


team_a = (
    driver_lookup[
        driver_a
    ]["team_name"]
)

team_b = (
    driver_lookup[
        driver_b
    ]["team_name"]
)


styles = get_driver_styles(
    driver_a,
    team_a,
    driver_b,
    team_b,
    high_contrast=high_contrast,
)


if team_a == team_b:
    st.info(
        f"Teammate comparison: {driver_a} and "
        f"{driver_b} both represent {team_a}. "
        "Driver A uses a solid line + circle; "
        "Driver B uses a dashed line + diamond "
        "and a related team-colour shade."
    )


# ============================================================
# GOLD LAP METRICS
# ============================================================

safe_driver_a = sql_safe(
    driver_a
)

safe_driver_b = sql_safe(
    driver_b
)


lap_metrics = query_dataframe(
    f"""
    SELECT
        driver_code,
        lap_number,
        lap_time_seconds,
        compound,
        tyre_life,
        position,

        telemetry_samples,

        avg_speed_kph,
        max_speed_kph,

        avg_rpm,
        peak_rpm,

        avg_throttle_pct,
        full_throttle_pct,

        braking_pct,
        drs_usage_pct,

        has_lap_record,
        has_lap_timing,
        lap_match_status

    FROM iceberg.gold.lap_telemetry_metrics

    WHERE season = {int(selected_season)}
      AND event_slug = '{safe_event}'
      AND session_type = 'R'
      AND driver_code IN (
          '{safe_driver_a}',
          '{safe_driver_b}'
      )

    ORDER BY
        driver_code,
        lap_number
    """
)


for column in [
    "lap_number",
    "lap_time_seconds",
    "telemetry_samples",
    "avg_speed_kph",
    "max_speed_kph",
    "avg_rpm",
    "peak_rpm",
    "avg_throttle_pct",
    "full_throttle_pct",
    "braking_pct",
    "drs_usage_pct",
]:
    lap_metrics[column] = (
        pd.to_numeric(
            lap_metrics[column],
            errors="coerce",
        )
    )


laps_a = (
    lap_metrics[
        lap_metrics["driver_code"]
        == driver_a
    ]
    .copy()
)

laps_b = (
    lap_metrics[
        lap_metrics["driver_code"]
        == driver_b
    ]
    .copy()
)


if (
    laps_a.empty
    or laps_b.empty
):
    st.error(
        "Telemetry lap metrics are missing "
        "for one of the selected drivers."
    )

    st.stop()


fastest_a = fastest_lap_number(
    laps_a
)

fastest_b = fastest_lap_number(
    laps_b
)


lap_select_a, lap_select_b = (
    st.columns(2)
)


options_a = sorted(
    laps_a[
        "lap_number"
    ]
    .dropna()
    .astype(int)
    .tolist()
)

options_b = sorted(
    laps_b[
        "lap_number"
    ]
    .dropna()
    .astype(int)
    .tolist()
)


with lap_select_a:
    lap_a = st.selectbox(
        f"{driver_a} lap",
        options_a,
        index=options_a.index(
            fastest_a
        ),
        format_func=lambda lap: (
            build_lap_label(
                lap,
                laps_a,
            )
        ),
    )


with lap_select_b:
    lap_b = st.selectbox(
        f"{driver_b} lap",
        options_b,
        index=options_b.index(
            fastest_b
        ),
        format_func=lambda lap: (
            build_lap_label(
                lap,
                laps_b,
            )
        ),
    )


row_a = (
    laps_a[
        laps_a["lap_number"]
        == lap_a
    ]
    .iloc[0]
)

row_b = (
    laps_b[
        laps_b["lap_number"]
        == lap_b
    ]
    .iloc[0]
)


# ============================================================
# DRIVER CARDS
# ============================================================

st.divider()

card_a, card_b = (
    st.columns(2)
)


with card_a:
    style = styles[driver_a]

    st.markdown(
        f"### {style['glyph']} "
        f"{driver_a} · {team_a}"
    )

    st.caption(
        driver_lookup[
            driver_a
        ]["full_name"]
    )

    st.metric(
        "Lap time",
        format_lap_time(
            row_a[
                "lap_time_seconds"
            ]
        ),
    )

    a1, a2, a3 = (
        st.columns(3)
    )

    a1.metric(
        "Max speed",
        format_metric(
            row_a[
                "max_speed_kph"
            ],
            " km/h",
        ),
    )

    a2.metric(
        "Full throttle",
        format_metric(
            row_a[
                "full_throttle_pct"
            ],
            "%",
        ),
    )

    a3.metric(
        "Braking",
        format_metric(
            row_a[
                "braking_pct"
            ],
            "%",
        ),
    )

    st.caption(
        f"{row_a['compound']} · "
        f"Tyre life {format_metric(row_a['tyre_life'], '', 0)} laps"
    )


with card_b:
    style = styles[driver_b]

    lap_a_time = numeric(
        row_a[
            "lap_time_seconds"
        ]
    )

    lap_b_time = numeric(
        row_b[
            "lap_time_seconds"
        ]
    )

    lap_delta = None

    if (
        lap_a_time is not None
        and lap_b_time is not None
    ):
        lap_delta = (
            lap_b_time
            - lap_a_time
        )

    st.markdown(
        f"### {style['glyph']} "
        f"{driver_b} · {team_b}"
    )

    st.caption(
        driver_lookup[
            driver_b
        ]["full_name"]
    )

    st.metric(
        "Lap time",
        format_lap_time(
            row_b[
                "lap_time_seconds"
            ]
        ),
        delta=(
            f"{lap_delta:+.3f}s vs {driver_a}"
            if lap_delta is not None
            else None
        ),
        delta_color="inverse",
    )

    b1, b2, b3 = (
        st.columns(3)
    )

    b1.metric(
        "Max speed",
        format_metric(
            row_b[
                "max_speed_kph"
            ],
            " km/h",
        ),
    )

    b2.metric(
        "Full throttle",
        format_metric(
            row_b[
                "full_throttle_pct"
            ],
            "%",
        ),
    )

    b3.metric(
        "Braking",
        format_metric(
            row_b[
                "braking_pct"
            ],
            "%",
        ),
    )

    st.caption(
        f"{row_b['compound']} · "
        f"Tyre life {format_metric(row_b['tyre_life'], '', 0)} laps"
    )


# ============================================================
# RAW SILVER TELEMETRY
# ============================================================

with st.spinner(
    "Loading sample-level telemetry..."
):
    telemetry_a = query_dataframe(
        f"""
        SELECT
            distance,
            relative_distance,
            sample_time_ms,
            speed_kph,
            throttle_pct,
            brake,
            gear,
            rpm,
            drs,
            x,
            y

        FROM iceberg.silver.silver_telemetry

        WHERE season = {int(selected_season)}
          AND event_slug = '{safe_event}'
          AND session_type = 'R'
          AND driver_code = '{safe_driver_a}'
          AND lap_number = {int(lap_a)}

        ORDER BY sample_time_ms
        """
    )

    telemetry_b = query_dataframe(
        f"""
        SELECT
            distance,
            relative_distance,
            sample_time_ms,
            speed_kph,
            throttle_pct,
            brake,
            gear,
            rpm,
            drs,
            x,
            y

        FROM iceberg.silver.silver_telemetry

        WHERE season = {int(selected_season)}
          AND event_slug = '{safe_event}'
          AND session_type = 'R'
          AND driver_code = '{safe_driver_b}'
          AND lap_number = {int(lap_b)}

        ORDER BY sample_time_ms
        """
    )


telemetry_a = prepare_telemetry(
    telemetry_a
)

telemetry_b = prepare_telemetry(
    telemetry_b
)


if (
    telemetry_a.empty
    or telemetry_b.empty
):
    st.warning(
        "Raw telemetry is unavailable "
        "for one of these laps."
    )

    st.stop()


# ============================================================
# CIRCUIT EXPLORER
# ============================================================

st.divider()

st.subheader(
    "Interactive Circuit Explorer"
)

st.caption(
    "Move through the lap to inspect both drivers "
    "at approximately the same circuit position."
)


playhead = st.slider(
    "Lap position",
    min_value=0,
    max_value=100,
    value=25,
    step=1,
    format="%d%%",
)


point_a = nearest_sample(
    telemetry_a,
    playhead,
)

point_b = nearest_sample(
    telemetry_b,
    playhead,
)


fig_track = go.Figure()


for driver, frame in [
    (
        driver_a,
        telemetry_a,
    ),
    (
        driver_b,
        telemetry_b,
    ),
]:
    style = styles[driver]

    xy = frame.dropna(
        subset=["x", "y"]
    )

    if xy.empty:
        continue

    hover_text = [
        (
            f"{driver}"
            f"<br>Lap position: "
            f"{row.lap_progress_pct:.1f}%"
            f"<br>Speed: "
            f"{row.speed_kph:.0f} km/h"
            f"<br>Throttle: "
            f"{row.throttle_pct:.0f}%"
            f"<br>Gear: "
            f"{row.gear:.0f}"
            f"<br>Brake: "
            f"{'ON' if bool(row.brake) else 'OFF'}"
        )
        for row in xy.itertuples()
    ]

    fig_track.add_trace(
        go.Scatter(
            x=xy["x"],
            y=xy["y"],
            mode="lines",
            name=(
                f"{style['glyph']} "
                f"{driver} · "
                f"{style['team']}"
            ),
            text=hover_text,
            hovertemplate=(
                "%{text}"
                "<extra></extra>"
            ),
            line={
                "color": (
                    style[
                        "plot_color"
                    ]
                ),
                "width": 4,
                "dash": (
                    style["dash"]
                ),
            },
        )
    )


for driver, point in [
    (
        driver_a,
        point_a,
    ),
    (
        driver_b,
        point_b,
    ),
]:
    if point is None:
        continue

    if (
        pd.isna(point["x"])
        or pd.isna(point["y"])
    ):
        continue

    style = styles[driver]

    fig_track.add_trace(
        go.Scatter(
            x=[point["x"]],
            y=[point["y"]],
            mode="markers+text",
            text=[driver],
            textposition="top center",
            showlegend=False,
            marker={
                "size": 17,
                "symbol": (
                    style[
                        "marker"
                    ]
                ),
                "color": (
                    style[
                        "plot_color"
                    ]
                ),
                "line": {
                    "width": 2,
                    "color": "#FFFFFF",
                },
            },
            hovertemplate=(
                f"{driver}"
                f"<br>Speed: "
                f"{numeric(point['speed_kph'], 0):.0f} km/h"
                f"<br>Throttle: "
                f"{numeric(point['throttle_pct'], 0):.0f}%"
                f"<br>Gear: "
                f"{numeric(point['gear'], 0):.0f}"
                "<extra></extra>"
            ),
        )
    )


fig_track.update_layout(
    template="plotly_white",
    height=600,
    margin={
        "l": 10,
        "r": 10,
        "t": 20,
        "b": 10,
    },
    legend={
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.01,
    },
)

fig_track.update_xaxes(
    visible=False,
    scaleanchor="y",
    scaleratio=1,
)

fig_track.update_yaxes(
    visible=False,
)


st.plotly_chart(
    fig_track,
    use_container_width=True,
)


# ============================================================
# PLAYHEAD TELEMETRY
# ============================================================

live_a, live_b = (
    st.columns(2)
)


with live_a:
    style = styles[driver_a]

    st.markdown(
        f"**{style['glyph']} "
        f"{driver_a} at {playhead}%**"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Speed",
        format_metric(
            point_a[
                "speed_kph"
            ],
            " km/h",
            0,
        ),
    )

    c2.metric(
        "Throttle",
        format_metric(
            point_a[
                "throttle_pct"
            ],
            "%",
            0,
        ),
    )

    c3.metric(
        "Gear",
        format_metric(
            point_a[
                "gear"
            ],
            "",
            0,
        ),
    )


with live_b:
    style = styles[driver_b]

    st.markdown(
        f"**{style['glyph']} "
        f"{driver_b} at {playhead}%**"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Speed",
        format_metric(
            point_b[
                "speed_kph"
            ],
            " km/h",
            0,
        ),
    )

    c2.metric(
        "Throttle",
        format_metric(
            point_b[
                "throttle_pct"
            ],
            "%",
            0,
        ),
    )

    c3.metric(
        "Gear",
        format_metric(
            point_b[
                "gear"
            ],
            "",
            0,
        ),
    )


# ============================================================
# SPEED TRACE
# ============================================================

st.divider()

fig_speed = go.Figure()

add_driver_trace(
    fig_speed,
    telemetry_a,
    "speed_kph",
    styles[driver_a],
    "Speed",
    " km/h",
)

add_driver_trace(
    fig_speed,
    telemetry_b,
    "speed_kph",
    styles[driver_b],
    "Speed",
    " km/h",
)

style_chart(
    fig_speed,
    "Speed Comparison",
    "Speed (km/h)",
)

st.plotly_chart(
    fig_speed,
    use_container_width=True,
)


# ============================================================
# THROTTLE
# ============================================================

fig_throttle = go.Figure()

add_driver_trace(
    fig_throttle,
    telemetry_a,
    "throttle_pct",
    styles[driver_a],
    "Throttle",
    "%",
)

add_driver_trace(
    fig_throttle,
    telemetry_b,
    "throttle_pct",
    styles[driver_b],
    "Throttle",
    "%",
)

style_chart(
    fig_throttle,
    "Throttle Application",
    "Throttle (%)",
)

fig_throttle.update_yaxes(
    range=[0, 100],
)

st.plotly_chart(
    fig_throttle,
    use_container_width=True,
)


# ============================================================
# RPM
# ============================================================

fig_rpm = go.Figure()

add_driver_trace(
    fig_rpm,
    telemetry_a,
    "rpm",
    styles[driver_a],
    "RPM",
)

add_driver_trace(
    fig_rpm,
    telemetry_b,
    "rpm",
    styles[driver_b],
    "RPM",
)

style_chart(
    fig_rpm,
    "Engine Speed",
    "RPM",
)

st.plotly_chart(
    fig_rpm,
    use_container_width=True,
)


# ============================================================
# BRAKING
# ============================================================

brake_a = telemetry_a.copy()
brake_b = telemetry_b.copy()

brake_a["brake_pct"] = (
    brake_a["brake"]
    .fillna(False)
    .astype(bool)
    .astype(int)
    * 100
)

brake_b["brake_pct"] = (
    brake_b["brake"]
    .fillna(False)
    .astype(bool)
    .astype(int)
    * 100
)


fig_brake = go.Figure()

add_driver_trace(
    fig_brake,
    brake_a,
    "brake_pct",
    styles[driver_a],
    "Brake",
    "%",
)

add_driver_trace(
    fig_brake,
    brake_b,
    "brake_pct",
    styles[driver_b],
    "Brake",
    "%",
)

style_chart(
    fig_brake,
    "Braking Zones",
    "Brake",
)

fig_brake.update_yaxes(
    range=[0, 105],
    tickvals=[0, 100],
    ticktext=[
        "OFF",
        "ON",
    ],
)

st.plotly_chart(
    fig_brake,
    use_container_width=True,
)


# ============================================================
# APPROXIMATE CUMULATIVE DELTA
# ============================================================

st.divider()

st.subheader(
    "Where Was the Lap Won?"
)

st.caption(
    "Approximate cumulative telemetry delta aligned by "
    "normalized lap distance. Positive values mean "
    f"{driver_a} reached that point sooner; negative "
    f"values mean {driver_b} reached it sooner."
)


minimum_progress = max(
    telemetry_a[
        "lap_progress"
    ].min(),
    telemetry_b[
        "lap_progress"
    ].min(),
)

maximum_progress = min(
    telemetry_a[
        "lap_progress"
    ].max(),
    telemetry_b[
        "lap_progress"
    ].max(),
)


if (
    pd.notna(minimum_progress)
    and pd.notna(maximum_progress)
    and maximum_progress
    > minimum_progress
):
    progress_grid = np.linspace(
        minimum_progress,
        maximum_progress,
        350,
    )

    elapsed_a = np.interp(
        progress_grid,
        telemetry_a[
            "lap_progress"
        ],
        telemetry_a[
            "elapsed_seconds"
        ],
    )

    elapsed_b = np.interp(
        progress_grid,
        telemetry_b[
            "lap_progress"
        ],
        telemetry_b[
            "elapsed_seconds"
        ],
    )

    # Positive = Driver A reached the same point sooner.
    advantage_a = (
        elapsed_b
        - elapsed_a
    )

    delta_frame = pd.DataFrame(
        {
            "progress": (
                progress_grid
                * 100
            ),
            "delta": advantage_a,
        }
    )

    positive = (
        delta_frame[
            "delta"
        ]
        .where(
            delta_frame[
                "delta"
            ]
            >= 0
        )
    )

    negative = (
        delta_frame[
            "delta"
        ]
        .where(
            delta_frame[
                "delta"
            ]
            < 0
        )
    )

    fig_delta = go.Figure()

    fig_delta.add_trace(
        go.Scatter(
            x=delta_frame[
                "progress"
            ],
            y=positive,
            mode="lines",
            name=(
                f"{driver_a} ahead"
            ),
            line={
                "color": (
                    styles[
                        driver_a
                    ][
                        "plot_color"
                    ]
                ),
                "width": 3,
            },
            fill="tozeroy",
            hovertemplate=(
                f"{driver_a} advantage"
                "<br>Lap: %{x:.1f}%"
                "<br>Delta: %{y:.3f}s"
                "<extra></extra>"
            ),
        )
    )

    fig_delta.add_trace(
        go.Scatter(
            x=delta_frame[
                "progress"
            ],
            y=negative,
            mode="lines",
            name=(
                f"{driver_b} ahead"
            ),
            line={
                "color": (
                    styles[
                        driver_b
                    ][
                        "plot_color"
                    ]
                ),
                "width": 3,
                "dash": "dash",
            },
            fill="tozeroy",
            hovertemplate=(
                f"{driver_b} advantage"
                "<br>Lap: %{x:.1f}%"
                "<br>Delta: %{y:.3f}s"
                "<extra></extra>"
            ),
        )
    )

    fig_delta.add_hline(
        y=0,
        line_width=1,
        line_dash="dot",
    )

    style_chart(
        fig_delta,
        (
            f"Cumulative Advantage — "
            f"{driver_a} vs {driver_b}"
        ),
        (
            f"Advantage to {driver_a} (s)"
        ),
    )

    st.plotly_chart(
        fig_delta,
        use_container_width=True,
    )


# ============================================================
# SECTOR COMPARISON
# ============================================================

sector_data = query_dataframe(
    f"""
    SELECT
        driver_code,
        lap_number,
        lap_time_ms,
        sector_1_ms,
        sector_2_ms,
        sector_3_ms

    FROM iceberg.silver.silver_laps

    WHERE season = {int(selected_season)}
      AND event_slug = '{safe_event}'
      AND session_type = 'R'
    """
)


for column in [
    "lap_number",
    "lap_time_ms",
    "sector_1_ms",
    "sector_2_ms",
    "sector_3_ms",
]:
    sector_data[column] = (
        pd.to_numeric(
            sector_data[column],
            errors="coerce",
        )
    )


sector_a = sector_data[
    (
        sector_data[
            "driver_code"
        ]
        == driver_a
    )
    & (
        sector_data[
            "lap_number"
        ]
        == lap_a
    )
]


sector_b = sector_data[
    (
        sector_data[
            "driver_code"
        ]
        == driver_b
    )
    & (
        sector_data[
            "lap_number"
        ]
        == lap_b
    )
]


if (
    not sector_a.empty
    and not sector_b.empty
):
    sector_a = sector_a.iloc[0]
    sector_b = sector_b.iloc[0]

    comparison_rows = []

    for label, column in [
        (
            "Sector 1",
            "sector_1_ms",
        ),
        (
            "Sector 2",
            "sector_2_ms",
        ),
        (
            "Sector 3",
            "sector_3_ms",
        ),
    ]:
        time_a = numeric(
            sector_a[column]
        )

        time_b = numeric(
            sector_b[column]
        )

        if (
            time_a is None
            or time_b is None
        ):
            comparison_rows.append(
                {
                    "Sector": label,
                    driver_a: None,
                    driver_b: None,
                    "Difference": None,
                    "Advantage": "N/A",
                }
            )

            continue

        seconds_a = (
            time_a / 1000
        )

        seconds_b = (
            time_b / 1000
        )

        delta = (
            seconds_b
            - seconds_a
        )

        if delta > 0:
            advantage = (
                f"{driver_a} "
                f"by {delta:.3f}s"
            )

        elif delta < 0:
            advantage = (
                f"{driver_b} "
                f"by {abs(delta):.3f}s"
            )

        else:
            advantage = "Equal"

        comparison_rows.append(
            {
                "Sector": label,
                driver_a: round(
                    seconds_a,
                    3,
                ),
                driver_b: round(
                    seconds_b,
                    3,
                ),
                "Difference": round(
                    delta,
                    3,
                ),
                "Advantage": advantage,
            }
        )

    st.markdown(
        "#### Sector Breakdown"
    )

    st.dataframe(
        pd.DataFrame(
            comparison_rows
        ),
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# THEORETICAL PERFECT LAP
# ============================================================

st.divider()

st.subheader(
    "Theoretical Perfect Lap"
)

st.caption(
    "Combines the fastest recorded sector from any "
    "driver/lap in the selected race."
)


perfect_rows = []
perfect_total_ms = 0.0
perfect_valid = True


for label, column in [
    (
        "Sector 1",
        "sector_1_ms",
    ),
    (
        "Sector 2",
        "sector_2_ms",
    ),
    (
        "Sector 3",
        "sector_3_ms",
    ),
]:
    valid = sector_data[
        sector_data[column]
        .notna()
        & (
            sector_data[column]
            > 0
        )
    ]

    if valid.empty:
        perfect_valid = False
        continue

    idx = valid[
        column
    ].idxmin()

    row = valid.loc[idx]

    sector_ms = float(
        row[column]
    )

    perfect_total_ms += (
        sector_ms
    )

    perfect_rows.append(
        {
            "Sector": label,
            "Driver": (
                row[
                    "driver_code"
                ]
            ),
            "Lap": int(
                row[
                    "lap_number"
                ]
            ),
            "Time (s)": round(
                sector_ms
                / 1000,
                3,
            ),
        }
    )


valid_lap_times = sector_data[
    sector_data[
        "lap_time_ms"
    ].notna()
    & (
        sector_data[
            "lap_time_ms"
        ]
        > 0
    )
]


if (
    perfect_valid
    and perfect_rows
    and not valid_lap_times.empty
):
    fastest_idx = (
        valid_lap_times[
            "lap_time_ms"
        ]
        .idxmin()
    )

    actual_fastest = (
        valid_lap_times.loc[
            fastest_idx
        ]
    )

    actual_fastest_ms = float(
        actual_fastest[
            "lap_time_ms"
        ]
    )

    perfect_seconds = (
        perfect_total_ms
        / 1000
    )

    actual_seconds = (
        actual_fastest_ms
        / 1000
    )

    theoretical_gain = (
        actual_seconds
        - perfect_seconds
    )

    perfect_1, perfect_2, perfect_3 = (
        st.columns(3)
    )

    perfect_1.metric(
        "Actual fastest lap",
        format_lap_time(
            actual_seconds
        ),
        help=(
            f"{actual_fastest['driver_code']} "
            f"· Lap "
            f"{int(actual_fastest['lap_number'])}"
        ),
    )

    perfect_2.metric(
        "Theoretical best",
        format_lap_time(
            perfect_seconds
        ),
    )

    perfect_3.metric(
        "Potential",
        (
            f"{max(theoretical_gain, 0):.3f}s"
        ),
    )

    st.dataframe(
        pd.DataFrame(
            perfect_rows
        ),
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# ACCESSIBILITY EXPLANATION
# ============================================================

with st.expander(
    "How driver identification works"
):
    st.markdown(
        f"""
**{driver_a}**

- Team: `{team_a}`
- Marker: `● circle`
- Line: `solid`

**{driver_b}**

- Team: `{team_b}`
- Marker: `◆ diamond`
- Line: `dashed`

Colours are never the only visual distinction. This means
drivers remain identifiable for visitors with colour-vision
deficiencies and when charts are printed in grayscale.

When two drivers are teammates, both remain in the same team
colour family while line pattern, marker shape and direct
driver labels provide the primary distinction.
        """
    )


st.divider()

st.caption(
    "FastF1 → SeaweedFS → Apache Iceberg → "
    "Trino → dbt → Streamlit"
)
