"""
4_Documents.py — Document Management UI

Phase 4 feature. Allows users to:
- View all ingested documents (with metadata)
- Ingest new text documents directly
- See collection sizes per chunking strategy
- Delete documents (by document ID)
"""

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DeepVault — Documents",
    page_icon="📁",
    layout="wide",
)

API_BASE = "http://localhost:8000/api/v1"
API_KEY = "deepvault_secret_key"
HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("📁 Document Management")
st.markdown("Browse, ingest, and manage your knowledge base documents.")
st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_browse, tab_ingest, tab_stats = st.tabs(["📋 Browse Documents", "➕ Ingest Document", "📊 Collection Stats"])


# ---- BROWSE TAB ----
with tab_browse:
    st.subheader("Ingested Documents")

    col_refresh, col_filter = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col_filter:
        search_term = st.text_input("Search by source name", placeholder="e.g. paper.pdf")

    try:
        resp = requests.get(f"{API_BASE}/documents", headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            docs = resp.json().get("documents", [])
            if search_term:
                docs = [d for d in docs if search_term.lower() in d.get("source", "").lower()]

            if not docs:
                st.info("No documents found. Use the 'Ingest Document' tab to add content.")
            else:
                st.caption(f"Showing **{len(docs)}** document(s)")
                for doc in docs:
                    with st.expander(f"📄 {doc.get('source', 'Unknown')} — {doc.get('chunk_count', '?')} chunks"):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Chunks", doc.get("chunk_count", "—"))
                        c2.metric("Strategy", doc.get("chunking_strategy", "—"))
                        c3.metric("Ingested", doc.get("created_at", "—")[:10] if doc.get("created_at") else "—")
                        st.caption(f"**ID:** `{doc.get('id', '—')}`")
                        st.caption(f"**Hash:** `{doc.get('hash', '—')[:16]}...`")
        else:
            st.error(f"Failed to fetch documents: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to the API. Make sure the FastAPI server is running at `http://localhost:8000`.")


# ---- INGEST TAB ----
with tab_ingest:
    st.subheader("Ingest New Document")

    with st.form("ingest_form"):
        source_name = st.text_input(
            "Document Source Name", placeholder="my_paper.md", help="A unique identifier for this document"
        )
        content = st.text_area(
            "Document Content",
            height=300,
            placeholder="Paste the document text here...",
            help="Plain text or Markdown content to ingest",
        )
        chunker = st.selectbox(
            "Chunking Strategy",
            options=["sliding", "recursive", "structure", "semantic"],
            help="Which strategy to use for splitting this document into chunks",
        )
        submitted = st.form_submit_button("🚀 Ingest Document", use_container_width=True, type="primary")

        if submitted:
            if not source_name.strip():
                st.error("Please provide a source name.")
            elif not content.strip():
                st.error("Please provide document content.")
            else:
                with st.status(f"Ingesting '{source_name}' with {chunker} chunking...", expanded=True) as status:
                    try:
                        st.write("Initializing chunker models...")
                        resp = requests.post(
                            f"{API_BASE}/documents/text",
                            json={"source": source_name, "content": content, "chunking_strategy": chunker},
                            headers=HEADERS,
                            timeout=60,
                        )
                        if resp.status_code == 200:
                            result = resp.json()
                            status.update(label=f"✅ Successfully created {result.get('chunk_count', '?')} chunks!", state="complete", expanded=False)
                            st.success(
                                f"Created **{result.get('chunk_count', '?')}** chunks from `{source_name}`"
                            )
                            st.balloons()
                        elif resp.status_code == 409:
                            status.update(label="Duplicate detected", state="error", expanded=False)
                            st.warning(
                                f"⚠️ Document `{source_name}` already exists (duplicate detected by content hash)."
                            )
                        else:
                            status.update(label="Ingestion failed", state="error", expanded=False)
                            st.error(f"Ingestion failed: {resp.status_code} — {resp.text[:200]}")
                    except requests.exceptions.ConnectionError:
                        status.update(label="Connection Error", state="error", expanded=False)
                        st.error("Cannot connect to the API.")


# ---- STATS TAB ----
with tab_stats:
    st.subheader("Collection Statistics")
    st.caption("Document counts and chunk sizes across all 4 chunking strategy collections.")

    strategies = ["sliding", "recursive", "structure", "semantic"]
    cols = st.columns(len(strategies))

    for col, strategy in zip(cols, strategies):
        with col:
            try:
                resp = requests.get(
                    f"{API_BASE}/documents/stats?chunking_strategy={strategy}",
                    headers=HEADERS,
                    timeout=10,
                )
                if resp.status_code == 200:
                    stats = resp.json()
                    col.metric(
                        label=f"**{strategy.title()}**",
                        value=f"{stats.get('total_chunks', 0):,} chunks",
                        delta=f"{stats.get('total_documents', 0)} docs",
                    )
                else:
                    col.metric(f"**{strategy.title()}**", "—")
            except Exception:
                col.metric(f"**{strategy.title()}**", "Unavailable")

    st.divider()
    st.info(
        "💡 Each chunking strategy maintains its own isolated Qdrant collection (`deepvault_sliding`, `deepvault_recursive`, etc.) to enable fair side-by-side comparison."
    )
