#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


try:
    from atlas_planner import GLOBAL_RISK_TOKENS
except ImportError:
    GLOBAL_RISK_TOKENS = (
        "appdelegate",
        "scenedelegate",
        "router",
        "routing",
        "route",
        "coordinator",
        "deeplink",
        "bootstrap",
        "assembly",
    )


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _normalize_rel_path(path: str, repo_root: Path | None = None) -> str:
    text = path.replace("\\", "/").strip()
    if not text:
        return text
    if repo_root:
        resolved_root = repo_root.resolve()
        try:
            candidate = Path(text).resolve()
            if candidate.is_absolute() and resolved_root in candidate.parents:
                return candidate.relative_to(resolved_root).as_posix()
        except OSError:
            pass
    return text.lstrip("./")


def _infer_kind(path: str) -> str:
    lowered = path.lower()
    if "viewcontroller" in lowered or "/controller/" in lowered:
        return "feature_screen"
    if "viewmodel" in lowered or "presenter" in lowered or "interactor" in lowered:
        return "feature_logic"
    if "service" in lowered or "repository" in lowered or "api" in lowered or "client" in lowered:
        return "feature_service"
    if "model" in lowered or "/model/" in lowered or "/models/" in lowered:
        return "feature_model"
    if "/view/" in lowered or "/views/" in lowered:
        return "feature_view"
    return "other"


def _risk_for_path(path: str) -> tuple[str, bool]:
    lowered = path.lower()
    if any(token in lowered for token in GLOBAL_RISK_TOKENS):
        return "high", False
    if "/debug/" in lowered:
        return "medium", False
    return "low", True


def _confidence_value(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    label = str(value or "").strip().lower()
    if label == "high":
        return 0.85
    if label == "medium":
        return 0.7
    if label == "low":
        return 0.55
    return 0.72


def touchpoints_from_llm_resolution(
    resolution: dict,
    profile: None = None,
    repo_root: Path = Path("."),
    limit: int = 8,
) -> list[dict]:
    suggested_paths = [str(item) for item in resolution.get("suggested_paths", []) if str(item).strip()]
    reason = str(resolution.get("rationale") or "llm suggested touchpoints")
    confidence = round(_confidence_value(resolution.get("confidence")), 2)

    touchpoints: list[dict] = []
    seen_paths: set[str] = set()
    for raw_path in suggested_paths:
        path = _normalize_rel_path(raw_path, repo_root=repo_root)
        if not path or path in seen_paths:
            continue
        risk, safe_patch = _risk_for_path(path)
        touchpoints.append(
            {
                "path": path,
                "kind": _infer_kind(path),
                "confidence": confidence,
                "risk": risk,
                "safe_patch": safe_patch,
                "reason": reason,
            }
        )
        seen_paths.add(path)
        if len(touchpoints) >= limit:
            return touchpoints
    return touchpoints


def merge_touchpoints(primary: list[dict], extras: list[dict], limit: int = 12) -> list[dict]:
    merged: dict[str, dict] = {}
    ordered_paths: list[str] = []

    def ingest(items: list[dict]) -> None:
        for item in items:
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            confidence = float(item.get("confidence") or 0.0)
            if path not in merged:
                merged[path] = dict(item)
                merged[path]["confidence"] = confidence
                merged[path]["reason"] = str(item.get("reason") or "")
                merged[path]["safe_patch"] = bool(item.get("safe_patch", True))
                ordered_paths.append(path)
                continue
            existing = merged[path]
            if confidence > float(existing.get("confidence") or 0.0):
                existing["confidence"] = confidence
                existing["kind"] = item.get("kind", existing.get("kind", "other"))
            existing["safe_patch"] = bool(existing.get("safe_patch", True)) and bool(item.get("safe_patch", True))
            if existing.get("risk") != "high" and item.get("risk") == "high":
                existing["risk"] = "high"
            elif existing.get("risk") == "low" and item.get("risk") == "medium":
                existing["risk"] = "medium"
            reason = str(item.get("reason") or "")
            if reason and reason not in str(existing.get("reason") or ""):
                if existing.get("reason"):
                    existing["reason"] = f"{existing['reason']} | {reason}"
                else:
                    existing["reason"] = reason

    ingest(primary)
    ingest(extras)

    ranked = sorted(
        (merged[path] for path in ordered_paths if path in merged),
        key=lambda item: (-float(item.get("confidence") or 0.0), str(item.get("path") or "")),
    )
    return ranked[:limit]
