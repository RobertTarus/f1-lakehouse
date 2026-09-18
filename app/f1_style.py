from __future__ import annotations

import plotly.graph_objects as go


# ============================================================
# TEAM COLOURS
#
# Team colour = team identity.
#
# Driver identity NEVER depends on colour alone:
#
# Driver A:
#     solid line
#     circle marker
#
# Driver B:
#     dashed line
#     diamond marker
# ============================================================

TEAM_COLORS = {

    "ferrari":
        "#E8002D",

    "mclaren":
        "#FF8700",

    "mercedes":
        "#00A19B",

    "red bull":
        "#3671C6",

    "racing bulls":
        "#6692FF",

    "williams":
        "#64C4FF",

    "aston martin":
        "#229971",

    "alpine":
        "#FF87BC",

    "haas":
        "#B6BABD",

    "audi":
        "#F50537",

    "cadillac":
        "#A6A6A6",

    "sauber":
        "#52E252",
}


# ============================================================
# ACCESSIBLE HIGH CONTRAST PALETTE
# ============================================================

HIGH_CONTRAST_COLORS = {

    "A":
        "#0072B2",

    "B":
        "#D55E00",
}


def normalize_team_name(
    team_name: str,
) -> str:

    if not team_name:
        return ""

    return (
        str(team_name)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def get_team_color(
    team_name: str,
) -> str:

    normalized = (
        normalize_team_name(
            team_name
        )
    )

    ordered_matches = [

        "racing bulls",

        "red bull",

        "aston martin",

        "mclaren",

        "mercedes",

        "ferrari",

        "williams",

        "alpine",

        "haas",

        "audi",

        "cadillac",

        "sauber",
    ]

    for key in ordered_matches:

        if key in normalized:

            return TEAM_COLORS[
                key
            ]

    return "#8A94A3"


def hex_to_rgb(
    hex_color: str,
) -> tuple[int, int, int]:

    value = (
        hex_color
        .lstrip("#")
    )

    return tuple(

        int(
            value[
                i : i + 2
            ],
            16,
        )

        for i
        in (
            0,
            2,
            4,
        )
    )


def rgb_to_hex(
    rgb: tuple[int, int, int],
) -> str:

    return "#{:02X}{:02X}{:02X}".format(
        *rgb
    )


def mix_color(
    color_a: str,
    color_b: str,
    amount: float,
) -> str:

    amount = max(
        0.0,
        min(
            1.0,
            amount,
        ),
    )

    rgb_a = (
        hex_to_rgb(
            color_a
        )
    )

    rgb_b = (
        hex_to_rgb(
            color_b
        )
    )

    mixed = tuple(

        round(
            a
            + (
                b - a
            )
            * amount
        )

        for a, b
        in zip(
            rgb_a,
            rgb_b,
        )
    )

    return rgb_to_hex(
        mixed
    )


def relative_luminance(
    hex_color: str,
) -> float:

    r, g, b = (
        hex_to_rgb(
            hex_color
        )
    )

    return (

        0.2126
        * (
            r / 255
        )

        + 0.7152
        * (
            g / 255
        )

        + 0.0722
        * (
            b / 255
        )
    )


def teammate_variant(
    base_color: str,
) -> str:

    luminance = (
        relative_luminance(
            base_color
        )
    )

    if luminance > 0.55:

        return mix_color(
            base_color,
            "#000000",
            0.35,
        )

    return mix_color(
        base_color,
        "#FFFFFF",
        0.35,
    )


def get_driver_styles(
    driver_a: str,
    team_a: str,
    driver_b: str,
    team_b: str,
    high_contrast: bool = False,
) -> dict:

    team_color_a = (
        get_team_color(
            team_a
        )
    )

    team_color_b = (
        get_team_color(
            team_b
        )
    )

    same_team = (

        normalize_team_name(
            team_a
        )

        ==

        normalize_team_name(
            team_b
        )
    )

    if high_contrast:

        plot_color_a = (
            HIGH_CONTRAST_COLORS[
                "A"
            ]
        )

        plot_color_b = (
            HIGH_CONTRAST_COLORS[
                "B"
            ]
        )

    elif same_team:

        plot_color_a = (
            team_color_a
        )

        plot_color_b = (
            teammate_variant(
                team_color_a
            )
        )

    else:

        plot_color_a = (
            team_color_a
        )

        plot_color_b = (
            team_color_b
        )

    return {

        driver_a: {

            "driver":
                driver_a,

            "team":
                team_a,

            "team_color":
                team_color_a,

            "plot_color":
                plot_color_a,

            "dash":
                "solid",

            "marker":
                "circle",

            "glyph":
                "●",

            "role":
                "A",
        },

        driver_b: {

            "driver":
                driver_b,

            "team":
                team_b,

            "team_color":
                team_color_b,

            "plot_color":
                plot_color_b,

            "dash":
                "dash",

            "marker":
                "diamond",

            "glyph":
                "◆",

            "role":
                "B",
        },
    }


def apply_plotly_theme(
    fig: go.Figure,
    title: str | None = None,
    x_title: str | None = None,
    y_title: str | None = None,
    height: int = 390,
) -> go.Figure:

    fig.update_layout(

        title={
            "text":
                title,

            "x":
                0,

            "xanchor":
                "left",

            "font": {
                "size":
                    19,

                "color":
                    "#F1F5F9",
            },
        },

        paper_bgcolor=
            "rgba(0,0,0,0)",

        plot_bgcolor=
            "rgba(0,0,0,0)",

        font={
            "color":
                "#D7DEE8",
        },

        margin={
            "l":
                45,

            "r":
                20,

            "t":
                65,

            "b":
                45,
        },

        height=
            height,

        hovermode=
            "x unified",

        legend={
            "orientation":
                "h",

            "yanchor":
                "bottom",

            "y":
                1.01,

            "xanchor":
                "right",

            "x":
                1,

            "bgcolor":
                "rgba(0,0,0,0)",
        },

        hoverlabel={
            "bgcolor":
                "#111821",

            "font_color":
                "#F4F7FB",

            "bordercolor":
                "#334155",
        },
    )

    fig.update_xaxes(

        title=
            x_title,

        showgrid=
            True,

        gridcolor=
            "rgba(148,163,184,0.10)",

        zeroline=
            False,

        linecolor=
            "rgba(148,163,184,0.18)",

        tickfont={
            "color":
                "#8491A3",
        },
    )

    fig.update_yaxes(

        title=
            y_title,

        showgrid=
            True,

        gridcolor=
            "rgba(148,163,184,0.10)",

        zeroline=
            False,

        linecolor=
            "rgba(148,163,184,0.18)",

        tickfont={
            "color":
                "#8491A3",
        },
    )

    return fig
