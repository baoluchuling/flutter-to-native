#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo_profile_core import (
    REQUIRED_ASSET_FILES,
    build_profile,
    git_changed_paths,
    parse_changed_file_list,
    required_assets_missing,
    update_profile,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Profiler for iOS native repositories (v2 only)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Create or refresh native-profile-v2")
    scan.add_argument("--repo-root", required=True, help="Path to the iOS repository")
    scan.add_argument("--output-dir", required=True, help="Path to .ai/t2n/native-profile-v2")
    scan.add_argument("--force", action="store_true", help="Force rebuild even if profile looks fresh")
    scan.add_argument("--scope", choices=("full", "changed"), default="full")
    scan.add_argument("--changed-files", help="Optional newline-delimited changed file list")
    scan.add_argument("--diff-from", help="Optional git revision for changed scope start")
    scan.add_argument("--diff-to", default="HEAD", help="Optional git revision for changed scope end")
    scan.add_argument("--include-tests", action=argparse.BooleanOptionalAction, default=True)
    scan.add_argument("--max-files", type=int, default=0, help="Optional limit for scanned files")

    status = subparsers.add_parser("status", help="Report v2 profile status")
    status.add_argument("--repo-root", required=True, help="Path to the iOS repository")
    status.add_argument("--output-dir", required=True, help="Path to .ai/t2n/native-profile-v2")

    invalidate = subparsers.add_parser("invalidate", help="Invalidate v2 profile")
    invalidate.add_argument("--output-dir", required=True, help="Path to .ai/t2n/native-profile-v2")

    return parser


def ensure_repo_root(repo_root: Path) -> None:
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"repo root not found or unreadable: {repo_root}")


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def collect_changed_paths(repo_root: Path, args: argparse.Namespace) -> list[str]:
    changed: list[str] = []
    if getattr(args, "changed_files", None):
        changed.extend(parse_changed_file_list(Path(args.changed_files).expanduser().resolve()))
    if getattr(args, "diff_from", None):
        changed.extend(git_changed_paths(repo_root, args.diff_from, getattr(args, "diff_to", "HEAD")))
    return sorted(set(changed))


def handle_scan(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_repo_root(repo_root)
    ensure_output_dir(output_dir)

    missing_assets = required_assets_missing(output_dir)
    if args.scope == "full":
        if not args.force and not missing_assets:
            print("Profile is fresh; no scan performed.")
            return 0
        counts = build_profile(
            repo_root=repo_root,
            output_dir=output_dir,
            include_tests=args.include_tests,
            max_files=args.max_files,
        )
        print("Profile build completed.")
        print(f"- output_dir: {output_dir}")
        print(f"- files: {counts['files']}")
        print(f"- features: {counts['features']}")
        print(f"- symbols: {counts['symbols']}")
        return 0

    changed_paths = collect_changed_paths(repo_root, args)
    if changed_paths and not missing_assets:
        counts = update_profile(
            repo_root=repo_root,
            output_dir=output_dir,
            changed_paths=changed_paths,
            include_tests=args.include_tests,
            max_files=args.max_files,
        )
        print("Profile update completed.")
        print(f"- output_dir: {output_dir}")
        print(f"- changed_paths: {len(changed_paths)}")
        print(f"- files: {counts['files']}")
        print(f"- features: {counts['features']}")
        return 0

    if not changed_paths:
        print("No changed files detected for changed scope; running full build.")
    if missing_assets:
        print("Profile assets incomplete; running full build.")
    counts = build_profile(
        repo_root=repo_root,
        output_dir=output_dir,
        include_tests=args.include_tests,
        max_files=args.max_files,
    )
    print("Profile build completed.")
    print(f"- output_dir: {output_dir}")
    print(f"- files: {counts['files']}")
    print(f"- features: {counts['features']}")
    print(f"- symbols: {counts['symbols']}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_repo_root(repo_root)
    missing_assets = required_assets_missing(output_dir)

    print("Profile status:")
    print(f"- repo_root: {repo_root}")
    print(f"- output_dir: {output_dir}")
    print(f"- exists: {'yes' if output_dir.exists() else 'no'}")
    print(f"- complete: {'yes' if output_dir.exists() and not missing_assets else 'no'}")
    if missing_assets:
        print("- missing_assets:")
        for name in missing_assets:
            print(f"  - {name}")
    return 0


def handle_invalidate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    removed = 0
    for name in sorted(REQUIRED_ASSET_FILES):
        path = output_dir / name
        if path.exists():
            path.unlink()
            removed += 1
    module_index = output_dir / "module_index.json"
    if module_index.exists():
        module_index.unlink()
        removed += 1

    if removed:
        print("Profile invalidated.")
        print(f"- removed_files: {removed}")
    else:
        print("Profile already invalid.")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "scan":
            return handle_scan(args)
        if args.command == "status":
            return handle_status(args)
        if args.command == "invalidate":
            return handle_invalidate(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"atlas-profiler error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
