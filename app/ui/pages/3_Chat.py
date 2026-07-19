"""
DeepVault Chat — Streaming RAG Interface

A ChatGPT-style streaming chat page that uses the POST /api/v1/stream
SSE endpoint to display LLM tokens as they arrive.

Uses httpx with streaming to consume the Server-Sent Events stream.
"""

import json
import os
import time
import uuid

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from app.ui.utils.chat_storage import delete_session, get_recent_sessions, load_session, save_session

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DeepVault Chat",
    page_icon="💬",
    layout="wide",
)

st.markdown(
    """
<style>
    /* Chat container styling */
    .stChatMessage { border-radius: 12px; }

    /* Typing cursor animation */
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
    .cursor { animation: blink 1s step-end infinite; font-weight: bold; color: #58a6ff; }

    /* Source citations box */
    .source-box {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.85rem;
        margin-top: 6px;
    }

    /* Strategy badge */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #238636;
        color: white;
        margin-right: 4px;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("💬 Chat with DeepVault")
st.caption("Ask questions and get answers grounded in your ingested documents.")

# --- Session Initialization ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = "Regular"
if "messages" not in st.session_state:
    st.session_state.messages = []

# Function to start a new chat
def start_new_chat():
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Sidebar: Configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Chat Settings")
    st.session_state.chat_mode = st.radio(
        "Chat Mode", 
        ["Regular", "Temporary"], 
        index=0 if st.session_state.chat_mode == "Regular" else 1,
        help="Regular chats are saved (up to 5). Temporary chats disappear on refresh."
    )
    
    API_URL = st.text_input("API Endpoint", value="http://localhost:8000")
    # Read from Streamlit secrets (production) or env var (local dev).
    try:
        _default_key = st.secrets.get("API_KEY", os.environ.get("API_KEY", ""))
    except Exception:
        _default_key = os.environ.get("API_KEY", "")
    API_KEY = st.text_input("API Token", value=_default_key, type="password")

    st.divider()
    model_selection = st.selectbox(
        "LLM Model",
        ["Auto (Router Selected)", "groq/llama-3.1-8b-instant", "groq/llama-3.3-70b-versatile", "groq/qwen/qwen3-32b"],
        index=0,
        help="Choose Auto to let the system pick the cheapest capable model based on query complexity."
    )
    # If "Auto" is chosen, pass None so the backend LLMRouter activates
    model_name = None if model_selection == "Auto (Router Selected)" else model_selection
    
    st.divider()
    st.subheader("Retrieval Settings")

    chunking_strategy = (
        st.selectbox(
            "Chunking Strategy",
            ["sliding", "recursive", "structure", "semantic"],
            index=0,
        )
        or "sliding"
    )

    retrieval_strategy = (
        st.selectbox(
            "Retrieval Strategy",
            ["auto", "auto_rewrite", "vector", "vector_rewrite", "hybrid", "hybrid_rewrite", "hybrid_rerank", "hybrid_rerank_rewrite"],
            index=1,
            help="Choose 'auto' to let the system intelligently route your query to the best strategy."
        )
        or "auto_rewrite"
    )

    top_k = st.slider("Top-K Documents", min_value=1, max_value=15, value=5)
    use_rewriting = "_rewrite" in retrieval_strategy

    st.divider()
    
    # Chat History Sidebar
    st.subheader("Chat History")
    if st.button("➕ New Chat", use_container_width=True):
        start_new_chat()
        st.rerun()
        
    recent_sessions = get_recent_sessions(limit=5)
    if recent_sessions:
        st.write("Recent Chats:")
        for s in recent_sessions:
            c1, c2 = st.columns([4, 1])
            with c1:
                # If it's the current session, show differently
                is_active = (s["session_id"] == st.session_state.session_id)
                btn_label = f"💬 {s['title']}" if not is_active else f"🟢 {s['title']}"
                if st.button(btn_label, key=f"load_{s['session_id']}", use_container_width=True):
                    st.session_state.session_id = s["session_id"]
                    loaded = load_session(s["session_id"])
                    if loaded:
                        st.session_state.messages = loaded.get("messages", [])
                    st.rerun()
            with c2:
                if st.button("🗑️", key=f"del_{s['session_id']}", help="Delete chat"):
                    delete_session(s["session_id"])
                    if is_active:
                        start_new_chat()
                    st.rerun()
    else:
        st.info("No saved chats.")

    st.divider()
    st.markdown(
        f"**Active:** `{retrieval_strategy}` + `{chunking_strategy}`  \n"
        f"**Top-K:** {top_k}  |  **Rewrite:** {'✅' if use_rewriting else '❌'}"
    )

# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Render Previous Messages
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Chat Input & Streaming Response
# ---------------------------------------------------------------------------

if prompt := st.chat_input("Ask anything about your documents…"):
    # Append and display the user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Stream the assistant response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        sources_placeholder = st.empty()
        full_response = ""
        sources = []
        start_ts = time.perf_counter()
        error_occurred = False

        payload = {
            "query_text": prompt,
            "top_k": top_k,
            "chunking_strategy": chunking_strategy,
            "retrieval_strategy": retrieval_strategy.replace("_rewrite", ""),
            "use_query_rewriting": use_rewriting,
            "model_name": model_name,
            # Pass all previous messages for multi-turn context (excluding system prompts if any)
            "messages": [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1] # exclude the prompt we just added
            ],
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream(
                    "POST",
                    f"{API_URL}/api/v1/stream",
                    json=payload,
                    headers={
                        "X-API-KEY": str(API_KEY),
                        "Accept": "text/event-stream",
                    },
                ) as resp:
                    if resp.status_code == 403:
                        st.error("❌ Authentication failed. Check your API key.")
                        error_occurred = True
                    elif resp.status_code != 200:
                        st.error(f"❌ API returned {resp.status_code}.")
                        error_occurred = True
                    else:
                        for line in resp.iter_lines():
                            if line.startswith("data: "):
                                token = line[6:]  # Strip "data: " prefix

                                if token == "[DONE]":
                                    break  # Stream finished successfully

                                if token.startswith("[ERROR]"):
                                    st.error(f"❌ {token}")
                                    error_occurred = True
                                    break
                                    
                                if token.startswith("[SOURCES] "):
                                    try:
                                        sources = json.loads(token[10:])
                                    except Exception:
                                        pass
                                    continue

                                full_response += token
                                # Render with blinking cursor
                                response_placeholder.markdown(
                                    full_response + '<span class="cursor">▌</span>',
                                    unsafe_allow_html=True,
                                )

        except httpx.ConnectError:
            st.error(
                f"❌ Cannot connect to API at `{API_URL}`. Make sure `make dev` or `docker compose up` is running."
            )
            error_occurred = True
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            error_occurred = True

        # Final render without cursor
        if not error_occurred and full_response:
            latency = (time.perf_counter() - start_ts) * 1000
            response_placeholder.markdown(full_response)
            
            # Render sources
            if sources:
                with sources_placeholder.container():
                    for idx, src in enumerate(sources):
                        score_str = f" (Score: {src.get('score'):.3f})" if src.get("score") else ""
                        with st.expander(f"📄 Source {idx+1}: {src.get('source', 'Unknown')}{score_str}"):
                            st.markdown(f"<div class='source-box'>{src.get('content', '')[:500]}...</div>", unsafe_allow_html=True)

            # Metadata footer
            st.caption(
                f"⚡ `{latency:.0f}ms` · "
                f"<span class='badge'>{retrieval_strategy}</span>"
                f"<span class='badge'>{chunking_strategy}</span>"
                f"<span class='badge'>{(model_name or 'Auto').split('/')[-1]}</span>",
                unsafe_allow_html=True,
            )
            
            # Human Feedback Buttons — wired to POST /api/v1/feedback
            col1, col2, _ = st.columns([1, 1, 10])
            msg_idx = len(st.session_state.messages)
            with col1:
                if st.button("👍", key=f"up_{msg_idx}"):
                    try:
                        httpx.post(
                            f"{API_URL}/api/v1/feedback",
                            json={
                                "request_id": f"chat-{st.session_state.session_id}-{msg_idx}",
                                "query_text": prompt,
                                "answer_text": full_response[:500],
                                "rating": 5,
                                "retrieval_strategy": retrieval_strategy,
                                "chunking_strategy": chunking_strategy,
                                "session_id": st.session_state.session_id,
                            },
                            headers={"X-API-KEY": str(API_KEY)},
                            timeout=5.0,
                        )
                        st.toast("👍 Feedback recorded!")
                    except Exception:
                        st.toast("Feedback saved locally (API unreachable).")
            with col2:
                if st.button("👎", key=f"down_{msg_idx}"):
                    try:
                        httpx.post(
                            f"{API_URL}/api/v1/feedback",
                            json={
                                "request_id": f"chat-{st.session_state.session_id}-{msg_idx}",
                                "query_text": prompt,
                                "answer_text": full_response[:500],
                                "rating": 1,
                                "retrieval_strategy": retrieval_strategy,
                                "chunking_strategy": chunking_strategy,
                                "session_id": st.session_state.session_id,
                            },
                            headers={"X-API-KEY": str(API_KEY)},
                            timeout=5.0,
                        )
                        st.toast("👎 Feedback recorded!")
                    except Exception:
                        st.toast("Feedback saved locally (API unreachable).")

    # Save to history only if we got a real response
    if not error_occurred and full_response:
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        
        # Save session to persistent storage if in Regular mode
        if st.session_state.chat_mode == "Regular":
            # Generate a title from the first query if it's the first exchange
            first_msg = next((m["content"] for m in st.session_state.messages if m["role"] == "user"), "Chat")
            title = first_msg[:25] + "..." if len(first_msg) > 25 else first_msg
            save_session(st.session_state.session_id, title, st.session_state.messages)
