# parsers/gemini.py
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from datetime import datetime

from core.config import VICConfig, Session


def parse_gemini_takeout(zip_path: Path, cfg: VICConfig) -> list[Session]:
    """Parse Google Takeout ZIP for Gemini conversation history.

    Takeout structure:
      Takeout/
        Gemini Apps Activity/
          Gemini Apps Activity.json   ← main conversation history
    """
    sessions = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        # Find Gemini activity files
        gemini_files = [
            n for n in names
            if "Gemini" in n and n.endswith(".json")
        ]

        if not gemini_files and cfg.verbose:
            print("[VIC] No Gemini history found in Takeout ZIP")
            print(f"[VIC] Available paths: {[n for n in names if n.endswith('.json')][:10]}")

        for fname in gemini_files:
            if cfg.verbose:
                print(f"[VIC] Parsing: {fname}")
            try:
                raw = zf.read(fname).decode("utf-8", errors="replace")
                data = json.loads(raw)
                sessions.extend(_parse_gemini_data(data, cfg))
            except Exception as e:
                if cfg.verbose:
                    print(f"[VIC] Failed to parse {fname}: {e}")
                continue

    return sessions


def _parse_gemini_data(data: dict | list, cfg: VICConfig) -> list[Session]:
    """Parse Gemini activity JSON into Session objects.

    Gemini Takeout format varies — handle both list and dict top level.
    """
    sessions = []

    # Normalize to list of conversation entries
    entries = []
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        # May be wrapped: {"conversations": [...]} or similar
        for key in ("conversations", "items", "activity", "data"):
            if key in data and isinstance(data[key], list):
                entries = data[key]
                break
        if not entries:
            entries = [data]

    for i, entry in enumerate(entries):
        session = _parse_gemini_entry(entry, index=i)
        if session:
            sessions.append(session)

    return sessions


def _parse_gemini_entry(entry: dict, index: int) -> Session | None:
    """Parse one Gemini conversation entry."""
    if not isinstance(entry, dict):
        return None

    # Extract timestamp
    date = _extract_date(entry)

    # Extract title
    title = (
        entry.get("title")
        or entry.get("header")
        or entry.get("subject")
        or f"Gemini Session {index + 1}"
    )

    # Extract turns — Gemini uses various field names
    turns = []
    raw_turns = (
        entry.get("turns")
        or entry.get("messages")
        or entry.get("conversation")
        or entry.get("content")
        or []
    )

    if isinstance(raw_turns, list):
        for turn in raw_turns:
            if not isinstance(turn, dict):
                continue
            role = _normalize_role(turn.get("role") or turn.get("author") or "unknown")
            content = _extract_content(turn)
            if content:
                turns.append({"role": role, "content": content})

    if not turns:
        return None

    return Session(
        session_id=f"gemini_{index:04d}",
        provider="gemini",
        date=date,
        title=str(title)[:200],
        raw_turns=turns,
    )


def _extract_date(entry: dict) -> str:
    """Extract ISO date string from entry."""
    for field in ("timestamp", "created_at", "date", "time", "updated_at"):
        val = entry.get(field)
        if val:
            if isinstance(val, (int, float)):
                # Unix timestamp — milliseconds or seconds
                ts = val / 1000 if val > 1e10 else val
                try:
                    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                except Exception:
                    pass
            elif isinstance(val, str):
                # Try to parse ISO string
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(val[:19], fmt).strftime("%Y-%m-%d")
                    except Exception:
                        continue
    return "0000-00-00"


def _normalize_role(role: str) -> str:
    role = role.lower().strip()
    if role in ("user", "human", "you"):
        return "user"
    if role in ("assistant", "model", "gemini", "bot", "ai"):
        return "assistant"
    return role


def _extract_content(turn: dict) -> str:
    """Extract text content from a turn — handles nested structures."""
    # Direct content field
    for field in ("content", "text", "message", "parts"):
        val = turn.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, list):
            # Gemini sometimes uses parts: [{"text": "..."}]
            texts = []
            for part in val:
                if isinstance(part, str):
                    texts.append(part)
                elif isinstance(part, dict):
                    t = part.get("text") or part.get("content") or ""
                    if t:
                        texts.append(str(t))
            if texts:
                return " ".join(texts).strip()
    return ""
