#!/usr/bin/env python3
"""plan.py — T2N Atlas 第二步：读取功能意图，加载原生画像，生成 sync_plan.md。

流程：
1. 读取 feature_intent.md（由 digest_flutter.py 生成）
2. 读取 native-profile/overview.md（了解模块/子功能索引）
3. LLM 根据功能意图，从 overview.md 中识别相关的业务子功能模块
4. 加载对应的 native-profile/modules/<module>/<sub-feature>.md 文件（按需加载）
5. LLM 读取相关原生目标文件的实际内容（获取调用链上下文）
6. LLM 生成 sync_plan.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


OUTPUT_FILE = "sync_plan.md"
FEATURE_INTENT_FILE = "feature_intent.md"
OVERVIEW_FILE = "overview.md"
MODULES_DIR = "modules"


# ---------------------------------------------------------------------------
# 文件读取工具
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    """读取文件内容，优先 UTF-8，降级 latin-1。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def write_text(path: Path, content: str) -> None:
    """写入文件，使用 UTF-8 编码，结尾保留一个换行。"""
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Claude API 调用
# ---------------------------------------------------------------------------

def call_llm(prompt: str, max_tokens: int = 8096) -> str:
    """调用 Claude API，返回文本响应。"""
    import anthropic  # 延迟导入，避免在未安装时影响 --help

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# 步骤 3：让 LLM 从 overview.md 识别相关模块
# ---------------------------------------------------------------------------

def build_module_selection_prompt(feature_intent: str, overview: str) -> str:
    return "\n".join([
        "# T2N Atlas — 模块识别",
        "",
        "你是一名 iOS 原生开发架构师，正在分析一份功能意图文档，需要从原生项目画像索引中",
        "挑选出与该功能相关的模块和子功能文件。",
        "",
        "## 功能意图",
        "",
        feature_intent.strip(),
        "",
        "## 原生项目画像索引（overview.md）",
        "",
        overview.strip(),
        "",
        "## 任务",
        "",
        "请列出所有与上述功能意图相关的模块子功能文件路径（相对于 native-profile/ 目录）。",
        "格式要求：仅返回 JSON 数组，每个元素是一个相对路径字符串，例如：",
        "",
        '["modules/Reader/reading_complete.md", "modules/Shelf/shelf_refresh.md"]',
        "",
        "要求：",
        "- 只列出确实相关的文件，不要过度扩展",
        "- 支持跨模块（一个功能可能涉及多个模块）",
        "- 如果 overview.md 中没有明确的子功能文件路径，则根据模块名称推断合理路径",
        "- 如果确实没有相关模块，返回空数组 []",
        "",
        "只输出 JSON 数组，不要附加任何解释文字。",
    ])


def parse_file_list_from_llm(text: str) -> list[str]:
    """从 LLM 响应中提取 JSON 数组形式的文件路径列表。"""
    stripped = text.strip()
    # 尝试直接解析
    try:
        result = json.loads(stripped)
        if isinstance(result, list):
            return [str(p).strip() for p in result if str(p).strip()]
    except json.JSONDecodeError:
        pass
    # 从文本中提取第一个 JSON 数组
    match = re.search(r"\[.*?\]", stripped, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return [str(p).strip() for p in result if str(p).strip()]
        except json.JSONDecodeError:
            pass
    return []


# ---------------------------------------------------------------------------
# 步骤 5：让 LLM 确定需要读取哪些原生源文件
# ---------------------------------------------------------------------------

def build_file_selection_prompt(
    feature_intent: str,
    module_profiles: dict[str, str],
    native_root: Path,
) -> str:
    module_sections = []
    for rel_path, content in module_profiles.items():
        module_sections.append(f"### {rel_path}\n\n{content.strip()}")

    return "\n".join([
        "# T2N Atlas — 原生目标文件识别",
        "",
        "你是一名 iOS 原生开发架构师，正在根据功能意图和模块画像，",
        "确定需要读取哪些原生源文件的实际内容（以便后续生成精确的修改计划）。",
        "",
        "## 功能意图",
        "",
        feature_intent.strip(),
        "",
        "## 相关模块画像",
        "",
        "\n\n".join(module_sections) if module_sections else "（无相关模块画像）",
        "",
        f"## 原生项目根目录",
        "",
        str(native_root),
        "",
        "## 任务",
        "",
        "请列出所有需要查阅实际内容的原生源文件路径（相对于原生项目根目录）。",
        "这些文件将被读取，让你看到真实的调用链和代码结构。",
        "",
        "格式要求：仅返回 JSON 数组，每个元素是相对于原生项目根目录的路径字符串，例如：",
        "",
        '["Sources/Reader/ReaderViewController.swift", "Sources/Shelf/ShelfViewModel.swift"]',
        "",
        "要求：",
        "- 只列出真正需要查阅的文件，不要过度扩展",
        "- 路径来自模块画像中列出的文件",
        "- 如果没有需要查阅的文件，返回空数组 []",
        "",
        "只输出 JSON 数组，不要附加任何解释文字。",
    ])


# ---------------------------------------------------------------------------
# 步骤 6：生成 sync_plan.md
# ---------------------------------------------------------------------------

def build_plan_prompt(
    feature_intent: str,
    module_profiles: dict[str, str],
    native_file_contents: dict[str, str],
) -> str:
    module_sections = []
    for rel_path, content in module_profiles.items():
        module_sections.append(f"### 模块画像：{rel_path}\n\n{content.strip()}")

    file_sections = []
    for rel_path, content in native_file_contents.items():
        file_sections.append(f"### 原生文件：{rel_path}\n\n```swift\n{content.strip()}\n```")

    return "\n".join([
        "# T2N Atlas — 生成原生修改计划",
        "",
        "你是一名资深 iOS 原生开发工程师，正在为一个功能需求生成原生代码修改计划。",
        "该计划将提供给工程师审查，再决定是否执行。",
        "",
        "## 功能意图",
        "",
        feature_intent.strip(),
        "",
        "## 相关模块画像",
        "",
        "\n\n".join(module_sections) if module_sections else "（无相关模块画像）",
        "",
        "## 原生目标文件实际内容",
        "",
        "\n\n".join(file_sections) if file_sections else "（无目标文件内容）",
        "",
        "## 任务",
        "",
        "请生成一份 sync_plan.md，格式如下：",
        "",
        "- 按功能分节，每节以 `## 功能 N：<功能名>` 开头",
        "- 每节列出涉及的模块（`涉及模块：ModuleA、ModuleB`）",
        "- 每个模块下列出受影响的文件，及该文件的具体类/方法变更",
        "  - 新增方法用 `- 新增 \`methodName()\``",
        "  - 修改方法用 `- 修改 \`methodName()\` — <说明>`",
        "- 如需新增文件，在该功能节末尾用 `### 新增文件` 小节列出",
        "- 节与节之间用 `---` 分隔",
        "",
        "要求：",
        "- 计划粒度到类和方法级别",
        "- 跨模块功能在同一节内展示所有模块的修改",
        "- 基于实际代码内容给出精确的方法签名",
        "- 语言使用中文",
        "",
        "直接输出 Markdown 内容，不要附加任何前言或结尾说明。",
    ])


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run(run_dir: Path, profile_dir: Path, native_root: Path) -> int:
    # 步骤 1：读取 feature_intent.md
    intent_path = run_dir / FEATURE_INTENT_FILE
    if not intent_path.exists():
        print(f"错误：feature_intent.md 不存在：{intent_path}", file=sys.stderr)
        return 3
    print(f"[1/5] 读取功能意图：{intent_path}")
    feature_intent = read_text(intent_path)

    # 步骤 2：读取 native-profile/overview.md
    overview_path = profile_dir / OVERVIEW_FILE
    if not overview_path.exists():
        print(f"错误：overview.md 不存在：{overview_path}", file=sys.stderr)
        return 3
    print(f"[2/5] 读取原生画像索引：{overview_path}")
    overview = read_text(overview_path)

    # 步骤 3：LLM 识别相关模块文件
    print("[3/5] LLM 分析功能意图，识别相关模块文件...")
    module_selection_prompt = build_module_selection_prompt(feature_intent, overview)
    module_files_response = call_llm(module_selection_prompt, max_tokens=1024)
    module_rel_paths = parse_file_list_from_llm(module_files_response)
    print(f"      识别到相关模块文件 {len(module_rel_paths)} 个：")
    for p in module_rel_paths:
        print(f"      - {p}")

    # 步骤 4：加载对应的模块子功能画像文件（按需加载）
    module_profiles: dict[str, str] = {}
    for rel_path in module_rel_paths:
        full_path = profile_dir / rel_path
        if full_path.exists():
            module_profiles[rel_path] = read_text(full_path)
            print(f"      已加载：{rel_path}")
        else:
            print(f"      警告：文件不存在，跳过：{full_path}")

    # 步骤 5：LLM 确定需要读取哪些原生源文件，并读取实际内容
    print("[4/5] LLM 识别需要查阅的原生源文件...")
    file_selection_prompt = build_file_selection_prompt(
        feature_intent, module_profiles, native_root
    )
    native_files_response = call_llm(file_selection_prompt, max_tokens=1024)
    native_rel_paths = parse_file_list_from_llm(native_files_response)
    print(f"      识别到目标源文件 {len(native_rel_paths)} 个：")
    for p in native_rel_paths:
        print(f"      - {p}")

    native_file_contents: dict[str, str] = {}
    for rel_path in native_rel_paths:
        full_path = native_root / rel_path
        if full_path.exists():
            native_file_contents[rel_path] = read_text(full_path)
            print(f"      已读取：{rel_path} ({len(native_file_contents[rel_path])} 字节)")
        else:
            print(f"      警告：原生文件不存在，跳过：{full_path}")

    # 步骤 6：LLM 生成 sync_plan.md
    print("[5/5] LLM 生成 sync_plan.md...")
    plan_prompt = build_plan_prompt(feature_intent, module_profiles, native_file_contents)
    sync_plan_text = call_llm(plan_prompt, max_tokens=8096)

    # 写入输出文件
    output_path = run_dir / OUTPUT_FILE
    write_text(output_path, sync_plan_text)
    print(f"\n完成！sync_plan.md 已写入：{output_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "T2N Atlas plan — 读取功能意图和原生项目画像，生成原生修改计划 sync_plan.md。"
            "这是每次需求迁移的第二步（在 digest_flutter.py 之后）。"
        )
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="本次运行目录，包含 feature_intent.md，sync_plan.md 将输出到此目录",
    )
    parser.add_argument(
        "--profile-dir",
        help=(
            "native-profile 目录（默认：<native-root>/.ai/t2n/native-profile）。"
            "需包含 overview.md 和 modules/ 子目录。"
        ),
    )
    parser.add_argument(
        "--native-root",
        help="原生项目根目录（用于读取目标文件实际内容）",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        print(f"错误：run-dir 不存在或不是目录：{run_dir}", file=sys.stderr)
        return 3

    # 解析 native-root
    if args.native_root:
        native_root = Path(args.native_root).expanduser().resolve()
    else:
        native_root = Path(".").resolve()
        print(f"警告：未指定 --native-root，使用当前目录：{native_root}", file=sys.stderr)

    if not native_root.exists() or not native_root.is_dir():
        print(f"错误：native-root 不存在或不是目录：{native_root}", file=sys.stderr)
        return 3

    # 解析 profile-dir
    if args.profile_dir:
        profile_dir = Path(args.profile_dir).expanduser().resolve()
    else:
        profile_dir = native_root / ".ai" / "t2n" / "native-profile"
        print(f"信息：--profile-dir 未指定，使用默认路径：{profile_dir}")

    if not profile_dir.exists() or not profile_dir.is_dir():
        print(f"错误：profile-dir 不存在或不是目录：{profile_dir}", file=sys.stderr)
        return 3

    try:
        return run(run_dir, profile_dir, native_root)
    except KeyboardInterrupt:
        print("\n中断。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"plan.py 错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
