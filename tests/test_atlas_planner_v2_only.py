import argparse
import tempfile
import unittest
from pathlib import Path

import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from atlas_planner import (
    build_contract,
    build_inputs,
    build_parser,
    build_plan_validation,
    render_plan_validation,
    validate_inputs,
)  # type: ignore



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
            llm_resolution_path = Path(tmp_dir) / "llm_plan.json"

            repo_root.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(parents=True, exist_ok=True)
            flutter_path.mkdir(parents=True, exist_ok=True)
            (repo_root / "Sample.swift").write_text("import Foundation\n", encoding="utf-8")

            profile_v2_dir.mkdir(parents=True, exist_ok=True)
            (profile_v2_dir / "feature_registry.json").write_text("[]\n", encoding="utf-8")
            (profile_v2_dir / "host_mapping.json").write_text("[]\n", encoding="utf-8")
            llm_resolution_path.write_text('{"tasks":[{"task_name":"demo"}]}\n', encoding="utf-8")

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
                llm_resolution_path=str(llm_resolution_path),
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
            llm_resolution_path = Path(tmp_dir) / "llm_plan.json"

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
            llm_resolution_path.write_text('{"tasks":[{"task_name":"demo"}]}\n', encoding="utf-8")

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
                llm_resolution_path=str(llm_resolution_path),
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


    def test_plan_validation_pass_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            target_file = repo_root / "Sources/Reader/ReaderViewController.swift"
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(
                (
                    "import UIKit\n"
                    "final class ReaderViewController: UIViewController {\n"
                    "    func handleUnlockState() {\n"
                    "        presentUnlockSheet()\n"
                    "    }\n"
                    "}\n"
                ),
                encoding="utf-8",
            )

            contract = {
                "target": {"repo_root": str(repo_root)},
                "behavior": {"user_flows": ["用户翻页进入解锁章节后触发购买引导"], "interactions": ["tap unlock CTA"]},
                "patch_plan": {"update": ["Sources/Reader/ReaderViewController.swift"]},
                "native_impact": {
                    "selected_touchpoints": [
                        {
                            "path": "Sources/Reader/ReaderViewController.swift",
                            "kind": "feature_logic",
                            "reason": "场景入口在章节解锁链路中，由 ReaderViewController 编排购买引导",
                            "ui_role": "non_ui",
                            "source_screens": [],
                        }
                    ]
                },
            }
            tasks = [
                {
                    "task_id": "G01",
                    "task_name": "功能组-章节解锁链路",
                    "feature_scope": "reader_unlock_flow",
                    "trigger_lifecycle": "chapter unlock flow",
                    "trigger_or_precondition": "用户翻页进入解锁章节后触发购买引导链路",
                    "planned_action": "update",
                    "behavior_contract": {
                        "logic_constraints": ["解锁章节时进入购买引导分支"],
                        "interactions": ["点击继续解锁入口"],
                    },
                    "native_landing": {
                        "primary_path": "Sources/Reader/ReaderViewController.swift",
                    },
                    "mapping_proof": {
                        "status": "mapped",
                        "confidence": "high",
                        "entry_kind": "orchestration_entry",
                        "entry_semantics": "state_render",
                        "flutter_entrypoints": ["lib/features/reader/reader_page.dart"],
                        "native_chain": [
                            "ReaderViewController.handleUnlockState",
                            "PurchaseCoordinator.presentUnlockSheet",
                        ],
                        "reverse_trace": ["用户翻页 -> ReaderViewController.handleUnlockState"],
                        "evidence_lines": ["Sources/Reader/ReaderViewController.swift:2"],
                        "evidence": [
                            "ReaderViewController 负责章节解锁状态编排",
                            "PurchaseCoordinator 负责购买引导展示",
                        ],
                    },
                }
            ]
            llm_plan = {
                "meta": {
                    "mapping_pipeline": {
                        "capability_split": True,
                        "flutter_hunk_extract": True,
                        "flutter_chain_extract": True,
                        "native_chain_match": True,
                        "disambiguation": True,
                    }
                },
                "hunk_facts": {
                    "business_hunks": [
                        {"file": "lib/features/reader/reader_page.dart"},
                    ]
                },
                "capability_slices": "- 章节解锁链路\n",
                "flutter_chain_map": {
                    "unlock_flow": {
                        "trigger": "page_flip",
                        "effect": "show_purchase_guide",
                    }
                },
                "native_chain_candidates": {
                    "unlock_flow": [
                        {
                            "path": "Sources/Reader/ReaderViewController.swift",
                            "score": 0.98,
                        }
                    ]
                },
                "mapping_disambiguation": "Top1 命中 ReaderViewController，已排除纯视图候选。",
            }
            sync_plan_text = "# Sync Plan\n\n## 计划触点\n\n- `Sources/Reader/ReaderViewController.swift`: update"

            validation = build_plan_validation(contract, sync_plan_text, tasks=tasks, llm_plan=llm_plan)
            rendered = render_plan_validation(validation)

            self.assertEqual(validation["conclusion"], "PASS")
            self.assertIn("# Plan Validation", rendered)
            self.assertIn("**结论：PASS**", rendered)

    def test_plan_validation_fail_when_sync_plan_has_unresolved(self) -> None:
        contract = {
            "behavior": {"user_flows": ["flow"], "interactions": ["tap"]},
            "patch_plan": {"update": []},
            "native_impact": {"selected_touchpoints": []},
        }

        validation = build_plan_validation(contract, "## 功能 1\n- 会员入口需确认具体文件")

        self.assertEqual(validation["conclusion"], "FAIL")
        v1 = next(item for item in validation["checks"] if item["id"] == "V1")
        self.assertEqual(v1["result"], "FAIL")




    def test_plan_validation_fail_when_ui_touchpoint_missing_design_inputs(self) -> None:
        contract = {
            "behavior": {"user_flows": ["展示购买弹窗"], "interactions": ["tap buy"]},
            "patch_plan": {"update": ["Sources/Pay/BuyDialogViewController.swift"]},
            "native_impact": {
                "selected_touchpoints": [
                    {
                        "path": "Sources/Pay/BuyDialogViewController.swift",
                        "kind": "feature_view",
                        "reason": "用户点击后展示购买弹窗",
                        "ui_role": "auxiliary_dialog",
                        "source_screens": [],
                    }
                ]
            },
        }

        validation = build_plan_validation(contract, "# Sync Plan")

        self.assertEqual(validation["conclusion"], "FAIL")
        v5 = next(item for item in validation["checks"] if item["id"] == "V5")
        self.assertEqual(v5["result"], "FAIL")

    def test_validate_inputs_requires_flutter_change_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "ios"
            run_dir = Path(tmp_dir) / "run"
            profile_v2_dir = Path(tmp_dir) / "native-profile-v2"
            prd_path = Path(tmp_dir) / "prd.md"

            repo_root.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(parents=True, exist_ok=True)
            profile_v2_dir.mkdir(parents=True, exist_ok=True)
            (repo_root / "Sample.swift").write_text("import Foundation\n", encoding="utf-8")
            (profile_v2_dir / "feature_registry.json").write_text("[]\n", encoding="utf-8")
            (profile_v2_dir / "host_mapping.json").write_text("[]\n", encoding="utf-8")
            prd_path.write_text("demo prd\n", encoding="utf-8")

            args = argparse.Namespace(
                repo_root=str(repo_root),
                profile_v2_dir=str(profile_v2_dir),
                run_dir=str(run_dir),
                prd_path=str(prd_path),
                flutter_root=None,
                flutter_path=None,
                flutter_digest_path=None,
                pr_diff_path=None,
                tests_path=None,
                llm_resolution_path=None,
                requirement_id="REQ-EVIDENCE",
                requirement_name="need_flutter_changes",
                force=True,
            )
            inputs = build_inputs(args)
            with self.assertRaises(FileNotFoundError):
                validate_inputs(inputs)


if __name__ == "__main__":
    unittest.main()
