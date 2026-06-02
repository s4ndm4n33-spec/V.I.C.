# output/pdf_writer.py
from __future__ import annotations

from pathlib import Path
from core.config import VICConfig, Session
from core.project import ProjectSummary


def write_pdf(sessions: list[Session],
              project: ProjectSummary,
              cfg: VICConfig) -> Path:
    """Write PDF report. Uses reportlab if available, falls back to plain text."""
    output_path = cfg.output_path / "archive.pdf"

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            HRFlowable, PageBreak, Table, TableStyle,
        )
        _write_pdf_reportlab(output_path, sessions, project, cfg)
    except ImportError:
        # Fallback to plain text if reportlab not installed
        _write_pdf_fallback(output_path, sessions, project, cfg)

    return output_path


def _write_pdf_reportlab(output_path: Path,
                         sessions: list[Session],
                         project: ProjectSummary,
                         cfg: VICConfig) -> None:
    """Full PDF using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        HRFlowable, PageBreak,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "VICTitle",
        parent=styles["Title"],
        fontSize=24,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )
    h1_style = ParagraphStyle(
        "VICH1",
        parent=styles["Heading1"],
        fontSize=16,
        spaceBefore=16,
        spaceAfter=6,
        textColor=colors.HexColor("#16213e"),
        borderPad=4,
    )
    h2_style = ParagraphStyle(
        "VICH2",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=12,
        spaceAfter=4,
        textColor=colors.HexColor("#0f3460"),
    )
    body_style = ParagraphStyle(
        "VICBody",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        leading=14,
    )
    bullet_style = ParagraphStyle(
        "VICBullet",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=3,
        leftIndent=16,
        bulletIndent=8,
        leading=14,
    )
    meta_style = ParagraphStyle(
        "VICMeta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=2,
    )

    story = []

    # ── Cover ────────────────────────────────────────────────────────
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("V.I.C.", title_style))
    story.append(Paragraph("Value In Conversation", ParagraphStyle(
        "sub", parent=styles["Normal"], fontSize=14,
        textColor=colors.grey, spaceAfter=4)))
    story.append(Paragraph(f"<b>{_esc(project.name)}</b>", ParagraphStyle(
        "projname", parent=styles["Normal"], fontSize=18, spaceAfter=8)))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Date range: {project.date_range}", meta_style))
    story.append(Paragraph(
        f"Sessions: {project.total_sessions} | "
        f"Words: {project.total_words:,} | "
        f"Providers: {', '.join(project.providers)}", meta_style))
    story.append(Spacer(1, 1*cm))

    # ── Executive Summary ────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", h1_style))
    story.append(Paragraph(_esc(project.executive_summary), body_style))
    story.append(Spacer(1, 0.5*cm))

    # ── Top Topics ───────────────────────────────────────────────────
    if project.top_topics:
        story.append(Paragraph("Key Topics", h1_style))
        story.append(Paragraph(
            " · ".join(f"<b>{_esc(t)}</b>" for t in project.top_topics),
            body_style))
        story.append(Spacer(1, 0.5*cm))

    # ── Key Decisions ────────────────────────────────────────────────
    if project.all_decisions:
        story.append(Paragraph("Key Decisions", h1_style))
        for d in project.all_decisions[:30]:
            story.append(Paragraph(f"• {_esc(d)}", bullet_style))
        story.append(Spacer(1, 0.5*cm))

    # ── Issues & Resolutions ─────────────────────────────────────────
    if project.all_bugs:
        story.append(Paragraph("Issues Encountered", h1_style))
        for b in project.all_bugs[:30]:
            story.append(Paragraph(f"• {_esc(b)}", bullet_style))
        story.append(Spacer(1, 0.3*cm))

    if project.all_fixes:
        story.append(Paragraph("Resolutions Applied", h1_style))
        for f in project.all_fixes[:30]:
            story.append(Paragraph(f"• {_esc(f)}", bullet_style))
        story.append(Spacer(1, 0.5*cm))

    # ── Open Questions ───────────────────────────────────────────────
    if project.all_open_questions:
        story.append(Paragraph("Open Questions", h1_style))
        for q in project.all_open_questions[:20]:
            story.append(Paragraph(f"• {_esc(q)}", bullet_style))
        story.append(Spacer(1, 0.5*cm))

    # ── Session Cliffnotes ───────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Session Cliffnotes", h1_style))
    story.append(Paragraph(
        f"One paragraph per session, chronological. "
        f"{project.total_sessions} total sessions.", meta_style))
    story.append(Spacer(1, 0.3*cm))

    for i, session in enumerate(sessions):
        story.append(Paragraph(
            f"<b>{i+1}. {_esc(session.title)}</b> "
            f"<font color='grey' size='8'>[{session.provider} · {session.date}]</font>",
            h2_style))
        if session.cliffnotes:
            story.append(Paragraph(_esc(session.cliffnotes), body_style))
        else:
            story.append(Paragraph(
                f"Session with {session.word_count} words. "
                f"Topics: {', '.join(session.key_topics[:5]) or 'general'}.",
                body_style))
        story.append(Spacer(1, 0.2*cm))

    doc.build(story)


def _write_pdf_fallback(output_path: Path,
                        sessions: list[Session],
                        project: ProjectSummary,
                        cfg: VICConfig) -> None:
    """Plain text fallback when reportlab is not installed.
    Saves as .txt with PDF extension note."""
    txt_path = output_path.with_suffix(".txt")
    lines = []

    lines.append("V.I.C. — VALUE IN CONVERSATION")
    lines.append("=" * 60)
    lines.append(f"Project: {project.name}")
    lines.append(f"Date range: {project.date_range}")
    lines.append(f"Sessions: {project.total_sessions} | Words: {project.total_words:,}")
    lines.append(f"Providers: {', '.join(project.providers)}")
    lines.append("")
    lines.append("NOTE: reportlab not installed. Install with:")
    lines.append("  pip install reportlab")
    lines.append("Then re-run for PDF output. This is a plain text fallback.")
    lines.append("=" * 60)
    lines.append("")

    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 40)
    lines.append(project.executive_summary)
    lines.append("")

    if project.top_topics:
        lines.append("KEY TOPICS")
        lines.append("-" * 40)
        lines.append(", ".join(project.top_topics))
        lines.append("")

    if project.all_decisions:
        lines.append("KEY DECISIONS")
        lines.append("-" * 40)
        for d in project.all_decisions[:30]:
            lines.append(f"  • {d}")
        lines.append("")

    if project.all_bugs:
        lines.append("ISSUES ENCOUNTERED")
        lines.append("-" * 40)
        for b in project.all_bugs[:30]:
            lines.append(f"  • {b}")
        lines.append("")

    if project.all_fixes:
        lines.append("RESOLUTIONS APPLIED")
        lines.append("-" * 40)
        for f in project.all_fixes[:30]:
            lines.append(f"  • {f}")
        lines.append("")

    if project.all_open_questions:
        lines.append("OPEN QUESTIONS")
        lines.append("-" * 40)
        for q in project.all_open_questions[:20]:
            lines.append(f"  • {q}")
        lines.append("")

    lines.append("SESSION CLIFFNOTES")
    lines.append("=" * 60)
    for i, session in enumerate(sessions):
        lines.append(f"\n{i+1}. {session.title}")
        lines.append(f"   [{session.provider} · {session.date}]")
        lines.append(f"   {session.cliffnotes or 'No notes extracted.'}")

    txt_path.write_text("\n".join(lines), encoding="utf-8")
    # Copy to PDF path so pipeline result is consistent
    import shutil
    shutil.copy(txt_path, output_path)


def _esc(text: str) -> str:
    """Escape XML special chars for reportlab Paragraph."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
