from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator


class Recommendation(str, Enum):
    hire = "hire"
    hold = "hold"
    no_hire = "no_hire"


class RequirementSet(BaseModel):
    role_title: str = "Unknown role"
    domain: str = ""
    seniority: str = ""
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    min_years_experience: float = 0
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)

    @field_validator("must_have_skills", "nice_to_have_skills", mode="before")
    @classmethod
    def normalize_skill_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class CandidateProfile(BaseModel):
    candidate_id: str
    name: str = "Unknown candidate"
    email: str | None = None
    phone: str | None = None
    current_title: str = ""
    location: str = ""
    total_years_experience: float = 0
    skills: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    raw_text_excerpt: str = ""
    source_file: str = ""


class DimensionScore(BaseModel):
    dimension: str
    weight: float
    score: float = Field(ge=0, le=10)
    justification: str = Field(min_length=1, max_length=350)
    evidence: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def weighted_score(self) -> float:
        return round(self.score * self.weight, 2)


class CandidateEvaluation(BaseModel):
    candidate_id: str
    name: str
    recommendation: Recommendation
    scores: list[DimensionScore]
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    overall_justification: str
    confidence: float = Field(default=0.7, ge=0, le=1)

    @computed_field
    @property
    def weighted_total(self) -> float:
        return round(sum(score.weighted_score for score in self.scores), 2)


class OverrideRecord(BaseModel):
    candidate_id: str
    dimension: str | None = None
    old_score: float | None = None
    new_score: float | None = None
    old_recommendation: Recommendation | None = None
    new_recommendation: Recommendation | None = None
    reason: str
    reviewer: str = "hr_reviewer"
    created_at: datetime = Field(default_factory=datetime.utcnow)

