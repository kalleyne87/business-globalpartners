import os
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
from databricks import sql

load_dotenv()

st.set_page_config(page_title="Restaurant Dashboard", layout="wide")
st.title("Restaurant Business Insights Dashboard")
st.caption(
    "Customer behavior, sales trends, loyalty impact, and location performance from Databricks Gold tables."
)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "").strip()
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH", "").strip()
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "").strip()

st.write("Host set:", bool(DATABRICKS_HOST))
st.write("HTTP path set:", bool(DATABRICKS_HTTP_PATH))
st.write("Token set:", bool(DATABRICKS_TOKEN))

def get_connection():
    return sql.connect(
        server_hostname=DATABRICKS_HOST.replace("https://", "").replace("http://", ""),
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    )

def load_table(query: str) -> pd.DataFrame:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall_arrow().to_pandas()
        
# -----------------------------
# Queries
# -----------------------------
QUERIES = {
    "customer_metrics": "SELECT * FROM business_global_partners_workspace.default.gold_customer_metrics",
    "sales_trends": "SELECT * FROM business_global_partners_workspace.default.gold_sales_trends",
    "loyalty": "SELECT * FROM business_global_partners_workspace.default.gold_loyalty",
    "location": "SELECT * FROM business_global_partners_workspace.default.gold_location",
}

# -----------------------------
# Load data
# -----------------------------
try:
    customer_df = load_table(QUERIES["customer_metrics"])
    sales_df = load_table(QUERIES["sales_trends"])
    loyalty_df = load_table(QUERIES["loyalty"])
    location_df = load_table(QUERIES["location"])
except Exception as e:
    st.error("Databricks connection or query failed")
    st.exception(e)
    st.stop()

# -----------------------------
# Standardize / convert columns
# -----------------------------
if "last_order_date" in customer_df.columns:
    customer_df["last_order_date"] = pd.to_datetime(customer_df["last_order_date"], errors="coerce")

if "month" in sales_df.columns:
    sales_df["month"] = pd.to_datetime(sales_df["month"], errors="coerce")

for df in [customer_df, sales_df, loyalty_df, location_df]:
    for col in df.columns:
        if any(token in col for token in ["spend", "revenue", "value", "total"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "count" in col or "orders" in col or "recency" in col:
            df[col] = pd.to_numeric(df[col], errors="coerce")


# -----------------------------
# KPI calculations
# -----------------------------
total_customers = int(customer_df["customer_id"].nunique()) if "customer_id" in customer_df.columns else 0

total_spend = float(customer_df["total_spend"].fillna(0).sum()) if "total_spend" in customer_df.columns else 0.0

avg_order_value = (
    float(customer_df["avg_order_value"].dropna().mean())
    if "avg_order_value" in customer_df.columns and not customer_df["avg_order_value"].dropna().empty
    else 0.0
)

at_risk_customers = (
    int((customer_df["churn_flag"].astype(str).str.lower() == "at risk").sum())
    if "churn_flag" in customer_df.columns
    else 0
)

# -----------------------------
# KPI cards
# -----------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Identifiable Customers", f"{total_customers:,}")
k2.metric("Total Customer Spend", f"${total_spend:,.2f}")
k3.metric("Avg Order Value", f"${avg_order_value:,.2f}")
k4.metric("At-Risk Customers", f"{at_risk_customers:,}")

st.divider()

# -----------------------------
# Customer metrics section
# -----------------------------
st.subheader("Customer Segmentation and Churn")
left, right = st.columns(2)

with left:
    if "customer_segment" in customer_df.columns:
        segment_df = (
            customer_df["customer_segment"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("customer_segment")
            .reset_index(name="customer_count")
        )
        fig_segment = px.bar(
            segment_df,
            x="customer_segment",
            y="customer_count",
            text_auto=True,
            title="Customer Segment Distribution",
        )
        fig_segment.update_layout(xaxis_title="Segment", yaxis_title="Customers")
        st.plotly_chart(fig_segment, use_container_width=True)
    else:
        st.info("customer_segment column not found.")

with right:
    if "churn_flag" in customer_df.columns:
        churn_df = (
            customer_df["churn_flag"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("churn_flag")
            .reset_index(name="customer_count")
        )
        fig_churn = px.pie(
            churn_df,
            names="churn_flag",
            values="customer_count",
            title="Churn Status",
        )
        st.plotly_chart(fig_churn, use_container_width=True)
    else:
        st.info("churn_flag column not found.")

if {"recency_days", "total_spend"}.issubset(customer_df.columns):
    scatter_df = customer_df.copy()
    if "customer_segment" not in scatter_df.columns:
        scatter_df["customer_segment"] = "All Customers"

    fig_scatter = px.scatter(
        scatter_df,
        x="recency_days",
        y="total_spend",
        color="customer_segment",
        hover_data=[c for c in ["customer_id", "order_count", "avg_order_value"] if c in scatter_df.columns],
        title="Recency vs Total Spend",
    )
    fig_scatter.update_layout(xaxis_title="Recency (days)", yaxis_title="Total Spend")
    st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# -----------------------------
# Sales trends section
# -----------------------------

st.subheader("Sales Trends Over Time")
if not sales_df.empty:
    month_col = "month" if "month" in sales_df.columns else sales_df.columns[0]
    revenue_col = "monthly_revenue" if "monthly_revenue" in sales_df.columns else "revenue"

    if revenue_col in sales_df.columns:
        sales_plot_df = sales_df.sort_values(month_col).copy()
        fig_sales = px.line(
            sales_plot_df,
            x=month_col,
            y=revenue_col,
            markers=True,
            title="Revenue Over Time",
        )
        fig_sales.update_layout(xaxis_title="Month", yaxis_title="Revenue")
        st.plotly_chart(fig_sales, use_container_width=True)
    else:
        st.info("Revenue column not found in sales trends table.")
else:
    st.info("No sales trends data returned.")

st.divider()

# -----------------------------
# Loyalty section
# -----------------------------
st.subheader("Loyalty Program Impact")
if not loyalty_df.empty:
    loyalty_key = "is_loyalty" if "is_loyalty" in loyalty_df.columns else loyalty_df.columns[0]
    loyalty_revenue_col = "total_revenue" if "total_revenue" in loyalty_df.columns else "revenue"

    loyalty_df["loyalty_labels"] = loyalty_df[loyalty_key].map({
        True: "Is Loyalty",
        False: "Non Loyalty"
    }).fillna(loyalty_df[loyalty_key].astype(str))

    if loyalty_revenue_col in loyalty_df.columns:
        fig_loyalty = px.bar(
            loyalty_df,
            x="loyalty_labels",
            y=loyalty_revenue_col,
            text_auto=True,
            title="Revenue by Loyalty Status",
        )
        fig_loyalty.update_layout(xaxis_title="Loyalty Status", yaxis_title="Total Revenue")
        st.plotly_chart(fig_loyalty, use_container_width=True)
    else:
        st.info("Revenue column not found in loyalty table.")
else:
    st.info("No loyalty data returned.")
st.divider()

# -----------------------------
# Location section
# -----------------------------
st.subheader("Location Performance")

if not location_df.empty:
    location_key = "restaurant_id" if "restaurant_id" in location_df.columns else location_df.columns[0]
    location_revenue_col = "total_revenue" if "total_revenue" in location_df.columns else "revenue"

    location_top_n = 10
    location_worst_n = 10
    
    if location_revenue_col in location_df.columns:
        top_locations_df = (
            location_df
            .sort_values(location_revenue_col, ascending=False)
            .head(location_top_n)
        )

        worst_locations_df = (
            location_df
            .sort_values(location_revenue_col, ascending=True)
            .head(location_top_n)
        )

        left, right = st.columns(2)

        with left:
            fig_top = px.bar(
                top_locations_df,
                x=location_key,
                y=location_revenue_col,
                text_auto=True,
                title=f"Top {location_top_n} Locations by Revenue",
            )
            fig_top.update_layout(
                xaxis_title="Restaurant ID",
                yaxis_title="Revenue"
            )
            st.plotly_chart(fig_top, use_container_width=True)

        with right:
            fig_worst = px.bar(
                worst_locations_df,
                x=location_key,
                y=location_revenue_col,
                text_auto=True,
                title=f"Worst {location_top_n} Locations by Revenue",
            )
            fig_worst.update_layout(
                xaxis_title="Restaurant ID",
                yaxis_title="Revenue"
            )
            st.plotly_chart(fig_worst, use_container_width=True)

    else:
        st.info("Revenue column not found in location table.")
else:
    st.info("No location data returned.")