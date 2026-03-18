import json
import tempfile
import unittest
from pathlib import Path

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from atlas_intent_bridge import (  # type: ignore
    load_profile_v2,
    merge_touchpoints,
    select_touchpoints_from_profile,
    touchpoints_from_llm_resolution,
)


class AtlasIntentBridgeTests(unittest.TestCase):
    def test_select_touchpoints_from_profile_uses_host_mapping_entities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "feature_registry.json").write_text(
                json.dumps(
                    [
                        {
                            "feature_id": "feature.book_detail",
                            "name": "Book Detail",
                            "description": "Book detail page and actions",
                            "aliases": ["book", "detail"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "host_mapping.json").write_text(
                json.dumps(
                    [
                        {
                            "feature_id": "feature.book_detail",
                            "page_hosts": ["BookDetailViewController"],
                            "action_hosts": ["BookDetailActionHandler"],
                            "state_hosts": ["BookDetailViewModel"],
                            "data_hosts": ["BookService"],
                            "code_entities": [
                                "Reader/BookDetailViewController.swift",
                                "Reader/BookDetailViewModel.swift",
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            profile = load_profile_v2(root)
            keyword_bundle = {
                "ordered": ["book", "detail"],
                "base": ["book", "detail"],
                "aliases": [],
            }
            evidence = {
                "flutter": {
                    "screens": ["BookDetailPage"],
                    "interactions": ["open_book_detail"],
                }
            }
            touchpoints = select_touchpoints_from_profile(
                profile=profile,
                keyword_bundle=keyword_bundle,
                evidence=evidence,
                limit=5,
            )

            paths = {item["path"] for item in touchpoints}
            self.assertIn("Reader/BookDetailViewController.swift", paths)
            self.assertIn("Reader/BookDetailViewModel.swift", paths)

    def test_touchpoints_from_llm_resolution_uses_suggested_paths(self) -> None:
        resolution = {
            "suggested_paths": [
                "Reader/PlaybackViewController.swift",
                "Reader/PlaybackService.swift",
            ],
            "rationale": "Playback flow and service touched.",
        }
        touchpoints = touchpoints_from_llm_resolution(resolution=resolution, profile=None, repo_root=Path("."))
        paths = [item["path"] for item in touchpoints]
        self.assertEqual(
            paths,
            ["Reader/PlaybackViewController.swift", "Reader/PlaybackService.swift"],
        )

    def test_merge_touchpoints_prefers_higher_confidence(self) -> None:
        primary = [
            {
                "path": "Reader/BookDetailViewController.swift",
                "kind": "feature_screen",
                "confidence": 0.55,
                "risk": "low",
                "safe_patch": True,
                "reason": "heuristic",
            }
        ]
        extras = [
            {
                "path": "Reader/BookDetailViewController.swift",
                "kind": "feature_screen",
                "confidence": 0.82,
                "risk": "low",
                "safe_patch": True,
                "reason": "profile",
            }
        ]

        merged = merge_touchpoints(primary=primary, extras=extras, limit=5)
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0]["confidence"], 0.82, places=2)
        self.assertIn("profile", merged[0]["reason"])


if __name__ == "__main__":
    unittest.main()
