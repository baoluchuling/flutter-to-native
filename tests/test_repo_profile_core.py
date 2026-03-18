import json
import tempfile
import unittest
from pathlib import Path

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from repo_profile_core import build_profile, update_profile  # type: ignore


class RepoProfileCoreTests(unittest.TestCase):
    def _write_swift(self, root: Path, rel_path: str, content: str) -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_dart(self, root: Path, rel_path: str, content: str) -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_build_profile_generates_v2_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            output_dir = Path(tmp_dir) / "native-profile-v2"
            repo_root.mkdir(parents=True, exist_ok=True)

            self._write_swift(
                repo_root,
                "Reader/BookDetail/BookDetailViewController.swift",
                """
import UIKit

final class BookDetailViewController: UIViewController {
    private let viewModel = BookDetailViewModel()
}

final class BookDetailViewModel {
}
""",
            )
            self._write_swift(
                repo_root,
                "Reader/Playback/PlaybackService.swift",
                """
import Foundation

final class PlaybackService {
}
""",
            )

            build_profile(repo_root=repo_root, output_dir=output_dir, include_tests=True, max_files=0)

            required = [
                "feature_registry.json",
                "host_mapping.json",
                "symbol_graph.jsonl",
                "relation_graph.jsonl",
                "feature_file_index.json",
                "scan_meta.yaml",
            ]
            for name in required:
                self.assertTrue((output_dir / name).exists(), msg=f"missing {name}")

            feature_registry = json.loads((output_dir / "feature_registry.json").read_text(encoding="utf-8"))
            feature_ids = {item["feature_id"] for item in feature_registry}
            self.assertIn("feature.book_detail", feature_ids)
            self.assertIn("feature.playback", feature_ids)

            host_mapping = json.loads((output_dir / "host_mapping.json").read_text(encoding="utf-8"))
            book_detail = next(item for item in host_mapping if item["feature_id"] == "feature.book_detail")
            self.assertIn("BookDetailViewController", book_detail["page_hosts"])
            self.assertIn("BookDetailViewModel", book_detail["state_hosts"])

    def test_update_profile_preserves_unchanged_features_and_updates_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            output_dir = Path(tmp_dir) / "native-profile-v2"
            repo_root.mkdir(parents=True, exist_ok=True)

            book_path = "Reader/BookDetail/BookDetailViewController.swift"
            playback_path = "Reader/Playback/PlaybackService.swift"

            self._write_swift(
                repo_root,
                book_path,
                """
import UIKit
final class BookDetailViewController: UIViewController {}
""",
            )
            self._write_swift(
                repo_root,
                playback_path,
                """
import Foundation
final class PlaybackService {}
""",
            )
            build_profile(repo_root=repo_root, output_dir=output_dir, include_tests=True, max_files=0)

            self._write_swift(
                repo_root,
                book_path,
                """
import UIKit
final class BookDetailViewController: UIViewController {}
final class BookDetailActionHandler {}
""",
            )

            update_profile(
                repo_root=repo_root,
                output_dir=output_dir,
                changed_paths=[book_path],
                include_tests=True,
                max_files=0,
            )

            host_mapping = json.loads((output_dir / "host_mapping.json").read_text(encoding="utf-8"))
            book_detail = next(item for item in host_mapping if item["feature_id"] == "feature.book_detail")
            self.assertIn("BookDetailActionHandler", book_detail["action_hosts"])
            playback = next(item for item in host_mapping if item["feature_id"] == "feature.playback")
            self.assertIn("PlaybackService", playback["data_hosts"])

    def test_build_profile_supports_flutter_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "flutter"
            output_dir = Path(tmp_dir) / "flutter-profile"
            repo_root.mkdir(parents=True, exist_ok=True)

            self._write_dart(
                repo_root,
                "lib/features/book_detail/book_detail_page.dart",
                """
import 'package:flutter/widgets.dart';

class BookDetailPage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container();
  }
}
""",
            )

            counts = build_profile(
                repo_root=repo_root,
                output_dir=output_dir,
                include_tests=True,
                max_files=0,
                platform="flutter",
            )

            required = [
                "scan_meta.json",
                "feature_index.json",
                "route_map.json",
                "state_patterns.json",
                "data_flow_index.json",
                "resource_index.json",
                "test_index.json",
                "repo_summary.md",
            ]
            for name in required:
                self.assertTrue((output_dir / name).exists(), msg=f"missing {name}")

            self.assertGreaterEqual(counts.get("files", 0), 1)


if __name__ == "__main__":
    unittest.main()
