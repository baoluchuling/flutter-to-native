#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


OUTPUT_FILE = "llm_intent_resolution.json"
PROMPT_FILE = "llm_intent_prompt.md"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas intent resolver for CLI/agent model integration")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve", help="Generate llm intent resolution artifact")
    resolve.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    resolve.add_argument("--provider", choices=("none", "agent", "cli"), default="none")
    resolve.add_argument("--feature-intent-path", help="Optional feature_intent_spec path for prompt context")
    resolve.add_argument("--agent-response-path", help="Required when provider=agent")
    resolve.add_argument("--cli-command", help="Required when provider=cli")
    resolve.add_argument("--requirement-id", help="Optional requirement id used in output metadata")
    resolve.add_argument("--requirement-name", help="Optional requirement name used in output metadata")
    resolve.add_argument("--output-path", help="Optional output JSON path (default <run-dir>/llm_intent_resolution.json)")
    resolve.add_argument("--timeout-seconds", type=int, default=60)
    resolve.add_argument("--force", action="store_true", help="Overwrite existing output file")

    status = subparsers.add_parser("status", help="Report resolver artifact status")
    status.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    status.add_argument("--output-path", help="Optional output JSON path override")
    return parser


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_resolution_payload(provider: str, requirement_id: str, requirement_name: str, payload: dict) -> dict:
    model = str(payload.get("model") or payload.get("model_name") or "unknown")
    confidence_raw = str(payload.get("confidence") or "").strip().lower()
    confidence = confidence_raw if confidence_raw in {"low", "medium", "high"} else "low"
    suggested_feature_ids = [
        str(item).strip()
        for item in payload.get("suggested_feature_ids", [])
        if str(item).strip()
    ]
    suggested_paths = [
        str(item).strip()
        for item in payload.get("suggested_paths", [])
        if str(item).strip()
    ]
    rationale = str(payload.get("rationale") or "No rationale provided.")
    warnings = [str(item) for item in payload.get("warnings", []) if str(item).strip()]

    return {
        "provider": provider,
        "model": model,
        "generated_at": utc_now_iso(),
        "requirement": {
            "id": requirement_id or "unknown",
            "name": requirement_name or "unknown",
        },
        "confidence": confidence,
        "suggested_feature_ids": suggested_feature_ids,
        "suggested_paths": suggested_paths,
        "rationale": rationale,
        "warnings": warnings,
    }


def extract_json_from_text(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(stripped[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def build_prompt(requirement_id: str, requirement_name: str, feature_intent_text: str) -> str:
    return "\n".join(
        [
            "# Atlas LLM Intent Resolution Prompt",
            "",
            "Return a JSON object only. Do not return markdown.",
            "",
            "Required JSON fields:",
            '- "model": string',
            '- "confidence": "low" | "medium" | "high"',
            '- "suggested_feature_ids": string[]',
            '- "suggested_paths": string[]',
            '- "rationale": string',
            '- "warnings": string[]',
            "",
            f"Requirement ID: {requirement_id or 'unknown'}",
            f"Requirement Name: {requirement_name or 'unknown'}",
            "",
            "feature_intent_spec excerpt:",
            feature_intent_text[:4000] if feature_intent_text else "(empty)",
            "",
            "Output JSON now.",
        ]
    )


def resolve_from_agent(agent_response_path: Path) -> dict:
    if not agent_response_path.exists():
        raise FileNotFoundError(f"agent response path not found: {agent_response_path}")
    payload = extract_json_from_text(read_text(agent_response_path))
    if not payload:
        raise ValueError("agent response path did not contain a valid JSON object")
    return payload


def resolve_from_cli(
    command: str,
    prompt_path: Path,
    output_path: Path,
    timeout_seconds: int,
) -> dict:
    env = dict(os.environ)
    env["ATLAS_PROMPT_PATH"] = str(prompt_path)
    env["ATLAS_OUTPUT_PATH"] = str(output_path)
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"cli command failed with exit code {completed.returncode}: {completed.stderr.strip()[:300]}")
    if output_path.exists():
        from_file = extract_json_from_text(read_text(output_path))
        if from_file:
            return from_file
    payload = extract_json_from_text(completed.stdout or "")
    if not payload:
        raise ValueError("cli command completed, but no valid JSON object was found in stdout or output file")
    return payload


def resolve_output_path(run_dir: Path, output_path_arg: str | None) -> Path:
    if output_path_arg:
        return Path(output_path_arg).expanduser().resolve()
    return (run_dir / OUTPUT_FILE).resolve()


def handle_resolve(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"run dir not found or unreadable: {run_dir}")

    output_path = resolve_output_path(run_dir, args.output_path)
    if output_path.exists() and not args.force:
        raise FileExistsError(f"output already exists: {output_path} (use --force to overwrite)")

    feature_intent_path = (
        Path(args.feature_intent_path).expanduser().resolve()
        if args.feature_intent_path
        else (run_dir / "feature_intent_spec.yaml")
    )
    feature_intent_text = read_text(feature_intent_path) if feature_intent_path.exists() else ""
    requirement_id = str(args.requirement_id or "")
    requirement_name = str(args.requirement_name or "")
    prompt_text = build_prompt(requirement_id, requirement_name, feature_intent_text)
    prompt_path = (run_dir / PROMPT_FILE).resolve()
    prompt_path.write_text(prompt_text + "\n", encoding="utf-8")

    if args.provider == "none":
        raw_payload = {}
    elif args.provider == "agent":
        if not args.agent_response_path:
            raise FileNotFoundError("--agent-response-path is required when provider=agent")
        raw_payload = resolve_from_agent(Path(args.agent_response_path).expanduser().resolve())
    else:
        if not args.cli_command:
            raise FileNotFoundError("--cli-command is required when provider=cli")
        raw_payload = resolve_from_cli(
            command=args.cli_command,
            prompt_path=prompt_path,
            output_path=output_path,
            timeout_seconds=max(5, int(args.timeout_seconds)),
        )

    normalized = normalize_resolution_payload(
        provider=args.provider,
        requirement_id=requirement_id,
        requirement_name=requirement_name,
        payload=raw_payload,
    )
    write_json(output_path, normalized)
    print("LLM intent resolution generated.")
    print(f"- output_path: {output_path}")
    print(f"- provider: {normalized['provider']}")
    print(f"- suggested_feature_ids: {len(normalized['suggested_feature_ids'])}")
    print(f"- suggested_paths: {len(normalized['suggested_paths'])}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    output_path = resolve_output_path(run_dir, args.output_path)
    if not output_path.exists():
        print("Resolver status: pending")
        print(f"- output_path: {output_path}")
        return 0
    payload = extract_json_from_text(read_text(output_path))
    print("Resolver status: present")
    print(f"- output_path: {output_path}")
    print(f"- provider: {payload.get('provider', 'unknown')}")
    print(f"- confidence: {payload.get('confidence', 'unknown')}")
    print(f"- suggested_feature_ids: {len(payload.get('suggested_feature_ids', []))}")
    print(f"- suggested_paths: {len(payload.get('suggested_paths', []))}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "resolve":
            return handle_resolve(args)
        if args.command == "status":
            return handle_status(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 5
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"atlas-intent-resolver error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
