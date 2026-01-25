# Retrieval report

- Workspace: `/home/rjs/Workspace/codebase/research-units-pipeline-skills/workspaces/e2e-agent-survey-latex-verify-20260125-045301`
- queries.md: `/home/rjs/Workspace/codebase/research-units-pipeline-skills/workspaces/e2e-agent-survey-latex-verify-20260125-045301/queries.md`
- Keywords: `12`
- Excludes: `5`
- Time window: ``..``
- Online retrieval (best-effort): `OK`

## Summary

- Imported/collected records (pre-dedupe): `809`
- Deduped records (output): `800`
- Online error: (none)
- Missing stable ID (arxiv_id/doi/url all empty): `0`
- Missing abstract: `0`
- Missing authors: `0`

## Sources

- Offline inputs: `0`
- Snowball inputs: `0`

## Coverage buckets (by route)

| route | unique_papers |
|---|---:|
| arxiv_query:(all:"agent survey latex" OR all:"LLM agent" OR all:"language model agent" OR all:"tool-using agent") | 792 |
| pinned_arxiv_id:2210.03629v3 | 1 |
| pinned_arxiv_id:2302.04761v1 | 1 |
| pinned_arxiv_id:2303.11366v4 | 1 |
| pinned_arxiv_id:2305.10601v2 | 1 |
| pinned_arxiv_id:2305.16291v2 | 1 |
| pinned_arxiv_id:2308.11432v7 | 1 |
| pinned_arxiv_id:2411.18279v12 | 1 |
| pinned_arxiv_id:2503.21460v1 | 1 |
| pinned_arxiv_id:2503.23037v3 | 1 |

## Next actions

- If the pool is too small: add more exports under `papers/imports/` (multi-route) or enable network and rerun with `--online`.
- If cite coverage is poor later: increase candidate pool size and run snowballing (provide exports under `papers/snowball/`).
- If many abstracts are missing: provide richer exports or rerun online enrichment.
