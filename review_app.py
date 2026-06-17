import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from db_fetch import fetch_logicbox_qb_list, fetch_questions_for_qb
from generate_review_doc import build_review_document_multi
from mapper import map_db_row_to_qc_input
from qc_engine import qc_and_revamp_chain
from utils import strip_html


st.set_page_config(layout="wide", page_title="AILB QC & Revamp Review")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main > div {
        padding-top: 2.5rem;
        padding-bottom: 2rem;
        padding-left: 3rem;
        padding-right: 3rem;
        max-width: 1400px;
        margin: 0 auto;
    }
    
    h1 {
        color: #0f172a;
        font-weight: 700;
        font-size: 2.4rem;
        letter-spacing: -0.02em;
        margin-bottom: 0.3rem;
    }
    
    .subtitle {
        color: #64748b;
        font-size: 1rem;
        font-weight: 400;
        margin-bottom: 2rem;
    }
    
    .stRadio > div > div {
        gap: 0.5rem;
        flex-wrap: wrap;
    }
    
    .stRadio > div > div > label {
        background: #ffffff;
        padding: 0.5rem 1.1rem;
        border-radius: 9999px;
        border: 1.5px solid #e2e8f0;
        font-size: 0.9rem;
        font-weight: 500;
        color: #475569;
        transition: all 0.2s ease;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    
    .stRadio > div > div > label:hover {
        background: #f1f5f9;
        border-color: #94a3b8;
        color: #1e293b;
    }
    
    .stRadio > div > div > label[data-checked="true"] {
        background: #6366f1;
        color: #ffffff;
        border-color: #6366f1;
        box-shadow: 0 2px 4px rgba(99, 102, 241, 0.3);
    }
    
    .stTextInput > div > div > input {
        border-radius: 0.6rem;
        border: 1.5px solid #e2e8f0;
        padding: 0.65rem 1rem;
        font-size: 1rem;
        color: #1e293b;
        background: #ffffff;
        transition: all 0.2s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #6366f1;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
        outline: none;
    }
    
    .stTextInput > div > div > input::placeholder {
        color: #94a3b8;
    }
    
    .search-container {
        background: #ffffff;
        border-radius: 0.75rem;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    
    .question-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }
    
    .question-card:hover {
        box-shadow: 0 6px 12px rgba(0,0,0,0.08);
        border-color: #c7d2fe;
        transform: translateY(-1px);
    }
    
    .question-header {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        margin-bottom: 0.6rem;
    }
    
    .question-id {
        background: #eef2ff;
        color: #3730a3;
        font-weight: 600;
        font-size: 0.8rem;
        padding: 0.2rem 0.6rem;
        border-radius: 0.375rem;
        white-space: nowrap;
        letter-spacing: 0.02em;
    }
    
    .question-preview {
        color: #1e293b;
        font-size: 0.95rem;
        line-height: 1.65;
        word-wrap: break-word;
        flex: 1;
    }
    
    .stButton > button {
        border-radius: 0.5rem;
        font-weight: 600;
        font-size: 0.9rem;
        transition: all 0.2s ease;
        border: none;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.12);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    div[data-testid="stVerticalBlock"] > div[data-testid="stButton"] button[kind="secondary"]:not(:hover) {
        background: #ffffff !important;
        border: 1.5px solid #e2e8f0 !important;
        color: #334155 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
    }
    
    div[data-testid="stVerticalBlock"] > div[data-testid="stButton"] button[kind="primary"]:not(:hover) {
        background: #ffffff !important;
        border: 2px solid #6366f1 !important;
        color: #312e81 !important;
        box-shadow: 0 2px 6px rgba(99, 102, 241, 0.2) !important;
    }
    
    .sidebar-header {
        font-weight: 700;
        font-size: 1.2rem;
        color: #0f172a;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .progress-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    
    .progress-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }
    
    .progress-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
        margin-top: 0.2rem;
    }
    
    .comparison-panel {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    
    .section-title {
        font-weight: 700;
        font-size: 1.1rem;
        color: #1e293b;
        margin-bottom: 0.75rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .tag {
        display: inline-block;
        background: #f1f5f9;
        color: #475569;
        font-size: 0.75rem;
        padding: 0.15rem 0.5rem;
        border-radius: 0.25rem;
        margin-right: 0.25rem;
        margin-bottom: 0.25rem;
        font-weight: 500;
    }
    
    .divider {
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 1.5rem 0;
    }
    
    .info-bar {
        background: #f8fafc;
        border-radius: 0.6rem;
        padding: 0.75rem 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
        font-size: 0.9rem;
        color: #475569;
    }
    
    .stMetric > div > div > div > div {
        color: #0f172a;
        font-weight: 700;
    }
    
    .stMetric > div > div > div > label {
        color: #64748b;
        font-weight: 500;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

st.title("AILB QC & Revamp Documentation")
st.caption("Review LogicBox questions, apply QC suggestions, and generate polished question banks.")


def clean_for_display(value):
    text = "" if value is None else str(value)
    return strip_html(text) if "<" in text else text


def detect_code_language(text):
    content = (text or "").lower()
    if "using system" in content or "namespace" in content:
        return "csharp"
    return "python"


def render_text_panel(label, value, key, height=260, expanded=False):
    text = clean_for_display(value)
    if len(text) > 500:
        with st.expander(label, expanded=expanded):
            st.text_area(label, value=text, height=max(height, 360), disabled=True, key=key)
    else:
        st.text_area(label, value=text, height=height, disabled=True, key=key)


def render_code_panel(label, value, key):
    text = clean_for_display(value)
    language = detect_code_language(text)
    st.code(text, language=language)


def section_reasons(qc_section):
    if not isinstance(qc_section, dict):
        return []
    if qc_section.get("qc_result") != "fail":
        return []
    reasons = qc_section.get("reasons", [])
    if isinstance(reasons, list):
        return [str(reason) for reason in reasons if str(reason).strip()]
    if reasons:
        return [str(reasons)]
    return []


def maybe_show_reasons(label, qc_section):
    reasons = section_reasons(qc_section)
    if reasons:
        st.warning("\n".join(f"- {reason}" for reason in reasons))
    return reasons


def is_failed(qc_section):
    if not isinstance(qc_section, dict):
        return False
    return str(qc_section.get("qc_result", "")).strip().lower() == "fail"


def extract_scenario_suggestion(suggested):
    if isinstance(suggested, dict):
        for key in ("scenario", "scenario_text", "revamped_scenario"):
            value = suggested.get(key)
            if value:
                return value
        nested = suggested.get("instructions")
        if isinstance(nested, dict):
            for key in ("scenario", "scenario_text", "revamped_scenario"):
                value = nested.get(key)
                if value:
                    return value
        return json.dumps(suggested, indent=2)
    return suggested


def serialize_progress(progress_data):
    if not isinstance(progress_data, dict):
        return "{}"
    try:
        return json.dumps(progress_data)
    except (TypeError, ValueError):
        serializable = {}
        for que_id, entry in progress_data.items():
            if not isinstance(entry, dict):
                continue
            try:
                json.dumps(entry)
                serializable[que_id] = entry
            except (TypeError, ValueError):
                serializable[que_id] = {
                    "mapped": entry.get("mapped", {}),
                    "qc_result": entry.get("qc_result", {}),
                    "approved": entry.get("approved", {}),
                }
        return json.dumps(serializable)


def get_progress_file_name(qb_id, qb_name):
    raw_name = str(qb_name or f"qb_{qb_id}").strip()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw_name).strip("_") or f"qb_{qb_id}"
    return f"progress_{qb_id}_{safe_name}.json"


def save_progress(qb_id, qb_name, progress_data):
    file_path = Path(get_progress_file_name(qb_id, qb_name))
    payload = serialize_progress(progress_data)
    file_path.write_text(payload, encoding="utf-8")


def load_progress(qb_id, qb_name):
    file_path = Path(get_progress_file_name(qb_id, qb_name))
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def init_session_state():
    defaults = {
        "current_qb_id": None,
        "current_df": None,
        "current_question": None,
        "reviewed_questions": {},
        "cached_results": {},
        "last_saved_approved": {},
        "pending_reviewed": None,
        "_qb_search_query": "",
        "_qb_suggestions": [],
        "_qb_selected_id": None,
        "_qb_input_mode": "name",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_question_status(que_id):
    return str(que_id) in st.session_state["reviewed_questions"]


def run_qc_if_needed(que_id, question_row):
    que_id_str = str(que_id)
    if que_id_str in st.session_state["cached_results"]:
        return st.session_state["cached_results"][que_id_str]

    mapped = map_db_row_to_qc_input(question_row)
    with st.spinner(f"Running QC for QueId {que_id}..."):
        qc_result = qc_and_revamp_chain(
            topic=mapped.get("topic", ""),
            sub_topic=mapped.get("sub_topic", ""),
            difficulty=mapped.get("difficulty", ""),
            code_snippet=mapped.get("code_snippet", ""),
            instructions=mapped.get("instructions", ""),
            answers=mapped.get("answers", {}),
            scenario=mapped.get("scenario", ""),
        )

    entry = {
        "mapped": mapped,
        "qc_result": qc_result,
        "approved": {},
    }
    st.session_state["cached_results"][que_id_str] = entry
    st.session_state["reviewed_questions"][que_id_str] = entry
    st.session_state["last_saved_approved"][que_id_str] = {}
    return entry


init_session_state()

if st.session_state["current_question"] is None:
    st.subheader("Question Bank Search")

    current_input_mode = st.radio(
        "Search mode",
        ["Search by Name", "Search by QID"],
        horizontal=True,
        label_visibility="collapsed",
        index=0 if st.session_state["_qb_input_mode"] == "name" else 1,
        key="qb_mode_radio",
    )
    st.session_state["_qb_input_mode"] = "name" if "Name" in current_input_mode else "qid"

    if st.session_state["_qb_input_mode"] == "name":
        search_name = st.text_input(
            "Search LogicBox Question Banks by name",
            placeholder="Start typing a LogicBox QB name...",
            key="qb_search_input",
        )
        current_query = (search_name or "").strip()
        prev_query = (st.session_state.get("_qb_search_query") or "").strip()

        if current_query != prev_query:
            st.session_state["_qb_search_query"] = current_query
            st.session_state["_qb_suggestions"] = []
            st.session_state["_qb_selected_id"] = None
            if current_query:
                try:
                    with st.spinner("Searching LogicBox question banks..."):
                        rows = fetch_logicbox_qb_list(search=current_query, limit=50)
                    matching = [
                        row for row in rows
                        if isinstance(row.get("QBName"), str)
                        and any(token.lower() in row["QBName"].lower() for token in ["logicbox", "logic box", "lb_", "_lb"])
                    ]
                    st.session_state["_qb_suggestions"] = matching
                except Exception as exc:
                    st.error(f"Error searching question banks: {exc}")
                    st.session_state["_qb_suggestions"] = []

        suggestions = st.session_state.get("_qb_suggestions", [])
        selected_id = st.session_state.get("_qb_selected_id")

        st.markdown('<p style="font-size:0.9rem;font-weight:600;color:#374151;margin-bottom:0.5rem;">Matches:</p>', unsafe_allow_html=True)
        seen = set()
        unique_suggestions = []
        for item in suggestions:
            key = (item.get("QBId"), item.get("QBName"))
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(item)
        if unique_suggestions:
            cols = st.columns(2)
            for idx, qb in enumerate(unique_suggestions):
                col = cols[idx % 2]
                qb_id = qb.get("QBId")
                label = qb.get("QBName", str(qb_id))
                q_count = qb.get("NoOfQues")
                count_text = f" ({q_count} ques)" if q_count is not None else ""
                button_label = f"{label}{count_text}"
                is_selected = selected_id is not None and qb_id is not None and int(qb_id) == int(selected_id)
                with col:
                    if st.button(
                        button_label,
                        key=f"sugg_{idx}_{qb_id}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state["_qb_selected_id"] = qb_id
                        st.session_state["_qb_search_query"] = label
                        st.session_state["current_qb_id"] = qb_id
                        st.session_state["current_qb_name"] = label
                        try:
                            with st.spinner("Loading questions..."):
                                df = fetch_questions_for_qb(qb_id)
                        except Exception as exc:
                            st.error(f"Error fetching questions: {exc}")
                            df = pd.DataFrame()
                        if df.empty:
                            st.warning("No questions found for this LogicBox QB.")
                        else:
                            st.session_state["current_df"] = df
                            existing_reviewed = load_progress(qb_id, label)
                            if existing_reviewed:
                                st.session_state["pending_reviewed"] = existing_reviewed
            if len(unique_suggestions) > 10:
                st.caption(f"Showing all {len(unique_suggestions)} matches. Refine your search if needed.")
        elif current_query:
            st.info("No matching LogicBox Question Banks found.")
    else:
        qb_id_raw = st.text_input("Enter QB ID", placeholder="e.g. 12345")
        if st.button("Load Questions by QID"):
            if not qb_id_raw.strip():
                st.error("Please enter a QB ID.")
            else:
                try:
                    qb_id = int(qb_id_raw.strip())
                except ValueError:
                    st.error("QB ID must be a number.")
                    qb_id = None
                if qb_id is not None:
                    try:
                        with st.spinner("Loading questions..."):
                            df = fetch_questions_for_qb(qb_id)
                    except Exception as exc:
                        st.error(f"Error fetching questions: {exc}")
                        df = pd.DataFrame()
                    if df.empty:
                        st.warning("No questions found for this QB ID.")
                    else:
                        st.session_state["current_qb_id"] = qb_id
                        st.session_state["current_qb_name"] = str(qb_id)
                        st.session_state["current_df"] = df
                        existing_reviewed = load_progress(qb_id, str(qb_id))
                        if existing_reviewed:
                            st.session_state["pending_reviewed"] = existing_reviewed

    if st.session_state.get("pending_reviewed") is not None:
        if st.button("Resume previous session"):
            pending = st.session_state.pop("pending_reviewed")
            st.session_state["reviewed_questions"] = pending
            for que_id, data in pending.items():
                que_id_str = str(que_id)
                st.session_state["cached_results"][que_id_str] = data
                st.session_state["last_saved_approved"][que_id_str] = data.get("approved", {}).copy()

    df = st.session_state.get("current_df")
    if df is not None and not df.empty:
        st.subheader("Questions", divider="rainbow")
        for _, row in df.iterrows():
            que_id = int(row["QueId"])
            preview = strip_html(str(row.get("Question", "")))
            difficulty = row.get("DifficultyLevel", "")
            difficulty_value = (str(difficulty) or "").strip()
            if not difficulty_value:
                difficulty_value = "N/A"
            elif difficulty_value.lower() == "easy":
                difficulty_value = "Easy"
            elif difficulty_value.lower() == "medium":
                difficulty_value = "Medium"
            elif difficulty_value.lower() == "hard":
                difficulty_value = "Hard"

            with st.container(border=True):
                st.text_area(
                    "",
                    value=f"Q{que_id} | {difficulty_value}\n\n{preview}",
                    height=140,
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"card_{que_id}",
                )
                if st.button("Revamp This Question", key=f"revamp_{que_id}", type="primary", use_container_width=True):
                    st.session_state["current_question"] = str(que_id)
                    st.rerun()
else:
    que_id = st.session_state["current_question"]
    if st.button("Back to Question List"):
        current_approved = st.session_state["reviewed_questions"].get(que_id, {}).get("approved", {})
        last_approved = st.session_state["last_saved_approved"].get(que_id, {})
        if current_approved != last_approved:
            st.warning("You have unsaved changes for this question")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Discard changes and go back"):
                    st.session_state["current_question"] = None
                    st.rerun()
            with col2:
                if st.button("Save to Document"):
                    entry = st.session_state["reviewed_questions"].get(que_id)
                    if entry:
                        st.session_state["last_saved_approved"][que_id] = entry.get("approved", {}).copy()
                    st.session_state["current_question"] = None
                    st.rerun()
        else:
            st.session_state["current_question"] = None
            st.rerun()

    df = st.session_state.get("current_df")
    question_row = None
    if df is not None:
        matches = df[pd.to_numeric(df["QueId"], errors="coerce") == int(que_id)]
        if not matches.empty:
            question_row = matches.iloc[0].to_dict()

    if question_row is None:
        st.error("Question not found in current list.")
    else:
        if str(que_id) not in st.session_state.get("cached_results", {}):
            with st.spinner("Running QC..."):
                entry = run_qc_if_needed(que_id, question_row)
        else:
            entry = st.session_state["cached_results"][str(que_id)]
        mapped = entry["mapped"]
        qc = entry["qc_result"]
        approved = entry["approved"]

        topic = mapped.get("topic", "")
        sub_topic = mapped.get("sub_topic", "")
        difficulty = mapped.get("difficulty", "")
        info_text = f"Topic: {topic} | Sub-topic: {sub_topic} | Difficulty: {difficulty}"
        st.markdown(f"""
        <div class="info-bar">
            <span style="font-weight:600;color:#1e293b;">{info_text}</span>
        </div>
        """, unsafe_allow_html=True)

        scenario_qc = qc.get("scenario_qc", {}) if isinstance(qc.get("scenario_qc", {}), dict) else {}
        instructions_qc = qc.get("instructions_qc", {}) if isinstance(qc.get("instructions_qc", {}), dict) else {}
        sections = [
            ("scenario", "Scenario", mapped.get("scenario", ""), qc.get("revamped_scenario") or scenario_qc.get("revamped_scenario"), scenario_qc),
            ("instructions", "Instructions", mapped.get("instructions", ""), qc.get("revamped_instructions") or instructions_qc.get("revamped_instructions"), instructions_qc),
            ("code_snippet", "Code Snippet / Sample Script", mapped.get("code_snippet", ""), qc.get("revamped_code_snippet"), qc.get("code_snippet_qc", {})),
        ]

        for key, label, original, suggested, qc_section in sections:
            st.subheader(label)
            maybe_show_reasons(label, qc_section)

            qc_failed = is_failed(qc_section)
            suggested_value = suggested
            if not qc_failed and not suggested_value:
                suggested_value = original
            if key == "scenario":
                suggested_display = extract_scenario_suggestion(suggested_value)
            else:
                suggested_display = suggested_value

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Current (from DB)**")
                if key == "code_snippet":
                    render_code_panel(f"Current {label} (from database)", original, key=f"orig_{key}_{que_id}")
                else:
                    render_text_panel(f"Current {label} (from database)", original, key=f"orig_{key}_{que_id}")

            with col2:
                st.markdown("**Suggested Revamp**")
                if key == "code_snippet":
                    render_code_panel(f"Suggested {label}", suggested_display, key=f"sugg_{key}_{que_id}")
                else:
                    render_text_panel(f"Suggested {label}", suggested_display, key=f"sugg_{key}_{que_id}")

            if key != "code_snippet":
                approved[key] = st.checkbox(f"Apply this change to {label}", key=f"approve_{key}_{que_id}", value=approved.get(key, False))

        st.subheader("Alternate Answers")
        alt_answers = qc.get("alternate_answers", {})
        if isinstance(alt_answers, dict) and alt_answers:
            rows = []
            answers = mapped.get("answers", {})
            for blank_key in sorted(set(list(answers.keys()) + list(alt_answers.keys()))):
                current_answer = answers.get(blank_key, "")
                suggested_alternates = alt_answers.get(blank_key, [])
                if isinstance(suggested_alternates, list):
                    alternates_display = ", ".join(str(item) for item in suggested_alternates)
                else:
                    alternates_display = str(suggested_alternates)
                rows.append(
                    {
                        "Blank": blank_key,
                        "Current Answer": current_answer,
                        "Suggested Alternates": alternates_display,
                    }
                )

            alt_df = pd.DataFrame(rows)
            st.dataframe(alt_df, use_container_width=True, hide_index=True)
            approved["alternate_answers"] = st.checkbox("Apply alternate answers", key=f"approve_alt_{que_id}", value=approved.get("alternate_answers", False))
        else:
            st.write("No alternate answers generated.")
            approved["alternate_answers"] = approved.get("alternate_answers", False)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save to Document"):
                st.session_state["last_saved_approved"][que_id] = approved.copy()
                st.session_state["current_question"] = None
                st.rerun()
        with col2:
            if st.button("Discard and go back"):
                st.session_state["current_question"] = None
                st.rerun()

with st.sidebar:
    st.markdown('<div class="sidebar-header">Progress</div>', unsafe_allow_html=True)

    reviewed = st.session_state.get("reviewed_questions", {})
    current_df = st.session_state.get("current_df")
    if current_df is None:
        current_df = pd.DataFrame()
    total = len(current_df)
    qb_name = st.session_state.get("current_qb_name")
    qb_id = st.session_state.get("current_qb_id")
    display_label = qb_name if qb_name else (str(qb_id) if qb_id else "None")

    st.markdown(f"""
    <div class="progress-card">
        <div class="progress-label">Question Bank</div>
        <div style="font-size:0.95rem;font-weight:600;color:#0f172a;margin-top:0.2rem;word-break:break-word;">{display_label}</div>
    </div>
    """, unsafe_allow_html=True)

    reviewed_count = len(reviewed)
    progress_pct = int((reviewed_count / total * 100)) if total else 0
    st.markdown(f"""
    <div class="progress-card">
        <div class="progress-label">Review Progress</div>
        <div class="progress-value">{reviewed_count} of {total}</div>
        <div style="margin-top:0.5rem;background:#e2e8f0;border-radius:9999px;height:8px;overflow:hidden;">
            <div style="background:#6366f1;height:100%;width:{progress_pct}%;border-radius:9999px;transition:width 0.3s ease;"></div>
        </div>
        <div style="font-size:0.8rem;color:#64748b;margin-top:0.3rem;">{progress_pct}% complete</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Save Progress", use_container_width=True, type="secondary"):
        qb_id = st.session_state.get("current_qb_id")
        qb_name = st.session_state.get("current_qb_name")
        if qb_id is not None:
            save_progress(qb_id, qb_name, reviewed)
            st.success("Progress saved!")

    reviewed_que_ids = []
    for qid in reviewed.keys():
        try:
            reviewed_que_ids.append(str(int(qid)))
        except (TypeError, ValueError):
            continue
    reviewed_que_ids = sorted(reviewed_que_ids, key=lambda x: int(x))
    disabled = len(reviewed_que_ids) == 0
    if st.button("Generate Complete Document", disabled=disabled, use_container_width=True, type="primary"):
        questions_data = []
        for que_id in reviewed_que_ids:
            data = reviewed[str(que_id)]
            questions_data.append({
                "que_id": que_id,
                "mapped": data["mapped"],
                "qc_result": data["qc_result"],
                "approved": data.get("approved", {}),
            })
        qb_name = st.session_state.get("current_qb_name") or st.session_state.get("current_qb_id") or "review"
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(qb_name)).strip("_") or "review"
        output_path = f"{safe_name}.docx"
        try:
            with st.spinner("Generating document..."):
                build_review_document_multi(
                    questions_data=questions_data,
                    output_path=output_path,
                )
            with open(output_path, "rb") as file_handle:
                st.session_state["download_bytes"] = file_handle.read()
            st.session_state["download_name"] = output_path
            st.success(f"Document generated: {output_path}")
        except Exception as exc:
            st.error(f"Failed to generate document: {exc}")
            st.session_state["download_bytes"] = None
            st.session_state["download_name"] = None

    if st.session_state.get("download_bytes") is not None:
        st.download_button(
            "Download .docx",
            data=st.session_state["download_bytes"],
            file_name=st.session_state.get("download_name") or "review.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    current_df = st.session_state.get("current_df")
    if current_df is not None and not current_df.empty:
        qids = [int(row["QueId"]) for _, row in current_df.iterrows() if pd.notna(row.get("QueId"))]
        reviewed = st.session_state.get("reviewed_questions", {})
        reviewed_keys = {str(qid) for qid in reviewed.keys()}
        checklist_key = f"_reviewed_qid_checkboxes_{qb_id or 'default'}"
        expected_qid_keys = {str(qid) for qid in qids}
        if checklist_key not in st.session_state:
            st.session_state[checklist_key] = {qid: qid in reviewed_keys for qid in expected_qid_keys}
        elif set(st.session_state[checklist_key].keys()) != expected_qid_keys:
            st.session_state[checklist_key] = {qid: qid in reviewed_keys for qid in expected_qid_keys}

        checked_count = sum(1 for qid in expected_qid_keys if qid in reviewed_keys)

        for key in st.session_state.get(checklist_key, {}):
            if key in reviewed_keys:
                st.session_state[checklist_key][key] = True
        st.markdown(f"""
        <div class="progress-card">
            <div class="progress-label">Review Checklist</div>
            <div class="progress-value">{checked_count} of {len(qids)}</div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("View QIDs", expanded=False):
            for qid in sorted(qids, key=lambda x: int(x)):
                qid_key = str(qid)
                checked = st.checkbox(
                    f"Q{qid}",
                    value=st.session_state[checklist_key].get(qid_key, False),
                    key=f"qid_check_{qb_id or 'default'}_{qid}",
                )
                st.session_state[checklist_key][qid_key] = checked

    st.divider()
