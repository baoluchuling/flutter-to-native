#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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

PROFILE_FILES = {
    "scan_meta.json",
    "feature_index.json",
    "route_map.json",
    "state_patterns.json",
    "data_flow_index.json",
    "resource_index.json",
    "test_index.json",
    "repo_summary.md",
}


@dataclass
class GitInfo:
    head: str | None
    branch: str | None
    dirty: bool | None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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

    output_dir.mkdir(parents=True, exist_ok=True)
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
