"""
DeepVault Chat — Streaming RAG Interface

A ChatGPT-style streaming chat page that uses the POST /api/v1/stream
SSE endpoint to display LLM tokens as they arrive.

Uses httpx with streaming to consume the Server-Sent Events stream.
"""

import time

import httpx
import streamlit as st

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

st.title("💬 DeepVault Chat")
st.caption(
    "Streaming RAG answers powered by Groq Llama-3.3-70b. "
    "Tokens appear as they are generated — no waiting."
)
st.divider()

# ---------------------------------------------------------------------------
# Sidebar: Configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Session Settings")

    API_URL = st.text_input("API Endpoint", value="http://localhost:8000")
    API_KEY = st.text_input("API Token", value="deepvault_secret_key", type="password")

    st.divider()
    st.subheader("Retrieval Settings")

    chunking_strategy = st.selectbox(
        "Chunking Strategy",
        ["fixed", "sliding", "structure", "semantic"],
        index=0,
    ) or "fixed"

    retrieval_strategy = st.selectbox(
        "Retrieval Strategy",
        ["vector", "hybrid", "hybrid_rerank"],
        index=1,
    ) or "hybrid"

    top_k = st.slider("Top-K Documents", min_value=1, max_value=15, value=5)
    use_rewriting = st.checkbox("Query Rewriting (Groq)", value=False)

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown(
        f"**Active:** `{retrieval_strategy}` + `{chunking_strategy}`  \n"
        f"**Top-K:** {top_k}  |  **Rewrite:** {'✅' if use_rewriting else '❌'}"
    )

# ---------------------------------------------------------------------------
# Chat State Init
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
        full_response = ""
        start_ts = time.perf_counter()
        error_occurred = False

        payload = {
            "query_text": prompt,
            "top_k": top_k,
            "chunking_strategy": chunking_strategy,
            "retrieval_strategy": retrieval_strategy,
            "use_query_rewriting": use_rewriting,
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream(
                    "POST",
                    f"{API_URL}/api/v1/stream",
                    json=payload,
                    headers={
                        "X-API-KEY": API_KEY,
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

                                full_response += token
                                # Render with blinking cursor
                                response_placeholder.markdown(
                                    full_response + '<span class="cursor">▌</span>',
                                    unsafe_allow_html=True,
                                )

        except httpx.ConnectError:
            st.error(
                f"❌ Cannot connect to API at `{API_URL}`. "
                "Make sure `make dev` or `docker compose up` is running."
            )
            error_occurred = True
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            error_occurred = True

        # Final render without cursor
        if not error_occurred and full_response:
            latency = (time.perf_counter() - start_ts) * 1000
            response_placeholder.markdown(full_response)

            # Metadata footer
            st.caption(
                f"⚡ `{latency:.0f}ms` · "
                f"<span class='badge'>{retrieval_strategy}</span>"
                f"<span class='badge'>{chunking_strategy}</span>",
                unsafe_allow_html=True,
            )

    # Save to history only if we got a real response
    if not error_occurred and full_response:
        st.session_state.messages.append({"role": "assistant", "content": full_response})
