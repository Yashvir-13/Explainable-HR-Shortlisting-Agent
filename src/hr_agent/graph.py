from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .config import Settings, load_settings
from .heuristics import parse_jd_heuristic, parse_profile_heuristic, score_heuristic
from .llm import get_llm_client
from .models import CandidateEvaluation, CandidateProfile, RequirementSet
from .parsers import load_jd, load_profiles
from .prompts import JD_SYSTEM_PROMPT, PROFILE_SYSTEM_PROMPT, SCORING_SYSTEM_PROMPT
from .report import write_reports


class AgentState(TypedDict, total=False):
    jd_path: str
    profile_paths: list[str]
    jd_text: str
    profile_inputs: list[dict[str, str]]
    requirements: RequirementSet
    profiles: list[CandidateProfile]
    evaluations: list[CandidateEvaluation]
    output_dir: str
    report_paths: dict[str, str]


def build_graph(settings: Settings | None = None):
    settings = settings or load_settings()
    llm = get_llm_client(settings)

    def load_inputs(state: AgentState) -> AgentState:
        jd_path = Path(state["jd_path"])
        profile_paths = [
            path if isinstance(path, str) and path.startswith("http") else Path(path) 
            for path in state["profile_paths"]
        ]
        return {
            **state,
            "jd_text": load_jd(jd_path),
            "profile_inputs": load_profiles(profile_paths),
        }

    def parse_jd(state: AgentState) -> AgentState:
        parsed = llm.complete_json(JD_SYSTEM_PROMPT, {"job_description": state["jd_text"]}, RequirementSet) if llm and llm.enabled else None
        return {**state, "requirements": parsed or parse_jd_heuristic(state["jd_text"])}

    def parse_profiles(state: AgentState) -> AgentState:
        profiles: list[CandidateProfile] = []
        for item in state["profile_inputs"]:
            payload = {"candidate_id": item["candidate_id"], "profile_text": item["text"]}
            parsed = llm.complete_json(PROFILE_SYSTEM_PROMPT, payload, CandidateProfile) if llm and llm.enabled else None
            profile = parsed or parse_profile_heuristic(item["candidate_id"], item["text"], item["source_file"])
            profile.source_file = item["source_file"]
            profiles.append(profile)
        return {**state, "profiles": profiles}

    def score_profiles(state: AgentState) -> AgentState:
        evaluations: list[CandidateEvaluation] = []
        for profile in state["profiles"]:
            payload = {
                "requirements": state["requirements"].model_dump(),
                "candidate_profile": profile.model_dump(exclude={"email", "phone"}),
            }
            parsed = llm.complete_json(SCORING_SYSTEM_PROMPT, payload, CandidateEvaluation) if llm and llm.enabled else None
            evaluations.append(parsed or score_heuristic(state["requirements"], profile))
        ranked = sorted(evaluations, key=lambda item: item.weighted_total, reverse=True)
        return {**state, "evaluations": ranked}

    def generate_reports(state: AgentState) -> AgentState:
        output_dir = Path(state.get("output_dir") or settings.output_dir)
        report_paths = write_reports(state["requirements"], state["profiles"], state["evaluations"], output_dir)
        return {**state, "report_paths": {key: str(path) for key, path in report_paths.items()}}

    workflow = StateGraph(AgentState)
    workflow.add_node("load_inputs", load_inputs)
    workflow.add_node("parse_jd", parse_jd)
    workflow.add_node("parse_profiles", parse_profiles)
    workflow.add_node("score_profiles", score_profiles)
    workflow.add_node("generate_reports", generate_reports)
    workflow.set_entry_point("load_inputs")
    workflow.add_edge("load_inputs", "parse_jd")
    workflow.add_edge("parse_jd", "parse_profiles")
    workflow.add_edge("parse_profiles", "score_profiles")
    workflow.add_edge("score_profiles", "generate_reports")
    workflow.add_edge("generate_reports", END)
    return workflow.compile()


def run_shortlisting(jd_path: str, profile_paths: list[str], output_dir: str = "outputs", settings: Settings | None = None) -> AgentState:
    graph = build_graph(settings)
    return graph.invoke({"jd_path": jd_path, "profile_paths": profile_paths, "output_dir": output_dir})

