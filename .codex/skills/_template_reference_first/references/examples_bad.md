# Bad examples

Read once when authoring; each is a pattern the standard rejects and why.

## Restating the packet

```markdown
## How this step is worked
The harness writes `steps/<step>/pass-<n>/packet.json` with `schema`,
`run_id`, `pass_id`, `inputs [{name, path, hash}]`, `budget {...}` …
1. Read the packet. 2. Write `outputs/<name>`. 3. Run `rh continue`.
```

`packet.md § Instructions` already says this; thirty lines per Skill go
stale the day `steps.py` changes.

## Inventing kernel behavior

```markdown
The Fault the repairer sees joins the findings' messages with `; ` and
keeps the first 600 characters, so put the most important finding first.
```

`faults.from_result` makes one Fault per finding, message verbatim. A kernel
claim `src/rh/kernel/*.py` does not support is a bug in the Skill.

## A finding without grounds

```json
{"message": "s3 overstates the result.", "evidence": ["<sha256 of brief.md>"]}
```

This locates the claim but does not explain or cite what contradicts it.
For a source-support failure, add the source hash and what the passage
actually says; name `s3` through `statement`. The kernel keeps the draft
hash in the Fault but excludes prior outputs of the repaired step from
its cited Evidence. Coverage findings may cite a deliverable to show an omission.

## Self-verification

```markdown
After writing, check the table against the criteria and append `Quality: OK`.
```

A producer's verdict is not Evidence; gates and provers verify.

## Vague output, soft method

```markdown
## Outputs
- a notes file for later steps
## Method
Consider merging directions that seem similar; keep a reasonable number.
```

No file name, format, or example to write the next Skill against; no rule
or count, so two agents produce two tables. The same goes for "leave `TODO`
where a source is missing": `scaffold-absent` fails the step on the token.
