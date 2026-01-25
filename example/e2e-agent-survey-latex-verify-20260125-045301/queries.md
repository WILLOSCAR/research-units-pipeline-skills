# Queries

> 写检索式（关键词/时间窗/排除词），并记录每次检索的变体与原因。

## Primary query
- keywords:
  - "agent survey latex"
  - "LLM agent"
  - "language model agent"
  - "tool use"
  - "function calling"
  - "tool-using agent"
  - "ReAct"
  - "Toolformer"
  - "Reflexion"
  - "AutoGPT"
  - "Voyager"
  - "Tree of Thoughts"
- exclude:
  - "agent-based modeling"
  - "react hooks"
  - "perovskite"
  - "banach"
  - "coxeter"
- max_results: "800"
- core_size: "220"
- per_subsection: ""         # section-mapper target papers per H3 (arxiv-survey default: 18)
- global_citation_min_subsections: ""  # treat citations mapped to >=N subsections as globally allowed for citation-scope checks (default: 3)
- draft_profile: survey    # survey | deep (default: survey deliverable, >=110 unique cites; deep is stricter and pairs best with fulltext)
- enrich_metadata: ""        # true|false; optional arXiv id_list backfill for offline imports (needs network)
- evidence_mode: "abstract"   # abstract | fulltext (abstract: metadata-only evidence; fulltext: download PDFs for stronger protocol/number anchoring)
- fulltext_max_papers: ""
- fulltext_max_pages: ""
- fulltext_min_chars: ""
- time window:
  - from: ""
  - to: ""

## Notes
- (fill) scope decisions / dataset constraints
