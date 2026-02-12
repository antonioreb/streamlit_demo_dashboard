import pandas as pd
import streamlit as st

from logic.metrics import add_metrics


@st.cache_data
def load_data():
    df = pd.read_csv("data/ads_data.csv", parse_dates=["date"])

    # Make channel mix less uniform so spend/revenue concentration looks realistic.
    channel_volume_scale = {
        "Amazon": 1.85,
        "Google": 1.20,
        "Facebook": 0.72,
        "TikTok": 0.38,
    }
    df["channel_scale"] = df["channel"].map(channel_volume_scale).fillna(1.0)

    volume_cols = ["impressions", "clicks", "add_to_cart", "orders"]
    value_cols = ["cost", "revenue"]

    for col in volume_cols:
        if col in df.columns:
            df[col] = (df[col] * df["channel_scale"]).round().clip(lower=0).astype(int)
    for col in value_cols:
        if col in df.columns:
            df[col] = (df[col] * df["channel_scale"]).round(2).clip(lower=0)

    df = df.drop(columns=["channel_scale"])
    df = add_metrics(df)
    df["date_day"] = df["date"].dt.floor("D")
    return df
