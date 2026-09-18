import streamlit as st


def apply_app_theme():

    st.markdown(
        """
        <style>

        /* ==================================================
           APPLICATION BACKGROUND
        ================================================== */

        .stApp {
            background:
                radial-gradient(
                    circle at 85% 0%,
                    rgba(225, 6, 0, 0.08),
                    transparent 28%
                ),
                radial-gradient(
                    circle at 10% 35%,
                    rgba(0, 161, 155, 0.035),
                    transparent 25%
                ),
                linear-gradient(
                    180deg,
                    #090D12 0%,
                    #0B1016 100%
                );

            color: #F4F7FB;
        }


        /* ==================================================
           MAIN CONTENT
        ================================================== */

        .block-container {
            max-width: 1500px;

            padding-top: 2rem;

            padding-left: 2.2rem;
            padding-right: 2.2rem;

            padding-bottom: 5rem;
        }


        /* ==================================================
           SIDEBAR
        ================================================== */

        section[data-testid="stSidebar"] {
            background:
                linear-gradient(
                    180deg,
                    #111821 0%,
                    #0C1219 100%
                );

            border-right: 1px solid #222C38;
        }


        section[data-testid="stSidebar"] > div {
            padding-top: 1.2rem;
        }


        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: #F4F7FB;
        }


        /* ==================================================
           PAGE HEADINGS
        ================================================== */

        h1 {
            letter-spacing: -0.045em !important;
            font-weight: 800 !important;
        }

        h2 {
            letter-spacing: -0.025em !important;
            font-weight: 700 !important;
        }

        h3 {
            letter-spacing: -0.02em !important;
        }


        /* ==================================================
           METRIC CARDS
        ================================================== */

        div[data-testid="stMetric"] {
            background:
                linear-gradient(
                    145deg,
                    rgba(23, 32, 43, 0.96),
                    rgba(13, 19, 27, 0.96)
                );

            border: 1px solid #263241;

            border-radius: 14px;

            padding: 16px 18px;

            min-height: 108px;
        }


        div[data-testid="stMetric"]:hover {
            border-color: #3A495C;
        }


        div[data-testid="stMetricLabel"] {
            color: #95A2B3;
        }


        div[data-testid="stMetricValue"] {
            font-weight: 750;
        }


        /* ==================================================
           SELECT / INPUT
        ================================================== */

        div[data-baseweb="select"] > div {
            background-color: #121A24;

            border-color: #293545;

            border-radius: 9px;
        }


        div[data-baseweb="select"] > div:hover {
            border-color: #45546A;
        }


        /* ==================================================
           DATAFRAME
        ================================================== */

        div[data-testid="stDataFrame"] {
            border: 1px solid #222C38;

            border-radius: 12px;

            overflow: hidden;
        }


        /* ==================================================
           TABS
        ================================================== */

        button[data-baseweb="tab"] {
            font-weight: 650;
        }


        /* ==================================================
           DIVIDER
        ================================================== */

        hr {
            border-color: #222C38 !important;
        }


        /* ==================================================
           CUSTOM HERO
        ================================================== */

        .f1-eyebrow {
            color: #8795A8;

            font-size: 0.73rem;

            font-weight: 800;

            letter-spacing: 0.16em;

            text-transform: uppercase;

            margin-bottom: 0.45rem;
        }


        .f1-title {
            color: #F7F9FC;

            font-size: clamp(
                2.4rem,
                5vw,
                4rem
            );

            font-weight: 850;

            line-height: 0.95;

            letter-spacing: -0.055em;

            margin: 0;
        }


        .f1-subtitle {
            color: #97A5B6;

            font-size: 1rem;

            margin-top: 0.8rem;

            margin-bottom: 1rem;

            max-width: 850px;
        }


        /* ==================================================
           STATUS
        ================================================== */

        .status-good {
            display: inline-block;

            color: #7EE2B8;

            background: rgba(
                0,
                200,
                120,
                0.09
            );

            border: 1px solid rgba(
                0,
                200,
                120,
                0.28
            );

            padding: 5px 10px;

            border-radius: 999px;

            font-size: 0.75rem;

            font-weight: 750;

            letter-spacing: 0.04em;
        }


        /* ==================================================
           SECTION LABEL
        ================================================== */

        .section-label {
            color: #7D8A9A;

            font-size: 0.70rem;

            font-weight: 800;

            letter-spacing: 0.14em;

            text-transform: uppercase;

            margin-top: 1rem;

            margin-bottom: 0.2rem;
        }


        /* ==================================================
           DRIVER CARD
        ================================================== */

        .driver-card {
            background:
                linear-gradient(
                    145deg,
                    rgba(23, 32, 43, 0.96),
                    rgba(13, 19, 27, 0.96)
                );

            border: 1px solid #263241;

            border-radius: 14px;

            padding: 18px;

            margin-bottom: 10px;
        }


        .driver-code {
            font-size: 1.7rem;

            font-weight: 850;

            letter-spacing: -0.035em;
        }


        .driver-team {
            color: #91A0B2;

            font-size: 0.86rem;
        }


        /* ==================================================
           SMALL LABEL
        ================================================== */

        .muted-label {
            color: #7F8C9D;

            font-size: 0.78rem;

            font-weight: 650;
        }


        /* ==================================================
           RESPONSIVE
        ================================================== */

        @media (max-width: 700px) {

            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .f1-title {
                font-size: 2.4rem;
            }

        }

        </style>
        """,
        unsafe_allow_html=True,
    )
