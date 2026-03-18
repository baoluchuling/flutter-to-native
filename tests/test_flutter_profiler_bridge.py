import argparse
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from flutter_profiler import handle_scan  # type: ignore


class FlutterProfilerBridgeTests(unittest.TestCase):
    def _write_dart(self, root: Path, rel_path: str, content: str) -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_scan_uses_repo_profile_core_path_not_legacy_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "flutter"
            output_dir = Path(tmp_dir) / "flutter-profile"
            repo_root.mkdir(parents=True, exist_ok=True)
            self._write_dart(
                repo_root,
                "lib/features/book_detail/book_detail_page.dart",
                "class BookDetailPage {}\n",
            )

            args = argparse.Namespace(
                repo_root=str(repo_root),
                output_dir=str(output_dir),
                force=True,
                include_tests=True,
                max_files=0,
            )

            with mock.patch("flutter_profiler.scan_flutter_repo", side_effect=AssertionError("legacy path should not be called")):
                handle_scan(args)

            self.assertTrue((output_dir / "scan_meta.json").exists())
            self.assertTrue((output_dir / "feature_index.json").exists())


if __name__ == "__main__":
    unittest.main()
