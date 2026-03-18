import argparse
import tempfile
import unittest
from pathlib import Path

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from atlas_planner import build_contract, build_inputs, build_parser, validate_inputs  # type: ignore


class AtlasPlannerV2OnlyTests(unittest.TestCase):
    def test_plan_parser_requires_profile_v2_dir_and_does_not_expose_profile_dir(self) -> None:
        parser = build_parser()
        plan_action = next(
            action
            for action in parser._actions
            if action.dest == "command"
        )
        plan_parser = plan_action.choices["plan"]
        option_dests = {action.dest for action in plan_parser._actions}
        self.assertIn("profile_v2_dir", option_dests)
        self.assertNotIn("profile_dir", option_dests)

    def test_validate_inputs_accepts_profile_v2_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            run_dir = Path(tmp_dir) / "run"
            profile_v2_dir = Path(tmp_dir) / "native-profile-v2"
            flutter_path = Path(tmp_dir) / "flutter_feature"

            repo_root.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(parents=True, exist_ok=True)
            flutter_path.mkdir(parents=True, exist_ok=True)
            (repo_root / "Sample.swift").write_text("import Foundation\n", encoding="utf-8")

            profile_v2_dir.mkdir(parents=True, exist_ok=True)
            (profile_v2_dir / "feature_registry.json").write_text("[]\n", encoding="utf-8")
            (profile_v2_dir / "host_mapping.json").write_text("[]\n", encoding="utf-8")

            args = argparse.Namespace(
                repo_root=str(repo_root),
                profile_v2_dir=str(profile_v2_dir),
                run_dir=str(run_dir),
                prd_path=None,
                flutter_root=None,
                flutter_path=str(flutter_path),
                flutter_digest_path=None,
                pr_diff_path=None,
                tests_path=None,
                llm_resolution_path=None,
                requirement_id="REQ-1",
                requirement_name="book_detail_sync",
                force=True,
            )
            inputs = build_inputs(args)
            validate_inputs(inputs)

    def test_build_contract_uses_profile_v2_dir_in_target_profile_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            run_dir = Path(tmp_dir) / "run"
            profile_v2_dir = Path(tmp_dir) / "native-profile-v2"
            flutter_path = Path(tmp_dir) / "flutter_feature"

            repo_root.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(parents=True, exist_ok=True)
            flutter_path.mkdir(parents=True, exist_ok=True)

            (repo_root / "BookDetailViewController.swift").write_text(
                "import UIKit\nfinal class BookDetailViewController: UIViewController {}\n",
                encoding="utf-8",
            )
            (flutter_path / "book_detail_page.dart").write_text(
                "class BookDetailPage {}\n",
                encoding="utf-8",
            )

            profile_v2_dir.mkdir(parents=True, exist_ok=True)
            (profile_v2_dir / "feature_registry.json").write_text(
                '[{"feature_id":"feature.book_detail","name":"Book Detail","description":"Book detail page"}]\n',
                encoding="utf-8",
            )
            (profile_v2_dir / "host_mapping.json").write_text(
                (
                    '[{"feature_id":"feature.book_detail","page_hosts":["BookDetailViewController"],'
                    '"action_hosts":[],"state_hosts":[],"data_hosts":[],"side_effect_hosts":[],'
                    '"code_entities":["BookDetailViewController.swift"]}]\n'
                ),
                encoding="utf-8",
            )

            args = argparse.Namespace(
                repo_root=str(repo_root),
                profile_v2_dir=str(profile_v2_dir),
                run_dir=str(run_dir),
                prd_path=None,
                flutter_root=None,
                flutter_path=str(flutter_path),
                flutter_digest_path=None,
                pr_diff_path=None,
                tests_path=None,
                llm_resolution_path=None,
                requirement_id="REQ-2",
                requirement_name="book_detail",
                force=True,
            )
            inputs = build_inputs(args)
            validate_inputs(inputs)
            contract = build_contract(inputs)

            self.assertEqual(Path(contract["target"]["profile_path"]).resolve(), profile_v2_dir.resolve())
            self.assertIn("Profile v2 enabled: yes", contract["source"]["notes"])
            self.assertNotIn("Legacy profile enabled: no", contract["source"]["notes"])


if __name__ == "__main__":
    unittest.main()
