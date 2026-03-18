#!/usr/bin/env python3
"""verify.py — T2N Atlas post-apply verification script.

Validates that changes from apply step match the sync plan and feature intent.
Outputs verify_report.md in the run directory.

Usage:
    python3 scripts/verify.py \
        --run-dir /path/to/.ai/t2n/runs/2026-03-16-feature-foo \
        --native-root /path/to/native-ios \
        [--skip-syntax]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERIFY_REPORT_FILE = "verify_report.md"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FeatureResult:
    """Verification result for a single feature."""
    name: str
    # A: Plan conformance
    plan_status: str = "unknown"          # "pass" | "fail" | "skip"
    plan_items: list[dict] = field(default_factory=list)
    # C: Intent conformance (LLM)
    intent_status: str = "unknown"        # "pass" | "warn" | "fail" | "skip"
    intent_notes: list[str] = field(default_factory=list)
    # B: Swift syntax
    syntax_status: str = "skip"           # "pass" | "fail" | "skip"
    syntax_items: list[dict] = field(default_factory=list)


@dataclass
class VerifyInputs:
    run_dir: Path
    native_root: Path
    skip_syntax: bool


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="T2N Atlas post-apply verification — outputs verify_report.md",
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Run directory containing sync_plan.md, feature_intent.md, apply_report.md and backup/",
    )
    parser.add_argument(
        "--native-root",
        required=True,
        help="Root directory of the native iOS project",
    )
    parser.add_argument(
        "--skip-syntax",
        action="store_true",
        help="Skip Swift syntax check (swiftc -parse)",
    )
    return parser


def parse_inputs(args: argparse.Namespace) -> VerifyInputs:
    return VerifyInputs(
        run_dir=Path(args.run_dir).expanduser().resolve(),
        native_root=Path(args.native_root).expanduser().resolve(),
        skip_syntax=args.skip_syntax,
    )


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    """Read a file with UTF-8 encoding, falling back to latin-1."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def write_text(path: Path, content: str) -> None:
    """Write content to a file using UTF-8 encoding."""
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# sync_plan.md parser
# ---------------------------------------------------------------------------

def parse_sync_plan(run_dir: Path) -> dict:
    """
    Parse sync_plan.md and extract planned file operations.

    Returns a dict with keys:
        - features: list of feature names found in the document
        - modify_files: list of relative file paths that should be modified
        - create_files: list of relative file paths that should be created
    """
    sync_plan_path = run_dir / "sync_plan.md"
    if not sync_plan_path.exists():
        return {"features": [], "modify_files": [], "create_files": []}

    content = read_text(sync_plan_path)
    lines = content.splitlines()

    features: list[str] = []
    modify_files: list[str] = []
    create_files: list[str] = []

    # Parse feature names from headings like "## 功能 1：xxx" or "## Feature 1: xxx"
    for line in lines:
        m = re.match(r"^#{1,3}\s+(?:功能\s*\d+[：:]\s*|Feature\s*\d+[：:]\s*)(.+)", line)
        if m:
            features.append(m.group(1).strip())

    # Parse "需更新的现有文件" section for modify targets
    in_modify = False
    in_create = False
    for line in lines:
        # Detect section headings
        stripped = line.strip()
        if re.search(r"需更新|修改文件|Updated?.*[Ff]ile|[Mm]odif", stripped):
            in_modify = True
            in_create = False
            continue
        if re.search(r"计划新建|新增文件|Creat.*[Ff]ile|新建", stripped):
            in_create = True
            in_modify = False
            continue
        # Stop at next section heading
        if re.match(r"^#{1,4}\s", line):
            if in_modify or in_create:
                in_modify = False
                in_create = False
            continue

        # Parse list items with backtick file paths: - `path/to/File.swift`: ...
        m = re.match(r"^\s*[-*]\s+`([^`]+\.swift)`", stripped)
        if m:
            fpath = m.group(1)
            if in_modify:
                modify_files.append(fpath)
            elif in_create:
                create_files.append(fpath)

    return {
        "features": features,
        "modify_files": list(dict.fromkeys(modify_files)),   # deduplicate, preserve order
        "create_files": list(dict.fromkeys(create_files)),
    }


# ---------------------------------------------------------------------------
# apply_report.md parser — extract actually applied files
# ---------------------------------------------------------------------------

def parse_apply_report(run_dir: Path) -> dict:
    """
    Parse apply_report.md to extract the list of files that were actually
    created or modified during the apply step.

    Returns a dict with keys:
        - created: list of relative file paths
        - updated: list of relative file paths
        - all_files: combined list (created + updated)
    """
    report_path = run_dir / "apply_report.md"
    if not report_path.exists():
        return {"created": [], "updated": [], "all_files": []}

    content = read_text(report_path)
    lines = content.splitlines()

    created: list[str] = []
    updated: list[str] = []

    # The apply_report uses headings "### `<file-path>`" under
    # "## 2. 已执行创建项" and "## 3. 已执行更新项" sections.
    in_create_section = False
    in_update_section = False

    for line in lines:
        stripped = line.strip()
        # Section detection
        if re.search(r"已执行创建|Executed.*Creat|Actual.*Creat", stripped):
            in_create_section = True
            in_update_section = False
            continue
        if re.search(r"已执行更新|Executed.*Updat|Actual.*Updat", stripped):
            in_update_section = True
            in_create_section = False
            continue
        # Stop at unrelated level-2 sections
        if re.match(r"^##\s+[^#]", line):
            in_create_section = False
            in_update_section = False
            # Re-check for section names in case the heading itself contains the keyword
            if re.search(r"已执行创建|Executed.*Creat", stripped):
                in_create_section = True
            elif re.search(r"已执行更新|Executed.*Updat", stripped):
                in_update_section = True
            continue

        # Heading entries like "### `path/to/File.swift`"
        m = re.match(r"^#{2,4}\s+`([^`]+)`", stripped)
        if m:
            fpath = m.group(1)
            if in_create_section:
                created.append(fpath)
            elif in_update_section:
                updated.append(fpath)
            continue

        # Also handle plain list items for robustness
        m2 = re.match(r"^\s*[-*]\s+`([^`]+\.swift)`", stripped)
        if m2:
            fpath = m2.group(1)
            if in_create_section and fpath not in created:
                created.append(fpath)
            elif in_update_section and fpath not in updated:
                updated.append(fpath)

    all_files = list(dict.fromkeys(created + updated))
    return {"created": created, "updated": updated, "all_files": all_files}


# ---------------------------------------------------------------------------
# A: Plan conformance check (pure script, no LLM)
# ---------------------------------------------------------------------------

def check_plan_conformance(
    run_dir: Path,
    native_root: Path,
    sync_plan: dict,
    apply_report: dict,
) -> tuple[str, list[dict]]:
    """
    Verify that:
    - Files listed as "modify" in sync_plan exist and were modified
      (detected via mtime comparison with backup/ or content diff).
    - Files listed as "create" in sync_plan exist.

    Returns (status, items) where status is "pass" | "fail",
    and items is a list of dicts with keys: path, kind, status, note.
    """
    backup_dir = run_dir / "backup"
    items: list[dict] = []

    # Check modify targets
    for rel_path in sync_plan["modify_files"]:
        target = native_root / rel_path
        note = ""
        if not target.exists():
            items.append({"path": rel_path, "kind": "modify", "status": "fail", "note": "文件不存在"})
            continue

        # Determine if the file was actually modified
        modified = False
        backup = backup_dir / rel_path
        if backup.exists():
            # Compare content: if content differs, it was modified
            original_content = read_text(backup)
            current_content = read_text(target)
            modified = (original_content != current_content)
            note = "内容与备份相同，可能未被修改" if not modified else "已修改"
        elif rel_path in apply_report["all_files"]:
            # apply_report confirms it was touched
            modified = True
            note = "已修改（来自 apply_report）"
        else:
            # Fall back to mtime check — if file mtime is newer than sync_plan.md
            sync_mtime = (run_dir / "sync_plan.md").stat().st_mtime
            file_mtime = target.stat().st_mtime
            modified = file_mtime > sync_mtime
            note = "已修改（mtime）" if modified else "mtime 未更新，可能未被修改"

        status = "pass" if modified else "warn"
        items.append({"path": rel_path, "kind": "modify", "status": status, "note": note})

    # Check create targets
    for rel_path in sync_plan["create_files"]:
        target = native_root / rel_path
        if target.exists():
            items.append({"path": rel_path, "kind": "create", "status": "pass", "note": "已创建"})
        else:
            items.append({"path": rel_path, "kind": "create", "status": "fail", "note": "文件未创建"})

    # Determine overall status
    has_fail = any(item["status"] == "fail" for item in items)
    status = "fail" if has_fail else "pass"
    return status, items


# ---------------------------------------------------------------------------
# C: Intent conformance check (LLM)
# ---------------------------------------------------------------------------

def build_intent_prompt(
    feature_intent_content: str,
    modified_files_content: dict[str, str],
) -> str:
    """Build the LLM prompt for intent conformance review."""
    files_section = ""
    for path, content in modified_files_content.items():
        # Truncate very long files to avoid token limits
        MAX_CHARS = 4000
        truncated = content[:MAX_CHARS]
        if len(content) > MAX_CHARS:
            truncated += f"\n... [truncated, {len(content) - MAX_CHARS} chars omitted]"
        files_section += f"\n### {path}\n```swift\n{truncated}\n```\n"

    prompt = f"""你是一名 iOS 原生代码 review 专家。请对照功能意图描述，审查以下代码文件是否正确实现了功能意图。

## 功能意图（feature_intent.md）

{feature_intent_content}

## 被修改/新增的代码文件

{files_section}

## 审查维度

请逐条检查以下内容，并给出结论：
1. 代码是否覆盖了功能意图中描述的**业务逻辑**（核心流程）？
2. 数据变更是否落实（状态更新、持久化、模型变化）？
3. 交互是否实现（用户操作、事件绑定、回调）？
4. 副作用（网络请求、存储、埋点/统计）是否处理？

## 输出格式

请用如下格式输出（保持简洁，每条一行）：

RESULT: ✅  （如果整体符合，用 ✅；如有部分问题用 ⚠️；如有关键缺失用 ❌）
- ✅ <已实现的点>
- ⚠️ <有疑问或部分实现的点>
- ❌ <明确缺失的点>

请直接输出结果，不要有前言或后记。
"""
    return prompt


def check_intent_conformance(
    run_dir: Path,
    native_root: Path,
    apply_report: dict,
) -> tuple[str, list[str]]:
    """
    Use LLM to check whether modified files implement the feature intent.

    Returns (status, notes) where status is "pass" | "warn" | "fail".
    """
    feature_intent_path = run_dir / "feature_intent.md"
    if not feature_intent_path.exists():
        return "skip", ["feature_intent.md 不存在，跳过意图符合性检查"]

    feature_intent_content = read_text(feature_intent_path)
    all_files = apply_report["all_files"]

    if not all_files:
        return "skip", ["apply_report 中无实际修改文件，跳过意图符合性检查"]

    # Read content of modified/created files
    modified_files_content: dict[str, str] = {}
    for rel_path in all_files:
        target = native_root / rel_path
        if target.exists():
            modified_files_content[rel_path] = read_text(target)

    if not modified_files_content:
        return "skip", ["所有修改文件均不存在于 native-root，跳过意图符合性检查"]

    print(f"  [C] 调用 LLM 审查意图符合性（{len(modified_files_content)} 个文件）...")

    prompt = build_intent_prompt(feature_intent_content, modified_files_content)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
    except Exception as exc:
        return "skip", [f"LLM 调用失败: {exc}"]

    # Parse the LLM response
    notes: list[str] = []
    overall_status = "pass"

    lines = raw.strip().splitlines()
    result_line = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("RESULT:"):
            result_line = line
            if "❌" in line:
                overall_status = "fail"
            elif "⚠️" in line:
                overall_status = "warn"
            else:
                overall_status = "pass"
        elif line.startswith(("- ✅", "- ⚠️", "- ❌", "✅", "⚠️", "❌")):
            notes.append(line.lstrip("- ").strip())

    if not notes:
        # Fallback: use the entire response as a single note
        notes = [raw.strip()[:500]]

    return overall_status, notes


# ---------------------------------------------------------------------------
# B: Swift syntax check
# ---------------------------------------------------------------------------

def find_swiftc() -> str | None:
    """Find the swiftc or xcrun binary on the current system."""
    if shutil.which("xcrun"):
        return "xcrun"
    if shutil.which("swiftc"):
        return "swiftc"
    return None


def check_swift_syntax(
    native_root: Path,
    file_paths: list[str],
) -> tuple[str, list[dict]]:
    """
    Run swiftc -parse on each Swift file.

    Returns (status, items) where status is "pass" | "fail" | "skip",
    and items contains per-file results.
    """
    swift_files = [p for p in file_paths if p.endswith(".swift")]
    if not swift_files:
        return "skip", [{"path": "(none)", "status": "skip", "note": "没有 Swift 文件需要检查"}]

    compiler = find_swiftc()
    if compiler is None:
        return "skip", [{"path": "(all)", "status": "skip", "note": "swiftc / xcrun 不在 PATH 中，跳过语法检查"}]

    items: list[dict] = []
    has_fail = False

    for rel_path in swift_files:
        target = native_root / rel_path
        if not target.exists():
            items.append({"path": rel_path, "status": "fail", "note": "文件不存在"})
            has_fail = True
            continue

        if compiler == "xcrun":
            cmd = ["xcrun", "swiftc", "-parse", str(target)]
        else:
            cmd = ["swiftc", "-parse", str(target)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            items.append({"path": rel_path, "status": "fail", "note": "语法检查超时"})
            has_fail = True
            continue
        except FileNotFoundError:
            # Compiler disappeared mid-run
            return "skip", [{"path": "(all)", "status": "skip", "note": "swiftc 执行失败，跳过语法检查"}]

        if result.returncode == 0:
            items.append({"path": rel_path, "status": "pass", "note": ""})
        else:
            raw_err = (result.stderr or result.stdout or "").strip()
            # Filter noise lines from xcrun
            err_lines = [
                ln for ln in raw_err.splitlines()
                if ln.strip()
                and "DVTFilePathFSEvents" not in ln
                and "Requested but did not find extension point" not in ln
            ]
            note = err_lines[0][:220] if err_lines else "语法检查失败（无错误输出）"
            items.append({"path": rel_path, "status": "fail", "note": note})
            has_fail = True

    status = "fail" if has_fail else "pass"
    return status, items


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

STATUS_ICON = {
    "pass": "✅",
    "warn": "⚠️",
    "fail": "❌",
    "skip": "⏭",
    "unknown": "❓",
}

INTENT_STATUS_ICON = {
    "pass": "✅",
    "warn": "⚠️",
    "fail": "❌",
    "skip": "⏭",
}


def icon(status: str) -> str:
    return STATUS_ICON.get(status, "❓")


def overall_section_icon(status: str) -> str:
    return icon(status)


def render_plan_section(result: FeatureResult) -> list[str]:
    lines: list[str] = []
    s = result.plan_status
    lines.append(f"### A. 计划符合性 {overall_section_icon(s)}")
    lines.append("")
    if not result.plan_items:
        lines.append("sync_plan.md 中未找到任何计划文件。")
    else:
        if s == "pass":
            lines.append("所有计划文件均已修改/创建：")
        elif s == "fail":
            lines.append("部分计划文件缺失或未被修改：")
        else:
            lines.append("部分文件状态未知：")
        lines.append("")
        for item in result.plan_items:
            item_icon = "✅" if item["status"] == "pass" else ("⚠️" if item["status"] == "warn" else "❌")
            kind_label = "已修改" if item["kind"] == "modify" else "已创建"
            if item["status"] == "pass":
                lines.append(f"- {item_icon} {item['path']}（{kind_label}）")
            else:
                lines.append(f"- {item_icon} {item['path']}（{item['note']}）")
    return lines


def render_intent_section(result: FeatureResult) -> list[str]:
    lines: list[str] = []
    s = result.intent_status
    lines.append(f"### C. 意图符合性 {INTENT_STATUS_ICON.get(s, '❓')}")
    lines.append("")
    if s == "skip":
        lines.append(f"⏭ {result.intent_notes[0] if result.intent_notes else '已跳过'}")
    elif s == "pass":
        lines.append("代码实现与功能意图一致：")
        lines.append("")
        for note in result.intent_notes:
            lines.append(f"- {note}")
    elif s == "warn":
        lines.append("代码实现基本符合功能意图，但存在以下注意点：")
        lines.append("")
        for note in result.intent_notes:
            lines.append(f"- {note}")
    else:
        lines.append("代码实现与功能意图存在偏差：")
        lines.append("")
        for note in result.intent_notes:
            lines.append(f"- {note}")
    return lines


def render_syntax_section(result: FeatureResult) -> list[str]:
    lines: list[str] = []
    s = result.syntax_status
    lines.append(f"### B. Swift 语法检查 {overall_section_icon(s)}")
    lines.append("")
    if not result.syntax_items:
        lines.append("无文件需要检查。")
    else:
        for item in result.syntax_items:
            item_icon = "✅" if item["status"] == "pass" else ("⏭" if item["status"] == "skip" else "❌")
            note_part = f"（{item['note']}）" if item.get("note") else ""
            lines.append(f"- {item_icon} {item['path']}{note_part}")
    return lines


def render_summary_table(feature_results: list[FeatureResult]) -> list[str]:
    lines: list[str] = []
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 功能 | 计划符合性 | 意图符合性 | 语法检查 |")
    lines.append("|------|-----------|-----------|---------|")
    for fr in feature_results:
        plan_icon = overall_section_icon(fr.plan_status)
        intent_icon = INTENT_STATUS_ICON.get(fr.intent_status, "❓")
        syntax_icon = overall_section_icon(fr.syntax_status)
        lines.append(f"| {fr.name} | {plan_icon} | {intent_icon} | {syntax_icon} |")
    return lines


def render_report(feature_results: list[FeatureResult]) -> str:
    """Render the full verify_report.md content."""
    lines: list[str] = ["# Verify Report", ""]

    for idx, fr in enumerate(feature_results, start=1):
        lines.append(f"## 功能 {idx}：{fr.name}")
        lines.append("")
        lines.extend(render_plan_section(fr))
        lines.append("")
        lines.extend(render_intent_section(fr))
        lines.append("")
        lines.extend(render_syntax_section(fr))
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.extend(render_summary_table(feature_results))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main verification orchestration
# ---------------------------------------------------------------------------

def verify_feature(
    feature_name: str,
    run_dir: Path,
    native_root: Path,
    sync_plan: dict,
    apply_report: dict,
    skip_syntax: bool,
) -> FeatureResult:
    """Run A → C → B verification for a single feature."""
    result = FeatureResult(name=feature_name)

    # A: Plan conformance
    print(f"  [A] 检查计划符合性...")
    plan_status, plan_items = check_plan_conformance(run_dir, native_root, sync_plan, apply_report)
    result.plan_status = plan_status
    result.plan_items = plan_items

    # C: Intent conformance (LLM)
    print(f"  [C] 检查意图符合性（LLM）...")
    intent_status, intent_notes = check_intent_conformance(run_dir, native_root, apply_report)
    result.intent_status = intent_status
    result.intent_notes = intent_notes

    # B: Swift syntax
    if skip_syntax:
        result.syntax_status = "skip"
        result.syntax_items = [{"path": "(all)", "status": "skip", "note": "已通过 --skip-syntax 跳过"}]
        print(f"  [B] 语法检查已跳过（--skip-syntax）")
    else:
        print(f"  [B] 检查 Swift 语法...")
        all_files = list(dict.fromkeys(sync_plan["modify_files"] + sync_plan["create_files"]))
        syntax_status, syntax_items = check_swift_syntax(native_root, all_files)
        result.syntax_status = syntax_status
        result.syntax_items = syntax_items

    return result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    inputs = parse_inputs(args)

    # Validate directories
    if not inputs.run_dir.exists():
        print(f"错误: run-dir 不存在: {inputs.run_dir}", file=sys.stderr)
        return 1
    if not inputs.native_root.exists():
        print(f"错误: native-root 不存在: {inputs.native_root}", file=sys.stderr)
        return 1

    print(f"[verify] run-dir:     {inputs.run_dir}")
    print(f"[verify] native-root: {inputs.native_root}")
    print(f"[verify] skip-syntax: {inputs.skip_syntax}")
    print()

    # Parse input artifacts
    print("[1/4] 解析 sync_plan.md...")
    sync_plan = parse_sync_plan(inputs.run_dir)
    features = sync_plan["features"]
    if not features:
        # No explicit feature headings — treat the whole run as one unnamed feature
        features = ["(本次迁移)"]
    print(f"       找到 {len(features)} 个功能: {', '.join(features)}")

    print("[2/4] 解析 apply_report.md...")
    apply_report = parse_apply_report(inputs.run_dir)
    print(f"       实际创建: {len(apply_report['created'])} 个文件，实际更新: {len(apply_report['updated'])} 个文件")
    print()

    # Verify each feature
    feature_results: list[FeatureResult] = []
    for idx, feature_name in enumerate(features, start=1):
        print(f"[3/4] 验证功能 {idx}/{len(features)}：{feature_name}")
        fr = verify_feature(
            feature_name=feature_name,
            run_dir=inputs.run_dir,
            native_root=inputs.native_root,
            sync_plan=sync_plan,
            apply_report=apply_report,
            skip_syntax=inputs.skip_syntax,
        )
        feature_results.append(fr)
        print()

    # Render and write report
    print("[4/4] 生成 verify_report.md...")
    report_content = render_report(feature_results)
    report_path = inputs.run_dir / VERIFY_REPORT_FILE
    write_text(report_path, report_content)
    print(f"       报告已写入: {report_path}")
    print()

    # Print summary
    any_fail = any(
        fr.plan_status == "fail" or fr.intent_status == "fail" or fr.syntax_status == "fail"
        for fr in feature_results
    )
    any_warn = any(
        fr.plan_status == "warn" or fr.intent_status == "warn"
        for fr in feature_results
    )

    if any_fail:
        print("[verify] 结论：存在验证失败项，请查看 verify_report.md 了解详情。")
        return 1
    elif any_warn:
        print("[verify] 结论：验证通过，但存在警告，请查看 verify_report.md 了解详情。")
        return 0
    else:
        print("[verify] 结论：所有验证项通过。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
