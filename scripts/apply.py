#!/usr/bin/env python3
"""apply.py — T2N Atlas feature sync applicator.

This is the third step in each requirement migration. After the user has
reviewed and approved ``sync_plan.md``, this script calls the Claude API to
generate complete file contents for every touched file and writes them to the
native project.

Usage example:
    python3 scripts/apply.py \
        --run-dir /path/to/.ai/t2n/runs/2026-03-16-feature-foo \
        --native-root /path/to/native-ios \
        --profile-dir /path/to/.ai/t2n/native-profile \
        --approved
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import anthropic

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYNC_PLAN_FILE = "sync_plan.md"
FEATURE_INTENT_FILE = "feature_intent.md"
CONVENTIONS_FILE = "conventions.md"
APPLY_REPORT_FILE = "apply_report.md"

CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 8096

# Section headers used when parsing sync_plan.md
SECTION_MODIFY = "需更新的现有文件"
SECTION_CREATE = "计划新建的文件"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FileAction:
    """A planned file action from sync_plan.md."""

    path: str       # relative path inside the native project
    action: str     # "update" or "create"
    note: str = ""  # any inline comment from the plan


@dataclass
class FeatureResult:
    """Execution result for a single feature (group of FileActions)."""

    name: str
    actions: list[FileAction] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "T2N Atlas apply.py — LLM-driven native file patch applicator. "
            "Reads sync_plan.md, generates complete file contents via Claude, "
            "and writes them to the native project."
        ),
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to the run directory containing sync_plan.md and feature_intent.md",
    )
    parser.add_argument(
        "--native-root",
        required=True,
        help="Root directory of the native iOS project",
    )
    parser.add_argument(
        "--profile-dir",
        required=True,
        help="Path to native-profile directory (contains conventions.md)",
    )
    parser.add_argument(
        "--approved",
        action="store_true",
        help="Required safety flag — confirms the user has reviewed sync_plan.md",
    )
    return parser


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def ensure_approved(approved: bool) -> None:
    """Refuse to proceed without the --approved flag."""
    if not approved:
        print(
            "\n[ERROR] --approved flag is required.\n"
            "Please review sync_plan.md first, then re-run with --approved.\n",
            file=sys.stderr,
        )
        sys.exit(1)


def ensure_readable(path: Path, label: str) -> str:
    """Read a text file or abort with a clear error message."""
    if not path.exists():
        print(f"[ERROR] {label} not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


# ---------------------------------------------------------------------------
# sync_plan.md parser
# ---------------------------------------------------------------------------


class _PlanSection(NamedTuple):
    name: str
    action: str  # "update" or "create"


# Map section heading keywords to action types
_SECTION_ACTION_MAP: list[tuple[str, str]] = [
    (SECTION_MODIFY, "update"),
    (SECTION_CREATE, "create"),
]


def _parse_file_line(line: str, action: str) -> FileAction | None:
    """
    Match a markdown list item that references a file path.

    Accepted forms:
        - `path/to/File.swift`: reason | risk=low
        - `path/to/File.swift`: reason
        - - `path/to/File.swift` (bare)
    """
    # Look for a backtick-quoted token that looks like a file path
    match = re.search(r"`([^`]+\.[a-zA-Z0-9]+)`", line)
    if not match:
        return None
    raw_path = match.group(1).strip()
    # Skip non-file-looking entries (e.g. `high`, `medium`, requirement IDs)
    if "/" not in raw_path and "." not in raw_path:
        return None
    # Extract optional trailing note (text after the first colon after the path)
    note = ""
    after = line[match.end():]
    colon_match = re.search(r":\s*(.+)", after)
    if colon_match:
        note = colon_match.group(1).strip()
    return FileAction(path=raw_path, action=action, note=note)


def parse_sync_plan(content: str) -> list[tuple[str, list[FileAction]]]:
    """
    Parse sync_plan.md into a list of (feature_name, [FileAction]) pairs.

    The parser uses a two-level structure:
      - Top-level ``## N. ...`` sections are plan stages (ignored as feature names).
      - Within "计划触点" sections, ``### 需更新的现有文件`` and
        ``### 计划新建的文件`` sub-sections enumerate file actions.

    Because sync_plan.md may not always divide files by "feature" at the
    section level (it groups them by action type instead), we collect all
    update and create actions into a single synthetic feature that mirrors
    the plan's own requirement name.  If the plan contains multiple H2
    sections with file lists we aggregate all of them.

    Returns a list with one entry per logical feature group.
    """
    lines = content.splitlines()

    # Extract requirement name from the title line "# Sync Plan: <name>"
    requirement_name = "Requirement"
    for line in lines:
        title_match = re.match(r"^#\s+Sync Plan:\s+(.+)", line)
        if title_match:
            requirement_name = title_match.group(1).strip()
            break

    # Walk the document, tracking active sub-sections
    current_action: str | None = None
    all_actions: list[FileAction] = []

    for line in lines:
        # Detect action-typed sub-section headers (### level)
        if line.startswith("###"):
            current_action = None
            for keyword, action in _SECTION_ACTION_MAP:
                if keyword in line:
                    current_action = action
                    break
            continue

        # Reset on new top-level or secondary sections that aren't file lists
        if line.startswith("## "):
            current_action = None
            continue

        if current_action is None:
            continue

        # Parse list items in the active section
        stripped = line.strip()
        if stripped.startswith("-") or stripped.startswith("*"):
            action_item = _parse_file_line(stripped, current_action)
            if action_item:
                all_actions.append(action_item)

    if not all_actions:
        return []

    return [(requirement_name, all_actions)]


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


def _build_prompt(
    sync_plan: str,
    feature_intent: str,
    conventions: str,
    file_path: str,
    file_action: str,
    existing_content: str,
) -> str:
    """Construct the prompt sent to Claude for a single file."""
    action_description = (
        "Modify the existing file to implement the planned changes."
        if file_action == "update"
        else "Create a new file that implements the planned changes."
    )

    existing_section = (
        f"## Existing File Content\n\n```swift\n{existing_content}\n```\n\n"
        if existing_content
        else "## Existing File Content\n\nThis is a new file — no existing content.\n\n"
    )

    return f"""You are an iOS native code generator for the T2N Atlas migration tool.

Your task: {action_description}

Target file: `{file_path}`

---

## Sync Plan (approved by user)

{sync_plan}

---

## Feature Intent

{feature_intent}

---

## Code Conventions

{conventions}

---

{existing_section}## Instructions

1. Output ONLY the complete, final file content — no explanation, no markdown fences, no extra commentary.
2. The output must be a complete, compilable Swift file (or other appropriate file type).
3. Follow the conventions exactly.
4. Implement every change described in the sync plan that is relevant to `{file_path}`.
5. Preserve all existing functionality not covered by the plan.
6. Do NOT output anything before or after the file content.
"""


def generate_file_content(
    client: anthropic.Anthropic,
    sync_plan: str,
    feature_intent: str,
    conventions: str,
    file_path: str,
    file_action: str,
    existing_content: str,
) -> str:
    """Call Claude to generate the complete content for a single file."""
    prompt = _build_prompt(
        sync_plan=sync_plan,
        feature_intent=feature_intent,
        conventions=conventions,
        file_path=file_path,
        file_action=file_action,
        existing_content=existing_content,
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def backup_file(source: Path, backup_dir: Path) -> None:
    """Copy source to backup_dir, preserving relative structure."""
    dest = backup_dir / source.name
    # Avoid collision: append an index if the name already exists
    if dest.exists():
        stem = source.stem
        suffix = source.suffix
        idx = 1
        while dest.exists():
            dest = backup_dir / f"{stem}_{idx}{suffix}"
            idx += 1
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def write_native_file(native_path: Path, content: str) -> None:
    """Write content to native_path, creating parent directories as needed."""
    native_path.parent.mkdir(parents=True, exist_ok=True)
    native_path.write_text(content.rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Feature processor
# ---------------------------------------------------------------------------


def process_feature(
    feature_name: str,
    actions: list[FileAction],
    native_root: Path,
    backup_dir: Path,
    sync_plan: str,
    feature_intent: str,
    conventions: str,
    client: anthropic.Anthropic,
    feature_index: int,
    total_features: int,
) -> FeatureResult:
    """Process all file actions for one feature, returning a FeatureResult."""
    result = FeatureResult(name=feature_name, actions=actions)

    print(f"\n[{feature_index}/{total_features}] 正在处理功能：{feature_name}")
    print(f"  涉及文件数：{len(actions)}")

    for action in actions:
        file_path_str = action.path
        native_path = native_root / file_path_str
        file_action = action.action

        print(f"  → [{file_action}] {file_path_str}")

        # --- Read existing content (or empty string for new files) ---
        existing_content = ""
        if native_path.exists():
            if file_action == "create":
                print(f"    警告：计划新建的文件已存在，将覆盖：{file_path_str}")
            try:
                existing_content = native_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                existing_content = native_path.read_text(encoding="latin-1")
        elif file_action == "update":
            msg = f"目标文件未找到：{file_path_str}"
            print(f"    [跳过] {msg}")
            result.errors.append(msg)
            result.skipped_files.append(file_path_str)
            continue

        # --- Backup existing file before overwriting ---
        if native_path.exists():
            try:
                backup_file(native_path, backup_dir)
                print(f"    备份完成 → {backup_dir.name}/{native_path.name}")
            except Exception as exc:
                print(f"    [警告] 备份失败（继续执行）：{exc}")

        # --- Call LLM to generate new content ---
        try:
            new_content = generate_file_content(
                client=client,
                sync_plan=sync_plan,
                feature_intent=feature_intent,
                conventions=conventions,
                file_path=file_path_str,
                file_action=file_action,
                existing_content=existing_content,
            )
        except Exception as exc:
            msg = f"LLM 生成失败 [{file_path_str}]: {exc}"
            print(f"    [跳过] {msg}")
            result.errors.append(msg)
            result.skipped_files.append(file_path_str)
            continue

        # --- Write generated content ---
        try:
            write_native_file(native_path, new_content)
            print(f"    写入完成：{file_path_str}")
        except Exception as exc:
            msg = f"文件写入失败 [{file_path_str}]: {exc}"
            print(f"    [跳过] {msg}")
            result.errors.append(msg)
            result.skipped_files.append(file_path_str)
            continue

        # --- Record success ---
        if file_action == "create":
            result.created_files.append(file_path_str)
        else:
            result.modified_files.append(file_path_str)

    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _section_files(title: str, files: list[str], action: str) -> str:
    if not files:
        return f"## {title}\n\n（无）\n"
    lines = [f"## {title}\n"]
    for f in files:
        lines.append(f"### `{f}`\n")
        lines.append(f"- Action: `{action}`")
        lines.append("- Status: `completed`")
        lines.append("- Planned: `yes`\n")
    return "\n".join(lines) + "\n"


def generate_apply_report(
    requirement_name: str,
    feature_results: list[FeatureResult],
) -> str:
    """Build the apply_report.md content from feature execution results."""
    all_created: list[str] = []
    all_modified: list[str] = []
    all_skipped: list[str] = []
    all_errors: list[str] = []

    for fr in feature_results:
        all_created.extend(fr.created_files)
        all_modified.extend(fr.modified_files)
        all_skipped.extend(fr.skipped_files)
        all_errors.extend(fr.errors)

    total_planned_creates = sum(
        sum(1 for a in fr.actions if a.action == "create") for fr in feature_results
    )
    total_planned_updates = sum(
        sum(1 for a in fr.actions if a.action == "update") for fr in feature_results
    )

    if all_skipped and not (all_created or all_modified):
        apply_status = "aborted"
    elif all_skipped:
        apply_status = "partial"
    else:
        apply_status = "completed"

    lines: list[str] = [
        f"# Apply Report: {requirement_name}",
        "",
        "## 1. 执行概览",
        "",
        f"- Requirement Name: `{requirement_name}`",
        f"- Apply Status: `{apply_status}`",
        f"- Planned Creates: `{total_planned_creates}`",
        f"- Planned Updates: `{total_planned_updates}`",
        f"- Actual Creates: `{len(all_created)}`",
        f"- Actual Updates: `{len(all_modified)}`",
        "",
    ]

    # Section 2: created files
    lines.append("## 2. 已执行创建项")
    lines.append("")
    if all_created:
        for f in all_created:
            lines += [f"### `{f}`", "", "- Action: `create`", "- Status: `completed`", "- Planned: `yes`", ""]
    else:
        lines += ["（无）", ""]

    # Section 3: updated files
    lines.append("## 3. 已执行更新项")
    lines.append("")
    if all_modified:
        for f in all_modified:
            lines += [f"### `{f}`", "", "- Action: `update`", "- Status: `completed`", "- Planned: `yes`", ""]
    else:
        lines += ["（无）", ""]

    # Section 4: skipped files
    lines.append("## 4. 未执行项")
    lines.append("")
    if all_skipped:
        for f in all_skipped:
            # Find matching error message for this file
            reason = next(
                (e for e in all_errors if f in e),
                "执行失败，详见执行偏差与异常",
            )
            lines += [
                f"### `{f}`",
                "",
                "- Planned Action: `update|create`",
                "- Reason Not Applied:",
                f"  - {reason}",
                "",
            ]
    else:
        lines += ["（无）", ""]

    # Section 5: manual items (placeholder — not parsed from plan in this script)
    lines += ["## 5. 人工保留项", "", "（无自动处理的人工保留项）", ""]

    # Section 6: deviations / errors
    lines.append("## 6. 执行偏差与异常")
    lines.append("")
    if all_errors:
        for err in all_errors:
            lines.append(f"- {err}")
        lines.append("")
    else:
        lines += ["- 无异常", ""]

    # Section 7: follow-up recommendations
    lines.append("## 7. 后续建议")
    lines.append("")
    if apply_status == "completed":
        lines.append("- 所有计划文件已成功应用，建议运行 atlas_verify 进行验收。")
    elif apply_status == "partial":
        lines.append("- 部分文件应用失败，请人工检查未执行项并决定是否重跑或手动处理。")
        lines.append("- 成功应用的文件建议先行 build 确认可编译。")
    else:
        lines.append("- 所有文件均未成功应用，建议回到 planner 检查计划或人工处理。")
    lines.append("")

    # Summary block
    success_count = sum(1 for fr in feature_results if fr.success)
    fail_count = len(feature_results) - success_count
    lines += [
        "---",
        "",
        "## 汇总",
        "",
        f"成功：{success_count} 个功能",
    ]
    if fail_count:
        failed_names = [fr.name for fr in feature_results if not fr.success]
        lines.append(f"失败：{fail_count} 个功能（{', '.join(failed_names)}）")
    else:
        lines.append("失败：0 个功能")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --- Safety gate ---
    ensure_approved(args.approved)

    run_dir = Path(args.run_dir).expanduser().resolve()
    native_root = Path(args.native_root).expanduser().resolve()
    profile_dir = Path(args.profile_dir).expanduser().resolve()

    # --- Validate directories ---
    for path, label in [
        (run_dir, "--run-dir"),
        (native_root, "--native-root"),
        (profile_dir, "--profile-dir"),
    ]:
        if not path.exists() or not path.is_dir():
            print(f"[ERROR] {label} not found or not a directory: {path}", file=sys.stderr)
            sys.exit(1)

    # --- Read input documents ---
    print("[apply.py] 读取输入文件...")
    sync_plan = ensure_readable(run_dir / SYNC_PLAN_FILE, "sync_plan.md")
    feature_intent = ensure_readable(run_dir / FEATURE_INTENT_FILE, "feature_intent.md")
    conventions = ensure_readable(profile_dir / CONVENTIONS_FILE, "conventions.md")

    # --- Parse sync_plan.md ---
    print("[apply.py] 解析 sync_plan.md...")
    feature_groups = parse_sync_plan(sync_plan)
    if not feature_groups:
        print("[ERROR] sync_plan.md 中未找到任何文件操作计划。请检查文件格式。", file=sys.stderr)
        sys.exit(1)

    total_files = sum(len(actions) for _, actions in feature_groups)
    print(f"[apply.py] 共找到 {len(feature_groups)} 个功能，{total_files} 个文件操作。")

    # --- Prepare backup directory ---
    backup_dir = run_dir / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"[apply.py] 备份目录：{backup_dir}")

    # --- Initialise Claude client ---
    print("[apply.py] 初始化 Claude API 客户端...")
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment

    # --- Process each feature ---
    feature_results: list[FeatureResult] = []
    for idx, (feature_name, actions) in enumerate(feature_groups, start=1):
        try:
            result = process_feature(
                feature_name=feature_name,
                actions=actions,
                native_root=native_root,
                backup_dir=backup_dir,
                sync_plan=sync_plan,
                feature_intent=feature_intent,
                conventions=conventions,
                client=client,
                feature_index=idx,
                total_features=len(feature_groups),
            )
        except Exception as exc:
            # Unexpected error — record and continue
            result = FeatureResult(name=feature_name, actions=actions)
            result.errors.append(f"未预期错误：{exc}")
            print(f"  [跳过整个功能] 未预期错误：{exc}")

        feature_results.append(result)

    # --- Generate and write apply_report.md ---
    print("\n[apply.py] 生成 apply_report.md...")
    requirement_name = feature_groups[0][0] if feature_groups else "Unknown"
    report_content = generate_apply_report(requirement_name, feature_results)
    report_path = run_dir / APPLY_REPORT_FILE
    report_path.write_text(report_content, encoding="utf-8")
    print(f"[apply.py] 报告已写入：{report_path}")

    # --- Print summary ---
    success_count = sum(1 for fr in feature_results if fr.success)
    fail_count = len(feature_results) - success_count
    print("\n========================================")
    print(f"  apply.py 完成")
    print(f"  成功：{success_count} 个功能")
    if fail_count:
        print(f"  失败（已跳过）：{fail_count} 个功能")
    print(f"  报告：{report_path}")
    print("========================================\n")

    # Exit non-zero if any feature failed
    if fail_count:
        sys.exit(2)


if __name__ == "__main__":
    main()
