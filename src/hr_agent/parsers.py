from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from docx import Document

from .security import sanitize_input


def read_text_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".json":
        return linkedin_json_to_text(json.loads(path.read_text(encoding="utf-8")))
    if suffix in {".html", ".htm"}:
        return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").get_text("\n")
    return path.read_text(encoding="utf-8")


def read_pdf(path: Path) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())


def linkedin_json_to_text(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(f"{prefix} {key}".strip(), child)
        elif isinstance(value, list):
            for child in value:
                walk(prefix, child)
        elif value not in (None, ""):
            lines.append(f"{prefix}: {value}")

    walk("", data)
    return "\n".join(lines)


def candidate_id_from_path(path: Path) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", path.stem).strip("-").lower()


def load_jd(path: Path) -> str:
    return sanitize_input(read_text_file(path))


def load_profiles(paths: list[Path | str]) -> list[dict[str, str]]:
    import urllib.parse
    profiles = []
    for path in paths:
        if isinstance(path, str) and path.startswith("http"):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(path, headers=headers, timeout=10)
                response.raise_for_status()
                text = BeautifulSoup(response.text, "html.parser").get_text("\n")
                parsed = urllib.parse.urlparse(path)
                parts = [p for p in parsed.path.split('/') if p]
                base_id = parts[-1] if parts else "url"
            except Exception as e:
                text = f"Failed to fetch profile from {path}. Error: {str(e)}\nPlease use manual upload for this candidate."
                base_id = "failed_url"
            
            c_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_id).strip("-").lower()
            profiles.append({
                "candidate_id": f"url_{c_id}",
                "source_file": path,
                "text": sanitize_input(text),
            })
        else:
            profiles.append(
                {
                    "candidate_id": candidate_id_from_path(path),
                    "source_file": str(path),
                    "text": sanitize_input(read_text_file(path)),
                }
            )
    return profiles

