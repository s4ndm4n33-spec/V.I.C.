# parsers/claude.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from core.config import VICConfig, Session


def parse_claude_export(data: dict, source: str, cfg: VICConfig) -> list[Session]:
    """Parse a single Claude conversation export.

    Claude export format (as of 2025-2026):
    {
        "uuid": "...",
        "name": "conversation title",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "...",
        "chat_messages": [
            {
                "uuid": "...",
                "text": "...",
                "sender": "human" | "assistant",
                "created_at": "..."
            }
        ]
    }
    """
    if not isinstance(data, dict):
        return []

    title = (
        data.get("name")
        or data.get("title")
        or Path(source).stem
        or "Claude Session"
    )

    date = _parse_claude_date(
        data.get("created_at") or data.get("updated_at") or ""
    )

    messages = data.get("chat_messages") or data.get("messages") or []
    turns = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        sender = msg.get("sender") or msg.get("role") or "unknown"
        role = "user" if sender in ("human", "user") else "assistant"
        content = msg.get("text") or msg.get("content") or ""
        if isinstance(content, list):
            # Handle structured content blocks
            texts = []
            for block in content:
                if isinstance(block, str):
                    texts.append(block)
                elif isinstance(block, dict):
                    t = block.get("text") or block.get("content") or ""
                    if t:
                        texts.append(str(t))
            content = " ".join(texts)
        content = str(content).strip()
        if content:
            turns.append({"role": role, "content": content})

    if not turns:
        return []

    session_id = f"claude_{data.get('uuid', Path(source).stem)[:20]}"

    return [Session(
        session_id=session_id,
        provider="claude",
        date=date,
        title=str(title)[:200],
        raw_turns=turns,
    )]


def _parse_claude_date(date_str: str) -> str:
    if not date_str:
        return "0000-00-00"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:26], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return date_str[:10] if len(date_str) >= 10 else "0000-00-00"
