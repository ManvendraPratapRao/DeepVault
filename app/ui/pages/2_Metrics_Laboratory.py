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

EVAL_RUNS_DIR = Path("data/eval_runs")
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

# --- Helper: Get Runs ---
@st.cache_data(ttl=5) # Cache to avoid thrashing disk, but low TTL for live updates
def get_runs(strategy: str):
    s_dir = EVAL_RUNS_DIR / strategy
    if not s_dir.exists():
        return []
    
    runs = []
    # Sort folders by timestamp descending (newest first)
    for folder in sorted(s_dir.iterdir(), reverse=True):
        if folder.is_dir() and folder.name.startswith("run_"):
            runs.append(folder.name)
    return runs

def format_run_name(name):
    # e.g. run_20240413_131235 -> 2024-04-13 13:12:35
    try:
        parts = name.split('_')
        date_str = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:]}"
        time_str = f"{parts[2][:2]}:{parts[2][2:4]}:{parts[2][4:]}"
        return f"{date_str} {time_str}"
    except:
        return name

# --- Sidebar: Controls ---
with st.sidebar:
    st.header("Controls & Filters")
    
    # 1. Strategy & Run Selector
    selected_r_strat = st.selectbox("Retrieval Strategy", ["vector", "hybrid", "rerank"])
    available_runs = get_runs(selected_r_strat)
    
    selected_run = None
    if available_runs:
        selected_run = st.selectbox("Select Benchmark Run", available_runs, format_func=format_run_name)
    else:
        st.warning(f"No runs found for {selected_r_strat} strategy.")
    
    st.divider()

    # 2. Admin Controls
    with st.expander("Trigger New Benchmarking Run"):
        st.markdown("**Warning: Costs API Credits**")
        q_limit = st.number_input("Questions per Strategy", min_value=1, value=50, max_value=250)
        chunk_strats = st.multiselect("Chunking Strategies", ["fixed", "sliding", "structure", "semantic"], default=["fixed", "sliding", "structure", "semantic"])
        r_strats = st.multiselect("Retrieval Strategies", ["vector"], default=["vector"])
        
        dry_run = st.checkbox("Dry Run (Estimate costs only)", value=False)
        pwd = st.text_input("Admin Password", type="password")
        
        if st.button("🚀 Start Evaluation"):
            if pwd == ADMIN_PASSWORD:
                try:
                    cmd = ["uv", "run", "python", "scripts/eval_engine_metrics.py"]
                    if chunk_strats:
                        cmd.extend(["--chunking-strategies"] + chunk_strats)
                    if r_strats:
                        cmd.extend(["--retrieval-strategies"] + r_strats)
                    cmd.extend(["--limit", str(int(q_limit))])
                    if dry_run:
                        cmd.append("--dry-run")
                    
                    subprocess.Popen(cmd)
                    if dry_run:
                        st.info("Check terminal for Dry Run Output.")
                    else:
                        st.success("Evaluation started in background!")
                except Exception as e:
                    st.error(f"Failed to start: {e}")
            else:
                st.error("Invalid password.")

    st.divider()
    
    # 3. Live Progress Tracker
    active_run_dir = EVAL_RUNS_DIR / selected_r_strat / (selected_run if selected_run else "")
    progress_file = active_run_dir / "progress.json" if active_run_dir.exists() else None
    
    if progress_file and progress_file.exists():
        try:
            with open(progress_file, "r") as f:
                progress = json.load(f)
            
            # Check if it's less than a day old to show as "active"
            last_up = datetime.fromisoformat(progress["last_updated"])
            if (datetime.now() - last_up).total_seconds() < 86400:
                st.subheader("Live Run Progress")
                st.progress(progress["percentage"] / 100)
                st.write(f"**Strategy**: {progress['current_strategy']}")
                st.write(f"**Run pass**: {progress['current_run']}")
                st.caption(f"Last updated: {progress['last_updated']}")
                if st.button("Refresh Dashboard"):
                    st.rerun()
        except Exception:
            pass

# --- Load Selected Run Data ---
if not selected_run:
    st.info("👈 Please select or trigger a run from the sidebar.")
    st.stop()

run_dir = EVAL_RUNS_DIR / selected_r_strat / selected_run

try:
    with open(run_dir / "config.json", "r") as f:
        config_data = json.load(f)
        
    with open(run_dir / "results.json", "r") as f:
        results_data = json.load(f)
        
    with open(run_dir / "summary.json", "r") as f:
        summary_data = json.load(f)
except FileNotFoundError:
    st.warning("Run files are still generating. Please click 'Refresh Dashboard' in the sidebar.")
    st.stop()

# Convert to DataFrame
rows = []
for strategy, items in results_data.items():
    if not items:
        continue
    for item in items:
        rows.append({"strategy": strategy, **item})

if not rows:
    st.warning("No completed results yet for this run index.")
    st.stop()

df = pd.DataFrame(rows)

# --- 1. Run Config Summary ---
st.markdown("### 📋 Run Parameters")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Date", config_data["timestamp"][:10])
col2.metric("Questions Configured", config_data.get("questions_per_strategy", "Unknown"))
col3.metric("Evaluated Strategies", len(config_data.get("chunking_strategies", [])))
col4.metric("Judges Models", config_data.get("judge_faith_model", "Unknown").replace("-instant", ""))

# --- 2. Strategy Leaderboard ---
st.divider()
st.subheader("📊 Performance Leaderboard")

# Build dataframe from summary_data for cleaner logic
sd = summary_data.get("by_chunking_strategy", {})
summary_rows = []
for strat, metrics in sd.items():
    summary_rows.append({
        "Strategy": strat.capitalize(),
        "CP@1 (First Hit)": f"{metrics.get('context_precision_at_1', 0)*100:.1f}%",
        "R@k (Hit Rate)": f"{metrics.get('hit_rate', 0)*100:.1f}%",
        "Faithfulness": f"{metrics.get('faithfulness', 0):.2f}",
        "Relevance": f"{metrics.get('relevance', 0):.2f}",
        "Hallucination": f"{metrics.get('hallucination_rate', 0)*100:.1f}%",
        "Cost (¢ per 1K Qs)": f"{metrics.get('cost_cents_per_1k_queries', 0):.1f}¢",
        "Efficiency Index": f"{metrics.get('efficiency_index', 0):.2f}",
        "Latency p95": f"{metrics.get('p95_latency_ms', 0):.0f}ms",
    })

ldb_df = pd.DataFrame(summary_rows)
if not ldb_df.empty:
    st.dataframe(
        ldb_df.sort_values(by="Efficiency Index", ascending=False).set_index("Strategy"),
        use_container_width=True,
    )

# --- 3. Cost-Benefit Dashboard ---
st.divider()
st.subheader("💸 Cost-Benefit Matrix (Production Viability)")

cb_df = pd.DataFrame([
    {
        "strategy": k, 
        "cost_cents_1k": v.get("cost_cents_per_1k_queries", 0),
        "faithfulness": v.get("faithfulness", 0),
        "efficiency": v.get("efficiency_index", 0)
    } 
    for k, v in sd.items()
])

if not cb_df.empty:
    cb1, cb2 = st.columns(2)
    with cb1:
        fig_cost = px.bar(
            cb_df.sort_values("cost_cents_1k"), 
            x="strategy", y="cost_cents_1k", 
            text_auto='.1f',
            title="Estimated Cost per 1,000 Queries (Cents)",
            color="strategy",
            labels={"cost_cents_1k": "Cents (US)"}
        )
        fig_cost.update_layout(template="plotly_dark", showlegend=False)
        st.plotly_chart(fig_cost, use_container_width=True)
        
    with cb2:
        fig_scatter = px.scatter(
            cb_df, x="cost_cents_1k", y="faithfulness", 
            text="strategy", color="strategy",
            size="efficiency", size_max=30,
            title="Faithfulness vs. Cost (Bubble size = Efficiency Index)",
            labels={"cost_cents_1k": "Cost per 1k (Cents)", "faithfulness": "Quality (Faithfulness)"}
        )
        fig_scatter.update_traces(textposition='top right')
        fig_scatter.update_layout(template="plotly_dark", showlegend=False)
        st.plotly_chart(fig_scatter, use_container_width=True)

# --- 4. Quality Distribution (Category Splits + Boxplots) ---
st.divider()
st.subheader("📈 Quality Breakdown")

qb1, qb2 = st.columns(2)
with qb1:
    fig_spread = px.box(
        df, x="strategy", y="faithfulness", color="strategy", 
        title="Faithfulness Variabilty Spread"
    )
    fig_spread.update_layout(template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig_spread, use_container_width=True)

with qb2:
    # Bar chart showing Research vs Synthetic
    split_data = []
    for k, v in sd.items():
        split_data.append({"strategy": k, "source": "Research", "score": v.get("research_faithfulness", 0)})
        split_data.append({"strategy": k, "source": "Synthetic", "score": v.get("synthetic_faithfulness", 0)})
    split_df = pd.DataFrame(split_data)
    
    if not split_df.empty:
        fig_split = px.bar(
            split_df, x="strategy", y="score", color="source", barmode="group",
            title="Domain Resilience (Research vs. Synthetic)",
            labels={"score": "Avg Faithfulness"}
        )
        fig_split.update_layout(template="plotly_dark")
        st.plotly_chart(fig_split, use_container_width=True)

# --- 5. Latency & Retrieval ---
st.divider()
st.subheader("⚡ Latency & Search Accuracy")

lr1, lr2 = st.columns(2)
with lr1:
    fig_hist = px.histogram(
        df, x="latency_ms", color="strategy", barmode="overlay", marginal="box", 
        title="Latency Spread (ms)"
    )
    fig_hist.update_layout(template="plotly_dark", xaxis_title="Latency (ms)", yaxis_title="Query Count")
    st.plotly_chart(fig_hist, use_container_width=True)

with lr2:
    search_data = []
    for k, v in sd.items():
        search_data.append({"strategy": k, "metric": "Hit Rate (In Top K)", "val": v.get("hit_rate", 0)*100})
        search_data.append({"strategy": k, "metric": "Context Precision @1", "val": v.get("context_precision_at_1", 0)*100})
    search_df = pd.DataFrame(search_data)
    if not search_df.empty:
        fig_search = px.bar(
            search_df, x="strategy", y="val", color="metric", barmode="group",
            title="Retrieval Potency (%)",
            labels={"val": "Percentage %"}
        )
        fig_search.update_layout(template="plotly_dark")
        st.plotly_chart(fig_search, use_container_width=True)


# --- 6. Query X-Ray ---
st.divider()
st.subheader("🔍 Query X-Ray (Full Trace Analysis)")
selected_q = st.selectbox("Select a query to investigate across strategies:", options=df["question"].unique())

q_subset = df[df["question"] == selected_q]

if not q_subset.empty:
    ground_truth = q_subset.iloc[0]["ground_truth"]
    st.info(f"**Target Source**: {q_subset.iloc[0].get('category', 'unknown').upper()} | **Ground Truth Answer**: {ground_truth}")
    
    all_strategies = sorted(df["strategy"].unique().tolist())
    cols = st.columns(max(len(all_strategies), 1))
    
    for i, strategy in enumerate(all_strategies):
        with cols[i]:
            st.markdown(f"#### {strategy.upper().replace('_VECTOR', '')}")
            
            strat_data = q_subset[q_subset["strategy"] == strategy]
            if not strat_data.empty:
                row = strat_data.iloc[0]
                
                # Check CP1 and Hit
                hit_emoji = "✅" if row['hit'] == 1 else "❌"
                cp1_emoji = "🥇" if row['context_precision_at_1'] == 1 else ""
                
                st.caption(f"Cost: **${row['cost_usd']:.5f}** | Latency: **{row['latency_ms']:.0f}ms**")
                
                c1, c2 = st.columns(2)
                c1.metric("Faithfulness", f"{row['faithfulness']}/5")
                c2.metric("Retrieval", hit_emoji + cp1_emoji)
                
                with st.container(border=True):
                    st.write("**Answer**")
                    st.caption(row["generated_answer"])
                
                with st.expander("Show Judge Reasoning"):
                    st.markdown(f"**Faithfulness**:\n{row.get('faithfulness_reasoning', 'N/A')}")
                    st.divider()
                    st.markdown(f"**Relevance**:\n{row.get('relevance_reasoning', 'N/A')}")
                
                with st.expander(f"View Sources ({len(row['sources'])})"):
                    for s_idx, source in enumerate(row["sources"]):
                        badge = "🥇 " if s_idx == 0 else ""
                        st.markdown(f"**{badge}Chunk {source['chunk_index']}** (Score: {source['score']:.3f})")
                        st.caption(source["content"])
                        st.divider()
            else:
                st.warning("No execution for this strategy.")

# --- 7. Failure Analysis ---
st.divider()
st.subheader("❌ Failure Gallery")

tab1, tab2 = st.tabs(["Hallucination Hall of Shame", "Retrieval Misses"])

with tab1:
    hallucinations = df[df["hallucination"] == 1]
    if not hallucinations.empty:
        st.warning(f"Detected {len(hallucinations)} queries with severe hallucinations (Faithfulness <= 2).")
        st.dataframe(
            hallucinations[["strategy", "category", "question", "generated_answer", "faithfulness_reasoning"]],
            use_container_width=True
        )
    else:
        st.success("Clean run! No critical hallucinations detected.")

with tab2:
    misses = df[df["hit"] == 0]
    if not misses.empty:
        st.error(f"Retrieval completely missed the target document for {len(misses)} query attempts.")
        st.dataframe(
            misses[["strategy", "category", "question", "ground_truth", "precision_at_k"]],
            use_container_width=True
        )
    else:
        st.success("Top-k retrieval was 100% successful.")
