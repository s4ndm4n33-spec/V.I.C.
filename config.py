# core/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VICConfig:
    """Runtime configuration for V.I.C. processing pipeline."""
    input_path: Path
    output_path: Path
    project_name: str | None = None
    generate_pdf: bool = True
    generate_jsonl: bool = True
    min_length: int = 100          # skip trivially short conversations
    verbose: bool = False


@dataclass
class Session:
    """One normalized conversation session from any provider."""
    session_id: str
    provider: str                  # "gemini" | "chatgpt" | "claude" | "unknown"
    date: str                      # ISO format string
    title: str
    raw_turns: list[dict]          # [{"role": "user"|"assistant", "content": str}]

    # Extracted fields (populated by extractor)
    summary: str = ""
    decisions: list[str] = field(default_factory=list)
    bugs: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    key_topics: list[str] = field(default_factory=list)
    cliffnotes: str = ""

    @property
    def full_text(self) -> str:
        """Concatenated conversation text for analysis."""
        parts = []
        for turn in self.raw_turns:
            role = turn.get("role", "unknown").upper()
            content = turn.get("content", "")
            if content:
                parts.append(f"{role}: {content}")
        return "\n\n".join(parts)

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "provider": self.provider,
            "date": self.date,
            "title": self.title,
            "summary": self.summary,
            "decisions": self.decisions,
            "bugs": self.bugs,
            "fixes": self.fixes,
            "open_questions": self.open_questions,
            "key_topics": self.key_topics,
            "cliffnotes": self.cliffnotes,
            "word_count": self.word_count,
        }


@dataclass
class PipelineResult:
    """Result of a full V.I.C. pipeline run."""
    success: bool
    sessions_processed: int = 0
    pdf_path: str | None = None
    jsonl_path: str | None = None
    error: str = ""
