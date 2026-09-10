import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import query_dataframe


# =========================================================
# Page configuration
# =========================================================

st.set_page_config(
    page_title="F1 Lakehouse",
    page_icon="🏎️",
    layout="wide",
)


st.title("🏎️ F1 Lakehouse")

st.caption(
    "FastF1 → SeaweedFS → Apache Iceberg → "
    "Trino → dbt → Streamlit"
)


# =========================================================
# Available races
# =========================================================

events = query_dataframe(
    """
    SELECT DISTINCT
        season,
        event_name,
        event_slug,
        session_type
    FROM iceberg.gold.race_driver_performance
    ORDER BY season DESC, event_name
    """
)


if events.empty:
    st.error(
        "No Gold race data found. "
        "Build race_driver_performance first."
    )

    st.stop()


# =========================================================
# Sidebar
# =========================================================

st.sidebar.header("Race Selection")


seasons = sorted(
    events["season"].unique(),
    reverse=True,
)


selected_season = st.sidebar.selectbox(
    "Season",
    seasons,
)


season_events = events[
    events["season"] == selected_season
]


event_options = (
    season_events[
        [
            "event_name",
            "event_slug",
        ]
    ]
    .drop_duplicates()
)


event_names = event_options[
    "event_name"
].tolist()


selected_event_name = st.sidebar.selectbox(
    "Event",
    event_names,
)


selected_event_slug = (
    event_options[
        event_options["event_name"]
        == selected_event_name
    ]["event_slug"]
    .iloc[0]
)


sessions = (
    season_events[
        season_events["event_slug"]
        == selected_event_slug
    ]["session_type"]
    .unique()
    .tolist()
)


selected_session = st.sidebar.selectbox(
    "Session",
    sessions,
)


# =========================================================
# Driver performance
# =========================================================

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

    WHERE season = {selected_season}

      AND event_slug = '{selected_event_slug}'

      AND session_type = '{selected_session}'

    ORDER BY finish_position
    """
)


if performance.empty:

    st.warning(
        "No data exists for this selection."
    )

    st.stop()


drivers = performance[
    "driver_code"
].tolist()


default_driver_1 = drivers[0]

default_driver_2 = (
    drivers[1]
    if len(drivers) > 1
    else drivers[0]
)


driver_1 = st.sidebar.selectbox(
    "Driver 1",
    drivers,
    index=drivers.index(
        default_driver_1
    ),
)


driver_2 = st.sidebar.selectbox(
    "Driver 2",
    drivers,
    index=drivers.index(
        default_driver_2
    ),
)


# =========================================================
# Race summary
# =========================================================

st.subheader(
    f"{selected_season} {selected_event_name}"
)


metric_1, metric_2, metric_3, metric_4 = (
    st.columns(4)
)


winner = performance.iloc[0]


metric_1.metric(
    "Winner",
    winner["driver_code"],
)


metric_2.metric(
    "Winning Team",
    winner["team_name"],
)


metric_3.metric(
    "Track Temp",
    (
        f"{winner['avg_track_temp_c']:.1f} °C"
        if winner["avg_track_temp_c"] is not None
        else "N/A"
    ),
)


metric_4.metric(
    "Conditions",
    (
        "Wet"
        if winner["rain_detected"] == 1
        else "Dry"
    ),
)


# =========================================================
# Race classification
# =========================================================

st.subheader("Race Classification")


classification = performance[
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


st.dataframe(
    classification,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# Pace comparison
# =========================================================

st.subheader("Driver Pace")


pace_data = performance[
    performance["driver_code"].isin(
        [
            driver_1,
            driver_2,
        ]
    )
]


fig_pace = px.bar(
    pace_data,
    x="driver_code",
    y="avg_lap_seconds",
    text="avg_lap_seconds",
    labels={
        "driver_code": "Driver",
        "avg_lap_seconds": "Average Lap Time (s)",
    },
)


fig_pace.update_layout(
    showlegend=False,
)


st.plotly_chart(
    fig_pace,
    use_container_width=True,
)


# =========================================================
# Lap metrics
# =========================================================

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
        braking_pct

    FROM iceberg.gold.lap_telemetry_metrics

    WHERE season = {selected_season}

      AND event_slug = '{selected_event_slug}'

      AND session_type = '{selected_session}'

      AND driver_code IN (
          '{driver_1}',
          '{driver_2}'
      )

    ORDER BY
        driver_code,
        lap_number
    """
)


# =========================================================
# Lap time comparison
# =========================================================

st.subheader(
    f"Lap Time — {driver_1} vs {driver_2}"
)


fig_laps = px.line(
    lap_metrics,
    x="lap_number",
    y="lap_time_seconds",
    color="driver_code",
    markers=True,

    hover_data=[
        "compound",
        "tyre_life",
        "max_speed_kph",
    ],

    labels={
        "lap_number": "Lap",
        "lap_time_seconds": "Lap Time (s)",
        "driver_code": "Driver",
    },
)


st.plotly_chart(
    fig_laps,
    use_container_width=True,
)


# =========================================================
# Maximum speed
# =========================================================

st.subheader("Maximum Speed by Lap")


fig_speed = px.line(
    lap_metrics,
    x="lap_number",
    y="max_speed_kph",
    color="driver_code",
    markers=True,

    labels={
        "lap_number": "Lap",
        "max_speed_kph": "Maximum Speed (km/h)",
        "driver_code": "Driver",
    },
)


st.plotly_chart(
    fig_speed,
    use_container_width=True,
)


# =========================================================
# Driver summary
# =========================================================

st.subheader("Telemetry Summary")


summary = (
    lap_metrics
    .groupby("driver_code")
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
    )
    .reset_index()
)


st.dataframe(
    summary,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# Telemetry trace
# =========================================================

st.subheader("Fastest Lap Telemetry")


selected_driver = st.selectbox(
    "Telemetry Driver",
    [
        driver_1,
        driver_2,
    ],
)


driver_laps = lap_metrics[
    lap_metrics["driver_code"]
    == selected_driver
]


driver_laps = driver_laps.dropna(
    subset=["lap_time_seconds"]
)


if not driver_laps.empty:

    fastest_lap = int(
        driver_laps.loc[
            driver_laps[
                "lap_time_seconds"
            ].idxmin(),
            "lap_number",
        ]
    )

    st.caption(
        f"{selected_driver} fastest valid lap: "
        f"Lap {fastest_lap}"
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

        WHERE season = {selected_season}

          AND event_slug = '{selected_event_slug}'

          AND session_type = '{selected_session}'

          AND driver_code = '{selected_driver}'

          AND lap_number = {fastest_lap}

        ORDER BY distance
        """
    )


    # -----------------------------------------------------
    # Speed
    # -----------------------------------------------------

    fig = go.Figure()


    fig.add_trace(
        go.Scatter(
            x=telemetry["distance"],
            y=telemetry["speed_kph"],
            mode="lines",
            name="Speed",
        )
    )


    fig.update_layout(
        title="Speed Trace",
        xaxis_title="Distance",
        yaxis_title="Speed (km/h)",
    )


    st.plotly_chart(
        fig,
        use_container_width=True,
    )


    # -----------------------------------------------------
    # Throttle / Brake
    # -----------------------------------------------------

    fig_controls = go.Figure()


    fig_controls.add_trace(
        go.Scatter(
            x=telemetry["distance"],
            y=telemetry["throttle_pct"],
            mode="lines",
            name="Throttle %",
        )
    )


    brake_value = (
        telemetry["brake"]
        .astype(int)
        * 100
    )


    fig_controls.add_trace(
        go.Scatter(
            x=telemetry["distance"],
            y=brake_value,
            mode="lines",
            name="Brake",
        )
    )


    fig_controls.update_layout(
        title="Throttle / Brake",
        xaxis_title="Distance",
        yaxis_title="Percent",
    )


    st.plotly_chart(
        fig_controls,
        use_container_width=True,
    )


st.divider()


st.caption(
    "Data platform: FastF1 · SeaweedFS · "
    "Apache Iceberg · Trino · dbt · Streamlit"
)
