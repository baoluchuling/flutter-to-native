# Atlas Profiler Implementation Design

## Purpose

This document turns the high-level `Atlas Profiler` concept into an implementation-ready design.

Use it when building the first profiler script or refining the output contracts consumed by `Atlas Planner`.

## Recommended Script Shape

V1 should start with a single entry script:

- `scripts/atlas_profiler.py`

The script may later be split into modules, but the first implementation should keep one stable command-line entry point.

## Command-Line Interface

Recommended command:

```bash
python3 scripts/atlas_profiler.py scan \
  --repo-root /path/to/native-ios \
  --output-dir /path/to/native-ios/.ai/t2n/native-profile
```

Recommended subcommands:

- `scan`
- `status`
- `invalidate`

### `scan`

Purpose:

- create or refresh the native profile

Suggested flags:

- `--repo-root`
- `--output-dir`
- `--force`
- `--scope full|changed`
- `--changed-files <path>`
- `--include-tests`
- `--max-files <int>`

V1 defaults:

- `scope=full`
- `include-tests=true`

### `status`

Purpose:

- report whether the cached profile exists and whether it appears stale

Suggested output:

- profile exists or not
- last scanned commit
- last scanned time
- stale reason list

### `invalidate`

Purpose:

- remove or mark the cached profile as stale

V1 can implement this by deleting `scan_meta.json` or writing a stale marker.

## Exit Codes

Recommended exit codes:

- `0`: success
- `1`: general runtime failure
- `2`: invalid arguments
- `3`: repo root not found or not readable
- `4`: profile incomplete or corrupted

## Execution Flow

### Phase 0: Preflight

Tasks:

- validate repo root exists
- validate output directory path
- capture current time
- capture git metadata when available
- decide whether to reuse or refresh

Preflight outputs:

- in-memory run context
- stale reason list

### Phase 1: Repository Inventory

Tasks:

- list candidate files
- classify by extension and role
- ignore build artifacts and dependency directories

Recommended ignores:

- `Pods/`
- `Carthage/`
- `DerivedData/`
- `.build/`
- `build/`
- `.git/`
- `.ai/t2n/`

Primary file types:

- `.swift`
- `.storyboard`
- `.xib`
- `.plist`

Secondary file types:

- `.md`
- `.json`
- dependency manifests such as `Podfile`, `Package.swift`, `Cartfile`

### Phase 2: Symbol and Pattern Harvest

Tasks:

- collect filenames
- collect directory names
- collect class, struct, enum, protocol names where cheap
- collect inheritance patterns where cheap
- collect selected API usage patterns by text search

V1 guidance:

- use text heuristics and regex first
- do not block V1 on AST parsing

### Phase 3: Architecture Classification

Goal:

- infer project-wide and zone-level architectural styles

Suggested labels:

- `mvc`
- `mvvm`
- `coordinator`
- `router_based`
- `viper_like`
- `mixed`

Heuristic examples:

- many `*ViewController.swift` files with direct service usage: MVC signal
- many `*ViewModel.swift` files referenced by controllers: MVVM signal
- presence of `*Coordinator.swift` and `start()` flows: Coordinator signal
- centralized `Router` objects: router-based signal

Recommended output fields:

- `label`
- `confidence`
- `evidence`
- `notes`

### Phase 4: Navigation Detection

Search for:

- `pushViewController`
- `present(`
- `show(`
- `setViewControllers`
- `UINavigationController`
- `UITabBarController`
- `Coordinator`
- `Router`
- deep-link handlers

Capture:

- primary navigation style
- likely app entry files
- flow launchers
- route registration hotspots

### Phase 5: UI Pattern Detection

Search for:

- `UIViewController`
- `UITableView`
- `UICollectionView`
- `UIStackView`
- Auto Layout anchors
- SnapKit or Masonry usage if present
- storyboard loading patterns
- custom base controllers
- loading, empty, and error view helpers

Capture:

- programmatic vs storyboard bias
- list screen patterns
- form screen patterns
- reusable container patterns
- common base classes

### Phase 6: Networking and Data Detection

Search for:

- `URLSession`
- Alamofire usage
- service client classes
- request builders
- `Codable`
- `Decodable`
- response wrappers
- error enums or error mappers

Capture:

- primary networking style
- service layer conventions
- model placement conventions
- error handling patterns

### Phase 7: Touchpoint Scoring

Build machine-readable candidates for likely future updates.

Touchpoint kinds:

- `app_entry`
- `global_router`
- `feature_screen`
- `feature_flow`
- `feature_service`
- `shared_model`
- `shared_ui`
- `dependency_root`
- `theme_root`

Touchpoint scoring inputs:

- filename semantics
- directory semantics
- symbol matches
- API pattern matches
- proximity to feature-like directories
- cross-reference density if available

### Phase 8: Risk Scoring

Build a separate risk model for files and directories.

Risk signals:

- very large files
- app-wide configuration files
- router or coordinator roots
- dependency injection roots
- files with multiple unrelated responsibilities
- files touched by many patterns

Suggested risk levels:

- `low`
- `medium`
- `high`

### Phase 9: Write Output Files

Write all profile outputs atomically where feasible.

Write order:

1. machine-readable JSON outputs
2. markdown summaries
3. `scan_meta.json`

If a scan fails mid-run, avoid leaving a partially valid profile that appears complete.

## Heuristic Priorities

When heuristics disagree, prioritize in this order:

1. explicit symbol and API evidence
2. base class and inheritance evidence
3. directory clustering
4. filename conventions alone

This reduces overfitting to naming style.

## Output Schemas

### `scan_meta.json`

Recommended fields:

```json
{
  "profile_version": "v1",
  "tool_name": "atlas-profiler",
  "tool_version": "0.1.0",
  "repo_root": "/abs/path/to/native-ios",
  "output_dir": "/abs/path/to/native-ios/.ai/t2n/native-profile",
  "platform": "ios",
  "language": "swift",
  "ui_framework": "uikit",
  "scan_scope": "full",
  "scanned_at": "2026-03-15T10:00:00Z",
  "git": {
    "head": "abc123",
    "branch": "main",
    "dirty": true
  },
  "counts": {
    "swift_files": 320,
    "storyboards": 4,
    "xibs": 12,
    "test_files": 45
  },
  "stale_after": {
    "git_change": true,
    "manual_rescan": false
  }
}
```

### `module_map.json`

Recommended fields:

```json
{
  "zones": [
    {
      "name": "profile",
      "kind": "feature",
      "paths": ["Sources/Profile/"],
      "confidence": "medium",
      "notes": ["Contains profile controller, service, and reusable views"]
    }
  ],
  "shared_zones": [
    {
      "name": "networking",
      "paths": ["Sources/Core/Networking/"]
    }
  ]
}
```

### `navigation_map.json`

Recommended fields:

```json
{
  "primary_style": "uikit-navigation-controller",
  "confidence": "high",
  "entry_points": [
    {
      "path": "AppDelegate.swift",
      "reason": "App bootstrap"
    }
  ],
  "patterns": [
    {
      "kind": "push",
      "evidence": ["Sources/Home/HomeViewController.swift"]
    }
  ],
  "routing_hotspots": [
    {
      "path": "Sources/App/AppRouter.swift",
      "risk": "high"
    }
  ]
}
```

### `touchpoint_index.json`

Recommended fields:

```json
{
  "touchpoints": [
    {
      "path": "Sources/Profile/ProfileViewController.swift",
      "kind": "feature_screen",
      "confidence": 0.88,
      "risk": "medium",
      "safe_patch": true,
      "reason": "Likely host for profile screen behavior"
    }
  ]
}
```

## Staleness Detection

The profiler should avoid rescanning on every run, but it must not trust clearly stale data.

V1 staleness rules:

- stale if `scan_meta.json` is missing
- stale if `profile_version` changes
- stale if `repo_root` changes
- stale if current git head differs from stored git head
- stale if `--force` is passed

Optional V1.1 rules:

- stale if critical files changed
- stale if output files are missing
- stale if the last scan used a different scope

## Safety Rules

The profiler must never:

- modify project source files
- write outside `.ai/t2n/` unless explicitly requested
- present low-confidence guesses as facts

The profiler may:

- mark outputs as partial
- emit low-confidence findings with notes
- recommend manual review of risky files

## Suggested Internal Modules

If the script grows, split into these modules:

- `inventory.py`
- `patterns.py`
- `architecture.py`
- `navigation.py`
- `ui_patterns.py`
- `networking.py`
- `touchpoints.py`
- `risk.py`
- `writers.py`

V1 can still begin with a single file and refactor later.

## Minimum Useful First Version

The first working version does not need every heuristic.

Minimum acceptable V1:

- inventory Swift, storyboard, xib, and test files
- detect likely architecture style from names and references
- detect navigation APIs and hotspots
- detect basic networking conventions
- write all required output files
- support cache reuse with git-head invalidation

That is enough for `Atlas Planner` to start producing useful plans.
