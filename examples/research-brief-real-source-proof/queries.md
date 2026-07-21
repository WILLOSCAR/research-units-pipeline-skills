# Queries

> 写检索式（关键词/时间窗/排除词），并记录每次检索的变体与原因。
> 标量默认值应由当前 pipeline contract materialize；这里保持通用空模板。

## Primary query
- keywords:
  - "reliable adaptation of embodied agents under distribution shift"
  - "(all:robot OR all:robotic OR all:embodied) AND (all:adaptation OR all:shift OR all:sim-to-real OR all:continual OR all:out-of-distribution)"
  - "embodied agent adaptation"
  - "robot policy adaptation"
  - "robot learning distribution shift"
  - "robot domain adaptation"
  - "robot test-time adaptation"
  - "sim-to-real policy adaptation"
  - "continual robot learning"
  - "out-of-distribution robot policy"
- exclude:
  - "agent-based modeling"
  - "react hooks"
  - "perovskite"
  - "banach"
  - "coxeter"

# Retrieval + scaling knobs
- max_results: "80"
- core_size: "12"
- per_subsection: ""

# Citation-scope flexibility
- global_citation_min_subsections: ""

# Writing contract
- draft_profile: ""

# Global citation target policy
- citation_target: ""

# Metadata enrichment
- enrich_metadata: ""

# Evidence strength
- evidence_mode: ""
- fulltext_max_papers: ""
- fulltext_max_pages: ""
- fulltext_min_chars: ""

# Optional time window
- time window:
  - from: "2018"
  - to: ""

## Notes
- (fill) scope decisions / dataset constraints
