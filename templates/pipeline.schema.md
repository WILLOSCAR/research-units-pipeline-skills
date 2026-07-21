# Pipeline spec v2 (frontmatter-first)

Every pipeline file lives under `pipelines/*.pipeline.md` and must start with YAML frontmatter.

## Parse boundary

Machine-readable contract data lives in frontmatter only.
Markdown body is explanatory only.

During the transition, legacy body-stage blocks may still exist, but new metadata-first pipelines should put their executable stage contract in frontmatter `stages`.

## Frontmatter (required)

Base pipeline:

```yaml
---
contract_model: pipeline.frontmatter/v1
name: <pipeline-name>
version: <int-or-string>
profile: <pipeline-family>
units_template: templates/<UNITS-template>.csv
default_checkpoints: [C0, C1, C2]
target_artifacts:
  - <path>
structure_mode: default | section_first
pre_retrieval_shell:
  enabled: true
  approval_surface: false
  allowed_h2: [Introduction, Related Work, Core Chapters, Discussion, Conclusion]
binding_layers: [chapter_skeleton, section_bindings, section_briefs, subsection_mapping]
core_chapter_h3_target: 3

routing_hints: [<hint>]
routing_default: false
routing_priority: 0

query_defaults:
  <key>: <value>
overridable_query_fields:
  - <query-key>

quality_contract:
  completion_policy:
    required_checks: [<required-skill-with-registered-checker>]
  <policy>: <value>
loop_policy:
  stage_retry_budget:
    C1: 2

stages:
  C0:
    title: Init
    mode: no_prose | short_prose_ok | prose_allowed
    required_skills: [workspace-init, pipeline-router]
    optional_skills: []
    produces:
      - STATUS.md
    human_checkpoint:
      approve: <short-approval-label>
      write_to: DECISIONS.md
---
```

Variant pipeline:

```yaml
---
name: <variant-name>
version: <int-or-string>
variant_of: <base-pipeline-name-or-path>
variant_overrides:
  units_template: templates/<variant-UNITS-template>.csv
  target_artifacts:
    __append__:
      - <variant-artifact>
  stages:
    C5:
      required_skills:
        __append__:
          - <required-skill-added-by-variant>
      optional_skills:
        __remove__:
          - <skill-no-longer-optional-in-variant>
      produces:
        __append__:
          - <variant-output>
---
```

## Contract rules

- `contract_model` must be `pipeline.frontmatter/v1`.
- `units_template` must exist.
- `default_checkpoints` must match the ordered `stages` keys exactly.
- Every stage must define non-empty `required_skills` and `produces`.
- If a stage has `human_checkpoint`, it must write to `DECISIONS.md`.
- `target_artifacts` must be covered by stage outputs; units-template coverage is also expected and is checked separately by repo validation.
- `quality_contract.completion_policy.required_checks` names the required Workflow Skills whose registered Harness checks must pass before a Unit can become `DONE`, including default and manual completion paths.
- Every required completion check must be a required Skill in the resolved Workflow and must exist in the Harness quality-check registry.
- `structure_mode: section_first` requires:
  - `pre_retrieval_shell`
  - `binding_layers`
  - positive `core_chapter_h3_target`
  - target artifacts for `chapter_skeleton`, `section_bindings`, `section_binding_report`, `section_briefs`, `outline`, and `outline_state`
- `variant_of` pipelines are resolved by:
  1. loading the base pipeline
  2. deep-merging mappings
  3. replacing scalar fields
  4. replacing list fields by default, unless the override uses list-patch operators
  5. validating the resolved contract
- List-patch operators are:
  - `__append__`: add items to the end of the inherited list
  - `__prepend__`: add items to the beginning of the inherited list
  - `__remove__`: remove inherited items by exact value
  - `__replace__`: replace the inherited list entirely
- Variant files may keep only `name`, `version`, `variant_of`, and `variant_overrides` at top level. Any other behavior-changing field must live under `variant_overrides`.
- If no list-patch operator is used, list overrides still replace wholesale.

## Legacy compatibility

- `scripts/validate_repo.py` still accepts old Markdown body-stage blocks for pipelines that do not set `contract_model`.
- `PipelineSpec.load()` is frontmatter-only and does not load body-only legacy pipeline specs.
- New metadata-first pipelines should treat body-stage blocks as explanation only, not as the canonical stage contract.
