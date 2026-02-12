import numpy as np
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

st.header("Optimization Potential")

if df.empty:
    st.warning("No data for the current filters.")
    st.stop()

campaign = (
    df.groupby(["campaign", "channel", "campaign_type"], as_index=False)[
        ["impressions", "clicks", "add_to_cart", "orders", "cost", "revenue"]
    ]
    .sum()
)

campaign["ctr"] = campaign["clicks"] / campaign["impressions"].replace(0, np.nan)
campaign["cvr"] = campaign["orders"] / campaign["clicks"].replace(0, np.nan)
campaign["roas"] = campaign["revenue"] / campaign["cost"].replace(0, np.nan)
campaign["cpc"] = campaign["cost"] / campaign["clicks"].replace(0, np.nan)
campaign["cpa"] = campaign["cost"] / campaign["orders"].replace(0, np.nan)
campaign["eff_score"] = (campaign["roas"] * 0.55) + (campaign["cvr"] * 100 * 0.35) - (campaign["cpc"] * 0.1)
campaign = campaign.replace([np.inf, -np.inf], np.nan).fillna(0)

volume_cut = campaign["cost"].median()
eff_cut = campaign["eff_score"].median()


def _segment(row):
    high_volume = row["cost"] >= volume_cut
    high_eff = row["eff_score"] >= eff_cut
    if high_volume and high_eff:
        return "Scale"
    if high_volume and not high_eff:
        return "Optimize"
    if not high_volume and high_eff:
        return "Test"
    return "Pause"


def _action(row):
    if row["segment"] == "Scale":
        return "Increase budget 10-20%"
    if row["segment"] == "Optimize":
        return "Reduce bids and tighten targeting"
    if row["segment"] == "Test":
        return "Try new creatives and audience expansion"
    return "Pause or keep minimal learning budget"


campaign["segment"] = campaign.apply(_segment, axis=1)
campaign["action"] = campaign.apply(_action, axis=1)
campaign["priority"] = (campaign["cost"] * (filters["target_roas"] - campaign["roas"])).clip(lower=0)


st.subheader("Budget Reallocation Matrix")
st.caption(
    "This matrix balances efficiency and budget concentration at campaign level. "
    "Campaigns farther right have stronger blended economics (ROAS/CVR/CPC), and campaigns higher on the chart consume more spend. "
    "Top-right is best for scaling, top-left is usually where budget leaks, bottom-right is where controlled tests can be expanded, and bottom-left is pause/contain territory. "
    "Action: use this chart to decide where incremental budget should come from and where it should go."
)
if alt:
    x_min = campaign["eff_score"].min() * 0.9
    x_max = campaign["eff_score"].max() * 1.1
    y_max = campaign["cost"].max() * 1.1

    points = (
        alt.Chart(campaign)
        .mark_circle(opacity=0.8)
        .encode(
            x=alt.X("eff_score:Q", title="Efficiency Score", scale=alt.Scale(domain=[x_min, x_max])),
            y=alt.Y("cost:Q", title="Spend (EUR)", scale=alt.Scale(domain=[0, y_max])),
            size=alt.Size("revenue:Q", title="Revenue (EUR)"),
            color=alt.Color("segment:N", title="Segment"),
            tooltip=[
                "campaign",
                "channel",
                "campaign_type",
                "segment",
                "cost",
                "revenue",
                "roas",
                "ctr",
                "cvr",
                "action",
            ],
        )
    )
    vline = alt.Chart(pd.DataFrame({"eff_cut": [eff_cut]})).mark_rule(color="#666").encode(x="eff_cut:Q")
    hline = alt.Chart(pd.DataFrame({"volume_cut": [volume_cut]})).mark_rule(color="#666").encode(y="volume_cut:Q")
    st.altair_chart(points + vline + hline, use_container_width=True)
else:
    st.scatter_chart(campaign, x="eff_score", y="cost")

segment_mix = campaign.groupby("segment", as_index=False)[["cost", "revenue"]].sum()
segment_mix["spend_share"] = segment_mix["cost"] / segment_mix["cost"].sum()

left, right = st.columns(2)
with left:
    st.subheader("Spend Share by Segment")
    st.caption(
        "This chart shows how total spend is currently allocated across Scale, Optimize, Test, and Pause buckets. "
        "Healthy allocation depends on strategy, but excessive spend in Optimize/Pause usually indicates opportunity cost. "
        "Action: rebalance budget toward Scale/Test while reducing chronic Optimize/Pause exposure."
    )
    if alt:
        chart = (
            alt.Chart(segment_mix)
            .mark_bar()
            .encode(
                x=alt.X("segment:N", title="Segment"),
                y=alt.Y("spend_share:Q", title="Spend Share"),
                color=alt.Color("segment:N", legend=None),
                tooltip=["segment", "cost", "revenue", "spend_share"],
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(segment_mix.set_index("segment")["spend_share"])

with right:
    st.subheader("Segment Count")
    st.caption(
        "This chart shows how many campaigns fall into each operating segment. "
        "A high count in Optimize or Pause often means structural setup issues (keywords, audiences, creative quality, or landing-page fit). "
        "Action: use count plus spend share together to separate many-small issues from few-high-impact issues."
    )
    if alt:
        chart = (
            alt.Chart(campaign)
            .mark_bar(color="#4c78a8")
            .encode(
                x=alt.X("segment:N", title="Segment"),
                y=alt.Y("count():Q", title="Campaign Count"),
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.dataframe(campaign["segment"].value_counts())

st.subheader("Actionable Campaign Table")
action_table = campaign.sort_values(["priority", "cost"], ascending=[False, False]).copy()
action_table["cost"] = action_table["cost"].apply(lambda v: format_k(v, currency=True))
action_table["revenue"] = action_table["revenue"].apply(lambda v: format_k(v, currency=True))
action_table["roas"] = action_table["roas"].apply(lambda v: format_float(v, 2))
action_table["ctr"] = action_table["ctr"].apply(lambda v: format_pct(v, 2))
action_table["cvr"] = action_table["cvr"].apply(lambda v: format_pct(v, 2))
action_table["cpc"] = action_table["cpc"].apply(lambda v: format_float(v, 2))
action_table["cpa"] = action_table["cpa"].apply(lambda v: format_float(v, 2))
action_table["priority"] = action_table["priority"].apply(lambda v: format_k(v, currency=True))

st.dataframe(
    action_table[
        [
            "campaign",
            "channel",
            "campaign_type",
            "segment",
            "action",
            "cost",
            "revenue",
            "roas",
            "ctr",
            "cvr",
            "cpc",
            "cpa",
            "priority",
        ]
    ],
    use_container_width=True,
)
