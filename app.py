import os
import uuid
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from auth.auth_manager import ensure_default_admin, list_users, register_user, verify_login
from backend.gemini_helper import (
    explain_contract,
    get_active_model,
    get_active_provider,
    get_available_models,
    get_available_providers,
    set_active_model,
)
from comparison.contract_compare import compare_contracts
from document_processing.file_extractor import SUPPORTED_EXTENSIONS, extract_structured
from rag.chunker import chunk_structured_document
from rag.qa_chain import answer_question
from reports.pdf_generator import generate_pdf
from risk_analysis.clause_highlighter import build_checklist, highlight_clauses_in_text
from risk_analysis.missing_clause_detector import detect_missing_clauses
from risk_analysis.risk_analyzer import analyze_risk
from storage.history import (
    get_admin_stats,
    get_all_documents,
    get_all_reports,
    get_risk_history,
    get_user_documents,
    get_user_reports,
    save_document,
    save_report,
    save_risk_analysis,
)
from vector_store.chroma_store import add_documents, delete_document

# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="JurisAI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------- LOAD CSS ----------------

def load_css():

    with open(
        "styles/style.css"
    ) as f:

        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )


load_css()

ensure_default_admin()


# ---------------- SESSION STATE ----------------

_defaults = {
    "authenticated": False,
    "user": None,
    "explanation": "",
    "risk_data": None,
    "clause_data": None,
    "qa_history": [],
    "comparison_report": "",
    "documents_added": False,
    "structured_doc": None,
    "uploaded_filename": "",
    "current_doc_id": "",
    "comparison_text1": "",
    "comparison_text2": "",
    "comparison_filename1": "",
    "comparison_filename2": "",
    "selected_model": get_active_model(),
    "selected_provider": get_active_provider(),
}

for key, value in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------- LOGIN / REGISTER ----------------

if not st.session_state.authenticated:

    st.title("JurisAI")
    st.caption("Contract intelligence for legal professionals and enterprises.")
    st.divider()

    login_tab, register_tab = st.tabs(["Log In", "Create Account"])

    with login_tab:

        with st.form("login_form"):

            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In")

            if submitted:
                user = verify_login(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        st.caption("First time here? Default admin login: **admin / admin123**")

    with register_tab:

        with st.form("register_form"):

            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Choose a password", type="password")
            register_submitted = st.form_submit_button("Create Account")

            if register_submitted:
                success, message = register_user(new_username, new_password)
                if success:
                    st.success(message + " You can now log in.")
                else:
                    st.error(message)

    st.stop()


user = st.session_state.user


# ---------------- SIDEBAR ----------------

st.sidebar.title("JurisAI")
st.sidebar.caption("Contract Intelligence")
st.sidebar.divider()

st.sidebar.markdown(f"**{user['username']}**  \n`{user['role']}`")

if st.sidebar.button("Log Out"):
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

st.sidebar.divider()

nav_options = [
    "Home",
    "Document Analysis",
    "Multi-Document Search",
    "Contract Comparison",
    "Analytics",
    "Reports",
    "History",
]

if user["role"] == "admin":
    nav_options.append("Admin")

page = st.sidebar.radio(
    "Workspace",
    nav_options
)

st.sidebar.divider()
st.sidebar.markdown("### 🤖 Free AI Engine")
providers = get_available_providers()
provider_keys = list(providers.keys())

active_p = st.session_state.get("selected_provider", get_active_provider())
p_idx = provider_keys.index(active_p) if active_p in provider_keys else 0

selected_provider = st.sidebar.selectbox(
    "Provider",
    options=provider_keys,
    format_func=lambda k: providers[k]["name"],
    index=p_idx,
    help="Select the AI provider. All options support 100% free tiers for students!"
)

provider_meta = providers[selected_provider]

custom_key = None
if provider_meta.get("key_env"):
    env_key = os.getenv(provider_meta["key_env"])
    if not env_key:
        st.sidebar.warning(f"Key needed: {provider_meta['key_env']}")
        st.sidebar.caption(provider_meta["key_hint"])
        custom_key = st.sidebar.text_input(
            f"Enter {selected_provider.upper()} Key",
            type="password",
            key=f"api_key_input_{selected_provider}"
        )
    else:
        st.sidebar.caption(f"✓ {provider_meta['key_env']} active from .env")
        custom_key = env_key

available_models = get_available_models(selected_provider, api_key=custom_key)
model_keys = list(available_models.keys())

# Default to the first priority model if current model is not for this provider
active_m = st.session_state.get(f"model_choice_{selected_provider}", model_keys[0] if model_keys else "")
if active_m not in model_keys:
    active_m = model_keys[0] if model_keys else ""
m_idx = model_keys.index(active_m) if active_m in model_keys else 0

selected_model = st.sidebar.selectbox(
    "Model",
    options=model_keys,
    format_func=lambda k: available_models.get(k, k),
    index=m_idx,
    key=f"sb_model_{selected_provider}",
    help="Select the free model for contract review, risk analysis, and Q&A."
)

st.session_state[f"model_choice_{selected_provider}"] = selected_model
st.session_state.selected_model = selected_model

if (selected_provider != get_active_provider() or selected_model != get_active_model()) or custom_key:
    try:
        ok, msg = set_active_model(selected_model, provider=selected_provider, custom_key=custom_key)
        if ok:
            st.session_state.selected_provider = selected_provider
            st.session_state.selected_model = selected_model
            st.sidebar.caption(f"✓ Active: {selected_model}")
        else:
            st.sidebar.error(msg)
    except Exception as e:
        st.sidebar.error(f"Setup error: {e}")


# ---------------- HOME PAGE ----------------

if page == "Home":

    st.title("JurisAI")

    st.caption(
        "Contract intelligence for legal professionals and enterprises."
    )

    st.divider()

    st.subheader("AI-Powered Contract Analysis")

    st.info(
        """
JurisAI helps organizations simplify contract review and analysis.

• Contract Understanding with Source-Cited Answers

• Structured, Multi-Factor Risk Assessment with Confidence Scoring

• Missing Clause Detection with In-Text Highlighting

• Multi-Format Support (PDF, DOCX, TXT, Scanned Images via OCR)

• Multi-Document Search Across Your Entire Workspace

• Contract Comparison

• Professional Report Generation

• Login, History, and Saved Reports
"""
    )

# ---------------- DOCUMENT ANALYSIS ----------------

elif page == "Document Analysis":

    st.title("Document Analysis")

    st.caption(
        "Upload a contract to begin analysis. Supported formats: "
        + ", ".join(f".{ext}" for ext in SUPPORTED_EXTENSIONS)
    )

    uploaded_file = st.file_uploader(
        "Upload a contract",
        type=SUPPORTED_EXTENSIONS
    )

    # ---------- Preserve Uploaded Document ----------

    if uploaded_file is not None and uploaded_file.name != st.session_state.uploaded_filename:

        with st.spinner("Extracting document text..."):
            structured_doc = extract_structured(uploaded_file)

        st.session_state.structured_doc = structured_doc
        st.session_state.uploaded_filename = uploaded_file.name
        st.session_state.current_doc_id = uuid.uuid4().hex

        # Reset per-document analysis state
        st.session_state.explanation = ""
        st.session_state.risk_data = None
        st.session_state.clause_data = None
        st.session_state.qa_history = []
        st.session_state.documents_added = False

    structured_doc = st.session_state.structured_doc

    # ---------- Continue Only If Document Exists ----------

    if structured_doc:

        extracted_text = structured_doc["full_text"]

        st.success("Document loaded successfully.")

        st.caption(f"Current document: {st.session_state.uploaded_filename}")

        if structured_doc.get("used_ocr"):
            st.info("This document had no extractable text layer — content was recovered using OCR.")

        if not st.session_state.documents_added:

            chunks = chunk_structured_document(structured_doc)

            add_documents(
                doc_id=st.session_state.current_doc_id,
                filename=st.session_state.uploaded_filename,
                user_id=user["id"],
                chunks=chunks,
            )

            save_document(
                doc_id=st.session_state.current_doc_id,
                user_id=user["id"],
                filename=st.session_state.uploaded_filename,
                used_ocr=structured_doc.get("used_ocr", False),
            )

            st.session_state.documents_added = True

        # ---------- Document Preview ----------

        st.subheader("Document Preview")

        st.text_area(
            "Content",
            extracted_text,
            height=300
        )

        st.divider()

        # ---------- Action Buttons ----------

        col1, col2, col3 = st.columns(3)

        with col1:
            explain_btn = st.button("Explain Contract")

        with col2:
            clause_btn = st.button("Detect Missing Clauses")

        with col3:
            risk_btn = st.button("Analyze Risk")

        # ---------- Contract Explanation ----------

        if explain_btn:

            with st.spinner("Analyzing document..."):

                st.session_state.explanation = explain_contract(extracted_text)

        if st.session_state.explanation:

            with st.expander("Contract Explanation"):

                st.write(st.session_state.explanation)

        # ---------- Missing Clauses ----------

        if clause_btn:

            with st.spinner("Checking clauses..."):

                st.session_state.clause_data = detect_missing_clauses(extracted_text)

        if st.session_state.clause_data:

            clause_data = st.session_state.clause_data

            with st.expander("Missing Clauses", expanded=True):

                if clause_data.get("clauses"):

                    checklist = build_checklist(clause_data["clauses"])
                    st.markdown("**Clause Checklist**")
                    for line in checklist:
                        st.write(line)

                    st.markdown("---")

                    for item in clause_data["clauses"]:
                        if not item["present"]:
                            st.markdown(f"**{item['clause']} — Missing**")
                            if item.get("risk_if_missing"):
                                st.caption(f"Risk: {item['risk_if_missing']}")
                            if item.get("recommendation"):
                                st.caption(f"Recommendation: {item['recommendation']}")

                    st.markdown("---")
                    st.markdown("**Highlighted Clauses in Document**")
                    highlighted_html = highlight_clauses_in_text(
                        extracted_text, clause_data["clauses"]
                    )
                    st.markdown(
                        f'<div style="max-height:400px;overflow-y:auto;">{highlighted_html}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.write(clause_data.get("raw_text", "No data available."))

        # ---------- Risk Assessment ----------

        if risk_btn:

            with st.spinner("Performing risk analysis..."):

                clause_results = None
                if st.session_state.clause_data and st.session_state.clause_data.get("clauses"):
                    clause_results = st.session_state.clause_data["clauses"]

                risk_data = analyze_risk(extracted_text, clause_results=clause_results)
                st.session_state.risk_data = risk_data

                if not risk_data.get("error"):
                    save_risk_analysis(
                        user_id=user["id"],
                        document_id=st.session_state.current_doc_id,
                        risk_score=risk_data["risk_score"],
                        risk_level=risk_data["risk_level"],
                    )

        if st.session_state.risk_data:

            risk_data = st.session_state.risk_data

            with st.expander("Risk Assessment", expanded=True):

                if risk_data.get("error"):
                    st.write(risk_data["narrative"])
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Risk Score", f"{risk_data['risk_score']}/100")
                    m2.metric("Risk Level", risk_data["risk_level"])
                    m3.metric("Confidence", f"{risk_data['confidence']}%")

                    st.markdown("**Risk Breakdown**")
                    breakdown = risk_data.get("breakdown", {})
                    for key, value in breakdown.items():
                        if value is not None:
                            st.write(f"{key.replace('_', ' ').title()}: {value}/100")

                    if risk_data.get("major_risks"):
                        st.markdown("**Major Risks**")
                        for r in risk_data["major_risks"]:
                            st.write(f"- {r}")

                    if risk_data.get("recommendations"):
                        st.markdown("**Recommendations**")
                        for r in risk_data["recommendations"]:
                            st.write(f"- {r}")

                    if risk_data.get("narrative"):
                        st.markdown("**Summary**")
                        st.write(risk_data["narrative"])

        st.divider()

        # ---------- Ask Questions ----------

        st.subheader("Ask Questions")

        question = st.text_input("Enter your question")

        ask_btn = st.button("Ask")

        if ask_btn and question:

            with st.spinner("Searching document..."):

                result = answer_question(
                    question,
                    doc_id=st.session_state.current_doc_id,
                    user_id=user["id"],
                    cross_document=False,
                )

                st.session_state.qa_history.append({
                    "question": question,
                    "answer": result["answer"],
                    "sources": result["sources"],
                })

        if st.session_state.qa_history:

            latest = st.session_state.qa_history[-1]

            with st.expander("Response", expanded=True):

                st.write(latest["answer"])

                if latest["sources"]:
                    st.markdown("**Source:**")
                    for src in latest["sources"]:
                        st.caption(f"{src['filename']} — Page {src['page']}, Paragraph {src['paragraph']}")

        st.divider()

        # ---------- Clear Workspace ----------

        if st.button("Clear Workspace"):

            delete_document(st.session_state.current_doc_id)

            st.session_state.structured_doc = None
            st.session_state.uploaded_filename = ""
            st.session_state.current_doc_id = ""
            st.session_state.explanation = ""
            st.session_state.risk_data = None
            st.session_state.clause_data = None
            st.session_state.qa_history = []
            st.session_state.documents_added = False

            st.rerun()

    else:

        st.info("Upload a document to begin analysis.")

# ---------------- MULTI-DOCUMENT SEARCH ----------------

elif page == "Multi-Document Search":

    st.title("Multi-Document Search")

    st.caption(
        "Ask a question across every contract you've uploaded — not just the one currently open."
    )

    st.divider()

    user_docs = get_user_documents(user["id"])

    if not user_docs:
        st.info("Upload documents in Document Analysis first to search across them.")
    else:
        st.markdown(f"**{len(user_docs)} document(s)** in your workspace:")
        for d in user_docs:
            st.caption(f"• {d['filename']}")

        st.divider()

        cross_question = st.text_input("Enter your question", key="cross_doc_question")
        cross_ask_btn = st.button("Search All Documents")

        if cross_ask_btn and cross_question:

            with st.spinner("Searching across all documents..."):

                result = answer_question(
                    cross_question,
                    user_id=user["id"],
                    cross_document=True,
                )

            st.markdown("### Answer")
            st.write(result["answer"])

            if result["sources"]:
                st.markdown("**Sources:**")
                for src in result["sources"]:
                    st.caption(f"{src['filename']} — Page {src['page']}, Paragraph {src['paragraph']}")

# ---------------- CONTRACT COMPARISON ----------------

elif page == "Contract Comparison":

    st.title("Contract Comparison")

    st.caption(
        "Compare two agreements to identify differences and potential changes."
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        file1 = st.file_uploader(
            "First Contract",
            type=SUPPORTED_EXTENSIONS,
            key="file1"
        )

    with col2:

        file2 = st.file_uploader(
            "Second Contract",
            type=SUPPORTED_EXTENSIONS,
            key="file2"
        )

    # ---------- Preserve Contracts ----------

    if file1 is not None and file2 is not None:

        text1 = extract_structured(file1)["full_text"]
        text2 = extract_structured(file2)["full_text"]

        st.session_state.comparison_text1 = text1
        st.session_state.comparison_text2 = text2
        st.session_state.comparison_filename1 = file1.name
        st.session_state.comparison_filename2 = file2.name

    elif (
        st.session_state.comparison_text1
        and
        st.session_state.comparison_text2
    ):

        text1 = st.session_state.comparison_text1
        text2 = st.session_state.comparison_text2

    else:

        text1 = None
        text2 = None

    # ---------- Continue Only If Both Contracts Exist ----------

    if text1 and text2:

        st.success("Contracts loaded successfully.")

        compare_btn = st.button("Compare Contracts")

        if compare_btn:

            with st.spinner("Analyzing differences..."):

                st.session_state.comparison_report = compare_contracts(text1, text2)

        if st.session_state.comparison_report:

            st.divider()

            with st.expander("Comparison Report", expanded=True):

                st.write(st.session_state.comparison_report)

        st.divider()

        # ---------- Clear Comparison ----------

        clear_btn = st.button("Clear Comparison")

        if clear_btn:

            st.session_state.comparison_text1 = ""
            st.session_state.comparison_text2 = ""
            st.session_state.comparison_report = ""

            st.rerun()

    else:

        st.info("Upload two contracts to begin comparison.")

# ---------------- ANALYTICS ----------------

elif page == "Analytics":

    st.title("Analytics")

    st.caption("Overview of contract analysis and risk metrics.")

    st.divider()

    risk_data = st.session_state.risk_data
    clause_data = st.session_state.clause_data

    has_risk = risk_data and not risk_data.get("error")
    has_clauses = clause_data and clause_data.get("clauses")

    if not has_risk and not has_clauses:

        st.info("Run document analysis to view analytics.")

    else:

        # ---------- Metrics ----------

        risk_score = risk_data["risk_score"] if has_risk else "N/A"
        risk_level = risk_data["risk_level"] if has_risk else "N/A"
        confidence = risk_data["confidence"] if has_risk else "N/A"
        missing_count = sum(1 for c in clause_data["clauses"] if not c["present"]) if has_clauses else 0
        total_clauses = len(clause_data["clauses"]) if has_clauses else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Risk Score", f"{risk_score}/100" if has_risk else "N/A")
        col2.metric("Risk Level", risk_level)
        col3.metric("Confidence", f"{confidence}%" if has_risk else "N/A")
        col4.metric("Missing Clauses", f"{missing_count}/{total_clauses}" if has_clauses else "N/A")

        st.markdown("### Risk Insights")

        col1, col2 = st.columns(2)

        # ---------- Risk Category Breakdown ----------

        with col1:
            if has_risk and risk_data.get("breakdown"):
                breakdown = risk_data["breakdown"]
                labels = [k.replace("_", " ").title() for k, v in breakdown.items() if v is not None]
                values = [v for v in breakdown.values() if v is not None]

                fig1 = px.bar(
                    x=labels,
                    y=values,
                    title="Risk Category Breakdown",
                    labels={"x": "Category", "y": "Score"},
                    color=labels,
                    color_discrete_sequence=["#E7E5E4", "#D6D3D1", "#A8A29E", "#78716C"],
                )
                fig1.update_layout(plot_bgcolor="white", paper_bgcolor="white", font_color="#334155", showlegend=False)
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("Run risk analysis to view the risk category breakdown.")

        # ---------- Clause Distribution ----------

        with col2:
            if has_clauses:
                present = sum(1 for c in clause_data["clauses"] if c["present"])
                missing = sum(1 for c in clause_data["clauses"] if not c["present"])

                fig2 = px.pie(
                    names=["Present", "Missing"],
                    values=[present, missing],
                    title="Clause Distribution",
                    color_discrete_sequence=["#A8A29E", "#E7E5E4"],
                )
                fig2.update_layout(paper_bgcolor="white", font_color="#334155")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Run missing clause detection to view clause distribution.")

        st.markdown("### Risk Overview")

        col1, col2 = st.columns(2)

        # ---------- Contract Health Score ----------

        with col1:
            health_score = 100 - risk_score if has_risk else 0

            fig3 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=health_score,
                title={"text": "Contract Health Score"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#78716C"},
                    "steps": [
                        {"range": [0, 40], "color": "#A8A29E"},
                        {"range": [40, 70], "color": "#D6D3D1"},
                        {"range": [70, 100], "color": "#F5F5F4"},
                    ],
                },
            ))
            st.plotly_chart(fig3, use_container_width=True)

        # ---------- Missing Clause Percentage ----------

        with col2:
            missing_pct = round((missing_count / total_clauses) * 100) if total_clauses else 0

            fig4 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=missing_pct,
                title={"text": "Missing Clause Percentage"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#78716C"},
                    "steps": [
                        {"range": [0, 30], "color": "#F5F5F4"},
                        {"range": [30, 60], "color": "#D6D3D1"},
                        {"range": [60, 100], "color": "#A8A29E"},
                    ],
                },
            ))
            st.plotly_chart(fig4, use_container_width=True)

        # ---------- Risk Timeline ----------

        st.markdown("### Risk Timeline")

        risk_history = get_risk_history(user["id"])

        if risk_history:
            timeline_x = [r["created_at"] for r in risk_history]
            timeline_y = [r["risk_score"] for r in risk_history]

            fig5 = px.line(
                x=timeline_x,
                y=timeline_y,
                title="Risk Score Over Time (All Documents)",
                labels={"x": "Date", "y": "Risk Score"},
                markers=True,
            )
            fig5.update_traces(line_color="#78716C")
            fig5.update_layout(plot_bgcolor="white", paper_bgcolor="white", font_color="#334155")
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.info("Analyze risk on a few documents to build a timeline.")

        st.divider()

        st.caption("Analytics are automatically generated from the latest document analysis.")

# ---------------- REPORTS ----------------

elif page == "Reports":

    st.title("Reports")

    st.caption("Generate and download analysis reports.")

    st.divider()

    has_content = (
        st.session_state.explanation
        or st.session_state.risk_data
        or st.session_state.clause_data
        or st.session_state.comparison_report
        or st.session_state.qa_history
    )

    if not has_content:

        st.info("Run document analysis or contract comparison to generate reports.")

    else:

        st.write(
            """
The report includes:

• Contract Explanation

• Structured Risk Assessment with Confidence Score

• Missing Clause Checklist

• Contract Comparison

• Question & Answer History with Source Citations
"""
        )

        generate_btn = st.button("Generate Report")

        if generate_btn:

            with st.spinner("Preparing report..."):

                pdf_path = generate_pdf(
                    st.session_state.uploaded_filename,
                    st.session_state.explanation,
                    st.session_state.risk_data,
                    st.session_state.clause_data,
                    st.session_state.comparison_report,
                    st.session_state.qa_history,
                )

                summary_bits = []
                if st.session_state.risk_data and not st.session_state.risk_data.get("error"):
                    summary_bits.append(f"Risk {st.session_state.risk_data['risk_score']}/100")

                save_report(
                    user_id=user["id"],
                    document_id=st.session_state.current_doc_id or None,
                    report_type="Full Analysis",
                    pdf_path=pdf_path,
                    summary=", ".join(summary_bits) if summary_bits else None,
                )

            st.success("Report generated successfully.")

            with open(pdf_path, "rb") as file:

                st.download_button(
                    label="Download PDF",
                    data=file,
                    file_name="JurisAI_Report.pdf",
                    mime="application/pdf"
                )

# ---------------- HISTORY ----------------

elif page == "History":

    st.title("History")

    st.caption("Your uploaded documents and generated reports.")

    st.divider()

    st.subheader("Documents")

    docs = get_user_documents(user["id"])

    if docs:
        for d in docs:
            ocr_tag = " (OCR)" if d.get("used_ocr") else ""
            st.write(f"• {d['filename']}{ocr_tag} — uploaded {d['created_at']}")
    else:
        st.info("No documents uploaded yet.")

    st.divider()

    st.subheader("Reports")

    reports = get_user_reports(user["id"])

    if reports:
        for r in reports:
            label = f"{r['report_type']} — {r.get('document_filename') or 'N/A'} ({r['created_at']})"
            if r.get("summary"):
                label += f" — {r['summary']}"
            st.write(f"• {label}")

            if r.get("pdf_path"):
                try:
                    with open(r["pdf_path"], "rb") as f:
                        st.download_button(
                            "Download",
                            data=f,
                            file_name=f"JurisAI_Report_{r['id']}.pdf",
                            mime="application/pdf",
                            key=f"report_{r['id']}",
                        )
                except FileNotFoundError:
                    st.caption("(file no longer available)")
    else:
        st.info("No reports generated yet.")

# ---------------- ADMIN ----------------

elif page == "Admin":

    st.title("Admin Dashboard")

    st.caption("Workspace-wide usage and user management.")

    st.divider()

    stats = get_admin_stats()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users", stats["users"])
    col2.metric("Total Documents", stats["documents"])
    col3.metric("Total Reports", stats["reports"])

    st.divider()

    st.subheader("Users")
    for u in list_users():
        st.write(f"• {u['username']} — `{u['role']}` — joined {u['created_at']}")

    st.divider()

    st.subheader("All Documents")
    all_docs = get_all_documents()
    if all_docs:
        for d in all_docs:
            st.write(f"• {d['filename']} — uploaded by {d['username']} on {d['created_at']}")
    else:
        st.info("No documents uploaded yet.")

    st.divider()

    st.subheader("All Reports")
    all_reports = get_all_reports()
    if all_reports:
        for r in all_reports:
            st.write(f"• {r['report_type']} — generated by {r['username']} on {r['created_at']}")
    else:
        st.info("No reports generated yet.")

# ---------------- FOOTER ----------------

st.divider()

st.caption(
    "JurisAI • Contract Intelligence"
)
