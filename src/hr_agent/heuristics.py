from __future__ import annotations

import re
from collections import Counter

from .models import CandidateEvaluation, CandidateProfile, DimensionScore, Recommendation, RequirementSet

SKILL_VOCAB = {
    "python", "sql", "machine learning", "ml", "deep learning", "nlp", "llm",
    "langchain", "langgraph", "rag", "streamlit", "fastapi", "docker", "aws",
    "azure", "gcp", "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow",
    "data analysis", "statistics", "api", "etl", "vector database", "chromadb",
    "prompt engineering", "hr analytics", "recruiting", "talent acquisition",
}


def normalize_terms(items: list[str]) -> set[str]:
    return {item.strip().lower() for item in items if item and item.strip()}


def extract_skills(text: str) -> list[str]:
    lower = text.lower()
    found = [skill for skill in SKILL_VOCAB if skill in lower]
    explicit = re.findall(r"(?:skills?|technologies)[:\s]+([^\n]+)", text, flags=re.I)
    for chunk in explicit:
        found.extend(part.strip().lower() for part in re.split(r"[,|;/]", chunk) if part.strip())
    return sorted(set(found))


def extract_years(text: str) -> float:
    matches = re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)", text, flags=re.I)
    return max((float(match) for match in matches), default=0.0)


def parse_jd_heuristic(text: str) -> RequirementSet:
    skills = extract_skills(text)
    role_match = re.search(r"(?:role|title|position)[:\s]+([^\n]+)", text, flags=re.I)
    domain = " ".join(re.findall(r"\b(?:HR|recruiting|analytics|AI|machine learning|data)\b", text, flags=re.I)[:3])
    education = re.findall(r"\b(?:bachelor'?s?|master'?s?|phd|degree|mba)\b[^\n,.]*", text, flags=re.I)
    certs = re.findall(r"\b(?:aws|azure|gcp|shrm|phr|sphr|certified)[^\n,.]*", text, flags=re.I)
    return RequirementSet(
        role_title=role_match.group(1).strip() if role_match else "AI HR Shortlisting Specialist",
        domain=domain or "AI recruiting",
        seniority="senior" if "senior" in text.lower() else "mid",
        must_have_skills=skills[:10],
        nice_to_have_skills=skills[10:],
        min_years_experience=extract_years(text),
        education=education[:3],
        certifications=certs[:3],
        responsibilities=[line.strip("- ") for line in text.splitlines() if len(line.strip()) > 30][:8],
    )


def parse_profile_heuristic(candidate_id: str, text: str, source_file: str = "") -> CandidateProfile:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    name = lines[0].split(":")[-1].strip() if lines else candidate_id
    education = [line for line in lines if re.search(r"bachelor|master|phd|degree|university|college", line, re.I)]
    certs = [line for line in lines if re.search(r"certified|certificate|aws|azure|gcp|shrm", line, re.I)]
    projects = [line for line in lines if re.search(r"project|portfolio|built|deployed|created|implemented", line, re.I)]
    domains = re.findall(r"\b(?:HR|recruiting|fintech|healthcare|analytics|AI|machine learning|data)\b", text, re.I)
    return CandidateProfile(
        candidate_id=candidate_id,
        name=name[:80],
        email=email_match.group(0) if email_match else None,
        current_title=next((line for line in lines if re.search(r"engineer|scientist|analyst|recruiter|manager", line, re.I)), ""),
        total_years_experience=extract_years(text),
        skills=extract_skills(text),
        domains=sorted(set(domain.lower() for domain in domains)),
        education=education[:5],
        certifications=certs[:5],
        projects=projects[:8],
        achievements=[line for line in lines if re.search(r"improved|reduced|increased|led|saved|ranked", line, re.I)][:6],
        raw_text_excerpt=text[:1200],
        source_file=source_file,
    )


def score_heuristic(jd: RequirementSet, profile: CandidateProfile) -> CandidateEvaluation:
    required = normalize_terms(jd.must_have_skills)
    skills = normalize_terms(profile.skills)
    matched = required & skills
    skill_ratio = len(matched) / max(len(required), 1)
    skill_score = min(10, round(skill_ratio * 10, 1))
    if skill_ratio >= 0.85:
        skill_label = "excellent"
    elif 0.50 <= skill_ratio <= 0.70:
        skill_label = "average"
    else:
        skill_label = "partial" if skill_ratio > 0 else "poor"

    domain_overlap = normalize_terms([jd.domain]) & normalize_terms(profile.domains)
    title_text = f"{profile.current_title} {' '.join(profile.domains)}".lower()
    exact_seniority = jd.seniority.lower() in title_text if jd.seniority else True
    exp_ratio = profile.total_years_experience / max(jd.min_years_experience, 1)
    exp_score = 10 if domain_overlap and exact_seniority and exp_ratio >= 1 else 7 if domain_overlap or exp_ratio >= 1 else 4 if exp_ratio >= 0.6 else 2

    edu_text = " ".join(profile.education + profile.certifications).lower()
    min_edu_text = " ".join(jd.education + jd.certifications).lower()
    has_edu = not min_edu_text or any(term in edu_text for term in ["bachelor", "master", "phd", "degree", "certified", "aws", "azure", "gcp"])
    extra_certs = len(profile.certifications) > len(jd.certifications)
    edu_score = 10 if has_edu and extra_certs else 7 if has_edu else 2

    relevant_projects = [p for p in profile.projects if any(skill in p.lower() for skill in required)]
    project_score = 10 if len(relevant_projects) >= 2 else 7 if relevant_projects else 5 if profile.projects else 1

    words = re.findall(r"\w+", profile.raw_text_excerpt)
    repeated = Counter(word.lower() for word in words)
    impact_terms = sum(1 for word in ["improved", "reduced", "increased", "led", "deployed", "measured"] if word in repeated)
    communication_score = 9 if len(profile.raw_text_excerpt) > 400 and impact_terms >= 2 else 7 if len(words) > 120 else 4

    scores = [
        DimensionScore(dimension="Skills Match", weight=0.30, score=skill_score, justification=f"{skill_label.title()} skills match with {len(matched)}/{len(required)} required skills evidenced.", evidence=sorted(matched)[:5]),
        DimensionScore(dimension="Experience Relevance", weight=0.25, score=exp_score, justification=f"{profile.total_years_experience:g} years shown against {jd.min_years_experience:g}+ required with {'domain overlap' if domain_overlap else 'limited domain overlap'}.", evidence=profile.domains[:4]),
        DimensionScore(dimension="Education & Certs", weight=0.15, score=edu_score, justification="Education/certification evidence meets or exceeds the stated baseline." if has_edu else "Minimum education/certification evidence is weak or missing.", evidence=(profile.education + profile.certifications)[:4]),
        DimensionScore(dimension="Project / Portfolio", weight=0.20, score=project_score, justification=f"{len(profile.projects)} project or portfolio signals found, with {len(relevant_projects)} directly tied to required skills.", evidence=profile.projects[:3]),
        DimensionScore(dimension="Communication Quality", weight=0.10, score=communication_score, justification="Profile is structured with clear impact language." if communication_score >= 7 else "Profile has limited structure or sparse achievement detail.", evidence=profile.achievements[:3]),
    ]
    provisional_total = sum(score.weighted_score for score in scores)
    recommendation = Recommendation.hire if provisional_total >= 7.5 else Recommendation.hold if provisional_total >= 5.5 else Recommendation.no_hire
    gaps = sorted(required - skills)[:6]
    return CandidateEvaluation(
        candidate_id=profile.candidate_id,
        name=profile.name,
        recommendation=recommendation,
        scores=scores,
        strengths=[f"Matches {skill}" for skill in sorted(matched)[:5]],
        gaps=[f"Missing or weak evidence for {gap}" for gap in gaps],
        risk_flags=[] if skill_ratio > 0.4 else ["Low required-skill coverage"],
        overall_justification=f"Weighted score reflects {skill_label} skill coverage, experience fit, and portfolio evidence.",
        confidence=0.65,
    )

