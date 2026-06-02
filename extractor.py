# core/extractor.py
from __future__ import annotations

import re
from core.config import VICConfig, Session


# ── Keyword patterns for extraction ──────────────────────────────────

_DECISION_PATTERNS = [
    r"(?:decided|decision|chose|choosing|going with|we['\u2019]ll use|will use|using|switched to|moving to)\s+(.{10,120})",
    r"(?:the fix is|fix:|solution:|resolved by|the approach is)\s+(.{10,120})",
    r"(?:architecture|design|approach|strategy):\s+(.{10,120})",
]

_BUG_PATTERNS = [
    r"(?:bug|issue|problem|error|broken|failing|crash|exception|traceback|doesn['\u2019]t work|not working)\s*[:\-]?\s+(.{10,150})",
    r"(?:found that|discovered|noticed|turns out)\s+(.{10,150})",
    r"(?:root cause|the issue is|the problem is)\s+(.{10,150})",
]

_FIX_PATTERNS = [
    r"(?:fixed|fix:|fixed by|resolved|solution|the fix|patched|corrected)\s*[:\-]?\s+(.{10,150})",
    r"(?:adding|added|removing|removed|changed|updated|rewrote)\s+(.{10,150})",
    r"(?:the solution was|this works because|now works)\s+(.{10,150})",
]

_QUESTION_PATTERNS = [
    r"(?:question:|todo:|to do:|next step:|should we|need to|wondering if|not sure|unclear|open question)\s+(.{10,150})",
    r"(?:still need to|haven['\u2019]t|remaining|pending|blocked on)\s+(.{10,150})",
]

_TOPIC_KEYWORDS = [
    "api", "database", "auth", "authentication", "model", "memory", "context",
    "router", "tool", "agent", "pipeline", "architecture", "performance",
    "security", "test", "deploy", "refactor", "optimization", "bug", "feature",
    "config", "server", "client", "endpoint", "schema", "migration",
    # Sovereign Shards specific
    "five masters", "shard", "sovereign", "gguf", "llama", "circuit breaker",
    "working memory", "long-term", "retriever", "bm25", "sandbox", "forge",
]


def extract_all(sessions: list[Session], cfg: VICConfig) -> list[Session]:
    """Run extraction on all sessions."""
    for session in sessions:
        _extract_session(session, cfg)
    return sessions


def _extract_session(session: Session, cfg: VICConfig) -> None:
    """Extract structured information from a single session."""
    text = session.full_text

    session.decisions = _extract_pattern_matches(text, _DECISION_PATTERNS)
    session.bugs = _extract_pattern_matches(text, _BUG_PATTERNS)
    session.fixes = _extract_pattern_matches(text, _FIX_PATTERNS)
    session.open_questions = _extract_pattern_matches(text, _QUESTION_PATTERNS)
    session.key_topics = _extract_topics(text)
    session.summary = _build_summary(session)
    session.cliffnotes = _build_cliffnotes(session)


def _extract_pattern_matches(text: str, patterns: list[str]) -> list[str]:
    """Extract unique matches from text using pattern list."""
    matches = []
    seen = set()
    text_lower = text.lower()

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            extracted = match.group(1).strip()
            # Clean up trailing punctuation and newlines
            extracted = re.sub(r"[\n\r]+", " ", extracted)
            extracted = extracted.rstrip(".,;:")
            extracted = extracted[:200]  # cap length

            # Deduplicate
            key = extracted.lower()[:50]
            if key not in seen and len(extracted) > 15:
                seen.add(key)
                matches.append(extracted)

    return matches[:10]  # cap at 10 per category


def _extract_topics(text: str) -> list[str]:
    """Extract key topics mentioned in the conversation."""
    text_lower = text.lower()
    found = []
    for keyword in _TOPIC_KEYWORDS:
        if keyword in text_lower:
            found.append(keyword)
    return found[:15]


def _build_summary(session: Session) -> str:
    """Build a 2-3 sentence summary from session content."""
    # Use first meaningful assistant response as summary seed
    assistant_texts = [
        t["content"] for t in session.raw_turns
        if t.get("role") == "assistant" and len(t.get("content", "")) > 100
    ]

    if not assistant_texts:
        return f"Session covering: {', '.join(session.key_topics[:5]) or 'general discussion'}."

    # Take first 300 chars of first substantial assistant message
    seed = assistant_texts[0][:300].strip()
    seed = re.sub(r"\n+", " ", seed)

    topic_str = ""
    if session.key_topics:
        topic_str = f" Topics: {', '.join(session.key_topics[:5])}."

    return f"{seed}...{topic_str}"


def _build_cliffnotes(session: Session) -> str:
    """Build a paragraph cliffnotes entry for this session."""
    parts = []

    # Opening line
    provider = session.provider.capitalize()
    parts.append(f"[{session.date}] {provider} session: \"{session.title}\".")

    # What was discussed
    if session.key_topics:
        parts.append(f"Covered: {', '.join(session.key_topics[:6])}.")

    # Key decision
    if session.decisions:
        parts.append(f"Key decision: {session.decisions[0]}.")

    # Bug found
    if session.bugs:
        parts.append(f"Issue encountered: {session.bugs[0]}.")

    # Fix applied
    if session.fixes:
        parts.append(f"Resolution: {session.fixes[0]}.")

    # Open question
    if session.open_questions:
        parts.append(f"Left open: {session.open_questions[0]}.")

    return " ".join(parts)
