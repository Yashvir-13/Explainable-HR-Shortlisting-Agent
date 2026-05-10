# Explainable HR Shortlisting Agent - Presentation Deck

## Slide 1 - Problem
HR teams screen hundreds of applications per role, creating fatigue, inconsistent evaluation, and hidden bias risk.

## Slide 2 - Solution
The prototype turns a JD plus resumes or LinkedIn JSON into a ranked shortlist with transparent dimension-level scoring.

## Slide 3 - Agent Flow
JD Parser -> Profile Parser -> Score Agent -> Ranker -> HTML/JSON Report -> HR Override Log.

## Slide 4 - Architecture
LangGraph orchestrates deterministic nodes. Groq supplies structured LLM reasoning when configured, with heuristic fallback for offline demos.

## Slide 5 - Scoring Rubric
The mandatory five dimensions are Skills Match, Experience Relevance, Education & Certs, Project / Portfolio, and Communication Quality.

## Slide 6 - Security
The design mitigates prompt injection, PII leakage, API key exposure, hallucination, and unauthorized access through sanitization, masking, schemas, `.env`, and review gates.

## Slide 7 - Human-in-the-Loop
HR can override a dimension or recommendation with a required reason, producing an append-only audit log.

## Slide 8 - Demo Scenario
The sample JD is evaluated against five candidates: one strong AI/HR fit, two partial fits, one junior adjacent fit, and one low-fit frontend profile.

## Slide 9 - Results
The generated report ranks candidates by weighted total and exposes one-line justification plus evidence for every score.

## Slide 10 - Learnings
Structured outputs, deterministic fallback logic, and traceable overrides make the prototype easier to debug, audit, and present.

