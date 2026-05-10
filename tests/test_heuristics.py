from src.hr_agent.heuristics import parse_jd_heuristic, parse_profile_heuristic, score_heuristic


def test_heuristic_scoring_returns_mandatory_dimensions():
    jd = parse_jd_heuristic("Role: Senior AI Engineer\n5+ years Python SQL LangGraph RAG HR analytics")
    profile = parse_profile_heuristic(
        "candidate",
        "Isha Raman\nSenior AI Engineer\n6 years Python SQL LangGraph RAG HR analytics Streamlit\n"
        "Bachelor's degree in Computer Science\nAWS certified\nBuilt project with LangGraph and RAG.",
    )
    evaluation = score_heuristic(jd, profile)
    assert len(evaluation.scores) == 5
    assert {score.dimension for score in evaluation.scores} == {
        "Skills Match",
        "Experience Relevance",
        "Education & Certs",
        "Project / Portfolio",
        "Communication Quality",
    }
    assert 0 <= evaluation.weighted_total <= 10

