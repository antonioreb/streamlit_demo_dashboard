import streamlit as st


def apply_sidebar_filters(df):
    st.sidebar.header("Filters")

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = st.sidebar.date_input("Date range", (min_date, max_date))
    if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:
        date_range = (min_date, max_date)

    channels = sorted(df["channel"].unique().tolist())
    channel_sel = st.sidebar.multiselect("Channel", channels, default=channels)
    if not channel_sel:
        channel_sel = channels

    campaign_types = sorted(df["campaign_type"].unique().tolist())
    campaign_type_sel = st.sidebar.multiselect(
        "Campaign type", campaign_types, default=campaign_types
    )
    if not campaign_type_sel:
        campaign_type_sel = campaign_types

    products = sorted(df["product"].unique().tolist())
    product_sel = st.sidebar.multiselect("Product", products, default=products)
    if not product_sel:
        product_sel = products

    st.sidebar.header("Targets")
    target_roas = st.sidebar.number_input("Target ROAS", min_value=0.5, value=2.8, step=0.1)
    target_acos = st.sidebar.number_input("Target ACOS", min_value=0.05, value=0.35, step=0.05)
    target_cpa = st.sidebar.number_input("Target CPA (€)", min_value=5.0, value=25.0, step=1.0)

    start_date, end_date = date_range
    mask = (
        (df["date"].dt.date >= start_date)
        & (df["date"].dt.date <= end_date)
        & (df["channel"].isin(channel_sel))
        & (df["campaign_type"].isin(campaign_type_sel))
        & (df["product"].isin(product_sel))
    )

    filtered = df.loc[mask].copy()
    return filtered, {
        "date_range": (start_date, end_date),
        "channels": channel_sel,
        "campaign_types": campaign_type_sel,
        "products": product_sel,
        "target_roas": target_roas,
        "target_acos": target_acos,
        "target_cpa": target_cpa,
    }


def format_k(value, currency=False):
    try:
        num = float(value)
        if num != num:
            return "-"
    except Exception:
        return value
    if abs(num) >= 1000:
        display = f"{num/1000:.1f}k"
    else:
        display = f"{num:.0f}"
    if currency:
        return f"€{display}"
    return display


def format_pct(value, decimals=1):
    try:
        if value != value:
            return "-"
        return f"{float(value):.{decimals}%}"
    except Exception:
        return value


def format_float(value, decimals=2):
    try:
        num = float(value)
        if num != num:
            return "-"
        return f"{num:.{decimals}f}"
    except Exception:
        return value
