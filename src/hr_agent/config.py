from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


class Settings(BaseModel):
    active_provider: str = "Groq"  # "Groq", "Hugging Face", "Gemini", or "Heuristics"
    
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    
    hf_token: str | None = None
    hf_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    
    langsmith_tracing: bool = False
    langsmith_project: str = "explainable-hr-shortlisting-agent"
    app_access_token: str | None = None
    output_dir: Path = Path("outputs")


def load_settings() -> Settings:
    load_dotenv(override=True)
    return Settings(
        active_provider=os.getenv("ACTIVE_PROVIDER", "Groq"),
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        hf_token=os.getenv("HF_TOKEN") or None,
        hf_model=os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct"),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        langsmith_tracing=os.getenv("LANGSMITH_TRACING", "false").lower() == "true",
        langsmith_project=os.getenv("LANGSMITH_PROJECT", "explainable-hr-shortlisting-agent"),
        app_access_token=os.getenv("APP_ACCESS_TOKEN") or None,
    )

