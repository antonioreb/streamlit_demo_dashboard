import pandas as pd
import streamlit as st

from logic.data import load_data
from logic.ui import apply_sidebar_filters, format_float, format_k, format_pct

try:
    import altair as alt
except Exception:
    alt = None


df = load_data()
df, filters = apply_sidebar_filters(df)

st.header("Executive Overview")

if df.empty:
    st.warning("No data for the current filters.")
    st.stop()

spend = df["cost"].sum()
revenue = df["revenue"].sum()
impressions = df["impressions"].sum()
clicks = df["clicks"].sum()
orders = df["orders"].sum()
add_to_cart = df["add_to_cart"].sum() if "add_to_cart" in df.columns else 0

roas = revenue / spend if spend else 0
ctr = clicks / impressions if impressions else 0
cvr = orders / clicks if clicks else 0
cpc = spend / clicks if clicks else 0
cpa = spend / orders if orders else float("nan")
atc_rate = add_to_cart / clicks if clicks and add_to_cart else 0

kpi_row = st.columns(6)
kpi_row[0].metric("Spend", format_k(spend, currency=True))
kpi_row[1].metric("Revenue", format_k(revenue, currency=True))
kpi_row[2].metric("ROAS", f"{roas:.2f}", delta=f"{roas - filters['target_roas']:+.2f}")
kpi_row[3].metric("CTR", format_pct(ctr, 2))
kpi_row[4].metric("CVR", format_pct(cvr, 2))
kpi_row[5].metric("CPA", format_k(cpa, currency=True) if cpa == cpa else "-")

sub_row = st.columns(3)
sub_row[0].metric("Clicks", format_k(clicks))
sub_row[1].metric("Add to Cart Rate", format_pct(atc_rate, 2))
sub_row[2].metric("CPC", f"EUR {cpc:,.2f}")

trend = (
    df.groupby("date_day", as_index=False)[["cost", "revenue", "impressions", "clicks", "orders"]].sum()
)
trend["roas"] = trend["revenue"] / trend["cost"].replace(0, float("nan"))
trend["roas"] = trend["roas"].fillna(0)
trend["roas_7d"] = trend["roas"].rolling(7, min_periods=1).mean()

st.subheader("Spend, Revenue, and ROAS")
st.caption(
    "This trend combines spend, revenue, and 7-day ROAS in one view to separate growth from efficiency. "
    "If spend rises faster than revenue while ROAS declines, acquisition quality is weakening and bids/targeting should be tightened. "
    "If spend and revenue rise together with stable or improving ROAS, scaling is usually justified. "
    "Action: investigate any sustained ROAS downtrend before increasing budget."
)
if alt:
    max_money = max(trend["cost"].max(), trend["revenue"].max()) * 1.1
    max_roas = max(trend["roas_7d"].max(), 1.0) * 1.15

    base = alt.Chart(trend).encode(x=alt.X("date_day:T", title="Date"))
    money_layer = (
        base.transform_fold(["cost", "revenue"], as_=["metric", "value"])
        .mark_line(interpolate="monotone", strokeWidth=2.2)
        .encode(
            y=alt.Y(
                "value:Q",
                title="Spend / Revenue (EUR)",
                scale=alt.Scale(domain=[0, max_money]),
            ),
            color=alt.Color("metric:N", title="Series"),
            tooltip=[
                alt.Tooltip("date_day:T", title="Date"),
                alt.Tooltip("metric:N", title="Series"),
                alt.Tooltip("value:Q", title="Value", format=",.0f"),
            ],
        )
    )
    roas_layer = (
        base.mark_line(color="#7a0177", strokeWidth=2, interpolate="monotone", strokeDash=[6, 4])
        .encode(
            y=alt.Y(
                "roas_7d:Q",
                title="ROAS (7d)",
                axis=alt.Axis(titleColor="#7a0177", labelColor="#7a0177"),
                scale=alt.Scale(domain=[0, max_roas]),
            ),
            tooltip=[alt.Tooltip("roas_7d:Q", title="ROAS 7d", format=".2f")],
        )
    )
    st.altair_chart(alt.layer(money_layer, roas_layer).resolve_scale(y="independent"), use_container_width=True)
else:
    st.line_chart(trend.set_index("date_day")[["cost", "revenue", "roas_7d"]])

channel = (
    df.groupby("channel", as_index=False)[
        ["impressions", "clicks", "add_to_cart", "orders", "cost", "revenue"]
    ]
    .sum()
    .sort_values("cost", ascending=False)
)
channel["ctr"] = channel["clicks"] / channel["impressions"].replace(0, float("nan"))
channel["cvr"] = channel["orders"] / channel["clicks"].replace(0, float("nan"))
channel["atc_rate"] = channel["add_to_cart"] / channel["clicks"].replace(0, float("nan"))
channel["roas"] = channel["revenue"] / channel["cost"].replace(0, float("nan"))
channel["cpc"] = channel["cost"] / channel["clicks"].replace(0, float("nan"))
channel["cpa"] = channel["cost"] / channel["orders"].replace(0, float("nan"))
channel = channel.fillna(0)

ctr_median = channel["ctr"].median()
cvr_median = channel["cvr"].median()


def _channel_action(row):
    if row["ctr"] >= ctr_median and row["cvr"] >= cvr_median:
        return "Scale budget"
    if row["ctr"] >= ctr_median and row["cvr"] < cvr_median:
        return "Fix landing page / offer"
    if row["ctr"] < ctr_median and row["cvr"] >= cvr_median:
        return "Improve creatives"
    return "Refine targeting"


channel["action"] = channel.apply(_channel_action, axis=1)

st.subheader("Channel Quality Matrix (CTR vs CVR)")
st.caption(
    "This matrix diagnoses where each channel is failing in the funnel. "
    "Top-right channels are strong on both click quality (CTR) and conversion quality (CVR), and are primary scale candidates. "
    "High CTR but low CVR points to post-click problems (landing page, offer, mismatch in intent). "
    "Low CTR but solid CVR points to creative/ad relevance issues. "
    "Action labels summarize the recommended next move per channel."
)
if alt:
    x_min = max(0, channel["ctr"].min() * 0.85)
    x_max = channel["ctr"].max() * 1.15
    y_min = max(0, channel["cvr"].min() * 0.85)
    y_max = channel["cvr"].max() * 1.15

    points = (
        alt.Chart(channel)
        .mark_circle(opacity=0.85)
        .encode(
            x=alt.X("ctr:Q", title="CTR", scale=alt.Scale(domain=[x_min, x_max])),
            y=alt.Y("cvr:Q", title="CVR", scale=alt.Scale(domain=[y_min, y_max])),
            size=alt.Size("cost:Q", title="Spend (EUR)"),
            color=alt.Color("roas:Q", title="ROAS"),
            tooltip=["channel", "ctr", "cvr", "roas", "cost", "action"],
        )
    )
    vline = alt.Chart(pd.DataFrame({"ctr_median": [ctr_median]})).mark_rule(color="#666").encode(x="ctr_median:Q")
    hline = alt.Chart(pd.DataFrame({"cvr_median": [cvr_median]})).mark_rule(color="#666").encode(y="cvr_median:Q")
    st.altair_chart((points + vline + hline), use_container_width=True)
else:
    st.scatter_chart(channel, x="ctr", y="cvr")

display = channel[["channel", "cost", "revenue", "roas", "ctr", "atc_rate", "cvr", "cpc", "cpa", "action"]].copy()
display["cost"] = display["cost"].apply(lambda v: format_k(v, currency=True))
display["revenue"] = display["revenue"].apply(lambda v: format_k(v, currency=True))
display["roas"] = display["roas"].apply(lambda v: format_float(v, 2))
display["ctr"] = display["ctr"].apply(lambda v: format_pct(v, 2))
display["atc_rate"] = display["atc_rate"].apply(lambda v: format_pct(v, 2))
display["cvr"] = display["cvr"].apply(lambda v: format_pct(v, 2))
display["cpc"] = display["cpc"].apply(lambda v: format_float(v, 2))
display["cpa"] = display["cpa"].apply(lambda v: format_float(v, 2))
st.dataframe(display, use_container_width=True)
