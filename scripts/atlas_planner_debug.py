#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
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


PLAN_VALIDATION_FILE = "plan_validation.md"
FLUTTER_CHANGES_FILE = "flutter_changes.md"
INTENT_MARKDOWN_FILE = "intent.md"
EDIT_TASKS_MARKDOWN_FILE = "edit_tasks.md"
EDIT_TASKS_JSON_FILE = "edit_tasks.json"
NATIVE_TOUCHPOINTS_FILE = "native_touchpoints.md"
EXECUTION_LOG_FILE = "execution_log.md"
HUNK_FACTS_FILE = "hunk_facts.json"

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

LOGIC_SIGNAL_TOKENS = (
    "if ",
    " if(",
    "when",
    "countdown",
    "timer",
    "expire",
    "remaining",
    "unlock",
    "purchase",
    "paywall",
    "dialog",
    "popup",
    "retention",
    "intro",
    "price",
    "coin",
    "product",
    "sku",
    "vip",
    "enable",
    "disable",
    "visible",
    "hidden",
    "show",
    "hide",
    "倒计时",
    "挽留",
    "解锁",
    "充值",
    "引言",
)

FEATURE_GROUP_KEYWORDS = {
    "引言样式": ("引言", "intro", "style", "theme"),
    "引言更多": ("引言", "more", "expand", "detail"),
    "充值商品弹窗": ("充值", "商品", "purchase", "paywall", "dialog", "popup", "product", "sku"),
    "章节解锁页面": ("章节", "解锁", "unlock", "chapter", "countdown"),
    "充值挽留": ("挽留", "retention", "countdown", "timer", "expire"),
}

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


def parse_prd_sections(path: Path | None) -> dict[str, list[str]]:
    text = read_text_safe(path)
    if not text:
        return {}
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*")):
            if current is not None:
                sections.setdefault(current, []).append(line.lstrip("-*").strip())
            continue
        # 纯文本行优先视为分组标题，URL 行不作为标题。
        if "http://" in line or "https://" in line:
            if current is not None:
                sections.setdefault(current, []).append(line)
            continue
        current = line.lstrip("#").strip()
        sections.setdefault(current, [])
    return sections


def normalize_logic_line(line: str) -> str:
    text = line.strip()
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.lstrip("+-* ").strip()
    if len(text) > 140:
        text = text[:137] + "..."
    return text


def extract_logic_constraints(lines: list[str], limit: int = 12) -> list[str]:
    constraints: list[str] = []
    for raw in lines:
        line = normalize_logic_line(raw)
        if len(line) < 6:
            continue
        lower = line.lower()
        if not any(token in lower for token in LOGIC_SIGNAL_TOKENS):
            continue
        if re.search(r"\bif\s*\(([^)]+)\)", line, re.IGNORECASE):
            match = re.search(r"\bif\s*\(([^)]+)\)", line, re.IGNORECASE)
            assert match is not None
            constraints.append(f"条件分支: {match.group(1).strip()}")
            continue
        if any(token in lower for token in ("countdown", "timer", "expire", "remaining", "倒计时")):
            constraints.append(f"倒计时约束: {line}")
            continue
        if any(token in lower for token in ("enable", "disable", "disabled", "按钮")):
            constraints.append(f"可用性约束: {line}")
            continue
        if any(token in lower for token in ("visible", "hidden", "show", "hide", "display", "展示", "显示")):
            constraints.append(f"显隐约束: {line}")
            continue
        if any(token in lower for token in ("price", "coin", "product", "sku", "充值", "商品")):
            constraints.append(f"价格商品约束: {line}")
            continue
        constraints.append(f"业务约束: {line}")
    return unique_preserve(constraints)[:limit]


def parse_diff_evidence(path: Path | None) -> dict:
    text = read_text_safe(path)
    if not text:
        return {"files": [], "summary_lines": [], "logic_constraints": []}
    files: list[str] = []
    summary_lines: list[str] = []
    added_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("+++ b/"):
            files.append(stripped[6:])
        elif stripped.startswith("+") and not stripped.startswith("+++"):
            content = stripped[1:].strip()
            if content and len(summary_lines) < 8:
                summary_lines.append(content[:160])
            if content and not content.startswith("//"):
                added_lines.append(content)
    logic_constraints = extract_logic_constraints(added_lines, limit=16)
    return {"files": files[:20], "summary_lines": summary_lines, "logic_constraints": logic_constraints}


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
    prd_sections = parse_prd_sections(inputs.prd_path)
    prd_logic_constraints = extract_logic_constraints(
        [item for values in prd_sections.values() for item in values],
        limit=10,
    )
    diff_evidence = parse_diff_evidence(inputs.pr_diff_path)
    logic_constraints = unique_preserve(prd_logic_constraints + diff_evidence.get("logic_constraints", []))
    return {
        "prd": parse_prd_evidence(inputs.prd_path),
        "prd_sections": prd_sections,
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
            "logic_constraints": digest_field(flutter_digest, "logic_constraints", logic_constraints),
        },
        "diff": diff_evidence,
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
    if not any([inputs.flutter_path, inputs.flutter_digest_path, inputs.pr_diff_path]):
        raise FileNotFoundError("flutter change evidence is required: provide at least one of --flutter-path, --flutter-digest-path, --pr-diff-path")
    if inputs.llm_resolution_path is None:
        raise FileNotFoundError("llm analysis output is required: provide --llm-resolution-path")
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


def normalize_llm_task(task: dict, index: int) -> dict:
    behavior = task.get("behavior_contract", {}) if isinstance(task.get("behavior_contract"), dict) else {}
    landing = task.get("native_landing", {}) if isinstance(task.get("native_landing"), dict) else {}
    anchor = task.get("edit_anchor", {}) if isinstance(task.get("edit_anchor"), dict) else {}
    touchpoints = landing.get("touchpoints", [])
    if not isinstance(touchpoints, list):
        touchpoints = []
    mapping = task.get("mapping_proof", {}) if isinstance(task.get("mapping_proof"), dict) else {}
    flutter_entrypoints = mapping.get("flutter_entrypoints", [])
    native_chain = mapping.get("native_chain", [])
    mapping_evidence = mapping.get("evidence", [])
    evidence_lines = mapping.get("evidence_lines", [])
    reverse_trace = mapping.get("reverse_trace", [])
    if not isinstance(flutter_entrypoints, list):
        flutter_entrypoints = []
    if not isinstance(native_chain, list):
        native_chain = []
    if not isinstance(mapping_evidence, list):
        mapping_evidence = []
    if not isinstance(evidence_lines, list):
        evidence_lines = []
    if not isinstance(reverse_trace, list):
        reverse_trace = []
    return {
        "task_id": task.get("task_id") or f"G{index:02d}",
        "task_name": task.get("task_name") or f"功能组-{index}",
        "feature_scope": str(task.get("feature_scope", "")).strip(),
        "trigger_lifecycle": str(task.get("trigger_lifecycle", "")).strip(),
        "capability_goal": task.get("capability_goal") or "待补充",
        "trigger_or_precondition": task.get("trigger_or_precondition") or "待补充",
        "behavior_contract": {
            "states": behavior.get("states", []) if isinstance(behavior.get("states", []), list) else [],
            "interactions": behavior.get("interactions", []) if isinstance(behavior.get("interactions", []), list) else [],
            "side_effects": behavior.get("side_effects", []) if isinstance(behavior.get("side_effects", []), list) else [],
            "exceptions": behavior.get("exceptions", []) if isinstance(behavior.get("exceptions", []), list) else [],
            "logic_constraints": behavior.get("logic_constraints", []) if isinstance(behavior.get("logic_constraints", []), list) else [],
        },
        "native_landing": {
            "primary_path": landing.get("primary_path", ""),
            "touchpoint_count": landing.get("touchpoint_count", len(touchpoints) if touchpoints else 0),
            "ui_roles": landing.get("ui_roles", []) if isinstance(landing.get("ui_roles", []), list) else [],
            "touchpoints": touchpoints,
        },
        "edit_anchor": {
            "target_file": anchor.get("target_file", ""),
            "target_files": anchor.get("target_files", []) if isinstance(anchor.get("target_files", []), list) else [],
            "class_or_symbol_hint": anchor.get("class_or_symbol_hint", ""),
            "candidate_only": bool(anchor.get("candidate_only", True)),
        },
        "acceptance_assertions": task.get("acceptance_assertions", []) if isinstance(task.get("acceptance_assertions", []), list) else [],
        "mapping_proof": {
            "status": str(mapping.get("status", "unmapped")).lower(),
            "confidence": str(mapping.get("confidence", "low")).lower(),
            "entry_kind": str(mapping.get("entry_kind", "")).strip().lower(),
            "entry_semantics": str(mapping.get("entry_semantics", "")).strip().lower(),
            "flutter_entrypoints": flutter_entrypoints,
            "native_chain": native_chain,
            "reverse_trace": reverse_trace,
            "evidence_lines": evidence_lines,
            "evidence": mapping_evidence,
        },
        "execution_mode": task.get("execution_mode") or "cli_direct_edit",
        "planned_action": task.get("planned_action") or "review",
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_llm_plan(path: Path | None, inputs: PlanningInputs) -> dict:
    if path is None:
        raise ValueError("missing llm plan path")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("llm plan payload must be object")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("llm plan payload must include non-empty tasks")
    hunk_facts = payload.get("hunk_facts")
    if not isinstance(hunk_facts, (dict, list)) or not hunk_facts:
        raise ValueError("llm plan payload must include non-empty hunk_facts (from flutter_hunk_extract)")

    meta = payload.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("llm plan payload must include meta object")
    analysis_mode = str(meta.get("analysis_mode", "")).strip().lower()
    if analysis_mode != "live_llm":
        raise ValueError("llm plan meta.analysis_mode must be live_llm")
    generated_by = str(meta.get("generated_by", "")).strip()
    if not generated_by:
        raise ValueError("llm plan meta.generated_by is required")
    lowered = generated_by.lower()
    if any(token in lowered for token in ("demo", "example", "sample", "mock")):
        raise ValueError("llm plan appears to be example/sample output; real LLM analysis is required")

    evidence = meta.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("llm plan meta.evidence is required")
    if inputs.pr_diff_path:
        expected_diff = str(inputs.pr_diff_path)
        provided_diff = str(evidence.get("pr_diff_path", "")).strip()
        if provided_diff != expected_diff:
            raise ValueError("llm plan evidence.pr_diff_path does not match planner --pr-diff-path")
        provided_hash = str(evidence.get("pr_diff_sha256", "")).strip().lower()
        actual_hash = file_sha256(inputs.pr_diff_path).lower()
        if provided_hash != actual_hash:
            raise ValueError("llm plan evidence.pr_diff_sha256 mismatch; output is not based on current diff")
    schema_failures: list[str] = []
    for idx, task in enumerate(tasks, 1):
        if not isinstance(task, dict):
            schema_failures.append(f"G{idx:02d}: task payload not object")
            continue
        task_name = task.get("task_name") or task.get("task_id") or f"G{idx:02d}"
        planned_action = str(task.get("planned_action") or "review")
        if planned_action not in {"update", "create", "manual"}:
            continue
        if not str(task.get("feature_scope", "")).strip():
            schema_failures.append(f"{task_name}: missing feature_scope")
        if not str(task.get("trigger_lifecycle", "")).strip():
            schema_failures.append(f"{task_name}: missing trigger_lifecycle")
        mapping = task.get("mapping_proof", {})
        if not isinstance(mapping, dict):
            schema_failures.append(f"{task_name}: missing mapping_proof")
            continue
        if not str(mapping.get("entry_kind", "")).strip():
            schema_failures.append(f"{task_name}: missing mapping_proof.entry_kind")
        if is_popup_task(task):
            entry_semantics = str(mapping.get("entry_semantics", "")).strip().lower()
            native_chain = mapping.get("native_chain", [])
            first_chain = str(native_chain[0]) if isinstance(native_chain, list) and native_chain else ""
            if entry_semantics != "popup_show":
                schema_failures.append(f"{task_name}: popup task requires mapping_proof.entry_semantics=popup_show")
            if not popup_entry_ok(first_chain):
                schema_failures.append(f"{task_name}: popup task first native_chain must be show/present entry")
        native_chain = mapping.get("native_chain", [])
        reverse_trace = mapping.get("reverse_trace", [])
        evidence_lines = mapping.get("evidence_lines", [])
        if not isinstance(native_chain, list) or not [x for x in native_chain if str(x).strip()]:
            schema_failures.append(f"{task_name}: missing mapping_proof.native_chain")
        if not isinstance(reverse_trace, list) or not [x for x in reverse_trace if str(x).strip()]:
            schema_failures.append(f"{task_name}: missing mapping_proof.reverse_trace")
        if not isinstance(evidence_lines, list) or not [x for x in evidence_lines if str(x).strip()]:
            schema_failures.append(f"{task_name}: missing mapping_proof.evidence_lines")
    if schema_failures:
        raise ValueError("llm plan schema check failed: " + "; ".join(schema_failures[:10]))
    return payload


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


def find_unresolved_items(sync_plan_text: str) -> list[str]:
    unresolved_tokens = ("需确认", "待定", "TBD", "需要确认", "具体文件待定")
    hits: list[str] = []
    lines = sync_plan_text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if any(token.lower() in line.lower() for token in unresolved_tokens):
            hits.append(f"L{idx}: {line.strip()[:160]}")
    return hits


def has_descriptive_trigger(trigger: str) -> bool:
    text = (trigger or "").strip()
    if not text:
        return False
    lowered = text.lower()
    weak_tokens = ("待补充", "待确认", "待定", "tbd", "触发 ", "对应流程")
    if any(token in lowered for token in weak_tokens):
        return False
    return len(text) >= 8


def parse_evidence_line_ref(ref: str) -> tuple[str, int] | None:
    text = (ref or "").strip()
    if not text or ":" not in text:
        return None
    path_part, line_part = text.rsplit(":", 1)
    try:
        line_no = int(line_part.strip())
    except ValueError:
        return None
    if line_no <= 0:
        return None
    return path_part.strip(), line_no


def validate_evidence_lines(repo_root: Path, evidence_lines: list[str]) -> tuple[bool, str]:
    if not evidence_lines:
        return False, "empty evidence_lines"
    checked = 0
    for item in evidence_lines:
        parsed = parse_evidence_line_ref(str(item))
        if not parsed:
            continue
        rel_path, line_no = parsed
        abs_path = (repo_root / rel_path).resolve()
        try:
            abs_path.relative_to(repo_root.resolve())
        except ValueError:
            continue
        if not abs_path.exists() or not abs_path.is_file():
            continue
        try:
            with abs_path.open("r", encoding="utf-8", errors="ignore") as fh:
                for idx, _ in enumerate(fh, 1):
                    if idx == line_no:
                        checked += 1
                        break
        except OSError:
            continue
    return checked > 0, f"matched={checked}"


def lifecycle_expected_tokens(lifecycle: str) -> set[str]:
    lower = lifecycle.lower()
    tokens: set[str] = set()
    if any(k in lower for k in ("tail", "尾", "footer")):
        tokens.update({"tail", "chaptertailview", "tailview", "footer"})
    if any(k in lower for k in ("prologue", "引言", "header")):
        tokens.update({"prologue", "header"})
    if any(k in lower for k in ("unlock", "解锁")):
        tokens.update({"unlock", "purchase", "buy"})
    if any(k in lower for k in ("retain", "挽留", "countdown", "倒计时")):
        tokens.update({"retain", "charge", "paywall", "countdown"})
    return tokens


def popup_entry_ok(chain_item: str) -> bool:
    lower = (chain_item or "").lower()
    return any(token in lower for token in ("show(", ".show(", ".show(...", "present("))


def is_popup_task(task: dict) -> bool:
    name = str(task.get("task_name") or "").lower()
    feature_scope = str(task.get("feature_scope") or "").lower()
    lifecycle = str(task.get("trigger_lifecycle") or "").lower()
    return any(token in name for token in ("弹窗", "popup", "dialog")) or "popup" in feature_scope or "popup" in lifecycle


def collect_hunk_files(hunk_facts: object) -> set[str]:
    files: set[str] = set()
    if isinstance(hunk_facts, dict):
        items = hunk_facts.get("business_hunks", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    f = str(item.get("file") or "").strip()
                    if f:
                        files.add(f)
    elif isinstance(hunk_facts, list):
        for item in hunk_facts:
            if isinstance(item, dict):
                f = str(item.get("file") or "").strip()
                if f:
                    files.add(f)
    return files


def build_plan_validation(contract: dict, sync_plan_text: str, tasks: list[dict] | None = None, llm_plan: dict | None = None) -> dict:
    checks: list[dict] = []

    unresolved_hits = find_unresolved_items(sync_plan_text)
    checks.append(
        {
            "id": "V1",
            "name": "无未决项",
            "result": "PASS" if not unresolved_hits else "FAIL",
            "detail": "" if not unresolved_hits else "; ".join(unresolved_hits[:8]),
        }
    )

    selected_touchpoints = [
        item
        for item in contract.get("native_impact", {}).get("selected_touchpoints", [])
        if item.get("path") in set(contract.get("patch_plan", {}).get("update", []))
    ]
    missing_reasons = [item.get("path", "unknown") for item in selected_touchpoints if not (item.get("reason") or "").strip()]
    checks.append(
        {
            "id": "V2",
            "name": "入口已定位",
            "result": "PASS" if not missing_reasons else "FAIL",
            "detail": "" if not missing_reasons else "缺少触点原因: " + ", ".join(missing_reasons[:8]),
        }
    )

    weak_reason_paths = []
    for item in selected_touchpoints:
        reason = (item.get("reason") or "").lower()
        if reason and not any(token in reason for token in ("trigger", "flow", "delegate", "callback", "事件", "场景", "链路", "入口")):
            weak_reason_paths.append(item.get("path", "unknown"))
    task_chain_gaps: list[str] = []
    normalized_tasks = tasks or []
    for task in normalized_tasks:
        if not isinstance(task, dict):
            continue
        task_name = task.get("task_name") or task.get("task_id") or "unknown_task"
        trigger = str(task.get("trigger_or_precondition") or "")
        behavior_contract = task.get("behavior_contract", {})
        if not isinstance(behavior_contract, dict):
            behavior_contract = {}
        logic_constraints = behavior_contract.get("logic_constraints", [])
        interactions = behavior_contract.get("interactions", [])
        planned_action = str(task.get("planned_action") or "review")
        if planned_action in {"update", "create", "manual"}:
            if not has_descriptive_trigger(trigger):
                task_chain_gaps.append(f"{task_name}: 触发条件描述不足")
            has_logic = isinstance(logic_constraints, list) and len([x for x in logic_constraints if str(x).strip()]) > 0
            has_interactions = isinstance(interactions, list) and len([x for x in interactions if str(x).strip()]) > 0
            if not (has_logic or has_interactions):
                task_chain_gaps.append(f"{task_name}: 缺少逻辑约束/关键交互")

    v3_warn_details: list[str] = []
    if task_chain_gaps:
        v3_warn_details.extend(task_chain_gaps[:8])
    elif not normalized_tasks and weak_reason_paths:
        v3_warn_details.append("建议补充场景/链路描述: " + ", ".join(weak_reason_paths[:8]))
    checks.append(
        {
            "id": "V3",
            "name": "入口定位方式",
            "result": "PASS" if not v3_warn_details else "WARN",
            "detail": "" if not v3_warn_details else "; ".join(v3_warn_details),
        }
    )

    model_related = [
        item
        for item in contract.get("native_impact", {}).get("selected_touchpoints", [])
        if item.get("kind") == "feature_model"
    ]
    checks.append(
        {
            "id": "V4",
            "name": "字段对齐表",
            "result": "PASS" if not model_related else "WARN",
            "detail": "" if not model_related else "当前版本尚未自动生成逐字段表，涉及 model 触点请人工复核。",
        }
    )

    missing_design_source = [
        item.get("path", "unknown")
        for item in contract.get("native_impact", {}).get("selected_touchpoints", [])
        if item.get("ui_role") in {"primary_screen", "auxiliary_dialog", "auxiliary_overlay", "component_view"}
        and not item.get("source_screens")
    ]
    checks.append(
        {
            "id": "V5",
            "name": "UI 设计参考",
            "result": "PASS" if not missing_design_source else "FAIL",
            "detail": "" if not missing_design_source else "UI 触点缺少设计输入（需 Figma 链接+截图）: " + ", ".join(missing_design_source[:8]),
        }
    )

    behavior = contract.get("behavior", {})
    has_trigger_signal = bool(behavior.get("user_flows") or behavior.get("interactions"))
    checks.append(
        {
            "id": "V6",
            "name": "触发方式",
            "result": "PASS" if has_trigger_signal else "FAIL",
            "detail": "" if has_trigger_signal else "behavior 中缺少 user_flows/interactions，无法确认触发方式。",
        }
    )

    mapping_failures: list[str] = []
    for task in normalized_tasks:
        if not isinstance(task, dict):
            continue
        planned_action = str(task.get("planned_action") or "review")
        if planned_action not in {"update", "create", "manual"}:
            continue
        task_name = task.get("task_name") or task.get("task_id") or "unknown_task"
        mapping = task.get("mapping_proof", {})
        if not isinstance(mapping, dict):
            mapping_failures.append(f"{task_name}: 缺少 mapping_proof")
            continue
        status = str(mapping.get("status", "unmapped")).lower()
        confidence = str(mapping.get("confidence", "low")).lower()
        flutter_entrypoints = mapping.get("flutter_entrypoints", [])
        native_chain = mapping.get("native_chain", [])
        evidence = mapping.get("evidence", [])
        if status != "mapped":
            mapping_failures.append(f"{task_name}: mapping_status={status}")
            continue
        if confidence not in {"high", "medium", "low"}:
            mapping_failures.append(f"{task_name}: mapping_confidence 无效")
        if not isinstance(flutter_entrypoints, list) or not [x for x in flutter_entrypoints if str(x).strip()]:
            mapping_failures.append(f"{task_name}: 缺少 flutter_entrypoints")
        if not isinstance(native_chain, list) or not [x for x in native_chain if str(x).strip()]:
            mapping_failures.append(f"{task_name}: 缺少 native_chain")
        if not isinstance(evidence, list) or not [x for x in evidence if str(x).strip()]:
            mapping_failures.append(f"{task_name}: 缺少 mapping_evidence")

    checks.append(
        {
            "id": "V7",
            "name": "映射证明",
            "result": "PASS" if not mapping_failures else "FAIL",
            "detail": "" if not mapping_failures else "; ".join(mapping_failures[:8]),
        }
    )

    pipeline_missing: list[str] = []
    artifact_missing: list[str] = []
    mapping_pipeline = {}
    if isinstance(llm_plan, dict):
        meta = llm_plan.get("meta", {})
        if isinstance(meta, dict):
            mp = meta.get("mapping_pipeline", {})
            if isinstance(mp, dict):
                mapping_pipeline = mp

    required_steps = ["capability_split", "flutter_hunk_extract", "flutter_chain_extract", "native_chain_match", "disambiguation"]
    for step in required_steps:
        value = mapping_pipeline.get(step)
        normalized = str(value).strip().lower()
        ok = value is True or normalized in {"done", "completed", "pass", "passed", "yes", "true"}
        if not ok:
            pipeline_missing.append(step)

    if not isinstance(llm_plan, dict) or not isinstance(llm_plan.get("hunk_facts"), (dict, list)) or not llm_plan.get("hunk_facts"):
        artifact_missing.append("hunk_facts")
    if not isinstance(llm_plan, dict) or not str(llm_plan.get("capability_slices", "")).strip():
        artifact_missing.append("capability_slices")
    if not isinstance(llm_plan, dict) or not isinstance(llm_plan.get("flutter_chain_map"), dict) or not llm_plan.get("flutter_chain_map"):
        artifact_missing.append("flutter_chain_map")
    if not isinstance(llm_plan, dict) or not isinstance(llm_plan.get("native_chain_candidates"), dict) or not llm_plan.get("native_chain_candidates"):
        artifact_missing.append("native_chain_candidates")
    if not isinstance(llm_plan, dict) or not str(llm_plan.get("mapping_disambiguation", "")).strip():
        artifact_missing.append("mapping_disambiguation")

    v8_failures = []
    if pipeline_missing:
        v8_failures.append("缺少流程步骤: " + ", ".join(pipeline_missing))
    if artifact_missing:
        v8_failures.append("缺少流程产物: " + ", ".join(artifact_missing))

    checks.append(
        {
            "id": "V8",
            "name": "自动映射流程完整性",
            "result": "PASS" if not v8_failures else "FAIL",
            "detail": "" if not v8_failures else "; ".join(v8_failures[:8]),
        }
    )

    v9_failures: list[str] = []
    for task in normalized_tasks:
        if not isinstance(task, dict):
            continue
        planned_action = str(task.get("planned_action") or "review")
        if planned_action not in {"update", "create", "manual"}:
            continue
        task_name = task.get("task_name") or task.get("task_id") or "unknown_task"
        landing = task.get("native_landing", {})
        mapping = task.get("mapping_proof", {})
        if not isinstance(landing, dict) or not isinstance(mapping, dict):
            v9_failures.append(f"{task_name}: 缺少 landing/mapping 结构")
            continue
        primary_path = str(landing.get("primary_path") or "")
        entry_kind = str(mapping.get("entry_kind") or "").strip().lower()
        reverse_trace = mapping.get("reverse_trace", [])
        evidence = mapping.get("evidence", [])
        has_orchestration_signal = (
            "controller" in primary_path.lower()
            or "coordinator" in primary_path.lower()
            or "manager" in primary_path.lower()
            or entry_kind == "orchestration_entry"
        )
        if not has_orchestration_signal:
            v9_failures.append(f"{task_name}: 主落点非编排入口（primary={primary_path or 'none'}）")
        if not isinstance(reverse_trace, list) or not [x for x in reverse_trace if str(x).strip()]:
            v9_failures.append(f"{task_name}: 缺少 reverse_trace")
        if not isinstance(evidence, list) or len([x for x in evidence if str(x).strip()]) < 2:
            v9_failures.append(f"{task_name}: 映射证据不足（<2）")

    checks.append(
        {
            "id": "V9",
            "name": "入口级映射真实性",
            "result": "PASS" if not v9_failures else "FAIL",
            "detail": "" if not v9_failures else "; ".join(v9_failures[:8]),
        }
    )

    v10_failures: list[str] = []
    repo_root = Path(str(contract.get("target", {}).get("repo_root", "") or ".")).resolve()
    for task in normalized_tasks:
        if not isinstance(task, dict):
            continue
        planned_action = str(task.get("planned_action") or "review")
        if planned_action not in {"update", "create", "manual"}:
            continue
        task_name = task.get("task_name") or task.get("task_id") or "unknown_task"
        lifecycle = str(task.get("trigger_lifecycle") or task.get("trigger_or_precondition") or "")
        mapping = task.get("mapping_proof", {})
        if not isinstance(mapping, dict):
            v10_failures.append(f"{task_name}: missing mapping_proof")
            continue
        native_chain = mapping.get("native_chain", [])
        evidence_lines = mapping.get("evidence_lines", [])
        chain_text = " ".join(str(x).lower() for x in native_chain) if isinstance(native_chain, list) else ""
        expected = lifecycle_expected_tokens(lifecycle)
        if expected and not any(token in chain_text for token in expected):
            v10_failures.append(f"{task_name}: lifecycle mismatch ({lifecycle})")
        ok_evidence, _ = validate_evidence_lines(repo_root, evidence_lines if isinstance(evidence_lines, list) else [])
        if not ok_evidence:
            v10_failures.append(f"{task_name}: evidence_lines 不可执行")

    checks.append(
        {
            "id": "V10",
            "name": "生命周期与证据可执行性",
            "result": "PASS" if not v10_failures else "FAIL",
            "detail": "" if not v10_failures else "; ".join(v10_failures[:8]),
        }
    )

    v11_failures: list[str] = []
    hunk_files = collect_hunk_files(llm_plan.get("hunk_facts") if isinstance(llm_plan, dict) else None)
    for task in normalized_tasks:
        if not isinstance(task, dict):
            continue
        planned_action = str(task.get("planned_action") or "review")
        if planned_action not in {"update", "create", "manual"}:
            continue
        if not is_popup_task(task):
            continue
        task_name = task.get("task_name") or task.get("task_id") or "unknown_task"
        mapping = task.get("mapping_proof", {})
        if not isinstance(mapping, dict):
            v11_failures.append(f"{task_name}: missing mapping_proof")
            continue
        native_chain = mapping.get("native_chain", [])
        first_chain = str(native_chain[0]) if isinstance(native_chain, list) and native_chain else ""
        entry_semantics = str(mapping.get("entry_semantics") or "").strip().lower()
        flutter_entrypoints = mapping.get("flutter_entrypoints", [])
        if entry_semantics != "popup_show":
            v11_failures.append(f"{task_name}: entry_semantics 必须为 popup_show")
        if not popup_entry_ok(first_chain):
            v11_failures.append(f"{task_name}: 首条 native_chain 不是 show/present 入口")
        if "didclick" in first_chain.lower() or "purchase(" in first_chain.lower():
            v11_failures.append(f"{task_name}: 首条 native_chain 误用点击/购买回调")
        if isinstance(flutter_entrypoints, list) and flutter_entrypoints:
            matched = any(str(item).strip() in hunk_files for item in flutter_entrypoints)
            if hunk_files and not matched:
                v11_failures.append(f"{task_name}: flutter_entrypoints 与 hunk_facts 未对齐")

    checks.append(
        {
            "id": "V11",
            "name": "弹窗入口语义约束",
            "result": "PASS" if not v11_failures else "FAIL",
            "detail": "" if not v11_failures else "; ".join(v11_failures[:8]),
        }
    )

    has_fail = any(item["result"] == "FAIL" for item in checks)
    has_warn = any(item["result"] == "WARN" for item in checks)
    if has_fail:
        conclusion = "FAIL"
    elif has_warn:
        conclusion = "WARN"
    else:
        conclusion = "PASS"

    return {
        "checks": checks,
        "conclusion": conclusion,
    }


def render_plan_validation(validation: dict) -> str:
    lines = [
        "# Plan Validation",
        "",
        "| # | 检查项 | 结果 | 说明 |",
        "|---|---|---|---|",
    ]
    for item in validation.get("checks", []):
        result = item.get("result", "UNKNOWN")
        icon = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "❌ FAIL"}.get(result, result)
        detail = (item.get("detail") or "").replace("|", "\\|")
        lines.append(f"| {item.get('id', '?')} | {item.get('name', '')} | {icon} | {detail} |")
    lines.extend(["", f"**结论：{validation.get('conclusion', 'UNKNOWN')}**"])
    return "\n".join(lines)


def render_flutter_changes_markdown(contract: dict) -> str:
    source = contract.get("source", {})
    flutter = contract.get("flutter_evidence", {})
    diff_files = flutter.get("key_files", [])
    lines = [
        "# Flutter Changes",
        "",
        "## 变更输入来源",
        "",
        f"- change_basis: {', '.join(source.get('change_basis', [])) or 'none'}",
        f"- flutter_paths: {', '.join(source.get('flutter_paths', [])) or 'none'}",
        f"- pr_diff_path: {source.get('pr_diff_path') or 'none'}",
        "",
        "## 关键变更证据",
        "",
    ]
    if diff_files:
        for item in diff_files[:20]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(["", "## 语义摘要", ""])
    screens = flutter.get("screens", [])
    api_calls = flutter.get("api_calls", [])
    models = flutter.get("models", [])
    lines.append(f"- screens: {', '.join(screens[:8]) if screens else 'none'}")
    lines.append(f"- api_calls: {', '.join(api_calls[:8]) if api_calls else 'none'}")
    lines.append(f"- models: {', '.join(models[:8]) if models else 'none'}")
    return "\n".join(lines)


def render_intent_markdown(contract: dict) -> str:
    requirement = contract.get("requirement", {})
    behavior = contract.get("behavior", {})
    lines = [
        f"# Intent: {requirement.get('name', 'unknown')}",
        "",
        "## 需求目标",
        "",
        f"- Requirement ID: `{requirement.get('id', 'unknown')}`",
        f"- 业务摘要: {requirement.get('summary', '')}",
        "",
        "## 用户价值与行为变化",
        "",
    ]
    user_flows = behavior.get("user_flows", [])
    acceptance_points = behavior.get("acceptance_points", [])
    interactions = behavior.get("interactions", [])
    if user_flows:
        lines.extend(f"- 用户流程: {item}" for item in user_flows)
    if acceptance_points:
        lines.extend(f"- 验收点: {item}" for item in acceptance_points)
    if interactions:
        lines.extend(f"- 关键交互: {item}" for item in interactions)
    if not any([user_flows, acceptance_points, interactions]):
        lines.append("- 暂无明确行为证据，请补充 Flutter 需求输入。")
    return "\n".join(lines)


def parse_feature_groups_from_prd(prd_path: str | None) -> list[str]:
    if not prd_path:
        return []
    path = Path(prd_path)
    if not path.exists() or not path.is_file():
        return []
    lines = read_text_safe(path).splitlines()
    groups: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("-"):
            continue
        if "http://" in line or "https://" in line:
            continue
        if line not in groups:
            groups.append(line)
    return groups


def classify_feature_group(path: str, ui_role: str, fallback_groups: list[str], component_counter: int) -> str:
    lower = path.lower()
    if ui_role == "primary_screen" or "unlock" in lower or "chapter" in lower:
        return "章节解锁页面" if "章节解锁页面" in fallback_groups else (fallback_groups[0] if fallback_groups else "章节解锁页面")
    if ui_role == "auxiliary_dialog" or any(token in lower for token in ["purchase", "buy", "vip"]):
        return "充值商品弹窗" if "充值商品弹窗" in fallback_groups else (fallback_groups[0] if fallback_groups else "充值商品弹窗")
    if ui_role == "auxiliary_overlay" or any(token in lower for token in ["retention", "retain", "overlay"]):
        return "充值挽留" if "充值挽留" in fallback_groups else (fallback_groups[0] if fallback_groups else "充值挽留")
    if ui_role == "component_view":
        if "引言样式" in fallback_groups and "引言更多" in fallback_groups:
            return "引言样式" if component_counter % 2 == 0 else "引言更多"
        if "引言样式" in fallback_groups:
            return "引言样式"
        if "引言更多" in fallback_groups:
            return "引言更多"
    return fallback_groups[0] if fallback_groups else "功能分组待确认"


def build_edit_tasks(contract: dict) -> list[dict]:
    requirement = contract.get("requirement", {})
    behavior = contract.get("behavior", {})
    patch_plan = contract.get("patch_plan", {})
    selected = contract.get("native_impact", {}).get("selected_touchpoints", [])
    source = contract.get("source", {})

    updates = set(patch_plan.get("update", []))
    creates = set(patch_plan.get("create", []))
    manuals = set(patch_plan.get("manual_candidates", []))

    feature_groups = parse_feature_groups_from_prd(source.get("prd_path"))
    if not feature_groups:
        feature_groups = [requirement.get("name", "功能分组")]

    grouped: dict[str, list[dict]] = {name: [] for name in feature_groups}
    component_counter = 0
    for item in selected:
        path = item.get("path", "")
        ui_role = item.get("ui_role", "non_ui")
        if ui_role == "component_view":
            component_counter += 1
        group_name = classify_feature_group(path, ui_role, feature_groups, component_counter)
        grouped.setdefault(group_name, []).append(item)

    tasks: list[dict] = []
    for idx, group_name in enumerate(feature_groups, start=1):
        touchpoints = grouped.get(group_name, [])
        touchpoint_paths = [item.get("path", "") for item in touchpoints if item.get("path")]

        planned_action = "review"
        if any(path in updates for path in touchpoint_paths):
            planned_action = "update"
        elif any(path in creates for path in touchpoint_paths):
            planned_action = "create"
        elif any(path in manuals for path in touchpoint_paths):
            planned_action = "manual"

        primary_path = touchpoint_paths[0] if touchpoint_paths else ""
        ui_roles = sorted({item.get("ui_role", "non_ui") for item in touchpoints})

        related_acceptance = [
            item
            for item in behavior.get("acceptance_points", [])
            if any(key in item for key in [group_name, "figma", "Figma", "http"])
        ]
        if not related_acceptance:
            related_acceptance = behavior.get("acceptance_points", [])[:3] or [f"{group_name} 与 Flutter 行为保持一致"]

        related_flows = [item for item in behavior.get("user_flows", []) if any(key in item for key in ["open", "unlock", "purchase", "retention", "intro"])]
        trigger = related_flows[0] if related_flows else f"触发 {group_name} 对应流程"

        tasks.append(
            {
                "task_id": f"G{idx:02d}",
                "task_name": f"功能组-{group_name}",
                "capability_goal": group_name,
                "trigger_or_precondition": trigger,
                "behavior_contract": {
                    "states": [state.get("name") for state in behavior.get("states", [])[:4] if state.get("name")],
                    "interactions": behavior.get("interactions", [])[:4],
                    "side_effects": behavior.get("side_effects", []),
                    "exceptions": ["异常场景需保持可回退与可观测"],
                },
                "native_landing": {
                    "primary_path": primary_path,
                    "touchpoint_count": len(touchpoints),
                    "ui_roles": ui_roles,
                    "touchpoints": [
                        {
                            "path": item.get("path", ""),
                            "kind": item.get("kind", "other"),
                            "ui_role": item.get("ui_role", "non_ui"),
                            "reason": item.get("reason", ""),
                            "source_screens": item.get("source_screens", []),
                        }
                        for item in touchpoints
                    ],
                },
                "edit_anchor": {
                    "target_file": primary_path,
                    "target_files": touchpoint_paths,
                    "class_or_symbol_hint": Path(primary_path).stem if primary_path else group_name,
                    "candidate_only": True,
                },
                "acceptance_assertions": related_acceptance,
                "execution_mode": "cli_direct_edit",
                "planned_action": planned_action,
            }
        )

    return tasks


def render_edit_tasks_markdown(tasks: list[dict]) -> str:
    lines = ["# Edit Tasks", "", "按功能分组组织，触点作为子项，类/方法仅为候选锚点。", ""]
    if not tasks:
        lines.extend(["- 无可执行任务", ""])
        return "\n".join(lines)

    for task in tasks:
        landing = task.get("native_landing", {})
        anchor = task.get("edit_anchor", {})
        contract = task.get("behavior_contract", {})
        mapping = task.get("mapping_proof", {})
        lines.extend(
            [
                f"## {task.get('task_id')} {task.get('task_name')}",
                "",
                f"- 功能域: `{task.get('feature_scope', '') or 'none'}`",
                f"- 触发生命周期: `{task.get('trigger_lifecycle', '') or 'none'}`",
                f"- 功能目标: {task.get('capability_goal', '')}",
                f"- 触发条件/前置条件: {task.get('trigger_or_precondition', '')}",
                f"- 主落点: `{landing.get('primary_path', '')}`",
                f"- 触点数量: `{landing.get('touchpoint_count', 0)}`",
                f"- UI 角色集合: `{', '.join(landing.get('ui_roles', [])) if landing.get('ui_roles') else 'none'}`",
                f"- 候选锚点: file=`{anchor.get('target_file', '')}` symbol_hint=`{anchor.get('class_or_symbol_hint', '')}`",
                f"- 计划动作: `{task.get('planned_action', 'review')}`",
                f"- 映射状态: `{mapping.get('status', 'unmapped')}` / confidence=`{mapping.get('confidence', 'low')}`",
                "",
                "### 触点子项",
                "",
            ]
        )
        touchpoints = landing.get("touchpoints", [])
        if touchpoints:
            for item in touchpoints:
                lines.append(
                    f"- `{item.get('path', '')}` | kind=`{item.get('kind', 'other')}` | ui_role=`{item.get('ui_role', 'non_ui')}`"
                )
        else:
            lines.append("- none")

        lines.extend(["", "### 行为契约", ""])
        states = contract.get("states", [])
        interactions = contract.get("interactions", [])
        side_effects = contract.get("side_effects", [])
        exceptions = contract.get("exceptions", [])
        logic_constraints = contract.get("logic_constraints", [])
        lines.append(f"- 状态: {', '.join(states) if states else 'none'}")
        lines.append(f"- 交互: {', '.join(interactions) if interactions else 'none'}")
        lines.append(f"- 副作用: {', '.join(side_effects) if side_effects else 'none'}")
        lines.append(f"- 异常: {', '.join(exceptions) if exceptions else 'none'}")
        lines.append(f"- 逻辑约束: {', '.join(logic_constraints) if logic_constraints else 'none'}")

        lines.extend(["", "### 映射证据链", ""])
        flutter_entrypoints = mapping.get("flutter_entrypoints", [])
        native_chain = mapping.get("native_chain", [])
        reverse_trace = mapping.get("reverse_trace", [])
        evidence_lines = mapping.get("evidence_lines", [])
        mapping_evidence = mapping.get("evidence", [])
        lines.append(f"- 入口类型: {mapping.get('entry_kind', 'unknown') or 'unknown'}")
        lines.append(f"- 入口语义: {mapping.get('entry_semantics', 'unknown') or 'unknown'}")
        if flutter_entrypoints:
            lines.extend(f"- Flutter 入口: {item}" for item in flutter_entrypoints[:8])
        else:
            lines.append("- Flutter 入口: none")
        if native_chain:
            lines.extend(f"- Native 链路: {item}" for item in native_chain[:8])
        else:
            lines.append("- Native 链路: none")
        if reverse_trace:
            lines.extend(f"- 反向回溯: {item}" for item in reverse_trace[:8])
        else:
            lines.append("- 反向回溯: none")
        if evidence_lines:
            lines.extend(f"- 证据行: {item}" for item in evidence_lines[:8])
        else:
            lines.append("- 证据行: none")
        if mapping_evidence:
            lines.extend(f"- 证据: {item}" for item in mapping_evidence[:8])
        else:
            lines.append("- 证据: none")

        lines.extend(["", "### 验收断言", ""])
        assertions = task.get("acceptance_assertions", [])
        if assertions:
            lines.extend(f"- {item}" for item in assertions)
        else:
            lines.append("- 无")
        lines.extend(["", "---", ""])

    return "\n".join(lines).rstrip() + "\n"


def render_execution_log_template(tasks: list[dict]) -> str:
    lines = [
        "# Execution Log",
        "",
        "由 CLI 直接改码后更新本日志。",
        "",
        "| task_id | status | touched_files | notes |",
        "|---|---|---|---|",
    ]
    for task in tasks:
        target = task.get("edit_anchor", {}).get("target_file", "")
        lines.append(f"| {task.get('task_id')} | pending | {target} | |")
    if not tasks:
        lines.append("| - | pending | - | no task |")
    return "\n".join(lines) + "\n"


def handle_plan(args: argparse.Namespace) -> int:
    inputs = build_inputs(args)
    validate_inputs(inputs)
    ensure_dir(inputs.run_dir)
    contract = build_contract(inputs)
    llm_plan = load_llm_plan(inputs.llm_resolution_path, inputs)
    touchpoints_text = llm_plan.get("native_touchpoints_markdown") if isinstance(llm_plan.get("native_touchpoints_markdown"), str) else render_touchpoints(contract)
    risk_text = llm_plan.get("risk_report_markdown") if isinstance(llm_plan.get("risk_report_markdown"), str) else render_risk_report(contract)
    llm_tasks = llm_plan.get("tasks", [])
    tasks = [normalize_llm_task(task, index + 1) for index, task in enumerate(llm_tasks) if isinstance(task, dict)]
    if not tasks:
        raise ValueError("llm plan tasks cannot be empty after normalization")
    intent_text = llm_plan.get("intent_markdown") if isinstance(llm_plan.get("intent_markdown"), str) else render_intent_markdown(contract)
    edit_tasks_text = render_edit_tasks_markdown(tasks)

    write_text(inputs.run_dir / FLUTTER_CHANGES_FILE, render_flutter_changes_markdown(contract))
    write_text(inputs.run_dir / INTENT_MARKDOWN_FILE, intent_text)
    write_text(inputs.run_dir / HUNK_FACTS_FILE, json.dumps(llm_plan.get("hunk_facts"), ensure_ascii=False, indent=2) + "\n")
    write_text(inputs.run_dir / EDIT_TASKS_JSON_FILE, json.dumps(tasks, ensure_ascii=False, indent=2) + "\n")
    write_text(inputs.run_dir / EDIT_TASKS_MARKDOWN_FILE, edit_tasks_text)
    write_text(inputs.run_dir / NATIVE_TOUCHPOINTS_FILE, touchpoints_text)
    write_text(inputs.run_dir / "risk_report.md", risk_text)
    write_text(inputs.run_dir / EXECUTION_LOG_FILE, render_execution_log_template(tasks))

    validation = build_plan_validation(contract, edit_tasks_text, tasks=tasks, llm_plan=llm_plan)
    if isinstance(llm_plan.get("plan_validation"), dict):
        pv = llm_plan.get("plan_validation")
        checks = pv.get("checks", [])
        conclusion = pv.get("conclusion")
        if isinstance(checks, list) and isinstance(conclusion, str) and checks:
            validation = {"checks": checks, "conclusion": conclusion}
    write_text(inputs.run_dir / PLAN_VALIDATION_FILE, render_plan_validation(validation))

    print("Planning artifacts generated.")
    print(f"- run_dir: {inputs.run_dir}")
    print(f"- tasks: {len(tasks)}")
    print(f"- plan_validation: {validation['conclusion']}")
    if validation["conclusion"] == "FAIL":
        print("Plan validation failed. Please refine inputs and rerun planner.", file=sys.stderr)
        return 2
    return 0


def handle_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        print("Run status: missing")
        return 0
    expected = [
        PLAN_VALIDATION_FILE,
        FLUTTER_CHANGES_FILE,
        NATIVE_TOUCHPOINTS_FILE,
        "risk_report.md",
        INTENT_MARKDOWN_FILE,
        EDIT_TASKS_MARKDOWN_FILE,
        EDIT_TASKS_JSON_FILE,
        EXECUTION_LOG_FILE,
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
        import traceback; traceback.print_exc(file=sys.stderr)
        print(f"atlas-planner error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
