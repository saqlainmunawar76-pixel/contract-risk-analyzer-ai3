"""
app.py
======
AI-Powered Contract & Legal Document Risk Analyzer
TEYZIX CORE Internship Program - Task 3 (AI-3)

Full Streamlit dashboard tying together:
    auth.py, storage.py, document_processor.py, ai_analyzer.py,
    semantic_search.py, report_generator.py

Run locally:
    streamlit run app.py

Deploy on Streamlit Community Cloud:
    Set GEMINI_API_KEY in the app's Secrets. Works fully without it too
    (every AI feature has a rule-based fallback).
"""

import os
import json
from datetime import datetime

import streamlit as st

from src import storage, auth, document_processor as dp, ai_analyzer as ai
from src.semantic_search import SemanticIndex
from src import report_generator as rg

# --------------------------------------------------------------- config ----
TEYZIX_GREEN = "#1a5d3a"
TEYZIX_GREEN_LIGHT = "#2e8b57"

st.set_page_config(
    page_title="Contract Risk Analyzer | TEYZIX Task 3",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_api_key() -> str:
    """Look for the Gemini key in Streamlit secrets first, then env var."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


@st.cache_resource
def get_gemini_client(api_key: str):
    return ai.get_client(api_key)


def inject_css():
    st.markdown(f"""
    <style>
        .main .block-container {{ padding-top: 2rem; }}
        h1, h2, h3 {{ color: {TEYZIX_GREEN}; }}
        div.stButton > button:first-child {{
            background-color: {TEYZIX_GREEN}; color: white; border: none; border-radius: 6px;
        }}
        div.stButton > button:first-child:hover {{ background-color: {TEYZIX_GREEN_LIGHT}; }}
        .hero-banner {{
            background: linear-gradient(90deg, {TEYZIX_GREEN} 0%, {TEYZIX_GREEN_LIGHT} 100%);
            padding: 1.5rem 2rem; border-radius: 10px; color: white; margin-bottom: 1.5rem;
        }}
        .risk-high {{ color: #c0392b; font-weight: 600; }}
        .risk-medium {{ color: #d68910; font-weight: 600; }}
        .risk-low {{ color: #1e8449; font-weight: 600; }}
        [data-testid="stMetricValue"] {{ color: {TEYZIX_GREEN}; }}
    </style>
    """, unsafe_allow_html=True)


def init_session_state():
    defaults = {
        "user": None, "current_document_id": None, "current_document_text": None,
        "current_document_name": None, "semantic_index": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ------------------------------------------------------------ auth pages ---
def render_login_register():
    st.markdown(f"""
    <div class="hero-banner">
        <h1 style="color:white; margin:0;">⚖️ AI-Powered Contract & Legal Document Risk Analyzer</h1>
        <p style="margin:0;">TEYZIX CORE Internship Program \u2014 Task 3 (AI-3) \u2014 Advanced AI Application</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔐 Login", "📝 Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", width='stretch')
            if submitted:
                try:
                    user = auth.login_user(username, password)
                    st.session_state.user = user
                    st.success(f"Welcome back, {user['username']}!")
                    st.rerun()
                except auth.AuthError as e:
                    st.error(str(e))

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", width='stretch')
            if submitted:
                try:
                    user = auth.register_user(new_username, new_email, new_password, confirm_password)
                    st.success(f"Account created! Role: {user['role']}. Please log in.")
                except auth.AuthError as e:
                    st.error(str(e))


# --------------------------------------------------------------- sidebar ---
def render_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"### 👤 {user['username']}")
        st.caption(f"Role: {user['role'].title()}")
        st.divider()

        api_key = get_api_key()
        if api_key:
            st.success("✅ Gemini AI: Connected")
        else:
            st.warning("⚠️ Gemini AI: Not configured\n\nUsing rule-based fallback mode.")
        st.divider()

        docs = storage.list_documents_for_user(user["id"])
        st.markdown("### 📄 Your Documents")
        if docs:
            for d in docs:
                label = f"{d['filename']}"
                if st.button(label, key=f"doc_{d['id']}", width='stretch'):
                    load_document(d["id"])
        else:
            st.caption("No documents uploaded yet.")

        st.divider()
        if st.button("🚪 Logout", width='stretch'):
            auth.logout_user(user["id"], user["username"])
            st.session_state.user = None
            st.session_state.current_document_id = None
            st.rerun()


def load_document(document_id: int):
    doc = storage.get_document(document_id)
    if doc:
        st.session_state.current_document_id = doc["id"]
        st.session_state.current_document_text = doc["raw_text"]
        st.session_state.current_document_name = doc["filename"]
        st.session_state.semantic_index = SemanticIndex(doc["raw_text"])


# ------------------------------------------------------------ upload tab ---
def render_upload_tab():
    st.subheader("📤 Upload a Contract or Legal Document")
    uploaded_file = st.file_uploader("Choose a PDF, DOCX, or TXT file", type=["pdf", "docx", "txt"])

    if uploaded_file is not None:
        if st.button("Process Document", type="primary"):
            with st.spinner("Extracting text (OCR fallback if needed)..."):
                result = dp.process_document(uploaded_file.name, uploaded_file.getvalue())

            if not result.success:
                st.error(f"❌ {result.error}")
                return

            for w in result.warnings:
                st.warning(w)
            if result.ocr_pages_used:
                st.info(f"ℹ️ OCR was used on {result.ocr_pages_used} scanned page(s).")

            user = st.session_state.user
            doc_id = storage.save_document(user["id"], uploaded_file.name, result.file_type, result.text)
            storage.log_action(user["id"], user["username"], "upload_document", uploaded_file.name)
            st.success(f"✅ Document processed and saved ({result.pages_processed} page(s), {len(result.text)} characters).")
            load_document(doc_id)
            st.rerun()

    if st.session_state.current_document_text:
        st.divider()
        st.markdown(f"**Currently loaded:** {st.session_state.current_document_name}")
        with st.expander("Preview extracted text"):
            st.text(st.session_state.current_document_text[:3000])


# --------------------------------------------------------- analysis tab ----
def render_analysis_tab(client):
    if not st.session_state.current_document_text:
        st.info("👈 Upload or select a document first.")
        return

    text = st.session_state.current_document_text
    doc_id = st.session_state.current_document_id

    if st.button("🔍 Run Full Analysis", type="primary"):
        with st.spinner("Analyzing document..."):
            info = ai.extract_contract_info(text, client=client)
            risks = ai.detect_risks(text, client=client)
            summary = ai.generate_summary(text, client=client)
            compliance = ai.compliance_score(text, risk_result=risks, client=client)

        storage.save_analysis(doc_id, "info", json.dumps(info))
        storage.save_analysis(doc_id, "risks", json.dumps(risks))
        storage.save_analysis(doc_id, "summary", json.dumps(summary))
        storage.save_analysis(doc_id, "compliance", json.dumps(compliance))
        storage.log_action(st.session_state.user["id"], st.session_state.user["username"], "run_analysis",
                            st.session_state.current_document_name)
        st.session_state["_last_info"] = info
        st.session_state["_last_risks"] = risks
        st.session_state["_last_summary"] = summary
        st.session_state["_last_compliance"] = compliance

    info = st.session_state.get("_last_info") or _load_cached(doc_id, "info")
    risks = st.session_state.get("_last_risks") or _load_cached(doc_id, "risks")
    summary = st.session_state.get("_last_summary") or _load_cached(doc_id, "summary")
    compliance = st.session_state.get("_last_compliance") or _load_cached(doc_id, "compliance")

    if not info:
        return

    source_tag = "🤖 AI-generated" if info.get("source") == "ai" else "📐 Rule-based fallback"
    st.caption(source_tag)

    col1, col2, col3 = st.columns(3)
    col1.metric("Compliance Score", f"{compliance.get('score', 'N/A')}/100", compliance.get("grade", ""))
    col2.metric("Overall Risk", risks.get("overall_risk_level", "N/A").upper())
    col3.metric("Missing Clauses", len(risks.get("missing_clauses", [])))

    st.subheader("📋 Contract Information")
    st.json(info, expanded=False)

    st.subheader("⚠️ Risk Analysis")
    for risk in risks.get("risks", []):
        level = risk.get("risk_level", "low")
        css_class = f"risk-{level}"
        st.markdown(f"<span class='{css_class}'>[{level.upper()}]</span> **{risk.get('clause','')}** \u2014 {risk.get('explanation','')}",
                    unsafe_allow_html=True)

    if risks.get("missing_clauses"):
        st.warning("Missing standard clauses: " + ", ".join(risks["missing_clauses"]))

    st.subheader("📝 Executive Summary")
    st.write(summary.get("executive_summary", ""))
    colA, colB, colC = st.columns(3)
    with colA:
        st.markdown("**Key Obligations**")
        for o in summary.get("key_obligations", []):
            st.markdown(f"- {o}")
    with colB:
        st.markdown("**Important Dates**")
        for d in summary.get("important_dates", []):
            st.markdown(f"- {d}")
    with colC:
        st.markdown("**Recommended Actions**")
        for a in summary.get("recommended_actions", []):
            st.markdown(f"- {a}")

    st.divider()
    st.subheader("📥 Export Report")
    col1, col2 = st.columns(2)
    with col1:
        pdf_bytes = rg.generate_pdf_report(st.session_state.current_document_name, info, risks, summary, compliance)
        st.download_button("Download PDF Report", data=pdf_bytes,
                            file_name=f"analysis_{st.session_state.current_document_name}.pdf",
                            mime="application/pdf", width='stretch')
    with col2:
        docx_bytes = rg.generate_docx_report(st.session_state.current_document_name, info, risks, summary, compliance)
        st.download_button("Download DOCX Report", data=docx_bytes,
                            file_name=f"analysis_{st.session_state.current_document_name}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            width='stretch')


def _load_cached(doc_id, analysis_type):
    if not doc_id:
        return None
    row = storage.get_latest_analysis(doc_id, analysis_type)
    return json.loads(row["result_json"]) if row else None


# --------------------------------------------------------- search/RAG tab --
def render_search_tab(client):
    if not st.session_state.current_document_text:
        st.info("👈 Upload or select a document first.")
        return

    st.subheader("🔎 Semantic Search")
    query = st.text_input("Search within this document (natural language)")
    if query:
        results = st.session_state.semantic_index.search(query, top_k=5)
        if not results:
            st.warning("No relevant matches found.")
        for r in results:
            st.markdown(f"**Relevance: {r.score:.2f}**")
            st.write(r.chunk)
            st.divider()

    st.subheader("💬 AI Chat Assistant (RAG Q&A)")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            st.write(msg)

    question = st.chat_input("Ask a question about this document...")
    if question:
        st.session_state.chat_history.append(("user", question))
        with st.spinner("Thinking..."):
            result = ai.answer_question(
                st.session_state.current_document_text, question,
                client=client, semantic_index=st.session_state.semantic_index,
            )
        st.session_state.chat_history.append(("assistant", result["answer"]))
        st.rerun()


# ------------------------------------------------------- comparison tab ----
def render_comparison_tab(client):
    st.subheader("🔀 AI Clause Comparison")
    st.caption("Compare two contract versions clause-by-clause.")

    col1, col2 = st.columns(2)
    with col1:
        file_a = st.file_uploader("Contract Version A", type=["pdf", "docx", "txt"], key="cmp_a")
    with col2:
        file_b = st.file_uploader("Contract Version B", type=["pdf", "docx", "txt"], key="cmp_b")

    if file_a and file_b and st.button("Compare Contracts", type="primary"):
        result_a = dp.process_document(file_a.name, file_a.getvalue())
        result_b = dp.process_document(file_b.name, file_b.getvalue())

        if not result_a.success:
            st.error(f"Version A: {result_a.error}")
            return
        if not result_b.success:
            st.error(f"Version B: {result_b.error}")
            return

        with st.spinner("Comparing clauses..."):
            comparison = ai.compare_contracts(result_a.text, result_b.text, client=client)

        st.caption("🤖 AI-generated" if comparison.get("source") == "ai" else "📐 Rule-based fallback (similarity scores only)")
        for c in comparison.get("comparisons", []):
            colA, colB = st.columns(2)
            with colA:
                st.markdown("**Version A**")
                st.info(c.get("clause_a", ""))
            with colB:
                st.markdown("**Version B**")
                st.info(c.get("clause_b", ""))
            st.markdown(f"*Difference:* {c.get('difference', '')}")
            st.divider()


# ------------------------------------------------------------ insights tab -
def render_insights_tab():
    st.subheader("📊 AI Insights Dashboard")
    stats = storage.get_dashboard_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users", stats["total_users"])
    col2.metric("Total Documents", stats["total_documents"])
    col3.metric("Total Analyses", stats["total_analyses"])

    if stats["documents_by_type"]:
        st.bar_chart(stats["documents_by_type"])

    st.subheader("📁 Document History")
    docs = storage.list_documents_for_user(st.session_state.user["id"])
    if docs:
        st.dataframe(docs, width='stretch')
    else:
        st.caption("No documents yet.")

    if st.session_state.current_document_text:
        st.divider()
        st.subheader("🌐 Language Detection")
        api_key = get_api_key()
        client = get_gemini_client(api_key)
        lang = ai.detect_language(st.session_state.current_document_text, client=client)
        st.write(f"Detected language: **{lang['language']}** (confidence: {lang['confidence']:.0%})")


# --------------------------------------------------------------- admin tab -
def render_admin_tab():
    st.subheader("🛠️ Admin Panel")
    users = storage.list_all_users()
    st.markdown("### All Users")
    st.dataframe(users, width='stretch')

    with st.expander("Change a user's role"):
        options = {f"{u['username']} ({u['role']})": u["id"] for u in users}
        selected = st.selectbox("Select user", list(options.keys()))
        new_role = st.selectbox("New role", ["user", "admin"])
        if st.button("Update role"):
            storage.set_user_role(options[selected], new_role)
            st.success("Role updated.")
            st.rerun()

    st.markdown("### All Documents")
    all_docs = storage.list_all_documents()
    st.dataframe(all_docs, width='stretch')

    st.markdown("### Audit Log")
    log = storage.get_audit_log(limit=100)
    st.dataframe(log, width='stretch')


# ---------------------------------------------------------------- main -----
def main():
    storage.init_db()
    init_session_state()
    inject_css()

    if st.session_state.user is None:
        render_login_register()
        return

    render_sidebar()

    api_key = get_api_key()
    client = get_gemini_client(api_key)

    st.markdown(f"""
    <div class="hero-banner">
        <h2 style="color:white; margin:0;">⚖️ Contract & Legal Document Risk Analyzer</h2>
        <p style="margin:0;">Document: {st.session_state.current_document_name or 'None loaded'}</p>
    </div>
    """, unsafe_allow_html=True)

    tabs = ["📤 Upload", "🔍 Analysis", "💬 Search & Chat", "🔀 Compare", "📊 Insights"]
    is_admin = auth.is_admin(st.session_state.user)
    if is_admin:
        tabs.append("🛠️ Admin")

    tab_objs = st.tabs(tabs)
    with tab_objs[0]:
        render_upload_tab()
    with tab_objs[1]:
        render_analysis_tab(client)
    with tab_objs[2]:
        render_search_tab(client)
    with tab_objs[3]:
        render_comparison_tab(client)
    with tab_objs[4]:
        render_insights_tab()
    if is_admin:
        with tab_objs[5]:
            render_admin_tab()


if __name__ == "__main__":
    main()
