"""TrustGuard AI 4.1: document-grounded Q&A with security monitoring (Streamlit entry point).

Run with:  python -m streamlit run app.py
Core logic lives in trustguard/ (no Streamlit imports); one module per page lives in views/.
"""
import streamlit as st

st.set_page_config(page_title="TrustGuard AI", page_icon="🛡️", layout="wide")

from trustguard import __version__, config, db, state          # noqa: E402  (after set_page_config)
from trustguard.llm import ollama_status                       # noqa: E402
from trustguard.ui import inject_css, stretch                  # noqa: E402
from views import about, dashboard, eval_lab, qa, security_lab, security_monitor   # noqa: E402

# Section names are unchanged from Phase 4 ("Evaluation Dashboard" is now the Dashboard overview).
NAV = [
    ("WORKSPACE", [("Dashboard", "📊", dashboard), ("Document Q&A", "📄", qa)]),
    ("SECURITY", [("Security Monitor", "🛡️", security_monitor), ("Phase 4 Security Lab", "🧪", security_lab)]),
    ("EVALUATION", [("Phase 3 Evaluation Lab", "📈", eval_lab)]),
    ("INFO", [("About & Limitations", "ℹ️", about)]),
]
PAGES = {name: module for _, items in NAV for name, _, module in items}


@st.cache_data(ttl=10, show_spinner=False)
def _cached_ollama_status() -> dict:
    return ollama_status()


def _sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="tg-brand"><div class="tg-logo">🛡️</div><div><div class="tg-brand-name">TrustGuard AI</div>'
                    '<div class="tg-brand-sub">SECURE DOCUMENT INTELLIGENCE</div></div></div>', unsafe_allow_html=True)
        current = st.session_state["nav_page"]
        for group, items in NAV:
            st.markdown(f'<div class="tg-nav-label">{group}</div>', unsafe_allow_html=True)
            for name, icon, _ in items:
                st.button(f"{icon}  {name}", key=f"nav_{name}", type="primary" if name == current else "secondary",
                          on_click=state.go_to, args=(name,), **stretch())
        st.markdown('<div class="tg-nav-label">MODEL</div>', unsafe_allow_html=True)
        status = _cached_ollama_status()
        if status["model_ready"]:
            dot, text = "🟢", f"Ollama ready · {config.OLLAMA_MODEL}"
        elif status["available"]:
            dot, text = "🟠", f"Model '{config.OLLAMA_MODEL}' not installed"
        else:
            dot, text = "🔴", "Ollama not reachable"
        st.markdown(f'<div class="tg-side-status">{dot} {text}</div>', unsafe_allow_html=True)
        st.toggle("Use local Ollama generation", key="use_llm",
                  help="When off (or when Ollama is unavailable) answers fall back to evidence-only mode.")
        if st.session_state["use_llm"] and not status["model_ready"]:
            st.caption(status["message"])
        with st.expander("Configuration"):
            st.caption(f"Answer model: {config.OLLAMA_MODEL}")
            st.caption(f"Embedding model: {config.EMBEDDING_MODEL_NAME}")
            st.caption(f"Ollama URL: {config.OLLAMA_URL}")
            if st.button("Refresh status", key="refresh_ollama"):
                _cached_ollama_status.clear()
                st.rerun()
        st.divider()
        st.markdown(f'<div class="tg-footer">TrustGuard AI {__version__} · local academic prototype<br>Not a production security boundary.</div>',
                    unsafe_allow_html=True)


db.init_db()
state.init_state()
inject_css()
_sidebar()
PAGES.get(st.session_state["nav_page"], dashboard).render()
