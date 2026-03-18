#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


VERIFY_REPORT_FILE = "verify_report.md"
VERIFY_RESULT_FILE = "verify_result.json"
APPLY_RESULT_FILE = "apply_result.json"
GENERATED_MARKER_PREFIX = "T2N Atlas Generated Patch Start"
HOOKABLE_UI_ROLES = {"primary_screen", "auxiliary_dialog", "auxiliary_overlay", "component_view"}
REQUIRED_RUN_FILES = {
    "requirement_sync_contract.yaml",
    "native_operation_plan.yaml",
    "sync_plan.md",
    "touchpoints.md",
    "risk_report.md",
    "apply_report.md",
    APPLY_RESULT_FILE,
}


@dataclass
class VerifyInputs:
    run_dir: Path
    repo_root: Path | None
    force: bool
    swift_parse_check: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Verify for applied requirement sync runs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="Verify an applied sync run")
    verify_parser.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    verify_parser.add_argument("--repo-root", help="Optional override for target repository root")
    verify_parser.add_argument("--force", action="store_true", help="Overwrite an existing verify result")
    verify_parser.add_argument(
        "--swift-parse-check",
        action="store_true",
        help="Run optional `xcrun swiftc -parse` checks for touched Swift files",
    )

    status_parser = subparsers.add_parser("status", help="Report verify status for a run directory")
    status_parser.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    return parser


def build_inputs(args: argparse.Namespace) -> VerifyInputs:
    return VerifyInputs(
        run_dir=Path(args.run_dir).expanduser().resolve(),
        repo_root=Path(args.repo_root).expanduser().resolve() if getattr(args, "repo_root", None) else None,
        force=bool(getattr(args, "force", False)),
        swift_parse_check=bool(getattr(args, "swift_parse_check", False)),
    )


def ensure_run_dir(run_dir: Path) -> None:
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"run dir not found or unreadable: {run_dir}")
    missing = [name for name in REQUIRED_RUN_FILES if not (run_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"run dir missing required files: {', '.join(missing)}")


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def write_text(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def load_contract(run_dir: Path) -> dict:
    return yaml.safe_load((run_dir / "requirement_sync_contract.yaml").read_text(encoding="utf-8"))


def load_operation_plan(run_dir: Path) -> dict:
    return yaml.safe_load((run_dir / "native_operation_plan.yaml").read_text(encoding="utf-8"))


def load_apply_result(run_dir: Path) -> dict:
    return json.loads((run_dir / APPLY_RESULT_FILE).read_text(encoding="utf-8"))


def resolve_repo_root(contract: dict, override_repo_root: Path | None) -> Path:
    if override_repo_root:
        return override_repo_root
    repo_root = contract.get("target", {}).get("repo_root")
    if not repo_root:
        raise FileNotFoundError("contract missing target.repo_root")
    return Path(repo_root).expanduser().resolve()


def marker_for_requirement(requirement_id: str) -> str:
    return f"{GENERATED_MARKER_PREFIX} [{requirement_id}]"


def detect_apply_marker(content: str, requirement_id: str) -> str | None:
    if marker_for_requirement(requirement_id) in content:
        return "generated_patch"
    return None


def sanitize_identifier(value: str) -> str:
    identifier = re.sub(r"[^a-zA-Z0-9_]+", "_", value)
    identifier = re.sub(r"_+", "_", identifier).strip("_")
    if not identifier:
        return "atlas_requirement"
    if identifier[0].isdigit():
        identifier = f"atlas_{identifier}"
    return identifier


def install_method_name(kind: str, ui_role: str, requirement_slug: str) -> str:
    role_suffix = {
        "primary_screen": "InstallPrimaryScreen",
        "auxiliary_dialog": "InstallAuxiliaryDialog",
        "auxiliary_overlay": "InstallAuxiliaryOverlay",
        "component_view": "InstallComponentView",
    }.get(ui_role)
    if role_suffix:
        return f"atlasSync{role_suffix}_{requirement_slug}"
    suffix = {
        "feature_screen": "InstallScreen",
        "feature_logic": "InstallLogic",
        "feature_view": "InstallView",
        "feature_service": "InstallService",
        "feature_model": "InstallModel",
    }.get(kind, "InstallRequirement")
    return f"atlasSync{suffix}_{requirement_slug}"


def render_method_name(ui_role: str, requirement_slug: str) -> str:
    mapping = {
        "primary_screen": "RenderPrimaryScreen",
        "auxiliary_dialog": "PresentAuxiliaryDialog",
        "auxiliary_overlay": "RefreshAuxiliaryOverlay",
        "component_view": "RenderComponentView",
    }
    suffix = mapping.get(ui_role, "Render")
    return f"atlasSync{suffix}_{requirement_slug}"


def interaction_method_name(ui_role: str, requirement_slug: str) -> str:
    mapping = {
        "primary_screen": "BindPrimaryActions",
        "auxiliary_dialog": "BindDialogActions",
        "auxiliary_overlay": "BindOverlayActions",
        "component_view": "BindComponentActions",
    }
    suffix = mapping.get(ui_role, "Interactions")
    return f"atlasSync{suffix}_{requirement_slug}"


def semantic_helper_names(kind: str, ui_role: str, requirement_name: str) -> list[str]:
    requirement_slug = sanitize_identifier(requirement_name)
    if ui_role == "primary_screen":
        return [
            f"atlasSyncPrimaryStateFlags_{requirement_slug}",
            f"atlasSyncPrimaryCopy_{requirement_slug}",
            f"atlasSyncPrimaryCTA_{requirement_slug}",
        ]
    if ui_role == "auxiliary_dialog":
        return [
            f"atlasSyncDialogPresentation_{requirement_slug}",
            f"atlasSyncDialogCTA_{requirement_slug}",
        ]
    if ui_role == "auxiliary_overlay":
        return [
            f"atlasSyncOverlayState_{requirement_slug}",
            f"atlasSyncOverlayCopy_{requirement_slug}",
        ]
    if kind == "feature_logic":
        return [
            f"atlasSyncLogicContext_{requirement_slug}",
            f"atlasSyncLogicStateGraph_{requirement_slug}",
        ]
    if kind == "feature_service":
        return [
            f"atlasSyncServiceRequestPayload_{requirement_slug}",
            f"atlasSyncServiceResponseFields_{requirement_slug}",
        ]
    if kind == "feature_model":
        return [
            f"atlasSyncModelFieldMap_{requirement_slug}",
            f"atlasSyncModelDefaults_{requirement_slug}",
        ]
    if ui_role == "component_view":
        return [f"atlasSyncComponentCopy_{requirement_slug}"]
    return []


def infer_create_type_name(relative_path: str) -> str:
    stem = Path(relative_path).stem
    slug = sanitize_identifier(stem)
    return slug.replace("_", "")


def expected_method_names(kind: str, requirement_name: str) -> list[str]:
    requirement_slug = sanitize_identifier(requirement_name)
    return expected_method_names_for_touchpoint(kind, "non_ui", requirement_name)


def expected_method_names_for_touchpoint(kind: str, ui_role: str, requirement_name: str) -> list[str]:
    requirement_slug = sanitize_identifier(requirement_name)
    install_name = install_method_name(kind, ui_role, requirement_slug)
    render_name = render_method_name(ui_role, requirement_slug)
    interaction_name = interaction_method_name(ui_role, requirement_slug)
    request_name = f"atlasSyncRequests_{requirement_slug}"
    if ui_role in {"primary_screen", "auxiliary_dialog", "auxiliary_overlay", "component_view"}:
        return [install_name, render_name, interaction_name]
    if kind == "feature_screen":
        return [install_name, render_name, interaction_name]
    if kind == "feature_logic":
        return [install_name, request_name, interaction_name]
    if kind == "feature_view":
        return [install_name, render_name, interaction_name]
    if kind == "feature_service":
        return [install_name, request_name]
    if kind == "feature_model":
        return [install_name, render_name]
    return [install_name]


def normalize_operation_action(action: str | None) -> str:
    mapping = {
        "create_file": "create",
        "edit_existing": "update",
        "manual_review": "manual",
    }
    return mapping.get(action or "", "unknown")


def iter_operations(operation_plan: dict) -> list[dict]:
    operations: list[dict] = []
    for raw in operation_plan.get("operations", []):
        if not isinstance(raw, dict):
            continue
        path = raw.get("target_path")
        if not path:
            continue
        operations.append(
            {
                "operation_id": raw.get("operation_id"),
                "path": path,
                "action": normalize_operation_action(raw.get("action")),
                "target_kind": raw.get("target_kind", "other"),
                "ui_role": raw.get("ui_role", "non_ui"),
            }
        )
    return operations


def ensure_operation_contract_consistency(operation_plan: dict, contract: dict) -> None:
    operations = iter_operations(operation_plan)
    from_operations = {
        "create": sorted({item["path"] for item in operations if item["action"] == "create"}),
        "update": sorted({item["path"] for item in operations if item["action"] == "update"}),
        "manual": sorted({item["path"] for item in operations if item["action"] == "manual"}),
    }
    patch_plan = contract.get("patch_plan", {})
    from_contract = {
        "create": sorted(set(patch_plan.get("create", []))),
        "update": sorted(set(patch_plan.get("update", []))),
        "manual": sorted(set(patch_plan.get("manual_candidates", []))),
    }
    if from_operations != from_contract:
        raise ValueError(
            "operation plan and contract patch plan are inconsistent: "
            f"operations={from_operations}, contract={from_contract}"
        )


def generated_block(content: str, requirement_id: str) -> str:
    start_token = marker_for_requirement(requirement_id)
    end_token = f"// T2N Atlas Generated Patch End [{requirement_id}]"
    start = content.find(start_token)
    if start < 0:
        return ""
    end = content.find(end_token, start)
    if end < 0:
        return content[start:]
    end += len(end_token)
    return content[start:end]


def content_without_generated_block(content: str, requirement_id: str) -> str:
    start_token = marker_for_requirement(requirement_id)
    end_token = f"// T2N Atlas Generated Patch End [{requirement_id}]"
    start = content.find(start_token)
    if start < 0:
        return content
    end = content.find(end_token, start)
    if end < 0:
        return content[:start]
    end += len(end_token)
    return content[:start] + content[end:]


def extract_array_items(block: str, array_name: str) -> list[str]:
    pattern = re.compile(
        rf"let\s+{re.escape(array_name)}\s*:\s*\[String\]\s*=\s*\[(.*?)\n\s*\]",
        re.DOTALL,
    )
    match = pattern.search(block)
    if not match:
        return []
    literals = re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    return [bytes(item, "utf-8").decode("unicode_escape") for item in literals]


def behavior_array_name(kind: str) -> str | None:
    mapping = {
        "user_flow": "atlasUserFlows",
        "acceptance_point": "atlasAcceptancePoints",
        "state": "atlasStateNames",
        "interaction": "atlasInteractionNames",
    }
    return mapping.get(kind)


def preferred_behavior_paths(behavior_kind: str, touched_lookup: dict[str, dict], all_paths: list[str]) -> list[str]:
    preferred: list[str] = []
    for path in all_paths:
        item = touched_lookup.get(path, {})
        kind = item.get("snippet_type", "other")
        ui_role = item.get("ui_role", "non_ui")
        if behavior_kind in {"user_flow", "acceptance_point"}:
            if ui_role in {"primary_screen", "auxiliary_dialog", "auxiliary_overlay"}:
                preferred.append(path)
        elif behavior_kind == "interaction":
            if ui_role in {"primary_screen", "auxiliary_dialog", "auxiliary_overlay", "component_view"} or kind == "feature_logic":
                preferred.append(path)
        elif behavior_kind == "state":
            if kind in {"feature_logic", "feature_screen", "feature_view", "feature_service", "feature_model"}:
                preferred.append(path)
    return preferred or all_paths


def classify_generation_alignment(touched_item: dict) -> tuple[str, str]:
    mode = touched_item.get("generation_mode")
    kind = touched_item.get("snippet_type", "other")
    action = touched_item.get("action")
    if not mode:
        return "unknown", "apply_result.json 中缺少 generation_mode。"
    if kind.startswith("feature_"):
        if action == "update" and mode == "swift_extension":
            return "verified", "Update 触点使用了预期的 swift_extension 生成模式。"
        if action == "create" and mode == "swift_file":
            return "verified", "Create 触点使用了预期的 swift_file 生成模式。"
        if mode == "marker_block":
            return "partial", "当前触点回退到了 marker_block，生成模式仍需增强。"
        return "unknown", f"触点类型 `{kind}` 与生成模式 `{mode}` 的组合不在预期范围内。"
    if mode in {"swift_extension", "swift_file", "marker_block"}:
        return "verified", f"通用触点使用了允许的生成模式 `{mode}`。"
    return "unknown", f"无法识别的生成模式 `{mode}`。"


def classify_structure_alignment(requirement: dict, path: str, content: str, touched_item: dict) -> tuple[str, str]:
    kind = touched_item.get("snippet_type", "other")
    mode = touched_item.get("generation_mode")
    ui_role = touched_item.get("ui_role", "non_ui")
    action = touched_item.get("action")
    requirement_id = requirement["id"]
    requirement_name = requirement["name"]
    if mode == "marker_block":
        return "partial", "当前文件使用 marker_block，无法做强结构校验。"

    block = generated_block(content, requirement_id)
    if mode == "swift_extension":
        if not block:
            return "missing", "未找到生成的 Swift extension 代码块。"
        if not re.search(r"\bextension\s+[A-Za-z_][A-Za-z0-9_]*\s*\{", block):
            return "partial", "已找到生成块，但未确认 extension 目标类型。"
        missing_methods = [name for name in expected_method_names_for_touchpoint(kind, ui_role, requirement_name) if f"{name}(" not in block]
        if missing_methods:
            return "partial", f"生成块缺少期望方法：{', '.join(missing_methods)}。"
        if ui_role != "non_ui" and f"ui_role={ui_role}" not in block:
            return "partial", f"生成块缺少 ui_role=`{ui_role}` 标记。"
        if action == "update" and ui_role in HOOKABLE_UI_ROLES:
            install_name = install_method_name(kind, ui_role, sanitize_identifier(requirement_name))
            stripped = content_without_generated_block(content, requirement_id)
            if f"{install_name}()" not in stripped:
                return "partial", f"更新触点缺少 UIKit hook 调用 `{install_name}()`。"
        return "verified", "已确认 extension 目标类型和期望方法。"

    if mode == "swift_file":
        expected_type = infer_create_type_name(path)
        if not re.search(rf"\b(class|struct|enum)\s+{re.escape(expected_type)}\b", content):
            return "partial", f"新文件中未找到期望类型 `{expected_type}`。"
        missing_methods = [name for name in expected_method_names_for_touchpoint(kind, ui_role, requirement_name) if f"{name}(" not in content]
        if missing_methods:
            return "partial", f"新文件缺少期望方法：{', '.join(missing_methods)}。"
        return "verified", "已确认新文件类型和期望方法。"

    return "unknown", "当前生成模式不支持结构级校验。"


def classify_semantic_alignment(requirement: dict, content: str, touched_item: dict) -> tuple[str, str]:
    kind = touched_item.get("snippet_type", "other")
    mode = touched_item.get("generation_mode")
    ui_role = touched_item.get("ui_role", "non_ui")
    requirement_id = requirement["id"]
    requirement_name = requirement["name"]
    if mode == "marker_block":
        return "partial", "当前文件使用 marker_block，无法确认更深层语义骨架。"
    block = generated_block(content, requirement_id)
    if not block:
        return "missing", "未找到可用于语义检查的生成块。"
    helpers = semantic_helper_names(kind, ui_role, requirement_name)
    if not helpers:
        return "verified", "当前触点不要求额外的深语义 helper。"
    missing = [name for name in helpers if name not in block]
    if missing:
        return "partial", f"生成块缺少更深层语义 helper：{', '.join(missing)}。"
    return "verified", "已确认更深层展示 / 状态 / 请求语义骨架。"


def classify_file_result(
    repo_root: Path,
    requirement: dict,
    path: str,
    touched_lookup: dict[str, dict],
) -> dict:
    target_path = repo_root / path
    touched_item = touched_lookup.get(path, {})
    ui_role = touched_item.get("ui_role", "non_ui")
    hook_target = touched_item.get("hook_target")
    if not target_path.exists():
        return {
            "path": path,
            "status": "missing",
            "reason": "Target file does not exist after apply.",
            "ui_role": ui_role,
            "hook_target": hook_target,
            "marker_status": "missing",
            "structure_status": "missing",
            "generation_status": "missing",
        }
    content = read_text_safe(target_path)
    requirement_id = requirement["id"]
    marker_mode = detect_apply_marker(content, requirement_id)
    generation_status, generation_reason = classify_generation_alignment(touched_item) if touched_item else (
        "unknown",
        "File does not exist in apply_result touched_files.",
    )
    structure_status, structure_reason = classify_structure_alignment(requirement, path, content, touched_item) if touched_item else (
        "unknown",
        "File does not exist in apply_result touched_files.",
    )
    semantic_status, semantic_reason = classify_semantic_alignment(requirement, content, touched_item) if touched_item else (
        "unknown",
        "File does not exist in apply_result touched_files.",
    )
    if marker_mode == "generated_patch":
        status = "verified" if generation_status == "verified" and structure_status == "verified" and semantic_status == "verified" else "partial"
        return {
            "path": path,
            "status": status,
            "reason": "Generated Swift patch marker found in file.",
            "ui_role": ui_role,
            "hook_target": hook_target,
            "marker_status": "verified",
            "structure_status": structure_status,
            "generation_status": generation_status,
            "semantic_status": semantic_status,
            "structure_reason": structure_reason,
            "generation_reason": generation_reason,
            "semantic_reason": semantic_reason,
        }
    if path in touched_lookup:
        return {
            "path": path,
            "status": "partial",
            "reason": "File was touched according to apply result, but marker was not found.",
            "ui_role": ui_role,
            "hook_target": hook_target,
            "marker_status": "missing",
            "structure_status": structure_status,
            "generation_status": generation_status,
            "semantic_status": semantic_status,
            "structure_reason": structure_reason,
            "generation_reason": generation_reason,
            "semantic_reason": semantic_reason,
        }
    return {
        "path": path,
        "status": "unknown",
        "reason": "File exists, but verify could not confirm Atlas apply output.",
        "ui_role": ui_role,
        "hook_target": hook_target,
        "marker_status": "unknown",
        "structure_status": "unknown",
        "generation_status": "unknown",
        "semantic_status": "unknown",
    }


def classify_behavior_result(
    requirement_id: str,
    behavior_kind: str,
    behavior: str,
    repo_root: Path,
    paths: list[str],
    touched_lookup: dict[str, dict],
) -> tuple[str, str]:
    array_name = behavior_array_name(behavior_kind)
    candidate_paths = preferred_behavior_paths(behavior_kind, touched_lookup, paths)
    for path in candidate_paths:
        target_path = repo_root / path
        if not target_path.exists():
            continue
        content = read_text_safe(target_path)
        marker_mode = detect_apply_marker(content, requirement_id)
        if marker_mode == "generated_patch":
            block = generated_block(content, requirement_id)
            if array_name and behavior in extract_array_items(block, array_name):
                return "verified", f"Behavior mapped inside `{array_name}` in `{path}`."
            if behavior in block:
                return "partial", f"Behavior text exists in generated block of `{path}`, but not in `{array_name}`."
    if candidate_paths:
        return "unknown", f"Behavior mapping was not found in preferred touched files: {', '.join(candidate_paths[:3])}."
    return "missing", "No touched files were available for behavior verification."


def coverage_label(statuses: list[str]) -> str:
    if not statuses:
        return "unknown"
    if all(item == "verified" for item in statuses):
        return "verified"
    if any(item == "missing" for item in statuses):
        return "missing"
    if any(item in {"partial", "unknown"} for item in statuses):
        return "partial"
    return "unknown"


def syntax_coverage_label(statuses: list[str], enabled: bool) -> str:
    if not enabled:
        return "skipped"
    if not statuses:
        return "unknown"
    if all(item == "verified" for item in statuses):
        return "verified"
    if any(item == "missing" for item in statuses):
        return "missing"
    if any(item in {"partial", "unknown"} for item in statuses):
        return "partial"
    return "unknown"


def compute_data_layer_coverage(contract: dict, apply_result: dict) -> tuple[str, str]:
    api_calls = contract.get("flutter_evidence", {}).get("api_calls", [])
    models = contract.get("flutter_evidence", {}).get("models", [])
    touched = apply_result.get("touched_files", [])
    touched_kinds = {item.get("snippet_type", "other") for item in touched}
    if not api_calls and not models:
        return "skipped", "Flutter evidence does not require data-layer touchpoints."
    if api_calls and any(kind in {"feature_logic", "feature_service"} for kind in touched_kinds):
        return "verified", "Planner / Apply included service or logic touchpoints for Flutter API evidence."
    if models and "feature_model" in touched_kinds:
        return "partial", "Only model touchpoints were covered; service / logic touchpoints are still missing."
    return "missing", "Flutter evidence includes api/model signals, but apply did not touch service / logic / model files."


def classify_swift_parse_result(repo_root: Path, path: str) -> dict:
    target_path = repo_root / path
    if target_path.suffix != ".swift":
        return {"path": path, "status": "skipped", "reason": "Only Swift files are eligible for parse checks."}
    if not target_path.exists():
        return {"path": path, "status": "missing", "reason": "Target file does not exist for parse check."}
    if shutil.which("xcrun") is None:
        return {"path": path, "status": "unknown", "reason": "`xcrun` is not available in the current environment."}
    command = ["xcrun", "swiftc", "-parse", str(target_path)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode == 0:
        return {"path": path, "status": "verified", "reason": "`swiftc -parse` passed."}
    raw_lines = (completed.stderr or completed.stdout or "").strip().splitlines()
    error_lines = [
        line
        for line in raw_lines
        if line.strip() and "DVTFilePathFSEvents" not in line and "Requested but did not find extension point" not in line
    ]
    preview = error_lines[0] if error_lines else raw_lines[0] if raw_lines else "`swiftc -parse` failed with no diagnostic output."
    return {"path": path, "status": "partial", "reason": preview[:220]}


def render_verify_report(result: dict) -> str:
    requirement = result["requirement"]
    lines = [
        f"# Verify Report: {requirement['name']}",
        "",
        "## 1. 验证概览",
        "",
        f"- Requirement ID: `{requirement['id']}`",
        f"- Requirement Name: `{requirement['name']}`",
        f"- Verify Status: `{result['verify_status']}`",
        f"- File Coverage: `{result['file_coverage']}`",
        f"- Behavior Coverage: `{result['behavior_coverage']}`",
        f"- Structure Coverage: `{result['structure_coverage']}`",
        f"- Generation Coverage: `{result['generation_coverage']}`",
        f"- Semantic Coverage: `{result['semantic_coverage']}`",
        f"- Data Layer Coverage: `{result['data_layer_coverage']}`",
        f"- Swift Parse Coverage: `{result['syntax_coverage']}`",
        "",
        "## 2. 文件覆盖结果",
        "",
        "### 已验证文件",
        "",
    ]
    verified_files = [item for item in result["file_results"] if item["status"] in {"verified", "partial"}]
    if not verified_files:
        lines.append("- None")
    else:
        lines.extend(
            f"- `{item['path']}`: `{item['status']}` | ui_role=`{item.get('ui_role', 'non_ui')}` | hook=`{item.get('hook_target') or 'none'}`"
            for item in verified_files
        )
    lines.extend(["", "### 缺失或未确认文件", ""])
    missing_files = [item for item in result["file_results"] if item["status"] in {"missing", "unknown"}]
    if not missing_files:
        lines.append("- None")
    else:
        lines.extend(f"- `{item['path']}`: `{item['status']}` | {item['reason']}" for item in missing_files)
    lines.extend(["", "## 3. 结构与生成模式校验", "", "### 结构已验证文件", ""])
    structure_verified = [item for item in result["file_results"] if item.get("structure_status") == "verified"]
    if not structure_verified:
        lines.append("- None")
    else:
        lines.extend(f"- `{item['path']}`: `{item['structure_status']}`" for item in structure_verified)
    lines.extend(["", "### 结构待补强文件", ""])
    structure_pending = [item for item in result["file_results"] if item.get("structure_status") in {"partial", "missing", "unknown"}]
    if not structure_pending:
        lines.append("- None")
    else:
        lines.extend(
            f"- `{item['path']}`: `{item.get('structure_status', 'unknown')}` | ui_role=`{item.get('ui_role', 'non_ui')}` | hook=`{item.get('hook_target') or 'none'}` | {item.get('structure_reason', item['reason'])}"
            for item in structure_pending
        )
    lines.extend(["", "### 生成模式校验", ""])
    generation_pending = [item for item in result["file_results"] if item.get("generation_status") != "verified"]
    if not generation_pending:
        lines.append("- All touched files passed generation mode checks")
    else:
        lines.extend(
            f"- `{item['path']}`: `{item.get('generation_status', 'unknown')}` | {item.get('generation_reason', 'No generation detail')}"
            for item in generation_pending
        )
    lines.extend(["", "### 语义深度校验", ""])
    semantic_pending = [item for item in result["file_results"] if item.get("semantic_status") != "verified"]
    if not semantic_pending:
        lines.append("- All touched files passed semantic-depth checks")
    else:
        lines.extend(
            f"- `{item['path']}`: `{item.get('semantic_status', 'unknown')}` | {item.get('semantic_reason', 'No semantic detail')}"
            for item in semantic_pending
        )
    lines.extend(["", "### Swift 语法检查", ""])
    syntax_results = result.get("syntax_results", [])
    if not syntax_results:
        lines.append("- Not enabled")
    else:
        lines.extend(
            f"- `{item['path']}`: `{item['status']}` | {item['reason']}"
            for item in syntax_results
        )
    lines.extend(["", "## 4. 行为覆盖结果", "", "### 已覆盖行为", ""])
    verified_behaviors = [item for item in result["behavior_results"] if item["status"] == "verified"]
    if not verified_behaviors:
        lines.append("- None")
    else:
        lines.extend(f"- [{item.get('kind', 'behavior')}] {item['behavior']}: `verified`" for item in verified_behaviors)
    lines.extend(["", "### 部分覆盖行为", ""])
    partial_behaviors = [item for item in result["behavior_results"] if item["status"] == "partial"]
    if not partial_behaviors:
        lines.append("- None")
    else:
        lines.extend(
            f"- [{item.get('kind', 'behavior')}] {item['behavior']}: `partial` | {item['reason']}"
            for item in partial_behaviors
        )
    lines.extend(["", "### 未覆盖或无法确认行为", ""])
    missing_behaviors = [item for item in result["behavior_results"] if item["status"] in {"missing", "unknown"}]
    if not missing_behaviors:
        lines.append("- None")
    else:
        lines.extend(
            f"- [{item.get('kind', 'behavior')}] {item['behavior']}: `{item['status']}` | {item['reason']}"
            for item in missing_behaviors
        )
    lines.extend(["", "## 5. 人工项与不支持项", "", "### 人工项", ""])
    if not result["manual_items"]:
        lines.append("- None")
    else:
        lines.extend(f"- `{item}`" for item in result["manual_items"])
    lines.extend(["", "### 不支持项", ""])
    if not result["unsupported"]:
        lines.append("- None")
    else:
        lines.extend(f"- {item}" for item in result["unsupported"])
    lines.extend(["", "### 数据层触点覆盖", ""])
    lines.append(f"- `{result['data_layer_coverage']}` | {result['data_layer_reason']}")
    lines.extend(["", "## 6. 偏差与缺口", ""])
    if not result["gaps"]:
        lines.append("- None")
    else:
        lines.extend(f"- {item}" for item in result["gaps"])
    lines.extend(
        [
            "",
            "## 7. 验证结论",
            "",
            f"- Overall Result: `{result['verify_status']}`",
            "- Summary:",
        ]
    )
    lines.extend(f"  - {item}" for item in result["summary"])
    lines.extend(["", "## 8. 下一步建议", ""])
    lines.extend(f"- {item}" for item in result["next_steps"])
    return "\n".join(lines)


def handle_verify(args: argparse.Namespace) -> int:
    inputs = build_inputs(args)
    ensure_run_dir(inputs.run_dir)
    result_path = inputs.run_dir / VERIFY_RESULT_FILE
    if result_path.exists() and not inputs.force:
        raise FileExistsError(f"verify result already exists: {result_path} (use --force to overwrite)")

    contract = load_contract(inputs.run_dir)
    operation_plan = load_operation_plan(inputs.run_dir)
    ensure_operation_contract_consistency(operation_plan, contract)
    operations = iter_operations(operation_plan)
    apply_result = load_apply_result(inputs.run_dir)
    repo_root = resolve_repo_root(contract, inputs.repo_root)
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"repo root not found or unreadable: {repo_root}")

    requirement = contract["requirement"]
    touched_lookup = {item["path"]: item for item in apply_result.get("touched_files", [])}
    planned_files = [item["path"] for item in operations if item["action"] in {"create", "update"}]
    file_results = []
    for path in planned_files:
        file_results.append(classify_file_result(repo_root, requirement, path, touched_lookup))

    touched_paths = [item["path"] for item in apply_result.get("touched_files", [])]
    behaviors: list[dict] = []
    for item in contract.get("behavior", {}).get("user_flows", []):
        behaviors.append({"kind": "user_flow", "value": item})
    for item in contract.get("behavior", {}).get("acceptance_points", []):
        behaviors.append({"kind": "acceptance_point", "value": item})
    for item in contract.get("behavior", {}).get("states", []):
        name = item.get("name")
        if name:
            behaviors.append({"kind": "state", "value": name})
    for item in contract.get("behavior", {}).get("interactions", []):
        behaviors.append({"kind": "interaction", "value": item})
    behavior_results = []
    for item in behaviors:
        status, reason = classify_behavior_result(
            requirement["id"],
            item["kind"],
            item["value"],
            repo_root,
            touched_paths,
            touched_lookup,
        )
        behavior_results.append(
            {
                "behavior": item["value"],
                "kind": item["kind"],
                "status": status,
                "reason": reason,
            }
        )

    file_coverage = coverage_label([item["status"] for item in file_results])
    behavior_coverage = coverage_label([item["status"] for item in behavior_results])
    structure_coverage = coverage_label([item.get("structure_status", "unknown") for item in file_results])
    generation_coverage = coverage_label([item.get("generation_status", "unknown") for item in file_results])
    semantic_coverage = coverage_label([item.get("semantic_status", "unknown") for item in file_results])
    data_layer_coverage, data_layer_reason = compute_data_layer_coverage(contract, apply_result)
    syntax_results = []
    if inputs.swift_parse_check:
        for path in planned_files:
            syntax_results.append(classify_swift_parse_result(repo_root, path))
    syntax_coverage = syntax_coverage_label([item["status"] for item in syntax_results], inputs.swift_parse_check)

    gaps: list[str] = []
    if apply_result.get("apply_status") == "aborted":
        gaps.append("Apply 阶段已中止，验证结果不能视为完整。")
    gaps.extend(apply_result.get("deviations", []))
    gaps.extend(item["reason"] for item in file_results if item["status"] in {"missing", "unknown"})
    gaps.extend(
        item["structure_reason"]
        for item in file_results
        if item.get("structure_status") in {"missing", "unknown", "partial"} and item.get("structure_reason")
    )
    gaps.extend(
        item["generation_reason"]
        for item in file_results
        if item.get("generation_status") in {"missing", "unknown", "partial"} and item.get("generation_reason")
    )
    gaps.extend(
        item["semantic_reason"]
        for item in file_results
        if item.get("semantic_status") in {"missing", "unknown", "partial"} and item.get("semantic_reason")
    )
    gaps.extend(item["reason"] for item in behavior_results if item["status"] == "partial")
    gaps.extend(item["reason"] for item in behavior_results if item["status"] in {"missing", "unknown"})
    gaps.extend(
        item["reason"]
        for item in syntax_results
        if item["status"] in {"partial", "missing", "unknown"}
    )
    if data_layer_coverage in {"partial", "missing"}:
        gaps.append(data_layer_reason)

    if (
        file_coverage == "verified"
        and behavior_coverage == "verified"
        and structure_coverage == "verified"
        and generation_coverage == "verified"
        and semantic_coverage == "verified"
        and data_layer_coverage in {"verified", "skipped"}
        and syntax_coverage in {"verified", "skipped"}
        and apply_result.get("apply_status") == "completed"
    ):
        verify_status = "verified"
    elif apply_result.get("apply_status") == "aborted" or file_coverage == "missing":
        verify_status = "failed"
    else:
        verify_status = "partial"

    summary = [
        f"文件覆盖结果为 `{file_coverage}`。",
        f"行为覆盖结果为 `{behavior_coverage}`。",
        f"结构校验结果为 `{structure_coverage}`。",
        f"生成模式校验结果为 `{generation_coverage}`。",
        f"语义深度校验结果为 `{semantic_coverage}`。",
        f"数据层触点覆盖结果为 `{data_layer_coverage}`。",
        f"Swift 语法检查结果为 `{syntax_coverage}`。",
    ]
    manual_items = [item["path"] for item in operations if item["action"] == "manual"]
    if manual_items:
        summary.append("仍存在人工保留项。")

    next_steps = []
    if verify_status == "verified":
        next_steps.append("进入人工验收或后续集成测试。")
    elif syntax_coverage in {"partial", "missing", "unknown"} and all(
        coverage == "verified"
        for coverage in [file_coverage, behavior_coverage, structure_coverage, generation_coverage]
    ):
        next_steps.append("修复 Swift 语法问题后重新执行 Atlas Verify。")
    elif verify_status == "partial":
        next_steps.append("补齐缺失触点后重新执行 Atlas Apply / Verify。")
    else:
        next_steps.append("回到 Atlas Planner 重新收敛触点和 patch 计划。")

    result = {
        "requirement": {
            "id": requirement["id"],
            "name": requirement["name"],
        },
        "verify_status": verify_status,
        "file_coverage": file_coverage,
        "behavior_coverage": behavior_coverage,
        "structure_coverage": structure_coverage,
        "generation_coverage": generation_coverage,
        "semantic_coverage": semantic_coverage,
        "data_layer_coverage": data_layer_coverage,
        "data_layer_reason": data_layer_reason,
        "syntax_coverage": syntax_coverage,
        "file_results": file_results,
        "behavior_results": behavior_results,
        "syntax_results": syntax_results,
        "manual_items": manual_items,
        "unsupported": contract.get("unsupported", []),
        "gaps": gaps,
        "summary": summary,
        "next_steps": next_steps,
    }

    write_text(inputs.run_dir / VERIFY_REPORT_FILE, render_verify_report(result))
    write_text(inputs.run_dir / VERIFY_RESULT_FILE, json.dumps(result, ensure_ascii=False, indent=2))
    print("Verify completed.")
    print(f"- run_dir: {inputs.run_dir}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        print("Verify status: missing-run")
        return 0
    result_path = run_dir / VERIFY_RESULT_FILE
    report_path = run_dir / VERIFY_REPORT_FILE
    print("Verify status: present" if result_path.exists() else "Verify status: pending")
    print(f"- {VERIFY_RESULT_FILE}: {'yes' if result_path.exists() else 'no'}")
    print(f"- {VERIFY_REPORT_FILE}: {'yes' if report_path.exists() else 'no'}")
    if result_path.exists():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        print(f"- verify_status: {payload.get('verify_status', 'unknown')}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "verify":
            return handle_verify(args)
        if args.command == "status":
            return handle_status(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 5
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"atlas-verify error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
