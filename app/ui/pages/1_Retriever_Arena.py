import streamlit as st
import httpx
import asyncio
import time
from typing import List, Dict, Any

# --- Page Configuration ---
# Note: Page config must be the first Streamlit command in the page script
st.set_page_config(
    page_title="Retriever Arena",
    page_icon="🧩",
    layout="wide",
)

# --- Custom Styling (Premium Aesthetics) ---
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    .stChatMessage {
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #30363d;
    }
    .strategy-card {
        background-color: #161b22;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #238636;
        margin-bottom: 20px;
    }
    .source-pill {
        display: inline-block;
        background-color: #21262d;
        color: #58a6ff;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin-right: 5px;
        border: 1px solid #30363d;
    }
    .latency-tag {
        color: #8b949e;
        font-size: 0.85em;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# --- State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- API Helpers ---
async def query_strategy(
    text: str, 
    strategy: str, 
    api_url: str, 
    api_key: str,
    top_k: int = 5, 
    temperature: float = 0.0
) -> Dict[str, Any]:
    """Call the DeepVault API for a specific chunking strategy."""
    headers = {"X-API-KEY": api_key}
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            payload = {
                "query_text": text,
                "strategy": strategy,
                "top_k": top_k,
            }
            response = await client.post(f"{api_url}/api/v1/query", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

# --- Sidebar: Control Center ---
with st.sidebar:
    st.title("🧩 DeepVault Arena")
    st.subheader("Diagnostic Controls")
    
    API_URL = st.text_input("API Endpoint", value="http://localhost:8000")
    API_KEY = st.text_input("API Token", value="deepvault_secret_key", type="password")
    
    st.divider()
    
    COL1_STRATEGY = st.selectbox(
        "Strategy A (Left Panel)", 
        options=["fixed", "sliding", "structure", "semantic"],
        index=0
    )
    
    COL2_STRATEGY = st.selectbox(
        "Strategy B (Right Panel)", 
        options=["fixed", "sliding", "structure", "semantic"],
        index=3
    )
    
    st.divider()
    
    TOP_K = st.slider("Retrieval Depth (Top-K)", min_value=1, max_value=10, value=5)
    TEMPERATURE = st.slider("LLM Temperature", min_value=0.0, max_value=1.0, value=0.0, step=0.1)
    
    if st.button("Clear Arena History"):
        st.session_state.messages = []
        st.rerun()

# --- Main Arena ---
st.header("RAG Strategy Battleground")
st.caption("Compare how different chunking strategies impact retrieval grounding and answer quality.")

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            # Display side-by-side results from history
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**{message['strategy_a']['name'].upper()}**")
                st.write(message['strategy_a']['answer'])
            with col_b:
                st.markdown(f"**{message['strategy_b']['name'].upper()}**")
                st.write(message['strategy_b']['answer'])

# Chat Input
if prompt := st.chat_input("Ask a question about the synthesized corpus..."):
    # Store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Trigger Generation
    with st.chat_message("assistant"):
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.info(f"Inference: {COL1_STRATEGY}...")
            container_a = st.empty()
        
        with col_b:
            st.info(f"Inference: {COL2_STRATEGY}...")
            container_b = st.empty()

        # Run both queries concurrently
        async def run_concurrent_queries():
            return await asyncio.gather(
                query_strategy(prompt, COL1_STRATEGY, API_URL, API_KEY, TOP_K, TEMPERATURE),
                query_strategy(prompt, COL2_STRATEGY, API_URL, API_KEY, TOP_K, TEMPERATURE)
            )

        t0 = time.perf_counter()
        res_a, res_b = asyncio.run(run_concurrent_queries())
        t_total = time.perf_counter() - t0

        # --- Render Column A ---
        with col_a:
            if "error" in res_a:
                st.error(f"Error: {res_a['error']}")
            else:
                container_a.markdown(res_a["answer"])
                st.markdown(f"<span class='latency-tag'>Latency: {res_a['latency_ms']:.1f}ms</span>", unsafe_allow_html=True)
                
                with st.expander(f"🔍 {COL1_STRATEGY} Context X-Ray"):
                    for i, source in enumerate(res_a.get("sources", [])):
                        score = source.get("score")
                        score_display = f"{score * 100:.1f}%" if score is not None else "N/A"
                        st.markdown(f"**Chunk {i+1}** (Relevance: {score_display})")
                        st.caption(f"Source: {source['metadata'].get('source', 'Unknown')}")
                        st.text_area(f"Content {i}", source["content"], height=150, key=f"a_{i}")
                        st.divider()

        # --- Render Column B ---
        with col_b:
            if "error" in res_b:
                st.error(f"Error: {res_b['error']}")
            else:
                container_b.markdown(res_b["answer"])
                st.markdown(f"<span class='latency-tag'>Latency: {res_b['latency_ms']:.1f}ms</span>", unsafe_allow_html=True)
                
                with st.expander(f"🔍 {COL2_STRATEGY} Context X-Ray"):
                    for i, source in enumerate(res_b.get("sources", [])):
                        score = source.get("score")
                        score_display = f"{score * 100:.1f}%" if score is not None else "N/A"
                        st.markdown(f"**Chunk {i+1}** (Relevance: {score_display})")
                        st.caption(f"Source: {source['metadata'].get('source', 'Unknown')}")
                        st.text_area(f"Content {i}", source["content"], height=150, key=f"b_{i}")
                        st.divider()

        # Store for session history
        st.session_state.messages.append({
            "role": "assistant",
            "strategy_a": {"name": COL1_STRATEGY, "answer": res_a.get("answer", "Error")},
            "strategy_b": {"name": COL2_STRATEGY, "answer": res_b.get("answer", "Error")}
        })
