#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


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


@dataclass
class FeatureRecord:
    feature_id: str
    name: str
    description: str
    aliases: list[str]


@dataclass
class HostMappingRecord:
    feature_id: str
    page_hosts: list[str]
    action_hosts: list[str]
    state_hosts: list[str]
    data_hosts: list[str]
    side_effect_hosts: list[str]
    code_entities: list[str]


@dataclass
class ProfileV2:
    features: dict[str, FeatureRecord]
    host_mappings: dict[str, HostMappingRecord]


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


def _load_json_list(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def load_profile_v2(profile_v2_dir: Path) -> ProfileV2:
    feature_path = profile_v2_dir / "feature_registry.json"
    host_path = profile_v2_dir / "host_mapping.json"
    if not feature_path.exists():
        raise FileNotFoundError(f"profile v2 missing file: {feature_path}")
    if not host_path.exists():
        raise FileNotFoundError(f"profile v2 missing file: {host_path}")

    features: dict[str, FeatureRecord] = {}
    for item in _load_json_list(feature_path):
        feature_id = str(item.get("feature_id") or "").strip()
        if not feature_id:
            continue
        features[feature_id] = FeatureRecord(
            feature_id=feature_id,
            name=str(item.get("name") or feature_id),
            description=str(item.get("description") or ""),
            aliases=[str(alias) for alias in item.get("aliases", []) if str(alias).strip()],
        )

    host_mappings: dict[str, HostMappingRecord] = {}
    for item in _load_json_list(host_path):
        feature_id = str(item.get("feature_id") or "").strip()
        if not feature_id:
            continue
        host_mappings[feature_id] = HostMappingRecord(
            feature_id=feature_id,
            page_hosts=[str(value) for value in item.get("page_hosts", []) if str(value).strip()],
            action_hosts=[str(value) for value in item.get("action_hosts", []) if str(value).strip()],
            state_hosts=[str(value) for value in item.get("state_hosts", []) if str(value).strip()],
            data_hosts=[str(value) for value in item.get("data_hosts", []) if str(value).strip()],
            side_effect_hosts=[str(value) for value in item.get("side_effect_hosts", []) if str(value).strip()],
            code_entities=[str(value) for value in item.get("code_entities", []) if str(value).strip()],
        )
    return ProfileV2(features=features, host_mappings=host_mappings)


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


def _feature_score(feature: FeatureRecord, keyword_tokens: set[str], evidence_tokens: set[str]) -> float:
    feature_tokens = _tokenize(f"{feature.feature_id} {feature.name} {feature.description} {' '.join(feature.aliases)}")
    keyword_hit = len(feature_tokens.intersection(keyword_tokens))
    evidence_hit = len(feature_tokens.intersection(evidence_tokens))
    if keyword_hit == 0 and evidence_hit == 0:
        return 0.0
    return keyword_hit * 1.0 + evidence_hit * 0.5


def _collect_evidence_tokens(evidence: dict) -> set[str]:
    flutter = evidence.get("flutter", {}) if isinstance(evidence, dict) else {}
    screens = flutter.get("screens", [])
    interactions = flutter.get("interactions", [])
    states = flutter.get("states", [])
    tokens: set[str] = set()
    for item in screens + interactions + states:
        if isinstance(item, dict):
            tokens.update(_tokenize(str(item.get("name") or "")))
        else:
            tokens.update(_tokenize(str(item)))
    return tokens


def select_touchpoints_from_profile(
    profile: ProfileV2,
    keyword_bundle: dict,
    evidence: dict,
    limit: int = 8,
) -> list[dict]:
    keyword_tokens = set()
    for key in ("ordered", "base", "aliases"):
        for token in keyword_bundle.get(key, []):
            keyword_tokens.update(_tokenize(str(token)))
    evidence_tokens = _collect_evidence_tokens(evidence)

    scored_features: list[tuple[float, FeatureRecord]] = []
    for feature in profile.features.values():
        score = _feature_score(feature, keyword_tokens, evidence_tokens)
        if score <= 0:
            continue
        scored_features.append((score, feature))
    scored_features.sort(key=lambda item: (-item[0], item[1].feature_id))

    touchpoints: list[dict] = []
    seen_paths: set[str] = set()
    for rank, (score, feature) in enumerate(scored_features, start=1):
        mapping = profile.host_mappings.get(feature.feature_id)
        if not mapping:
            continue
        confidence = max(0.55, min(0.94, 0.82 - 0.03 * (rank - 1) + min(score, 3.0) * 0.02))
        for raw_path in mapping.code_entities:
            path = _normalize_rel_path(raw_path)
            if not path or path in seen_paths:
                continue
            risk, safe_patch = _risk_for_path(path)
            touchpoints.append(
                {
                    "path": path,
                    "kind": _infer_kind(path),
                    "confidence": round(confidence, 2),
                    "risk": risk,
                    "safe_patch": safe_patch,
                    "reason": f"profile_v2 feature `{feature.feature_id}` matched scope keywords",
                }
            )
            seen_paths.add(path)
            if len(touchpoints) >= limit:
                return touchpoints
    return touchpoints


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
    profile: ProfileV2 | None,
    repo_root: Path,
    limit: int = 8,
) -> list[dict]:
    suggested_paths = [str(item) for item in resolution.get("suggested_paths", []) if str(item).strip()]
    suggested_features = [str(item) for item in resolution.get("suggested_feature_ids", []) if str(item).strip()]
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

    if profile:
        for feature_id in suggested_features:
            mapping = profile.host_mappings.get(feature_id)
            if not mapping:
                continue
            for raw_path in mapping.code_entities:
                path = _normalize_rel_path(raw_path, repo_root=repo_root)
                if not path or path in seen_paths:
                    continue
                risk, safe_patch = _risk_for_path(path)
                touchpoints.append(
                    {
                        "path": path,
                        "kind": _infer_kind(path),
                        "confidence": max(0.55, round(confidence - 0.05, 2)),
                        "risk": risk,
                        "safe_patch": safe_patch,
                        "reason": f"{reason} (feature {feature_id})",
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
