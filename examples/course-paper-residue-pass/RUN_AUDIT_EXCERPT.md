# Run Audit Excerpt

This is a curated projection of the `run-audit.v2` result generated on
2026-08-02. Absolute filesystem paths, private Run and Goal identifiers, and
per-Attempt identifiers are intentionally omitted.

## Identity And State

- Workflow: `arxiv-survey-latex`
- Durable state: `COMPLETED`
- Completion protocol: `recoverable-provenance.v2`
- Harness revision: `8c0cf7ddb71617e66d6583a4438a8f457c99191a`
- Repository dirty at Run initialization: yes
- Audit phase: `complete_candidate`
- Audit verdict: `PASS`

## Completion Evidence

- Units: 49 total, 49 `DONE`, 0 active
- Target Artifacts: 75 present, 0 missing
- Unit output Manifests: 49
- Harness issues: 0 errors, 0 warnings
- Locked Workflow acceptance: PASS
- Required checks represented: 31/31
- Required Units verified by a `DONE` Manifest plus committed Completion Event:
  31
- Required `DONE` Units without acceptance evidence: 0
- Ledger integrity issues: 0
- Harness Kernel lock: `PASS` (35/35 current paths matched; 35 locked)

## Template-Residue And Voice Evidence

- Scorecard: `template-residue-scorecard.v1`
- Verdict: PASS
- Whole-draft measurement: 0/226 sentences (0.0%)
- Policy limit: <=10%
- Run-selected template assets: 4
- Asset-selection verification: PASS
- Writer-implementation lock verification: PASS
- Blocked pipeline-voice matches: 0

## Delivery Evidence

- Artifact contract: PASS
- Writing audit: PASS
- Unique citations: 24
- PDF compilation: SUCCESS
- PDF pages: 10
- Requested range: 8-10 pages

## Attempt Summary

- Started and finished: 49
- Open: 0
- Extra retry Attempts: 0
- Terminal statuses: 49 succeeded
- Execution modes: 48 manual, 1 process

The manual Attempts revalidated retained research Artifacts under the current
contract; they do not establish autonomous generation or a repeated network
retrieval. See `run-summary.json` for content hashes and explicit limitations.
