# Atlas V2 Repo Profile Core Decoupling Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple repository-wide profiling from `flutter-to-native`, and make planner consume profile artifacts plus optional LLM intent outputs.

**Architecture:** Introduce an artifact bridge layer (`atlas_intent_bridge`) that reads `repo-profile-core` outputs (`feature_registry.json`, `host_mapping.json`) and converts them into planner touchpoints. Add an LLM resolution artifact path so planner consumes model outputs instead of relying only on heuristics. Keep existing heuristics as fallback.

**Tech Stack:** Python 3, stdlib (`json`, `unittest`, `subprocess`, `pathlib`), existing Atlas scripts.

---

## Chunk 1: Artifact Bridge + Tests

### Task 1: Add failing tests for profile artifact bridge

**Files:**
- Create: `flutter-to-native/tests/test_atlas_intent_bridge.py`
- Test: `flutter-to-native/tests/test_atlas_intent_bridge.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run tests and confirm failure**
Run: `python3 -m unittest flutter-to-native/tests/test_atlas_intent_bridge.py -v`
Expected: `ImportError` or missing functions from `atlas_intent_bridge`
- [ ] **Step 3: Implement minimal bridge module**
- [ ] **Step 4: Run tests and confirm pass**
Run: `python3 -m unittest flutter-to-native/tests/test_atlas_intent_bridge.py -v`
Expected: all tests pass

### Task 2: Add profile/LLM artifact bridge module

**Files:**
- Create: `flutter-to-native/scripts/atlas_intent_bridge.py`
- Modify: `flutter-to-native/scripts/atlas_planner.py`
- Test: `flutter-to-native/tests/test_atlas_intent_bridge.py`

- [ ] **Step 1: Implement `load_profile_v2` and score-based feature selection**
- [ ] **Step 2: Implement `touchpoints_from_llm_resolution` and `merge_touchpoints`**
- [ ] **Step 3: Hook bridge into planner as optional upstream source**
- [ ] **Step 4: Run focused tests**
Run: `python3 -m unittest flutter-to-native/tests/test_atlas_intent_bridge.py -v`
Expected: pass

## Chunk 2: LLM Resolver Artifact Path

### Task 3: Add LLM intent resolver CLI

**Files:**
- Create: `flutter-to-native/scripts/atlas_intent_resolver.py`
- Create: `flutter-to-native/tests/test_atlas_intent_resolver.py`
- Modify: `flutter-to-native/SKILL.md`

- [ ] **Step 1: Write failing resolver normalization tests**
- [ ] **Step 2: Run tests and confirm failure**
Run: `python3 -m unittest flutter-to-native/tests/test_atlas_intent_resolver.py -v`
Expected: missing module/function failures
- [ ] **Step 3: Implement resolver (`none`/`agent`/`cli`) and JSON normalization**
- [ ] **Step 4: Run resolver tests and confirm pass**
Run: `python3 -m unittest flutter-to-native/tests/test_atlas_intent_resolver.py -v`
Expected: all tests pass

### Task 4: Connect planner to LLM resolution artifact

**Files:**
- Modify: `flutter-to-native/scripts/atlas_planner.py`
- Test: `flutter-to-native/tests/test_atlas_intent_bridge.py`
- Test: `flutter-to-native/tests/test_atlas_intent_resolver.py`

- [ ] **Step 1: Add planner args for `--profile-v2-dir` and `--llm-resolution-path`**
- [ ] **Step 2: Merge profile/LLM touchpoints with legacy fallback heuristics**
- [ ] **Step 3: Ensure backward compatibility when new artifacts are absent**
- [ ] **Step 4: Run all unit tests**
Run: `python3 -m unittest discover -s flutter-to-native/tests -p 'test_*.py' -v`
Expected: all tests pass

## Chunk 3: Asset Contracts + Docs

### Task 5: Add reusable artifact templates and reference docs

**Files:**
- Create: `flutter-to-native/assets/repo-profile-core/feature_registry.template.json`
- Create: `flutter-to-native/assets/repo-profile-core/host_mapping.template.json`
- Create: `flutter-to-native/references/repo-profile-core-spec.md`
- Modify: `flutter-to-native/references/profile-assets-spec.md`
- Modify: `flutter-to-native/SKILL.md`

- [ ] **Step 1: Add minimal template contracts for external profile assets**
- [ ] **Step 2: Document integration boundary and incremental refresh path**
- [ ] **Step 3: Update skill references/assets list**
- [ ] **Step 4: Smoke check JSON/YAML readability**
Run: `python3 -m json.tool flutter-to-native/assets/repo-profile-core/feature_registry.template.json >/dev/null && python3 -m json.tool flutter-to-native/assets/repo-profile-core/host_mapping.template.json >/dev/null`
Expected: exit code 0

## Chunk 4: Verification

### Task 6: End-to-end dry run on a sample run-dir

**Files:**
- Modify (if needed): `flutter-to-native/scripts/atlas_planner.py`
- Output (manual run): `.ai/t2n/runs/<run-id>/`

- [ ] **Step 1: Prepare synthetic `profile-v2` + `llm-resolution` fixtures**
- [ ] **Step 2: Run planner with new args and verify generated artifacts**
Run: `python3 flutter-to-native/scripts/atlas_planner.py plan ... --profile-v2-dir ... --llm-resolution-path ...`
Expected: `feature_intent_spec.yaml`, `native_operation_plan.yaml`, `requirement_sync_contract.yaml` generated
- [ ] **Step 3: Ensure planner still works without new args**
Run: existing legacy planner command
Expected: no behavior regression

