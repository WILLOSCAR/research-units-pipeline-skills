---
name: source-manifest
description: List the source pack the Goal names (paths and URLs) as manifest.yml — one entry per source with a stable source_id, kind, locator, label, role, and audience note — so ingest knows what to fetch and every later step cites sources by id.
role: producer
reads: [goal.md, success_spec.yaml]
outputs: [manifest.yml]
---

# Source Manifest

The `manifest` step of the `tutorial` kind. The Goal names a fixed source
pack — files, URLs, a repository, a transcript — and an audience; this step
lists that pack as `manifest.yml`, one entry per source, so `source-ingest`
knows what to fetch and under which `source_id` to file it, and so
`concept-graph`, `module-planner`, and `tutorial-writer` cite each source by
a stable id. Nothing enters the tutorial that is not listed here. `manifest.yml` is
also among the writer's inputs, so a `spec-coverage` finding that cites it
and implicates `manifest` returns here as a Fault; everything downstream is
then re-run on the new list.

## Inputs

- `goal.md` (and the packet's `goal.text`) — the
  request, the audience, and the source pack, commonly `constraints.sources`
  as a list of paths or URLs.
- `success_spec.yaml` — the `coverage` criteria name sources or topics the
  tutorial must cover; each named source needs an entry. `scope` names the
  audience and what they already know.

## Outputs

`manifest.yml`:

```yaml
schema: rh.source_manifest/1
sources:
  - source_id: retries-guide
    kind: html            # pdf | html | md | repo | video-transcript
    locator: https://example.dev/docs/retries
    label: Client retries guide
    role: primary         # primary | supporting
    audience_note: Read in full; the retry budget is defined here at the audience's level.
  - source_id: client-repo-readme
    kind: repo
    locator: https://github.com/example/client#README.md
    label: Client repository README
    role: supporting
    audience_note: Only the installation and configuration sections matter here.
```

- `source_id` — `[a-z0-9-]+`, 3–40 characters, unique, derived from the
  label; it becomes the stem of `sources/<source_id>.md` and the id every
  later file cites.
- `kind` — from the locator: `.pdf` → `pdf`; an `http(s)` page → `html`;
  `.md` / `.txt` / `.rst` → `md`; a git URL or a directory → `repo`; `.srt`
  / `.vtt` or a transcript file → `video-transcript`.
- `locator` — the path or URL exactly as the Goal gives it; for `repo`,
  optionally `#<path within the repo>`.
- `label` — the human title. `role` — `primary` (a module teaches from it)
  or `supporting` (definitions, background, onward pointers).
  `audience_note` — one sentence: what this source gives the audience and
  which parts to skip.
- Kernel gates on this step: `schema-valid` (parses as YAML, not empty) and
  `scaffold-absent` (no `<!-- scaffold -->`, no whole-word `TODO`, `TBD`,
  `FIXME`, or `XXX`).

## Method

1. List every path and URL the Goal gives, in the Goal's order; each becomes
   one entry. Add an entry the Goal does not name only when it is a directly
   reachable part of a named source (a repository's README, a page under the
   named docs root).
2. Split a named source into several entries only when the tutorial will
   cite the parts separately (a repo's README and its `docs/` guide; the
   chapters of a book PDF); each entry is one ingestible unit of text.
3. A video is a source only through its transcript: with a watch page and no
   transcript path, subtitle file, or transcript URL, write no entry.
4. Mark `primary` every source a `coverage` criterion names, and at least one
   source per `coverage` criterion; the rest are `supporting`.
5. Check before writing: every named path or URL has exactly one entry; ids
   are unique; every `coverage` criterion has a `primary` entry.

## Repair

Kernel Faults — the integrity check (`manifest.yml` missing or empty),
`schema-valid` (does not parse), `scaffold-absent` (a placeholder token) —
are answered by writing the manifest again with the token replaced or the
entry dropped. A `spec-coverage` Fault names a source the spec covers that
the list lacks: add its entry from the Goal and keep every other entry.

## Do not

- Do not fetch or read the sources; `source-ingest` does.
- Do not add a source you found on your own, or an example or placeholder
  entry.
- Do not write an entry for a video without a transcript locator.
- Do not judge source quality beyond `role`.
- Do not change a `source_id` between passes.
