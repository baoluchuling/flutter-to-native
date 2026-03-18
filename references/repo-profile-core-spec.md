# Repo Profile Core Spec (Atlas V2)

## Purpose

`repo-profile-core` is an upstream capability that builds repository-wide profiling artifacts.
`flutter-to-native` should consume these artifacts instead of rebuilding full semantics in each requirement run.

## Directory Contract

Recommended output directory (`platform=native`):

```text
.ai/t2n/native-profile-v2/
  feature_registry.json
  host_mapping.json
  symbol_graph.jsonl
  relation_graph.jsonl
  scan_meta.yaml
```

For initial integration in this repository, only these two files are required:

- `feature_registry.json`
- `host_mapping.json`

Recommended output directory (`platform=flutter`):

```text
.ai/t2n/flutter-profile/
  scan_meta.json
  feature_index.json
  route_map.json
  state_patterns.json
  data_flow_index.json
  resource_index.json
  test_index.json
  repo_summary.md
```

`flutter_profiler digest` consumes this flutter profile directory.

## Minimum Artifact Fields

### `feature_registry.json`

Each feature entry should include:

- `feature_id`
- `name`
- `description`
- `aliases` (optional)
- `related_features` (optional)
- `status` (optional)
- `source_refs` (optional)
- `last_seen_commit` (optional)

### `host_mapping.json`

Each host mapping entry should include:

- `feature_id`
- `page_hosts`
- `action_hosts`
- `state_hosts`
- `data_hosts`
- `side_effect_hosts` (optional)
- `code_entities` (required for `flutter-to-native` planner to select concrete target files)

## Planner Integration

`atlas_planner.py plan` supports these artifact-driven inputs:

- `--profile-v2-dir`: directory containing `feature_registry.json` + `host_mapping.json`
- `--llm-resolution-path`: optional LLM/agent resolution JSON artifact

Selection order:

1. `repo-profile-core` touchpoints (`--profile-v2-dir`) as primary source
2. LLM resolution touchpoints (`--llm-resolution-path`) merged as semantic guidance
3. Native candidate heuristics remain fallback when profile evidence is insufficient

## LLM Resolution Artifact

Expected JSON structure:

```json
{
  "provider": "cli|agent|none",
  "model": "string",
  "generated_at": "ISO8601",
  "requirement": { "id": "REQ-123", "name": "feature_slug" },
  "confidence": "low|medium|high",
  "suggested_feature_ids": ["feature.book_detail"],
  "suggested_paths": ["Reader/BookDetail/BookDetailViewController.swift"],
  "rationale": "why these targets",
  "warnings": []
}
```

You can generate this artifact with `scripts/atlas_intent_resolver.py`.

## Incremental Update Guidance

`repo-profile-core` should support incremental refresh:

1. Read `git diff` between previous and current commits
2. Re-parse changed files
3. Update symbol and relation graphs
4. Recompute impacted feature candidates
5. Regenerate only changed feature/host entries
6. Keep stable IDs and historical continuity in registry entries
