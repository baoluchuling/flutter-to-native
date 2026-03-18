# Atlas Profiler Spec

## Purpose

`Atlas Profiler` is the repository analysis component of `T2N Atlas`.

Its job is to scan the target iOS repository once, infer how the project is actually organized, and write a reusable native profile into `.ai/t2n/native-profile/`.

The planner should consume this cached profile instead of rediscovering the native architecture on every requirement sync run.

## V1 Scope

The profiler is designed for:

- iOS repositories
- Swift
- UIKit
- legacy or mixed-architecture projects

The profiler must handle repositories with weak or inconsistent module boundaries.

## Non-Goals

- Perfect architectural classification
- Deep semantic understanding of every business rule
- Compilation or runtime verification
- Automatic code modification

The profiler exists to reduce planning uncertainty, not to replace human review.

## Inputs

- iOS repository path
- optional repo subpath filters
- optional force-rescan flag
- optional previous profile in `.ai/t2n/native-profile/`

## Core Questions the Profiler Must Answer

1. What architectural style dominates the project or each major area?
2. How is navigation implemented?
3. How are screens structured and composed?
4. How are network calls and models represented?
5. Which base classes, shared components, and conventions are reused?
6. Which files are high-probability touchpoints for future requirement sync runs?
7. Which directories or files are risky to patch automatically?

## Scan Pipeline

### 1. Repository Inventory

Build a lightweight inventory of the repository:

- top-level directories
- Swift source files
- storyboard or xib files if present
- test targets
- package or dependency manifests

Output intent:

- establish the project surface area
- identify likely app, feature, shared, and infrastructure zones

### 2. Architecture Inference

Infer the dominant structure with confidence notes.

Signals to inspect:

- file naming patterns such as `ViewController`, `ViewModel`, `Coordinator`, `Router`, `Presenter`, `Interactor`
- base classes and protocol naming
- directory clustering
- screen construction flow

Output should be descriptive, not absolute.

Example:

- `The profile area appears MVVM-like with moderate confidence because ViewModel files exist and view controllers hold only binding logic.`

### 3. Navigation Analysis

Detect how navigation is performed.

Signals:

- `UINavigationController`
- `pushViewController`
- `present`
- Coordinator classes
- Router abstractions
- deep-link entry points

Required outputs:

- likely app entry points
- route launch patterns
- registration hotspots
- risky navigation files

### 4. UI Construction Analysis

Identify the common UIKit implementation patterns:

- programmatic UI vs storyboard
- screen composition style
- table or collection usage
- form handling patterns
- modal or sheet patterns
- shared base views or base controllers

The goal is to help the planner generate native code that matches the existing repo style closely enough.

### 5. Networking and Data Analysis

Identify:

- networking client abstractions
- service naming patterns
- DTO and model placement
- decoding style
- error handling patterns
- caching or persistence clues if obvious

The profiler does not need to model every API. It only needs enough structure to guide requirement sync planning.

### 6. Shared Infrastructure Detection

Find reusable pieces such as:

- base view controllers
- UI helper utilities
- theme or style helpers
- alert presenters
- loading and empty-state helpers
- analytics wrappers

These findings help the planner avoid generating isolated one-off code when a shared pattern already exists.

### 7. Touchpoint and Risk Detection

Build a reusable index of probable touchpoints.

Touchpoints include:

- app entry routing files
- feature host controllers
- networking service hubs
- shared model containers
- feature registration files

Risk zones include:

- giant legacy files
- files with many responsibilities
- app-wide routers
- dependency wiring roots
- global theme or configuration files

Each risky file or directory should include a short reason.

## Output Files

The profiler writes to `.ai/t2n/native-profile/`.

### `architecture_summary.md`

Human-readable summary of:

- dominant architecture patterns
- mixed zones if present
- confidence notes
- notable inconsistencies

### `navigation_map.json`

Structured output describing:

- navigation mechanisms
- probable app entry points
- route or flow launch files
- feature-specific navigation hotspots

Suggested shape:

```json
{
  "primary_style": "uikit-navigation-controller",
  "entry_points": ["AppDelegate.swift", "SceneDelegate.swift"],
  "patterns": [
    {
      "kind": "push",
      "evidence": ["HomeViewController.swift", "ProfileCoordinator.swift"]
    }
  ],
  "risky_files": ["AppRouter.swift"]
}
```

### `module_map.json`

Structured grouping of likely repository zones:

- app shell
- features
- networking
- models
- shared UI
- utilities
- tests

Suggested shape:

```json
{
  "zones": [
    {
      "name": "profile",
      "kind": "feature",
      "paths": ["Sources/Profile/"]
    }
  ]
}
```

### `touchpoint_index.json`

Primary machine-readable artifact for planning.

Each touchpoint should include:

- file path
- touchpoint kind
- confidence
- likely reason it is relevant
- whether it is safe to patch automatically

Suggested shape:

```json
{
  "touchpoints": [
    {
      "path": "Sources/Profile/ProfileViewController.swift",
      "kind": "feature_screen",
      "confidence": 0.88,
      "reason": "Contains profile flow UI and refresh logic",
      "safe_patch": true
    }
  ]
}
```

### `ui_patterns.md`

Human-readable notes on:

- preferred UIKit layout patterns
- component reuse
- view hierarchy conventions
- list and form patterns
- state presentation patterns

### `networking_patterns.md`

Human-readable notes on:

- service structure
- request building
- decoding conventions
- error mapping
- model placement

### `risk_zones.md`

Human-readable report of:

- app-wide hotspots
- giant files
- files likely to create regressions if auto-patched
- suggested review level for each zone

### `scan_meta.json`

Control metadata for cache reuse.

Suggested fields:

```json
{
  "profile_version": "v1",
  "project_name": "T2N Atlas target",
  "repo_root": "/abs/path/to/native-ios",
  "scanned_at": "2026-03-15T10:00:00Z",
  "git_head": "abc123",
  "has_uncommitted_changes": true,
  "scan_scope": "full",
  "platform": "ios",
  "language": "swift",
  "ui_framework": "uikit"
}
```

## Cache Reuse and Staleness Rules

The profiler should be reused by default.

Treat the cached profile as stale when any of these are true:

- `.ai/t2n/native-profile/scan_meta.json` does not exist
- `profile_version` is incompatible
- repo root has changed
- git head has changed materially
- critical directories changed after the last scan
- the user requests a rescan

V1 can start with simple invalidation:

- compare repo path
- compare git head when available
- compare scan timestamp against a manual rescan policy

Later versions can move to finer-grained fingerprints.

## Confidence Model

Each major inference should carry an informal confidence score or confidence label.

Suggested labels:

- high
- medium
- low

Use lower confidence when:

- multiple architectural patterns conflict
- naming is inconsistent
- evidence is sparse

## Planner Integration Rules

The planner should treat the profiler as advisory but authoritative enough to set defaults.

Planner behavior:

- trust high-confidence touchpoints by default
- surface medium-confidence touchpoints in the plan
- require explicit review for low-confidence or risky touchpoints

## Failure Behavior

If the profiler cannot infer a clear structure:

- still write partial outputs
- mark uncertainty explicitly
- avoid blocking the planner completely

The system should degrade into:

- weaker defaults
- more user review in the plan

## V1 Implementation Notes

The first implementation can rely on repository heuristics:

- filename patterns
- directory patterns
- symbol search
- base class detection
- navigation API search

It does not need AST-perfect analysis in V1.

The priority is actionable planning accuracy, not compiler-grade modeling.
