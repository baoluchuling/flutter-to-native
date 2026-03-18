#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from flutter_profile_scan_core import (
    PROFILE_FILES as FLUTTER_PROFILE_FILES,
    scan_flutter_repo,
)


IGNORE_DIR_NAMES = {
    ".git",
    ".ai",
    ".build",
    "Pods",
    "Carthage",
    "DerivedData",
    "build",
}
GENERIC_PARTS = {
    "ios",
    "src",
    "source",
    "app",
    "apps",
    "module",
    "modules",
    "reader",
    "feature",
    "features",
    "ui",
    "views",
    "view",
    "controller",
    "controllers",
    "model",
    "models",
    "service",
    "services",
    "common",
    "shared",
    "core",
}
ROLE_SUFFIXES = (
    "ViewController",
    "ViewModel",
    "Controller",
    "View",
    "Service",
    "Manager",
    "Repository",
    "Router",
    "Coordinator",
    "ActionHandler",
    "Handler",
    "Interactor",
    "Model",
    "Store",
    "Context",
    "Presenter",
)
TEST_PARTS = {"test", "tests", "uitests", "integrationtests"}

SUPPORTED_PLATFORMS = {"native", "flutter"}

REQUIRED_ASSET_FILES_NATIVE = {
    "feature_registry.json",
    "host_mapping.json",
    "symbol_graph.jsonl",
    "relation_graph.jsonl",
    "feature_file_index.json",
    "scan_meta.yaml",
}

REQUIRED_ASSET_FILES_FLUTTER = set(FLUTTER_PROFILE_FILES)

# Backward compatibility for wrappers that import REQUIRED_ASSET_FILES.
REQUIRED_ASSET_FILES = REQUIRED_ASSET_FILES_NATIVE


@dataclass
class GitInfo:
    head: str | None
    branch: str | None
    dirty: bool | None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def ensure_repo_root(repo_root: Path) -> None:
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"repo root not found or unreadable: {repo_root}")


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def normalize_platform(platform: str | None) -> str:
    value = (platform or "native").strip().lower()
    if value not in SUPPORTED_PLATFORMS:
        raise ValueError(f"unsupported platform: {platform}")
    return value


def required_asset_files_for_platform(platform: str) -> set[str]:
    return REQUIRED_ASSET_FILES_NATIVE if platform == "native" else REQUIRED_ASSET_FILES_FLUTTER


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    content = "\n".join(json.dumps(item, ensure_ascii=False) for item in rows)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")


def yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or any(ch in text for ch in [":", "#", "[", "]", "{", "}", ",", "\n"]):
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


def dump_yaml(value, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def to_snake_case(name: str) -> str:
    if not name:
        return ""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower()


def title_from_feature_id(feature_id: str) -> str:
    slug = feature_id.removeprefix("feature.")
    return " ".join(part.capitalize() for part in slug.split("_") if part)


def feature_slug_from_file(rel_path: str) -> str:
    path = Path(rel_path)
    stem = path.stem
    base = stem
    for suffix in ROLE_SUFFIXES:
        if base.endswith(suffix) and len(base) > len(suffix):
            base = base[: -len(suffix)]
            break
    if base:
        slug = to_snake_case(base)
        if slug:
            return slug
    dirs = [part for part in path.parts[:-1] if part.lower() not in GENERIC_PARTS]
    if dirs:
        slug = to_snake_case(dirs[-1])
        if slug:
            return slug
    return "misc"


def classify_symbol_role(name: str) -> str | None:
    if name.endswith("ViewController") or name.endswith("PageController"):
        return "page_hosts"
    if name.endswith(("ActionHandler", "Router", "Coordinator", "Interactor", "Handler")):
        return "action_hosts"
    if name.endswith(("ViewModel", "Store", "State", "Context", "Presenter", "Bloc", "Cubit", "Notifier")):
        return "state_hosts"
    if name.endswith(("Service", "Repository", "Client", "Api", "Manager", "Datasource")):
        return "data_hosts"
    if any(token in name for token in ("Tracker", "Analytics", "Logger", "Reporter")):
        return "side_effect_hosts"
    return None


def infer_symbol_kind(keyword: str) -> str:
    mapping = {
        "class": "class",
        "struct": "struct",
        "enum": "enum",
        "protocol": "protocol",
    }
    return mapping.get(keyword, "symbol")


def extract_file_profile(repo_root: Path, abs_path: Path) -> dict:
    rel_path = abs_path.relative_to(repo_root).as_posix()
    text = read_text(abs_path)
    feature_slug = feature_slug_from_file(rel_path)
    feature_id = f"feature.{feature_slug}"
    feature_name = title_from_feature_id(feature_id)

    imports = sorted(set(re.findall(r"^\s*import\s+([A-Za-z0-9_\.]+)", text, flags=re.MULTILINE)))
    symbol_matches = list(
        re.finditer(
            r"^\s*(?:public|open|internal|private|fileprivate)?\s*(?:final\s+)?(class|struct|enum|protocol)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*([^{]+))?",
            text,
            flags=re.MULTILINE,
        )
    )
    symbols: list[dict] = []
    inherits: list[dict] = []
    host_roles: dict[str, set[str]] = {
        "page_hosts": set(),
        "action_hosts": set(),
        "state_hosts": set(),
        "data_hosts": set(),
        "side_effect_hosts": set(),
    }
    for match in symbol_matches:
        symbol_kind = infer_symbol_kind(match.group(1))
        symbol_name = match.group(2)
        symbol_id = f"{symbol_kind}:{symbol_name}"
        line = text.count("\n", 0, match.start()) + 1
        signature = match.group(0).strip()
        symbols.append(
            {
                "id": symbol_id,
                "name": symbol_name,
                "kind": symbol_kind,
                "line": line,
                "signature": signature,
            }
        )
        role = classify_symbol_role(symbol_name)
        if role:
            host_roles[role].add(symbol_name)
        parent_expr = (match.group(3) or "").strip()
        if parent_expr:
            parts = [part.strip() for part in parent_expr.split(",") if part.strip()]
            for part in parts:
                parent = re.sub(r"<.*>", "", part).strip()
                if parent:
                    inherits.append({"from": symbol_id, "to_type": parent})

    referenced_tokens = sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\b", text)))
    called_tokens = sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\(", text)))
    module = Path(rel_path).parts[0] if len(Path(rel_path).parts) > 1 else "root"

    return {
        "file_path": rel_path,
        "module": module,
        "feature_id": feature_id,
        "feature_name": feature_name,
        "symbols": symbols,
        "imports": imports,
        "inherits": inherits,
        "host_roles": {key: sorted(values) for key, values in host_roles.items()},
        "referenced_tokens": referenced_tokens,
        "called_tokens": called_tokens,
    }


def is_test_path(rel_path: Path) -> bool:
    parts_lower = [part.lower() for part in rel_path.parts]
    return any(part in TEST_PARTS for part in parts_lower)


def should_skip_path(rel_path: Path, include_tests: bool) -> bool:
    if any(part in IGNORE_DIR_NAMES for part in rel_path.parts):
        return True
    if not include_tests and is_test_path(rel_path):
        return True
    return False


def iter_swift_files(repo_root: Path, include_tests: bool, max_files: int, only_paths: set[str] | None = None) -> list[Path]:
    if only_paths is not None:
        files: list[Path] = []
        for raw in sorted(only_paths):
            rel = Path(normalize_rel_path(raw))
            abs_path = repo_root / rel
            if rel.suffix != ".swift":
                continue
            if not abs_path.exists() or not abs_path.is_file():
                continue
            if should_skip_path(rel, include_tests):
                continue
            files.append(abs_path)
        if max_files > 0:
            return files[:max_files]
        return files

    files = []
    for path in repo_root.rglob("*.swift"):
        rel = path.relative_to(repo_root)
        if should_skip_path(rel, include_tests):
            continue
        files.append(path)
        if max_files > 0 and len(files) >= max_files:
            break
    return files


def _feature_alias(name: str) -> str:
    return name.lower().strip()


def _build_assets_from_profiles(profiles: list[dict], repo_root: Path, scan_scope: str, changed_paths: list[str], git_info: GitInfo) -> dict:
    feature_registry_map: dict[str, dict] = {}
    host_mapping_map: dict[str, dict] = {}
    symbol_graph_rows: list[dict] = []
    relation_rows: list[dict] = []
    module_counts: dict[str, int] = {}

    symbol_name_to_ids: dict[str, list[str]] = {}
    file_to_symbols: dict[str, list[str]] = {}
    for profile in profiles:
        module_counts[profile["module"]] = module_counts.get(profile["module"], 0) + 1
        symbol_ids = []
        for symbol in profile["symbols"]:
            symbol_graph_rows.append(
                {
                    "id": symbol["id"],
                    "name": symbol["name"],
                    "kind": symbol["kind"],
                    "file_path": profile["file_path"],
                    "line": symbol["line"],
                    "module": profile["module"],
                    "feature_id": profile["feature_id"],
                }
            )
            symbol_name_to_ids.setdefault(symbol["name"], []).append(symbol["id"])
            symbol_ids.append(symbol["id"])
        file_to_symbols[profile["file_path"]] = symbol_ids

    relation_set: set[tuple[str, str, str]] = set()
    for profile in profiles:
        file_node = f"file:{profile['file_path']}"
        feature_id = profile["feature_id"]
        if feature_id not in feature_registry_map:
            feature_registry_map[feature_id] = {
                "feature_id": feature_id,
                "name": profile["feature_name"],
                "description": f"Auto-profiled feature cluster for {profile['feature_name']}.",
                "aliases": [_feature_alias(profile["feature_name"])],
                "related_features": [],
                "status": "active",
                "source_refs": ["repo_profile_core"],
                "last_seen_commit": git_info.head or "unknown",
            }
        mapping = host_mapping_map.setdefault(
            feature_id,
            {
                "feature_id": feature_id,
                "page_hosts": set(),
                "action_hosts": set(),
                "state_hosts": set(),
                "data_hosts": set(),
                "side_effect_hosts": set(),
                "code_entities": set(),
            },
        )
        for key in ("page_hosts", "action_hosts", "state_hosts", "data_hosts", "side_effect_hosts"):
            mapping[key].update(profile["host_roles"].get(key, []))
        mapping["code_entities"].add(profile["file_path"])

        for symbol_id in file_to_symbols.get(profile["file_path"], []):
            relation_set.add((file_node, "DECLARES", symbol_id))
            relation_set.add((symbol_id, "RELATED_TO_FEATURE", feature_id))
        relation_set.add((file_node, "BELONGS_TO_MODULE", f"module:{profile['module']}"))
        for module_name in profile.get("imports", []):
            relation_set.add((file_node, "IMPORTS", f"module:{module_name}"))
        for link in profile.get("inherits", []):
            target_ids = symbol_name_to_ids.get(link["to_type"])
            if target_ids:
                relation_set.add((link["from"], "IMPLEMENTS", target_ids[0]))
            else:
                relation_set.add((link["from"], "IMPLEMENTS", f"type:{link['to_type']}"))
        target_ids = [ids[0] for ids in symbol_name_to_ids.values() if ids]
        target_id_set = set(target_ids)
        for symbol_id in file_to_symbols.get(profile["file_path"], []):
            for token in profile.get("called_tokens", []):
                ids = symbol_name_to_ids.get(token, [])
                if not ids:
                    continue
                target_id = ids[0]
                if target_id != symbol_id and target_id in target_id_set:
                    relation_set.add((symbol_id, "CALLS", target_id))
            for token in profile.get("referenced_tokens", []):
                ids = symbol_name_to_ids.get(token, [])
                if not ids:
                    continue
                target_id = ids[0]
                if target_id != symbol_id and target_id in target_id_set:
                    relation_set.add((symbol_id, "USES_TYPE", target_id))

    for from_id, edge_type, to_id in sorted(relation_set):
        relation_rows.append({"from": from_id, "type": edge_type, "to": to_id})

    feature_registry = sorted(feature_registry_map.values(), key=lambda item: item["feature_id"])
    host_mapping = []
    for feature_id in sorted(host_mapping_map):
        item = host_mapping_map[feature_id]
        host_mapping.append(
            {
                "feature_id": feature_id,
                "page_hosts": sorted(item["page_hosts"]),
                "action_hosts": sorted(item["action_hosts"]),
                "state_hosts": sorted(item["state_hosts"]),
                "data_hosts": sorted(item["data_hosts"]),
                "side_effect_hosts": sorted(item["side_effect_hosts"]),
                "code_entities": sorted(item["code_entities"]),
            }
        )

    module_index = {
        "modules": [
            {"module": module, "file_count": count}
            for module, count in sorted(module_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
    }

    scan_meta = {
        "schema_version": "repo-profile-core.v2",
        "generated_at": utc_now_iso(),
        "repo_root": str(repo_root.resolve()),
        "scan_scope": scan_scope,
        "head_commit": git_info.head,
        "branch": git_info.branch,
        "dirty": git_info.dirty,
        "changed_paths": sorted(changed_paths),
        "counts": {
            "files": len(profiles),
            "features": len(feature_registry),
            "symbols": len(symbol_graph_rows),
            "relations": len(relation_rows),
        },
    }

    return {
        "feature_registry": feature_registry,
        "host_mapping": host_mapping,
        "symbol_graph": symbol_graph_rows,
        "relation_graph": relation_rows,
        "feature_file_index": sorted(profiles, key=lambda item: item["file_path"]),
        "module_index": module_index,
        "scan_meta": scan_meta,
    }


def _write_assets(output_dir: Path, assets: dict) -> None:
    write_json(output_dir / "feature_registry.json", assets["feature_registry"])
    write_json(output_dir / "host_mapping.json", assets["host_mapping"])
    write_jsonl(output_dir / "symbol_graph.jsonl", assets["symbol_graph"])
    write_jsonl(output_dir / "relation_graph.jsonl", assets["relation_graph"])
    write_json(output_dir / "feature_file_index.json", assets["feature_file_index"])
    write_json(output_dir / "module_index.json", assets["module_index"])
    (output_dir / "scan_meta.yaml").write_text("\n".join(dump_yaml(assets["scan_meta"])) + "\n", encoding="utf-8")


def _collect_profiles(repo_root: Path, include_tests: bool, max_files: int, only_paths: set[str] | None = None) -> list[dict]:
    files = iter_swift_files(repo_root, include_tests=include_tests, max_files=max_files, only_paths=only_paths)
    return [extract_file_profile(repo_root, path) for path in files]


def summarize_flutter_counts(payload: dict) -> dict:
    meta = payload.get("scan_meta", {})
    raw_counts = meta.get("counts", {})
    feature_count = len(payload.get("feature_index", {}).get("features", []))
    symbols = 0
    for item in payload.get("feature_index", {}).get("features", []):
        symbols += len(item.get("screens", []))
        symbols += len(item.get("components", []))
        symbols += len(item.get("state_holders", []))
        symbols += len(item.get("services", []))
        symbols += len(item.get("models", []))
    files = int(raw_counts.get("dart_files", 0)) + int(raw_counts.get("arb_files", 0)) + int(raw_counts.get("asset_files", 0))
    return {
        "files": files,
        "features": feature_count,
        "symbols": symbols,
        "relations": len(payload.get("route_map", {}).get("route_definitions", [])),
    }


def build_profile(repo_root: Path, output_dir: Path, include_tests: bool, max_files: int, platform: str = "native") -> dict:
    ensure_repo_root(repo_root)
    ensure_output_dir(output_dir)
    platform = normalize_platform(platform)
    if platform == "flutter":
        payload = scan_flutter_repo(
            repo_root=repo_root,
            output_dir=output_dir,
            include_tests=include_tests,
            max_files=max_files,
        )
        return summarize_flutter_counts(payload)

    profiles = _collect_profiles(repo_root=repo_root, include_tests=include_tests, max_files=max_files)
    assets = _build_assets_from_profiles(
        profiles=profiles,
        repo_root=repo_root,
        scan_scope="full",
        changed_paths=[],
        git_info=collect_git_info(repo_root),
    )
    _write_assets(output_dir, assets)
    return assets["scan_meta"]["counts"]


def _load_feature_file_index(output_dir: Path) -> list[dict]:
    path = output_dir / "feature_file_index.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict) and item.get("file_path")]


def update_profile(
    repo_root: Path,
    output_dir: Path,
    changed_paths: list[str],
    include_tests: bool,
    max_files: int,
    platform: str = "native",
) -> dict:
    ensure_repo_root(repo_root)
    ensure_output_dir(output_dir)
    platform = normalize_platform(platform)
    if not changed_paths:
        raise ValueError("update_profile requires at least one changed path")
    if platform == "flutter":
        return build_profile(
            repo_root=repo_root,
            output_dir=output_dir,
            include_tests=include_tests,
            max_files=max_files,
            platform=platform,
        )

    existing = _load_feature_file_index(output_dir)
    existing_by_path = {
        normalize_rel_path(str(item["file_path"])): item
        for item in existing
    }
    normalized_changed = sorted({normalize_rel_path(path) for path in changed_paths if normalize_rel_path(path)})
    for path in normalized_changed:
        existing_by_path.pop(path, None)

    changed_profiles = _collect_profiles(
        repo_root=repo_root,
        include_tests=include_tests,
        max_files=max_files,
        only_paths=set(normalized_changed),
    )
    for profile in changed_profiles:
        existing_by_path[normalize_rel_path(profile["file_path"])] = profile

    profiles = [existing_by_path[path] for path in sorted(existing_by_path)]
    assets = _build_assets_from_profiles(
        profiles=profiles,
        repo_root=repo_root,
        scan_scope="changed",
        changed_paths=normalized_changed,
        git_info=collect_git_info(repo_root),
    )
    _write_assets(output_dir, assets)
    return assets["scan_meta"]["counts"]


def parse_changed_file_list(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"changed-files list not found: {path}")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [normalize_rel_path(line) for line in lines]


def git_changed_paths(repo_root: Path, diff_from: str, diff_to: str) -> list[str]:
    output = run_git(repo_root, ["diff", "--name-only", diff_from, diff_to])
    if output is None:
        return []
    return [normalize_rel_path(line) for line in output.splitlines() if line.strip()]


def required_assets_missing(output_dir: Path, platform: str = "native") -> list[str]:
    normalized = normalize_platform(platform)
    required = required_asset_files_for_platform(normalized)
    return [name for name in sorted(required) if not (output_dir / name).exists()]


def handle_build(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    platform = normalize_platform(getattr(args, "platform", "native"))
    if output_dir.exists() and not args.force:
        missing = required_assets_missing(output_dir, platform=platform)
        if not missing:
            raise FileExistsError(f"output dir already has complete assets: {output_dir} (use --force to rebuild)")
    counts = build_profile(
        repo_root=repo_root,
        output_dir=output_dir,
        include_tests=args.include_tests,
        max_files=args.max_files,
        platform=platform,
    )
    print("Repo profile build completed.")
    print(f"- platform: {platform}")
    print(f"- output_dir: {output_dir}")
    print(f"- files: {counts['files']}")
    print(f"- features: {counts['features']}")
    print(f"- symbols: {counts.get('symbols', 0)}")
    return 0


def handle_update(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    platform = normalize_platform(getattr(args, "platform", "native"))
    changed: list[str] = []
    if args.changed_files:
        changed.extend(parse_changed_file_list(Path(args.changed_files).expanduser().resolve()))
    if args.diff_from:
        changed.extend(git_changed_paths(repo_root, args.diff_from, args.diff_to))
    changed = sorted(set(changed))
    if not changed:
        raise ValueError("no changed files found; provide --changed-files or --diff-from")
    has_incremental_index = (output_dir / "feature_file_index.json").exists() if platform == "native" else False
    if not has_incremental_index:
        counts = build_profile(
            repo_root=repo_root,
            output_dir=output_dir,
            include_tests=args.include_tests,
            max_files=args.max_files,
            platform=platform,
        )
        print("No previous index found; executed full build.")
    else:
        counts = update_profile(
            repo_root=repo_root,
            output_dir=output_dir,
            changed_paths=changed,
            include_tests=args.include_tests,
            max_files=args.max_files,
            platform=platform,
        )
    print("Repo profile update completed.")
    print(f"- platform: {platform}")
    print(f"- output_dir: {output_dir}")
    print(f"- changed_paths: {len(changed)}")
    print(f"- files: {counts['files']}")
    print(f"- features: {counts['features']}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    platform = normalize_platform(getattr(args, "platform", "native"))
    ensure_repo_root(repo_root)
    print("Repo profile status:")
    print(f"- platform: {platform}")
    print(f"- repo_root: {repo_root}")
    print(f"- output_dir: {output_dir}")
    required = required_asset_files_for_platform(platform)
    missing = required_assets_missing(output_dir, platform=platform) if output_dir.exists() else sorted(required)
    print(f"- exists: {'yes' if output_dir.exists() else 'no'}")
    print(f"- complete: {'yes' if not missing else 'no'}")
    if missing:
        print("- missing_assets:")
        for item in missing:
            print(f"  - {item}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repo Profile Core for Atlas v2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build full repository profile assets")
    build.add_argument("--repo-root", required=True, help="Path to target repository")
    build.add_argument("--output-dir", required=True, help="Path to profile output directory")
    build.add_argument("--platform", choices=("native", "flutter"), default="native")
    build.add_argument("--include-tests", action=argparse.BooleanOptionalAction, default=True)
    build.add_argument("--max-files", type=int, default=0)
    build.add_argument("--force", action="store_true", help="Overwrite existing assets")

    update = subparsers.add_parser("update", help="Incrementally update profile assets")
    update.add_argument("--repo-root", required=True, help="Path to target repository")
    update.add_argument("--output-dir", required=True, help="Path to profile output directory")
    update.add_argument("--platform", choices=("native", "flutter"), default="native")
    update.add_argument("--changed-files", help="Path to newline-delimited changed file list")
    update.add_argument("--diff-from", help="Git revision for diff start")
    update.add_argument("--diff-to", default="HEAD", help="Git revision for diff end (default HEAD)")
    update.add_argument("--include-tests", action=argparse.BooleanOptionalAction, default=True)
    update.add_argument("--max-files", type=int, default=0)

    status = subparsers.add_parser("status", help="Show profile asset status")
    status.add_argument("--repo-root", required=True, help="Path to target repository")
    status.add_argument("--output-dir", required=True, help="Path to profile output directory")
    status.add_argument("--platform", choices=("native", "flutter"), default="native")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "build":
            return handle_build(args)
        if args.command == "update":
            return handle_update(args)
        if args.command == "status":
            return handle_status(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 5
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"repo-profile-core error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
