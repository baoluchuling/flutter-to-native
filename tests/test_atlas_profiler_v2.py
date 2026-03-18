import argparse
import json
import tempfile
import unittest
from pathlib import Path

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from atlas_profiler import handle_scan  # type: ignore


class AtlasProfilerV2Tests(unittest.TestCase):
    def _write_swift(self, root: Path, rel_path: str, content: str) -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_scan_v2_full_generates_repo_profile_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            output_dir = Path(tmp_dir) / "native-profile-v2"
            repo_root.mkdir(parents=True, exist_ok=True)
            self._write_swift(
                repo_root,
                "Reader/BookDetail/BookDetailViewController.swift",
                "import UIKit\nfinal class BookDetailViewController: UIViewController {}\n",
            )

            args = argparse.Namespace(
                repo_root=str(repo_root),
                output_dir=str(output_dir),
                force=True,
                scope="full",
                changed_files=None,
                diff_from=None,
                diff_to="HEAD",
                include_tests=True,
                max_files=0,
            )
            exit_code = handle_scan(args)
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "feature_registry.json").exists())
            self.assertTrue((output_dir / "host_mapping.json").exists())
            # atlas_profiler should no longer emit legacy profile markers.
            self.assertFalse((output_dir / "scan_meta.json").exists())

    def test_scan_v2_changed_updates_profile_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            output_dir = Path(tmp_dir) / "native-profile-v2"
            repo_root.mkdir(parents=True, exist_ok=True)
            file_path = "Reader/BookDetail/BookDetailViewController.swift"
            changed_path_file = Path(tmp_dir) / "changed.txt"

            self._write_swift(
                repo_root,
                file_path,
                "import UIKit\nfinal class BookDetailViewController: UIViewController {}\n",
            )
            full_args = argparse.Namespace(
                repo_root=str(repo_root),
                output_dir=str(output_dir),
                force=True,
                scope="full",
                changed_files=None,
                diff_from=None,
                diff_to="HEAD",
                include_tests=True,
                max_files=0,
            )
            self.assertEqual(handle_scan(full_args), 0)

            self._write_swift(
                repo_root,
                file_path,
                (
                    "import UIKit\n"
                    "final class BookDetailViewController: UIViewController {}\n"
                    "final class BookDetailActionHandler {}\n"
                ),
            )
            changed_path_file.write_text(file_path + "\n", encoding="utf-8")
            changed_args = argparse.Namespace(
                repo_root=str(repo_root),
                output_dir=str(output_dir),
                force=True,
                scope="changed",
                changed_files=str(changed_path_file),
                diff_from=None,
                diff_to="HEAD",
                include_tests=True,
                max_files=0,
            )
            self.assertEqual(handle_scan(changed_args), 0)

            host_mapping = json.loads((output_dir / "host_mapping.json").read_text(encoding="utf-8"))
            entry = next(item for item in host_mapping if item["feature_id"] == "feature.book_detail")
            self.assertIn("BookDetailActionHandler", entry["action_hosts"])
            self.assertFalse((output_dir / "scan_meta.json").exists())


if __name__ == "__main__":
    unittest.main()
