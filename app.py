"""EU AI Act RAG Demo — Streamlit UI."""
import time
import streamlit as st

from src.config import DEFAULT_EMBEDDER, DEFAULT_GENERATOR, TOP_K, LOW_CONFIDENCE_THRESHOLD
from src.embedders import REGISTRY as EMBEDDER_REGISTRY, get_embedder
from src.generators import REGISTRY as GENERATOR_REGISTRY, get_generator
from src.ingest import ingest
from src.lex_client import get_structured_context
from src.retrieve import retrieve
from src.prompts import SYSTEM_PROMPT, build_user_prompt

st.set_page_config(
    page_title="EU AI Act — Pharma RAG Demo",
    page_icon="⚖️",
    layout="wide",
)

st.markdown("""
<style>
    /* Header — fixed, dark navy, title baked in via pseudo-element */
    header[data-testid="stHeader"] {
        background: linear-gradient(90deg, #1d3461 0%, #009eb5 60%, #3d9142 100%);
        position: fixed !important;
        top: 0; left: 0; right: 0;
        z-index: 999;
        min-height: 6rem !important;
        display: flex !important;
        align-items: center !important;
    }
    header[data-testid="stHeader"] button { opacity: 1 !important; visibility: visible !important; }
    header[data-testid="stHeader"] svg { fill: #ffffff !important; }
    header[data-testid="stHeader"]::after {
        content: "EU AI Act — Pharma Compliance Assistant";
        color: #ffffff;
        font-size: 2rem;
        font-weight: 700;
        position: absolute;
        left: 50%;
        transform: translateX(-50%);
        white-space: nowrap;
    }

    /* Remove default top gap, just clear the header */
    [data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }
    [data-testid="stAppViewContainer"] > .main > .block-container {
        padding-top: 6.5rem !important;
        padding-bottom: 1rem !important;
    }

    /* Title — hidden, now in header */
    h1 { display: none !important; }

    /* Sidebar — light teal background, navy text (keeps widgets readable) */
    [data-testid="stSidebar"] { background-color: #eaf4f6; border-right: 3px solid #009eb5; }

    /* Sidebar headings and labels */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label { color: #1d3461 !important; }

    /* Subheadings */
    h2, h3 { color: #1d3461 !important; }

    /* Chat messages — teal left border */
    [data-testid="stChatMessage"] { border-left: 3px solid #009eb5; padding-left: 0.75rem; }

    /* User avatar — teal */
    [data-testid="stChatMessageAvatarUser"] {
        background-color: #009eb5 !important;
        color: #ffffff !important;
    }

    /* Assistant avatar — navy */
    [data-testid="stChatMessageAvatarAssistant"] {
        background-color: #1d3461 !important;
        color: #ffffff !important;
    }

    /* Avatar SVG icons */
    [data-testid="stChatMessageAvatarUser"] svg,
    [data-testid="stChatMessageAvatarAssistant"] svg {
        fill: #ffffff !important;
    }

    /* Expander */
    [data-testid="stExpander"] summary { color: #1d3461 !important; font-weight: 600; }

    /* Captions */
    [data-testid="stCaptionContainer"] { color: #8c8c8c !important; }

    /* Dividers */
    hr { border-color: #009eb5; opacity: 0.3; }

    /* Sidebar toggle buttons — always visible */
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="collapsedControl"] button,
    section[data-testid="stSidebar"] ~ div button[kind="headerNoPadding"],
    header button[kind="headerNoPadding"] {
        opacity: 1 !important;
        visibility: visible !important;
        background-color: #009eb5 !important;
        border-radius: 4px !important;
    }
    [data-testid="stSidebarCollapseButton"] button svg,
    [data-testid="stSidebarCollapsedControl"] button svg,
    [data-testid="collapsedControl"] button svg,
    header button[kind="headerNoPadding"] svg {
        fill: #ffffff !important;
        opacity: 1 !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Configuration")

    embedder_name = st.selectbox(
        "Embedder",
        options=list(EMBEDDER_REGISTRY.keys()),
        index=list(EMBEDDER_REGISTRY.keys()).index(DEFAULT_EMBEDDER),
    )

    sensitive = st.toggle(
        "I will use sensitive data",
        value=False,
        help="Hides cloud generators that may use prompts for model training.",
    )

    available_generators = {
        k: v for k, v in GENERATOR_REGISTRY.items()
        if not sensitive or v.data_sharing_ok
    }
    if sensitive and len(available_generators) < len(GENERATOR_REGISTRY):
        st.warning(
            "Free-tier cloud APIs (e.g. Gemini free tier) are hidden because they "
            "may use your prompts for model training. Remaining options are local "
            "or paid APIs that do not train on your data."
        )

    default_gen = DEFAULT_GENERATOR if DEFAULT_GENERATOR in available_generators else list(available_generators)[0]
    generator_name = st.selectbox(
        "Generator",
        options=list(available_generators.keys()),
        index=list(available_generators.keys()).index(default_gen),
    )

    st.divider()
    if st.button("Re-index for selected embedder", use_container_width=True):
        with st.spinner(f"Indexing with {embedder_name}…"):
            try:
                ingest(embedder_name)
                st.success("Indexing complete.")
            except Exception as e:
                st.error(f"Indexing failed: {e}")

    st.divider()
    if st.button("Clear chat history", use_container_width=True):
        st.session_state.history = []
        st.rerun()

    st.markdown(
        "**Defaults:** fully local (bge-m3 + Ollama gemma2), "
        "no API keys required, no data leaves the machine."
    )

# ── Session state ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ── Render chat history ───────────────────────────────────────────────────────
for entry in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(entry["question"])
    with st.chat_message("assistant"):
        if entry.get("low_confidence"):
            st.warning(
                f"⚠️ Low retrieval confidence (top score: {entry['top_score']:.2f}) — "
                "the AI Act may not directly cover this question."
            )
        if entry["answer"]:
            st.markdown(entry["answer"])
        st.caption(
            f"Retrieval: {entry['retrieval_ms']:.0f} ms · "
            f"Generation: {entry['generation_ms']:.0f} ms · "
            f"Embedder: {entry['embedder']} · Generator: {entry['generator']}"
        )
        with st.expander("Sources"):
            if entry.get("structured_display"):
                st.markdown("**Structured classification (lexbeam MCP)**")
                st.markdown(entry["structured_display"])
                st.divider()
            for chunk, score in entry["sources"]:
                label = f"{'Article' if chunk.type == 'article' else 'Annex III, point'} {chunk.number} — {chunk.title}"
                st.markdown(f"**{label}** · score: `{score:.3f}`")
                st.text(chunk.text[:2000] + ("…" if len(chunk.text) > 2000 else ""))
                st.divider()

# ── Chat input ────────────────────────────────────────────────────────────────
question = st.chat_input("Ask about the EU AI Act…")

if question and question.strip():
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        # Load embedder
        cache_key = f"embedder_{embedder_name}"
        if cache_key not in st.session_state:
            with st.spinner("Loading embedder…"):
                try:
                    st.session_state[cache_key] = get_embedder(embedder_name)
                except Exception as e:
                    st.error(f"Failed to load embedder: {e}")
                    st.stop()
        embedder = st.session_state[cache_key]

        # Retrieve
        t0 = time.perf_counter()
        try:
            results = retrieve(question, embedder, top_k=TOP_K)
        except Exception as e:
            st.error(f"Retrieval failed: {e}\n\nHave you run `uv run python -m src.ingest` yet?")
            st.stop()
        retrieval_ms = (time.perf_counter() - t0) * 1000

        if not results:
            st.warning("No chunks returned. Run `uv run python -m src.ingest` first.")
            st.stop()

        top_score = results[0][1]
        chunks = [c for c, _ in results]
        low_confidence = top_score < LOW_CONFIDENCE_THRESHOLD

        if low_confidence:
            st.warning(
                f"⚠️ This question does not appear to be covered by the EU AI Act "
                f"(retrieval score: {top_score:.2f}). Please ask about the AI Act or its "
                "implications for pharmaceutical organisations."
            )
            st.session_state.history.append({
                "question": question, "answer": None,
                "sources": [], "structured_display": "",
                "retrieval_ms": retrieval_ms, "generation_ms": 0,
                "embedder": embedder_name, "generator": generator_name,
                "top_score": top_score, "low_confidence": True,
            })
            st.stop()

        # Load generator
        gen_cache_key = f"generator_{generator_name}"
        if gen_cache_key not in st.session_state:
            with st.spinner("Loading generator…"):
                try:
                    st.session_state[gen_cache_key] = get_generator(generator_name)
                except Exception as e:
                    st.error(f"Failed to load generator: {e}")
                    st.stop()
        generator = st.session_state[gen_cache_key]

        if not low_confidence:
            with st.spinner("Getting structured classification…"):
                structured_display, structured_prompt = get_structured_context(question)
        else:
            structured_display, structured_prompt = "", ""

        user_prompt = build_user_prompt(question, chunks, structured_prompt)

        t1 = time.perf_counter()
        with st.spinner("Generating answer…"):
            try:
                answer = generator.generate(SYSTEM_PROMPT, user_prompt)
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()
        generation_ms = (time.perf_counter() - t1) * 1000

        st.markdown(answer)
        st.caption(
            f"Retrieval: {retrieval_ms:.0f} ms · "
            f"Generation: {generation_ms:.0f} ms · "
            f"Embedder: {embedder_name} · Generator: {generator_name}"
        )
        with st.expander("Sources"):
            if structured_display:
                st.markdown("**Structured classification (lexbeam MCP)**")
                st.markdown(structured_display)
                st.divider()
            for chunk, score in results:
                label = f"{'Article' if chunk.type == 'article' else 'Annex III, point'} {chunk.number} — {chunk.title}"
                st.markdown(f"**{label}** · score: `{score:.3f}`")
                st.text(chunk.text[:2000] + ("…" if len(chunk.text) > 2000 else ""))
                st.divider()

        # Save to history
        st.session_state.history.append({
            "question": question,
            "answer": answer,
            "sources": results,
            "structured_display": structured_display,
            "retrieval_ms": retrieval_ms,
            "generation_ms": generation_ms,
            "embedder": embedder_name,
            "generator": generator_name,
            "top_score": top_score,
            "low_confidence": low_confidence,
        })
