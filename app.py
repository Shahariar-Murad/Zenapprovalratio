import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

try:
    import pycountry
except Exception:
    pycountry = None

st.set_page_config(
    page_title="ZEN Approval & Revenue Dashboard",
    page_icon="💳",
    layout="wide"
)

REQUIRED_COLUMNS = [
    "merchant_transaction_id", "created_at", "transaction_state", "authorization_amount",
    "authorization_currency", "customer_country", "payment_channel", "reject_code",
    "transaction_id"
]

CHANNELS = ["Apple Pay", "Google Pay", "Card"]


def get_country_name(country_code: str) -> str:
    """Convert ISO-2 country code to full country name for dashboard display."""
    if pd.isna(country_code):
        return "Unknown"
    code = str(country_code).strip().upper()
    if not code or code in {"NAN", "NONE", "UNKNOWN"}:
        return "Unknown"
    if pycountry is not None:
        try:
            country = pycountry.countries.get(alpha_2=code)
            if country:
                return country.name
        except Exception:
            pass
    fallback = {
        "AE": "United Arab Emirates", "AU": "Australia", "BE": "Belgium", "BO": "Bolivia",
        "BR": "Brazil", "CA": "Canada", "CL": "Chile", "DE": "Germany", "DO": "Dominican Republic",
        "DZ": "Algeria", "EC": "Ecuador", "EG": "Egypt", "ES": "Spain", "FR": "France",
        "GB": "United Kingdom", "HU": "Hungary", "JP": "Japan", "KE": "Kenya", "US": "United States",
        "ZA": "South Africa",
    }
    return fallback.get(code, code)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def load_data(uploaded_file=None) -> pd.DataFrame:
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    else:
        default_file = Path("ZEN-Authorization-Report.csv")
        if default_file.exists():
            df = pd.read_csv(default_file)
        else:
            st.info("Upload the ZEN Authorization Report CSV from the sidebar to start.")
            st.stop()

    df = normalize_columns(df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}")
        st.stop()

    # ZEN report timestamps are in GMT+0 / UTC.
    # Convert all dashboard dates and displayed timestamps to GMT+6 (Asia/Dhaka).
    df["created_at_utc"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["created_at_gmt6"] = df["created_at_utc"].dt.tz_convert("Asia/Dhaka")
    df["created_date_gmt6"] = df["created_at_gmt6"].dt.date

    # Keep created_at as the GMT+6 timestamp for dashboard display/export.
    df["created_at"] = df["created_at_gmt6"].dt.strftime("%Y-%m-%d %H:%M:%S GMT+6")
    df["authorization_amount"] = pd.to_numeric(df["authorization_amount"], errors="coerce").fillna(0)
    df["transaction_state"] = df["transaction_state"].astype(str).str.upper().str.strip()
    df["payment_channel"] = df["payment_channel"].astype(str).str.strip()
    df["customer_country"] = df["customer_country"].fillna("Unknown").astype(str).str.upper().str.strip()
    df["customer_country_name"] = df["customer_country"].apply(get_country_name)
    df["country_display"] = df.apply(
        lambda r: r["customer_country_name"] if r["customer_country_name"] != "Unknown" else "Unknown", axis=1
    )
    df["reject_code"] = df["reject_code"].fillna("Accepted / No Reject Code").astype(str)
    df["merchant_transaction_id"] = df["merchant_transaction_id"].fillna(df["transaction_id"]).astype(str)

    df = df[df["payment_channel"].isin(CHANNELS)].copy()
    return df


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    min_date = df["created_date_gmt6"].min()
    max_date = df["created_date_gmt6"].max()
    date_range = st.sidebar.date_input(
        "Date range (GMT+6 / Bangladesh Time)",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    selected_channels = st.sidebar.multiselect(
        "Payment channel",
        options=CHANNELS,
        default=CHANNELS
    )

    st.sidebar.markdown("### Country")
    all_countries = st.sidebar.checkbox("All countries", value=True)

    country_options = (
        df[["customer_country", "country_display"]]
        .drop_duplicates()
        .sort_values("country_display")
    )
    country_label_to_code = dict(
        zip(country_options["country_display"], country_options["customer_country"])
    )

    if all_countries:
        selected_country_codes = set(country_options["customer_country"].tolist())
    else:
        selected_country_labels = st.sidebar.multiselect(
            "Select country by full name",
            options=list(country_label_to_code.keys()),
            default=[]
        )
        selected_country_codes = {country_label_to_code[label] for label in selected_country_labels}

    filtered = df.copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        # Important: use the GMT+6 date column. The original CSV timestamp is GMT+0.
        filtered = filtered[
            (filtered["created_date_gmt6"] >= start_date) &
            (filtered["created_date_gmt6"] <= end_date)
        ]

    filtered = filtered[filtered["payment_channel"].isin(selected_channels)]
    filtered = filtered[filtered["customer_country"].isin(selected_country_codes)]
    return filtered


def summarize_by_channel(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for channel, group in df.groupby("payment_channel"):
        total_attempts = group["transaction_id"].nunique()
        unique_orders = group["merchant_transaction_id"].nunique()
        approved_attempts = group.loc[group["transaction_state"] == "ACCEPTED", "transaction_id"].nunique()

        order_status = group.groupby("merchant_transaction_id")["transaction_state"].apply(lambda x: (x == "ACCEPTED").any())
        approved_orders = int(order_status.sum())
        approval_ratio = (approved_orders / unique_orders * 100) if unique_orders else 0

        approved_revenue = group.loc[group["transaction_state"] == "ACCEPTED", "authorization_amount"].sum()
        avg_approved_ticket = approved_revenue / approved_orders if approved_orders else 0
        retry_ratio = ((total_attempts - unique_orders) / total_attempts * 100) if total_attempts else 0

        rows.append({
            "Payment Channel": channel,
            "Total Attempts": total_attempts,
            "Unique Orders": unique_orders,
            "Approved Orders": approved_orders,
            "Approval Ratio %": approval_ratio,
            "Approved Revenue": approved_revenue,
            "Average Approved Ticket": avg_approved_ticket,
            "Retry Ratio %": retry_ratio,
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values("Approved Revenue", ascending=False)


def summarize_country_revenue(df: pd.DataFrame) -> pd.DataFrame:
    accepted = df[df["transaction_state"] == "ACCEPTED"].copy()
    country_revenue = accepted.pivot_table(
        index="country_display",
        columns="payment_channel",
        values="authorization_amount",
        aggfunc="sum",
        fill_value=0
    ).reset_index()

    for channel in CHANNELS:
        if channel not in country_revenue.columns:
            country_revenue[channel] = 0

    country_revenue["Total Revenue"] = country_revenue[CHANNELS].sum(axis=1)
    country_revenue = country_revenue.rename(columns={"country_display": "Country"})
    country_revenue = country_revenue.sort_values("Total Revenue", ascending=False)
    return country_revenue


def summarize_country_approval(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (country, channel), group in df.groupby(["country_display", "payment_channel"]):
        unique_orders = group["merchant_transaction_id"].nunique()
        approved_orders = group.groupby("merchant_transaction_id")["transaction_state"].apply(lambda x: (x == "ACCEPTED").any()).sum()
        approved_revenue = group.loc[group["transaction_state"] == "ACCEPTED", "authorization_amount"].sum()
        rows.append({
            "Country": country,
            "Payment Channel": channel,
            "Unique Orders": unique_orders,
            "Approved Orders": int(approved_orders),
            "Approval Ratio %": (approved_orders / unique_orders * 100) if unique_orders else 0,
            "Approved Revenue": approved_revenue,
        })
    return pd.DataFrame(rows).sort_values(["Approved Revenue", "Approval Ratio %"], ascending=False)


def decline_reason_summary(df: pd.DataFrame) -> pd.DataFrame:
    rejected = df[df["transaction_state"] != "ACCEPTED"].copy()
    if rejected.empty:
        return pd.DataFrame()
    return (
        rejected.groupby(["payment_channel", "reject_code"])
        .agg(Declined_Attempts=("transaction_id", "nunique"), Declined_Amount=("authorization_amount", "sum"))
        .reset_index()
        .sort_values("Declined_Attempts", ascending=False)
    )


def format_money(value):
    return f"${value:,.2f}"


def render_kpis(summary: pd.DataFrame):
    total_orders = int(summary["Unique Orders"].sum()) if not summary.empty else 0
    total_approved = int(summary["Approved Orders"].sum()) if not summary.empty else 0
    total_revenue = float(summary["Approved Revenue"].sum()) if not summary.empty else 0
    overall_approval = (total_approved / total_orders * 100) if total_orders else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique Orders", f"{total_orders:,}")
    c2.metric("Approved Orders", f"{total_approved:,}")
    c3.metric("Approval Ratio", f"{overall_approval:.2f}%")
    c4.metric("Approved Revenue", format_money(total_revenue))


def render_insights(summary: pd.DataFrame, country_approval: pd.DataFrame, decline_summary: pd.DataFrame):
    st.subheader("Automated Insights")

    if summary.empty:
        st.warning("No data available for the selected filters.")
        return

    best_channel = summary.sort_values("Approval Ratio %", ascending=False).iloc[0]
    revenue_channel = summary.sort_values("Approved Revenue", ascending=False).iloc[0]
    weakest_channel = summary.sort_values("Approval Ratio %", ascending=True).iloc[0]

    insights = []
    insights.append(f"Highest approval ratio is from **{best_channel['Payment Channel']}** at **{best_channel['Approval Ratio %']:.2f}%**.")
    insights.append(f"Highest revenue contribution is from **{revenue_channel['Payment Channel']}** with **{format_money(revenue_channel['Approved Revenue'])}** approved revenue.")
    insights.append(f"Weakest method is **{weakest_channel['Payment Channel']}** with **{weakest_channel['Approval Ratio %']:.2f}%** approval. This method needs routing or configuration review.")

    if not country_approval.empty:
        top_country = country_approval.sort_values("Approved Revenue", ascending=False).iloc[0]
        insights.append(f"Top revenue country is **{top_country['Country']}** through **{top_country['Payment Channel']}**, generating **{format_money(top_country['Approved Revenue'])}**.")

    if not decline_summary.empty:
        top_decline = decline_summary.iloc[0]
        insights.append(f"Most frequent decline reason is **{top_decline['reject_code']}** on **{top_decline['payment_channel']}** with **{int(top_decline['Declined_Attempts'])}** declined attempts.")

    for item in insights:
        st.markdown(f"- {item}")

    st.markdown("**Routing recommendation logic:** Prefer the channel with the highest approval ratio for each country, but validate volume first. A country with very low volume may show 100% approval but may not be reliable enough for routing decisions.")


def main():
    st.title("ZEN Authorization Report Dashboard")
    st.caption("Approval ratio, country revenue, decline analysis, and routing insights for Apple Pay, Google Pay, and Card. All timestamps and date filters are converted from GMT+0 to GMT+6.")

    uploaded_file = st.sidebar.file_uploader("Upload ZEN Authorization Report CSV", type=["csv"])
    df = load_data(uploaded_file)
    filtered = filter_data(df)

    summary = summarize_by_channel(filtered)
    country_revenue = summarize_country_revenue(filtered)
    country_approval = summarize_country_approval(filtered)
    declines = decline_reason_summary(filtered)

    render_kpis(summary)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Executive Overview", "Country Revenue", "Country Approval", "Decline Analysis", "Raw Data"
    ])

    with tab1:
        st.subheader("Payment Method Performance")
        st.dataframe(
            summary.style.format({
                "Approval Ratio %": "{:.2f}%",
                "Approved Revenue": "${:,.2f}",
                "Average Approved Ticket": "${:,.2f}",
                "Retry Ratio %": "{:.2f}%",
            }),
            use_container_width=True
        )

        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(summary, x="Payment Channel", y="Approval Ratio %", text="Approval Ratio %", title="Approval Ratio by Payment Channel")
            fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.pie(summary, names="Payment Channel", values="Approved Revenue", title="Approved Revenue Share")
            st.plotly_chart(fig, use_container_width=True)

        render_insights(summary, country_approval, declines)

    with tab2:
        st.subheader("Country-wise Approved Revenue by Method")
        st.dataframe(
            country_revenue.style.format({c: "${:,.2f}" for c in CHANNELS + ["Total Revenue"]}),
            use_container_width=True
        )

        top_n = st.slider("Top countries to show", 5, 30, 15)
        chart_df = country_revenue.head(top_n).melt(
            id_vars="country_display",
            value_vars=CHANNELS,
            var_name="Payment Channel",
            value_name="Approved Revenue"
        )
        fig = px.bar(chart_df, x="country_display", y="Approved Revenue", color="Payment Channel", barmode="group", title=f"Top {top_n} Countries by Approved Revenue")
        fig.update_layout(xaxis_title="Country")
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Country-wise Approval Ratio")
        st.dataframe(
            country_approval.style.format({
                "Approval Ratio %": "{:.2f}%",
                "Approved Revenue": "${:,.2f}",
            }),
            use_container_width=True
        )

        min_orders = st.slider("Minimum unique orders for routing recommendation", 1, 50, 3)
        routing = country_approval[country_approval["Unique Orders"] >= min_orders].copy()
        if not routing.empty:
            routing = routing.sort_values(["Country", "Approval Ratio %", "Approved Revenue"], ascending=[True, False, False])
            routing = routing.groupby("Country").head(1).sort_values("Approved Revenue", ascending=False)
            st.subheader("Suggested Best Route by Country")
            st.dataframe(
                routing.rename(columns={"Payment Channel": "Suggested Route"}).style.format({
                    "Approval Ratio %": "{:.2f}%",
                    "Approved Revenue": "${:,.2f}",
                }),
                use_container_width=True
            )
        else:
            st.info("No countries meet the selected minimum order threshold.")

    with tab4:
        st.subheader("Decline Reason Comparison")
        st.dataframe(declines, use_container_width=True)
        if not declines.empty:
            fig = px.bar(declines.head(20), x="reject_code", y="Declined_Attempts", color="payment_channel", barmode="group", title="Top Decline Reasons by Channel")
            st.plotly_chart(fig, use_container_width=True)

    with tab5:
        st.subheader("Filtered Raw Data")
        raw_display = filtered.copy()
        raw_display = raw_display.rename(columns={"country_display": "Country", "created_date_gmt6": "created_date"})
        st.dataframe(raw_display, use_container_width=True)
        csv = raw_display.to_csv(index=False).encode("utf-8")
        st.download_button("Download Filtered Data", data=csv, file_name="zen_filtered_data.csv", mime="text/csv")


if __name__ == "__main__":
    main()
