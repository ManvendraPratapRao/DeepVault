import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.eval.pdf_generator import generate_pdf_from_markdown

# --- Page Configuration ---
st.set_page_config(
    page_title="Metrics Laboratory",
    page_icon="🧪",
    layout="wide",
)

EVAL_RUNS_DIR = Path("data/eval_runs")
DOCS_BENCHMARKS_DIR = Path("docs/benchmarks")

# Read admin password from environment (set in .env) — no hardcoded fallback.
ADMIN_PASSWORD = os.environ.get("EVAL_ADMIN_PASSWORD", "")

# --- Custom Styling ---
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# --- Header ---
st.title("🧪 Metrics Laboratory")
st.caption("Deep-dive analytics and strategy benchmarking for the DeepVault RAG system.")


# --- Helper: Get Runs ---
def get_available_runs():
    """Dynamically discover completed eval runs from docs/benchmarks."""
    if not DOCS_BENCHMARKS_DIR.exists():
        return []
    runs = []
    for file in DOCS_BENCHMARKS_DIR.glob("*.md"):
        runs.append(file.stem)
    # Also check data/eval_runs for runs that haven't had MD generated yet
    if EVAL_RUNS_DIR.exists():
        for d in EVAL_RUNS_DIR.iterdir():
            if d.is_dir() and d.name not in runs:
                if (d / "summary.json").exists():
                    runs.append(d.name)
    return sorted(list(set(runs)), reverse=True)


# --- Sidebar: Controls ---
with st.sidebar:
    st.header("Controls & Filters")

    available_runs = get_available_runs()
    selected_run = st.selectbox("Select Evaluation Run", available_runs) if available_runs else None

    if not available_runs:
        st.warning("No completed evaluation runs found.")

    st.divider()

    # Admin Controls
    with st.expander("Trigger New Benchmarking Run"):
        st.markdown("**Warning: Costs API Credits**")
        run_id = st.text_input("Run ID", value=f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        q_limit = st.number_input("Questions per Strategy Limit (0 for all)", min_value=0, value=25)

        chunk_strats = st.multiselect(
            "Chunking Strategies",
            ["sliding", "recursive", "structure", "semantic"],
            default=["sliding", "recursive", "structure", "semantic"],
        )

        all_r_opts = ["vector", "hybrid", "hybrid_rerank", "vector_rewrite", "hybrid_rewrite", "hybrid_rerank_rewrite"]
        r_strats = st.multiselect("Retrieval Strategies", all_r_opts, default=["vector"])

        gen_model = st.selectbox(
            "Generator Model",
            ["groq/llama-3.1-8b-instant", "groq/llama-3.3-70b-versatile", "groq/qwen/qwen3-32b"],
            index=1,
        )
        judge_model = st.selectbox("Judge Model", ["groq/llama-3.3-70b-versatile", "groq/qwen/qwen3-32b"], index=0)

        pwd = st.text_input("Admin Password", type="password")

        if st.button("🚀 Start Evaluation"):
            if pwd == ADMIN_PASSWORD:
                try:
                    cmd = ["uv", "run", "python", "-m", "scripts.eval.runner_v2", "--run-id", run_id]
                    if q_limit > 0:
                        cmd.extend(["--limit", str(int(q_limit))])
                    if chunk_strats:
                        cmd.extend(["--chunk-strategies", ",".join(chunk_strats)])
                    if r_strats:
                        cmd.extend(["--retrieval-strategies", ",".join(r_strats)])
                    if gen_model:
                        cmd.extend(["--generator", gen_model])
                    if judge_model:
                        cmd.extend(["--judge", judge_model])

                    # Spawn in background
                    subprocess.Popen(cmd)
                    st.success(f"Evaluation '{run_id}' started in the background! Please check the terminal for logs.")
                except Exception as e:
                    st.error(f"Failed to start: {e}")
            else:
                st.error("Invalid password.")

# --- Render Selected Run ---
if not selected_run:
    st.info("👈 Please trigger a run from the sidebar to view metrics.")
    st.stop()

run_dir = EVAL_RUNS_DIR / selected_run
summary_file = run_dir / "summary.json"

if not summary_file.exists():
    st.warning("Run is still executing or missing summary.json. Please wait for it to complete.")
    st.stop()

with open(summary_file) as f:
    summary_data = json.load(f)

# Convert to DataFrame
rows = []
for combo, data in summary_data.items():
    ret = data.get("custom_retrieval", {})
    ragas = data.get("ragas", {})

    rows.append(
        {
            "Strategy": combo,
            "Hit Rate": ret.get("hit_rate", 0),
            "MRR": ret.get("mrr", 0),
            "Precision": ret.get("precision", 0),
            "Latency P50 (ms)": ret.get("latency_p50_ms", 0),
            "Latency P95 (ms)": ret.get("latency_p95_ms", 0),
            "Context Precision": ragas.get("context_precision") or 0.0,
            "Context Recall": ragas.get("context_recall") or 0.0,
            "Faithfulness": ragas.get("faithfulness") or 0.0,
            "Answer Relevancy": ragas.get("answer_relevancy") or 0.0,
            "Answer Correctness": ragas.get("answer_correctness") or 0.0,
            "Score": (ret.get("hit_rate", 0) + (ragas.get("answer_correctness") or 0.0)),
        }
    )

df = pd.DataFrame(rows)
if df.empty:
    st.error("Summary data is empty.")
    st.stop()

df = df.sort_values(by="Score", ascending=False)

# --- Action Buttons: Download Reports ---
col1, col2 = st.columns(2)
md_path = DOCS_BENCHMARKS_DIR / f"{selected_run}.md"
pdf_path = DOCS_BENCHMARKS_DIR / f"{selected_run}.pdf"

# We must ensure the MD is generated if we have a summary.json
if not md_path.exists():
    from scripts.eval.report import generate_markdown_report

    generate_markdown_report(selected_run, summary_data)

with col1:
    with open(md_path, encoding="utf-8") as f:
        st.download_button(
            label="📄 Download Markdown Report", data=f.read(), file_name=md_path.name, mime="text/markdown"
        )

with col2:
    if st.button("📑 Generate & Download PDF Report"):
        with st.spinner("Rendering PDF via xhtml2pdf (Dark Mode)..."):
            try:
                generate_pdf_from_markdown(selected_run)
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="⬇️ Click here to Download PDF",
                        data=pdf_file.read(),
                        file_name=pdf_path.name,
                        mime="application/pdf",
                    )
            except Exception as e:
                st.error(f"Failed to generate PDF: {e}")

st.divider()

# --- 1. Strategy Leaderboard ---
st.subheader("🏆 Performance Leaderboard")

# Format columns for display
display_df = df.copy()
display_df["Hit Rate"] = display_df["Hit Rate"].apply(lambda x: f"{x * 100:.1f}%")
display_df["MRR"] = display_df["MRR"].apply(lambda x: f"{x:.3f}")
display_df["Context Precision"] = display_df["Context Precision"].apply(lambda x: f"{x * 100:.1f}%")
display_df["Faithfulness"] = display_df["Faithfulness"].apply(lambda x: f"{x:.3f}")
display_df["Answer Correctness"] = display_df["Answer Correctness"].apply(lambda x: f"{x:.3f}")

st.dataframe(
    display_df.drop(columns=["Score"]).set_index("Strategy"),
    use_container_width=True,
)

# --- 2. Cost-Benefit Dashboard ---
st.divider()
st.subheader("💸 Speed vs Quality (Production Viability)")

cb1, cb2 = st.columns(2)
with cb1:
    fig_lat = px.bar(
        df.sort_values("Latency P50 (ms)"),
        x="Strategy",
        y="Latency P50 (ms)",
        text_auto=".0f",
        title="Median Latency (P50 ms)",
        color="Strategy",
    )
    fig_lat.update_layout(template="plotly_dark", showlegend=False)
    st.plotly_chart(fig_lat, use_container_width=True)

with cb2:
    fig_scatter = px.scatter(
        df,
        x="Latency P95 (ms)",
        y="Answer Correctness",
        text="Strategy",
        color="Strategy",
        size="Hit Rate",
        size_max=30,
        title="Accuracy vs. P95 Latency (Bubble size = Hit Rate)",
        labels={"Latency P95 (ms)": "P95 Latency (ms)", "Answer Correctness": "Answer Correctness (Quality)"},
    )
    fig_scatter.update_traces(textposition="top right")
    fig_scatter.update_layout(template="plotly_dark", showlegend=False)
    st.plotly_chart(fig_scatter, use_container_width=True)

# --- 3. Retrieval Potency ---
st.divider()
st.subheader("⚡ Retrieval Potency")
fig_search = px.bar(
    df,
    x="Strategy",
    y=["Hit Rate", "MRR"],
    barmode="group",
    title="Custom Retrieval Metrics",
)
fig_search.update_layout(template="plotly_dark")
st.plotly_chart(fig_search, use_container_width=True)
