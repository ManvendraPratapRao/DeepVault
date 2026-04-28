"""
5_Feedback.py — Feedback Analytics Dashboard

Phase 5 / Session 26 feature.

Shows:
- Overall rating distribution
- Average ratings by retrieval strategy (to identify which strategy users prefer)
- Recent low-rated responses for quality review
- A/B test results summary
"""

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DeepVault — Feedback Analytics",
    page_icon="⭐",
    layout="wide",
)

API_BASE = "http://localhost:8000/api/v1"
API_KEY = "deepvault_secret_key"
HEADERS = {"X-API-KEY": API_KEY}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("⭐ Feedback Analytics")
st.markdown("User ratings on RAG responses — used to measure quality and guide strategy selection.")
st.divider()

# ---------------------------------------------------------------------------
# Submit Feedback Section (manual testing widget)
# ---------------------------------------------------------------------------

with st.expander("➕ Submit Test Feedback", expanded=False):
    with st.form("feedback_form"):
        col1, col2 = st.columns(2)
        with col1:
            test_query = st.text_input("Query", placeholder="What is BM25?")
            test_answer = st.text_area("Answer", placeholder="BM25 is a keyword-based retrieval algorithm...", height=100)
        with col2:
            test_rating = st.slider("Rating", min_value=1, max_value=5, value=4, help="1 = terrible, 5 = excellent")
            test_strategy = st.selectbox("Retrieval Strategy", ["vector", "hybrid", "hybrid_rerank", "auto"])
            test_comment = st.text_input("Comment (optional)", placeholder="The answer missed the context about...")

        fb_submitted = st.form_submit_button("Submit Feedback", type="primary")
        if fb_submitted:
            if not test_query or not test_answer:
                st.error("Please fill in query and answer.")
            else:
                try:
                    r = requests.post(
                        f"{API_BASE}/feedback",
                        json={
                            "request_id": f"manual-{hash(test_query) % 100000}",
                            "query_text": test_query,
                            "answer_text": test_answer,
                            "rating": test_rating,
                            "comment": test_comment or None,
                            "retrieval_strategy": test_strategy,
                        },
                        headers={**HEADERS, "Content-Type": "application/json"},
                        timeout=10,
                    )
                    if r.status_code == 200:
                        st.success(f"✅ Feedback submitted! ID: `{r.json().get('feedback_id', '?')}`")
                    else:
                        st.error(f"Failed: {r.status_code} — {r.text[:200]}")
                except Exception as e:
                    st.error(f"Error: {e}")

st.divider()

# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

try:
    resp = requests.get(f"{API_BASE}/feedback/analytics", headers=HEADERS, timeout=10)

    if resp.status_code != 200:
        st.error(f"Could not load analytics: {resp.status_code}")
        st.stop()

    data = resp.json()
    overall = data.get("overall", {})
    dist = data.get("rating_distribution", {})
    by_strategy = data.get("by_retrieval_strategy", {})
    low_rated = data.get("recent_low_ratings", [])

    # --- Overview metrics ---
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Total Feedback", overall.get("total_feedback", 0))
    avg = overall.get("average_rating", 0)
    stars = "⭐" * round(avg)
    col2.metric("⭐ Average Rating", f"{avg:.2f} / 5", delta=stars)

    positive_count = sum(v for k, v in dist.items() if int(k) >= 4)
    total_feedback = overall.get("total_feedback", 1)
    positive_rate = positive_count / max(total_feedback, 1)
    col3.metric("👍 Positive Rate (≥ 4★)", f"{positive_rate:.1%}")

    st.divider()

    # --- Rating distribution ---
    col_dist, col_strategy = st.columns(2)

    with col_dist:
        st.subheader("Rating Distribution")
        if dist:
            chart_data = {f"{k}★": v for k, v in sorted(dist.items(), key=lambda x: int(x[0]))}
            st.bar_chart(chart_data, color="#6366F1")
        else:
            st.info("No rating data yet.")

    with col_strategy:
        st.subheader("Average Rating by Retrieval Strategy")
        if by_strategy:
            rows = [
                {
                    "Strategy": strategy,
                    "Avg Rating": f"{info['avg_rating']:.2f} ⭐",
                    "Responses": info["total_responses"],
                }
                for strategy, info in sorted(by_strategy.items(), key=lambda x: -x[1]["avg_rating"])
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No strategy-level data yet. Submit feedback with a retrieval_strategy set.")

    st.divider()

    # --- Low-rated responses ---
    st.subheader("🔴 Recent Low-Rated Responses (≤ 2★)")
    st.caption("Use these to identify failure modes and improve prompts or retrieval strategies.")

    if low_rated:
        for entry in low_rated[:10]:
            rating_stars = "⭐" * entry.get("rating", 0)
            with st.expander(f"{rating_stars} [{entry.get('retrieval_strategy', 'unknown')}] {entry.get('query_text', '')[:80]}"):
                st.caption(f"**Date:** {entry.get('created_at', '—')[:16]}  |  **ID:** `{entry.get('id', '—')}`")
                if entry.get("comment"):
                    st.warning(f"💬 **Comment:** {entry['comment']}")
    else:
        st.success("🎉 No low-rated responses! Keep it up.")

except requests.exceptions.ConnectionError:
    st.error("⚠️ Cannot connect to the API. Make sure FastAPI is running at `http://localhost:8000`.")
    st.info("Run: `make dev` or `uvicorn app.main:app --reload`")
