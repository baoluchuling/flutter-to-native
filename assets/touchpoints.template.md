# Touchpoints: <requirement-name>

## 1. 触点概览

- Requirement ID: `<requirement-id>`
- Requirement Name: `<requirement-name>`
- Total Touchpoints: `<count>`
- Existing Files: `<count>`
- New Files: `<count>`
- Manual Candidates: `<count>`

## 2. 现有文件触点

### `<file-path>`

- Type: `<feature_screen|feature_flow|feature_service|shared_model|shared_ui|global_router|other>`
- Action: `update`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this file is involved>
- Expected Change:
  - <change-summary-1>

## 3. 新建文件触点

### `<file-path>`

- Type: `<feature_screen|feature_view|feature_component|feature_service|feature_model|other>`
- Action: `create`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this file should be created>
- Expected Responsibility:
  - <responsibility-1>

## 4. 注册点与全局触点

### `<file-path>`

- Type: `<registration_point|global_router|dependency_root|theme_root|other>`
- Action: `<update|manual_candidate>`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this global file is relevant>
- Note:
  - <note-1>

## 5. 人工候选触点

### `<file-path>`

- Type: `<touchpoint-type>`
- Confidence: `<high|medium|low>`
- Risk: `<low|medium|high>`
- Reason: <why this should not be auto-patched in V1>
- Suggested Manual Action:
  - <manual-action-1>
