import streamlit as st

# --- Page Configuration ---
st.set_page_config(
    page_title="DeepVault | RAG Control Center",
    page_icon="🤖",
    layout="wide",
)

# --- Custom Styling ---
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: -webkit-linear-gradient(#238636, #2ea043);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #8b949e;
        margin-top: -10px;
        margin-bottom: 30px;
    }
    .feature-card {
        background-color: #161b22;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #30363d;
        height: 100%;
        transition: transform 0.3s ease;
    }
    .feature-card:hover {
        transform: translateY(-5px);
        border-color: #58a6ff;
    }
</style>
""", unsafe_allow_html=True)

# --- Content ---
st.markdown("<h1 class='main-header'>DeepVault</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Autonomous AI Knowledge Platform & RAG Diagnostics</p>", unsafe_allow_html=True)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class='feature-card'>
        <h3>🧩 Retriever Arena</h3>
        <p>Live, side-by-side diagnostic tool to compare chunking strategies in real-time. 
        Battle-test your query logic across Fixed, Sliding, Structure, and Semantic collections.</p>
        <p><i>Use this to debug specific queries and visualize retrieval context.</i></p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Arena", use_container_width=True):
        st.switch_page("pages/1_Retriever_Arena.py")

with col2:
    st.markdown("""
    <div class='feature-card'>
        <h3>🧪 Metrics Laboratory</h3>
        <p>Enterprise-grade benchmarking suite. Analyze Faithfulness, Relevance, and Latency (p95) 
        across thousands of automated test cases using LLM-as-a-judge (Llama-3-70b).</p>
        <p><i>Use this for structural evaluation and production readiness checks.</i></p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Explore Laboratory", use_container_width=True):
        st.switch_page("pages/2_Metrics_Laboratory.py")

st.divider()

st.subheader("System Status")
c1, c2, c3, c4 = st.columns(4)
c1.success("Vector Store: Connected")
c2.success("LLM (Groq): Online")
c3.info("Strategy: Hybrid-Active")
c4.warning("Embedding: BGE-v1.5")

st.info("💡 **Tip**: Use the sidebar to navigate between toolsets. DeepVault is currently optimized for high-precision technical retrieval.")
