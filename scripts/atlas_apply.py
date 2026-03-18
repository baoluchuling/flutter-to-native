#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


REQUIRED_RUN_FILES = {
    "requirement_sync_contract.yaml",
    "native_operation_plan.yaml",
    "sync_plan.md",
    "touchpoints.md",
    "risk_report.md",
}

APPLY_RESULT_FILE = "apply_result.json"
APPLY_REPORT_FILE = "apply_report.md"
GENERATED_MARKER_PREFIX = "T2N Atlas Generated Patch Start"
HOOKABLE_UI_ROLES = {"primary_screen", "auxiliary_dialog", "auxiliary_overlay", "component_view"}


@dataclass
class ApplyInputs:
    run_dir: Path
    repo_root: Path | None
    approved: bool
    force: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Apply for approved requirement sync plans")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply", help="Apply an approved sync plan to the target repository")
    apply_parser.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    apply_parser.add_argument("--repo-root", help="Optional override for target repository root")
    apply_parser.add_argument("--approved", action="store_true", help="Required flag to confirm the plan was approved")
    apply_parser.add_argument("--force", action="store_true", help="Overwrite an existing apply result")

    status_parser = subparsers.add_parser("status", help="Report apply status for a run directory")
    status_parser.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")

    return parser


def ensure_run_dir(run_dir: Path) -> None:
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"run dir not found or unreadable: {run_dir}")
    missing = [name for name in REQUIRED_RUN_FILES if not (run_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"run dir missing required files: {', '.join(missing)}")


def build_inputs(args: argparse.Namespace) -> ApplyInputs:
    return ApplyInputs(
        run_dir=Path(args.run_dir).expanduser().resolve(),
        repo_root=Path(args.repo_root).expanduser().resolve() if getattr(args, "repo_root", None) else None,
        approved=bool(getattr(args, "approved", False)),
        force=bool(getattr(args, "force", False)),
    )


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


def resolve_repo_root(contract: dict, override_repo_root: Path | None) -> Path:
    if override_repo_root:
        return override_repo_root
    repo_root = contract.get("target", {}).get("repo_root")
    if not repo_root:
        raise FileNotFoundError("contract missing target.repo_root")
    return Path(repo_root).expanduser().resolve()


def ensure_repo_root(repo_root: Path) -> None:
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"repo root not found or unreadable: {repo_root}")


def ensure_apply_allowed(inputs: ApplyInputs) -> None:
    if not inputs.approved:
        raise PermissionError("apply requires --approved to confirm the reviewed plan")
    result_path = inputs.run_dir / APPLY_RESULT_FILE
    if result_path.exists() and not inputs.force:
        raise FileExistsError(f"apply result already exists: {result_path} (use --force to overwrite)")


def comment_prefix(path: Path) -> str:
    if path.suffix in {".swift", ".kt", ".java", ".dart", ".m", ".mm", ".h"}:
        return "//"
    if path.suffix in {".md", ".txt", ".yaml", ".yml"}:
        return "#"
    return "//"


def sanitize_identifier(value: str) -> str:
    identifier = re.sub(r"[^a-zA-Z0-9_]+", "_", value)
    identifier = re.sub(r"_+", "_", identifier).strip("_")
    if not identifier:
        return "atlas_requirement"
    if identifier[0].isdigit():
        identifier = f"atlas_{identifier}"
    return identifier


def extract_primary_swift_type(text: str) -> str | None:
    pattern = re.compile(r"^\s*(?:public|open|internal|private|fileprivate)?\s*(?:final\s+)?(class|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
    match = pattern.search(text)
    if match:
        return match.group(2)
    return None


def touchpoint_kind_map(contract: dict) -> dict[str, str]:
    return {
        item["path"]: item.get("kind", "other")
        for item in contract.get("native_impact", {}).get("selected_touchpoints", [])
    }


def touchpoint_meta_map(contract: dict) -> dict[str, dict]:
    return {
        item["path"]: item
        for item in contract.get("native_impact", {}).get("selected_touchpoints", [])
    }


def generated_marker(requirement_id: str) -> str:
    return f"{GENERATED_MARKER_PREFIX} [{requirement_id}]"


def build_patch_block(contract: dict, relative_path: str, meta: dict | None = None) -> str:
    requirement = contract["requirement"]
    behavior = contract.get("behavior", {})
    source = contract.get("source", {})
    meta = meta or {}
    prefix = comment_prefix(Path(relative_path))
    lines = [
        f"{prefix} T2N Atlas Apply Start [{requirement['id']}]",
        f"{prefix} Requirement: {requirement['name']}",
        f"{prefix} Summary: {requirement['summary']}",
        f"{prefix} Target File: {relative_path}",
        f"{prefix} UI Role: {meta.get('ui_role', 'non_ui')}",
        f"{prefix} Source Basis: {', '.join(source.get('change_basis', [])) or 'unknown'}",
    ]
    source_screens = meta.get("source_screens") or []
    if source_screens:
        lines.append(f"{prefix} Source Screens: {', '.join(source_screens)}")
    for item in behavior.get("user_flows", [])[:3]:
        lines.append(f"{prefix} User Flow: {item}")
    for item in behavior.get("acceptance_points", [])[:5]:
        lines.append(f"{prefix} Acceptance: {item}")
    lines.append(f"{prefix} T2N Atlas Apply End [{requirement['id']}]")
    return "\n".join(lines) + "\n"


def swift_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_swift_array(name: str, items: list[str], indent: str = "        ") -> list[str]:
    if not items:
        return [f"{indent}let {name}: [String] = []"]
    lines = [f"{indent}let {name}: [String] = ["]
    lines.extend(f"{indent}    {swift_string_literal(item)}," for item in items)
    lines.append(f"{indent}]")
    return lines


def extension_method_name(kind: str, ui_role: str, requirement_slug: str) -> str:
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


def extension_payload_name(kind: str, ui_role: str, requirement_slug: str) -> str:
    role_suffix = {
        "primary_screen": "PrimaryScreenPayload",
        "auxiliary_dialog": "AuxiliaryDialogPayload",
        "auxiliary_overlay": "AuxiliaryOverlayPayload",
        "component_view": "ComponentViewPayload",
    }.get(ui_role)
    if role_suffix:
        return f"atlasSync{role_suffix}_{requirement_slug}"
    suffix = {
        "feature_screen": "ScreenPayload",
        "feature_logic": "LogicPayload",
        "feature_view": "ViewPayload",
        "feature_service": "ServicePayload",
        "feature_model": "ModelPayload",
    }.get(kind, "RequirementPayload")
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


def hook_anchor_candidates(kind: str, ui_role: str) -> list[str]:
    if ui_role == "primary_screen":
        return ["viewDidLoad", "setupViews", "setupView", "setupUI", "bind", "refresh", "init_frame", "init"]
    if ui_role == "auxiliary_dialog":
        return ["show", "present", "init_frame", "init", "layoutSubviews"]
    if ui_role == "auxiliary_overlay":
        return ["refresh", "update", "layoutSubviews", "addNotifiy", "init_frame", "init"]
    if ui_role == "component_view":
        if kind == "feature_screen":
            return ["viewDidLoad", "setupViews", "setupView", "setupUI", "bind", "refresh", "init_frame", "init"]
        return ["setupViews", "setupView", "setupUI", "init_frame", "init", "layoutSubviews"]
    if kind == "feature_screen":
        return ["viewDidLoad", "setupViews", "setupView", "setupUI", "bind", "refresh"]
    if kind == "feature_view":
        return ["init_frame", "init", "layoutSubviews"]
    return []


def hook_anchor_pattern(anchor: str) -> re.Pattern[str]:
    patterns = {
        "viewDidLoad": r"^(\s*)(?:override\s+)?func\s+viewDidLoad\s*\([^)]*\)\s*\{",
        "setupViews": r"^(\s*)(?:private\s+|fileprivate\s+|internal\s+)?func\s+setupViews\s*\([^)]*\)\s*\{",
        "setupView": r"^(\s*)(?:private\s+|fileprivate\s+|internal\s+)?func\s+setupView\s*\([^)]*\)\s*\{",
        "setupUI": r"^(\s*)(?:private\s+|fileprivate\s+|internal\s+)?func\s+setupUI\s*\([^)]*\)\s*\{",
        "bind": r"^(\s*)(?:private\s+|fileprivate\s+|internal\s+)?func\s+bind(?:ViewModel)?\s*\([^)]*\)\s*\{",
        "refresh": r"^(\s*)(?:override\s+)?func\s+refresh\s*\([^)]*\)\s*\{",
        "update": r"^(\s*)(?:override\s+)?func\s+update\s*\([^)]*\)\s*\{",
        "addNotifiy": r"^(\s*)(?:override\s+)?func\s+addNotifiy\s*\([^)]*\)\s*\{",
        "layoutSubviews": r"^(\s*)(?:override\s+)?func\s+layoutSubviews\s*\([^)]*\)\s*\{",
        "show": r"^(\s*)(?:private\s+|fileprivate\s+|internal\s+)?func\s+show[A-Za-z0-9_]*\s*\([^)]*\)\s*\{",
        "present": r"^(\s*)(?:private\s+|fileprivate\s+|internal\s+)?func\s+present[A-Za-z0-9_]*\s*\([^)]*\)\s*\{",
        "init_frame": r"^(\s*)(?:override\s+)?init\s*\(\s*frame\s*:\s*CGRect\s*\)\s*\{",
        "init": r"^(\s*)(?:override\s+)?init\s*\([^)]*\)\s*\{",
    }
    return re.compile(patterns[anchor])


def preferred_super_tokens(anchor: str) -> tuple[str, ...]:
    mapping = {
        "viewDidLoad": ("super.viewDidLoad()",),
        "refresh": ("super.refresh()",),
        "layoutSubviews": ("super.layoutSubviews()",),
        "init_frame": ("super.init(frame: frame)", "super.init(frame:"),
        "init": ("super.init()", "super.init("),
    }
    return mapping.get(anchor, ())


def find_method_block(lines: list[str], start_index: int) -> int:
    depth = lines[start_index].count("{") - lines[start_index].count("}")
    end_index = start_index
    while depth > 0 and end_index + 1 < len(lines):
        end_index += 1
        depth += lines[end_index].count("{") - lines[end_index].count("}")
    return end_index


def inject_install_hook(existing: str, call_name: str, kind: str, ui_role: str) -> tuple[str, str | None, bool]:
    if not existing.strip():
        return existing, None, False
    call_line = f"{call_name}()"
    if call_line in existing:
        return existing, "existing_call", False

    lines = existing.splitlines()
    for anchor in hook_anchor_candidates(kind, ui_role):
        pattern = hook_anchor_pattern(anchor)
        for index, line in enumerate(lines):
            match = pattern.match(line)
            if not match:
                continue
            indent = match.group(1) + "    "
            end_index = find_method_block(lines, index)
            insert_at = index + 1
            preferred_tokens = preferred_super_tokens(anchor)
            for body_index in range(index + 1, end_index):
                body_line = lines[body_index]
                if call_line in body_line:
                    return existing, anchor, False
                if preferred_tokens and any(token in body_line for token in preferred_tokens):
                    insert_at = body_index + 1
                    break
            lines.insert(insert_at, f"{indent}{call_line}")
            return "\n".join(lines) + "\n", anchor, True
    return existing, None, False


def build_generated_swift_extension(
    contract: dict,
    relative_path: str,
    kind: str,
    target_type: str,
    ui_role: str,
    source_screens: list[str],
) -> str:
    requirement = contract["requirement"]
    behavior = contract.get("behavior", {})
    source = contract.get("source", {})
    requirement_slug = sanitize_identifier(requirement["name"])
    method_name = extension_method_name(kind, ui_role, requirement_slug)
    payload_name = extension_payload_name(kind, ui_role, requirement_slug)
    state_names = [item["name"] for item in behavior.get("states", [])]
    render_name = render_method_name(ui_role, requirement_slug)
    interaction_name = interaction_method_name(ui_role, requirement_slug)
    request_name = f"atlasSyncRequests_{requirement_slug}"
    primary_state_flags_name = f"atlasSyncPrimaryStateFlags_{requirement_slug}"
    primary_copy_name = f"atlasSyncPrimaryCopy_{requirement_slug}"
    primary_cta_name = f"atlasSyncPrimaryCTA_{requirement_slug}"
    dialog_presentation_name = f"atlasSyncDialogPresentation_{requirement_slug}"
    dialog_cta_name = f"atlasSyncDialogCTA_{requirement_slug}"
    overlay_state_name = f"atlasSyncOverlayState_{requirement_slug}"
    overlay_copy_name = f"atlasSyncOverlayCopy_{requirement_slug}"
    component_copy_name = f"atlasSyncComponentCopy_{requirement_slug}"
    logic_context_name = f"atlasSyncLogicContext_{requirement_slug}"
    logic_state_graph_name = f"atlasSyncLogicStateGraph_{requirement_slug}"
    service_payload_name = f"atlasSyncServiceRequestPayload_{requirement_slug}"
    service_response_name = f"atlasSyncServiceResponseFields_{requirement_slug}"
    model_field_map_name = f"atlasSyncModelFieldMap_{requirement_slug}"
    model_defaults_name = f"atlasSyncModelDefaults_{requirement_slug}"
    lines = [
        f"// {generated_marker(requirement['id'])}",
        f"// kind={kind} ui_role={ui_role} mode=swift_extension target={relative_path}",
        f"// source_screens={', '.join(source_screens) if source_screens else 'none'}",
        f"extension {target_type} {{",
        f"    func {method_name}() {{",
        f"        let {payload_name} = {swift_string_literal(requirement['summary'])}",
        *build_swift_array("atlasUserFlows", behavior.get("user_flows", [])),
        *build_swift_array("atlasAcceptancePoints", behavior.get("acceptance_points", [])),
        *build_swift_array("atlasStateNames", state_names),
        *build_swift_array("atlasInteractionNames", behavior.get("interactions", [])),
        *build_swift_array("atlasStringKeys", behavior.get("strings", [])),
        *build_swift_array("atlasAssetPaths", behavior.get("assets", [])),
        *build_swift_array("atlasChangeBasis", source.get("change_basis", [])),
        *build_swift_array("atlasSourceScreens", source_screens),
        f"        _ = {payload_name}",
        "        _ = atlasUserFlows",
        "        _ = atlasAcceptancePoints",
        "        _ = atlasStateNames",
        "        _ = atlasInteractionNames",
        "        _ = atlasStringKeys",
        "        _ = atlasAssetPaths",
        "        _ = atlasChangeBasis",
        "        _ = atlasSourceScreens",
    ]
    if ui_role == "primary_screen":
        lines.extend(
            [
                f"        let atlasStateFlags = {primary_state_flags_name}(atlasStateNames)",
                f"        let atlasDisplayCopy = {primary_copy_name}(atlasStringKeys)",
                f"        let atlasPrimaryCTA = {primary_cta_name}(atlasStringKeys, interactions: atlasInteractionNames)",
                f"        {render_name}(atlasStateNames, strings: atlasStringKeys, assets: atlasAssetPaths)",
                f"        {interaction_name}(atlasInteractionNames)",
                "    }",
                "",
                f"    func {render_name}(_ states: [String], strings: [String], assets: [String]) {{",
                f"        let atlasStateFlags = {primary_state_flags_name}(states)",
                f"        let atlasDisplayCopy = {primary_copy_name}(strings)",
                f"        let atlasPrimaryCTA = {primary_cta_name}(strings, interactions: atlasInteractionNames)",
                "        _ = atlasStateFlags",
                "        _ = atlasDisplayCopy",
                "        _ = atlasPrimaryCTA",
                "        _ = assets",
                "    }",
                "",
                f"    func {interaction_name}(_ interactions: [String]) {{",
                f"        let atlasPrimaryCTA = {primary_cta_name}(atlasStringKeys, interactions: interactions)",
                "        _ = atlasPrimaryCTA",
                "    }",
                "",
                f"    private func {primary_state_flags_name}(_ states: [String]) -> [String: Bool] {{",
                "        return [",
                '            "loading": states.contains(where: { $0.lowercased().contains("loading") }),',
                '            "error": states.contains(where: { $0.lowercased().contains("error") || $0.lowercased().contains("fail") }),',
                '            "ready": states.contains(where: { $0.lowercased().contains("success") || $0.lowercased().contains("ready") || $0.lowercased().contains("loaded") }),',
                "        ]",
                "    }",
                "",
                f"    private func {primary_copy_name}(_ strings: [String]) -> [String: String] {{",
                "        let title = strings.first ?? \"\"",
                "        let subtitle = strings.dropFirst().first ?? \"\"",
                "        let footnote = strings.dropFirst(2).first ?? \"\"",
                "        return [",
                '            "title": title,',
                '            "subtitle": subtitle,',
                '            "footnote": footnote,',
                "        ]",
                "    }",
                "",
                f"    private func {primary_cta_name}(_ strings: [String], interactions: [String]) -> [String: String] {{",
                "        let primaryTitle = strings.first(where: { item in",
                '            let lower = item.lowercased()',
                '            return lower.contains("join") || lower.contains("unlock") || lower.contains("purchase") || lower.contains("retry")',
                "        }) ?? (strings.first ?? \"Continue\")",
                "        return [",
                '            "title": primaryTitle,',
                '            "interaction": interactions.first ?? "onTap",',
                "        ]",
                "    }",
                "",
                "    private var atlasInteractionNames: [String] {",
                "        return []",
                "    }",
            ]
        )
    elif ui_role == "auxiliary_dialog":
        lines.extend(
            [
                f"        let atlasDialogPresentation = {dialog_presentation_name}(atlasStringKeys)",
                f"        let atlasDialogCTA = {dialog_cta_name}(atlasStringKeys, interactions: atlasInteractionNames)",
                f"        {render_name}(atlasStringKeys, states: atlasStateNames)",
                f"        {interaction_name}(atlasInteractionNames)",
                "    }",
                "",
                f"    func {render_name}(_ strings: [String], states: [String]) {{",
                f"        let atlasDialogPresentation = {dialog_presentation_name}(strings)",
                f"        let atlasDialogCTA = {dialog_cta_name}(strings, interactions: atlasInteractionNames)",
                "        _ = atlasDialogPresentation",
                "        _ = atlasDialogCTA",
                "        _ = states",
                "    }",
                "",
                f"    func {interaction_name}(_ interactions: [String]) {{",
                f"        let atlasDialogCTA = {dialog_cta_name}(atlasStringKeys, interactions: interactions)",
                "        _ = atlasDialogCTA",
                "    }",
                "",
                f"    private func {dialog_presentation_name}(_ strings: [String]) -> [String: String] {{",
                "        let title = strings.first ?? \"Unlock\"",
                "        let message = strings.dropFirst().first ?? \"\"",
                "        return [",
                '            "title": title,',
                '            "message": message,',
                '            "secondary": strings.dropFirst(2).first ?? "",',
                "        ]",
                "    }",
                "",
                f"    private func {dialog_cta_name}(_ strings: [String], interactions: [String]) -> [String: String] {{",
                "        let primaryTitle = strings.first(where: { item in",
                '            let lower = item.lowercased()',
                '            return lower.contains("join") || lower.contains("unlock") || lower.contains("purchase")',
                "        }) ?? (strings.first ?? \"Confirm\")",
                "        return [",
                '            "primary": primaryTitle,',
                '            "secondary": strings.first(where: { $0.lowercased().contains("retry") || $0.lowercased().contains("sign in") }) ?? "",',
                '            "interaction": interactions.first ?? "onTap",',
                "        ]",
                "    }",
                "",
                "    private var atlasStringKeys: [String] {",
                "        return []",
                "    }",
                "",
                "    private var atlasInteractionNames: [String] {",
                "        return []",
                "    }",
            ]
        )
    elif ui_role == "auxiliary_overlay":
        lines.extend(
            [
                f"        let atlasOverlayState = {overlay_state_name}(atlasStateNames)",
                f"        let atlasOverlayCopy = {overlay_copy_name}(atlasStringKeys)",
                f"        {render_name}(atlasStateNames, assets: atlasAssetPaths)",
                f"        {interaction_name}(atlasInteractionNames)",
                "    }",
                "",
                f"    func {render_name}(_ states: [String], assets: [String]) {{",
                f"        let atlasOverlayState = {overlay_state_name}(states)",
                f"        let atlasOverlayCopy = {overlay_copy_name}(atlasStringKeys)",
                "        _ = atlasOverlayState",
                "        _ = atlasOverlayCopy",
                "        _ = assets",
                "    }",
                "",
                f"    func {interaction_name}(_ interactions: [String]) {{",
                f"        let atlasOverlayCopy = {overlay_copy_name}(atlasStringKeys)",
                "        _ = atlasOverlayCopy",
                "        _ = interactions",
                "    }",
                "",
                f"    private func {overlay_state_name}(_ states: [String]) -> [String: Bool] {{",
                "        return [",
                '            "shouldDisplay": !states.contains(where: { $0.lowercased().contains("error") }),',
                '            "isLoading": states.contains(where: { $0.lowercased().contains("loading") }),',
                "        ]",
                "    }",
                "",
                f"    private func {overlay_copy_name}(_ strings: [String]) -> [String: String] {{",
                "        return [",
                '            "badge": strings.first ?? "",',
                '            "hint": strings.dropFirst().first ?? "",',
                "        ]",
                "    }",
                "",
                "    private var atlasStringKeys: [String] {",
                "        return []",
                "    }",
            ]
        )
    elif kind == "feature_logic":
        lines.extend(
            [
                f"        let atlasLogicContext = {logic_context_name}(atlasChangeBasis, interactions: atlasInteractionNames)",
                f"        let atlasStateGraph = {logic_state_graph_name}(atlasStateNames)",
                f"        {request_name}(atlasChangeBasis)",
                f"        {interaction_name}(atlasInteractionNames)",
                "    }",
                "",
                f"    func {request_name}(_ changeBasis: [String]) {{",
                f"        let atlasLogicContext = {logic_context_name}(changeBasis, interactions: atlasInteractionNames)",
                "        _ = atlasLogicContext",
                "    }",
                "",
                f"    func {interaction_name}(_ interactions: [String]) {{",
                f"        let atlasLogicContext = {logic_context_name}(atlasChangeBasis, interactions: interactions)",
                "        _ = atlasLogicContext",
                "    }",
                "",
                f"    private func {logic_context_name}(_ changeBasis: [String], interactions: [String]) -> [String: [String]] {{",
                "        return [",
                '            "change_basis": changeBasis,',
                '            "interactions": interactions,',
                "        ]",
                "    }",
                "",
                f"    private func {logic_state_graph_name}(_ states: [String]) -> [String] {{",
                "        return states.map { state in state.lowercased() }",
                "    }",
                "",
                "    private var atlasChangeBasis: [String] {",
                "        return []",
                "    }",
                "",
                "    private var atlasInteractionNames: [String] {",
                "        return []",
                "    }",
            ]
        )
    elif kind in {"feature_screen", "feature_view"}:
        lines.extend(
            [
                f"        let atlasViewCopy = {component_copy_name}(atlasStringKeys, assets: atlasAssetPaths)",
                f"        {render_name}(atlasStringKeys, assets: atlasAssetPaths)",
                f"        {interaction_name}(atlasInteractionNames)",
                "    }",
                "",
                f"    func {render_name}(_ strings: [String], assets: [String]) {{",
                f"        let atlasViewCopy = {component_copy_name}(strings, assets: assets)",
                "        _ = atlasViewCopy",
                "    }",
                "",
                f"    func {interaction_name}(_ interactions: [String]) {{",
                "        _ = interactions",
                "    }",
                "",
                f"    private func {component_copy_name}(_ strings: [String], assets: [String]) -> [String: String] {{",
                "        return [",
                '            "title": strings.first ?? "",',
                '            "asset": assets.first ?? "",',
                "        ]",
                "    }",
            ]
        )
    elif kind == "feature_service":
        lines.extend(
            [
                f"        let atlasRequestPayload = {service_payload_name}(atlasChangeBasis)",
                f"        let atlasResponseFields = {service_response_name}()",
                f"        {request_name}(atlasChangeBasis)",
                "    }",
                "",
                f"    func {request_name}(_ changeBasis: [String]) {{",
                f"        let atlasRequestPayload = {service_payload_name}(changeBasis)",
                f"        let atlasResponseFields = {service_response_name}()",
                "        _ = atlasRequestPayload",
                "        _ = atlasResponseFields",
                "    }",
                "",
                f"    private func {service_payload_name}(_ changeBasis: [String]) -> [String: String] {{",
                "        return [",
                '            "source": changeBasis.joined(separator: ","),',
                '            "request_id": "atlas_sync",',
                "        ]",
                "    }",
                "",
                f"    private func {service_response_name}() -> [String] {{",
                '        return ["status", "message", "data"]',
                "    }",
            ]
        )
    elif kind == "feature_model":
        lines.extend(
            [
                "    }",
                "",
                f"    static func {render_name}() -> [String] {{",
                "        return atlasDefaultModelFields()",
                "    }",
                "",
                "    private static func atlasDefaultModelFields() -> [String] {",
                '        return ["id", "status", "title", "subtitle"]',
                "    }",
                "",
                f"    static func {model_field_map_name}() -> [String: String] {{",
                "        return [",
                '            "id": "String",',
                '            "status": "String",',
                '            "title": "String",',
                '            "subtitle": "String",',
                "        ]",
                "    }",
                "",
                f"    static func {model_defaults_name}() -> [String: String] {{",
                "        return [",
                '            "status": "pending",',
                '            "title": "",',
                '            "subtitle": "",',
                "        ]",
                "    }",
            ]
        )
    else:
        lines.extend(
            [
                f"        {interaction_name}(atlasInteractionNames)",
                "    }",
                "",
                f"    func {interaction_name}(_ interactions: [String]) {{",
                "        _ = interactions",
                "    }",
            ]
        )
    lines.extend(
        [
            "}",
            f"// T2N Atlas Generated Patch End [{requirement['id']}]",
        ]
    )
    return "\n".join(lines) + "\n"


def infer_create_type_name(relative_path: str) -> str:
    stem = Path(relative_path).stem
    return sanitize_identifier(stem).replace("_", "")


def build_generated_swift_file(contract: dict, relative_path: str, kind: str, ui_role: str, source_screens: list[str]) -> str:
    requirement = contract["requirement"]
    type_name = infer_create_type_name(relative_path)
    requirement_slug = sanitize_identifier(requirement["name"])
    base_lines: list[str] = []
    if kind in {"feature_screen", "feature_view"} or ui_role in {"primary_screen", "auxiliary_dialog", "auxiliary_overlay", "component_view"}:
        base_lines.append("import UIKit")
    else:
        base_lines.append("import Foundation")

    if kind == "feature_screen" or ui_role == "primary_screen":
        base_lines.extend(
            [
                "",
                f"final class {type_name}: UIViewController {{",
                "    override func viewDidLoad() {",
                "        super.viewDidLoad()",
                "        view.backgroundColor = .systemBackground",
                "        setupAtlasViews()",
                f"        {extension_method_name(kind, ui_role, requirement_slug)}()",
                "    }",
                "",
                "    private func setupAtlasViews() {",
                "    }",
                "}",
                "",
            ]
        )
    elif kind == "feature_view":
        base_lines.extend(
            [
                "",
                f"final class {type_name}: UIView {{",
                "    override init(frame: CGRect) {",
                "        super.init(frame: frame)",
                "        setupAtlasView()",
                f"        {extension_method_name(kind, ui_role, requirement_slug)}()",
                "    }",
                "",
                "    required init?(coder: NSCoder) {",
                '        fatalError("init(coder:) has not been implemented")',
                "    }",
                "",
                "    private func setupAtlasView() {",
                "    }",
                "}",
                "",
            ]
        )
    elif kind == "feature_model":
        base_lines.extend(
            [
                "",
                f"struct {type_name} {{",
                '    var atlasIdentifier = ""',
                '    var atlasStatus = "pending"',
                '    var atlasTitle = ""',
                '    var atlasSubtitle = ""',
                "",
                "    init() {",
                "    }",
                "}",
                "",
            ]
        )
    elif kind == "feature_service":
        base_lines.extend(
            [
                "",
                f"final class {type_name} {{",
                "    init() {",
                f"        {extension_method_name(kind, ui_role, requirement_slug)}()",
                "    }",
                "",
                "    func atlasRequest(completion: @escaping ([String: String]) -> Void) {",
                "        completion([:])",
                "    }",
                "}",
                "",
            ]
        )
    elif kind == "feature_logic":
        base_lines.extend(
            [
                "",
                f"final class {type_name} {{",
                "    init() {",
                f"        {extension_method_name(kind, ui_role, requirement_slug)}()",
                "    }",
                "",
                "    func atlasHandle(action: String) {",
                "        _ = action",
                "    }",
                "}",
                "",
            ]
        )
    else:
        base_lines.extend(
            [
                "",
                f"final class {type_name} {{",
                "    init() {",
                f"        {extension_method_name(kind, ui_role, requirement_slug)}()",
                "    }",
                "}",
                "",
            ]
        )
    return "\n".join(base_lines) + build_generated_swift_extension(contract, relative_path, kind, type_name, ui_role, source_screens)


def build_patch_payload(contract: dict, relative_path: str, touchpoint: dict, action: str, existing: str) -> tuple[str, str, str]:
    kind = touchpoint.get("kind", "other")
    ui_role = touchpoint.get("ui_role", "non_ui")
    source_screens = touchpoint.get("source_screens", [])
    if Path(relative_path).suffix == ".swift":
        if action == "create" or not existing.strip():
            return build_generated_swift_file(contract, relative_path, kind, ui_role, source_screens), "swift_file", kind
        target_type = extract_primary_swift_type(existing)
        if target_type:
            return build_generated_swift_extension(contract, relative_path, kind, target_type, ui_role, source_screens), "swift_extension", kind
        return build_patch_block(contract, relative_path, touchpoint), "marker_block", "other"
    return build_patch_block(contract, relative_path, touchpoint), "marker_block", "other"


def apply_block_to_file(repo_root: Path, contract: dict, relative_path: str, touchpoint: dict, action: str) -> dict:
    target_path = repo_root / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_text_safe(target_path) if target_path.exists() else ""
    payload, generation_mode, snippet_type = build_patch_payload(contract, relative_path, touchpoint, action, existing)
    requirement_id = contract["requirement"]["id"]
    ui_role = touchpoint.get("ui_role", "non_ui")
    source_screens = touchpoint.get("source_screens", [])
    hook_target = None
    hook_inserted = False
    if generated_marker(requirement_id) in existing:
        return {
            "path": relative_path,
            "action": action,
            "status": "completed",
            "planned": True,
            "changed": False,
            "generation_mode": generation_mode,
            "snippet_type": snippet_type,
            "ui_role": ui_role,
            "source_screens": source_screens,
            "hook_target": hook_target,
            "hook_inserted": hook_inserted,
            "notes": ["Atlas patch already present; no additional write needed."],
        }

    if generation_mode == "swift_file":
        new_content = payload
    elif existing.strip():
        patched_existing = existing
        if generation_mode == "swift_extension" and ui_role in HOOKABLE_UI_ROLES:
            call_name = extension_method_name(touchpoint.get("kind", "other"), ui_role, sanitize_identifier(contract["requirement"]["name"]))
            patched_existing, hook_target, hook_inserted = inject_install_hook(existing, call_name, touchpoint.get("kind", "other"), ui_role)
        new_content = patched_existing.rstrip() + "\n\n" + payload
    else:
        new_content = payload
    write_text(target_path, new_content)
    notes = [
        "Atlas generated Swift patch appended."
        if generation_mode == "swift_extension"
        else "Atlas generated Swift file created."
        if generation_mode == "swift_file"
        else "Atlas marker patch appended."
    ]
    if hook_inserted and hook_target:
        notes.append(f"UIKit hook inserted into `{hook_target}`.")
    elif generation_mode == "swift_extension" and ui_role in HOOKABLE_UI_ROLES:
        notes.append("No existing UIKit hook target was found; fallback remained extension-only.")
    return {
        "path": relative_path,
        "action": action,
        "status": "completed",
        "planned": True,
        "changed": True,
        "generation_mode": generation_mode,
        "snippet_type": snippet_type,
        "ui_role": ui_role,
        "source_screens": source_screens,
        "hook_target": hook_target,
        "hook_inserted": hook_inserted,
        "notes": notes,
    }


def block_requirement_id(block: str) -> str:
    first_line = block.splitlines()[0]
    if "[" in first_line and "]" in first_line:
        return first_line.split("[", 1)[1].split("]", 1)[0]
    return "unknown"


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
        action = normalize_operation_action(raw.get("action"))
        operations.append(
            {
                "operation_id": raw.get("operation_id"),
                "path": path,
                "action": action,
                "target_kind": raw.get("target_kind", "other"),
                "ui_role": raw.get("ui_role", "non_ui"),
                "source_screens": raw.get("source_screens", []),
                "reason": raw.get("reason", ""),
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


def validate_operations(repo_root: Path, operations: list[dict]) -> tuple[list[str], list[str]]:
    missing_updates = [
        item["path"]
        for item in operations
        if item["action"] == "update" and not (repo_root / item["path"]).exists()
    ]
    create_conflicts = [
        item["path"]
        for item in operations
        if item["action"] == "create" and (repo_root / item["path"]).exists()
    ]
    return missing_updates, create_conflicts


def render_apply_report(result: dict) -> str:
    requirement = result["requirement"]
    lines = [
        f"# Apply Report: {requirement['name']}",
        "",
        "## 1. 执行概览",
        "",
        f"- Requirement ID: `{requirement['id']}`",
        f"- Requirement Name: `{requirement['name']}`",
        f"- Apply Status: `{result['apply_status']}`",
        f"- Planned Creates: `{result['planned_creates']}`",
        f"- Planned Updates: `{result['planned_updates']}`",
        f"- Actual Creates: `{len(result['executed_creates'])}`",
        f"- Actual Updates: `{len(result['executed_updates'])}`",
        "",
        "## 2. 已执行创建项",
        "",
    ]
    if not result["executed_creates"]:
        lines.append("- None")
    else:
        for item in result["executed_creates"]:
            lines.extend(
                [
                    f"### `{item['path']}`",
                    "",
                    "- Action: `create`",
                    f"- Status: `{item['status']}`",
                    "- Planned: `yes`",
                    f"- Generation Mode: `{item.get('generation_mode', 'unknown')}`",
                    f"- Snippet Type: `{item.get('snippet_type', 'other')}`",
                    f"- UI Role: `{item.get('ui_role', 'non_ui')}`",
                    f"- Source Screens: `{', '.join(item.get('source_screens', []))}`" if item.get("source_screens") else "- Source Screens: `none`",
                    f"- Hook Target: `{item.get('hook_target', 'none')}`",
                    "- Notes:",
                    *[f"  - {note}" for note in item["notes"]],
                    "",
                ]
            )
    lines.extend(["## 3. 已执行更新项", ""])
    if not result["executed_updates"]:
        lines.append("- None")
    else:
        for item in result["executed_updates"]:
            lines.extend(
                [
                    f"### `{item['path']}`",
                    "",
                    "- Action: `update`",
                    f"- Status: `{item['status']}`",
                    "- Planned: `yes`",
                    f"- Generation Mode: `{item.get('generation_mode', 'unknown')}`",
                    f"- Snippet Type: `{item.get('snippet_type', 'other')}`",
                    f"- UI Role: `{item.get('ui_role', 'non_ui')}`",
                    f"- Source Screens: `{', '.join(item.get('source_screens', []))}`" if item.get("source_screens") else "- Source Screens: `none`",
                    f"- Hook Target: `{item.get('hook_target', 'none')}`",
                    "- Notes:",
                    *[f"  - {note}" for note in item["notes"]],
                    "",
                ]
            )
    lines.extend(["## 4. 未执行项", ""])
    if not result["not_executed"]:
        lines.append("- None")
    else:
        for item in result["not_executed"]:
            lines.extend(
                [
                    f"### `{item['path']}`",
                    "",
                    f"- Planned Action: `{item['planned_action']}`",
                    "- Reason Not Applied:",
                    *[f"  - {reason}" for reason in item["reasons"]],
                    "",
                ]
            )
    lines.extend(["## 5. 人工保留项", ""])
    if not result["manual_items"]:
        lines.append("- None")
    else:
        for item in result["manual_items"]:
            lines.extend(
                [
                    f"### `{item['path']}`",
                    "",
                    "- Reason:",
                    *[f"  - {reason}" for reason in item["reasons"]],
                    "- Suggested Follow-up:",
                    "  - Keep this item under manual review in V1.",
                    "",
                ]
            )
    lines.extend(["## 6. 执行偏差与异常", ""])
    if not result["deviations"]:
        lines.append("- None")
    else:
        lines.extend(f"- {item}" for item in result["deviations"])
    lines.extend(["", "## 7. 后续建议", ""])
    lines.extend(f"- {item}" for item in result["next_steps"])
    return "\n".join(lines)


def build_apply_result(contract: dict, repo_root: Path, operations: list[dict]) -> dict:
    planned_creates = [item for item in operations if item["action"] == "create"]
    planned_updates = [item for item in operations if item["action"] == "update"]
    manual_items = [item for item in operations if item["action"] == "manual"]
    return {
        "requirement": {
            "id": contract["requirement"]["id"],
            "name": contract["requirement"]["name"],
        },
        "repo_root": str(repo_root),
        "planned_creates": len(planned_creates),
        "planned_updates": len(planned_updates),
        "executed_creates": [],
        "executed_updates": [],
        "not_executed": [],
        "manual_items": [
            {
                "path": item["path"],
                "reasons": ["Marked as manual candidate in the approved plan."],
            }
            for item in manual_items
        ],
        "deviations": [],
        "next_steps": [
            "Run Atlas Verify to compare actual file changes against the approved contract.",
        ],
        "apply_status": "completed",
        "touched_files": [],
    }


def handle_apply(args: argparse.Namespace) -> int:
    inputs = build_inputs(args)
    ensure_run_dir(inputs.run_dir)
    ensure_apply_allowed(inputs)
    contract = load_contract(inputs.run_dir)
    operation_plan = load_operation_plan(inputs.run_dir)
    ensure_operation_contract_consistency(operation_plan, contract)
    operations = iter_operations(operation_plan)
    repo_root = resolve_repo_root(contract, inputs.repo_root)
    ensure_repo_root(repo_root)

    result = build_apply_result(contract, repo_root, operations)
    meta_map = touchpoint_meta_map(contract)
    missing_updates, create_conflicts = validate_operations(repo_root, operations)
    if missing_updates:
        for path in missing_updates:
            result["not_executed"].append(
                {
                    "path": path,
                    "planned_action": "update",
                    "reasons": ["Target file is missing in repo_root; apply aborted before writing."],
                }
            )
        result["deviations"].append("One or more planned update files were missing.")
        result["next_steps"] = ["Return to Atlas Planner and regenerate touchpoints for the current repository state."]
        result["apply_status"] = "aborted"
        write_text(inputs.run_dir / APPLY_REPORT_FILE, render_apply_report(result))
        write_text(inputs.run_dir / APPLY_RESULT_FILE, json.dumps(result, ensure_ascii=False, indent=2))
        print("Apply aborted.")
        print(f"- run_dir: {inputs.run_dir}")
        return 2

    if create_conflicts:
        for path in create_conflicts:
            result["not_executed"].append(
                {
                    "path": path,
                    "planned_action": "create",
                    "reasons": ["Target file already exists; create action was skipped."],
                }
            )
        result["deviations"].append("One or more planned create files already existed.")
        result["apply_status"] = "partial"

    for operation in operations:
        path = operation["path"]
        action = operation["action"]
        if action == "manual":
            continue
        if action == "create" and path in create_conflicts:
            continue
        if action not in {"create", "update"}:
            result["not_executed"].append(
                {
                    "path": path,
                    "planned_action": action,
                    "reasons": [f"Unsupported operation action `{action}` in native_operation_plan."],
                }
            )
            result["deviations"].append(f"Unsupported action `{action}` for `{path}`.")
            result["apply_status"] = "partial"
            continue

        operation_meta = {
            "path": path,
            "kind": operation.get("target_kind", "other"),
            "ui_role": operation.get("ui_role", "non_ui"),
            "source_screens": operation.get("source_screens", []),
            "reason": operation.get("reason", ""),
        }
        merged_meta = dict(meta_map.get(path, {}))
        merged_meta.update(operation_meta)
        item = apply_block_to_file(repo_root, contract, path, merged_meta, action)
        if action == "create":
            result["executed_creates"].append(item)
        else:
            result["executed_updates"].append(item)
        result["touched_files"].append(
            {
                "path": path,
                "action": action,
                "changed": item["changed"],
                "generation_mode": item.get("generation_mode", "unknown"),
                "snippet_type": item.get("snippet_type", "other"),
                "ui_role": item.get("ui_role", "non_ui"),
                "source_screens": item.get("source_screens", []),
                "hook_target": item.get("hook_target"),
                "hook_inserted": item.get("hook_inserted", False),
                "operation_id": operation.get("operation_id"),
            }
        )

    if result["not_executed"] and result["apply_status"] == "completed":
        result["apply_status"] = "partial"

    write_text(inputs.run_dir / APPLY_REPORT_FILE, render_apply_report(result))
    write_text(inputs.run_dir / APPLY_RESULT_FILE, json.dumps(result, ensure_ascii=False, indent=2))
    print("Apply completed.")
    print(f"- run_dir: {inputs.run_dir}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        print("Apply status: missing-run")
        return 0
    result_path = run_dir / APPLY_RESULT_FILE
    report_path = run_dir / APPLY_REPORT_FILE
    print("Apply status: present" if result_path.exists() else "Apply status: pending")
    print(f"- {APPLY_RESULT_FILE}: {'yes' if result_path.exists() else 'no'}")
    print(f"- {APPLY_REPORT_FILE}: {'yes' if report_path.exists() else 'no'}")
    if result_path.exists():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        print(f"- apply_status: {payload.get('apply_status', 'unknown')}")
        print(f"- touched_files: {len(payload.get('touched_files', []))}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "apply":
            return handle_apply(args)
        if args.command == "status":
            return handle_status(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 5
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"atlas-apply error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
