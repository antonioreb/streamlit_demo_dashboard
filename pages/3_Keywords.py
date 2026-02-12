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

st.header("Keyword Intelligence and Auto-Mining")

if df.empty:
    st.warning("No data for the current filters.")
    st.stop()

st.sidebar.subheader("Keyword Rules")
min_spend = st.sidebar.number_input("Min spend for actions", min_value=1.0, value=60.0, step=10.0)
min_orders_promote = st.sidebar.number_input("Min orders to promote", min_value=1, value=2)

kw = (
    df.groupby("keyword", as_index=False)[
        ["impressions", "clicks", "add_to_cart", "orders", "cost", "revenue"]
    ]
    .sum()
    .sort_values("cost", ascending=False)
)
kw["ctr"] = kw["clicks"] / kw["impressions"].replace(0, np.nan)
kw["atc_rate"] = kw["add_to_cart"] / kw["clicks"].replace(0, np.nan)
kw["cvr"] = kw["orders"] / kw["clicks"].replace(0, np.nan)
kw["roas"] = kw["revenue"] / kw["cost"].replace(0, np.nan)
kw["cpc"] = kw["cost"] / kw["clicks"].replace(0, np.nan)
kw["cpa"] = kw["cost"] / kw["orders"].replace(0, np.nan)
kw["efficiency"] = (kw["roas"] * kw["cvr"]) / kw["cpc"].replace(0, np.nan)
kw = kw.replace([np.inf, -np.inf], np.nan)

kw["negate_flag"] = (
    (kw["cost"] >= min_spend)
    & (
        (kw["orders"] == 0)
        | (kw["roas"] < (filters["target_roas"] * 0.75))
        | (kw["cpa"] > (filters["target_cpa"] * 1.3))
    )
)
kw["negate_reason"] = np.select(
    [
        kw["orders"] == 0,
        kw["roas"] < (filters["target_roas"] * 0.75),
        kw["cpa"] > (filters["target_cpa"] * 1.3),
    ],
    [
        "No orders at current spend",
        "ROAS far below target",
        "CPA well above target",
    ],
    default="Mixed performance drift",
)
kw["negate_priority"] = (
    (kw["cost"] * (1.2 - kw["roas"]).clip(lower=0))
    + (kw["cpa"] - filters["target_cpa"]).clip(lower=0)
).fillna(0)

summary = st.columns(5)
summary[0].metric("Keywords", f"{kw['keyword'].nunique():,}")
summary[1].metric("Negate Candidates", f"{int(kw['negate_flag'].sum()):,}")
summary[2].metric("Avg CTR", format_pct((kw["clicks"].sum() / kw["impressions"].sum()), 2))
summary[3].metric("Avg CVR", format_pct((kw["orders"].sum() / max(kw["clicks"].sum(), 1)), 2))
summary[4].metric("Avg CPC", f"EUR {kw['cost'].sum() / max(kw['clicks'].sum(), 1):,.2f}")

kw_by_channel = (
    df.groupby(["channel", "keyword"], as_index=False)[["clicks", "cost", "revenue"]]
    .sum()
    .sort_values("clicks", ascending=False)
)
kw_by_channel["cpc"] = kw_by_channel["cost"] / kw_by_channel["clicks"].replace(0, np.nan)
kw_by_channel["roas"] = kw_by_channel["revenue"] / kw_by_channel["cost"].replace(0, np.nan)
kw_by_channel = kw_by_channel.replace([np.inf, -np.inf], np.nan).dropna(subset=["cpc", "roas"])

st.subheader("CPC vs ROAS by Channel")
st.caption(
    "Channel-level weighted CPC/ROAS view using total spend and revenue. "
    "Bottom-right channels (low CPC, high ROAS) are strongest for scaling; top-left channels need cost and quality fixes. "
    "Use benchmark lines to quickly see which channels are above target ROAS and below average CPC."
)
if not kw_by_channel.empty:
    channel_totals = (
        kw_by_channel.groupby("channel", as_index=False)[["clicks", "cost", "revenue"]]
        .sum()
        .sort_values("cost", ascending=False)
    )
    kw_counts = kw_by_channel.groupby("channel", as_index=False)["keyword"].nunique()
    kw_counts = kw_counts.rename(columns={"keyword": "keywords"})
    channel_totals = channel_totals.merge(kw_counts, on="channel", how="left")
    channel_totals["cpc"] = channel_totals["cost"] / channel_totals["clicks"].replace(0, np.nan)
    channel_totals["roas"] = channel_totals["revenue"] / channel_totals["cost"].replace(0, np.nan)
    channel_totals = channel_totals.replace([np.inf, -np.inf], np.nan).dropna(subset=["cpc", "roas"])

    total_cost = channel_totals["cost"].sum()
    total_clicks = channel_totals["clicks"].sum()
    avg_cpc = total_cost / total_clicks if total_clicks > 0 else 0
    target_roas = filters["target_roas"]

    channel_totals["spend_share"] = channel_totals["cost"] / max(total_cost, 1)
    channel_totals["roas_gap"] = channel_totals["roas"] - target_roas
    channel_totals["cpc_gap"] = channel_totals["cpc"] - avg_cpc
    channel_totals["eff_index"] = (
        (channel_totals["roas"] / max(target_roas, 0.01))
        / (channel_totals["cpc"] / max(avg_cpc, 0.01))
    )

    def _channel_action(row):
        if row["roas"] >= target_roas * 1.1 and row["cpc"] <= avg_cpc * 1.05:
            return "Scale"
        if row["roas"] < target_roas * 0.9 and row["cpc"] > avg_cpc * 1.1:
            return "Fix cost + quality"
        if row["roas"] < target_roas * 0.9:
            return "Fix conversion"
        if row["cpc"] > avg_cpc * 1.1:
            return "Tighten bids"
        return "Maintain/Test"

    channel_totals["action"] = channel_totals.apply(_channel_action, axis=1)
    channel_totals["impact"] = channel_totals["cost"] * (target_roas - channel_totals["roas"]).clip(lower=0)

    top = st.columns(4)
    top[0].metric("Target ROAS", format_float(target_roas, 2))
    top[1].metric("Weighted Avg CPC", f"EUR {avg_cpc:,.2f}")
    top[2].metric("Scale Channels", f"{int((channel_totals['action'] == 'Scale').sum())}")
    top[3].metric("Fix Now Channels", f"{int((channel_totals['action'].isin(['Fix cost + quality', 'Fix conversion'])).sum())}")

    if alt:
        x_min = max(channel_totals["cpc"].min() * 0.8, 0)
        x_max = channel_totals["cpc"].max() * 1.2
        y_min = max(channel_totals["roas"].min() * 0.8, 0)
        y_max = channel_totals["roas"].max() * 1.2

        base = (
            alt.Chart(channel_totals)
            .mark_circle(opacity=0.85, stroke="#111", strokeWidth=0.6)
            .encode(
                x=alt.X("cpc:Q", title="CPC (EUR)", scale=alt.Scale(domain=[x_min, x_max])),
                y=alt.Y("roas:Q", title="ROAS", scale=alt.Scale(domain=[y_min, y_max])),
                size=alt.Size("cost:Q", title="Spend (EUR)"),
                color=alt.Color("action:N", title="Action"),
                tooltip=[
                    "channel",
                    "keywords",
                    alt.Tooltip("cost:Q", title="Spend", format=",.0f"),
                    alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
                    alt.Tooltip("cpc:Q", title="CPC", format=".2f"),
                    alt.Tooltip("roas:Q", title="ROAS", format=".2f"),
                    alt.Tooltip("spend_share:Q", title="Spend Share", format=".1%"),
                    alt.Tooltip("eff_index:Q", title="Efficiency Index", format=".2f"),
                ],
            )
        )
        labels = base.mark_text(dy=-10, fontSize=11, color="#222").encode(text="channel:N", size=alt.value(0))
        roas_rule = alt.Chart(pd.DataFrame({"target_roas": [target_roas]})).mark_rule(
            strokeDash=[6, 4], color="#555"
        ).encode(y="target_roas:Q")
        cpc_rule = alt.Chart(pd.DataFrame({"avg_cpc": [avg_cpc]})).mark_rule(
            strokeDash=[6, 4], color="#555"
        ).encode(x="avg_cpc:Q")
        st.altair_chart((base + labels + roas_rule + cpc_rule).properties(height=420), use_container_width=True)
    else:
        st.dataframe(
            channel_totals[["channel", "cost", "revenue", "cpc", "roas", "action"]].sort_values(
                ["roas", "cpc"], ascending=[False, True]
            ),
            use_container_width=True,
        )

    channel_view = channel_totals.sort_values(["impact", "cost"], ascending=[False, False]).copy()
    channel_view["cost"] = channel_view["cost"].apply(lambda v: format_k(v, currency=True))
    channel_view["revenue"] = channel_view["revenue"].apply(lambda v: format_k(v, currency=True))
    channel_view["cpc"] = channel_view["cpc"].apply(lambda v: format_float(v, 2))
    channel_view["roas"] = channel_view["roas"].apply(lambda v: format_float(v, 2))
    channel_view["spend_share"] = channel_view["spend_share"].apply(lambda v: format_pct(v, 1))
    channel_view["eff_index"] = channel_view["eff_index"].apply(lambda v: format_float(v, 2))
    channel_view["impact"] = channel_view["impact"].apply(lambda v: format_k(v, currency=True))
    st.dataframe(
        channel_view[
            ["channel", "action", "keywords", "cost", "revenue", "cpc", "roas", "spend_share", "eff_index", "impact"]
        ],
        use_container_width=True,
    )
else:
    st.info("Not enough channel data for CPC/ROAS analysis in current filters.")

auto_df = df[df["campaign_type"] == "Auto"].copy()
auto_terms = (
    auto_df.groupby(["campaign", "keyword"], as_index=False)[
        ["impressions", "clicks", "orders", "cost", "revenue"]
    ]
    .sum()
)
auto_terms["ctr"] = auto_terms["clicks"] / auto_terms["impressions"].replace(0, np.nan)
auto_terms["cvr"] = auto_terms["orders"] / auto_terms["clicks"].replace(0, np.nan)
auto_terms["roas"] = auto_terms["revenue"] / auto_terms["cost"].replace(0, np.nan)
auto_terms = auto_terms.replace([np.inf, -np.inf], np.nan).fillna(0)

ctr_med = auto_terms["ctr"].median() if not auto_terms.empty else 0
cvr_med = auto_terms["cvr"].median() if not auto_terms.empty else 0


def _suggest(row):
    if row["cost"] >= min_spend and row["orders"] >= min_orders_promote and row["roas"] >= filters["target_roas"]:
        return "PROMOTE_TO_MANUAL"
    if row["cost"] >= min_spend and row["orders"] == 0:
        return "NEGATE"
    if row["ctr"] >= ctr_med and row["cvr"] < cvr_med:
        return "FIX_LANDING"
    return "KEEP_RUNNING"


auto_terms["suggestion"] = auto_terms.apply(_suggest, axis=1)
auto_actions = auto_terms[auto_terms["suggestion"] != "KEEP_RUNNING"].copy()
auto_actions["impact"] = auto_actions["cost"] * (auto_actions["roas"] - filters["target_roas"])
auto_actions = auto_actions.sort_values("impact", ascending=False)

st.subheader("Negate Candidates Queue")
st.caption(
    "Top keywords likely wasting budget under current thresholds. "
    "Priority is ranked by spend exposure and efficiency gap so execution can start from highest impact."
)
neg_view = kw[kw["negate_flag"]].copy()
if neg_view.empty:
    st.info("No strong negate candidates under current rules.")
else:
    neg_view = neg_view.sort_values(["negate_priority", "cost"], ascending=[False, False]).head(20)
    neg_view["cost"] = neg_view["cost"].apply(lambda v: format_k(v, currency=True))
    neg_view["orders"] = neg_view["orders"].apply(format_k)
    neg_view["roas"] = neg_view["roas"].apply(lambda v: format_float(v, 2))
    neg_view["cpa"] = neg_view["cpa"].apply(lambda v: format_float(v, 2))
    neg_view["negate_priority"] = neg_view["negate_priority"].apply(lambda v: format_float(v, 1))
    st.dataframe(
        neg_view[
            ["keyword", "negate_reason", "cost", "orders", "roas", "cpa", "negate_priority"]
        ],
        use_container_width=True,
    )

st.subheader("Auto Campaign Mining Actions")
st.caption(
    "This table converts auto-campaign term performance into execution steps. "
    "PROMOTE_TO_MANUAL means the term has enough spend, orders, and ROAS to deserve exact/phrase build-out. "
    "NEGATE means budget is being spent without sufficient conversion signal. "
    "FIX_LANDING indicates strong click intent but weak post-click conversion, usually requiring page, offer, or audience-message alignment changes. "
    "Prioritize rows with the largest positive impact first."
)
if auto_actions.empty:
    st.info("No auto-campaign actions from current filters and thresholds.")
else:
    auto_view = auto_actions[
        ["campaign", "keyword", "cost", "orders", "revenue", "roas", "ctr", "cvr", "suggestion", "impact"]
    ].copy()
    auto_view["cost"] = auto_view["cost"].apply(lambda v: format_k(v, currency=True))
    auto_view["revenue"] = auto_view["revenue"].apply(lambda v: format_k(v, currency=True))
    auto_view["roas"] = auto_view["roas"].apply(lambda v: format_float(v, 2))
    auto_view["ctr"] = auto_view["ctr"].apply(lambda v: format_pct(v, 2))
    auto_view["cvr"] = auto_view["cvr"].apply(lambda v: format_pct(v, 2))
    auto_view["impact"] = auto_view["impact"].apply(lambda v: format_k(v, currency=True))
    st.dataframe(auto_view, use_container_width=True)

st.subheader("Keyword Intelligence Table")
st.caption(
    "Use this table to make bid and negative-keyword decisions at term level. "
    "Read CTR and CPC together for traffic quality and acquisition cost, then CVR/CPA/ROAS for conversion efficiency and profitability. "
    "Rows highlighted in red are likely negative candidates under current thresholds. "
    "Action: increase bids on high-ROAS terms with acceptable CPA; negate or downbid terms with sustained spend and weak conversion economics."
)
table = kw[
    [
        "keyword",
        "impressions",
        "clicks",
        "cost",
        "orders",
        "revenue",
        "ctr",
        "atc_rate",
        "cvr",
        "cpc",
        "cpa",
        "roas",
        "efficiency",
        "negate_flag",
    ]
].copy()


def _highlight_negate(row):
    is_negate = bool(table.loc[row.name, "negate_flag"])
    return ["background-color: #ffe6e6" if is_negate else ""] * len(row)


table["impressions"] = table["impressions"].apply(format_k)
table["clicks"] = table["clicks"].apply(format_k)
table["cost"] = table["cost"].apply(lambda v: format_k(v, currency=True))
table["orders"] = table["orders"].apply(format_k)
table["revenue"] = table["revenue"].apply(lambda v: format_k(v, currency=True))
table["ctr"] = table["ctr"].apply(lambda v: format_pct(v, 2))
table["atc_rate"] = table["atc_rate"].apply(lambda v: format_pct(v, 2))
table["cvr"] = table["cvr"].apply(lambda v: format_pct(v, 2))
table["cpc"] = table["cpc"].apply(lambda v: format_float(v, 2))
table["cpa"] = table["cpa"].apply(lambda v: format_float(v, 2))
table["roas"] = table["roas"].apply(lambda v: format_float(v, 2))
table["efficiency"] = table["efficiency"].apply(lambda v: format_float(v, 3))

display = table.drop(columns=["negate_flag"])
st.dataframe(display.style.apply(_highlight_negate, axis=1), use_container_width=True)
