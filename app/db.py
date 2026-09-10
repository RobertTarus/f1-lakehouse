import pandas as pd
import streamlit as st

from trino.dbapi import connect


TRINO_HOST = "localhost"
TRINO_PORT = 8081
TRINO_CATALOG = "iceberg"


def get_connection(schema="gold"):
    return connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user="f1_streamlit",
        catalog=TRINO_CATALOG,
        schema=schema,
        http_scheme="http",
    )


@st.cache_data(ttl=300)
def query_dataframe(sql: str) -> pd.DataFrame:
    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(sql)

    rows = cursor.fetchall()

    columns = [
        column[0]
        for column in cursor.description
    ]

    return pd.DataFrame(
        rows,
        columns=columns,
    )
