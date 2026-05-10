from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.hr_agent.config import load_settings
from src.hr_agent.graph import run_shortlisting
from src.hr_agent.models import OverrideRecord
from src.hr_agent.overrides import append_override, read_overrides

st.set_page_config(
    page_title="Explainable HR Shortlisting Agent",
    page_icon="briefcase",
    layout="wide",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Sidebar polish ─────────────────────────────── */
    [data-testid="stSidebar"] { padding-top: 1.5rem; }
    [data-testid="stSidebar"] .stMarkdown h3 { margin-bottom: 0.3rem; }

    /* ── Metric cards ───────────────────────────────── */
    .metric-row { display: flex; gap: 0.8rem; flex-wrap: wrap; margin: 0.6rem 0 1rem; }
    .metric-card {
        flex: 1; min-width: 140px; padding: 0.7rem 1rem;
        border-radius: 8px; border: 1px solid rgba(255,255,255,.08);
        background: rgba(255,255,255,.03);
    }
    .metric-card .label { font-size: 0.72rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.04em; }
    .metric-card .value { font-size: 1.15rem; font-weight: 600; margin-top: 2px; }

    /* ── Recommendation badges ──────────────────────── */
    .rec-hire   { color: #22c55e; }
    .rec-hold   { color: #eab308; }
    .rec-no_hire { color: #ef4444; }

    /* ── Section dividers ───────────────────────────── */
    .section-divider { margin: 2rem 0 1.2rem; border-top: 1px solid rgba(255,255,255,.07); }
</style>
""", unsafe_allow_html=True)

settings = load_settings()

# ── Auth gate ───────────────────────────────────────────────────────────────
if settings.app_access_token and settings.app_access_token != "change-me-for-demo":
    token = st.sidebar.text_input("Access token", type="password")
    if token != settings.app_access_token:
        st.warning("Enter the demo access token to continue.")
        st.stop()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("Explainable HR Shortlisting Agent")
st.caption("Rank candidates against a transparent rubric with human-in-the-loop overrides.")

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    output_dir = st.text_input("Output directory", "outputs")
    
    provider_options = ["Groq", "Hugging Face", "Gemini", "Heuristics"]
    # Fallback to Heuristics if active_provider is invalid
    default_idx = provider_options.index(settings.active_provider) if settings.active_provider in provider_options else 3
    settings.active_provider = st.selectbox("LLM Provider", provider_options, index=default_idx)
    
    if settings.active_provider == "Groq":
        model_display = settings.groq_model
        if not settings.groq_api_key:
            st.warning("GROQ_API_KEY not found in .env. Will fall back to Heuristics.")
    elif settings.active_provider == "Hugging Face":
        model_display = settings.hf_model
        if not settings.hf_token:
            st.warning("HF_TOKEN not found in .env. Will fall back to Heuristics.")
    elif settings.active_provider == "Gemini":
        model_display = settings.gemini_model
        if not settings.gemini_api_key:
            st.warning("GEMINI_API_KEY not found in .env. Will fall back to Heuristics.")
    else:
        model_display = "Regex & Keywords"
        
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-card">
        <div class="label">LLM Status</div>
        <div class="value">{settings.active_provider}</div>
      </div>
      <div class="metric-card">
        <div class="label">Model</div>
        <div class="value" style="font-size:0.85rem;">{model_display}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**Supported formats**")
    st.markdown("JD — PDF, DOCX, TXT, JSON")
    st.markdown("Profiles — PDF, DOCX, JSON, HTML, TXT")

# ── Step 1  Upload ──────────────────────────────────────────────────────────
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.subheader("Step 1 · Upload Requirements")
col1, col2 = st.columns(2)
with col1:
    jd_file = st.file_uploader(
        "Job Description",
        type=["txt", "pdf", "docx", "json"],
        help="Upload the JD in PDF, DOCX, TXT, or JSON format.",
    )
with col2:
    profile_files = st.file_uploader(
        "Resumes / LinkedIn profiles",
        type=["txt", "pdf", "docx", "json", "html"],
        accept_multiple_files=True,
        help="Upload resume PDFs, DOCX files, or LinkedIn JSON exports.",
    )
    profile_urls_input = st.text_area(
        "Or paste LinkedIn / profile URLs (one per line)",
        placeholder="https://linkedin.com/in/johndoe\nhttps://linkedin.com/in/janedoe",
        height=80,
    )

profile_urls = [u.strip() for u in profile_urls_input.splitlines() if u.strip().startswith("http")] if profile_urls_input else []

# ── Step 2  Evaluate ────────────────────────────────────────────────────────
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.subheader("Step 2 · Evaluate")
has_profiles = bool(profile_files) or bool(profile_urls)
if st.button("Run Evaluation", type="primary", disabled=not jd_file or not has_profiles):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        jd_path = tmp_path / jd_file.name
        jd_path.write_bytes(jd_file.getvalue())
        profile_paths: list[str] = []
        if profile_files:
            for file in profile_files:
                path = tmp_path / file.name
                path.write_bytes(file.getvalue())
                profile_paths.append(str(path))
        profile_paths.extend(profile_urls)
        try:
            with st.spinner("Parsing, scoring, and writing reports …"):
                state = run_shortlisting(str(jd_path), profile_paths, output_dir, settings=settings)
            st.session_state["last_state"] = state
        except Exception as exc:
            st.error(f"**Evaluation failed.** {exc}")
            st.info(
                "If you pasted a LinkedIn URL, note that LinkedIn blocks automated scraping. "
                "Please export the profile as JSON or PDF and upload the file instead."
            )

# ── Step 3  Results ─────────────────────────────────────────────────────────
state = st.session_state.get("last_state")
if state:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.subheader("Step 3 · Ranked Shortlist")
    rows = []
    for rank, evaluation in enumerate(state["evaluations"], start=1):
        row = {
            "Rank": rank,
            "Candidate": evaluation.name,
            "Total": evaluation.weighted_total,
            "Recommendation": evaluation.recommendation.value,
            "Confidence": evaluation.confidence,
        }
        for score in evaluation.scores:
            row[score.dimension] = score.score
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    for evaluation in state["evaluations"]:
        rec_cls = f"rec-{evaluation.recommendation.value}"
        with st.expander(f"{evaluation.name}  —  {evaluation.weighted_total}/10"):
            cols = st.columns(5)
            for idx, score in enumerate(evaluation.scores):
                with cols[idx % 5]:
                    st.metric(
                        label=f"{score.dimension} ({score.weight*100:.0f}%)",
                        value=f"{score.score}/10",
                    )
            st.markdown("---")
            for score in evaluation.scores:
                st.markdown(f"**{score.dimension}** — {score.justification}")
                if score.evidence:
                    st.caption("Evidence: " + ", ".join(score.evidence))
            st.info(evaluation.overall_justification)

    # ── Human override ──────────────────────────────────────────────────────
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.subheader("Step 4 · Human Override")
    ov_col1, ov_col2, ov_col3 = st.columns([2, 2, 1])
    with ov_col1:
        candidate_id = st.selectbox("Candidate", [e.candidate_id for e in state["evaluations"]])
    with ov_col2:
        dimension = st.selectbox(
            "Dimension",
            ["Overall", "Skills Match", "Experience Relevance", "Education & Certs", "Project / Portfolio", "Communication Quality"],
        )
    with ov_col3:
        new_score = st.slider("New score", 0.0, 10.0, 7.0, 0.5)
    reason = st.text_area("Override reason (required)")
    if st.button("Log Override", disabled=not reason.strip()):
        append_override(
            OverrideRecord(
                candidate_id=candidate_id,
                dimension=None if dimension == "Overall" else dimension,
                new_score=new_score,
                reason=reason,
            )
        )
        st.success("Override logged successfully.")

    # ── Reports ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.subheader("Generated Reports")
    report_cols = st.columns(len(state["report_paths"]))
    for idx, (kind, path) in enumerate(state["report_paths"].items()):
        with report_cols[idx]:
            st.markdown(f"**{kind.upper()}**")
            st.code(path, language=None)

# ── Audit trail ─────────────────────────────────────────────────────────────
overrides = read_overrides()
if overrides:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.subheader("Override Audit Trail")
    st.dataframe(pd.DataFrame(overrides), use_container_width=True, hide_index=True)
