# ============================================================
# dashboard/app.py — Idea Mining Platform Dashboard
# ============================================================
# This Streamlit app reads from marts.analysis_ideas (the final
# dbt mart) and visualizes validated product ideas.
#
# Key concepts used:
#   1. @st.cache_data — prevents re-querying the DB on every click
#   2. st.columns() — creates side-by-side layouts
#   3. plotly.express — interactive charts (hover, zoom, filter)
#   4. st.sidebar — persistent filters that apply to all charts
#   5. Environment variables — DB credentials from Docker Compose
# ============================================================

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine


# ============================================================
# 1. PAGE CONFIG — Must be the FIRST Streamlit command
# ============================================================
# layout="wide" uses the full browser width instead of a narrow
# centered column. This is essential for dashboards.
# page_icon shows in the browser tab.

st.set_page_config(
    page_title="Idea Mining Dashboard",
    page_icon="💡",
    layout="wide",
)


# ============================================================
# 2. CUSTOM CSS — Override Streamlit's default styling
# ============================================================
# st.markdown with unsafe_allow_html=True lets you inject CSS.
# We use this to:
#   - Style the metric cards with background colors
#   - Reduce padding so more content fits on screen
#   - Add a subtle dark theme feel
#
# WHY NOT use a separate .css file?
# Streamlit doesn't serve static CSS files by default. Inline
# CSS via st.markdown is the standard approach.

st.markdown("""
<style>
    /* Reduce top padding — Streamlit adds too much by default */
    .block-container {
        padding-top: 1.5rem;
    }

    /* Style the metric cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e1e2e, #2a2a40);
        border: 1px solid #3a3a5c;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }

    /* Metric label (small text above the number) */
    div[data-testid="stMetric"] label {
        color: #a0a0c0;
        font-size: 0.85rem;
    }

    /* Metric value (the big number) */
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 3. DATABASE CONNECTION
# ============================================================
# @st.cache_data(ttl=600):
#   - Caches the DataFrame in memory for 600 seconds (10 min)
#   - Without this, EVERY user interaction (click a filter,
#     hover a chart) would re-execute the SQL query
#   - ttl (time-to-live) forces a refresh after 10 min so you
#     see new data after running `make pipeline` again
#
# os.getenv() reads env vars passed by docker-compose.yml.
# Fallback values ("admin", "localhost") let you run locally
# outside Docker too:
#   DB_HOST=localhost streamlit run app.py

@st.cache_data(ttl=600)
def load_data():
    """Load all validated ideas from the marts layer."""
    db_url = (
        f"postgresql://"
        f"{os.getenv('DB_USER', 'admin')}:"
        f"{os.getenv('DB_PASSWORD', 'super_admin')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:"
        f"{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'app_ideas')}"
    )
    engine = create_engine(db_url)
    df = pd.read_sql("SELECT * FROM marts.analysis_ideas", engine)
    return df


# ============================================================
# 4. LOAD DATA + ERROR HANDLING
# ============================================================
# Wrap in try/except because the DB might not be running.
# st.error() shows a red banner. st.stop() halts rendering
# so the rest of the dashboard doesn't crash with NameError.

try:
    df = load_data()
except Exception as e:
    st.error(f"❌ Cannot connect to database: {e}")
    st.info("Make sure PostgreSQL is running (`make up`) and "
            "marts.analysis_ideas has data (`make pipeline`).")
    st.stop()

if df.empty:
    st.warning("No data in marts.analysis_ideas. Run `make pipeline` first.")
    st.stop()


# ============================================================
# 5. SIDEBAR FILTERS
# ============================================================
# st.sidebar places widgets in the left panel. These filters
# modify the DataFrame BEFORE any chart renders.
#
# Pattern: multiselect with default=all options. When the user
# deselects values, df gets filtered down.
#
# .unique() pulls distinct values directly from the data, so
# filters always reflect what's actually in the DB.

st.sidebar.header("🔍 Filters")

# --- Urgency filter ---
urgency_options = sorted(df["urgency"].dropna().unique().tolist())
selected_urgency = st.sidebar.multiselect(
    "Urgency",
    options=urgency_options,
    default=urgency_options,  # All selected by default
)

# --- Product category filter ---
category_options = sorted(df["product_category"].dropna().unique().tolist())
selected_category = st.sidebar.multiselect(
    "Product Category",
    options=category_options,
    default=category_options,
)

# --- Subreddit filter ---
subreddit_options = sorted(df["subreddit"].unique().tolist())
selected_subreddit = st.sidebar.multiselect(
    "Subreddit",
    options=subreddit_options,
    default=subreddit_options,
)

# --- Pain intensity slider ---
# st.slider returns a tuple (min, max) when you give it two defaults.
pain_min, pain_max = st.sidebar.slider(
    "Pain Intensity Range",
    min_value=1, max_value=10,
    value=(1, 10),  # Default: full range
)

# --- Confidence slider ---
conf_min, conf_max = st.sidebar.slider(
    "Confidence Score Range",
    min_value=1, max_value=10,
    value=(1, 10),
)

# --- Apply all filters at once ---
# This creates a single boolean mask. Each condition returns a
# Series of True/False, and & combines them. .between() is
# inclusive on both ends by default.
mask = (
    df["urgency"].isin(selected_urgency)
    & df["product_category"].isin(selected_category)
    & df["subreddit"].isin(selected_subreddit)
    & df["pain_intensity"].between(pain_min, pain_max)
    & df["confidence_score"].between(conf_min, conf_max)
)
filtered = df[mask]


# ============================================================
# 6. HEADER
# ============================================================

st.title("💡 Idea Mining Dashboard")
st.caption(f"Showing **{len(filtered)}** of {len(df)} validated ideas  •  "
           f"Data from `marts.analysis_ideas`")


# ============================================================
# 7. KPI METRICS ROW
# ============================================================
# st.columns(5) creates 5 equal-width columns.
# st.metric() shows a label + big number + optional delta.
#
# We compute stats from `filtered` (not `df`) so the KPIs
# respond to sidebar filters.

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total Ideas", len(filtered))

col2.metric(
    "Avg Confidence",
    f"{filtered['confidence_score'].mean():.1f}" if len(filtered) else "—"
)

col3.metric(
    "Avg Pain",
    f"{filtered['pain_intensity'].mean():.1f}" if len(filtered) else "—"
)

wtp_count = filtered["willingness_to_pay"].sum()
wtp_pct = 100 * filtered["willingness_to_pay"].mean() if len(filtered) else 0
col4.metric("Willing to Pay", f"{wtp_count} ({wtp_pct:.0f}%)")

quality_issues = filtered["has_quality_issue"].sum()
col5.metric("Quality Issues", f"{quality_issues}")

st.divider()


# ============================================================
# 8. ROW 1: SCATTER PLOT + PRODUCT CATEGORY
# ============================================================
# st.columns([3, 2]) creates a 60/40 split (ratio, not pixels).
# The scatter plot gets more space because it's information-dense.

row1_left, row1_right = st.columns([3, 2])

# --- 8a. Pain vs Confidence Scatter ---
# This is the hero chart. Each dot is one idea.
# x = confidence (how sure the LLM is)
# y = pain (how severe the problem is)
# color = urgency (categorical → discrete colors)
# size = Reddit score (community engagement signal)
# hover_data = extra columns shown on hover tooltip
#
# The top-right quadrant (high pain + high confidence) is the
# sweet spot — those are your best product opportunities.

with row1_left:
    st.subheader("Pain Intensity vs Confidence")
    if len(filtered) > 0:
        fig_scatter = px.scatter(
            filtered,
            x="confidence_score",
            y="pain_intensity",
            color="urgency",
            size="score",
            size_max=20,
            hover_data=["title", "subreddit", "product_category"],
            color_discrete_map={
                "critical": "#ff4757",
                "high": "#ffa502",
                "medium": "#2ed573",
                "low": "#70a1ff",
            },
            labels={
                "confidence_score": "Confidence Score",
                "pain_intensity": "Pain Intensity",
                "score": "Reddit Score",
            },
        )
        # Update layout for dark theme feel
        fig_scatter.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",      # Transparent bg
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0c0",
            legend=dict(orientation="h", y=-0.15),
            height=420,
        )
        fig_scatter.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
        fig_scatter.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("No data matches filters.")

# --- 8b. Product Category Bar ---
# value_counts() gives us category → count, .reset_index() turns
# it back into a DataFrame that Plotly can chart.

with row1_right:
    st.subheader("Product Categories")
    if len(filtered) > 0:
        cat_counts = (
            filtered["product_category"]
            .value_counts()
            .reset_index()
        )
        cat_counts.columns = ["Category", "Count"]

        fig_cat = px.bar(
            cat_counts,
            x="Count", y="Category",
            orientation="h",
            color="Count",
            color_continuous_scale="tealgrn",
        )
        fig_cat.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0c0",
            showlegend=False,
            height=420,
            yaxis=dict(autorange="reversed"),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_cat, use_container_width=True)


# ============================================================
# 9. ROW 2: MONETIZATION + URGENCY + MARKET SIZE
# ============================================================
# Three equal columns for distribution charts.

row2_a, row2_b, row2_c = st.columns(3)

# --- 9a. Monetization Model Pie ---
with row2_a:
    st.subheader("Monetization Models")
    if len(filtered) > 0:
        mon_counts = filtered["monetization_model"].value_counts().reset_index()
        mon_counts.columns = ["Model", "Count"]

        fig_mon = px.pie(
            mon_counts,
            names="Model",
            values="Count",
            hole=0.4,  # Donut chart — looks more modern than a full pie
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_mon.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0c0",
            height=350,
            legend=dict(font=dict(size=11)),
        )
        # Show percentage inside the slices
        fig_mon.update_traces(textinfo="percent+label", textfont_size=11)
        st.plotly_chart(fig_mon, use_container_width=True)

# --- 9b. Urgency Distribution ---
with row2_b:
    st.subheader("Urgency Distribution")
    if len(filtered) > 0:
        urg_counts = filtered["urgency"].value_counts().reset_index()
        urg_counts.columns = ["Urgency", "Count"]

        # Explicit category order so bars always show in logical order
        urg_order = ["critical", "high", "medium", "low"]
        urg_counts["Urgency"] = pd.Categorical(
            urg_counts["Urgency"], categories=urg_order, ordered=True
        )
        urg_counts = urg_counts.sort_values("Urgency")

        fig_urg = px.bar(
            urg_counts,
            x="Urgency", y="Count",
            color="Urgency",
            color_discrete_map={
                "critical": "#ff4757",
                "high": "#ffa502",
                "medium": "#2ed573",
                "low": "#70a1ff",
            },
        )
        fig_urg.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0c0",
            showlegend=False,
            height=350,
        )
        st.plotly_chart(fig_urg, use_container_width=True)

# --- 9c. Market Size Signal ---
with row2_c:
    st.subheader("Market Size Signal")
    if len(filtered) > 0:
        mkt_counts = filtered["market_size_signal"].value_counts().reset_index()
        mkt_counts.columns = ["Market", "Count"]

        fig_mkt = px.pie(
            mkt_counts,
            names="Market",
            values="Count",
            hole=0.4,
            color_discrete_map={
                "large": "#2ed573",
                "medium": "#ffa502",
                "niche": "#70a1ff",
            },
        )
        fig_mkt.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0c0",
            height=350,
        )
        fig_mkt.update_traces(textinfo="percent+label", textfont_size=12)
        st.plotly_chart(fig_mkt, use_container_width=True)


st.divider()


# ============================================================
# 10. TOP SUBREDDITS BAR CHART
# ============================================================

st.subheader("🏆 Top Subreddits by Valid Ideas")

if len(filtered) > 0:
    sub_counts = (
        filtered["subreddit"]
        .value_counts()
        .head(15)
        .reset_index()
    )
    sub_counts.columns = ["Subreddit", "Ideas"]

    fig_sub = px.bar(
        sub_counts,
        x="Ideas", y="Subreddit",
        orientation="h",
        color="Ideas",
        color_continuous_scale="purp",
    )
    fig_sub.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#c0c0c0",
        height=400,
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_sub, use_container_width=True)


st.divider()


# ============================================================
# 11. IDEA DETAIL EXPANDER
# ============================================================
# Show the top 10 ideas as expandable cards. st.expander()
# creates a collapsible section — great for detail-on-demand.
#
# We sort by pain_intensity desc, then confidence_score desc
# (same ordering as the mart SQL).

st.subheader("🔥 Top Ideas — Detail View")

top_ideas = filtered.nlargest(10, ["pain_intensity", "confidence_score"])

for _, row in top_ideas.iterrows():
    # The expander label shows a summary; click to expand
    with st.expander(
        f"🎯 [{row['subreddit']}] {row['title'][:90]}  —  "
        f"Pain: {row['pain_intensity']} | Conf: {row['confidence_score']} | "
        f"Urgency: {row['urgency']}"
    ):
        detail_left, detail_right = st.columns(2)

        with detail_left:
            st.markdown(f"**Problem:** {row['problem_statement']}")
            st.markdown(f"**Solution:** {row['suggested_solution']}")
            st.markdown(f"**Target Audience:** {row['target_audience']}")
            st.markdown(f"**Existing Alternatives:** {row['existing_alternatives']}")

        with detail_right:
            st.markdown(f"**Category:** `{row['product_category']}`")
            st.markdown(f"**Monetization:** `{row['monetization_model']}`")
            st.markdown(f"**Market Size:** `{row['market_size_signal']}`")
            st.markdown(f"**Willing to Pay:** {'✅' if row['willingness_to_pay'] else '❌'}")
            st.markdown(f"**Competitive Gap:** {row['competitive_gap']}")
            st.markdown(f"**Reddit Score:** {row['score']}")
            if row["url"]:
                st.markdown(f"[Open Reddit Post]({row['url']})")


st.divider()


# ============================================================
# 12. FULL DATA TABLE
# ============================================================
# st.dataframe() renders an interactive table with sorting,
# searching, and column resizing built in.
#
# column_config lets you customize how specific columns render:
#   - LinkColumn makes URLs clickable
#   - NumberColumn can add formatting
#
# We select specific columns rather than showing everything
# to keep the table readable.

st.subheader("📋 All Ideas")

display_cols = [
    "title", "subreddit", "confidence_score", "pain_intensity",
    "urgency", "product_category", "monetization_model",
    "market_size_signal", "willingness_to_pay", "score",
    "problem_statement", "suggested_solution", "url",
]

st.dataframe(
    filtered[display_cols],
    use_container_width=True,
    height=500,
    column_config={
        "url": st.column_config.LinkColumn("Reddit Link", display_text="Open"),
        "title": st.column_config.TextColumn("Title", width="large"),
        "problem_statement": st.column_config.TextColumn("Problem", width="large"),
        "willingness_to_pay": st.column_config.CheckboxColumn("WTP"),
    },
)


# ============================================================
# 13. FOOTER
# ============================================================

st.markdown("---")
st.caption(
    "Built with Streamlit • Data from marts.analysis_ideas • "
    f"Last loaded: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}"
)