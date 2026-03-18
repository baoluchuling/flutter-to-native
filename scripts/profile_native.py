#!/usr/bin/env python3
"""profile_native.py — One-shot native iOS architecture profiler for T2N Atlas.

Scans a native iOS project and produces a reusable architecture profile under
<native-repo-root>/.ai/t2n/native-profile/ (or a custom --output-dir).

Steps:
  1. Static scan  — extract manifest from .swift files (zero LLM calls).
  2. LLM pass 1  — read manifest → generate overview.md and modules/<m>/<sf>.md.
  3. LLM pass 2  — sample 2-3 representative files → generate conventions.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8096

# Directories to skip during scanning
IGNORE_DIR_NAMES = {
    ".git",
    "Pods",
    "Carthage",
    "DerivedData",
    "build",
    ".build",
    "Tests",
    "tests",
}

# Manifest size threshold (bytes) above which we batch by directory
MANIFEST_BATCH_THRESHOLD = 50_000

# How many representative files to sample for conventions analysis
CONVENTIONS_SAMPLE_COUNT = 3

# Suffixes that help us pick representative files for conventions
REPRESENTATIVE_SUFFIXES = ("ViewController", "ViewModel", "Service", "Manager", "Repository")


# ---------------------------------------------------------------------------
# Step 1 — Static manifest extraction
# ---------------------------------------------------------------------------

def _should_skip(rel: Path) -> bool:
    """Return True if this path should be excluded from scanning."""
    for part in rel.parts:
        if part in IGNORE_DIR_NAMES:
            return True
    return False


def _collect_swift_files(repo_root: Path) -> list[Path]:
    """Return sorted list of .swift files under repo_root, skipping ignored dirs."""
    files: list[Path] = []
    for path in sorted(repo_root.rglob("*.swift")):
        rel = path.relative_to(repo_root)
        if _should_skip(rel):
            continue
        files.append(path)
    return files


# Regex patterns for manifest extraction
_TYPE_PATTERN = re.compile(
    r"^\s*(?:(?:public|open|internal|private|fileprivate)\s+)*"
    r"(?:final\s+)?"
    r"(class|struct|enum|protocol)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
_FUNC_PATTERN = re.compile(
    r"^\s*(?:(?:public|open|internal|private|fileprivate|override|static|class|mutating|required)\s+)*"
    r"func\s+([A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)(?:\s*->\s*[^\{]+)?)",
    re.MULTILINE,
)


def _extract_file_manifest(repo_root: Path, abs_path: Path) -> str:
    """Return manifest text for one file (header + type + method lines)."""
    try:
        text = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = abs_path.read_text(encoding="latin-1")

    rel = abs_path.relative_to(repo_root).as_posix()
    lines: list[str] = [rel]

    # Find all top-level types
    type_matches = list(_TYPE_PATTERN.finditer(text))
    if not type_matches:
        return ""  # skip files with no recognisable types

    for i, type_match in enumerate(type_matches):
        keyword = type_match.group(1)
        name = type_match.group(2)
        # Build a simple "class Foo: Bar" line
        full_line = type_match.group(0).strip()
        # Normalise whitespace in the signature
        full_line = re.sub(r"\s+", " ", full_line)
        lines.append(f"  {full_line}")

        # Determine body range for this type
        body_start = type_match.end()
        body_end = type_matches[i + 1].start() if i + 1 < len(type_matches) else len(text)
        body = text[body_start:body_end]

        # Extract func signatures inside body
        for func_match in _FUNC_PATTERN.finditer(body):
            sig = re.sub(r"\s+", " ", func_match.group(1).strip())
            lines.append(f"    func {sig}")

    return "\n".join(lines)


def build_manifest(repo_root: Path) -> tuple[str, list[Path]]:
    """Scan repo and return (manifest_text, swift_files).

    manifest_text is the full manifest for all files that have recognisable types.
    swift_files is the complete list of scanned .swift files.
    """
    print("[Step 1] Scanning Swift files ...")
    swift_files = _collect_swift_files(repo_root)
    print(f"  Found {len(swift_files)} .swift files (after ignoring excluded dirs)")

    file_sections: list[str] = []
    for path in swift_files:
        section = _extract_file_manifest(repo_root, path)
        if section:
            file_sections.append(section)

    manifest = "\n\n".join(file_sections)
    print(f"  Manifest size: {len(manifest.encode('utf-8'))} bytes, {len(file_sections)} files with types")
    return manifest, swift_files


# ---------------------------------------------------------------------------
# Step 2 — LLM: manifest → overview.md + modules/
# ---------------------------------------------------------------------------

def _chunk_manifest(manifest: str, threshold: int) -> list[str]:
    """Split manifest into chunks ≤ threshold bytes, splitting on file boundaries."""
    encoded = manifest.encode("utf-8")
    if len(encoded) <= threshold:
        return [manifest]

    # Split on double newlines (file boundaries in the manifest)
    sections = manifest.split("\n\n")
    chunks: list[str] = []
    current_parts: list[str] = []
    current_size = 0

    for section in sections:
        size = len(section.encode("utf-8")) + 2  # +2 for "\n\n"
        if current_size + size > threshold and current_parts:
            chunks.append("\n\n".join(current_parts))
            current_parts = [section]
            current_size = size
        else:
            current_parts.append(section)
            current_size += size

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks


def _call_llm(client: anthropic.Anthropic, prompt: str) -> str:
    """Call Claude API and return the text response."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


_OVERVIEW_PROMPT_TEMPLATE = """\
You are an expert iOS architect. Below is a manifest extracted from a native iOS project.
Each entry shows a file path, followed by the types (class/struct/enum/protocol) defined in it
and their method signatures.

Your task is to analyse this manifest and produce a structured architecture overview in Markdown.

## Output format

Produce ONLY valid Markdown (no extra commentary outside the Markdown).

### Required sections

1. **Architecture Pattern** — identify the dominant pattern (MVVM, MVC, VIPER, Clean Architecture, etc.)
   and briefly justify your choice based on what you see.

2. **Business Modules** — group files by business domain (NOT by technical layer like "ViewModels" or
   "Services"). Each module entry must include:
   - Module name (as a `##` heading)
   - One-sentence description
   - Sub-features table: | Sub-feature | Files |

Use concise language. Do not invent information not implied by the manifest.

## Manifest

{manifest}
"""

_MODULES_PROMPT_TEMPLATE = """\
You are an expert iOS architect. Below is a manifest extracted from a native iOS project.

Your task: for each business sub-feature you identify, produce a **separate fenced block** in the
following format (one block per sub-feature):

```yaml
module: <module_slug>          # snake_case, e.g. reader
sub_feature: <sub_feature_slug> # snake_case, e.g. reading_page
title: <Human Readable Title>
description: <one sentence describing what this sub-feature does>
files:
  - path: <relative/path/to/file.swift>
    classes:
      - name: <ClassName>
        responsibility: <one short sentence>
```

Produce ONLY the fenced YAML blocks, nothing else.

## Manifest

{manifest}
"""


def generate_overview_and_modules(client: anthropic.Anthropic, manifest: str, output_dir: Path) -> None:
    """Generate overview.md and modules/<module>/<sub_feature>.md from manifest."""
    print("[Step 2] Generating overview.md ...")

    chunks = _chunk_manifest(manifest, MANIFEST_BATCH_THRESHOLD)
    if len(chunks) > 1:
        print(f"  Manifest is large; processing in {len(chunks)} chunks")

    # ---- overview.md ----
    # For overview, summarise each chunk then combine if multiple
    if len(chunks) == 1:
        overview_text = _call_llm(client, _OVERVIEW_PROMPT_TEMPLATE.format(manifest=chunks[0]))
    else:
        part_overviews: list[str] = []
        for idx, chunk in enumerate(chunks, 1):
            print(f"  Overview chunk {idx}/{len(chunks)} ...")
            part_text = _call_llm(client, _OVERVIEW_PROMPT_TEMPLATE.format(manifest=chunk))
            part_overviews.append(part_text)
        # Merge partial overviews
        merge_prompt = (
            "You are an expert iOS architect. Below are partial architecture overviews generated from "
            "different portions of the same iOS project manifest.\n\n"
            "Merge them into a single coherent overview following the same format "
            "(Architecture Pattern section + Business Modules section). "
            "Remove duplicates and reconcile any conflicts. Produce ONLY valid Markdown.\n\n"
            "## Partial Overviews\n\n"
            + "\n\n---\n\n".join(part_overviews)
        )
        overview_text = _call_llm(client, merge_prompt)

    overview_path = output_dir / "overview.md"
    overview_path.write_text(overview_text, encoding="utf-8")
    print(f"  Written: {overview_path}")

    # ---- modules/<module>/<sub_feature>.md ----
    print("[Step 2] Generating module sub-feature files ...")

    all_yaml_blocks: list[str] = []
    for idx, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            print(f"  Module chunks {idx}/{len(chunks)} ...")
        raw = _call_llm(client, _MODULES_PROMPT_TEMPLATE.format(manifest=chunk))
        # Extract fenced ```yaml ... ``` blocks
        found = re.findall(r"```yaml\s*(.*?)```", raw, re.DOTALL)
        all_yaml_blocks.extend(found)

    print(f"  Found {len(all_yaml_blocks)} sub-feature blocks from LLM")

    modules_dir = output_dir / "modules"
    written_count = 0
    for block in all_yaml_blocks:
        meta = _parse_simple_yaml(block)
        module_slug = _safe_slug(meta.get("module", "misc"))
        sf_slug = _safe_slug(meta.get("sub_feature", "general"))
        title = meta.get("title", sf_slug.replace("_", " ").title())
        description = meta.get("description", "")
        files_raw = meta.get("files", [])

        # Build markdown content
        md_lines: list[str] = [
            f"# {title}",
            "",
            f"{description}",
            "",
            "## Files",
            "",
        ]
        if isinstance(files_raw, list):
            for file_entry in files_raw:
                if not isinstance(file_entry, dict):
                    continue
                file_path = file_entry.get("path", "")
                md_lines.append(f"### `{file_path}`")
                md_lines.append("")
                classes = file_entry.get("classes", [])
                if isinstance(classes, list):
                    for cls in classes:
                        if not isinstance(cls, dict):
                            continue
                        cls_name = cls.get("name", "")
                        cls_resp = cls.get("responsibility", "")
                        md_lines.append(f"- **{cls_name}** — {cls_resp}")
                md_lines.append("")

        sf_dir = modules_dir / module_slug
        sf_dir.mkdir(parents=True, exist_ok=True)
        sf_path = sf_dir / f"{sf_slug}.md"
        sf_path.write_text("\n".join(md_lines), encoding="utf-8")
        written_count += 1

    print(f"  Written {written_count} module sub-feature files under {modules_dir}")


# ---------------------------------------------------------------------------
# Step 3 — LLM: sample files → conventions.md
# ---------------------------------------------------------------------------

def _pick_sample_files(swift_files: list[Path], repo_root: Path, n: int) -> list[Path]:
    """Pick up to n representative files from the scanned set.

    Preference order: ViewController, ViewModel, Service/Manager/Repository.
    Fill remainder with any file not already selected.
    """
    picked: list[Path] = []
    used: set[Path] = set()

    for suffix in REPRESENTATIVE_SUFFIXES:
        if len(picked) >= n:
            break
        for path in swift_files:
            if path.stem.endswith(suffix) and path not in used:
                picked.append(path)
                used.add(path)
                break  # one per suffix category

    # Fill with remaining files if needed
    for path in swift_files:
        if len(picked) >= n:
            break
        if path not in used:
            picked.append(path)
            used.add(path)

    return picked[:n]


_CONVENTIONS_PROMPT_TEMPLATE = """\
You are an expert iOS architect reviewing real Swift source files.

Analyse the files below and produce a **conventions.md** for this project in Markdown.

## Required sections

1. **Naming Conventions** — classes, methods, variables (patterns you observe).
2. **Key Libraries & Usage Patterns** — list every significant third-party library
   (SnapKit, Moya, RxSwift, Combine, Alamofire, etc.) you detect and describe
   how it is typically used in this codebase.
3. **Dependency Injection** — how are dependencies provided (constructor injection,
   property injection, service locator, singletons, etc.)?
4. **Other Idioms** — any recurring patterns (delegates, closures, generics usage,
   error handling style, async/await vs. callbacks, etc.).

Produce ONLY valid Markdown. Be concise and precise.

## Source Files

{files_content}
"""


def generate_conventions(client: anthropic.Anthropic, swift_files: list[Path], repo_root: Path, output_dir: Path) -> None:
    """Sample a few files and generate conventions.md."""
    print("[Step 3] Sampling files for conventions analysis ...")
    sample = _pick_sample_files(swift_files, repo_root, CONVENTIONS_SAMPLE_COUNT)
    if not sample:
        print("  No .swift files to sample; skipping conventions.md")
        return

    files_content_parts: list[str] = []
    for path in sample:
        rel = path.relative_to(repo_root).as_posix()
        print(f"  Sampling: {rel}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        files_content_parts.append(f"### {rel}\n\n```swift\n{text}\n```")

    files_content = "\n\n".join(files_content_parts)
    prompt = _CONVENTIONS_PROMPT_TEMPLATE.format(files_content=files_content)

    print("  Calling LLM for conventions ...")
    conventions_text = _call_llm(client, prompt)

    conventions_path = output_dir / "conventions.md"
    conventions_path.write_text(conventions_text, encoding="utf-8")
    print(f"  Written: {conventions_path}")


# ---------------------------------------------------------------------------
# Minimal YAML parser (no external deps, handles the structured output we emit)
# ---------------------------------------------------------------------------

def _parse_simple_yaml(text: str) -> dict:
    """Parse the simple YAML blocks produced by the LLM (flat + one-level lists).

    This is intentionally minimal: we only need to handle the schema we asked for.
    It is NOT a general-purpose YAML parser.
    """
    result: dict = {}
    current_key: str | None = None
    current_list: list | None = None
    current_list_item: dict | None = None
    nested_list: list | None = None
    nested_list_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # Nested list item under a list-of-dicts item (e.g. classes under files)
        if nested_list is not None and re.match(r"^\s{6,}-\s+\S", line):
            # e.g. "      - name: Foo"
            stripped = line.strip().lstrip("- ").strip()
            kv = stripped.split(":", 1)
            if len(kv) == 2:
                k2, v2 = kv[0].strip(), kv[1].strip()
                if nested_list and isinstance(nested_list[-1], dict):
                    nested_list[-1][k2] = v2
                else:
                    nested_list.append({k2: v2})
            else:
                nested_list.append(stripped)
            continue

        # Nested key under a list-of-dicts item (e.g. "    classes:")
        if current_list_item is not None and re.match(r"^\s{4,}\w[\w_-]*:\s*$", line):
            key_part = line.strip().rstrip(":")
            nested_list = []
            nested_list_key = key_part
            current_list_item[key_part] = nested_list
            continue

        # Key-value inside a list-of-dicts item (e.g. "    path: foo.swift")
        if current_list_item is not None and re.match(r"^\s{4,}\w", line):
            kv = line.strip().split(":", 1)
            if len(kv) == 2:
                k2, v2 = kv[0].strip(), kv[1].strip()
                current_list_item[k2] = v2
                nested_list = None
                nested_list_key = None
            continue

        # Top-level list item "  - foo" or "  - key: val"
        if current_list is not None and re.match(r"^\s{2,}-\s", line):
            stripped = line.strip().lstrip("- ").strip()
            kv = stripped.split(":", 1)
            if len(kv) == 2 and kv[1].strip() == "":
                # Start of a mapping inside the list
                current_list_item = {}
                current_list.append(current_list_item)
                nested_list = None
                nested_list_key = None
            elif len(kv) == 2:
                current_list_item = {kv[0].strip(): kv[1].strip()}
                current_list.append(current_list_item)
                nested_list = None
                nested_list_key = None
            else:
                current_list.append(stripped)
                current_list_item = None
                nested_list = None
            continue

        # Top-level "key: value" or "key:" (list start)
        m = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if m:
            current_key = m.group(1).strip()
            value = m.group(2).strip()
            current_list = None
            current_list_item = None
            nested_list = None
            nested_list_key = None
            if value == "":
                # Expecting a list or mapping next
                lst: list = []
                result[current_key] = lst
                current_list = lst
            else:
                result[current_key] = value

    return result


def _safe_slug(text: str) -> str:
    """Convert arbitrary text to a safe filesystem slug."""
    text = text.strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower() or "misc"


# ---------------------------------------------------------------------------
# Cache detection
# ---------------------------------------------------------------------------

def _profile_dir_has_content(output_dir: Path) -> bool:
    """Return True if the profile output directory already has files."""
    if not output_dir.exists():
        return False
    return any(output_dir.iterdir())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="profile_native.py",
        description=(
            "One-shot native iOS architecture profiler for T2N Atlas. "
            "Scans a native iOS project and generates a reusable architecture profile."
        ),
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        help="Path to the root of the native iOS project to scan",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Path to write the profile output. "
            "Default: <repo-root>/.ai/t2n/native-profile"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing profile without asking",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Error: repo root not found or not a directory: {repo_root}", file=sys.stderr)
        return 3

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else repo_root / ".ai" / "t2n" / "native-profile"
    )

    # Cache detection
    if _profile_dir_has_content(output_dir) and not args.force:
        print(f"Profile directory already exists and has content: {output_dir}")
        answer = input("Overwrite? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted. Use --force to skip this prompt.")
            return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Profile will be written to: {output_dir}")

    # Initialise Claude client (reads ANTHROPIC_API_KEY from environment)
    client = anthropic.Anthropic()

    # --- Step 1: Build manifest ---
    manifest, swift_files = build_manifest(repo_root)
    if not manifest.strip():
        print("No Swift files with recognisable types found. Nothing to profile.", file=sys.stderr)
        return 2

    # --- Step 2: Generate overview.md + module files ---
    generate_overview_and_modules(client, manifest, output_dir)

    # --- Step 3: Generate conventions.md ---
    generate_conventions(client, swift_files, repo_root, output_dir)

    print()
    print("Native profile generation complete.")
    print(f"Output directory: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
