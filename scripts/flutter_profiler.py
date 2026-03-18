#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from flutter_profile_scan_core import (
    PROFILE_FILES as CORE_PROFILE_FILES,
    compute_stale_reasons as core_compute_stale_reasons,
    load_scan_meta as core_load_scan_meta,
)
from repo_profile_core import build_profile as build_repo_profile


IGNORE_DIR_NAMES = {
    ".git",
    ".ai",
    ".dart_tool",
    ".idea",
    ".fvm",
    "build",
    "ios",
    "android",
    "macos",
    "linux",
    "windows",
    "web",
}

GENERIC_UI_DIRS = {
    "components",
    "component",
    "widgets",
    "widget",
    "scroll",
    "slide",
    "common",
}

DART_SUFFIXES = {".dart"}
RESOURCE_SUFFIXES = {
    ".arb",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".gif",
    ".ttf",
    ".otf",
}

STATE_SUFFIXES = ("Bloc", "Cubit", "Notifier", "Provider", "ViewModel", "Controller")
MODEL_SUFFIXES = ("Model", "Entity", "Dto", "Request", "Response")
DATA_SUFFIXES = ("Api", "Repository", "Service", "Client", "Datasource")
WIDGET_BASES = {"StatelessWidget", "StatefulWidget", "ConsumerWidget", "HookWidget"}
PRIMARY_SCREEN_TOKENS = {"unlock", "reader", "book", "chapter", "membership", "buy"}
AUXILIARY_SCREEN_TOKENS = {"alert", "dialog", "sheet", "modal", "popup", "overlay"}
COMPONENT_SCREEN_TOKENS = {
    "header",
    "footer",
    "background",
    "tag",
    "menu",
    "badge",
    "button",
    "icon",
    "detector",
    "item",
    "cell",
}

PROFILE_FILES = set(CORE_PROFILE_FILES)

MAX_PRIMARY_SCREENS = 2
MAX_AUXILIARY_SCREENS = 2


@dataclass
class GitInfo:
    head: str | None
    branch: str | None
    dirty: bool | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flutter Profiler for T2N Atlas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan a Flutter repo and write repo-level profile")
    scan.add_argument("--repo-root", required=True, help="Path to the Flutter repository")
    scan.add_argument("--output-dir", required=True, help="Path to .ai/t2n/flutter-profile")
    scan.add_argument("--force", action="store_true", help="Force rescan even if cache looks fresh")
    scan.add_argument("--include-tests", action=argparse.BooleanOptionalAction, default=True)
    scan.add_argument("--max-files", type=int, default=0, help="Optional file scan limit")

    digest = subparsers.add_parser("digest", help="Generate a requirement-level Flutter feature digest")
    digest.add_argument("--repo-root", required=True, help="Path to the Flutter repository")
    digest.add_argument("--profile-dir", required=True, help="Path to .ai/t2n/flutter-profile")
    digest.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    digest.add_argument("--requirement-id", required=True, help="Requirement identifier")
    digest.add_argument("--requirement-name", required=True, help="Requirement name slug")
    digest.add_argument("--flutter-path", help="Optional Flutter path for the requirement scope")
    digest.add_argument("--pr-diff-path", help="Optional Flutter PR diff artifact")
    digest.add_argument("--tests-path", help="Optional Flutter tests path")
    digest.add_argument("--prd-path", help="Optional PRD path")
    digest.add_argument("--force", action="store_true", help="Overwrite existing digest artifacts")

    status = subparsers.add_parser("status", help="Report Flutter profile status")
    status.add_argument("--repo-root", required=True, help="Path to the Flutter repository")
    status.add_argument("--output-dir", required=True, help="Path to .ai/t2n/flutter-profile")

    invalidate = subparsers.add_parser("invalidate", help="Delete a cached Flutter profile")
    invalidate.add_argument("--output-dir", required=True, help="Path to .ai/t2n/flutter-profile")
    return parser


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_repo_root(repo_root: Path) -> None:
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"repo root not found or unreadable: {repo_root}")


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
    except OSError:
        return ""


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def run_git(repo_root: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return completed.stdout.strip()


def collect_git_info(repo_root: Path) -> GitInfo:
    head = run_git(repo_root, ["rev-parse", "HEAD"])
    branch = run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status = run_git(repo_root, ["status", "--porcelain"])
    dirty = None if status is None else bool(status)
    return GitInfo(head=head, branch=branch, dirty=dirty)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_scan_meta(output_dir: Path) -> dict | None:
    path = output_dir / "scan_meta.json"
    if not path.exists():
        return None
    try:
        return load_json(path)
    except (json.JSONDecodeError, OSError):
        return None


def compute_stale_reasons(repo_root: Path, output_dir: Path, force: bool) -> list[str]:
    reasons: list[str] = []
    if force:
        reasons.append("force flag set")
    meta = load_scan_meta(output_dir)
    if meta is None:
        reasons.append("scan_meta.json missing or unreadable")
        return reasons
    if meta.get("profile_version") != "v1":
        reasons.append("profile version mismatch")
    if meta.get("repo_root") != str(repo_root.resolve()):
        reasons.append("repo root changed")
    git_info = collect_git_info(repo_root)
    stored_git = meta.get("git", {})
    if git_info.head and stored_git.get("head") and git_info.head != stored_git.get("head"):
        reasons.append("git head changed")
    return reasons


def should_skip_path(path: Path, repo_root: Path, include_tests: bool) -> bool:
    rel_parts = path.relative_to(repo_root).parts
    if any(part in IGNORE_DIR_NAMES for part in rel_parts):
        return True
    if not include_tests and any(part.lower() in {"test", "tests", "integration_test"} for part in rel_parts):
        return True
    return False


def iter_repo_files(repo_root: Path, include_tests: bool, max_files: int) -> list[Path]:
    results: list[Path] = []
    for path in repo_root.rglob("*"):
        if max_files and len(results) >= max_files:
            break
        if not path.is_file():
            continue
        if should_skip_path(path, repo_root, include_tests):
            continue
        rel = path.relative_to(repo_root)
        if path.suffix.lower() in DART_SUFFIXES | RESOURCE_SUFFIXES:
            results.append(rel)
            continue
        if rel.parts and rel.parts[0] == "assets":
            results.append(rel)
    return results


def camel_tokens(value: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    tokens = re.split(r"[^a-zA-Z0-9]+", spaced)
    return [token.lower() for token in tokens if token]


def derive_feature_name(rel_path: Path) -> str:
    parts = rel_path.parts
    if "features" in parts:
        index = parts.index("features")
        if index + 1 < len(parts):
            return parts[index + 1]
    if "screens" in parts:
        index = parts.index("screens")
        useful = [part for part in parts[index + 1 : -1] if part not in GENERIC_UI_DIRS]
        if useful:
            return "_".join(useful[:3]).lower()
    if parts and parts[0] == "lib":
        useful = [part for part in parts[1:-1] if part not in {"ui", "src", "common", *GENERIC_UI_DIRS}]
        if useful:
            return "_".join(useful[:3]).lower()
    return "shared"


def class_name_entries(text: str) -> list[tuple[str, str | None]]:
    matches = re.findall(
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:extends\s+([A-Za-z_][A-Za-z0-9_<>]*))?",
        text,
    )
    return [(name, base if base else None) for name, base in matches]


def extract_route_defs(text: str, rel_path: str, feature: str) -> list[dict]:
    entries: list[dict] = []
    for route, screen in re.findall(
        r"(?:GoRoute|GetPage|AutoRoute)\s*\((?:(?!\)).)*?(?:path|name)\s*:\s*['\"]([^'\"]+)['\"](?:(?!\)).)*?(?:page|builder|widget)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)",
        text,
        re.DOTALL,
    ):
        entries.append(
            {
                "route": route,
                "screen": screen,
                "path": rel_path,
                "feature": feature,
                "confidence": 0.72,
            }
        )
    return entries


def classify_dart_entry(name: str, base: str | None, rel_path: Path) -> tuple[str, str] | None:
    lower = name.lower()
    rel_lower = rel_path.as_posix().lower()
    if name.endswith(("Page", "Screen")):
        return "screen", name
    if base in WIDGET_BASES and any(token in rel_lower for token in ("/screen", "/screens/", "/page", "/pages/", "/reader/")):
        return "screen", name
    if base in WIDGET_BASES:
        return "component", name
    if name.endswith(STATE_SUFFIXES):
        return "state_holder", name
    if name.endswith(MODEL_SUFFIXES) or any(token in rel_lower for token in ("/model/", "/models/")):
        return "model", name
    if name.endswith(DATA_SUFFIXES) or any(token in rel_lower for token in ("/service/", "/repository/", "/api/")):
        return "data", name
    if "test" in lower:
        return "test", name
    return None


def extract_string_literals(text: str) -> list[str]:
    literals = re.findall(r'["\']([^"\']{2,120})["\']', text)
    results: list[str] = []
    for item in literals:
        stripped = item.strip()
        if not stripped:
            continue
        if stripped.startswith(("dart:", "package:", "assets/", "http://", "https://")):
            continue
        if stripped.startswith(("../", "./", "/")):
            continue
        if "/" in stripped and "." in stripped:
            continue
        if stripped.endswith((".dart", ".png", ".jpg", ".jpeg", ".svg", ".json")):
            continue
        if "${" in stripped or "??" in stripped:
            continue
        if stripped in {"\\n", ":", "--"}:
            continue
        if re.fullmatch(r"[A-Z]{2,}(?:-[A-Z]{2,})+", stripped):
            continue
        if "\n" in stripped or len(stripped) > 80:
            continue
        if not re.search(r"[A-Za-z]", stripped):
            continue
        results.append(stripped)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in results:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:20]


def load_en_arb(repo_root: Path) -> dict[str, str]:
    arb_path = repo_root / "lib/services/language/l10n/app_en.arb"
    if not arb_path.exists():
        return {}
    try:
        payload = json.loads(arb_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        key: value
        for key, value in payload.items()
        if isinstance(value, str) and not key.startswith("@")
    }


def visible_text_value(value: str) -> str | None:
    stripped = value.strip()
    if not stripped:
        return None
    if stripped in {"\\n", ":", "--"}:
        return None
    if "${" in stripped or "??" in stripped:
        return None
    if re.fullmatch(r"[A-Z]{2,}(?:-[A-Z]{2,})+", stripped):
        return None
    if len(stripped) < 3:
        return None
    if not re.search(r"[A-Za-z]", stripped):
        return None
    return stripped


def extract_localized_texts(text: str, en_arb: dict[str, str]) -> list[str]:
    results: list[str] = []
    for match in re.finditer(r"AppLanguage\.of\(\)\?\.(\w+)", text):
        key = match.group(1)
        resolved = visible_text_value(en_arb.get(key, ""))
        if resolved:
            results.append(resolved)
        nearby = text[match.end() : match.end() + 180]
        fallback_match = re.search(r"\?\?\s*['\"]([^'\"]{2,120})['\"]", nearby)
        if fallback_match:
            fallback = visible_text_value(fallback_match.group(1))
            if fallback:
                results.append(fallback)
    return unique_preserve(results)


def extract_interactions(text: str) -> list[str]:
    interactions: list[str] = []
    for event_name, handler in re.findall(
        r"\b(onTap|onPressed|onChanged|onRefresh|onSubmitted|onLongPress)\s*:\s*(?:\(\)\s*=>\s*)?([A-Za-z_][A-Za-z0-9_\.]*)?",
        text,
    ):
        if handler:
            name = handler.split(".")[-1]
            if name.startswith(("is", "has")) or name in {"of", "builder", "child"}:
                continue
            interactions.append(name)
        else:
            interactions.append(event_name)
    return unique_preserve(interactions)[:12]


def extract_state_names(text: str) -> list[dict]:
    states: list[dict] = []
    for token in re.findall(r"\b(?:enum|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text):
        lowered = token.lower()
        if any(key in lowered for key in ("loading", "error", "empty", "success", "retry", "ready")):
            kind = "state"
            if "loading" in lowered:
                kind = "loading"
            elif "error" in lowered or "fail" in lowered:
                kind = "error"
            elif "empty" in lowered:
                kind = "empty"
            elif "retry" in lowered:
                kind = "retry"
            elif "success" in lowered or "ready" in lowered:
                kind = "success"
            states.append({"name": token, "kind": kind})
    for token in re.findall(r"\b(?:final\s+)?bool\s+(is[A-Z][A-Za-z0-9_]*)\b", text):
        lowered = token.lower()
        normalized = token[2:] if token.startswith("is") and len(token) > 2 else token
        if "loading" in lowered:
            states.append({"name": normalized, "kind": "loading"})
        elif "error" in lowered or "fail" in lowered:
            states.append({"name": normalized, "kind": "error"})
        elif "empty" in lowered:
            states.append({"name": normalized, "kind": "empty"})
        elif "success" in lowered or "ready" in lowered:
            states.append({"name": normalized, "kind": "success"})
        elif "retry" in lowered:
            states.append({"name": normalized, "kind": "retry"})
    return unique_dicts(states, ("name", "kind"))[:12]


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def unique_dicts(items: list[dict], keys: tuple[str, ...]) -> list[dict]:
    seen: set[tuple[object, ...]] = set()
    result: list[dict] = []
    for item in items:
        marker = tuple(item.get(key) for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def parse_diff_files(pr_diff_path: Path | None) -> list[str]:
    if pr_diff_path is None or not pr_diff_path.exists():
        return []
    files: list[str] = []
    for line in read_text_safe(pr_diff_path).splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:].strip())
    return unique_preserve(files)


def scan_flutter_repo(repo_root: Path, output_dir: Path, include_tests: bool, max_files: int) -> dict:
    files = iter_repo_files(repo_root, include_tests=include_tests, max_files=max_files)
    git_info = collect_git_info(repo_root)

    feature_map: dict[str, dict] = {}
    route_entries: list[dict] = []
    state_patterns: list[dict] = []
    data_index = {
        "apis": [],
        "repositories": [],
        "services": [],
        "models": [],
    }
    resource_index = {
        "assets": [],
        "l10n_files": [],
        "fonts": [],
    }
    test_index = {
        "widget_tests": [],
        "integration_tests": [],
        "behavior_tags": [],
    }

    counts = {
        "dart_files": 0,
        "arb_files": 0,
        "asset_files": 0,
        "test_files": 0,
    }

    for rel_path in files:
        feature = derive_feature_name(rel_path)
        rel_str = rel_path.as_posix()
        bucket = feature_map.setdefault(
            feature,
            {
                "name": feature,
                "paths": [],
                "screens": [],
                "components": [],
                "state_holders": [],
                "services": [],
                "models": [],
                "resources": [],
                "tests": [],
                "confidence": 0.7,
            },
        )
        parent_path = rel_path.parent.as_posix()
        if parent_path not in bucket["paths"]:
            bucket["paths"].append(parent_path)

        suffix = rel_path.suffix.lower()
        if suffix == ".dart":
            counts["dart_files"] += 1
            text = read_text_safe(repo_root / rel_path)
            route_entries.extend(extract_route_defs(text, rel_str, feature))
            for name, base in class_name_entries(text):
                classified = classify_dart_entry(name, base, rel_path)
                if classified is None:
                    continue
                kind, label = classified
                if kind == "screen":
                    bucket["screens"].append(label)
                elif kind == "component":
                    bucket["components"].append(label)
                elif kind == "state_holder":
                    bucket["state_holders"].append(label)
                    state_patterns.append(
                        {
                            "kind": "state_holder",
                            "name": label,
                            "path": rel_str,
                            "feature": feature,
                            "confidence": 0.75,
                        }
                    )
                elif kind == "model":
                    bucket["models"].append(label)
                    data_index["models"].append(
                        {
                            "name": label,
                            "path": rel_str,
                            "feature": feature,
                            "kind": "model",
                            "confidence": 0.78,
                        }
                    )
                elif kind == "data":
                    bucket["services"].append(label)
                    target = "services"
                    lowered = label.lower()
                    if lowered.endswith("api"):
                        target = "apis"
                    elif lowered.endswith("repository"):
                        target = "repositories"
                    data_index[target].append(
                        {
                            "name": label,
                            "path": rel_str,
                            "feature": feature,
                            "kind": target[:-1] if target.endswith("s") else target,
                            "confidence": 0.78,
                        }
                    )

            if any(part in {"test", "tests", "integration_test"} for part in rel_path.parts):
                counts["test_files"] += 1
                test_kind = "integration_tests" if "integration_test" in rel_path.parts else "widget_tests"
                test_index[test_kind].append({"path": rel_str, "feature": feature})
                bucket["tests"].append(rel_str)

        elif suffix == ".arb":
            counts["arb_files"] += 1
            resource_index["l10n_files"].append({"path": rel_str, "kind": "arb"})
            bucket["resources"].append(rel_str)
        elif suffix in {".ttf", ".otf"}:
            counts["asset_files"] += 1
            resource_index["fonts"].append({"path": rel_str, "feature": feature, "confidence": 0.9})
            bucket["resources"].append(rel_str)
        else:
            counts["asset_files"] += 1
            resource_index["assets"].append({"path": rel_str, "feature": feature, "confidence": 0.9})
            bucket["resources"].append(rel_str)

    features = []
    for item in feature_map.values():
        item["paths"] = sorted(unique_preserve(item["paths"]))[:8]
        item["screens"] = unique_preserve(item["screens"])[:12]
        item["components"] = unique_preserve(item["components"])[:20]
        item["state_holders"] = unique_preserve(item["state_holders"])[:12]
        item["services"] = unique_preserve(item["services"])[:12]
        item["models"] = unique_preserve(item["models"])[:12]
        item["resources"] = unique_preserve(item["resources"])[:20]
        item["tests"] = unique_preserve(item["tests"])[:12]
        features.append(item)

    feature_index = {"features": sorted(features, key=lambda item: item["name"])}
    route_map = {
        "primary_routing_style": infer_routing_style(route_entries),
        "route_definitions": unique_dicts(route_entries, ("route", "screen", "path"))[:100],
        "entry_points": [],
        "risky_routing_files": [],
    }
    state_patterns_payload = {"patterns": unique_dicts(state_patterns, ("name", "path"))[:200]}
    data_index = {key: unique_dicts(value, ("name", "path"))[:200] for key, value in data_index.items()}
    resource_index["assets"] = unique_dicts(resource_index["assets"], ("path",))[:300]
    resource_index["l10n_files"] = unique_dicts(resource_index["l10n_files"], ("path",))[:100]
    resource_index["fonts"] = unique_dicts(resource_index["fonts"], ("path",))[:50]
    test_index["widget_tests"] = unique_dicts(test_index["widget_tests"], ("path",))[:200]
    test_index["integration_tests"] = unique_dicts(test_index["integration_tests"], ("path",))[:200]

    scan_meta = {
        "profile_version": "v1",
        "generated_at": utc_now_iso(),
        "repo_root": str(repo_root.resolve()),
        "git": {
            "head": git_info.head,
            "branch": git_info.branch,
            "dirty": git_info.dirty,
        },
        "counts": counts,
    }

    write_json(output_dir / "scan_meta.json", scan_meta)
    write_json(output_dir / "feature_index.json", feature_index)
    write_json(output_dir / "route_map.json", route_map)
    write_json(output_dir / "state_patterns.json", state_patterns_payload)
    write_json(output_dir / "data_flow_index.json", data_index)
    write_json(output_dir / "resource_index.json", resource_index)
    write_json(output_dir / "test_index.json", test_index)
    write_text(output_dir / "repo_summary.md", build_repo_summary(feature_index, route_map, state_patterns_payload, counts))

    return {
        "scan_meta": scan_meta,
        "feature_index": feature_index,
        "route_map": route_map,
        "state_patterns": state_patterns_payload,
        "data_flow_index": data_index,
        "resource_index": resource_index,
        "test_index": test_index,
    }


def infer_routing_style(route_entries: list[dict]) -> str:
    if route_entries:
        return "declared_router"
    return "unknown"


def build_repo_summary(feature_index: dict, route_map: dict, state_patterns: dict, counts: dict) -> str:
    lines = [
        "# Flutter Repo Summary",
        "",
        "## 扫描概览",
        "",
        f"- Dart Files: `{counts['dart_files']}`",
        f"- ARB Files: `{counts['arb_files']}`",
        f"- Asset Files: `{counts['asset_files']}`",
        f"- Test Files: `{counts['test_files']}`",
        "",
        "## 主要 Feature",
        "",
    ]
    for item in feature_index.get("features", [])[:12]:
        lines.append(f"- `{item['name']}`: screens={len(item['screens'])}, state_holders={len(item['state_holders'])}, services={len(item['services'])}")
    lines.extend(
        [
            "",
            "## 路由模式",
            "",
            f"- Primary Routing Style: `{route_map.get('primary_routing_style', 'unknown')}`",
            f"- Route Definitions: `{len(route_map.get('route_definitions', []))}`",
            "",
            "## 状态模式",
            "",
            f"- State Holders Indexed: `{len(state_patterns.get('patterns', []))}`",
        ]
    )
    return "\n".join(lines)


def ensure_profile_dir(profile_dir: Path) -> None:
    if not profile_dir.exists() or not profile_dir.is_dir():
        raise FileNotFoundError(f"profile dir not found or unreadable: {profile_dir}")
    missing = [name for name in PROFILE_FILES if not (profile_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"profile dir missing required files: {', '.join(missing)}")


def collect_run_files(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    if path.is_file():
        return [str(path)]
    return [str(item) for item in sorted(path.rglob("*")) if item.is_file()]


def select_scope_files(repo_root: Path, flutter_path: Path | None, diff_files: list[str], tests_path: Path | None) -> list[Path]:
    selected: list[Path] = []
    if flutter_path is not None and flutter_path.exists():
        if flutter_path.is_file():
            selected.append(flutter_path.resolve())
        else:
            selected.extend(item.resolve() for item in sorted(flutter_path.rglob("*")) if item.is_file())
    for item in diff_files:
        candidate = repo_root / item
        if candidate.exists() and candidate.is_file():
            selected.append(candidate.resolve())
    if tests_path is not None and tests_path.exists():
        if tests_path.is_file():
            selected.append(tests_path.resolve())
        else:
            selected.extend(item.resolve() for item in sorted(tests_path.rglob("*")) if item.is_file())
    return [Path(item) for item in unique_preserve([str(path) for path in selected])]


def feature_names_for_scope(profile: dict, scope_files: list[Path], repo_root: Path) -> list[str]:
    features: list[str] = []
    path_map = {}
    for feature in profile["feature_index"].get("features", []):
        for path in feature.get("paths", []):
            path_map[path] = feature["name"]
    for path in scope_files:
        rel_parent = path.relative_to(repo_root).parent.as_posix()
        matched = [name for prefix, name in path_map.items() if rel_parent.startswith(prefix)]
        if matched:
            features.extend(matched)
        else:
            features.append(derive_feature_name(path.relative_to(repo_root)))
    return unique_preserve(features)


def split_primary_supporting_features(
    repo_root: Path,
    scope_files: list[Path],
    flutter_path: Path | None,
) -> tuple[list[str], list[str]]:
    primary_files: list[Path] = []
    supporting_files: list[Path] = []
    flutter_root = flutter_path.resolve() if flutter_path and flutter_path.exists() else None
    for path in scope_files:
        if flutter_root and str(path).startswith(str(flutter_root)):
            primary_files.append(path)
        else:
            supporting_files.append(path)
    primary_features = unique_preserve([derive_feature_name(path.relative_to(repo_root)) for path in primary_files])
    supporting_features = unique_preserve([derive_feature_name(path.relative_to(repo_root)) for path in supporting_files])
    supporting_features = [item for item in supporting_features if item not in set(primary_features)]
    return primary_features, supporting_features


def common_scope_root(scope_files: list[Path]) -> Path | None:
    if not scope_files:
        return None
    common = Path(scope_files[0]).parent
    for path in scope_files[1:]:
        while common != common.parent and not str(path).startswith(str(common)):
            common = common.parent
    return common


def representative_screens(
    profile: dict,
    features: list[str],
    scope_files: list[Path],
    repo_root: Path,
    preferred_root: Path | None = None,
) -> tuple[list[dict], list[dict]]:
    screens: list[dict] = []
    noise: list[dict] = []
    feature_roots = set(features)
    scope_root = preferred_root if preferred_root and preferred_root.exists() else common_scope_root(scope_files)
    candidates: list[dict] = []
    for path in scope_files:
        if path.suffix.lower() != ".dart":
            continue
        rel_path = path.relative_to(repo_root)
        rel_str = rel_path.as_posix()
        text = read_text_safe(path)
        feature_name = derive_feature_name(rel_path)
        if feature_roots and feature_name not in feature_roots:
            continue
        for name, base in class_name_entries(text):
            classified = classify_dart_entry(name, base, rel_path)
            if classified is None:
                continue
            kind, _ = classified
            depth = len(rel_path.parts)
            direct_under_scope = 1 if scope_root and path.parent == scope_root else 0
            under_generic_dir = 1 if any(part in GENERIC_UI_DIRS for part in rel_path.parts) else 0
            role = classify_widget_role(name, rel_path, kind)
            score = role_score(role)
            score += 2 if direct_under_scope else 0
            if name.startswith("_"):
                score -= 3
            score -= under_generic_dir
            score -= max(0, depth - 8)
            candidates.append(
                {
                    "name": name,
                    "path": rel_str,
                    "kind": kind,
                    "role": role,
                    "score": score,
                    "confidence": role_confidence(role, under_generic_dir, name),
                }
            )
    candidates.sort(key=lambda item: (-item["score"], item["path"], item["name"]))
    primary_count = 0
    auxiliary_count = 0
    for item in candidates:
        if item["kind"] == "screen" and item["role"] == "primary_screen" and primary_count < MAX_PRIMARY_SCREENS:
            screens.append(
                {
                    "name": item["name"],
                    "path": item["path"],
                    "role": item["role"],
                    "confidence": item["confidence"],
                }
            )
            primary_count += 1
        elif item["kind"] == "screen" and item["role"] == "auxiliary_screen" and auxiliary_count < MAX_AUXILIARY_SCREENS:
            screens.append(
                {
                    "name": item["name"],
                    "path": item["path"],
                    "role": item["role"],
                    "confidence": item["confidence"],
                }
            )
            auxiliary_count += 1
        elif len(noise) < 12:
            noise.append(
                {
                    "name": item["name"],
                    "kind": item["kind"],
                    "reason": f"Widget role `{item['role']}` kept outside representative screens",
                }
            )
    screens = unique_dicts(screens, ("name", "path"))[:4]
    noise = unique_dicts(noise, ("name", "kind"))[:12]
    return screens, noise


def classify_widget_role(name: str, rel_path: Path, kind: str) -> str:
    if kind != "screen":
        return "non_screen"
    tokens = set(camel_tokens(name) + camel_tokens(rel_path.stem))
    if tokens.intersection(AUXILIARY_SCREEN_TOKENS):
        return "auxiliary_screen"
    if tokens.intersection(COMPONENT_SCREEN_TOKENS):
        return "component_screen"
    if tokens.intersection(PRIMARY_SCREEN_TOKENS):
        return "primary_screen"
    if any(part in GENERIC_UI_DIRS for part in rel_path.parts):
        return "component_screen"
    return "candidate_screen"


def role_score(role: str) -> int:
    if role == "primary_screen":
        return 6
    if role == "auxiliary_screen":
        return 5
    if role == "candidate_screen":
        return 4
    if role == "component_screen":
        return 1
    return 0


def role_confidence(role: str, under_generic_dir: int, name: str) -> float:
    if role == "primary_screen" and not under_generic_dir and not name.startswith("_"):
        return 0.9
    if role == "auxiliary_screen" and not name.startswith("_"):
        return 0.82
    return 0.66


def digest_scope_sources(flutter_path: Path | None, pr_diff_path: Path | None, tests_path: Path | None) -> dict:
    return {
        "feature_paths": [str(flutter_path)] if flutter_path else [],
        "pr_diff_path": str(pr_diff_path) if pr_diff_path else None,
        "tests_paths": collect_run_files(tests_path),
    }


def build_digest(
    repo_root: Path,
    profile_dir: Path,
    run_dir: Path,
    requirement_id: str,
    requirement_name: str,
    flutter_path: Path | None,
    pr_diff_path: Path | None,
    tests_path: Path | None,
    prd_path: Path | None,
    force: bool,
) -> dict:
    ensure_profile_dir(profile_dir)
    ensure_dir(run_dir)
    digest_json = run_dir / "flutter-feature-digest.json"
    digest_md = run_dir / "flutter-feature-digest.md"
    if (digest_json.exists() or digest_md.exists()) and not force:
        raise FileExistsError(f"digest artifacts already exist in {run_dir} (use --force to overwrite)")

    profile = {
        "feature_index": load_json(profile_dir / "feature_index.json"),
        "state_patterns": load_json(profile_dir / "state_patterns.json"),
        "data_flow_index": load_json(profile_dir / "data_flow_index.json"),
        "resource_index": load_json(profile_dir / "resource_index.json"),
        "test_index": load_json(profile_dir / "test_index.json"),
    }
    diff_files = parse_diff_files(pr_diff_path)
    scope_files = select_scope_files(repo_root, flutter_path, diff_files, tests_path)
    scoped_features = feature_names_for_scope(profile, scope_files, repo_root)
    primary_features, supporting_features = split_primary_supporting_features(repo_root, scope_files, flutter_path)
    en_arb = load_en_arb(repo_root)
    screens, noise_candidates = representative_screens(
        profile,
        scoped_features,
        scope_files,
        repo_root,
        preferred_root=flutter_path if flutter_path and flutter_path.is_dir() else None,
    )

    interactions: list[str] = []
    raw_strings: list[str] = []
    localized_strings: list[str] = []
    states: list[dict] = []
    evidence_files: list[str] = []
    api_calls: list[dict] = []
    models: list[dict] = []
    assets: list[dict] = []

    data_entries = profile["data_flow_index"]
    resource_entries = profile["resource_index"]
    representative_paths = {item["path"] for item in screens}
    for path in scope_files:
        rel = path.relative_to(repo_root).as_posix()
        evidence_files.append(rel)
        if path.suffix.lower() == ".dart":
            text = read_text_safe(path)
            if not representative_paths or rel in representative_paths:
                interactions.extend(extract_interactions(text))
                states.extend(extract_state_names(text))
                localized_strings.extend(extract_localized_texts(text, en_arb))
                raw_strings.extend(extract_string_literals(text))
        for key in ("apis", "repositories", "services", "models"):
            api_calls.extend(item for item in data_entries.get(key, []) if item.get("path") == rel)
        models.extend(item for item in data_entries.get("models", []) if item.get("path") == rel)
        assets.extend(item for item in resource_entries.get("assets", []) if item.get("path") == rel)

    strings = unique_preserve(localized_strings + raw_strings)[:12]

    confidence = "high" if scoped_features and screens else "medium" if scoped_features else "low"
    conflicts = []
    if prd_path is None:
        conflicts.append({"kind": "missing_prd", "reason": "No PRD supplied; digest is based on Flutter evidence only."})
    if not diff_files:
        conflicts.append({"kind": "missing_diff", "reason": "No PR diff supplied; digest is based on scope files and profile."})

    digest = {
        "requirement": {
            "id": requirement_id,
            "name": requirement_name,
        },
        "source": {
            "flutter_root": str(repo_root),
            "feature_paths": digest_scope_sources(flutter_path, pr_diff_path, tests_path)["feature_paths"],
            "change_range": None,
            "pr_diff_path": str(pr_diff_path) if pr_diff_path else None,
            "prd_path": str(prd_path) if prd_path else None,
            "tests_paths": digest_scope_sources(flutter_path, pr_diff_path, tests_path)["tests_paths"],
        },
        "scope": {
            "features": scoped_features,
            "primary_features": primary_features,
            "supporting_features": supporting_features,
            "confidence": confidence,
            "reasons": [
                f"scope_files={len(scope_files)}",
                f"representative_screens={len(screens)}",
            ],
        },
        "representative_screens": screens,
        "user_flows": [f"open_{screen['name']}" for screen in screens[:2]] + interactions[:3],
        "states": unique_dicts(states, ("name", "kind"))[:12],
        "interactions": unique_preserve(interactions)[:12],
        "api_calls": unique_dicts(api_calls, ("name", "path"))[:12],
        "models": unique_dicts(models, ("name", "path"))[:12],
        "strings": strings,
        "assets": unique_dicts(assets, ("path",))[:12],
        "tests": collect_run_files(tests_path),
        "noise_candidates": noise_candidates,
        "conflicts": conflicts,
        "evidence_files": unique_preserve(evidence_files)[:40],
    }

    write_json(digest_json, digest)
    write_text(digest_md, build_digest_markdown(digest))
    return digest


def build_digest_markdown(digest: dict) -> str:
    lines = [
        f"# Flutter Feature Digest: {digest['requirement']['name']}",
        "",
        "## 需求范围",
        "",
        f"- Requirement ID: `{digest['requirement']['id']}`",
        f"- Requirement Name: `{digest['requirement']['name']}`",
        f"- Scope Confidence: `{digest['scope']['confidence']}`",
        f"- Primary Features: `{', '.join(digest['scope'].get('primary_features', [])) or 'none'}`",
        f"- Supporting Features: `{', '.join(digest['scope'].get('supporting_features', [])) or 'none'}`",
        "",
        "## 代表页面",
        "",
    ]
    if digest["representative_screens"]:
        for item in digest["representative_screens"]:
            lines.append(f"- `{item['name']}` | role=`{item['role']}` | confidence=`{item['confidence']}`")
    else:
        lines.append("- None")
    lines.extend(["", "## 关键流程", ""])
    for item in digest["user_flows"][:8]:
        lines.append(f"- {item}")
    if not digest["user_flows"]:
        lines.append("- None")
    lines.extend(["", "## 状态与交互", ""])
    for item in digest["states"][:8]:
        lines.append(f"- State: `{item['name']}` (`{item['kind']}`)")
    for item in digest["interactions"][:8]:
        lines.append(f"- Interaction: `{item}`")
    if not digest["states"] and not digest["interactions"]:
        lines.append("- None")
    lines.extend(["", "## API / Model", ""])
    for item in digest["api_calls"][:8]:
        lines.append(f"- API: `{item['name']}`")
    for item in digest["models"][:8]:
        lines.append(f"- Model: `{item['name']}`")
    if not digest["api_calls"] and not digest["models"]:
        lines.append("- None")
    lines.extend(["", "## 文案 / 资源", ""])
    for item in digest["strings"][:8]:
        lines.append(f"- String: `{item}`")
    for item in digest["assets"][:8]:
        lines.append(f"- Asset: `{item['path']}`")
    if not digest["strings"] and not digest["assets"]:
        lines.append("- None")
    lines.extend(["", "## 噪音候选", ""])
    for item in digest["noise_candidates"][:12]:
        lines.append(f"- `{item['name']}`: {item['reason']}")
    if not digest["noise_candidates"]:
        lines.append("- None")
    lines.extend(["", "## 冲突", ""])
    for item in digest["conflicts"][:12]:
        lines.append(f"- `{item['kind']}`: {item['reason']}")
    if not digest["conflicts"]:
        lines.append("- None")
    return "\n".join(lines)


def handle_scan(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_repo_root(repo_root)
    ensure_dir(output_dir)
    stale_reasons = core_compute_stale_reasons(repo_root, output_dir, args.force)
    if not stale_reasons:
        print("Flutter profile is fresh.")
        print(f"- output_dir: {output_dir}")
        return
    build_repo_profile(
        repo_root=repo_root,
        output_dir=output_dir,
        include_tests=args.include_tests,
        max_files=args.max_files,
        platform="flutter",
    )
    print("Flutter profile generated.")
    print(f"- output_dir: {output_dir}")


def handle_digest(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).expanduser().resolve()
    profile_dir = Path(args.profile_dir).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    flutter_path = Path(args.flutter_path).expanduser().resolve() if args.flutter_path else None
    pr_diff_path = Path(args.pr_diff_path).expanduser().resolve() if args.pr_diff_path else None
    tests_path = Path(args.tests_path).expanduser().resolve() if args.tests_path else None
    prd_path = Path(args.prd_path).expanduser().resolve() if args.prd_path else None
    ensure_repo_root(repo_root)
    digest = build_digest(
        repo_root=repo_root,
        profile_dir=profile_dir,
        run_dir=run_dir,
        requirement_id=args.requirement_id,
        requirement_name=args.requirement_name,
        flutter_path=flutter_path,
        pr_diff_path=pr_diff_path,
        tests_path=tests_path,
        prd_path=prd_path,
        force=args.force,
    )
    print("Flutter feature digest generated.")
    print(f"- run_dir: {run_dir}")
    print(f"- scoped_features: {len(digest['scope']['features'])}")
    print(f"- representative_screens: {len(digest['representative_screens'])}")


def handle_status(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_repo_root(repo_root)
    meta = core_load_scan_meta(output_dir)
    stale_reasons = core_compute_stale_reasons(repo_root, output_dir, force=False)
    print("Flutter profile status:")
    print(f"- repo_root: {repo_root}")
    print(f"- output_dir: {output_dir}")
    print(f"- exists: {'yes' if meta else 'no'}")
    print(f"- stale: {'yes' if stale_reasons else 'no'}")
    if meta:
        print(f"- generated_at: {meta.get('generated_at')}")
        if meta.get("git", {}).get("head"):
            print(f"- git_head: {meta['git']['head']}")
    if stale_reasons:
        print("- stale_reasons:")
        for reason in stale_reasons:
            print(f"  - {reason}")


def handle_invalidate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).expanduser().resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
        print(f"Invalidated: {output_dir}")
    else:
        print(f"No profile directory found: {output_dir}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "scan":
            handle_scan(args)
        elif args.command == "digest":
            handle_digest(args)
        elif args.command == "status":
            handle_status(args)
        elif args.command == "invalidate":
            handle_invalidate(args)
        else:
            parser.error(f"unsupported command: {args.command}")
    except Exception as exc:  # pragma: no cover - CLI guard
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
