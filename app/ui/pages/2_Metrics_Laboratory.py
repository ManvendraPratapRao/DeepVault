import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

# --- Page Configuration ---
st.set_page_config(
    page_title="Metrics Laboratory",
    page_icon="🧪",
    layout="wide",
)

RESULTS_FILE = Path("data/metrics_smoke_test_results.json")
PROGRESS_FILE = Path("data/eval_progress.json")
ENV_FILE = Path(".env")

# --- Load Environment (for Password) ---
def get_admin_password():
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.startswith("EVAL_ADMIN_PASSWORD="):
                    return line.split("=")[1].strip()
    return "deepvault_admin_2024" # Fallback

ADMIN_PASSWORD = get_admin_password()

# --- Custom Styling ---
st.markdown("""
<style>
    .metric-card {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30363d;
        text-align: center;
    }
    .best-perf { border-top: 4px solid #238636; }
    .worst-perf { border-top: 4px solid #da3633; }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.title("🧪 Metrics Laboratory")
st.caption("Deep-dive analytics and strategy benchmarking for the DeepVault RAG system.")

# --- Sidebar: Controls ---
with st.sidebar:
    st.header("Admin Controls")
    
    with st.expander("Trigger New Evaluation"):
        pwd = st.text_input("Admin Password", type="password")
        if st.button("🚀 Start Metrics Smoke Test"):
            if pwd == ADMIN_PASSWORD:
                # Trigger background process
                try:
                    # We use 'uv run' to ensure the environment is correct
                    subprocess.Popen(["uv", "run", "python", "scripts/eval_engine_metrics.py"])
                    st.success("Evaluation started in background!")
                except Exception as e:
                    st.error(f"Failed to start: {e}")
            else:
                st.error("Invalid password.")

    st.divider()
    
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r") as f:
            progress = json.load(f)
            
        st.subheader("Current Run Progress")
        st.progress(progress["percentage"] / 100)
        st.write(f"**Strategy**: {progress['current_strategy']}")
        st.write(f"**Run**: {progress['current_run']}/2")
        st.caption(f"Last updated: {progress['last_updated']}")
        
        if st.button("Refresh Progress"):
            st.rerun()

# --- Load Results ---
if not RESULTS_FILE.exists():
    st.warning("No evaluation results found. Please trigger a Metrics Smoke Test first.")
    st.stop()

with open(RESULTS_FILE, "r") as f:
    data = json.load(f)

raw_results = data["results"]
timestamp = data["timestamp"]

# Convert to DataFrame for easier plotting
rows = []
for strategy, items in raw_results.items():
    for item in items:
        rows.append({"strategy": strategy, **item})

df = pd.DataFrame(rows)

# --- 1. Top Section: Comparison Overview ---
st.subheader("📊 Strategy Performance Rankings")

# Group by strategy and calculate means/percentiles
summary_df = df.groupby("strategy").agg({
    "hit": "mean",
    "faithfulness": "mean",
    "relevance": "mean",
    "hallucination": "mean",
    "latency_ms": lambda x: x.quantile(0.95)
}).rename(columns={
    "hit": "P@k (Recall)",
    "faithfulness": "Faithfulness (1-5)",
    "relevance": "Relevance (1-5)",
    "hallucination": "Hallucination Rate (%)",
    "latency_ms": "p95 Latency (ms)"
})

# Format percentages
summary_df["P@k (Recall)"] = summary_df["P@k (Recall)"] * 100
summary_df["Hallucination Rate (%)"] = summary_df["Hallucination Rate (%)"] * 100

st.table(summary_df.sort_values("Faithfulness (1-5)", ascending=False).style.highlight_max(axis=0, color="#1e3a08").highlight_min(axis=0, color="#3e1b1b"))

# --- 2. Metric Breakdown (Interactive Charts) ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Faithfulness vs. Relevance")
    fig = px.box(df, x="strategy", y="faithfulness", color="strategy", 
                  title="Faithfulness Distribution (Higher is Better)")
    fig.update_layout(template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("⚡ Latency Analysis (p50 / p95 / p99)")
    latency_summary = df.groupby("strategy")["latency_ms"].agg([
        ("p50", "median"), 
        ("p95", lambda x: x.quantile(0.95)), 
        ("p99", lambda x: x.quantile(0.99))
    ])
    st.bar_chart(latency_summary)

# --- 3. Strategy Tradeoff View ---
st.divider()
st.subheader("🔄 Accuracy vs. Latency Tradeoff")
tradeoff_view = df.groupby("strategy").agg({
    "faithfulness": "mean",
    "latency_ms": lambda x: x.quantile(0.95)
}).reset_index()

fig_scatter = px.scatter(tradeoff_view, x="latency_ms", y="faithfulness", text="strategy",
                         size=[20, 20, 20, 20], color="strategy",
                         labels={"latency_ms": "p95 Latency (ms)", "faithfulness": "Avg Faithfulness Score"},
                         title="Strategy Tradeoff Matrix")
fig_scatter.update_traces(textposition='top center')
fig_scatter.update_layout(template="plotly_dark")
st.plotly_chart(fig_scatter, use_container_width=True)

# --- 4. Query Drill-Down ---
st.divider()
st.subheader("🔍 Query-Level Drill Down")
selected_q = st.selectbox("Select a query to inspect", options=df["question"].unique())

q_subset = df[df["question"] == selected_q]

for idx, row in q_subset.iterrows():
    with st.expander(f"Strategy: {row['strategy']} | Score: {row['faithfulness']}/5"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Faithfulness", f"{row['faithfulness']}/5")
        c2.metric("Relevance", f"{row['relevance']}/5")
        c3.metric("Similarity", f"{row['similarity']:.2f}")
        
        # In a real run, we would have stored the generated answer too. 
        # For now, we show the metrics.
        st.write(f"**Latency**: {row['latency_ms']:.1f}ms")
        st.write(f"**Hit**: {'✅' if row['hit'] else '❌'}")

# --- 5. Failure Analysis ---
st.divider()
st.subheader("❌ Failure Gallery (Hallucinations)")
hallucinations = df[df["hallucination"] == 1]
if not hallucinations.empty:
    st.dataframe(hallucinations[["strategy", "question", "faithfulness", "latency_ms"]].head(10))
else:
    st.success("No high-hallucination queries detected in current run!")
