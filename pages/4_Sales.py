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
df, _filters = apply_sidebar_filters(df)

st.header("Sales Outcomes")

if df.empty:
    st.warning("No data for the current filters.")
    st.stop()

revenue = df["revenue"].sum()
orders = df["orders"].sum()
aov = revenue / orders if orders else 0
atc = df["add_to_cart"].sum() if "add_to_cart" in df.columns else 0
checkout_rate = orders / atc if atc else 0

daily = df.groupby("date_day", as_index=False)[["orders", "revenue"]].sum()
daily["aov"] = daily["revenue"] / daily["orders"].replace(0, np.nan)
daily["aov"] = daily["aov"].fillna(0)
daily["orders_7d"] = daily["orders"].rolling(7, min_periods=1).mean()

prod = (
    df.groupby(["product", "category"], as_index=False)[["orders", "revenue"]]
    .sum()
    .sort_values("revenue", ascending=False)
)
prod["rev_share"] = prod["revenue"] / prod["revenue"].sum()
top5_share = prod.head(5)["rev_share"].sum()

kpis = st.columns(5)
kpis[0].metric("Revenue", format_k(revenue, currency=True))
kpis[1].metric("Orders", format_k(orders))
kpis[2].metric("AOV", f"EUR {aov:,.2f}")
kpis[3].metric("Checkout Rate", format_pct(checkout_rate, 2))
kpis[4].metric("Top 5 Product Share", format_pct(top5_share, 1))

st.subheader("Order Volume and AOV")
st.caption(
    "This trend separates demand volume (orders) from basket quality (AOV). "
    "Rising orders with flat or falling AOV can still grow revenue, but may compress margin if discounting is driving the mix. "
    "Rising AOV with weak order growth suggests premium mix strength but possible top-of-funnel limits. "
    "Action: use this view to decide whether to prioritize volume campaigns or value/mix optimization."
)
if alt:
    max_orders = max(daily["orders_7d"].max(), 1) * 1.15
    max_aov = max(daily["aov"].max(), 1) * 1.15
    base = alt.Chart(daily).encode(x=alt.X("date_day:T", title="Date"))
    orders_line = (
        base.mark_line(color="#1f77b4", strokeWidth=2.2, interpolate="monotone")
        .encode(
            y=alt.Y("orders_7d:Q", title="Orders (7d avg)", scale=alt.Scale(domain=[0, max_orders])),
            tooltip=["date_day", "orders_7d"],
        )
    )
    aov_line = (
        base.mark_line(color="#e45756", strokeWidth=2, interpolate="monotone", strokeDash=[6, 4])
        .encode(
            y=alt.Y(
                "aov:Q",
                title="AOV (EUR)",
                axis=alt.Axis(titleColor="#e45756", labelColor="#e45756"),
                scale=alt.Scale(domain=[0, max_aov]),
            ),
            tooltip=["aov"],
        )
    )
    st.altair_chart(alt.layer(orders_line, aov_line).resolve_scale(y="independent"), use_container_width=True)
else:
    st.line_chart(daily.set_index("date_day")[["orders_7d", "aov"]])

cat = df.groupby("category", as_index=False)[["orders", "revenue"]].sum().sort_values("revenue", ascending=False)
cat["aov"] = cat["revenue"] / cat["orders"].replace(0, np.nan)
cat = cat.fillna(0)

left, right = st.columns(2)
with left:
    st.subheader("Revenue Mix by Category")
    st.caption(
        "This donut shows where revenue is concentrated by category. "
        "High concentration can be positive for focus, but also increases dependency risk. "
        "Action: protect top categories with stable budget coverage and build second-tier categories to reduce concentration risk."
    )
    if alt:
        chart = (
            alt.Chart(cat)
            .mark_arc(innerRadius=55)
            .encode(
                theta=alt.Theta("revenue:Q"),
                color=alt.Color("category:N", title="Category"),
                tooltip=["category", "revenue", "orders", "aov"],
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(cat.set_index("category")["revenue"])

with right:
    st.subheader("AOV by Category")
    st.caption(
        "This chart compares average order value across categories. "
        "Categories with high AOV can support higher CPC tolerance if conversion remains healthy. "
        "Action: pair this with conversion metrics to decide where premium positioning or bundles can be pushed."
    )
    if alt:
        chart = (
            alt.Chart(cat)
            .mark_bar(color="#4c78a8")
            .encode(
                x=alt.X("aov:Q", title="AOV (EUR)", scale=alt.Scale(zero=True)),
                y=alt.Y("category:N", sort="-x"),
                tooltip=["category", "aov", "orders", "revenue"],
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(cat.set_index("category")["aov"])

pareto = prod[["product", "revenue"]].copy().sort_values("revenue", ascending=False)
pareto["cum_rev_share"] = pareto["revenue"].cumsum() / pareto["revenue"].sum()
pareto["rank"] = np.arange(1, len(pareto) + 1)

st.subheader("Product Concentration (Pareto)")
st.caption(
    "This Pareto view shows how quickly total revenue accumulates across top products. "
    "If the cumulative line reaches high percentages early, sales are concentrated in a small SKU set. "
    "Action: secure inventory and media continuity for top products, and test growth plans for mid-tier products to reduce concentration risk."
)
if alt:
    bars = (
        alt.Chart(pareto)
        .mark_bar(color="#72b7b2")
        .encode(
            x=alt.X("product:N", sort=None, title="Product"),
            y=alt.Y("revenue:Q", title="Revenue (EUR)", scale=alt.Scale(zero=True)),
            tooltip=["product", "revenue", "cum_rev_share"],
        )
    )
    line = (
        alt.Chart(pareto)
        .mark_line(color="#e45756", strokeWidth=2.2)
        .encode(
            x=alt.X("product:N", sort=None),
            y=alt.Y(
                "cum_rev_share:Q",
                title="Cumulative Revenue Share",
                axis=alt.Axis(format="%"),
                scale=alt.Scale(domain=[0, 1]),
            ),
        )
    )
    st.altair_chart(alt.layer(bars, line).resolve_scale(y="independent"), use_container_width=True)
else:
    st.bar_chart(pareto.set_index("product")["revenue"])

table = prod[["product", "category", "orders", "revenue", "rev_share"]].copy()
table["orders"] = table["orders"].apply(format_k)
table["revenue"] = table["revenue"].apply(lambda v: format_k(v, currency=True))
table["rev_share"] = table["rev_share"].apply(lambda v: format_pct(v, 1))
st.dataframe(table, use_container_width=True)
