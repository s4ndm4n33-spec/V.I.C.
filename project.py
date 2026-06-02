# core/project.py
from __future__ import annotations

from collections import Counter
from core.config import VICConfig, Session


class ProjectSummary:
    """Cross-session project analysis."""

    def __init__(self) -> None:
        self.name: str = ""
        self.date_range: str = ""
        self.total_sessions: int = 0
        self.total_words: int = 0
        self.providers: list[str] = []
        self.executive_summary: str = ""
        self.all_decisions: list[str] = []
        self.all_bugs: list[str] = []
        self.all_fixes: list[str] = []
        self.all_open_questions: list[str] = []
        self.top_topics: list[str] = []
        self.architecture_notes: list[str] = []


def build_project_summary(sessions: list[Session], cfg: VICConfig) -> ProjectSummary:
    """Build a cross-session project summary."""
    project = ProjectSummary()

    if not sessions:
        return project

    # Basic stats
    project.total_sessions = len(sessions)
    project.total_words = sum(s.word_count for s in sessions)

    # Date range
    dates = [s.date for s in sessions if s.date != "0000-00-00"]
    if dates:
        project.date_range = f"{min(dates)} to {max(dates)}"

    # Providers
    providers = list(set(s.provider for s in sessions))
    project.providers = sorted(providers)

    # Project name
    if cfg.project_name:
        project.name = cfg.project_name
    else:
        project.name = _detect_project_name(sessions)

    # Aggregate extractions (deduplicated)
    seen_decisions = set()
    seen_bugs = set()
    seen_fixes = set()
    seen_questions = set()

    for session in sessions:
        for d in session.decisions:
            key = d.lower()[:40]
            if key not in seen_decisions:
                seen_decisions.add(key)
                project.all_decisions.append(d)

        for b in session.bugs:
            key = b.lower()[:40]
            if key not in seen_bugs:
                seen_bugs.add(key)
                project.all_bugs.append(b)

        for f in session.fixes:
            key = f.lower()[:40]
            if key not in seen_fixes:
                seen_fixes.add(key)
                project.all_fixes.append(f)

        for q in session.open_questions:
            key = q.lower()[:40]
            if key not in seen_questions:
                seen_questions.add(key)
                project.all_open_questions.append(q)

    # Top topics across all sessions
    topic_counter: Counter = Counter()
    for session in sessions:
        for topic in session.key_topics:
            topic_counter[topic] += 1
    project.top_topics = [t for t, _ in topic_counter.most_common(15)]

    # Executive summary
    project.executive_summary = _build_executive_summary(project, sessions)

    return project


def _detect_project_name(sessions: list[Session]) -> str:
    """Try to auto-detect project name from conversation content."""
    # Look for common project name patterns in titles and content
    from collections import Counter
    import re

    name_candidates: Counter = Counter()

    for session in sessions:
        # Check title for capitalized project-like names
        words = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\b", session.title)
        for w in words:
            if len(w) > 3 and w not in ("The", "This", "That", "With", "From"):
                name_candidates[w] += 2  # title words weighted more

        # Check first user message
        if session.raw_turns:
            first = session.raw_turns[0].get("content", "")[:200]
            words = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\b", first)
            for w in words:
                if len(w) > 4:
                    name_candidates[w] += 1

    if name_candidates:
        return name_candidates.most_common(1)[0][0]

    return "AI Project Archive"


def _build_executive_summary(project: ProjectSummary, sessions: list[Session]) -> str:
    """Build the executive summary paragraph."""
    parts = []

    parts.append(
        f"{project.name} spans {project.total_sessions} conversation sessions "
        f"({project.date_range}) across {', '.join(project.providers)} "
        f"totaling approximately {project.total_words:,} words."
    )

    if project.top_topics:
        parts.append(
            f"Primary topics include: {', '.join(project.top_topics[:8])}."
        )

    if project.all_decisions:
        parts.append(
            f"{len(project.all_decisions)} key decisions were made throughout the project."
        )

    if project.all_bugs:
        parts.append(
            f"{len(project.all_bugs)} issues were identified, "
            f"with {len(project.all_fixes)} documented resolutions."
        )

    if project.all_open_questions:
        parts.append(
            f"{len(project.all_open_questions)} questions remain open."
        )

    return " ".join(parts)
