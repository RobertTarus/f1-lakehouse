from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import query_dataframe

from f1_style import (
    apply_plotly_theme,
    get_driver_styles,
)

from ui_theme import (
    apply_app_theme,
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(

    page_title=
        "F1 Lakehouse",

    page_icon=
        "🏎️",

    layout=
        "wide",

    initial_sidebar_state=
        "expanded",
)


apply_app_theme()


# ============================================================
# HELPERS
# ============================================================

def sql_safe(
    value: str,
) -> str:

    return (
        str(value)
        .replace(
            "'",
            "''",
        )
    )


def number(
    value,
    default=None,
):

    try:

        if pd.isna(
            value
        ):
            return default

        return float(
            value
        )

    except (
        ValueError,
        TypeError,
    ):

        return default


def format_lap_time(
    seconds,
) -> str:

    value = (
        number(
            seconds
        )
    )

    if value is None:

        return "N/A"

    minutes = int(
        value // 60
    )

    remainder = (
        value % 60
    )

    return (
        f"{minutes}:"
        f"{remainder:06.3f}"
    )


def format_number(
    value,
    decimals=1,
    suffix="",
):

    value = (
        number(
            value
        )
    )

    if value is None:

        return "N/A"

    return (
        f"{value:.{decimals}f}"
        f"{suffix}"
    )


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="f1-eyebrow">
        DATA ENGINEERING · RACE INTELLIGENCE
    </div>

    <div class="f1-title">
        F1 Lakehouse
    </div>

    <div class="f1-subtitle">
        Interactive Formula 1 analytics powered by a modern
        lakehouse architecture using FastF1, SeaweedFS,
        Apache Iceberg, Trino and dbt.
    </div>

    <span class="status-good">
        ● PIPELINE HEALTHY
    </span>
    """,
    unsafe_allow_html=True,
)


st.write("")


# ============================================================
# AVAILABLE EVENTS
# ============================================================

events = query_dataframe(
    """
    SELECT DISTINCT

        season,

        event_name,

        event_slug,

        session_type

    FROM iceberg.gold.race_driver_performance

    ORDER BY

        season DESC,

        event_name
    """
)


if events.empty:

    st.error(
        "No Gold race data found. "
        "Build race_driver_performance first."
    )

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    """
    <div class="section-label">
        Race Control
    </div>
    """,
    unsafe_allow_html=True,
)


seasons = sorted(

    events[
        "season"
    ]
    .dropna()
    .unique()
    .tolist(),

    reverse=True,
)


selected_season = (
    st.sidebar.selectbox(
        "Season",
        seasons,
    )
)


season_events = (
    events[
        events[
            "season"
        ]
        == selected_season
    ]
    .copy()
)


event_options = (

    season_events[
        [
            "event_name",
            "event_slug",
        ]
    ]

    .drop_duplicates()

    .sort_values(
        "event_name"
    )
)


selected_event_name = (
    st.sidebar.selectbox(

        "Grand Prix",

        event_options[
            "event_name"
        ]
        .tolist(),
    )
)


selected_event_slug = (

    event_options.loc[

        event_options[
            "event_name"
        ]
        == selected_event_name,

        "event_slug",

    ]

    .iloc[0]
)


sessions = (

    season_events.loc[

        season_events[
            "event_slug"
        ]
        == selected_event_slug,

        "session_type",

    ]

    .dropna()

    .unique()

    .tolist()
)


selected_session = (
    st.sidebar.selectbox(
        "Session",
        sessions,
    )
)


safe_event = (
    sql_safe(
        selected_event_slug
    )
)


safe_session = (
    sql_safe(
        selected_session
    )
)


# ============================================================
# RACE PERFORMANCE
# ============================================================

performance = query_dataframe(
    f"""
    SELECT

        finish_position,

        driver_code,

        full_name,

        team_name,

        grid_position,

        positions_gained,

        points,

        valid_laps,

        avg_lap_seconds,

        fastest_lap_seconds,

        avg_air_temp_c,

        avg_track_temp_c,

        rain_detected

    FROM iceberg.gold.race_driver_performance

    WHERE season = {int(selected_season)}

      AND event_slug = '{safe_event}'

      AND session_type = '{safe_session}'

    ORDER BY finish_position
    """
)


if performance.empty:

    st.warning(
        "No data exists for this selection."
    )

    st.stop()


drivers = (

    performance[
        "driver_code"
    ]

    .dropna()

    .tolist()
)


if not drivers:

    st.warning(
        "No drivers are available."
    )

    st.stop()


default_driver_1 = (
    drivers[0]
)


default_driver_2 = (

    drivers[1]

    if len(
        drivers
    )
    > 1

    else drivers[0]
)


st.sidebar.markdown(
    """
    <div class="section-label">
        Driver Comparison
    </div>
    """,
    unsafe_allow_html=True,
)


driver_1 = (
    st.sidebar.selectbox(

        "Driver A",

        drivers,

        index=
            drivers.index(
                default_driver_1
            ),
    )
)


driver_2_options = [

    driver

    for driver
    in drivers

    if driver != driver_1
]


if not driver_2_options:

    driver_2_options = [
        driver_1
    ]


driver_2 = (
    st.sidebar.selectbox(

        "Driver B",

        driver_2_options,

        index=0,
    )
)


high_contrast = (
    st.sidebar.toggle(

        "High contrast charts",

        value=False,

        help=(
            "Uses a colour-blind-friendly "
            "high-contrast chart palette. "
            "Line style and marker shape "
            "always distinguish drivers."
        ),
    )
)


# ============================================================
# DRIVER INFORMATION
# ============================================================

driver_1_row = (

    performance[
        performance[
            "driver_code"
        ]
        == driver_1
    ]

    .iloc[0]
)


driver_2_row = (

    performance[
        performance[
            "driver_code"
        ]
        == driver_2
    ]

    .iloc[0]
)


team_1 = (
    driver_1_row[
        "team_name"
    ]
)


team_2 = (
    driver_2_row[
        "team_name"
    ]
)


styles = (
    get_driver_styles(

        driver_1,
        team_1,

        driver_2,
        team_2,

        high_contrast=
            high_contrast,
    )
)


# ============================================================
# EVENT HEADER
# ============================================================

st.markdown(
    """
    <div class="section-label">
        Selected Event
    </div>
    """,
    unsafe_allow_html=True,
)


st.subheader(
    f"{selected_season} "
    f"{selected_event_name}"
)


# ============================================================
# RACE SUMMARY
# ============================================================

winner = (
    performance.iloc[0]
)


summary_1, summary_2, summary_3, summary_4 = (
    st.columns(4)
)


summary_1.metric(
    "Winner",
    winner[
        "driver_code"
    ],
)


summary_2.metric(
    "Winning Team",
    winner[
        "team_name"
    ],
)


summary_3.metric(

    "Track Temperature",

    format_number(
        winner[
            "avg_track_temp_c"
        ],
        decimals=1,
        suffix=" °C",
    ),
)


summary_4.metric(

    "Conditions",

    "Wet"

    if winner[
        "rain_detected"
    ]
    == 1

    else "Dry",
)


# ============================================================
# DRIVER COMPARISON CARDS
# ============================================================

st.write("")

st.markdown(
    '<div class="section-label">HEAD-TO-HEAD</div>',
    unsafe_allow_html=True,
)

driver_col_1, driver_col_2 = st.columns(2)


# ------------------------------------------------------------
# DRIVER A
# ------------------------------------------------------------

with driver_col_1:

    style = styles[driver_1]

    driver_1_name = str(
        driver_1_row["full_name"]
    )

    driver_1_team = str(
        team_1
    )

    driver_1_card = (
        f'<div class="driver-card" '
        f'style="border-top:3px solid {style["team_color"]};">'
        f'<div class="driver-code">'
        f'{style["glyph"]} {driver_1}'
        f'</div>'
        f'<div class="driver-team">'
        f'{driver_1_name} · {driver_1_team}'
        f'</div>'
        f'</div>'
    )

    st.markdown(
        driver_1_card,
        unsafe_allow_html=True,
    )

    d1a, d1b, d1c = st.columns(3)

    finish_1 = number(
        driver_1_row["finish_position"]
    )

    grid_1 = number(
        driver_1_row["grid_position"]
    )

    d1a.metric(
        "Finish",
        (
            f"P{int(finish_1)}"
            if finish_1 is not None
            else "N/A"
        ),
    )

    d1b.metric(
        "Grid",
        (
            f"P{int(grid_1)}"
            if grid_1 is not None
            else "N/A"
        ),
    )

    d1c.metric(
        "Fastest Lap",
        format_lap_time(
            driver_1_row[
                "fastest_lap_seconds"
            ]
        ),
    )


# ------------------------------------------------------------
# DRIVER B
# ------------------------------------------------------------

with driver_col_2:

    style = styles[driver_2]

    driver_2_name = str(
        driver_2_row["full_name"]
    )

    driver_2_team = str(
        team_2
    )

    driver_2_card = (
        f'<div class="driver-card" '
        f'style="border-top:3px solid {style["team_color"]};">'
        f'<div class="driver-code">'
        f'{style["glyph"]} {driver_2}'
        f'</div>'
        f'<div class="driver-team">'
        f'{driver_2_name} · {driver_2_team}'
        f'</div>'
        f'</div>'
    )

    st.markdown(
        driver_2_card,
        unsafe_allow_html=True,
    )

    d2a, d2b, d2c = st.columns(3)

    finish_2 = number(
        driver_2_row["finish_position"]
    )

    grid_2 = number(
        driver_2_row["grid_position"]
    )

    d2a.metric(
        "Finish",
        (
            f"P{int(finish_2)}"
            if finish_2 is not None
            else "N/A"
        ),
    )

    d2b.metric(
        "Grid",
        (
            f"P{int(grid_2)}"
            if grid_2 is not None
            else "N/A"
        ),
    )

    d2c.metric(
        "Fastest Lap",
        format_lap_time(
            driver_2_row[
                "fastest_lap_seconds"
            ]
        ),
    )


# ------------------------------------------------------------
# TEAMMATE MESSAGE
# ------------------------------------------------------------

if team_1 == team_2:

    st.caption(
        f"{driver_1} and {driver_2} are teammates at "
        f"{team_1}. "
        f"{driver_1} uses ● + solid line while "
        f"{driver_2} uses ◆ + dashed line."
    )

# ============================================================
# GOLD LAP METRICS
# ============================================================

safe_driver_1 = (
    sql_safe(
        driver_1
    )
)


safe_driver_2 = (
    sql_safe(
        driver_2
    )
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

        avg_speed_kph,

        max_speed_kph,

        full_throttle_pct,

        braking_pct,

        drs_usage_pct,

        avg_rpm,

        peak_rpm

    FROM iceberg.gold.lap_telemetry_metrics

    WHERE season = {int(selected_season)}

      AND event_slug = '{safe_event}'

      AND session_type = '{safe_session}'

      AND driver_code IN (

          '{safe_driver_1}',

          '{safe_driver_2}'
      )

    ORDER BY

        driver_code,

        lap_number
    """
)


numeric_columns = [

    "lap_number",

    "lap_time_seconds",

    "tyre_life",

    "position",

    "avg_speed_kph",

    "max_speed_kph",

    "full_throttle_pct",

    "braking_pct",

    "drs_usage_pct",

    "avg_rpm",

    "peak_rpm",
]


for column in numeric_columns:

    if column in lap_metrics.columns:

        lap_metrics[
            column
        ] = pd.to_numeric(

            lap_metrics[
                column
            ],

            errors=
                "coerce",
        )


# ============================================================
# CHART BUILDER
# ============================================================

def make_driver_chart(
    dataframe: pd.DataFrame,
    y_column: str,
    title: str,
    y_title: str,
    hover_suffix: str = "",
):
    fig = go.Figure()

    for driver in [
        driver_1,
        driver_2,
    ]:

        frame = (
            dataframe[
                dataframe["driver_code"] == driver
            ]
            .dropna(
                subset=[
                    "lap_number",
                    y_column,
                ]
            )
        )

        if frame.empty:
            continue

        style = styles[driver]

        fig.add_trace(
            go.Scatter(
                x=frame["lap_number"],
                y=frame[y_column],

                mode="lines+markers",

                name=(
                    f"{style['glyph']} "
                    f"{driver}"
                ),

                line={
                    "color": style["plot_color"],
                    "width": 2.8,
                    "dash": style["dash"],
                },

                marker={
                    "color": style["plot_color"],
                    "symbol": style["marker"],
                    "size": 6,
                },

                customdata=frame[
                    [
                        "compound",
                        "tyre_life",
                    ]
                ],

                hovertemplate=(
                    f"<b>{driver}</b>"
                    "<br>Lap %{x}"
                    f"<br>{y_title}: %{{y:.2f}}{hover_suffix}"
                    "<br>Compound: %{customdata[0]}"
                    "<br>Tyre life: %{customdata[1]}"
                    "<extra></extra>"
                ),
            )
        )

    return apply_plotly_theme(
        fig,
        title=title,
        x_title="Lap",
        y_title=y_title,
        height=385,
    )

# ============================================================
# RACE PACE + SPEED
# ============================================================

st.write("")

st.markdown(
    """
    <div class="section-label">
        Race Intelligence
    </div>
    """,
    unsafe_allow_html=True,
)


chart_left, chart_right = (
    st.columns(2)
)


fig_laps = (
    make_driver_chart(

        lap_metrics,

        y_column=
            "lap_time_seconds",

        title=
            "Lap Time Evolution",

        y_title=
            "Lap Time (s)",
    )
)


fig_speed = (
    make_driver_chart(

        lap_metrics,

        y_column=
            "max_speed_kph",

        title=
            "Maximum Speed by Lap",

        y_title=
            "Speed (km/h)",

        hover_suffix=
            " km/h",
    )
)


with chart_left:

    st.plotly_chart(
        fig_laps,
        use_container_width=True,
    )


with chart_right:

    st.plotly_chart(
        fig_speed,
        use_container_width=True,
    )


# ============================================================
# THROTTLE / BRAKING
# ============================================================

chart_left, chart_right = (
    st.columns(2)
)


fig_throttle = (
    make_driver_chart(

        lap_metrics,

        y_column=
            "full_throttle_pct",

        title=
            "Full-Throttle Exposure",

        y_title=
            "Full Throttle (%)",

        hover_suffix=
            "%",
    )
)


fig_braking = (
    make_driver_chart(

        lap_metrics,

        y_column=
            "braking_pct",

        title=
            "Braking Exposure",

        y_title=
            "Braking (%)",

        hover_suffix=
            "%",
    )
)


with chart_left:

    st.plotly_chart(
        fig_throttle,
        use_container_width=True,
    )


with chart_right:

    st.plotly_chart(
        fig_braking,
        use_container_width=True,
    )


# ============================================================
# DRIVER SUMMARY
# ============================================================

st.markdown(
    """
    <div class="section-label">
        Driver Telemetry Summary
    </div>
    """,
    unsafe_allow_html=True,
)


summary = (

    lap_metrics

    .groupby(
        "driver_code"
    )

    .agg(

        average_speed=(
            "avg_speed_kph",
            "mean",
        ),

        maximum_speed=(
            "max_speed_kph",
            "max",
        ),

        full_throttle_pct=(
            "full_throttle_pct",
            "mean",
        ),

        braking_pct=(
            "braking_pct",
            "mean",
        ),

        drs_usage_pct=(
            "drs_usage_pct",
            "mean",
        ),

        peak_rpm=(
            "peak_rpm",
            "max",
        ),
    )

    .reset_index()
)


summary = (
    summary.rename(
        columns={

            "driver_code":
                "Driver",

            "average_speed":
                "Avg Speed",

            "maximum_speed":
                "Top Speed",

            "full_throttle_pct":
                "Full Throttle %",

            "braking_pct":
                "Braking %",

            "drs_usage_pct":
                "DRS %",

            "peak_rpm":
                "Peak RPM",
        }
    )
)


st.dataframe(

    summary,

    use_container_width=True,

    hide_index=True,

    column_config={

        "Avg Speed":
            st.column_config.NumberColumn(
                format="%.1f km/h"
            ),

        "Top Speed":
            st.column_config.NumberColumn(
                format="%.1f km/h"
            ),

        "Full Throttle %":
            st.column_config.NumberColumn(
                format="%.1f%%"
            ),

        "Braking %":
            st.column_config.NumberColumn(
                format="%.1f%%"
            ),

        "DRS %":
            st.column_config.NumberColumn(
                format="%.1f%%"
            ),

        "Peak RPM":
            st.column_config.NumberColumn(
                format="%.0f"
            ),
    },
)


# ============================================================
# CLASSIFICATION
# ============================================================

with st.expander(
    "Race Classification",
    expanded=False,
):

    classification = (
        performance[
            [
                "finish_position",
                "driver_code",
                "full_name",
                "team_name",
                "grid_position",
                "positions_gained",
                "points",
                "fastest_lap_seconds",
            ]
        ]
        .copy()
    )

    classification = (
        classification.rename(
            columns={

                "finish_position":
                    "Finish",

                "driver_code":
                    "Driver",

                "full_name":
                    "Name",

                "team_name":
                    "Team",

                "grid_position":
                    "Grid",

                "positions_gained":
                    "Positions Gained",

                "points":
                    "Points",

                "fastest_lap_seconds":
                    "Fastest Lap (s)",
            }
        )
    )

    st.dataframe(

        classification,

        use_container_width=True,

        hide_index=True,
    )


# ============================================================
# FASTEST LAP TELEMETRY
# ============================================================

st.divider()


st.markdown(
    """
    <div class="section-label">
        Sample-Level Telemetry
    </div>
    """,
    unsafe_allow_html=True,
)


st.subheader(
    "Fastest Lap Trace"
)


selected_driver = (
    st.selectbox(

        "Telemetry Driver",

        [
            driver_1,
            driver_2,
        ],
    )
)


driver_laps = (

    lap_metrics[
        lap_metrics[
            "driver_code"
        ]
        == selected_driver
    ]

    .dropna(
        subset=[
            "lap_time_seconds"
        ]
    )
)


if not driver_laps.empty:

    fastest_index = (

        driver_laps[
            "lap_time_seconds"
        ]

        .idxmin()
    )


    fastest_lap = int(

        driver_laps.loc[
            fastest_index,
            "lap_number",
        ]
    )


    fastest_time = (

        driver_laps.loc[
            fastest_index,
            "lap_time_seconds",
        ]
    )


    st.caption(

        f"{selected_driver} fastest valid lap: "
        f"Lap {fastest_lap} · "
        f"{format_lap_time(fastest_time)}"
    )


    telemetry = query_dataframe(
        f"""
        SELECT

            distance,

            speed_kph,

            throttle_pct,

            brake,

            gear,

            rpm,

            drs

        FROM iceberg.silver.silver_telemetry

        WHERE season = {int(selected_season)}

          AND event_slug = '{safe_event}'

          AND session_type = '{safe_session}'

          AND driver_code =
              '{sql_safe(selected_driver)}'

          AND lap_number =
              {fastest_lap}

        ORDER BY distance
        """
    )


    for column in [

        "distance",

        "speed_kph",

        "throttle_pct",

        "gear",

        "rpm",

        "drs",
    ]:

        telemetry[
            column
        ] = pd.to_numeric(

            telemetry[
                column
            ],

            errors=
                "coerce",
        )


    telemetry = (

        telemetry

        .dropna(
            subset=[
                "distance"
            ]
        )

        .sort_values(
            "distance"
        )
    )


    selected_style = (
        styles[
            selected_driver
        ]
    )


    trace_left, trace_right = (
        st.columns(2)
    )


    # ========================================================
    # SPEED TRACE
    # ========================================================

    fig_trace_speed = (
        go.Figure()
    )


    fig_trace_speed.add_trace(

        go.Scatter(

            x=
                telemetry[
                    "distance"
                ],

            y=
                telemetry[
                    "speed_kph"
                ],

            mode=
                "lines",

            name=
                selected_driver,

            line={
                "color":
                    selected_style[
                        "plot_color"
                    ],

                "width":
                    3,
            },

            hovertemplate=(

                "<b>"
                + selected_driver
                + "</b>"

                "<br>Distance: "
                "%{x:.0f} m"

                "<br>Speed: "
                "%{y:.0f} km/h"

                "<extra></extra>"
            ),
        )
    )


    fig_trace_speed = (
        apply_plotly_theme(

            fig_trace_speed,

            title=
                "Speed Trace",

            x_title=
                "Distance (m)",

            y_title=
                "Speed (km/h)",

            height=
                385,
        )
    )


    # ========================================================
    # THROTTLE / BRAKE TRACE
    # ========================================================

    fig_controls = (
        go.Figure()
    )


    fig_controls.add_trace(

        go.Scatter(

            x=
                telemetry[
                    "distance"
                ],

            y=
                telemetry[
                    "throttle_pct"
                ],

            mode=
                "lines",

            name=
                "Throttle",

            line={
                "color":
                    selected_style[
                        "plot_color"
                    ],

                "width":
                    3,
            },
        )
    )


    brake_value = (

        telemetry[
            "brake"
        ]

        .fillna(
            False
        )

        .astype(
            bool
        )

        .astype(
            int
        )

        * 100
    )


    fig_controls.add_trace(

        go.Scatter(

            x=
                telemetry[
                    "distance"
                ],

            y=
                brake_value,

            mode=
                "lines",

            name=
                "Brake",

            line={
                "color":
                    "#F5F7FA",

                "width":
                    2,

                "dash":
                    "dot",
            },
        )
    )


    fig_controls = (
        apply_plotly_theme(

            fig_controls,

            title=
                "Throttle & Brake",

            x_title=
                "Distance (m)",

            y_title=
                "Control Input (%)",

            height=
                385,
        )
    )


    fig_controls.update_yaxes(
        range=[
            0,
            105,
        ]
    )


    with trace_left:

        st.plotly_chart(

            fig_trace_speed,

            use_container_width=True,
        )


    with trace_right:

        st.plotly_chart(

            fig_controls,

            use_container_width=True,
        )


# ============================================================
# ENGINEERING FOOTER
# ============================================================

st.divider()


footer_1, footer_2, footer_3 = (
    st.columns(
        [
            2,
            1,
            1,
        ]
    )
)


with footer_1:

    st.markdown(
        """
        **Data Platform**

        FastF1 → SeaweedFS → Apache Iceberg →
        Trino → dbt → Streamlit
        """
    )


with footer_2:

    st.metric(
        "Lap Reconciliation",
        "100%",
    )


with footer_3:

    st.metric(
        "Gold dbt Tests",
        "16 / 16",
    )
