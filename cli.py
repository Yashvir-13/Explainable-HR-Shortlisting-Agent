from __future__ import annotations

import argparse
from pathlib import Path

from src.hr_agent.graph import run_shortlisting
from src.hr_agent.models import OverrideRecord, Recommendation
from src.hr_agent.overrides import append_override


def main() -> None:
    parser = argparse.ArgumentParser(description="Explainable HR shortlisting agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run JD/profile scoring")
    run_parser.add_argument("--jd", required=True, help="Path to JD txt/pdf/docx")
    run_parser.add_argument("--profiles", nargs="+", required=True, help="Resume or LinkedIn JSON files")
    run_parser.add_argument("--out", default="outputs", help="Output directory")

    override_parser = subparsers.add_parser("override", help="Log a human override")
    override_parser.add_argument("--candidate-id", required=True)
    override_parser.add_argument("--reason", required=True)
    override_parser.add_argument("--reviewer", default="hr_reviewer")
    override_parser.add_argument("--dimension")
    override_parser.add_argument("--old-score", type=float)
    override_parser.add_argument("--new-score", type=float)
    override_parser.add_argument("--old-recommendation", choices=[item.value for item in Recommendation])
    override_parser.add_argument("--new-recommendation", choices=[item.value for item in Recommendation])
    override_parser.add_argument("--log", default="outputs/override_log.jsonl")

    args = parser.parse_args()
    if args.command == "run":
        state = run_shortlisting(args.jd, args.profiles, args.out)
        print("Shortlist complete")
        for key, path in state["report_paths"].items():
            print(f"{key}: {path}")
        for index, evaluation in enumerate(state["evaluations"], start=1):
            print(f"{index}. {evaluation.name} - {evaluation.weighted_total}/10 - {evaluation.recommendation.value}")
    elif args.command == "override":
        record = OverrideRecord(
            candidate_id=args.candidate_id,
            dimension=args.dimension,
            old_score=args.old_score,
            new_score=args.new_score,
            old_recommendation=args.old_recommendation,
            new_recommendation=args.new_recommendation,
            reason=args.reason,
            reviewer=args.reviewer,
        )
        path = append_override(record, Path(args.log))
        print(f"Override logged to {path}")


if __name__ == "__main__":
    main()

