#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERIFY_REPORT_FILE = "verify_report.md"
VERIFY_RESULT_FILE = "verify_result.json"

HUNK_FACTS_FILE = "hunk_facts.json"

REQUIRED_RUN_FILES = {
    "intent.md",
    "flutter_changes.md",
    "edit_tasks.md",
    "edit_tasks.json",
    "native_touchpoints.md",
    "risk_report.md",
    "plan_validation.md",
    "execution_log.md",
}


@dataclass
class VerifyInputs:
    run_dir: Path
    repo_root: Path | None
    force: bool
    swift_parse_check: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Verify (SOP mode)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="Verify a run using edit_tasks + execution_log")
    verify_parser.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    verify_parser.add_argument("--repo-root", help="Optional override for target repository root")
    verify_parser.add_argument("--force", action="store_true", help="Overwrite existing verify artifacts")
    verify_parser.add_argument("--swift-parse-check", action="store_true", help="Run optional swift -parse checks")

    status_parser = subparsers.add_parser("status", help="Report verify readiness for a run directory")
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
        raise FileNotFoundError(f"run dir not found: {run_dir}")
    missing = [name for name in sorted(REQUIRED_RUN_FILES) if not (run_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"run dir missing required files: {', '.join(missing)}")


def write_text(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "gbk", "shift_jis", "euc-kr", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    # latin-1 never raises UnicodeDecodeError, so this is a fallback safety net
    return path.read_text(encoding="latin-1", errors="replace")


def load_edit_tasks(run_dir: Path) -> list[dict]:
    raw = json.loads((run_dir / "edit_tasks.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def parse_execution_log(run_dir: Path) -> dict[str, dict]:
    table: dict[str, dict] = {}
    lines = read_text(run_dir / "execution_log.md").splitlines()
    for line in lines:
        striped = line.strip()
        if not striped.startswith("|"):
            continue
        cols = [c.strip() for c in striped.strip("|").split("|")]
        if len(cols) != 4:
            continue
        if cols[0] in {"task_id", "---", ""}:
            continue
        task_id, status, touched_files, notes = cols
        files = [f.strip() for f in touched_files.split(",") if f.strip()]
        table[task_id] = {
            "status": status.lower(),
            "touched_files": files,
            "notes": notes,
        }
    return table


def load_hunk_facts(run_dir: Path) -> dict | list | None:
    path = run_dir / HUNK_FACTS_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _extract_hunk_entries(hunk_facts: object) -> list[dict]:
    """Normalize hunk_facts into a flat list of per-file entries."""
    entries: list[dict] = []
    if isinstance(hunk_facts, dict):
        business_hunks = hunk_facts.get("business_hunks")
        if isinstance(business_hunks, list):
            entries = [item for item in business_hunks if isinstance(item, dict)]
        else:
            for key, value in hunk_facts.items():
                if isinstance(value, dict) and key != "business_hunks":
                    value.setdefault("file", key)
                    entries.append(value)
    elif isinstance(hunk_facts, list):
        entries = [item for item in hunk_facts if isinstance(item, dict)]
    return entries


def build_coverage_matrix(hunk_facts: object, tasks: list[dict]) -> list[dict]:
    """Cross-check hunk_facts fields against edit_tasks coverage.

    Returns a list of coverage rows, each with:
      category, item, file, covered (bool), status (PASS/WARN/FAIL), reason
    """
    entries = _extract_hunk_entries(hunk_facts)
    if not entries:
        return []

    # Build a search corpus from all tasks
    task_corpus = ""
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_corpus += " ".join([
            json.dumps(task, ensure_ascii=False),
        ]).lower() + " "

    rows: list[dict] = []

    for entry in entries:
        file_path = str(entry.get("file") or "unknown")

        # Check new_classes
        for cls in (entry.get("new_classes") or []):
            if not isinstance(cls, dict):
                continue
            name = str(cls.get("name") or "").strip()
            if not name:
                continue
            user_facing = bool(cls.get("user_facing", False))
            match_name = name.lstrip("_").lower()
            covered = match_name in task_corpus
            rows.append({
                "category": "new_class",
                "item": name,
                "file": file_path,
                "user_facing": user_facing,
                "covered": covered,
                "status": "PASS" if covered else ("FAIL" if user_facing else "WARN"),
                "reason": "" if covered else ("user_facing class 未覆盖" if user_facing else "非 user_facing class 未覆盖"),
            })

        # Check persistence_keys
        for key in (entry.get("persistence_keys") or []):
            key_str = str(key).strip()
            if not key_str:
                continue
            # Extract the core key name for matching (strip variable parts like ${userId})
            core_key = key_str.split("_${")[0].split("${")[0].rstrip("_").lower()
            covered = core_key in task_corpus if core_key else False
            rows.append({
                "category": "persistence_key",
                "item": key_str,
                "file": file_path,
                "user_facing": True,
                "covered": covered,
                "status": "PASS" if covered else "WARN",
                "reason": "" if covered else "持久化 key 未在 task 中提及",
            })

        # Check analytics_events
        for event in (entry.get("analytics_events") or []):
            event_str = str(event).strip()
            if not event_str:
                continue
            event_lower = event_str.split("(")[0].strip().lower()
            covered = event_lower in task_corpus if event_lower else False
            rows.append({
                "category": "analytics_event",
                "item": event_str,
                "file": file_path,
                "user_facing": True,
                "covered": covered,
                "status": "PASS" if covered else "WARN",
                "reason": "" if covered else "埋点事件未在 task 中提及",
            })

        # Check ab_gates
        for gate in (entry.get("ab_gates") or []):
            gate_str = str(gate).strip()
            if not gate_str:
                continue
            gate_lower = gate_str.lower()
            covered = any(token in task_corpus for token in gate_lower.split(".") if len(token) > 3)
            rows.append({
                "category": "ab_gate",
                "item": gate_str,
                "file": file_path,
                "user_facing": True,
                "covered": covered,
                "status": "PASS" if covered else "WARN",
                "reason": "" if covered else "AB 门控未在 task 中提及",
            })

        # Check new_methods
        for method in (entry.get("new_methods") or []):
            if isinstance(method, dict):
                method_name = str(method.get("name") or "").strip()
            elif isinstance(method, str):
                method_name = method.strip()
            else:
                continue
            if not method_name:
                continue
            covered = method_name.lower() in task_corpus
            rows.append({
                "category": "new_method",
                "item": method_name,
                "file": file_path,
                "user_facing": False,
                "covered": covered,
                "status": "PASS" if covered else "WARN",
                "reason": "" if covered else "新增方法未在 task 中提及",
            })

    return rows


def find_swiftc() -> str | None:
    if shutil.which("xcrun"):
        return "xcrun"
    if shutil.which("swiftc"):
        return "swiftc"
    return None


def run_swift_parse(repo_root: Path, file_paths: list[str]) -> list[dict]:
    compiler = find_swiftc()
    if not compiler:
        return [{"path": "(all)", "status": "skip", "reason": "swiftc/xcrun not found"}]

    results: list[dict] = []
    for rel_path in sorted(set(file_paths)):
        if not rel_path.endswith(".swift"):
            continue
        target = repo_root / rel_path
        if not target.exists():
            results.append({"path": rel_path, "status": "fail", "reason": "file missing"})
            continue
        cmd = ["xcrun", "swiftc", "-parse", str(target)] if compiler == "xcrun" else ["swiftc", "-parse", str(target)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            results.append({"path": rel_path, "status": "pass", "reason": ""})
        else:
            message = (proc.stderr or proc.stdout or "swift parse failed").strip().splitlines()
            results.append({"path": rel_path, "status": "fail", "reason": message[0][:220] if message else "swift parse failed"})
    if not results:
        return [{"path": "(none)", "status": "skip", "reason": "no swift file in execution log"}]
    return results


def build_verify_result(inputs: VerifyInputs) -> dict:
    tasks = load_edit_tasks(inputs.run_dir)
    execution = parse_execution_log(inputs.run_dir)
    repo_root = inputs.repo_root

    task_results: list[dict] = []
    touched_files: set[str] = set()
    for task in tasks:
        task_id = task.get("task_id", "unknown")
        log_item = execution.get(task_id)
        if not log_item:
            task_results.append({"task_id": task_id, "status": "missing", "reason": "task not found in execution_log"})
            continue
        status = log_item.get("status", "pending")
        files = log_item.get("touched_files", [])
        touched_files.update(files)
        if status not in {"done", "completed", "pass", "ok"}:
            task_results.append({"task_id": task_id, "status": "pending", "reason": f"status={status}"})
            continue

        missing_files: list[str] = []
        if repo_root:
            for rel in files:
                if not (repo_root / rel).exists():
                    missing_files.append(rel)

        if missing_files:
            task_results.append({"task_id": task_id, "status": "fail", "reason": "missing files: " + ", ".join(missing_files)})
        else:
            task_results.append({"task_id": task_id, "status": "pass", "reason": ""})

    swift_results: list[dict] = []
    if inputs.swift_parse_check and repo_root:
        swift_results = run_swift_parse(repo_root, sorted(touched_files))

    # --- diff 覆盖矩阵: hunk_facts → edit_tasks cross-check ---
    coverage_matrix: list[dict] = []
    hunk_facts = load_hunk_facts(inputs.run_dir)
    if hunk_facts is not None:
        coverage_matrix = build_coverage_matrix(hunk_facts, tasks)

    has_fail = (
        any(item["status"] == "fail" for item in task_results)
        or any(item["status"] == "fail" for item in swift_results)
        or any(item["status"] == "FAIL" for item in coverage_matrix)
    )
    has_pending = any(item["status"] in {"missing", "pending"} for item in task_results)
    has_coverage_warn = any(item["status"] == "WARN" for item in coverage_matrix)

    if has_fail:
        verify_status = "FAIL"
    elif has_pending or has_coverage_warn:
        verify_status = "WARN"
    else:
        verify_status = "PASS"

    coverage_pass = sum(1 for i in coverage_matrix if i["status"] == "PASS")
    coverage_warn = sum(1 for i in coverage_matrix if i["status"] == "WARN")
    coverage_fail = sum(1 for i in coverage_matrix if i["status"] == "FAIL")

    return {
        "verify_status": verify_status,
        "run_dir": str(inputs.run_dir),
        "repo_root": str(repo_root) if repo_root else None,
        "tasks_total": len(tasks),
        "task_results": task_results,
        "swift_parse_results": swift_results,
        "coverage_matrix": coverage_matrix,
        "summary": [
            f"tasks={len(tasks)}",
            f"pass={sum(1 for i in task_results if i['status']=='pass')}",
            f"pending_or_missing={sum(1 for i in task_results if i['status'] in {'pending','missing'})}",
            f"fail={sum(1 for i in task_results if i['status']=='fail')}",
            f"coverage_total={len(coverage_matrix)}",
            f"coverage_pass={coverage_pass}",
            f"coverage_warn={coverage_warn}",
            f"coverage_fail={coverage_fail}",
        ],
    }


def render_report(result: dict) -> str:
    lines = [
        "# Verify Report",
        "",
        f"- Overall: `{result['verify_status']}`",
        f"- Tasks Total: `{result['tasks_total']}`",
        "",
        "## Task Results",
        "",
    ]
    if not result["task_results"]:
        lines.append("- none")
    else:
        for item in result["task_results"]:
            lines.append(f"- `{item['task_id']}`: `{item['status']}` | {item.get('reason','')}")

    lines.extend(["", "## Swift Parse", ""])
    if not result["swift_parse_results"]:
        lines.append("- not enabled")
    else:
        for item in result["swift_parse_results"]:
            lines.append(f"- `{item['path']}`: `{item['status']}` | {item.get('reason','')}")

    # --- diff 覆盖矩阵 ---
    coverage_matrix = result.get("coverage_matrix", [])
    lines.extend(["", "## diff 覆盖矩阵", ""])
    if not coverage_matrix:
        lines.append("- hunk_facts.json 不存在或为空，跳过覆盖检查")
    else:
        lines.append("| category | item | file | user_facing | status | reason |")
        lines.append("|----------|------|------|-------------|--------|--------|")
        icon_map = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}
        for row in coverage_matrix:
            cat = row.get("category", "")
            item_name = row.get("item", "").replace("|", "\\|")
            file_name = row.get("file", "").replace("|", "\\|")
            uf = "Y" if row.get("user_facing") else "N"
            st = icon_map.get(row.get("status", ""), row.get("status", ""))
            reason = row.get("reason", "").replace("|", "\\|")
            lines.append(f"| {cat} | {item_name} | {file_name} | {uf} | {st} | {reason} |")

    lines.extend(["", "## Summary", ""])
    for item in result.get("summary", []):
        lines.append(f"- {item}")
    return "\n".join(lines)


def handle_verify(args: argparse.Namespace) -> int:
    inputs = build_inputs(args)
    ensure_run_dir(inputs.run_dir)

    result_path = inputs.run_dir / VERIFY_RESULT_FILE
    report_path = inputs.run_dir / VERIFY_REPORT_FILE
    if (result_path.exists() or report_path.exists()) and not inputs.force:
        raise FileExistsError("verify artifacts already exist (use --force)")

    result = build_verify_result(inputs)
    write_text(report_path, render_report(result))
    write_text(result_path, json.dumps(result, ensure_ascii=False, indent=2))

    print("Verify completed.")
    print(f"- run_dir: {inputs.run_dir}")
    print(f"- verify_status: {result['verify_status']}")

    if result["verify_status"] == "FAIL":
        return 2
    return 0


def handle_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        print("Run status: missing")
        return 0
    print("Run status: present")
    for name in sorted(REQUIRED_RUN_FILES):
        print(f"- {name}: {'yes' if (run_dir / name).exists() else 'no'}")
    print(f"- {VERIFY_REPORT_FILE}: {'yes' if (run_dir / VERIFY_REPORT_FILE).exists() else 'no'}")
    print(f"- {VERIFY_RESULT_FILE}: {'yes' if (run_dir / VERIFY_RESULT_FILE).exists() else 'no'}")
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
    except Exception as exc:  # pragma: no cover
        print(f"atlas-verify error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
