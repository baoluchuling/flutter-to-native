import unittest

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from atlas_intent_resolver import normalize_resolution_payload  # type: ignore


class AtlasIntentResolverTests(unittest.TestCase):
    def test_normalize_resolution_payload_keeps_suggestions(self) -> None:
        payload = {
            "model": "gpt-5",
            "confidence": "high",
            "suggested_feature_ids": ["feature.book_detail", "feature.tts_playback"],
            "suggested_paths": ["Reader/BookDetailViewController.swift"],
            "rationale": "Feature-level match.",
        }
        normalized = normalize_resolution_payload(
            provider="agent",
            requirement_id="REQ-1",
            requirement_name="book_detail_sync",
            payload=payload,
        )
        self.assertEqual(normalized["provider"], "agent")
        self.assertEqual(normalized["model"], "gpt-5")
        self.assertEqual(normalized["confidence"], "high")
        self.assertEqual(
            normalized["suggested_feature_ids"],
            ["feature.book_detail", "feature.tts_playback"],
        )
        self.assertEqual(
            normalized["suggested_paths"],
            ["Reader/BookDetailViewController.swift"],
        )

    def test_normalize_resolution_payload_defaults_for_empty_payload(self) -> None:
        normalized = normalize_resolution_payload(
            provider="none",
            requirement_id="REQ-2",
            requirement_name="empty_case",
            payload={},
        )
        self.assertEqual(normalized["provider"], "none")
        self.assertEqual(normalized["confidence"], "low")
        self.assertEqual(normalized["suggested_feature_ids"], [])
        self.assertEqual(normalized["suggested_paths"], [])


if __name__ == "__main__":
    unittest.main()
