from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)

from .models import CandidateEvaluation, CandidateProfile, RequirementSet


# ── Colour palette ──────────────────────────────────────────────────────────
NAVY    = colors.HexColor("#1a1f36")
BLUE    = colors.HexColor("#2563eb")
BLUE_LT = colors.HexColor("#eff6ff")
GREEN   = colors.HexColor("#0f7b3f")
GREEN_LT = colors.HexColor("#ecfdf5")
AMBER   = colors.HexColor("#92600a")
AMBER_LT = colors.HexColor("#fffbeb")
RED     = colors.HexColor("#b42318")
RED_LT  = colors.HexColor("#fef2f2")
GREY_50 = colors.HexColor("#f9fafb")
GREY_200 = colors.HexColor("#e5e7eb")
GREY_500 = colors.HexColor("#6b7280")
WHITE   = colors.HexColor("#ffffff")

REC_COLOUR = {"hire": GREEN, "hold": AMBER, "no_hire": RED}
REC_BG     = {"hire": GREEN_LT, "hold": AMBER_LT, "no_hire": RED_LT}


# ── Styles ──────────────────────────────────────────────────────────────────
def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", parent=base["Title"],
            fontSize=20, leading=24, textColor=NAVY, spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"],
            fontSize=10, leading=13, textColor=GREY_500, spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "Section", parent=base["Heading2"],
            fontSize=12, leading=15, textColor=BLUE, spaceAfter=6,
            spaceBefore=16, fontName="Helvetica-Bold",
            borderWidth=0, borderPadding=0,
        ),
        "subsection": ParagraphStyle(
            "Subsection", parent=base["Heading3"],
            fontSize=10.5, leading=14, textColor=NAVY, spaceAfter=4,
            spaceBefore=10, fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=9, leading=12.5, textColor=NAVY, spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["Normal"],
            fontSize=7.5, leading=10, textColor=GREY_500,
        ),
        "evidence": ParagraphStyle(
            "Evidence", parent=base["Normal"],
            fontSize=7.5, leading=10, textColor=GREY_500,
            fontName="Helvetica-Oblique", leftIndent=8,
        ),
        "cell": ParagraphStyle(
            "Cell", parent=base["Normal"],
            fontSize=8, leading=11, textColor=NAVY,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold", parent=base["Normal"],
            fontSize=8, leading=11, textColor=NAVY, fontName="Helvetica-Bold",
        ),
        "cell_small": ParagraphStyle(
            "CellSmall", parent=base["Normal"],
            fontSize=7.5, leading=10, textColor=GREY_500,
        ),
        "cell_center": ParagraphStyle(
            "CellCenter", parent=base["Normal"],
            fontSize=8, leading=11, textColor=NAVY, alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["Normal"],
            fontSize=7, leading=9, textColor=GREY_500, alignment=TA_CENTER,
        ),
    }


# ── Table helpers ───────────────────────────────────────────────────────────
def _rec_badge(rec: str, styles: dict) -> Paragraph:
    colour = REC_COLOUR.get(rec, GREY_500)
    label = rec.replace("_", " ").upper()
    return Paragraph(
        f'<font color="{colour.hexval()}">{label}</font>',
        styles["cell_bold"],
    )


def _score_colour(score: float) -> colors.HexColor:
    if score >= 7:
        return GREEN
    if score >= 4:
        return AMBER
    return RED


# ── Public API ──────────────────────────────────────────────────────────────
def write_reports(
    requirements: RequirementSet,
    profiles: list[CandidateProfile],
    evaluations: list[CandidateEvaluation],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles_by_id = {p.candidate_id: p for p in profiles}

    # ── JSON ────────────────────────────────────────────────────────────────
    payload = {
        "requirements": requirements.model_dump(),
        "ranked_candidates": [
            {
                **ev.model_dump(),
                "weighted_total": ev.weighted_total,
                "profile": (
                    profiles_by_id[ev.candidate_id].model_dump(exclude={"email", "phone"})
                    if ev.candidate_id in profiles_by_id
                    else {}
                ),
            }
            for ev in evaluations
        ],
    }
    json_path = output_dir / "shortlist_report.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, default=str),
        encoding="utf-8",
    )

    # ── HTML ────────────────────────────────────────────────────────────────
    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).resolve().parents[2] / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("shortlist_report.html.j2")
    html_path = output_dir / "shortlist_report.html"
    html_path.write_text(template.render(**payload), encoding="utf-8")

    # ── PDF (ReportLab) ─────────────────────────────────────────────────────
    pdf_path = output_dir / "shortlist_report.pdf"
    _write_pdf(requirements, evaluations, pdf_path)

    return {"json": json_path, "html": html_path, "pdf": pdf_path}


# ═══════════════════════════════════════════════════════════════════════════
# ReportLab PDF generation
# ═══════════════════════════════════════════════════════════════════════════

def _write_pdf(
    req: RequirementSet,
    evaluations: list[CandidateEvaluation],
    pdf_path: Path,
) -> None:
    styles = _build_styles()
    page_w, page_h = A4
    margin = 18 * mm

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=20 * mm,
        title="Shortlist Report",
        author="Explainable HR Shortlisting Agent",
    )
    story: list = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("Explainable HR Shortlist Report", styles["title"]))
    story.append(Paragraph(
        f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}  ·  "
        "Human review is required before any hiring decision",
        styles["subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=GREY_200, spaceAfter=10))

    # ── Job Requirements ────────────────────────────────────────────────────
    story.append(Paragraph("Job Requirements", styles["section"]))
    req_data = [
        ["Role", req.role_title],
        ["Domain", req.domain or "—"],
        ["Seniority", req.seniority or "—"],
        ["Must-have skills", ", ".join(req.must_have_skills[:10]) or "—"],
        ["Nice-to-have", ", ".join(req.nice_to_have_skills[:6]) or "—"],
        ["Min. experience", f"{req.min_years_experience:g} years"],
        ["Education", ", ".join(req.education[:3]) or "—"],
        ["Certifications", ", ".join(req.certifications[:3]) or "—"],
    ]
    req_table_data = [
        [Paragraph(r[0], styles["cell_bold"]), Paragraph(r[1], styles["cell"])]
        for r in req_data
    ]
    avail_w = page_w - 2 * margin
    req_table = Table(req_table_data, colWidths=[avail_w * 0.22, avail_w * 0.78])
    req_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), GREY_50),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, GREY_200),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(req_table)
    story.append(Spacer(1, 14))

    # ── Summary table ───────────────────────────────────────────────────────
    story.append(Paragraph("Ranked Candidates", styles["section"]))
    summary_header = [
        Paragraph("#", styles["cell_bold"]),
        Paragraph("Candidate", styles["cell_bold"]),
        Paragraph("Total", styles["cell_bold"]),
        Paragraph("Rec.", styles["cell_bold"]),
        Paragraph("Skills", styles["cell_bold"]),
        Paragraph("Exp.", styles["cell_bold"]),
        Paragraph("Edu.", styles["cell_bold"]),
        Paragraph("Projects", styles["cell_bold"]),
        Paragraph("Comm.", styles["cell_bold"]),
    ]
    summary_rows = [summary_header]
    for rank, ev in enumerate(evaluations, 1):
        scores_map = {s.dimension: s.score for s in ev.scores}
        row = [
            Paragraph(str(rank), styles["cell_center"]),
            Paragraph(ev.name, styles["cell_bold"]),
            Paragraph(f"<b>{ev.weighted_total:.1f}</b>/10", styles["cell"]),
            _rec_badge(ev.recommendation.value, styles),
        ]
        for dim in ["Skills Match", "Experience Relevance", "Education & Certs",
                     "Project / Portfolio", "Communication Quality"]:
            sc = scores_map.get(dim, 0)
            clr = _score_colour(sc)
            row.append(Paragraph(f'<font color="{clr.hexval()}">{sc}/10</font>', styles["cell_center"]))
        summary_rows.append(row)

    col_pcts = [0.04, 0.20, 0.08, 0.09, 0.11, 0.11, 0.10, 0.14, 0.13]
    summary_table = Table(
        summary_rows,
        colWidths=[avail_w * p for p in col_pcts],
        repeatRows=1,
    )
    table_style_cmds = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.4, GREY_200),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    # Alternating row backgrounds
    for i in range(1, len(summary_rows)):
        bg = GREY_50 if i % 2 == 0 else WHITE
        table_style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    summary_table.setStyle(TableStyle(table_style_cmds))
    story.append(summary_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_200, spaceAfter=4))

    # ── Candidate detail cards ──────────────────────────────────────────────
    for rank, ev in enumerate(evaluations, 1):
        card_elements = []
        card_elements.append(Spacer(1, 8))
        card_elements.append(Paragraph(
            f"{rank}. {ev.name}", styles["subsection"],
        ))

        rec_clr = REC_COLOUR.get(ev.recommendation.value, GREY_500)
        rec_label = ev.recommendation.value.replace("_", " ").upper()
        card_elements.append(Paragraph(
            f'Total: <b>{ev.weighted_total:.1f}/10</b>  ·  '
            f'Recommendation: <font color="{rec_clr.hexval()}"><b>{rec_label}</b></font>  ·  '
            f'Confidence: {ev.confidence:.0%}',
            styles["body"],
        ))
        card_elements.append(Spacer(1, 6))

        # Dimension scores table
        dim_header = [
            Paragraph("Dimension", styles["cell_bold"]),
            Paragraph("Weight", styles["cell_bold"]),
            Paragraph("Score", styles["cell_bold"]),
            Paragraph("Weighted", styles["cell_bold"]),
            Paragraph("Justification", styles["cell_bold"]),
        ]
        dim_rows = [dim_header]
        for sc in ev.scores:
            sc_clr = _score_colour(sc.score)
            just_text = sc.justification
            if sc.evidence:
                just_text += f'<br/><font size="7" color="{GREY_500.hexval()}"><i>Evidence: {", ".join(sc.evidence[:4])}</i></font>'
            dim_rows.append([
                Paragraph(sc.dimension, styles["cell"]),
                Paragraph(f"{sc.weight * 100:.0f}%", styles["cell_center"]),
                Paragraph(f'<font color="{sc_clr.hexval()}"><b>{sc.score}/10</b></font>', styles["cell_center"]),
                Paragraph(f"{sc.weighted_score:.2f}", styles["cell_center"]),
                Paragraph(just_text, styles["cell"]),
            ])

        dim_widths = [avail_w * p for p in [0.17, 0.08, 0.08, 0.09, 0.58]]
        dim_table = Table(dim_rows, colWidths=dim_widths, repeatRows=1)
        dim_style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("GRID", (0, 0), (-1, -1), 0.3, GREY_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(dim_rows)):
            bg = GREY_50 if i % 2 == 0 else WHITE
            dim_style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
        dim_table.setStyle(TableStyle(dim_style_cmds))
        card_elements.append(dim_table)
        card_elements.append(Spacer(1, 4))

        # Strengths
        if ev.strengths:
            card_elements.append(Paragraph(
                f'<font color="{GREEN.hexval()}"><b>Strengths:</b></font> '
                + " · ".join(ev.strengths[:5]),
                styles["body"],
            ))

        # Gaps
        if ev.gaps:
            card_elements.append(Paragraph(
                f'<font color="{RED.hexval()}"><b>Gaps:</b></font> '
                + " · ".join(ev.gaps[:5]),
                styles["body"],
            ))

        # Overall
        card_elements.append(Spacer(1, 3))
        card_elements.append(Paragraph(ev.overall_justification, styles["body"]))
        card_elements.append(HRFlowable(
            width="100%", thickness=0.5, color=GREY_200,
            spaceBefore=8, spaceAfter=4,
        ))

        story.append(KeepTogether(card_elements))

    # ── Footer ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Explainable HR Shortlisting Agent  ·  This report is for decision support only  ·  "
        "Protected attributes must never be used in hiring decisions",
        styles["footer"],
    ))

    doc.build(story)
