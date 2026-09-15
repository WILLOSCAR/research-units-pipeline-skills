---
name: source-ingest
description: Fetch every manifest.yml entry and write it as one faithful, citable Markdown file sources/<source_id>.md with front matter, headings preserved, and page or time anchors.
role: producer
reads: [manifest.yml]
outputs: [sources/]
---

# Source Ingest

The `ingest` step of the `tutorial` kind. For every entry in `manifest.yml`
it fetches the source, converts it to Markdown text without changing its
meaning, and writes `sources/<source_id>.md`. `concept-graph` and
`module-planner` point at this text by heading, page, time, or line anchors;
`tutorial-writer` quotes and condenses it; the `source-support` prover opens
the same file at the same anchors. The text must be faithful and its anchors
stable.

## Inputs

`manifest.yml` — `schema: rh.source_manifest/1`, `sources: [{source_id,
kind, locator, label, role, audience_note}]`. URL locators need network
access. `success_spec.yaml` is in the packet but is not needed here.

## Outputs

`sources/<source_id>.md`, one per manifest entry, UTF-8:

```markdown
---
source_id: retries-guide
title: Client retries guide
kind: html
locator: https://example.dev/docs/retries
ingested_at: 2026-09-13T10:42:00Z
---

# Client retries guide

## Retry policy

A retry budget bounds how many times the client re-sends a request …
```

- Front matter: `source_id` (equals the file stem and the manifest id),
  `title` (the document's own title, else the manifest `label`), `kind`,
  `locator`, `ingested_at` (ISO 8601, UTC).
- Body: the source's text in reading order; headings as Markdown headings,
  code as fenced blocks, tables as Markdown tables. Nothing summarised,
  paraphrased, translated, or reordered.
- Anchors later steps use as locators: a heading line verbatim
  (`## Retry policy`); `<!-- page N -->` alone on a line at each PDF page
  start (cited as `p.N`); `[mm:ss]` at the start of each transcript paragraph
  (cited as `[mm:ss]`); the file's own line numbers (`L40-L46`).
- Kernel checks on this step: the integrity check (`outputs/sources/` holds
  at least one file). `schema-valid` is bound but does not parse `.md`;
  `scaffold-absent` is not bound, so `TODO` inside ingested code stays as it
  is.

## Method

By `kind`:

1. `pdf` — `pdftotext -layout <file> -`, or PyMuPDF when available (use font
   size to recover headings). Re-join words hyphenated across lines, drop
   running headers and footers, keep figure and table captions, insert
   `<!-- page N -->` at each page start.
2. `html` — fetch the page; keep the main content; drop navigation,
   sidebars, footers, cookie banners, scripts, styles. Map `h1`–`h6` to
   `#`–`######`; keep lists, code blocks, tables, and link text (drop link
   targets unless the text is the URL).
3. `md` — copy the text; normalise line endings; keep headings as they are.
4. `repo` — ingest only what the locator names: the README and, after `#`,
   the named path. A code file is one section headed by its path
   (`## src/client/retry.py`) followed by one fenced block; a directory is
   one such section per file, in path order. Never the whole tree.
5. `video-transcript` — read the subtitle or transcript file, merge cues into
   paragraphs at pauses or speaker changes, start each paragraph with its
   `[mm:ss]` anchor.

Rules: one entry, one file. A source that cannot be fetched or yields no text
gets no file — try another route first (direct download, a cached copy, a
raw-content URL); if it still fails, leave it out and, when the entry is
`primary`, run `rh escalate --reason` naming it, since nothing can teach from
it. Keep headings verbatim, one blank line between paragraphs, no re-wrapping
of lines. Keep warnings, deprecation notes, and version banners. Preserve code
whitespace exactly; the writer's `quotes` relation depends on it.

## Repair

A Fault routed here (`source-support` or `spec-coverage` with
`implicates: ingest`, citing one `sources/<file>`) says the file is empty,
truncated, the wrong document, or lacks the passage a locator names. Re-fetch
that entry by another route and write the whole `outputs/sources/` again;
entries the manifest did not change come out with the same headings and
anchors, because every downstream step re-runs from this text.

## Do not

- Do not select what to teach, extract concepts, or plan modules.
- Do not ingest a source the manifest does not list, or re-decide an
  entry's `kind`.
- Do not write a stub, a summary from memory, or a copy of the manifest entry
  in place of text you could not fetch.
- Do not add commentary, notes, or ratings inside a source file.
- Do not strip body content that looks like boilerplate but carries meaning
  (warnings, version notes, deprecations).
