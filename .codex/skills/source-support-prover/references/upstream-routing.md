# Upstream routing

Consult this table when a finding implicates an upstream step. Cite a hash
from the prover packet that the named step produced. The table lists the
standard kinds; the actual checked step inputs bound which outputs are
available. The bound Success Spec is also supplied; a defect in that input
may implicate `spec` with its actual hash. With no such input, leave
`implicates` null.

| Kind | Upstream steps whose outputs `write` consumes |
|---|---|
| brief | retrieve, curate, outline |
| survey | retrieve, curate, taxonomy, outline, notes |
| ideas | retrieve, curate, signals, directions, screen |
| evidence-synthesis | protocol, retrieve, screen, extract, appraise |
| tutorial | manifest, ingest, concepts, plan |
| review | ingest, claims, audit, novelty |

An input gap routes upstream; a gap the writer can close using its inputs
stays on `write`. The kernel validates the step and producer of the cited
hash. Fault references remain unchanged. If repair targets an upstream step,
its own earlier outputs are excluded from cited Evidence; other steps'
outputs can still be provided as evidence of the downstream failure.
