# output/jsonl_writer.py
from __future__ import annotations

import json
from pathlib import Path

from core.config import VICConfig, Session
from core.project import ProjectSummary


def write_jsonl(sessions: list[Session],
                project: ProjectSummary,
                cfg: VICConfig) -> Path:
    """Write archive.jsonl — one entry per session plus a project header."""

    output_path = cfg.output_path / "archive.jsonl"

    with open(output_path, "w", encoding="utf-8") as f:
        # First line: project metadata header
        header = {
            "type": "project_header",
            "name": project.name,
            "date_range": project.date_range,
            "total_sessions": project.total_sessions,
            "total_words": project.total_words,
            "providers": project.providers,
            "top_topics": project.top_topics,
            "executive_summary": project.executive_summary,
            "all_decisions": project.all_decisions,
            "all_bugs": project.all_bugs,
            "all_fixes": project.all_fixes,
            "all_open_questions": project.all_open_questions,
        }
        f.write(json.dumps(header, ensure_ascii=False) + "\n")

        # One line per session
        for session in sessions:
            entry = {
                "type": "session",
                **session.to_dict(),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return output_path
