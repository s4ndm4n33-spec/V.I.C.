# tests/test_vic.py
"""V.I.C. core test suite. Zero external deps — stdlib unittest only."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import VICConfig, Session
from core.extractor import extract_all, _extract_pattern_matches, _DECISION_PATTERNS
from core.project import build_project_summary
from parsers.chatgpt import parse_chatgpt_conversation
from parsers.claude import parse_claude_export
from parsers.generic import parse_generic_json


def _make_cfg(tmp_dir: str) -> VICConfig:
    return VICConfig(
        input_path=Path(tmp_dir),
        output_path=Path(tmp_dir),
        project_name="Test Project",
        generate_pdf=False,
        generate_jsonl=True,
        verbose=False,
    )


def _make_session(**kwargs) -> Session:
    defaults = dict(
        session_id="test_001",
        provider="test",
        date="2026-01-01",
        title="Test Session",
        raw_turns=[
            {"role": "user", "content": "How do I fix the authentication bug?"},
            {"role": "assistant", "content": "The bug is caused by a missing token check. "
             "I decided to add a guard clause at the top of the auth function. "
             "Fixed by adding: if not token: raise AuthError. "
             "Open question: should we also validate token expiry?"},
        ],
    )
    defaults.update(kwargs)
    return Session(**defaults)


class TestSession(unittest.TestCase):
    def test_full_text_concatenates_turns(self):
        s = _make_session()
        text = s.full_text
        self.assertIn("USER:", text)
        self.assertIn("ASSISTANT:", text)
        self.assertIn("authentication bug", text)

    def test_word_count_positive(self):
        s = _make_session()
        self.assertGreater(s.word_count, 0)

    def test_to_dict_has_required_keys(self):
        s = _make_session()
        d = s.to_dict()
        for key in ("session_id", "provider", "date", "title",
                    "summary", "decisions", "bugs", "fixes",
                    "open_questions", "key_topics", "cliffnotes"):
            self.assertIn(key, d)


class TestExtractor(unittest.TestCase):
    def test_extracts_bug(self):
        sessions = [_make_session()]
        extract_all(sessions, _make_cfg(tempfile.mkdtemp()))
        # Should find something bug-related
        s = sessions[0]
        self.assertIsInstance(s.bugs, list)

    def test_extracts_fix(self):
        sessions = [_make_session()]
        extract_all(sessions, _make_cfg(tempfile.mkdtemp()))
        s = sessions[0]
        self.assertIsInstance(s.fixes, list)

    def test_builds_cliffnotes(self):
        sessions = [_make_session()]
        extract_all(sessions, _make_cfg(tempfile.mkdtemp()))
        s = sessions[0]
        self.assertIsInstance(s.cliffnotes, str)
        self.assertGreater(len(s.cliffnotes), 0)

    def test_pattern_match_deduplicates(self):
        text = "decided to use Python. decided to use Python. decided to use Python."
        matches = _extract_pattern_matches(text, _DECISION_PATTERNS)
        # Should deduplicate
        self.assertLessEqual(len(matches), 2)


class TestProjectSummary(unittest.TestCase):
    def test_builds_from_sessions(self):
        sessions = [_make_session()]
        extract_all(sessions, _make_cfg(tempfile.mkdtemp()))
        cfg = _make_cfg(tempfile.mkdtemp())
        project = build_project_summary(sessions, cfg)
        self.assertEqual(project.total_sessions, 1)
        self.assertGreater(project.total_words, 0)
        self.assertIsInstance(project.executive_summary, str)

    def test_uses_config_project_name(self):
        sessions = [_make_session()]
        cfg = _make_cfg(tempfile.mkdtemp())
        cfg.project_name = "My Custom Project"
        project = build_project_summary(sessions, cfg)
        self.assertEqual(project.name, "My Custom Project")

    def test_date_range(self):
        s1 = _make_session(session_id="s1", date="2025-01-01")
        s2 = _make_session(session_id="s2", date="2026-06-01")
        cfg = _make_cfg(tempfile.mkdtemp())
        project = build_project_summary([s1, s2], cfg)
        self.assertIn("2025-01-01", project.date_range)
        self.assertIn("2026-06-01", project.date_range)


class TestChatGPTParser(unittest.TestCase):
    def _make_convo(self) -> dict:
        return {
            "id": "abc123",
            "title": "Test ChatGPT Chat",
            "create_time": 1704067200.0,  # 2024-01-01
            "mapping": {
                "root": {
                    "id": "root",
                    "parent": None,
                    "children": ["msg1"],
                    "message": None,
                },
                "msg1": {
                    "id": "msg1",
                    "parent": "root",
                    "children": ["msg2"],
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello, help me build something"]},
                    },
                },
                "msg2": {
                    "id": "msg2",
                    "parent": "msg1",
                    "children": [],
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Sure, I can help with that."]},
                    },
                },
            },
        }

    def test_parses_basic_conversation(self):
        session = parse_chatgpt_conversation(self._make_convo())
        self.assertIsNotNone(session)
        self.assertEqual(session.provider, "chatgpt")
        self.assertEqual(len(session.raw_turns), 2)
        self.assertEqual(session.raw_turns[0]["role"], "user")
        self.assertEqual(session.raw_turns[1]["role"], "assistant")

    def test_extracts_date(self):
        session = parse_chatgpt_conversation(self._make_convo())
        self.assertEqual(session.date, "2024-01-01")

    def test_returns_none_for_empty_mapping(self):
        convo = {"id": "x", "title": "Empty", "mapping": {}}
        result = parse_chatgpt_conversation(convo)
        self.assertIsNone(result)


class TestClaudeParser(unittest.TestCase):
    def _make_export(self) -> dict:
        return {
            "uuid": "claude-uuid-001",
            "name": "Sovereign Shards Discussion",
            "created_at": "2026-05-01T10:00:00Z",
            "chat_messages": [
                {"sender": "human", "text": "How does the circuit breaker work?"},
                {"sender": "assistant", "text": "The circuit breaker detects repeated tool calls and halts the loop."},
            ],
        }

    def test_parses_basic_export(self):
        sessions = parse_claude_export(self._make_export(), source="test.json", cfg=None)
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "claude")
        self.assertEqual(len(s.raw_turns), 2)

    def test_extracts_title(self):
        sessions = parse_claude_export(self._make_export(), source="test.json", cfg=None)
        self.assertEqual(sessions[0].title, "Sovereign Shards Discussion")


class TestGenericParser(unittest.TestCase):
    def test_parses_message_list(self):
        data = [
            {"role": "user", "content": "What is the plan?"},
            {"role": "assistant", "content": "The plan has three steps."},
        ]
        sessions = parse_generic_json(data, source="test.json", cfg=None)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0].raw_turns), 2)

    def test_parses_wrapped_messages(self):
        data = {
            "title": "Planning Session",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hello back"},
            ],
        }
        sessions = parse_generic_json(data, source="test.json", cfg=None)
        self.assertEqual(len(sessions), 1)

    def test_returns_empty_for_empty_input(self):
        sessions = parse_generic_json({}, source="test.json", cfg=None)
        self.assertEqual(sessions, [])


class TestJSONLWriter(unittest.TestCase):
    def test_writes_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            sessions = [_make_session()]
            extract_all(sessions, cfg)
            from core.project import build_project_summary
            from output.jsonl_writer import write_jsonl
            project = build_project_summary(sessions, cfg)
            path = write_jsonl(sessions, project, cfg)

            self.assertTrue(path.exists())
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 2)  # header + at least 1 session

            # All lines must be valid JSON
            for line in lines:
                data = json.loads(line)
                self.assertIn("type", data)

    def test_header_has_project_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(tmp)
            sessions = [_make_session()]
            extract_all(sessions, cfg)
            from core.project import build_project_summary
            from output.jsonl_writer import write_jsonl
            project = build_project_summary(sessions, cfg)
            path = write_jsonl(sessions, project, cfg)

            first_line = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(first_line["type"], "project_header")
            self.assertEqual(first_line["name"], "Test Project")


if __name__ == "__main__":
    unittest.main(verbosity=2)
