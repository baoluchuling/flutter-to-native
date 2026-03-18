#!/usr/bin/env python3
"""digest_flutter.py — T2N Atlas step 1: distil feature intent from a Flutter diff.

Reads a Flutter git diff (required) and optional supplementary documents
(PRD, design specs, etc.), then asks Claude to produce a human-readable
feature_intent.md written in business language.

Usage
-----
python3 scripts/digest_flutter.py \
    --diff /path/to/flutter.diff \
    --run-dir /path/to/.ai/t2n/runs/2026-03-16-feature-foo \
    [--prd /path/to/prd.md] \
    [--extra /path/to/doc1.md /path/to/doc2.md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic


# Maximum diff size before we warn and truncate (bytes).
DIFF_SIZE_WARN_BYTES = 80 * 1024  # 80 KB
# Hard cap sent to the model (characters); keeps total prompt reasonable.
DIFF_CHAR_LIMIT = 60_000
# Cap per supplementary document (characters).
EXTRA_CHAR_LIMIT = 8_000

OUTPUT_FILE = "feature_intent.md"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8096


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_text(path: Path) -> str:
    """Read a file, falling back to latin-1 on UTF-8 errors."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def load_diff(diff_path: Path) -> str:
    """Load diff file, warn and truncate if it is too large."""
    if not diff_path.exists():
        raise FileNotFoundError(f"diff file not found: {diff_path}")

    raw = read_text(diff_path)
    byte_size = len(raw.encode("utf-8", errors="replace"))

    if byte_size > DIFF_SIZE_WARN_BYTES:
        print(
            f"[warn] diff is large ({byte_size / 1024:.0f} KB > "
            f"{DIFF_SIZE_WARN_BYTES // 1024} KB); content will be truncated for the LLM."
        )

    if len(raw) > DIFF_CHAR_LIMIT:
        raw = raw[:DIFF_CHAR_LIMIT]
        raw += "\n\n[... diff truncated due to size limit ...]"

    return raw


def load_optional_doc(path: Path, label: str) -> str:
    """Load an optional supplementary document, truncating if necessary."""
    if not path.exists():
        print(f"[warn] {label} not found, skipping: {path}", file=sys.stderr)
        return ""
    text = read_text(path)
    if len(text) > EXTRA_CHAR_LIMIT:
        text = text[:EXTRA_CHAR_LIMIT] + "\n\n[... truncated ...]"
    return text


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_prompt(diff_text: str, prd_text: str, extra_texts: list[tuple[str, str]]) -> str:
    """Assemble the LLM prompt from all available inputs."""
    sections: list[str] = []

    sections.append(
        "你是一名资深产品经理，擅长从代码变更中提炼业务功能意图。\n"
        "你的任务是阅读下面提供的 Flutter 代码 diff，结合补充材料（如 PRD、设计文档），\n"
        "用**业务语言**（非技术语言）描述本次变更实现了哪些功能。\n\n"
        "要求：\n"
        "- 每个独立功能单独一节，用 `## 功能 N：<功能名>` 作为标题。\n"
        "- 每节包含以下子标题：`### 业务描述`、`### 涉及数据变更`、`### 涉及交互`、`### 副作用`。\n"
        "- **禁止**出现文件名、类名、方法名等技术细节；只描述用户可感知的业务行为。\n"
        "- 如果多个代码变更共同实现同一个业务功能，合并为一节描述。\n"
        "- 节与节之间用 `---` 分隔。\n"
        "- 直接输出 Markdown，不要有任何前言或后记。"
    )

    if prd_text:
        sections.append(
            "---\n\n## 补充材料：PRD 文档\n\n"
            "以下 PRD 仅供参考，Flutter diff 是最权威的功能依据。\n\n"
            f"{prd_text}"
        )

    for label, text in extra_texts:
        if text:
            sections.append(
                f"---\n\n## 补充材料：{label}\n\n{text}"
            )

    sections.append(
        "---\n\n## Flutter Diff（最权威依据）\n\n"
        "```diff\n"
        f"{diff_text}\n"
        "```"
    )

    sections.append(
        "---\n\n请根据以上材料，按要求输出 `feature_intent.md` 的完整内容。"
    )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def call_llm(prompt: str) -> str:
    """Send prompt to Claude and return the response text."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
    print(f"[info] calling Claude ({MODEL}), max_tokens={MAX_TOKENS} …")
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "T2N Atlas — step 1: digest Flutter diff and produce feature_intent.md "
            "using Claude."
        )
    )
    parser.add_argument(
        "--diff",
        required=True,
        metavar="PATH",
        help="Path to the Flutter git diff file (required).",
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        metavar="DIR",
        help="Working directory for this migration run; created if absent.",
    )
    parser.add_argument(
        "--prd",
        metavar="PATH",
        default=None,
        help="Optional PRD document path for additional context.",
    )
    parser.add_argument(
        "--extra",
        nargs="+",
        metavar="PATH",
        default=[],
        help="Optional list of additional supplementary document paths.",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    diff_path = Path(args.diff).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()

    # Ensure run directory exists.
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[info] run_dir: {run_dir}")

    # Load required diff.
    print(f"[info] loading diff: {diff_path}")
    try:
        diff_text = load_diff(diff_path)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    diff_lines = diff_text.count("\n")
    print(f"[info] diff loaded: {len(diff_text)} chars, ~{diff_lines} lines")

    # Load optional PRD.
    prd_text = ""
    if args.prd:
        prd_path = Path(args.prd).expanduser().resolve()
        print(f"[info] loading PRD: {prd_path}")
        prd_text = load_optional_doc(prd_path, "PRD")

    # Load optional extra documents.
    extra_texts: list[tuple[str, str]] = []
    for raw_extra in args.extra:
        extra_path = Path(raw_extra).expanduser().resolve()
        label = extra_path.name
        print(f"[info] loading extra doc: {extra_path}")
        text = load_optional_doc(extra_path, label)
        extra_texts.append((label, text))

    # Build prompt.
    print("[info] building prompt …")
    prompt = build_prompt(diff_text, prd_text, extra_texts)
    print(f"[info] prompt length: {len(prompt)} chars")

    # Call LLM.
    try:
        result_text = call_llm(prompt)
    except Exception as exc:
        print(f"LLM call failed: {exc}", file=sys.stderr)
        return 1

    # Write output.
    output_path = run_dir / OUTPUT_FILE
    output_path.write_text(result_text, encoding="utf-8")
    print(f"[info] feature_intent.md written: {output_path}")
    print(f"[info] output length: {len(result_text)} chars")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
