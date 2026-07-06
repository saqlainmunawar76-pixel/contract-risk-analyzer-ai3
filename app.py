"""
app.py
======
AI-Powered Contract & Legal Document Risk Analyzer
TEYZIX CORE Internship Program - Task 3 (AI-3)

Full Streamlit dashboard tying together:
    auth.py, storage.py, document_processor.py, ai_analyzer.py,
    semantic_search.py, report_generator.py, notifier.py

Run locally:
    streamlit run app.py

Deploy on Streamlit Community Cloud:
    Set GEMINI_API_KEY in the app's Secrets. Works fully without it too
    (every AI feature has a rule-based fallback).
"""

import os
import json

import streamlit as st

from src import storage, auth, document_processor as dp, ai_analyzer as ai
from src.semantic_search import SemanticIndex
from src import report_generator as rg
from src import notifier

# --------------------------------------------------------------- config ----
NAVY_BG = "#0a0e17"
PANEL_BG = "#131a2a"
CARD_BG = "#1a2332"
BORDER = "#263349"
BLUE = "#3b82f6"
BLUE_LIGHT = "#60a5fa"
BLUE_DARK = "#2563eb"
TEXT = "#e5e9f0"
TEXT_MUTED = "#94a3b8"
RISK_HIGH = "#f87171"
RISK_MEDIUM = "#fbbf24"
RISK_LOW = "#34d399"

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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        .main .block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1300px; }}

        h1, h2, h3, h4 {{ color: {TEXT}; font-weight: 700; letter-spacing: -0.02em; }}
        p, span, label, li {{ color: {TEXT}; }}

        /* ---- Hero banner ---- */
        .hero-banner {{
            background: linear-gradient(135deg, {PANEL_BG} 0%, #0d1b2e 60%, #0a1420 100%);
            border: 1px solid {BORDER};
            padding: 1.75rem 2.25rem;
            border-radius: 14px;
            margin-bottom: 1.75rem;
            box-shadow: 0 8px 30px rgba(59, 130, 246, 0.08);
            position: relative;
            overflow: hidden;
        }}
        .hero-banner::before {{
            content: "";
            position: absolute; top: -40%; right: -10%;
            width: 300px; height: 300px; border-radius: 50%;
            background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, rgba(59,130,246,0) 70%);
        }}
        .hero-banner h1, .hero-banner h2 {{
            background: linear-gradient(90deg, {TEXT} 20%, {BLUE_LIGHT} 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin: 0; font-size: 1.9rem;
        }}
        .hero-banner p {{ color: {TEXT_MUTED}; margin: 0.35rem 0 0 0; }}
        .hero-badge {{
            display: inline-block; background: rgba(59,130,246,0.12); color: {BLUE_LIGHT};
            border: 1px solid rgba(59,130,246,0.35); padding: 3px 12px; border-radius: 999px;
            font-size: 0.75rem; font-weight: 600; margin-top: 0.6rem;
        }}

        /* ---- Buttons ---- */
        div.stButton > button, div.stDownloadButton > button, .stFormSubmitButton > button {{
            background: linear-gradient(135deg, {BLUE} 0%, {BLUE_DARK} 100%);
            color: white; border: none; border-radius: 8px; font-weight: 600;
            padding: 0.5rem 1.1rem; transition: all 0.15s ease;
            box-shadow: 0 2px 8px rgba(59,130,246,0.25);
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
            background: linear-gradient(135deg, {BLUE_LIGHT} 0%, {BLUE} 100%);
            box-shadow: 0 4px 14px rgba(59,130,246,0.4); transform: translateY(-1px);
        }}

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {{
            background: {PANEL_BG}; border-right: 1px solid {BORDER};
        }}

        /* ---- Metrics ---- */
        [data-testid="stMetric"] {{
            background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 10px;
            padding: 0.9rem 1rem;
        }}
        [data-testid="stMetricValue"] {{ color: {BLUE_LIGHT}; font-weight: 700; }}
        [data-testid="stMetricLabel"] {{ color: {TEXT_MUTED}; }}

        /* ---- Tabs ---- */
        .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {BORDER}; }}
        .stTabs [data-baseweb="tab"] {{
            background: transparent; color: {TEXT_MUTED}; border-radius: 8px 8px 0 0;
            padding: 0.5rem 1rem; font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{
            background: {CARD_BG}; color: {BLUE_LIGHT};
            border-bottom: 2px solid {BLUE};
        }}

        /* ---- Risk badges ---- */
        .risk-badge {{
            display: inline-block; padding: 2px 10px; border-radius: 999px;
            font-size: 0.72rem; font-weight: 700; margin-right: 6px; letter-spacing: 0.02em;
        }}
        .risk-high {{ background: rgba(248,113,113,0.15); color: {RISK_HIGH}; border: 1px solid rgba(248,113,113,0.4); }}
        .risk-medium {{ background: rgba(251,191,36,0.15); color: {RISK_MEDIUM}; border: 1px solid rgba(251,191,36,0.4); }}
        .risk-low {{ background: rgba(52,211,153,0.15); color: {RISK_LOW}; border: 1px solid rgba(52,211,153,0.4); }}
        .category-badge {{
            display: inline-block; padding: 1px 8px; border-radius: 6px; font-size: 0.68rem;
            background: rgba(148,163,184,0.12); color: {TEXT_MUTED}; border: 1px solid {BORDER};
            margin-left: 4px;
        }}

        /* ---- Cards / containers ---- */
        .info-card {{
            background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 10px;
            padding: 1rem 1.2rem; margin-bottom: 0.6rem;
        }}
        .source-tag {{
            display: inline-block; font-size: 0.75rem; color: {TEXT_MUTED};
            background: {CARD_BG}; border: 1px solid {BORDER}; padding: 2px 10px; border-radius: 999px;
        }}

        /* misc */
        hr {{ border-color: {BORDER}; }}
        [data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 8px; }}
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
    st.markdown("""
    <div class="hero-banner">
        <h1>⚖️ AI-Powered Contract & Legal Document Risk Analyzer</h1>
        <p>TEYZIX CORE Internship Program — Task 3 (AI-3) — Advanced AI Application</p>
        <span class="hero-badge">Ref: TC-INT-18991230-763</span>
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
        st.caption(f"Role: {user['role'].title()}  ·  {user['email']}")
        st.divider()

        api_key = get_api_key()
        if api_key:
            st.success("✅ Gemini AI: Connected")
        else:
            st.warning("⚠️ Gemini AI: Not configured\n\nUsing rule-based fallback mode.")

        if notifier.is_configured(_get_secrets()):
            st.success("✅ Email delivery: Configured")
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


def _get_secrets():
    try:
        return st.secrets
    except Exception:
        return None


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
    st.markdown(f"<span class='source-tag'>{source_tag}</span>", unsafe_allow_html=True)
    st.write("")

    col1, col2, col3 = st.columns(3)
    col1.metric("Compliance Score", f"{compliance.get('score', 'N/A')}/100", compliance.get("grade", ""))
    col2.metric("Overall Risk", risks.get("overall_risk_level", "N/A").upper())
    col3.metric("Missing Clauses", len(risks.get("missing_clauses", [])))

    st.subheader("📋 Contract Information")
    st.json(info, expanded=False)

    st.subheader("⚠️ Risk Analysis")
    category_labels = {
        "high_risk_clause": "High-Risk Clause", "missing_clause": "Missing Clause",
        "ambiguous_statement": "Ambiguous Statement", "unusual_payment_term": "Unusual Payment Term",
    }
    for risk in risks.get("risks", []):
        level = risk.get("risk_level", "low")
        category = category_labels.get(risk.get("risk_category", ""), "")
        cat_html = f"<span class='category-badge'>{category}</span>" if category else ""
        st.markdown(
            f"<div class='info-card'><span class='risk-badge risk-{level}'>{level.upper()}</span>"
            f"{cat_html} <b>{risk.get('clause','')}</b><br>"
            f"<span style='color:{TEXT_MUTED};font-size:0.9rem;'>{risk.get('explanation','')} "
            f"(confidence: {risk.get('confidence', 0):.0%})</span></div>",
            unsafe_allow_html=True,
        )

    if risks.get("missing_clauses"):
        st.warning("Missing standard clauses: " + ", ".join(risks["missing_clauses"]))

    st.subheader("📝 Executive Summary")
    st.write(summary.get("executive_summary", ""))
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Key Obligations**")
        for o in summary.get("key_obligations", []):
            st.markdown(f"- {o}")
        st.markdown("**Important Dates**")
        for d in summary.get("important_dates", []):
            st.markdown(f"- {d}")
    with colB:
        st.markdown("**Important Clauses**")
        for c in summary.get("important_clauses", []):
            st.markdown(f"- {c}")
        st.markdown("**Recommended Actions**")
        for a in summary.get("recommended_actions", []):
            st.markdown(f"- {a}")

    st.divider()
    st.subheader("📥 Export Report")
    pdf_bytes = rg.generate_pdf_report(st.session_state.current_document_name, info, risks, summary, compliance)
    docx_bytes = rg.generate_docx_report(st.session_state.current_document_name, info, risks, summary, compliance)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📄 Download PDF Report", data=pdf_bytes,
                            file_name=f"analysis_{st.session_state.current_document_name}.pdf",
                            mime="application/pdf", width='stretch')
    with col2:
        st.download_button("📝 Download DOCX Report", data=docx_bytes,
                            file_name=f"analysis_{st.session_state.current_document_name}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            width='stretch')

    secrets = _get_secrets()
    with st.expander("📧 Email this report (bonus feature)"):
        if not notifier.is_configured(secrets):
            st.caption("Email delivery isn't configured on this server. Use the download buttons above instead.")
        else:
            recipient = st.text_input("Recipient email", value=st.session_state.user["email"], key="email_recipient")
            fmt = st.radio("Format", ["PDF", "DOCX"], horizontal=True, key="email_format")
            if st.button("Send Report via Email"):
                attachment = pdf_bytes if fmt == "PDF" else docx_bytes
                ext = "pdf" if fmt == "PDF" else "docx"
                result = notifier.send_report_email(
                    recipient, f"Contract Analysis Report — {st.session_state.current_document_name}",
                    "Please find your AI-generated contract risk analysis report attached.\n\n"
                    "This report is AI-assisted and does not constitute legal advice.",
                    attachment, f"analysis_{st.session_state.current_document_name}.{ext}", secrets=secrets,
                )
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])


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
    query = st.text_input("Search within this document (natural language)",
                           placeholder='e.g. "Show payment terms" or "Find confidentiality clauses"')
    if query:
        results = st.session_state.semantic_index.search(query, top_k=5)
        if not results:
            st.warning("No relevant matches found.")
        for r in results:
            st.markdown(f"**Relevance: {r.score:.2f}**")
            st.markdown(f"<div class='info-card'>{r.chunk}</div>", unsafe_allow_html=True)

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
    st.caption("Compare two contract versions clause-by-clause (also doubles as Version Comparison).")

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

        source_tag = "🤖 AI-generated" if comparison.get("source") == "ai" else "📐 Rule-based fallback (similarity scores only)"
        st.markdown(f"<span class='source-tag'>{source_tag}</span>", unsafe_allow_html=True)
        st.write("")
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


# ------------------------------------------------------------ history tab --
def render_history_tab():
    st.subheader("📁 Document History")
    user = st.session_state.user
    docs = storage.list_documents_for_user(user["id"])

    if not docs:
        st.caption("No documents uploaded yet. Head to the Upload tab to get started.")
        return

    for d in docs:
        with st.expander(f"📄 {d['filename']}  ·  {d['file_type'].upper()}  ·  uploaded {d['uploaded_at'][:19]}"):
            analyses = storage.list_analyses_for_document(d["id"])
            if not analyses:
                st.caption("Not analyzed yet. Load this document and run analysis from the Analysis tab.")
                continue

            by_type = {}
            for a in analyses:
                by_type.setdefault(a["analysis_type"], a)  # first (most recent) wins, already ordered DESC

            if "compliance" in by_type:
                comp = json.loads(by_type["compliance"]["result_json"])
                st.metric("Compliance Score", f"{comp.get('score','N/A')}/100", comp.get("grade", ""))
            if "risks" in by_type:
                risks = json.loads(by_type["risks"]["result_json"])
                st.write(f"**Overall risk:** {risks.get('overall_risk_level','N/A').upper()}  ·  "
                         f"**Issues found:** {len(risks.get('risks', []))}")
            if "summary" in by_type:
                summ = json.loads(by_type["summary"]["result_json"])
                st.write(f"**Summary:** {summ.get('executive_summary', '')}")

            st.caption(f"Last processed: {by_type[list(by_type.keys())[0]]['created_at'][:19]}")

            if st.button("Load this document", key=f"hist_load_{d['id']}"):
                load_document(d["id"])
                st.rerun()


# ------------------------------------------------------------ insights tab -
def render_insights_tab():
    st.subheader("📊 AI Insights Dashboard")
    user = st.session_state.user
    stats = storage.get_dashboard_stats()
    insights = storage.get_user_risk_insights(user["id"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Documents", stats["total_documents"])
    avg_score = insights["average_compliance_score"]
    col2.metric("Avg. Risk/Compliance Score", f"{avg_score}/100" if avg_score is not None else "N/A")
    col3.metric("High-Risk Documents", insights["high_risk_document_count"])
    col4.metric("Documents Analyzed", insights["total_documents_analyzed"])

    if stats["documents_by_type"]:
        st.markdown("**Documents by File Type**")
        st.bar_chart(stats["documents_by_type"])

    if insights["frequently_detected_risks"]:
        st.markdown("**Frequently Detected Risks (your documents)**")
        chart_data = {r["clause"]: r["count"] for r in insights["frequently_detected_risks"]}
        st.bar_chart(chart_data)

    if insights["processing_history"]:
        st.markdown("**Processing History**")
        st.dataframe(insights["processing_history"], width='stretch')

    if st.session_state.current_document_text:
        st.divider()
        st.subheader("🌐 Language Detection")
        api_key = get_api_key()
        client = get_gemini_client(api_key)
        lang = ai.detect_language(st.session_state.current_document_text, client=client)
        st.write(f"Detected language: **{lang['language']}** (confidence: {lang['confidence']:.0%})")


# ------------------------------------------------------------ profile tab --
def render_profile_tab():
    st.subheader("👤 Profile & Account Settings")
    user = storage.get_user_by_id(st.session_state.user["id"])

    col1, col2 = st.columns(2)
    col1.metric("Username", user["username"])
    col2.metric("Role", user["role"].title())
    st.caption(f"Member since {user['created_at'][:19]}  ·  Last login: {(user['last_login'] or 'N/A')[:19]}")

    st.divider()
    st.markdown("### ✉️ Update Email")
    with st.form("update_email_form"):
        new_email = st.text_input("Email address", value=user["email"])
        submitted = st.form_submit_button("Update Email")
        if submitted:
            try:
                auth.update_email(user["id"], new_email)
                st.session_state.user["email"] = new_email
                st.success("Email updated successfully.")
            except auth.AuthError as e:
                st.error(str(e))

    st.markdown("### 🔒 Change Password")
    with st.form("change_password_form"):
        current_pw = st.text_input("Current password", type="password")
        new_pw = st.text_input("New password", type="password")
        confirm_pw = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Change Password")
        if submitted:
            try:
                auth.change_password(user["id"], current_pw, new_pw, confirm_pw)
                st.success("Password changed successfully.")
            except auth.AuthError as e:
                st.error(str(e))


# --------------------------------------------------------------- admin tab -
def render_admin_tab():
    st.subheader("🛠️ Admin Panel")

    usage = storage.get_ai_usage_stats()
    dash_stats = storage.get_dashboard_stats()

    st.markdown("### 📈 Processing Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Users", dash_stats["total_users"])
    col2.metric("Total Documents", dash_stats["total_documents"])
    col3.metric("Total Analyses Run", usage["total_analyses"])
    col4.metric("AI Usage Rate", f"{usage['ai_usage_percent']}%")

    st.markdown("### 🤖 AI Usage Monitoring")
    col1, col2 = st.columns(2)
    col1.metric("Gemini AI-Powered Analyses", usage["ai_powered_count"])
    col2.metric("Rule-Based Fallback Analyses", usage["fallback_count"])
    if usage["by_analysis_type"]:
        st.caption("Breakdown by analysis type:")
        st.dataframe(
            [{"analysis_type": k, **v} for k, v in usage["by_analysis_type"].items()],
            width='stretch',
        )

    st.divider()
    users = storage.list_all_users()
    st.markdown("### 👥 Manage Users")
    st.dataframe(users, width='stretch')

    with st.expander("Change a user's role"):
        options = {f"{u['username']} ({u['role']})": u["id"] for u in users}
        selected = st.selectbox("Select user", list(options.keys()))
        new_role = st.selectbox("New role", ["user", "admin"])
        if st.button("Update role"):
            storage.set_user_role(options[selected], new_role)
            st.success("Role updated.")
            st.rerun()

    st.markdown("### 📁 Manage Uploaded Documents")
    all_docs = storage.list_all_documents()
    st.dataframe(all_docs, width='stretch')

    st.markdown("### 🧾 System Logs (Audit Log)")
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
        <h2>⚖️ Contract & Legal Document Risk Analyzer</h2>
        <p>Document: {st.session_state.current_document_name or 'None loaded'}</p>
    </div>
    """, unsafe_allow_html=True)

    tabs = ["📤 Upload", "🔍 Analysis", "💬 Search & Chat", "🔀 Compare", "📁 History", "📊 Insights", "👤 Profile"]
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
        render_history_tab()
    with tab_objs[5]:
        render_insights_tab()
    with tab_objs[6]:
        render_profile_tab()
    if is_admin:
        with tab_objs[7]:
            render_admin_tab()


if __name__ == "__main__":
    main()
