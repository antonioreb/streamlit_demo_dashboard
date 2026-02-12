
import streamlit as st

from logic.data import load_data
from logic.ui import apply_sidebar_filters

try:
    import altair as alt
except Exception:
    alt = None

st.set_page_config(page_title="Ads Dashboard v1", layout="wide")

df = load_data()
df, _filters = apply_sidebar_filters(df)

st.title("Ads Dashboard")
st.write("Use the sidebar filters to slice performance across all views.")

if df.empty:
    st.warning("No data for the current filters.")
    st.stop()

spend = df["cost"].sum()
revenue = df["revenue"].sum()
orders = df["orders"].sum()
roas = revenue / spend if spend else 0

row = st.columns(4)
row[0].metric("Spend", f"€{spend:,.0f}")
row[1].metric("Revenue", f"€{revenue:,.0f}")
row[2].metric("Orders", f"{orders:,.0f}")
row[3].metric("ROAS", f"{roas:.2f}")

st.subheader("Channel Mix")
mix = df.groupby("channel", as_index=False)[["cost", "revenue"]].sum()
if alt:
    chart = (
        alt.Chart(mix)
        .mark_bar()
        .encode(
            x=alt.X("channel:N", title="Channel"),
            y=alt.Y("cost:Q", title="Spend (€)"),
            color=alt.Color("channel:N", legend=None),
            tooltip=["channel", "cost", "revenue"],
        )
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.bar_chart(mix.set_index("channel")["cost"])
