---
name: source-manifest
description: "Build or validate the source manifest for the source-tutorial pipeline from user-provided URLs/files."
---

# Source Manifest

## Triggers & routing

- **Trigger**: source manifest, sources list, tutorial sources, url list, 资料清单, 教程来源.
- **Use when**: `source-tutorial` 的 C1，需要把多源输入落成统一的 `sources/manifest.yml`，并在内容不完整时显式阻塞。
- **Skip if**: 已经有完整且经过确认的 `sources/manifest.yml`。
- **Network**: none.
- **Guardrail**: 不要伪造来源；manifest 不完整时应返回 BLOCKED，而不是假装完成。


Goal: collect the source candidates for `source-tutorial` into one explicit manifest before ingest starts.

## Inputs

- `GOAL.md`
- `DECISIONS.md`

## Outputs

- `sources/manifest.yml`

## Workflow

1. Read `GOAL.md` and any existing `DECISIONS.md` notes to understand what kinds of sources the tutorial is expected to use.
2. If `sources/manifest.yml` does not exist, scaffold it with a minimal example.
2. Validate that each source has:
   - `source_id`
   - `kind`
   - `locator`
   - `label`
   - for `kind: video`, prefer `transcript_locator` unless the platform exposes public subtitles
3. Reject placeholder/example-only manifests.
4. Return success only when at least one real source exists.

## Accepted `kind`

- `webpage`
- `pdf`
- `markdown`
- `repo`
- `docs_site`
- `video`

For `video`:
- preferred: add `transcript_locator`
- Bilibili may succeed from public subtitles when available
- YouTube should currently be paired with `transcript_locator`

## Script

### Quick Start

- `uv run python .codex/skills/source-manifest/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Scaffold or validate the manifest:
  - `uv run python .codex/skills/source-manifest/scripts/run.py --workspace <workspace>`

## Troubleshooting

### Issue: the unit keeps blocking after scaffold

**Cause**:
- The manifest still contains example placeholders.

**Fix**:
- Replace the scaffold entry with real URLs or local file paths, then rerun the unit.
