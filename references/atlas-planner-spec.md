# Atlas Planner Spec

## Purpose

`Atlas Planner` is the planning component of `T2N Atlas`.

Its job is to combine product requirement evidence, Flutter implementation evidence, Flutter diff evidence, Flutter test evidence, and the cached `native-profile-v2` artifacts, then produce a reviewable synchronization plan before any native code is modified.

## Planner Contract

The planner must never apply code changes directly.

The planner must always produce:

- `requirement_sync_contract.yaml`
- `sync_plan.md`
- `touchpoints.md`
- `risk_report.md`

The planner stops after writing those artifacts and waits for user confirmation.

## Inputs

### Product Inputs

- PRD
- ticket or requirement description
- acceptance criteria if available

### Flutter Inputs

- feature directories
- relevant implementation files
- PR diff
- tests

### Native Inputs

- cached native profile in `.ai/t2n/native-profile-v2/`
- target iOS repository path

## Planning Pipeline

### 1. Evidence Aggregation

Normalize all available evidence into a common planning context.

Evidence types:

- business intent
- Flutter UI structure
- Flutter state behavior
- Flutter API usage
- Flutter model shape
- Flutter tests and acceptance behavior
- native repository structure and touchpoints

The planner should use all available evidence, not just one source.

### 2. Requirement Scope Inference

Infer the business scope of the feature being synchronized.

The scope should answer:

- what feature is being delivered
- what user flows matter
- what success conditions matter
- which Flutter files best represent that behavior

The scope is business-led, not file-led.

#### Exclusion Criteria

Only the following changes may be excluded from scope:

- Pure code formatting (indentation, line breaks, import sorting) with **zero visual parameter changes**
- Pure Flutter framework internals (e.g., Widget class replacement) where iOS has no corresponding component
- Platform-specific features that iOS already handles differently (e.g., Firebase sync init when iOS is synchronous)

**UI tweaks (spacing, colors, corner radius, font size adjustments) must NOT be excluded.** They must be merged into the related feature's scope, as they directly affect UI fidelity in the final output.

### 3. Flutter Behavior Extraction

Extract behavior semantically:

- screens and subviews
- user interactions
- loading, success, error, and retry states
- APIs and model dependencies
- assets and strings
- notable unsupported behavior
- **model field shapes with nullable/non-nullable annotations**

Avoid one-to-one widget translation. The output should describe behavior and structure in native-friendly terms.

#### 3a. Model Field Alignment (Required for data changes)

When the feature involves model changes, the planner must produce a field alignment table:

- List every new/changed field from Flutter models
- For each field, record: Flutter type, nullable (`?`), proposed iOS type, proposed default value strategy
- Read the target iOS model file to determine existing convention (e.g., `Modelable` protocol uses `var x = ""` defaults, not optionals)
- Alignment decision must consider: (1) whether the server always returns the field (2) existing model's declaration pattern
- This table becomes part of `sync_plan.md` and is binding for the apply phase

#### 3b. Entry Point Localization and Call Chain Analysis (Required for existing file modifications)

When the feature involves modifying entry points in existing files, the planner must first **locate** the correct iOS method, then trace its call chain.

**Step 1: Functional scenario identification (from Flutter)**

Do NOT start from Flutter method names. Instead, describe the functional scenario:
- What triggers this behavior? (user action, page event, timer, data loaded, etc.)
- What is the expected outcome? (show UI, update data, fire event, etc.)
- Example: "When user scrolls to a locked chapter, automatically show the purchase UI"

**Step 2: iOS method localization (by scenario, NOT by name grep)**

Find the iOS method that serves the same functional scenario:
- Trace from the trigger event in iOS (e.g., page scroll callback → page change handler → locked content detection → purchase UI display)
- Follow the iOS architecture's own patterns (delegate chains, notification observers, lifecycle methods)
- **NEVER** grep for Flutter method names or similar keywords in iOS code to find the entry point
- The correct method is the one that fulfills the same functional role, regardless of its name

**Step 3: Verification**

- Confirm the found iOS method and Flutter method serve the same functional purpose
- If the iOS method name looks unrelated to the Flutter method name, that's expected — different architectures use different naming
- Trace upstream/downstream to verify compatibility

**Step 4: Document in sync_plan.md**

- Record the functional scenario
- Record how the iOS method was located (which call chain was followed)
- Record architecture differences
- This analysis is binding for the apply phase

### 4. Native Impact Selection

Using the cached native profile, decide:

- which existing native files likely need modification
- which new native files should be created
- which risky files should stay manual candidates

Every chosen touchpoint should have a reason.

### 5. Requirement Sync Contract Generation

Write the canonical intermediate artifact:

- `requirement_sync_contract.yaml`

This contract should be sufficient to drive patch generation later.

### 6. Plan and Risk Generation

Write:

- `sync_plan.md`
- `touchpoints.md`
- `risk_report.md`

These artifacts are intended for user review.

### 7. Plan Validation Gate (Automatic)

After generating all plan artifacts, the planner must self-validate before presenting to the user.

Validation checks:

| ID | Check | Pass Condition | On Fail |
|----|-------|----------------|---------|
| V1 | No unresolved items | No "需确认"/"TBD"/"待定"/"需要确认" in sync_plan | Loop back and resolve |
| V2 | Entry points located | Every existing-file modification has an explicit target method with call chain | Loop back, locate by scenario |
| V3 | Entry point method | Call chain analysis includes functional scenario and iOS trace path, not just method name | Loop back, add scenario trace |
| V4 | Field alignment tables | Every model change has a per-field alignment table | Loop back and complete |
| V5 | UI design reference | Every UI component cites design source (Figma/screenshot/none); missing = manual_candidate | Loop back or request from user |
| V6 | Trigger mode | Every feature specifies trigger mode (auto/user_action/conditional) | Loop back and complete |

Output: `<run-dir>/plan_validation.md`

- **All PASS**: proceed to confirmation gate
- **Any FAIL**: loop back to fix, do NOT present to user until all checks pass
- **WARN only**: proceed to confirmation gate, but highlight warnings to user

### 8. Confirmation Gate

The planner stops here.

The next phase may start only after explicit approval.

The planner must present both `sync_plan.md` and `plan_validation.md` to the user.

## Requirement Sync Contract

### Role

The contract is the machine-oriented representation of the feature sync task.

It should connect:

- business requirement
- Flutter evidence
- native impact
- planned patch actions
- known gaps

### Required Top-Level Fields

```yaml
requirement:
mode:
sync_strategy:
source:
target:
behavior:
flutter_evidence:
native_impact:
patch_plan:
unsupported:
```

### Field Specification

#### `requirement`

Purpose:

- identify the business request

Suggested fields:

- `id`
- `name`
- `summary`
- `acceptance_criteria`

#### `mode`

Expected value in V1:

- `feature_sync`

#### `sync_strategy`

Expected value in V1:

- `scoped_patch`

#### `source`

Purpose:

- describe the Flutter-side evidence and why it is relevant

Suggested fields:

- `flutter_paths`
- `change_basis`
- `change_ref`
- `notes`

#### `target`

Purpose:

- describe where synchronization will happen

Required fields:

- `platform`
- `language`
- `ui_framework`
- `repo_root`
- `profile_path`

Optional fields:

- `module_hint`
- `write_mode`

#### `behavior`

Purpose:

- capture what the feature must do

Suggested fields:

- `user_flows`
- `acceptance_points`
- `states`
- `strings`
- `assets`

#### `flutter_evidence`

Purpose:

- identify the source implementation evidence

Suggested fields:

- `screens`
- `state_holders`
- `api_calls`
- `tests`
- `key_files`

#### `native_impact`

Purpose:

- identify where the native repo will likely change

Suggested fields:

- `existing_files`
- `new_files`
- `registration_points`
- `risk_files`

#### `patch_plan`

Purpose:

- summarize intended file actions

Suggested fields:

- `create`
- `update`
- `manual_candidates`
- `deferred_items`

#### `unsupported`

Purpose:

- record behavior that V1 cannot safely automate

Examples:

- complex animation
- platform SDK wiring
- uncertain routing integration

## Sync Plan Format

`sync_plan.md` is the primary review artifact for the user.

It should be concise but specific enough for approval.

### Required Sections

#### 1. Requirement Summary

Include:

- requirement name
- short business summary
- planner confidence

#### 2. Flutter Evidence Summary

Include:

- key Flutter files
- relevant PR diff summary
- relevant tests

#### 3. Intended Native Outcome

Include:

- what the iOS feature should do after sync
- what behavior is expected to match Flutter

#### 4. Planned Touchpoints

Include:

- existing files to update
- new files to create
- reason each file is involved
- risk level

#### 5. Planned Actions

Include:

- UI work — **must reference design spec, not Flutter widgets**
- state or interaction work
- network or model work — **must include field alignment table**
- routing or registration work — **must include call chain analysis**

#### 6. Unsupported or Manual Items

Include:

- what will not be automated
- what remains for manual follow-up

#### 7. Approval Gate

Include:

- a clear statement that no code has been changed yet
- the exact next step if the user approves

## Touchpoints Format

`touchpoints.md` is the detailed file-level appendix for the plan.

For each touchpoint, record:

- file path
- touchpoint type
- why it matters
- whether it is create or update
- confidence
- risk level

## Risk Report Format

`risk_report.md` should separate technical and product risk.

Suggested sections:

- architectural uncertainty
- risky legacy files
- unsupported Flutter behavior
- behavior parity risks
- test coverage gaps

## Planning Rules for Existing Native Files

The planner may propose updates to existing files in V1.

Rules:

- every existing file must appear in `touchpoints.md`
- every existing file must include a reason
- high-risk files must be called out in `risk_report.md`
- app-wide files should default to manual candidates unless evidence is strong

## Confidence and Escalation Rules

Use planning confidence labels:

- high
- medium
- low

Escalate review when:

- native touchpoint confidence is low
- Flutter behavior is ambiguous
- acceptance criteria are incomplete
- the planner touches app-wide infrastructure

## Run Artifact Layout

Each planning run should write to a timestamped directory:

```text
.ai/t2n/runs/<run-id>/
  requirement_sync_contract.yaml
  sync_plan.md
  touchpoints.md
  risk_report.md
```

Suggested run id pattern:

- `YYYY-MM-DD-requirement-slug`

## Approval Flow

The planner phase ends with a review package.

Default control flow:

1. build or load native profile
2. aggregate evidence
3. write contract and review artifacts
4. present the plan
5. wait for user approval
6. only then allow apply

## UI Implementation Policy

The planner must not describe UI in terms of Flutter widgets. Instead:

- Describe UI behavior and visual requirements (what the user sees, what interactions are available)
- Reference design specs (Figma/screenshots) when available
- If no design spec is available, flag it as a risk and request from user
- Key visual parameters (spacing, colors, corner radius, gradient angles, font sizes) should be listed explicitly for user confirmation
- Flutter code is only a logic reference (interaction flow, state transitions, data binding), not a visual reference

## V1 Success Criteria

The planner is good enough when:

- it consistently identifies the correct business scope
- it proposes plausible native touchpoints
- the sync plan is reviewable without reading the whole repo
- the apply phase can proceed using the planner outputs without major reinterpretation
- **model field alignment tables are complete and accurate**
- **entry point call chains are correctly traced in the iOS architecture**
- **UI work references design specs, not Flutter widget trees**
