# understand_chat_log.md 格式（必须遵守）

每次调用 `/understand-anything:understand-chat` 或 `/understand-anything:understand-explain` 后，追加以下格式到 run-dir 的 `understand_chat_log.md`：

```markdown
## [序号] [阶段标签] YYYY-MM-DD HH:MM

**工具**: understand-chat | understand-explain
**阶段**: native_chain_match | execute-TASK-XX | ...
**问题**:
> （完整的查询问题原文）

**关键结论**:
- （节点名称、文件路径、调用关系等核心发现，3-10 条）

**用于**: （说明该结论被用在了哪个产物/决策，如 native_chain_candidates.json CAP-01）
```

规则：
- 序号从 1 开始，每次追加递增
- 阶段标签：plan 阶段用 `plan`，执行阶段用 `execute-TASK-XX`
- 禁止把原始 knowledge-graph 节点 JSON 全量粘贴，只写关键结论
- 若 skill 返回"找不到节点"或"无相关结果"，也必须记录（便于排查）
