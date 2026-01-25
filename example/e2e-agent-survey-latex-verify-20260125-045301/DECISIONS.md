# Decisions log

## Approvals (check to unblock)
- [x] Approve C2 (scope + outline)


> 这里是 HITL 的“签字页”：当 pipeline 声明 human checkpoint 时，把问题与结论记录在这里。
> 执行器会根据 `UNITS.csv` 中 `owner=HUMAN` 的行，自动生成/检查 `## Approvals` 勾选项。

## (example) 2026-01-04
- Decision: Approve scope + outline (C2)
- Approved sections: 1-5
- Notes: keep focus on X; exclude Y
- Signed by: <HUMAN_NAME>

<!-- BEGIN CHECKPOINT:C0 -->
## Kickoff — agent survey latex

- Pipeline: `pipelines/arxiv-survey-latex.pipeline.md`
- Workspace: `workspaces/e2e-agent-survey-latex-verify-20260125-045301`
- Workspace name: `e2e-agent-survey-latex-verify-20260125-045301`

Optional: confirm constraints (or reply "你自己决定" and we will proceed with best-effort defaults):
- Deliverable: language (中文/英文), target length, venue/audience, format (Markdown/LaTeX/PDF).
- Evidence mode: `abstract` (no PDF download) vs `fulltext` (download+extract snippets).
- Scope:
  - In-scope (e.g., tool-use agents, multi-agent, planning/reasoning, memory, reflection, code agents).
  - Out-of-scope (e.g., embodied agents/robotics, pure RL, agent-based modeling).
- Time window: from/to year (or no limit).
- Search constraints: must-include systems/papers/keywords; hard excludes.
- Human sign-off: who will approve C2 (scope+outline) in this file.

Note:
- The pipeline will pause once at C2 (scope+outline) for a single approval, then continue end-to-end.
<!-- END CHECKPOINT:C0 -->

<!-- BEGIN CHECKPOINT:C2 -->
## C2 review — scope + outline (NO PROSE)

- taxonomy: top-level=4, leaf-nodes=8
- outline: sections=6, subsections=8
- mapping: subsections_with_>=3_papers=8/8

Decision:
- Tick `Approve C2` in the approvals checklist above to proceed (evidence → citations → draft).
<!-- END CHECKPOINT:C2 -->
