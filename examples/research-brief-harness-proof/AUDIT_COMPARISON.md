# Completion Protocol Comparison

This comparison uses two completed `research-brief` Workspaces:

- before: an earlier Run whose lock did not declare a Completion Protocol;
- after: the current proof Run declaring
  `recoverable-provenance.v1`.

| Signal | Before | After | Delta |
|---|---:|---:|---:|
| Audit verdict | `ATTENTION` | `PASS` | improved |
| DONE Units | 11 | 11 | 0 |
| Target Artifacts present | 19 | 19 | 0 |
| DONE Unit Manifests | 10 | 11 | +1 |
| Harness issues | 8 | 0 | -8 |
| Units with retries | 1 | 0 | -1 |
| Extra Attempts | 1 | 0 | -1 |
| Scripted Attempts with measured runtime | 0 | 9 | +9 |

The old Audit retained eight errors even though all Units and target Artifacts
appeared complete. Six issue types were compatibility-sensitive evidence gaps:

- `done_output_unregistered`;
- `done_without_manifest`;
- `done_without_successful_attempt`;
- `failure_resolution_type_mismatch`;
- `failure_resolution_unverified`;
- `manifest_artifact_hash_mismatch`.

The current Run has 11 successful Attempts, 11 final Manifests, no open
Attempts, no retries, and no cross-ledger integrity issues.

The `run-audit-diff.v1` verdict is PASS. Runtime deltas are descriptive only and
do not affect that verdict. The comparison supports the current Completion
Protocol's provenance claim; it does not compare source quality or establish
that the protocol alone caused a better research deliverable.
