#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from collections import Counter

from atlas_intent_bridge import (
    ProfileV2,
    load_profile_v2,
    merge_touchpoints,
    select_touchpoints_from_profile,
    touchpoints_from_llm_resolution,
)


FEATURE_INTENT_FILE = "feature_intent_spec.yaml"
NATIVE_OPERATION_FILE = "native_operation_plan.yaml"

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "using",
    "that",
    "this",
    "will",
    "have",
    "your",
    "you",
    "page",
    "pages",
    "feature",
    "screen",
    "view",
    "views",
    "controller",
    "controllers",
    "presenter",
    "presenters",
    "viewmodel",
    "model",
    "models",
    "swift",
    "uikit",
    "ios",
    "flutter",
    "native",
    "tests",
    "test",
    "readme",
    "requirement",
    "sync",
    "app",
    "novelspa",
    "novelago",
    "users",
    "admin",
    "features",
    "feature",
    "lib",
    "api",
    "text",
    "tab",
    "action",
    "selector",
    "result",
    "results",
    "loading",
    "load",
    "dart",
    "evidence",
    "present",
    "include",
    "interaction",
    "services",
    "service",
    "language",
    "l10n",
    "arb",
    "components",
    "component",
    "import",
    "async",
    "math",
    "serif",
    "info",
    "mode",
    "child",
    "slide",
}

GENERIC_PRD_PATTERNS = (
    "docs.gitlab.com",
    "to make it easy for you to get started",
    "recommended next steps",
    "create a file",
    "set up project integrations",
    "invite team members",
    "create a new merge request",
)

GLOBAL_RISK_TOKENS = (
    "appdelegate",
    "scenedelegate",
    "scene",
    "navigator",
    "route",
    "routing",
    "router",
    "tabbar",
    "tabcontroller",
    "coordinator",
    "deeplink",
    "dependency",
    "assembly",
    "bootstrap",
    "pushnav",
    "openscreenmanager",
)

REGISTRATION_HINT_TOKENS = (
    "route",
    "router",
    "routing",
    "deeplink",
    "deep_link",
    "tab",
    "tabbar",
    "coordinator",
    "navigator",
    "login",
    "onboarding",
    "launch",
    "entry",
    "register",
)

STATE_KIND_PATTERNS = {
    "loading": ("loading", "initialloading", "isloading"),
    "success": ("loaded", "success", "ready", "completed"),
    "error": ("error", "failed", "failure", "exception"),
    "empty": ("empty", "nodata", "blank"),
    "retry": ("retry", "reload"),
    "partial": ("partial",),
}

STATE_HOLDER_SUFFIXES = ("Bloc", "Cubit", "Notifier", "Provider", "ViewModel")
MODEL_SUFFIXES = ("Model", "Entity", "Dto", "Request", "Response")
API_SUFFIXES = ("Api", "Repository", "Service", "Client", "Datasource")
INTERACTION_VERBS = (
    "load",
    "fetch",
    "refresh",
    "retry",
    "select",
    "open",
    "close",
    "apply",
    "submit",
    "toggle",
    "change",
    "search",
    "tap",
    "press",
)

KEYWORD_ALIASES = {
    "membership": ["vip", "subscribe", "subscription", "buy"],
    "reader": ["player", "read"],
    "unlock": ["buy", "purchase"],
    "short": ["player", "episode"],
    "alert": ["buy", "popup"],
}

PLAYER_CONTEXT_HINTS = (
    "/reader/",
    "/player/",
    "reader_",
    "player_",
    "short_reader",
    "/audio/buy/",
)
MEMBERSHIP_CONTEXT_TOKENS = ("membership", "vip", "subscribe", "subscription")
WALLET_CONTEXT_TOKENS = ("wallet", "purchased", "purchasehistory", "purchase_history")

PRIORITY_NATIVE_PATH_TOKENS = ("vip", "subscribe", "subscription", "buy", "unlock", "purchase")
UI_TOUCHPOINT_KINDS = {"feature_screen", "feature_view"}
DATA_LAYER_TOUCHPOINT_KINDS = {"feature_logic", "feature_service", "feature_model"}
DIALOG_PATH_TOKENS = ("alert", "dialog", "sheet", "popup", "modal", "buybutton", "purchasebutton", "unlockbutton")
OVERLAY_PATH_TOKENS = ("overlay", "floating", "mask", "autolock", "lock")
COMPONENT_PATH_TOKENS = ("button", "cell", "item", "tag", "badge", "header", "footer", "label")
UI_ROLE_ORDER = {
    "primary_screen": 0,
    "auxiliary_dialog": 1,
    "auxiliary_overlay": 2,
    "component_view": 3,
    "non_ui": 4,
    "registration_point": 5,
}
ANCHOR_PATH_STOPWORDS = {
    "swift",
    "classes",
    "pages",
    "views",
    "view",
    "controller",
    "controllers",
    "models",
    "model",
    "kit",
    "other",
}


@dataclass
class PlanningInputs:
    repo_root: Path
    profile_v2_dir: Path
    run_dir: Path
    prd_path: Path | None
    flutter_root: Path | None
    flutter_path: Path | None
    flutter_digest_path: Path | None
    pr_diff_path: Path | None
    tests_path: Path | None
    llm_resolution_path: Path | None
    requirement_id: str
    requirement_name: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Planner for Flutter-to-iOS sync planning")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Generate planning artifacts for a requirement sync run")
    plan.add_argument("--repo-root", required=True, help="Path to the target iOS repository")
    plan.add_argument("--profile-v2-dir", required=True, help="Path to repo-profile-core outputs (feature_registry.json + host_mapping.json)")
    plan.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")
    plan.add_argument("--prd-path", help="Optional path to PRD or requirement document")
    plan.add_argument("--flutter-root", help="Optional Flutter repository root")
    plan.add_argument("--flutter-path", help="Optional Flutter feature path")
    plan.add_argument("--flutter-digest-path", help="Optional path to flutter-feature-digest.json")
    plan.add_argument("--pr-diff-path", help="Optional Flutter diff artifact")
    plan.add_argument("--tests-path", help="Optional tests path")
    plan.add_argument("--llm-resolution-path", help="Optional path to llm intent resolution JSON")
    plan.add_argument("--requirement-id", required=True, help="Requirement identifier")
    plan.add_argument("--requirement-name", required=True, help="Requirement name slug")
    plan.add_argument("--force", action="store_true", help="Overwrite existing run artifacts")

    status = subparsers.add_parser("status", help="Report the state of a run directory")
    status.add_argument("--run-dir", required=True, help="Path to .ai/t2n/runs/<run-id>")

    return parser


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_repo_root(repo_root: Path) -> None:
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"repo root not found or unreadable: {repo_root}")


def ensure_profile_v2_dir(profile_v2_dir: Path) -> None:
    if not profile_v2_dir.exists() or not profile_v2_dir.is_dir():
        raise FileNotFoundError(f"profile v2 dir not found or unreadable: {profile_v2_dir}")
    required = ["feature_registry.json", "host_mapping.json"]
    missing = [name for name in required if not (profile_v2_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"profile v2 dir missing required files: {', '.join(missing)}")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_safe(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def load_flutter_digest(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def digest_field(digest: dict, key: str, fallback, item_key: str | None = None):
    if key not in digest:
        return fallback
    value = digest.get(key)
    if item_key and isinstance(value, list):
        return [item[item_key] if isinstance(item, dict) else item for item in value]
    return value


def gather_path_files(path: Path | None, limit: int = 20) -> list[str]:
    if path is None:
        return []
    if path.is_file():
        return [str(path)]
    files = sorted(p for p in path.rglob("*") if p.is_file())
    return [str(item) for item in files[:limit]]


def collect_lines(path: Path | None, max_lines: int = 20) -> list[str]:
    text = read_text_safe(path)
    if not text:
        return []
    return [line.strip() for line in text.splitlines()[:max_lines] if line.strip()]


def parse_prd_evidence(path: Path | None) -> dict:
    text = read_text_safe(path)
    if not text:
        return {
            "title": None,
            "summary": None,
            "acceptance_points": [],
            "user_flows": [],
            "raw_lines": [],
        }
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not any(pattern in line.lower() for pattern in GENERIC_PRD_PATTERNS)
    ]
    title = None
    summary = None
    acceptance_points: list[str] = []
    user_flows: list[str] = []
    current_section = ""
    for line in lines:
        normalized = line.lstrip("-*").strip()
        lowered = normalized.lower()
        if title is None and line.startswith("#"):
            title = line.lstrip("#").strip()
            continue
        if line.startswith("#"):
            current_section = normalized.lower()
            continue
        if summary is None and not line.startswith("#") and not line.startswith(("-", "*")):
            summary = normalized
            continue
        if any(token in lowered for token in ("accept", "验收", "expected", "结果")) or "验收" in current_section:
            acceptance_points.append(normalized)
        elif any(token in lowered for token in ("flow", "流程", "点击", "打开", "进入", "step")) or "流程" in current_section:
            user_flows.append(normalized)
        elif line.startswith(("-", "*")) and len(acceptance_points) < 5:
            acceptance_points.append(normalized)
    if not title and lines:
        title = lines[0][:80]
    if not summary:
        summary = title or "No summary found"
    return {
        "title": title,
        "summary": summary,
        "acceptance_points": acceptance_points[:5],
        "user_flows": user_flows[:5],
        "raw_lines": lines[:20],
    }


def parse_diff_evidence(path: Path | None) -> dict:
    text = read_text_safe(path)
    if not text:
        return {"files": [], "summary_lines": []}
    files: list[str] = []
    summary_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("+++ b/"):
            files.append(stripped[6:])
        elif stripped.startswith("+") and not stripped.startswith("+++"):
            content = stripped[1:].strip()
            if content and len(summary_lines) < 8:
                summary_lines.append(content[:160])
    return {"files": files[:20], "summary_lines": summary_lines}


def infer_user_flows_from_names(names: list[str]) -> list[str]:
    flows: list[str] = []
    for name in names:
        stem = Path(name).stem
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
        if normalized:
            flows.append(normalized)
    return flows[:5]


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def gather_flutter_feature_files(inputs: PlanningInputs, limit: int = 40) -> list[Path]:
    if inputs.flutter_path is None:
        return []
    if inputs.flutter_path.is_file():
        return [inputs.flutter_path]
    preferred_suffixes = {".dart", ".yaml", ".yml", ".json"}
    files = sorted(
        path
        for path in inputs.flutter_path.rglob("*")
        if path.is_file() and (path.suffix in preferred_suffixes or not path.suffix)
    )
    return files[:limit]


def sanitize_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def normalize_digest_screen_role(name: str, path: str, role: str | None) -> str:
    lowered = f"{name} {path}".lower()
    raw_role = role or "primary_screen"
    if raw_role == "primary_screen":
        return "primary_screen"
    if any(token in lowered for token in DIALOG_PATH_TOKENS):
        return "auxiliary_dialog"
    if any(token in lowered for token in OVERLAY_PATH_TOKENS):
        return "auxiliary_overlay"
    if raw_role == "auxiliary_screen":
        return "auxiliary_dialog"
    return raw_role


def normalize_representative_screens(digest: dict) -> list[dict]:
    items: list[dict] = []
    for item in digest.get("representative_screens", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        path = item.get("path", "")
        items.append(
            {
                "name": name,
                "path": path,
                "role": normalize_digest_screen_role(name, path, item.get("role")),
                "confidence": item.get("confidence"),
            }
        )
    return items


def group_representative_screens(screen_items: list[dict]) -> dict[str, list[dict]]:
    grouped = {
        "primary_screen": [],
        "auxiliary_dialog": [],
        "auxiliary_overlay": [],
        "component_view": [],
    }
    for item in screen_items:
        role = item.get("role", "primary_screen")
        if role not in grouped:
            role = "component_view"
        grouped[role].append(item)
    return grouped


def confidence_label(score: float | None) -> str:
    value = score or 0.0
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    return "low"


def is_global_review_path(path: str) -> bool:
    lowered = path.lower()
    return any(token in lowered for token in GLOBAL_RISK_TOKENS)


def classify_registration_kind(path: str) -> str:
    lowered = path.lower()
    if any(token in lowered for token in ("route", "router", "navigator", "coordinator", "tabbar")):
        return "global_router"
    if any(token in lowered for token in ("theme", "style", "appearance")):
        return "theme_root"
    if any(token in lowered for token in ("assembly", "dependency", "container", "factory")):
        return "dependency_root"
    return "registration_point"


def classify_state_kind(token: str) -> str | None:
    lowered = token.lower().replace("_", "").replace("-", "")
    for kind, patterns in STATE_KIND_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            return kind
    return None


def infer_state_entries(text: str) -> list[dict]:
    candidates: list[dict] = []
    enum_matches = re.findall(r"\b(?:enum|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text)
    state_tokens = re.findall(r"\b(?:is|state\.|state = |return )([A-Za-z_][A-Za-z0-9_]*)", text)
    for token in enum_matches + state_tokens:
        kind = classify_state_kind(token)
        if kind:
            candidates.append({"name": token, "kind": kind})
    for kind, patterns in STATE_KIND_PATTERNS.items():
        normalized_text = text.lower().replace("_", "").replace("-", "")
        if any(pattern in normalized_text for pattern in patterns):
            candidates.append({"name": kind, "kind": kind})

    result: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        key = (item["name"], item["kind"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result[:6]


def extract_class_names(text: str) -> list[tuple[str, str | None]]:
    matches = re.findall(
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:extends\s+([A-Za-z_][A-Za-z0-9_<>]*))?",
        text,
    )
    return [(name, base if base else None) for name, base in matches]


def extract_interactions(text: str) -> list[str]:
    candidates: list[str] = []
    handler_pairs = re.findall(
        r"\b(onTap|onPressed|onChanged|onRefresh|onSubmitted|onLongPress)\s*:\s*(?:\(\)\s*=>\s*)?([A-Za-z_][A-Za-z0-9_\.]*)?",
        text,
    )
    for event_name, handler in handler_pairs:
        if handler:
            normalized = sanitize_slug(handler.split(".")[-1])
            if normalized.startswith(("is", "has", "should", "null")):
                continue
            candidates.append(normalized)
        else:
            candidates.append(sanitize_slug(event_name))

    method_names = re.findall(
        r"\b(?:void|Future<void>|Future)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        text,
    )
    for name in method_names:
        lowered = name.lower()
        if any(lowered.startswith(prefix) for prefix in INTERACTION_VERBS):
            candidates.append(sanitize_slug(name))
    return unique_preserve(candidates)[:8]


def extract_string_literals(text: str) -> list[str]:
    literals = re.findall(r'["\']([^"\']{2,80})["\']', text)
    result: list[str] = []
    for item in literals:
        stripped = item.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if "/" in stripped or "\\" in stripped or lowered.startswith(("http", "assets/", "lib/")):
            continue
        if lowered.startswith(("dart:", "package:")):
            continue
        if "import" in lowered:
            continue
        if lowered.endswith((".dart", ".png", ".jpg", ".jpeg", ".svg", ".json")):
            continue
        if len(stripped) > 48:
            continue
        if not re.search(r"[A-Za-z]", stripped):
            continue
        if stripped.startswith("novelago://"):
            continue
        result.append(stripped)
    return unique_preserve(result)[:8]


def extract_asset_paths(text: str) -> list[str]:
    assets = re.findall(r'["\']((?:assets|images|icons|svg|lottie)/[^"\']+)["\']', text)
    return unique_preserve(assets)[:8]


def extract_api_signals(text: str) -> list[str]:
    api_names: list[str] = []
    method_calls = re.findall(r"\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]", text)
    for method, path in method_calls:
        api_names.append(f"{method.upper()} {path}")
    function_calls = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
    for name in function_calls:
        lowered = name.lower()
        if classify_state_kind(name):
            continue
        if lowered.startswith(("fetch", "query", "request")) or re.match(r"get[A-Z_].*", name):
            api_names.append(name)
    return unique_preserve(api_names)[:8]


def extract_flutter_semantics(inputs: PlanningInputs) -> dict:
    files = gather_flutter_feature_files(inputs)
    screens: list[str] = []
    state_holders: list[str] = []
    api_calls: list[str] = []
    models: list[str] = []
    interactions: list[str] = []
    strings: list[str] = []
    assets: list[str] = []
    states: list[dict] = []
    key_files: list[str] = []

    for path in files:
        rel = str(path)
        key_files.append(rel)
        lowered = rel.lower()
        text = read_text_safe(path)
        is_api_file = any(token in lowered for token in ("/api/", "api.dart", "repository.dart", "service.dart"))
        is_model_file = any(token in lowered for token in ("/model/", "/models/", "_model.dart", "model.dart"))
        class_pairs = extract_class_names(text)
        for name, base in class_pairs:
            base_name = base or ""
            if name.endswith(("Page", "Screen")) or base_name in {"StatelessWidget", "StatefulWidget", "ConsumerWidget"}:
                screens.append(name)
            if name.endswith(STATE_HOLDER_SUFFIXES) or (base_name and any(token in base_name for token in ("Cubit", "Bloc", "Notifier", "ChangeNotifier"))):
                state_holders.append(name)
            if name.endswith(MODEL_SUFFIXES) or "/model/" in lowered or "/models/" in lowered:
                models.append(name)
            if name.endswith(API_SUFFIXES) or "/api/" in lowered or "/repository/" in lowered or "/service/" in lowered:
                api_calls.append(name)

        if path.suffix == ".dart":
            if is_api_file:
                api_calls.extend(extract_api_signals(text))
            if not is_api_file and not is_model_file:
                interactions.extend(extract_interactions(text))
                strings.extend(extract_string_literals(text))
                assets.extend(extract_asset_paths(text))
            if not is_model_file:
                states.extend(infer_state_entries(text))

    deduped_states: list[dict] = []
    seen_states: set[tuple[str, str]] = set()
    for item in states:
        key = (item["name"], item["kind"])
        if key in seen_states:
            continue
        seen_states.add(key)
        deduped_states.append(item)

    return {
        "screens": unique_preserve(screens)[:8],
        "state_holders": unique_preserve(state_holders)[:8],
        "api_calls": unique_preserve(api_calls)[:8],
        "models": unique_preserve(models)[:8],
        "interactions": unique_preserve(interactions)[:8],
        "strings": unique_preserve(strings)[:8],
        "assets": unique_preserve(assets)[:8],
        "states": deduped_states[:8],
        "key_files": key_files[:12],
    }


def build_semantic_user_flows(semantics: dict, requirement_name: str) -> list[str]:
    flows: list[str] = []
    for screen in semantics.get("screens", [])[:2]:
        flows.append(f"open_{sanitize_slug(screen)}")
    flows.extend(semantics.get("interactions", [])[:4])
    if not flows:
        flows.append(f"deliver_{requirement_name}")
    return unique_preserve(flows)[:5]


def build_semantic_acceptance_points(semantics: dict) -> list[str]:
    points: list[str] = []
    for screen in semantics.get("screens", [])[:2]:
        points.append(f"Flutter evidence includes screen `{screen}`.")
    for interaction in semantics.get("interactions", [])[:3]:
        points.append(f"Interaction `{interaction}` is present in Flutter evidence.")
    for state in semantics.get("states", [])[:3]:
        points.append(f"State `{state['name']}` is modeled as `{state['kind']}`.")
    for api_name in semantics.get("api_calls", [])[:2]:
        points.append(f"API `{api_name}` is referenced by the Flutter feature.")
    return unique_preserve(points)[:5]


def tokenize_text(text: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    raw_tokens = re.split(r"[^a-zA-Z0-9]+", spaced.lower())
    return [
        token
        for token in raw_tokens
        if len(token) >= 3 and token not in STOPWORDS and not token.isdigit()
    ]


def build_scope_context(inputs: PlanningInputs, evidence: dict, base_keywords: list[str]) -> dict:
    digest_scope = evidence.get("flutter_digest", {}).get("scope", {})
    primary_features = digest_scope.get("primary_features", [])
    supporting_features = digest_scope.get("supporting_features", [])

    primary_text_parts: list[str] = []
    all_text_parts: list[str] = []

    if inputs.flutter_path:
        primary_text_parts.append(inputs.flutter_path.as_posix().lower())
    primary_text_parts.extend(item.lower() for item in primary_features)

    flutter_paths = evidence.get("flutter", {}).get("paths", [])
    all_text_parts.extend(path.lower() for path in flutter_paths if path)
    all_text_parts.extend(path.lower() for path in evidence.get("flutter", {}).get("key_files", [])[:12])
    all_text_parts.extend(path.lower() for path in evidence.get("diff", {}).get("files", [])[:12])
    all_text_parts.extend(item.lower() for item in supporting_features)
    all_text_parts.extend(primary_text_parts)

    primary_blob = " ".join(primary_text_parts)
    all_blob = " ".join(all_text_parts)
    keyword_set = set(base_keywords)

    membership_context = bool(keyword_set.intersection(MEMBERSHIP_CONTEXT_TOKENS)) or any(
        token in all_blob for token in MEMBERSHIP_CONTEXT_TOKENS
    )
    player_context = any(token in primary_blob for token in PLAYER_CONTEXT_HINTS) or bool(
        keyword_set.intersection({"reader", "player"})
    )
    chapter_list_context = "chapter" in keyword_set and bool(keyword_set.intersection({"list", "detail", "chapters"}))
    wallet_context = bool(keyword_set.intersection(WALLET_CONTEXT_TOKENS)) or any(
        token in all_blob for token in WALLET_CONTEXT_TOKENS
    )
    commerce_context = membership_context or bool(
        keyword_set.intersection({"buy", "purchase", "purchased", "unlock"})
    )
    return {
        "membership_context": membership_context,
        "player_context": player_context,
        "chapter_list_context": chapter_list_context,
        "wallet_context": wallet_context,
        "commerce_context": commerce_context,
        "primary_features": primary_features,
        "supporting_features": supporting_features,
    }


def aliases_for_keyword(token: str, context: dict) -> list[str]:
    aliases = KEYWORD_ALIASES.get(token, [])
    if not aliases:
        return []
    if token == "reader":
        return aliases if context.get("player_context") else []
    if token == "short":
        return aliases if context.get("player_context") else []
    if token == "unlock":
        if context.get("membership_context") or context.get("player_context"):
            return aliases
        if context.get("commerce_context") and not context.get("chapter_list_context"):
            return aliases
        return []
    if token == "alert":
        return aliases if context.get("commerce_context") else []
    return aliases


def build_scope_keywords(inputs: PlanningInputs, evidence: dict, scope: dict, limit: int = 10) -> dict:
    counter: Counter[str] = Counter()
    text_sources = [
        inputs.requirement_name,
        scope["display_name"],
        scope["summary"],
        *scope["acceptance_points"],
        *scope["user_flows"],
        *evidence["flutter"]["screens"],
        *evidence["flutter"]["state_holders"],
        *evidence["flutter"]["api_calls"],
        *evidence["flutter"]["models"],
        *evidence["flutter"]["interactions"],
    ]
    for item in text_sources:
        counter.update(tokenize_text(item))

    path_sources: list[str] = []
    if inputs.flutter_path:
        path_sources.append(inputs.flutter_path.name)
        path_sources.extend(part for part in inputs.flutter_path.parts if part not in ("/", ""))
    for path in evidence["flutter"]["key_files"][:12]:
        path_sources.append(Path(path).stem)
        path_sources.extend(Path(path).parts[-4:])
    for path in evidence["diff"]["files"][:12]:
        path_sources.append(Path(path).stem)
        path_sources.extend(Path(path).parts[-4:])
    for item in path_sources:
        counter.update(tokenize_text(item))

    keywords = [token for token, _ in counter.most_common(limit)]
    requirement_tokens = [token for token in tokenize_text(inputs.requirement_name) if token not in STOPWORDS]
    base_keywords = unique_preserve(requirement_tokens + keywords)
    context = build_scope_context(inputs, evidence, base_keywords)
    requirement_tokens_set = set(tokenize_text(inputs.requirement_name))
    flutter_name_tokens = set(tokenize_text(inputs.flutter_path.name if inputs.flutter_path else ""))
    if (
        "short" in base_keywords
        and not context.get("player_context")
        and "short" not in requirement_tokens_set
        and "short" not in flutter_name_tokens
    ):
        base_keywords = [token for token in base_keywords if token != "short"]
        context = build_scope_context(inputs, evidence, base_keywords)
    expanded_keywords: list[str] = []
    alias_keywords: list[str] = []
    for token in base_keywords:
        if token in STOPWORDS:
            continue
        if token not in expanded_keywords:
            expanded_keywords.append(token)
        for alias in aliases_for_keyword(token, context):
            if alias not in expanded_keywords and alias not in STOPWORDS:
                expanded_keywords.append(alias)
            if alias not in alias_keywords and alias not in STOPWORDS:
                alias_keywords.append(alias)
    if inputs.flutter_path:
        flutter_name = inputs.flutter_path.name.lower()
        if flutter_name not in expanded_keywords and flutter_name not in STOPWORDS:
            expanded_keywords.insert(0, flutter_name)
        if flutter_name not in base_keywords and flutter_name not in STOPWORDS:
            base_keywords.insert(0, flutter_name)
    return {
        "ordered": expanded_keywords[: max(limit, 18)],
        "base": unique_preserve(base_keywords),
        "aliases": unique_preserve(alias_keywords),
        "context": context,
    }


def build_evidence(inputs: PlanningInputs) -> dict:
    flutter_semantics = extract_flutter_semantics(inputs)
    flutter_digest = load_flutter_digest(inputs.flutter_digest_path)
    representative_screens = normalize_representative_screens(flutter_digest)
    digest_screens = [item for item in digest_field(flutter_digest, "representative_screens", [], item_key="name") if item]
    digest_api_calls = [item for item in digest_field(flutter_digest, "api_calls", [], item_key="name") if item]
    digest_models = [item for item in digest_field(flutter_digest, "models", [], item_key="name") if item]
    digest_assets = [item for item in digest_field(flutter_digest, "assets", [], item_key="path") if item]
    digest_feature_paths = flutter_digest.get("source", {}).get("feature_paths") or ([str(inputs.flutter_path)] if inputs.flutter_path else [])
    return {
        "prd": parse_prd_evidence(inputs.prd_path),
        "flutter_digest": flutter_digest,
        "flutter": {
            "paths": digest_feature_paths,
            "key_files": flutter_digest.get("evidence_files") or flutter_semantics["key_files"] or gather_flutter_key_files(inputs),
            "representative_screens": representative_screens,
            "screens": digest_screens if "representative_screens" in flutter_digest else flutter_semantics["screens"],
            "state_holders": digest_field(flutter_digest, "state_holders", flutter_semantics["state_holders"]),
            "api_calls": digest_api_calls if "api_calls" in flutter_digest else flutter_semantics["api_calls"],
            "models": digest_models if "models" in flutter_digest else flutter_semantics["models"],
            "interactions": digest_field(flutter_digest, "interactions", flutter_semantics["interactions"]),
            "strings": digest_field(flutter_digest, "strings", flutter_semantics["strings"]),
            "assets": digest_assets if "assets" in flutter_digest else flutter_semantics["assets"],
            "states": digest_field(flutter_digest, "states", flutter_semantics["states"]),
        },
        "diff": parse_diff_evidence(inputs.pr_diff_path),
        "tests": gather_path_files(inputs.tests_path, limit=20),
    }


def infer_requirement_scope(inputs: PlanningInputs, evidence: dict) -> dict:
    prd = evidence["prd"]
    flutter = evidence["flutter"]
    flutter_digest = evidence.get("flutter_digest", {})
    title = prd["title"] or inputs.requirement_name
    summary = prd["summary"] or f"Sync {inputs.requirement_name} from Flutter into iOS"
    semantic_acceptance = build_semantic_acceptance_points(flutter)
    acceptance_points = unique_preserve(semantic_acceptance + prd["acceptance_points"][:] + prd["raw_lines"][:3])
    if not acceptance_points:
        acceptance_points = [f"Review {inputs.requirement_name} behavior against Flutter evidence"]
    semantic_flows = flutter_digest.get("user_flows") or build_semantic_user_flows(flutter, inputs.requirement_name)
    user_flows = unique_preserve(semantic_flows + prd["user_flows"][:])
    if not user_flows and evidence["tests"]:
        user_flows = infer_user_flows_from_names(evidence["tests"])
    if not user_flows and evidence["flutter"]["key_files"]:
        user_flows = infer_user_flows_from_names(evidence["flutter"]["key_files"])
    if not user_flows:
        user_flows = [f"deliver_{inputs.requirement_name}"]
    has_rich_flutter = any(
        [
            flutter["screens"],
            flutter["state_holders"],
            flutter["api_calls"],
            flutter["models"],
            flutter["interactions"],
            flutter["states"],
        ]
    )
    digest_confidence = flutter_digest.get("scope", {}).get("confidence")
    confidence = (
        "high"
        if has_rich_flutter and (inputs.pr_diff_path or inputs.tests_path or inputs.flutter_path or inputs.flutter_digest_path or digest_confidence == "high")
        else "medium"
        if inputs.prd_path or inputs.flutter_path or inputs.flutter_digest_path
        else "low"
    )
    return {
        "id": inputs.requirement_id,
        "name": inputs.requirement_name,
        "display_name": title,
        "summary": summary,
        "acceptance_points": acceptance_points[:5],
        "user_flows": user_flows[:5],
        "confidence": confidence,
    }


def build_inputs(args: argparse.Namespace) -> PlanningInputs:
    repo_root = Path(args.repo_root).expanduser().resolve()
    profile_v2_dir = Path(args.profile_v2_dir).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    prd_path = Path(args.prd_path).expanduser().resolve() if args.prd_path else None
    flutter_root = Path(args.flutter_root).expanduser().resolve() if args.flutter_root else None
    flutter_path = Path(args.flutter_path).expanduser().resolve() if args.flutter_path else None
    flutter_digest_path = Path(args.flutter_digest_path).expanduser().resolve() if args.flutter_digest_path else None
    pr_diff_path = Path(args.pr_diff_path).expanduser().resolve() if args.pr_diff_path else None
    tests_path = Path(args.tests_path).expanduser().resolve() if args.tests_path else None
    llm_resolution_path = Path(args.llm_resolution_path).expanduser().resolve() if getattr(args, "llm_resolution_path", None) else None
    return PlanningInputs(
        repo_root=repo_root,
        profile_v2_dir=profile_v2_dir,
        run_dir=run_dir,
        prd_path=prd_path,
        flutter_root=flutter_root,
        flutter_path=flutter_path,
        flutter_digest_path=flutter_digest_path,
        pr_diff_path=pr_diff_path,
        tests_path=tests_path,
        llm_resolution_path=llm_resolution_path,
        requirement_id=args.requirement_id,
        requirement_name=args.requirement_name,
    )


def validate_inputs(inputs: PlanningInputs) -> None:
    ensure_repo_root(inputs.repo_root)
    ensure_profile_v2_dir(inputs.profile_v2_dir)
    if not any([inputs.prd_path, inputs.flutter_path, inputs.flutter_digest_path, inputs.pr_diff_path, inputs.tests_path]):
        raise FileNotFoundError("at least one of --prd-path, --flutter-path, --flutter-digest-path, --pr-diff-path, --tests-path is required")
    if inputs.prd_path and not inputs.prd_path.exists():
        raise FileNotFoundError(f"prd path not found: {inputs.prd_path}")
    if inputs.flutter_root and not inputs.flutter_root.exists():
        raise FileNotFoundError(f"flutter root not found: {inputs.flutter_root}")
    if inputs.flutter_path and not inputs.flutter_path.exists():
        raise FileNotFoundError(f"flutter path not found: {inputs.flutter_path}")
    if inputs.flutter_digest_path and not inputs.flutter_digest_path.exists():
        raise FileNotFoundError(f"flutter digest path not found: {inputs.flutter_digest_path}")
    if inputs.pr_diff_path and not inputs.pr_diff_path.exists():
        raise FileNotFoundError(f"pr diff path not found: {inputs.pr_diff_path}")
    if inputs.tests_path and not inputs.tests_path.exists():
        raise FileNotFoundError(f"tests path not found: {inputs.tests_path}")
    if inputs.llm_resolution_path and not inputs.llm_resolution_path.exists():
        raise FileNotFoundError(f"llm resolution path not found: {inputs.llm_resolution_path}")


def build_change_basis(inputs: PlanningInputs) -> list[str]:
    basis = []
    if inputs.prd_path:
        basis.append("prd")
    if inputs.flutter_digest_path:
        basis.append("flutter_digest")
    if inputs.flutter_path:
        basis.append("flutter_code")
    if inputs.pr_diff_path:
        basis.append("flutter_pr_diff")
    if inputs.tests_path:
        basis.append("flutter_tests")
    return basis


def gather_flutter_key_files(inputs: PlanningInputs, limit: int = 12) -> list[str]:
    if inputs.flutter_path is None:
        return []
    if inputs.flutter_path.is_file():
        return [str(inputs.flutter_path)]
    files = sorted(p for p in inputs.flutter_path.rglob("*") if p.is_file())
    return [str(path) for path in files[:limit]]


def split_key_files(inputs: PlanningInputs, evidence: dict) -> tuple[list[str], list[str]]:
    key_files = evidence["flutter"]["key_files"]
    if not key_files:
        return [], []
    if not inputs.flutter_root or not inputs.flutter_path:
        return key_files[:20], []
    try:
        prefix = inputs.flutter_path.relative_to(inputs.flutter_root).as_posix().rstrip("/")
    except ValueError:
        return key_files[:20], []
    primary = [path for path in key_files if path.startswith(prefix)]
    supporting = [path for path in key_files if not path.startswith(prefix)]
    return primary[:20], supporting[:20]


def infer_native_kind(rel_path: str) -> str:
    lower = rel_path.lower()
    if "viewmodel" in lower or "presenter" in lower:
        return "feature_logic"
    if "viewcontroller" in lower or "/controller/" in lower:
        return "feature_screen"
    if "/api/" in lower or "service" in lower or "manager" in lower:
        return "feature_service"
    if "/model/" in lower or "/models/" in lower or lower.endswith("model.swift"):
        return "feature_model"
    if "/view/" in lower or "/views/" in lower:
        return "feature_view"
    return "other"


def normalize_touchpoint_kind(kind: str | None, path: str) -> str:
    if kind == "feature_flow":
        return "feature_logic"
    if kind and kind != "other":
        return kind
    inferred = infer_native_kind(path)
    return inferred if inferred != "other" else (kind or "other")


def derive_risk(rel_path: str) -> tuple[str, bool]:
    lower = rel_path.lower()
    if any(token in lower for token in GLOBAL_RISK_TOKENS):
        return "high", False
    if "/debug/" in lower:
        return "medium", False
    if "/appdelegate." in lower or lower.endswith("appdelegate.swift"):
        return "high", False
    return "low", True


def matched_keyword_reason(matched_base: list[str], matched_alias: list[str]) -> str:
    if matched_base and matched_alias:
        return f"Matched base keywords: {', '.join(sorted(set(matched_base))[:4])}; alias keywords: {', '.join(sorted(set(matched_alias))[:3])}"
    if matched_base:
        return f"Matched base keywords: {', '.join(sorted(set(matched_base))[:4])}"
    return f"Matched alias keywords: {', '.join(sorted(set(matched_alias))[:4])}"


def contextual_native_score(lower: str, kind: str, matched_base: list[str], matched_alias: list[str], context: dict) -> float:
    score = 0.0
    base_set = set(matched_base)
    alias_set = set(matched_alias)

    if context.get("player_context"):
        if "/player/" in lower or "/reader/" in lower:
            score += 0.28
        if not context.get("wallet_context") and ("/wallet/" in lower or "/usercenter/" in lower):
            score -= 0.18
    else:
        if "/player/" in lower:
            score -= 0.32
        if "/player/" in lower and alias_set.intersection({"player", "episode", "buy"}):
            score -= 0.24
        if "/buy/" in lower and "buy" in alias_set and not base_set.intersection({"buy", "purchase", "membership"}):
            score -= 0.14

    if context.get("chapter_list_context"):
        if "chapter" in lower:
            score += 0.10
        if "chapterlist" in lower or "/chapterlist/" in lower or "unlockchapter" in lower:
            score += 0.16
        if kind == "feature_screen":
            score += 0.06

    if context.get("wallet_context"):
        if "/wallet/" in lower or "unlockchapter" in lower:
            score += 0.18
        if "/usercenter/" in lower or "/me/" in lower:
            score += 0.06

    if context.get("membership_context"):
        if any(token in lower for token in ("membership", "vip", "subscribe", "subscription", "buy", "purchase", "unlock")):
            score += 0.12
    elif "/wallet/" in lower and base_set.intersection({"purchased", "purchase"}):
        score += 0.08

    return score


def locate_native_candidates(repo_root: Path, keyword_bundle: dict, limit: int = 12) -> list[dict]:
    candidates: list[dict] = []
    keywords = keyword_bundle["ordered"]
    base_keywords = set(keyword_bundle.get("base", keywords))
    alias_keywords = set(keyword_bundle.get("aliases", []))
    context = keyword_bundle.get("context", {})
    priority_enabled = any(token in keywords for token in PRIORITY_NATIVE_PATH_TOKENS)
    for path in repo_root.rglob("*.swift"):
        rel_path = path.relative_to(repo_root).as_posix()
        lower = rel_path.lower()
        path_tokens = set(tokenize_text(rel_path))
        basename_tokens = set(tokenize_text(path.stem))
        if lower.startswith("pods/") or lower.startswith("deriveddata/") or any(skip in lower for skip in ("/pods/", "/deriveddata/", ".build/")):
            continue
        matched_base = [keyword for keyword in base_keywords if keyword in path_tokens]
        matched_alias = [keyword for keyword in alias_keywords if keyword in path_tokens and keyword not in matched_base]
        if not matched_base and not matched_alias:
            continue
        score = 0.24 + min(0.42, 0.16 * len(set(matched_base)) + 0.05 * len(set(matched_alias)))
        if any(keyword in basename_tokens for keyword in matched_base):
            score += 0.18
        elif any(keyword in basename_tokens for keyword in matched_alias):
            score += 0.06
        kind = infer_native_kind(rel_path)
        if kind == "feature_screen":
            score += 0.16
        elif kind != "other":
            score += 0.1
        if priority_enabled and any(token in lower for token in PRIORITY_NATIVE_PATH_TOKENS):
            score += 0.12
        if priority_enabled and "discover" in lower:
            score -= 0.12
        score += contextual_native_score(lower, kind, matched_base, matched_alias, context)
        if "/debug/" in lower:
            score -= 0.35
        if score < 0.45:
            continue
        risk, safe_patch = derive_risk(rel_path)
        candidates.append(
            {
                "path": rel_path,
                "kind": kind,
                "confidence": round(min(score, 1.8), 2),
                "risk": risk,
                "safe_patch": safe_patch,
                "reason": matched_keyword_reason(matched_base, matched_alias),
            }
        )
    candidates.sort(
        key=lambda item: (
            0 if item.get("safe_patch") else 1,
            -item.get("confidence", 0),
            item["path"],
        )
    )
    return candidates[:limit]


def path_anchor_tokens(path: str) -> set[str]:
    return {
        token
        for token in tokenize_text(path)
        if token not in STOPWORDS and token not in ANCHOR_PATH_STOPWORDS and len(token) >= 4
    }

def role_to_screen_names(screen_groups: dict[str, list[dict]]) -> dict[str, list[str]]:
    return {
        role: [item["name"] for item in items]
        for role, items in screen_groups.items()
        if items
    }


def score_touchpoint_for_ui_role(path: str, kind: str, ui_role: str) -> int:
    lowered = path.lower()
    basename = Path(path).stem.lower()
    score = 0
    if kind == "feature_screen":
        score += 4 if ui_role == "primary_screen" else 1
    elif kind == "feature_view":
        score += 2
    else:
        return -10

    if ui_role == "primary_screen":
        if "viewcontroller" in lowered or "/controller/" in lowered:
            score += 6
        if basename.endswith("view"):
            score += 4
        if any(token in lowered for token in DIALOG_PATH_TOKENS + OVERLAY_PATH_TOKENS):
            score -= 3
        if any(token in lowered for token in COMPONENT_PATH_TOKENS):
            score -= 3
    elif ui_role == "auxiliary_dialog":
        if any(token in lowered for token in ("alert", "dialog", "sheet", "popup", "modal")):
            score += 6
        if any(token in lowered for token in ("buybutton", "purchasebutton", "unlockbutton", "buyview", "purchaseview", "unlockview")):
            score += 4
        if "button" in lowered:
            score += 2
        if any(token in lowered for token in OVERLAY_PATH_TOKENS):
            score -= 2
    elif ui_role == "auxiliary_overlay":
        if any(token in lowered for token in OVERLAY_PATH_TOKENS):
            score += 6
        if "button" in lowered:
            score += 1
        if any(token in lowered for token in ("alert", "dialog", "sheet", "popup", "modal")):
            score -= 2
    elif ui_role == "component_view":
        if any(token in lowered for token in COMPONENT_PATH_TOKENS):
            score += 5
        if basename.endswith("view"):
            score += 2
    return score


def assign_ui_roles_to_touchpoints(touchpoints: list[dict], representative_screens: list[dict]) -> tuple[dict[str, str], dict[str, list[str]], list[str]]:
    screen_groups = group_representative_screens(representative_screens)
    screen_names_by_role = role_to_screen_names(screen_groups)
    assignments: dict[str, str] = {}
    source_screens: dict[str, list[str]] = {}
    gaps: list[str] = []
    ui_candidates = [item for item in touchpoints if item.get("kind") in UI_TOUCHPOINT_KINDS]
    used_paths: set[str] = set()

    for desired_role in ("primary_screen", "auxiliary_dialog", "auxiliary_overlay"):
        if not screen_names_by_role.get(desired_role):
            continue
        ranked = sorted(
            (
                {
                    "score": score_touchpoint_for_ui_role(item["path"], item.get("kind", "other"), desired_role),
                    "item": item,
                }
                for item in ui_candidates
                if item["path"] not in used_paths
            ),
            key=lambda entry: (entry["score"], entry["item"]["path"]),
        )
        if not ranked:
            gaps.append(f"{desired_role} 没有可用的 UIKit 触点候选。")
            continue
        score = ranked[-1]["score"]
        best_item = ranked[-1]["item"]
        if score < 3:
            gaps.append(f"{desired_role} 没有达到阈值的 UIKit 触点候选。")
            continue
        assignments[best_item["path"]] = desired_role
        source_screens[best_item["path"]] = screen_names_by_role[desired_role][:2]
        used_paths.add(best_item["path"])

    for item in touchpoints:
        path = item["path"]
        kind = item.get("kind", "other")
        if path in assignments:
            continue
        if kind not in UI_TOUCHPOINT_KINDS:
            assignments[path] = "non_ui"
            source_screens[path] = []
            continue
        assignments[path] = "component_view"
        source_screens[path] = screen_names_by_role.get("component_view", [])[:2]

    return assignments, source_screens, gaps


def selected_touchpoint_sort_key(item: dict) -> tuple[int, int, str, str]:
    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    kind_rank = {
        "feature_screen": 0,
        "feature_view": 1,
        "feature_logic": 2,
        "feature_service": 3,
        "feature_model": 4,
        "other": 5,
    }
    return (
        UI_ROLE_ORDER.get(item.get("ui_role", "non_ui"), 9),
        kind_rank.get(item.get("kind", "other"), 9),
        confidence_rank.get(item.get("confidence", "low"), 9),
        item["path"],
    )


def has_explicit_registration_signal(scope: dict, evidence: dict) -> bool:
    corpus = [
        scope["display_name"],
        scope["summary"],
        *scope["acceptance_points"],
        *scope["user_flows"],
        *evidence["diff"]["summary_lines"],
        *evidence["diff"]["files"],
        *evidence["flutter"]["interactions"],
    ]
    tokens: set[str] = set()
    for item in corpus:
        tokens.update(tokenize_text(item))
    return any(token in tokens for token in REGISTRATION_HINT_TOKENS)


def build_manual_review_entries(
    scope: dict,
    evidence: dict,
    touchpoints: list[dict],
    registration_points: list[dict],
) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()

    for item in touchpoints:
        path = item["path"]
        if item.get("safe_patch") and not is_global_review_path(path):
            continue
        reason = item.get("reason", "") or "Touchpoint requires explicit manual review in V1"
        if is_global_review_path(path):
            reason = f"{reason}; path belongs to a global registration or app-wide area"
        entry = {
            "path": path,
            "kind": classify_registration_kind(path) if is_global_review_path(path) else item.get("kind", "other"),
            "confidence": confidence_label(item.get("confidence")),
            "risk": "high" if is_global_review_path(path) else item.get("risk", "medium"),
            "reason": reason,
        }
        if path not in seen:
            entries.append(entry)
            seen.add(path)

    has_screen_evidence = bool(evidence["flutter"]["screens"])
    has_screen_touchpoint = any(
        item.get("kind") in {"feature_screen", "feature_view"} and item.get("safe_patch")
        for item in touchpoints
    )
    needs_registration_review = bool(registration_points) and (
        has_explicit_registration_signal(scope, evidence)
        or (has_screen_evidence and not has_screen_touchpoint)
    )

    if needs_registration_review:
        for item in registration_points[:2]:
            path = item["path"]
            if path in seen:
                continue
            reason = item["reason"]
            if has_screen_evidence and not has_screen_touchpoint:
                reason = (
                    "Flutter evidence includes screen behavior, but planner did not find a stable UIKit "
                    f"screen touchpoint; keep `{path}` under manual registration review"
                )
            elif has_explicit_registration_signal(scope, evidence):
                reason = (
                    f"Requirement scope carries routing/registration signals; `{path}` should stay under "
                    "manual review before apply"
                )
            entries.append(
                {
                    "path": path,
                    "kind": classify_registration_kind(path),
                    "confidence": "medium",
                    "risk": "high",
                    "reason": reason,
                }
            )
            seen.add(path)
    return entries


def compute_native_impact_confidence(touchpoints: list[dict], manual_entries: list[dict]) -> str:
    if not touchpoints:
        return "low"
    safe_touchpoints = [item for item in touchpoints if item.get("safe_patch") and not is_global_review_path(item["path"])]
    high_confidence_safe = [item for item in safe_touchpoints if (item.get("confidence") or 0) >= 0.75]
    if high_confidence_safe and len(manual_entries) <= 1:
        return "high"
    if safe_touchpoints:
        return "medium"
    return "low"


def compute_overall_risk(scope_confidence: str, native_impact_confidence: str, risk_files: list[dict]) -> str:
    high_risk_count = sum(1 for item in risk_files if item.get("risk") == "high")
    if scope_confidence == "low" or native_impact_confidence == "low" or high_risk_count >= 2:
        return "high"
    if scope_confidence == "medium" or native_impact_confidence == "medium" or risk_files:
        return "medium"
    return "low"


def build_contract(inputs: PlanningInputs) -> dict:
    evidence = build_evidence(inputs)
    scope = infer_requirement_scope(inputs, evidence)
    scope_keyword_bundle = build_scope_keywords(inputs, evidence, scope)
    scope_keywords = scope_keyword_bundle["ordered"]
    primary_key_files, supporting_key_files = split_key_files(inputs, evidence)
    digest_scope = evidence.get("flutter_digest", {}).get("scope", {})
    profile_v2: ProfileV2 = load_profile_v2(inputs.profile_v2_dir)

    external_touchpoints: list[dict] = []
    external_touchpoints.extend(
        select_touchpoints_from_profile(
            profile=profile_v2,
            keyword_bundle=scope_keyword_bundle,
            evidence=evidence,
            limit=8,
        )
    )
    if inputs.llm_resolution_path:
        llm_resolution = load_json(inputs.llm_resolution_path)
        if isinstance(llm_resolution, dict):
            external_touchpoints.extend(
                touchpoints_from_llm_resolution(
                    resolution=llm_resolution,
                    profile=profile_v2,
                    repo_root=inputs.repo_root,
                    limit=8,
                )
            )

    heuristic_touchpoints = locate_native_candidates(inputs.repo_root, scope_keyword_bundle, limit=8)
    touchpoints = merge_touchpoints(primary=external_touchpoints, extras=heuristic_touchpoints, limit=12)
    ui_role_map, source_screen_map, ui_role_gaps = assign_ui_roles_to_touchpoints(
        touchpoints,
        evidence["flutter"]["representative_screens"],
    )
    registration_points = [
        {
            "path": item["path"],
            "kind": classify_registration_kind(item["path"]),
            "reason": "Potential registration/routing touchpoint from selected candidates.",
        }
        for item in touchpoints
        if is_global_review_path(item["path"])
    ]
    manual_entries = build_manual_review_entries(scope, evidence, touchpoints, registration_points)
    manual_candidate_paths = [item["path"] for item in manual_entries]
    selected_touchpoints = []
    seen_selected: set[str] = set()
    for item in touchpoints:
        payload = {
            "path": item["path"],
            "kind": item.get("kind", "other"),
            "confidence": confidence_label(item.get("confidence")),
            "reason": item.get("reason", ""),
            "risk": item.get("risk", "low"),
            "ui_role": ui_role_map.get(item["path"], "non_ui"),
            "source_screens": source_screen_map.get(item["path"], []),
        }
        selected_touchpoints.append(payload)
        seen_selected.add(item["path"])
    for item in manual_entries:
        if item["path"] in seen_selected:
            continue
        selected_touchpoints.append(
            {
                "path": item["path"],
                "kind": item["kind"],
                "confidence": item["confidence"],
                "reason": item["reason"],
                "risk": item["risk"],
                "ui_role": "registration_point" if item["kind"] in {"global_router", "theme_root", "dependency_root", "registration_point"} else "non_ui",
                "source_screens": [],
            }
        )
        seen_selected.add(item["path"])
    selected_touchpoints.sort(key=selected_touchpoint_sort_key)
    existing_files = [
        item["path"]
        for item in selected_touchpoints
        if item["path"] not in manual_candidate_paths and item.get("ui_role") != "registration_point"
    ]
    scope_confidence = scope["confidence"]
    native_impact_confidence = compute_native_impact_confidence(touchpoints, manual_entries)
    overall_risk = compute_overall_risk(scope_confidence, native_impact_confidence, manual_entries)
    ui_role_summary = ", ".join(
        f"{item['ui_role']}->{Path(item['path']).name}"
        for item in selected_touchpoints
        if item.get("ui_role") in {"primary_screen", "auxiliary_dialog", "auxiliary_overlay"}
    ) or "none"

    return {
        "requirement": {
            "id": scope["id"],
            "name": scope["name"],
            "summary": scope["summary"],
            "acceptance_criteria": scope["acceptance_points"],
        },
        "mode": "feature_sync",
        "sync_strategy": "scoped_patch",
        "source": {
            "flutter_paths": [str(inputs.flutter_path)] if inputs.flutter_path else [],
            "change_basis": build_change_basis(inputs),
            "change_ref": inputs.pr_diff_path.name if inputs.pr_diff_path else inputs.requirement_name,
            "prd_path": str(inputs.prd_path) if inputs.prd_path else None,
            "pr_diff_path": str(inputs.pr_diff_path) if inputs.pr_diff_path else None,
            "tests_paths": evidence["tests"],
            "notes": [
                "Planner output based on available evidence and upstream profile artifacts.",
                f"Scope keywords: {', '.join(scope_keywords) if scope_keywords else 'none'}",
                f"Base keywords: {', '.join(scope_keyword_bundle['base']) if scope_keyword_bundle['base'] else 'none'}",
                f"Alias keywords: {', '.join(scope_keyword_bundle['aliases']) if scope_keyword_bundle['aliases'] else 'none'}",
                "Profile v2 enabled: yes",
                "Profile source: repo_profile_core",
                f"LLM resolution enabled: {'yes' if inputs.llm_resolution_path else 'no'}",
            ],
        },
        "target": {
            "platform": "ios",
            "language": "swift",
            "ui_framework": "uikit",
            "repo_root": str(inputs.repo_root),
            "profile_path": str(inputs.profile_v2_dir),
            "module_hint": inputs.flutter_path.name if inputs.flutter_path else inputs.requirement_name,
            "write_mode": "apply_after_approval",
        },
        "behavior": {
            "user_flows": scope["user_flows"],
            "acceptance_points": scope["acceptance_points"],
            "states": evidence["flutter"]["states"],
            "interactions": evidence["flutter"]["interactions"],
            "strings": evidence["flutter"]["strings"],
            "assets": evidence["flutter"]["assets"],
        },
        "flutter_evidence": {
            "screens": evidence["flutter"]["screens"],
            "representative_screens": evidence["flutter"]["representative_screens"],
            "state_holders": evidence["flutter"]["state_holders"],
            "api_calls": evidence["flutter"]["api_calls"],
            "models": evidence["flutter"]["models"],
            "tests": evidence["tests"],
            "primary_features": digest_scope.get("primary_features", []),
            "supporting_features": digest_scope.get("supporting_features", []),
            "key_files_primary": primary_key_files,
            "key_files_supporting": supporting_key_files,
            "key_files": evidence["flutter"]["key_files"] + evidence["diff"]["files"][:8],
            "noise_candidates": evidence.get("flutter_digest", {}).get("noise_candidates", []),
            "conflicts": evidence.get("flutter_digest", {}).get("conflicts", []),
        },
        "native_impact": {
            "existing_files": existing_files,
            "new_files": [],
            "registration_points": [entry["path"] for entry in registration_points],
            "risk_files": [
                {
                    "path": item["path"],
                    "risk": item["risk"],
                    "reason": item["reason"],
                }
                for item in manual_entries
            ],
            "selected_touchpoints": selected_touchpoints,
        },
        "patch_plan": {
            "create": [],
            "update": existing_files,
            "manual_candidates": manual_candidate_paths,
            "deferred_items": [],
        },
        "unsupported": [],
        "notes": [
            f"Initial V1 planner output with scope confidence={scope_confidence}.",
            f"Native impact confidence={native_impact_confidence}; overall risk={overall_risk}.",
            f"Selected touchpoints using keywords: {', '.join(scope_keywords) if scope_keywords else 'none'}.",
            f"Keyword context: membership={scope_keyword_bundle['context'].get('membership_context')}, player={scope_keyword_bundle['context'].get('player_context')}, chapter_list={scope_keyword_bundle['context'].get('chapter_list_context')}, wallet={scope_keyword_bundle['context'].get('wallet_context')}.",
            f"UI role mapping: {ui_role_summary}.",
            *[f"UI role gap: {item}" for item in ui_role_gaps],
        ],
    }


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
        lines = []
        if not value:
            return [f"{prefix}[]"]
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def write_text(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_feature_intent_spec(contract: dict) -> dict:
    requirement = contract["requirement"]
    behavior = contract["behavior"]
    flutter = contract["flutter_evidence"]
    source = contract["source"]
    representative = flutter.get("representative_screens", [])
    states = [item["name"] for item in behavior.get("states", []) if isinstance(item, dict) and item.get("name")]
    intents: list[dict] = []

    for index, item in enumerate(representative, start=1):
        intents.append(
            {
                "intent_id": f"ui_{index:02d}",
                "intent_type": "ui_flow",
                "screen_name": item.get("name"),
                "screen_path": item.get("path"),
                "screen_role": item.get("role", "primary_screen"),
                "interactions": behavior.get("interactions", [])[:6],
                "states": states[:6],
                "acceptance_points": behavior.get("acceptance_points", [])[:4],
            }
        )

    if flutter.get("api_calls"):
        intents.append(
            {
                "intent_id": f"data_{len(intents) + 1:02d}",
                "intent_type": "data_flow",
                "api_calls": flutter.get("api_calls", []),
                "models": flutter.get("models", []),
                "states": states[:6],
                "acceptance_points": behavior.get("acceptance_points", [])[:3],
            }
        )

    if not intents:
        intents.append(
            {
                "intent_id": "ui_01",
                "intent_type": "ui_flow",
                "screen_name": requirement["name"],
                "interactions": behavior.get("interactions", [])[:6],
                "states": states[:6],
                "acceptance_points": behavior.get("acceptance_points", [])[:4],
            }
        )

    return {
        "requirement": {
            "id": requirement["id"],
            "name": requirement["name"],
            "summary": requirement["summary"],
        },
        "intent_scope": {
            "primary_features": flutter.get("primary_features", []),
            "supporting_features": flutter.get("supporting_features", []),
            "flutter_paths": source.get("flutter_paths", []),
            "change_basis": source.get("change_basis", []),
            "change_ref": source.get("change_ref"),
        },
        "intent_units": intents,
        "behavior_contract": {
            "user_flows": behavior.get("user_flows", []),
            "acceptance_points": behavior.get("acceptance_points", []),
            "strings": behavior.get("strings", [])[:20],
            "assets": behavior.get("assets", [])[:20],
        },
    }


def planned_action_for_path(path: str, contract: dict) -> str:
    patch_plan = contract.get("patch_plan", {})
    if path in patch_plan.get("create", []):
        return "create_file"
    if path in patch_plan.get("update", []):
        return "edit_existing"
    if path in patch_plan.get("manual_candidates", []):
        return "manual_review"
    return "review_candidate"


def build_native_operation_plan(contract: dict) -> dict:
    requirement = contract["requirement"]
    behavior = contract["behavior"]
    selected = contract.get("native_impact", {}).get("selected_touchpoints", [])
    operations: list[dict] = []
    for index, item in enumerate(selected, start=1):
        operations.append(
            {
                "operation_id": f"op_{index:02d}",
                "action": planned_action_for_path(item["path"], contract),
                "target_path": item["path"],
                "target_kind": item.get("kind", "other"),
                "ui_role": item.get("ui_role", "non_ui"),
                "confidence": item.get("confidence", "low"),
                "risk": item.get("risk", "low"),
                "source_screens": item.get("source_screens", []),
                "intent_links": behavior.get("user_flows", [])[:4],
                "reason": item.get("reason", ""),
            }
        )

    manual_candidates = contract.get("patch_plan", {}).get("manual_candidates", [])
    return {
        "requirement": {
            "id": requirement["id"],
            "name": requirement["name"],
        },
        "operation_policy": {
            "execution_mode": "plan_then_confirm_then_apply",
            "auto_apply_confidence": "high",
            "manual_when": [
                "action=manual_review",
                "risk=high",
                "confidence=low",
                "ui_role=registration_point",
            ],
        },
        "operations": operations,
        "manual_candidates": manual_candidates,
    }


def extract_note_value(contract: dict, prefix: str, fallback: str) -> str:
    for note in contract.get("notes", []):
        if note.startswith(prefix):
            return note.split(prefix, 1)[1].rstrip(".")
    return fallback


def manual_reason_map(contract: dict) -> dict[str, dict]:
    risk_files = {
        item["path"]: item
        for item in contract.get("native_impact", {}).get("risk_files", [])
    }
    touchpoints = {
        item["path"]: item
        for item in contract.get("native_impact", {}).get("selected_touchpoints", [])
    }
    merged = dict(risk_files)
    for path, item in touchpoints.items():
        merged.setdefault(path, item)
    return merged


def render_sync_plan(contract: dict) -> str:
    req = contract["requirement"]
    behavior = contract["behavior"]
    source = contract["source"]
    native_impact = contract["native_impact"]
    patch_plan = contract["patch_plan"]
    scope_confidence = extract_note_value(contract, "Initial V1 planner output with scope confidence=", "medium")
    native_impact_confidence = extract_note_value(contract, "Native impact confidence=", "medium").split(";", 1)[0]
    overall_risk = extract_note_value(contract, "Native impact confidence=", "medium").split("overall risk=")[-1]
    manual_lookup = manual_reason_map(contract)
    lines = [
        f"# Sync Plan: {req['name']}",
        "",
        "## 1. 需求概览",
        "",
        f"- Requirement ID: `{req['id']}`",
        f"- Requirement Name: `{req['name']}`",
        f"- Summary: {req['summary']}",
        f"- Scope Confidence: `{scope_confidence}`",
        f"- Native Impact Confidence: `{native_impact_confidence}`",
        "",
        "### 关键用户流程",
        "",
    ]
    lines.extend(f"- {item}" for item in behavior["user_flows"])
    lines.extend(
        [
            "",
            "### 关键验收点",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in behavior["acceptance_points"])
    lines.extend(
        [
            "",
            "## 2. Flutter 证据概览",
            "",
            "### 主要代码范围",
            "",
        ]
    )
    flutter_paths = source.get("flutter_paths") or contract["flutter_evidence"]["key_files"]
    if flutter_paths:
        lines.extend(f"- {item}" for item in flutter_paths[:10])
    else:
        lines.append("- No Flutter path provided")
    primary_features = contract["flutter_evidence"].get("primary_features", [])
    supporting_features = contract["flutter_evidence"].get("supporting_features", [])
    if primary_features:
        lines.extend(["", "### 需求主范围", ""])
        lines.append(f"- Primary Features: `{', '.join(primary_features)}`")
    if supporting_features:
        lines.extend(["", "### 配套范围", ""])
        lines.append(f"- Supporting Features: `{', '.join(supporting_features)}`")
    lines.extend(
        [
            "",
            "### PR Diff 摘要",
            "",
            f"- Change basis: {', '.join(source['change_basis'])}",
        ]
    )
    if source.get("pr_diff_path"):
        lines.append(f"- Diff artifact: {source['pr_diff_path']}")
    lines.extend(["", "### 提取到的页面与状态管理", ""])
    representative_screens = contract["flutter_evidence"].get("representative_screens", [])
    if representative_screens:
        lines.extend(
            f"- Screen: `{item['name']}` | role=`{item.get('role', 'primary_screen')}`"
            for item in representative_screens
        )
    elif contract["flutter_evidence"]["screens"]:
        lines.extend(f"- Screen: `{item}`" for item in contract["flutter_evidence"]["screens"])
    if contract["flutter_evidence"]["state_holders"]:
        lines.extend(f"- State Holder: `{item}`" for item in contract["flutter_evidence"]["state_holders"])
    if not contract["flutter_evidence"]["screens"] and not contract["flutter_evidence"]["state_holders"]:
        lines.append("- No explicit screen or state-holder evidence detected")
    lines.extend(["", "### API 与模型证据", ""])
    if contract["flutter_evidence"]["api_calls"]:
        lines.extend(f"- API: `{item}`" for item in contract["flutter_evidence"]["api_calls"])
    if contract["flutter_evidence"].get("models"):
        lines.extend(f"- Model: `{item}`" for item in contract["flutter_evidence"]["models"])
    if not contract["flutter_evidence"]["api_calls"] and not contract["flutter_evidence"].get("models"):
        lines.append("- No explicit API or model evidence detected")
    lines.extend(["", "### 测试证据", ""])
    tests = contract["flutter_evidence"]["tests"]
    if tests:
        lines.extend(f"- {item}" for item in tests)
    else:
        lines.append("- No explicit test input provided")
    lines.extend(
        [
            "",
            "## 3. 目标原生结果",
            "",
            "### 目标行为",
            "",
            f"- Deliver `{req['name']}` into the iOS repository using scoped patching",
            "",
            "### 期望与 Flutter 保持一致的点",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in behavior["acceptance_points"])
    lines.extend(["", "### 提取到的状态与交互", ""])
    if behavior["states"]:
        lines.extend(f"- State: `{item['name']}` (`{item['kind']}`)" for item in behavior["states"])
    if behavior["interactions"]:
        lines.extend(f"- Interaction: `{item}`" for item in behavior["interactions"])
    if behavior["strings"]:
        lines.extend(f"- String: `{item}`" for item in behavior["strings"])
    if behavior["assets"]:
        lines.extend(f"- Asset: `{item}`" for item in behavior["assets"])
    if not any([behavior["states"], behavior["interactions"], behavior["strings"], behavior["assets"]]):
        lines.append("- No additional behavior metadata extracted from Flutter files")
    lines.extend(
        [
            "",
            "## 4. 计划触点",
            "",
            "### 需更新的现有文件",
            "",
        ]
    )
    if native_impact["existing_files"]:
        for item in native_impact["selected_touchpoints"]:
            if item["path"] in native_impact["existing_files"]:
                lines.append(
                    f"- `{item['path']}`: {item['reason']} | kind=`{item.get('kind', 'other')}` | "
                    f"ui_role=`{item.get('ui_role', 'non_ui')}` | risk=`{item.get('risk', 'low')}`"
                )
    else:
        lines.append("- No existing file selected yet")
    lines.extend(
        [
            "",
            "### 计划新建的文件",
            "",
        ]
    )
    if patch_plan["create"]:
        lines.extend(f"- `{item}`: planned create" for item in patch_plan["create"])
    else:
        lines.append("- No new file is planned in this initial output")
    lines.extend(
        [
            "",
            "### 可能涉及但暂不自动处理的注册点",
            "",
        ]
    )
    if patch_plan["manual_candidates"]:
        for item in patch_plan["manual_candidates"]:
            detail = manual_lookup.get(item, {})
            lines.append(
                f"- `{item}`: {detail.get('reason', 'manual candidate')} | risk=`{detail.get('risk', 'high')}`"
            )
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## 5. 计划动作",
            "",
            "### UI",
            "",
            "- 将代表页面映射为 `primary_screen / auxiliary_dialog / auxiliary_overlay / component_view`",
            "",
            "### 状态与交互",
            "",
            "- Map Flutter behavior into the selected iOS touchpoints",
            "",
            "### Networking / Model",
            "",
            "- Reuse the profiled networking/model conventions where needed",
            "",
            "### 路由 / 注册",
            "",
            "- Keep route or global registration changes behind explicit review",
            "",
            "## 6. 不支持项与人工处理项",
            "",
            "### 当前不支持项",
            "",
        ]
    )
    if contract["unsupported"]:
        lines.extend(f"- {item}" for item in contract["unsupported"])
    else:
        lines.append("- None declared in this initial output")
    lines.extend(
        [
            "",
            "### 需人工处理项",
            "",
        ]
    )
    if patch_plan["manual_candidates"]:
        for item in patch_plan["manual_candidates"]:
            detail = manual_lookup.get(item, {})
            lines.append(f"- {item}: {detail.get('reason', 'manual candidate')}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## 7. 风险摘要",
            "",
            f"- Overall Risk: `{overall_risk}`",
            "- Main Risks:",
            f"  - Native touchpoint confidence is `{native_impact_confidence}` and may still need manual refinement",
        "",
            "## 8. 确认闸门",
            "",
            "- 当前尚未修改任何原生代码",
            "- 如果确认本计划，将进入 `apply` 阶段",
            "- Apply 阶段将依据 `requirement_sync_contract.yaml` 和本计划执行 patch",
        ]
    )
    return "\n".join(lines)


def render_touchpoints(contract: dict) -> str:
    req = contract["requirement"]
    touchpoints = contract["native_impact"]["selected_touchpoints"]
    manual_lookup = manual_reason_map(contract)
    lines = [
        f"# Touchpoints: {req['name']}",
        "",
        "## 1. 触点概览",
        "",
        f"- Requirement ID: `{req['id']}`",
        f"- Requirement Name: `{req['name']}`",
        f"- Total Touchpoints: `{len(touchpoints)}`",
        f"- Existing Files: `{len(contract['native_impact']['existing_files'])}`",
        f"- New Files: `{len(contract['native_impact']['new_files'])}`",
        f"- Manual Candidates: `{len(contract['patch_plan']['manual_candidates'])}`",
        "",
        "## 2. 现有文件触点",
        "",
    ]
    existing = [item for item in touchpoints if item["path"] in contract["native_impact"]["existing_files"]]
    if not existing:
        lines.append("- None")
    for item in existing:
        source_screens = item.get("source_screens", [])
        lines.extend(
            [
                f"### `{item['path']}`",
                "",
                f"- Type: `{item['kind']}`",
                f"- UI Role: `{item.get('ui_role', 'non_ui')}`",
                "- Action: `update`",
                f"- Confidence: `{item['confidence']}`",
                f"- Risk: `{item.get('risk', 'low')}`",
                f"- Reason: {item['reason']}",
                f"- Source Screens: `{', '.join(source_screens)}`" if source_screens else "- Source Screens: `none`",
                "- Expected Change:",
                "  - Refine and align this touchpoint with Flutter behavior",
                "",
            ]
        )
    lines.extend(["## 3. 新建文件触点", "", "- None", "", "## 4. 注册点与全局触点", ""])
    manual = contract["patch_plan"]["manual_candidates"]
    if not manual:
        lines.append("- None")
    else:
        for item in manual:
            detail = manual_lookup.get(item, {})
            lines.extend(
                [
                    f"### `{item}`",
                    "",
                    f"- Type: `{detail.get('kind', 'registration_point')}`",
                    "- Action: `manual_candidate`",
                    f"- Confidence: `{detail.get('confidence', 'medium')}`",
                    f"- Risk: `{detail.get('risk', 'high')}`",
                    f"- Reason: {detail.get('reason', 'Global touchpoint should stay under explicit review')}",
                    "- Note:",
                    "  - Keep this out of automatic apply unless explicitly approved.",
                    "",
                ]
            )
    lines.extend(["## 5. 人工候选触点", ""])
    if not manual:
        lines.append("- None")
    else:
        for item in manual:
            detail = manual_lookup.get(item, {})
            lines.extend(
                [
                    f"### `{item}`",
                    "",
                    f"- Type: `{detail.get('kind', 'registration_point')}`",
                    f"- Confidence: `{detail.get('confidence', 'medium')}`",
                    f"- Risk: `{detail.get('risk', 'high')}`",
                    f"- Reason: {detail.get('reason', 'Global integration should be reviewed manually in V1')}",
                    "- Suggested Manual Action:",
                    "  - Review and wire this touchpoint after plan approval.",
                    "",
                ]
            )
    return "\n".join(lines)


def render_risk_report(contract: dict) -> str:
    req = contract["requirement"]
    risk_files = contract["native_impact"]["risk_files"]
    unsupported = contract["unsupported"]
    digest_noise = contract["flutter_evidence"].get("noise_candidates", [])
    digest_conflicts = contract["flutter_evidence"].get("conflicts", [])
    ui_role_gaps = [note.split("UI role gap: ", 1)[1] for note in contract.get("notes", []) if note.startswith("UI role gap: ")]
    scope_confidence = extract_note_value(contract, "Initial V1 planner output with scope confidence=", "medium")
    native_impact_confidence = extract_note_value(contract, "Native impact confidence=", "medium").split(";", 1)[0]
    overall_risk = extract_note_value(contract, "Native impact confidence=", "medium").split("overall risk=")[-1]
    lines = [
        f"# Risk Report: {req['name']}",
        "",
        "## 1. 风险总览",
        "",
        f"- Requirement ID: `{req['id']}`",
        f"- Requirement Name: `{req['name']}`",
        f"- Overall Risk: `{overall_risk}`",
        f"- Scope Confidence: `{scope_confidence}`",
        f"- Native Impact Confidence: `{native_impact_confidence}`",
        "",
        "### 主要风险",
        "",
        "- Touchpoint selection is still based on initial V1 profile heuristics.",
        "- Global registration points and app-wide files remain behind manual review.",
        "",
        "## 2. Flutter Digest 风险",
        "",
    ]
    if not digest_conflicts and not digest_noise:
        lines.append("- No explicit digest conflicts or noise candidates were recorded.")
    else:
        if digest_conflicts:
            lines.append("### 输入冲突")
            lines.append("")
            for item in digest_conflicts:
                kind = item.get("kind", "conflict")
                reason = item.get("reason", "Digest conflict requires review")
                lines.append(f"- `{kind}`: {reason}")
            lines.append("")
        if digest_noise:
            lines.append("### 噪音候选")
            lines.append("")
            for item in digest_noise[:12]:
                name = item.get("name", "unknown")
                reason = item.get("reason", "Digest marked this item as noise candidate")
                lines.append(f"- `{name}`: {reason}")
            lines.append("")
    if ui_role_gaps:
        lines.append("### UIKit 语义映射缺口")
        lines.append("")
        for item in ui_role_gaps:
            lines.append(f"- {item}")
        lines.append("")
    lines.extend(
        [
            "## 3. 架构与仓库不确定性",
            "",
            "- Initial planner output may need narrower feature evidence to refine touchpoints.",
            "- Legacy UIKit repositories may mix feature, service, and registration logic inside the same file.",
            "",
            "## 4. 高风险旧文件",
            "",
        ]
    )
    if not risk_files:
        lines.append("- None")
    else:
        for item in risk_files:
            lines.extend(
                [
                    f"### `{item['path']}`",
                    "",
                    f"- Risk: `{item['risk']}`",
                    f"- Reason: {item['reason']}",
                    "- Potential Impact:",
                    "  - May require app-wide review before patching.",
                    "",
                ]
            )
    lines.extend(
        [
            "## 5. Flutter 不支持或难以自动同步的行为",
            "",
        ]
    )
    if unsupported:
        lines.extend(f"- {item}" for item in unsupported)
    else:
        lines.append("- None declared in this initial output")
    lines.extend(
        [
            "",
            "## 6. 一致性风险",
            "",
            "- Behavior parity still depends on deeper feature evidence.",
            "",
            "## 7. 测试与验证缺口",
            "",
        ]
    )
    if contract["flutter_evidence"]["tests"]:
        lines.extend(f"- Review test evidence from {item}" for item in contract["flutter_evidence"]["tests"])
    else:
        lines.append("- No explicit Flutter tests were provided.")
    lines.extend(
        [
            "",
            "## 8. 建议审查重点",
            "",
            "- Confirm the selected touchpoints before apply.",
            "- Confirm whether any manual candidates should remain manual in V1.",
        ]
    )
    return "\n".join(lines)


def handle_plan(args: argparse.Namespace) -> int:
    inputs = build_inputs(args)
    validate_inputs(inputs)
    ensure_dir(inputs.run_dir)
    contract = build_contract(inputs)
    contract_text = "\n".join(dump_yaml(contract)) + "\n"
    feature_intent_spec = build_feature_intent_spec(contract)
    native_operation_plan = build_native_operation_plan(contract)
    write_text(inputs.run_dir / "requirement_sync_contract.yaml", contract_text)
    write_text(inputs.run_dir / FEATURE_INTENT_FILE, "\n".join(dump_yaml(feature_intent_spec)) + "\n")
    write_text(inputs.run_dir / NATIVE_OPERATION_FILE, "\n".join(dump_yaml(native_operation_plan)) + "\n")
    write_text(inputs.run_dir / "sync_plan.md", render_sync_plan(contract))
    write_text(inputs.run_dir / "touchpoints.md", render_touchpoints(contract))
    write_text(inputs.run_dir / "risk_report.md", render_risk_report(contract))
    print("Planning artifacts generated.")
    print(f"- run_dir: {inputs.run_dir}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        print("Run status: missing")
        return 0
    expected = [
        FEATURE_INTENT_FILE,
        NATIVE_OPERATION_FILE,
        "requirement_sync_contract.yaml",
        "sync_plan.md",
        "touchpoints.md",
        "risk_report.md",
    ]
    print("Run status: present")
    for name in expected:
        print(f"- {name}: {'yes' if (run_dir / name).exists() else 'no'}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "plan":
            return handle_plan(args)
        if args.command == "status":
            return handle_status(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"atlas-planner error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
