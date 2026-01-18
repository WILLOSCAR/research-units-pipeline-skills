# PIPELINE_FLOWS

## Legend

- Required skill: solid node
- Optional skill: dashed node
- HUMAN checkpoint: red node

## arxiv-survey (C0–C5)

```mermaid
flowchart LR
  classDef optional stroke-dasharray: 5 5;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    WS[workspace-init]
    PR0[pipeline-router]
  end

  subgraph "C1 - Retrieval & core set"
    KX[keyword-expansion]:::optional
    LE[literature-engineer]
    DR[dedupe-rank]
    SSH[survey-seed-harvest]:::optional
  end

  subgraph "C2 - Structure [NO PROSE]"
    TB[taxonomy-builder]
    OB[outline-builder]
    OBU[outline-budgeter]:::optional
    SM[section-mapper]
    OR[outline-refiner]
    PR2[pipeline-router]
    C2A{{Approve C2 (HUMAN)}}:::human
  end

  subgraph "C3 - Evidence [NO PROSE]"
    PT[pdf-text-extractor]
    PN[paper-notes]
    SB[subsection-briefs]
    CB[chapter-briefs]
  end

  subgraph "C4 - Citations + visuals [NO PROSE]"
    CV[citation-verifier]
    EB[evidence-binder]
    ED[evidence-draft]
    AS[anchor-sheet]
    WCP[writer-context-pack]
    CMR[claim-matrix-rewriter]
    TS[table-schema]
    TF[table-filler]
    SV[survey-visuals]
  end

  subgraph "C5 - Writing [PROSE after C2]"
    SW[subsection-writer]
    SLP[section-logic-polisher]
    TW[transition-weaver]
    MG[section-merger]
    CD[citation-diversifier]
    CI[citation-injector]
    DP[draft-polisher]
    GR[global-reviewer]
    PA[pipeline-auditor]
    LS[latex-scaffold]:::optional
    LCQ[latex-compile-qa]:::optional
  end

  WS --> PR0 --> LE --> DR --> TB --> OB --> SM --> OR --> PR2 --> C2A --> PT --> PN --> SB --> CB --> CV --> EB --> ED --> AS --> WCP --> CMR --> TS --> TF --> SV --> SW --> SLP --> TW --> MG --> CD --> CI --> DP --> GR --> PA
  KX -.-> LE
  SSH -.-> TB
  OB -.-> OBU -.-> SM
  PA -.-> LS -.-> LCQ
```

## arxiv-survey-latex (C0–C5)

```mermaid
flowchart LR
  classDef optional stroke-dasharray: 5 5;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    WS[workspace-init]
    PR0[pipeline-router]
  end

  subgraph "C1 - Retrieval & core set"
    KX[keyword-expansion]:::optional
    LE[literature-engineer]
    DR[dedupe-rank]
    SSH[survey-seed-harvest]:::optional
  end

  subgraph "C2 - Structure [NO PROSE]"
    TB[taxonomy-builder]
    OB[outline-builder]
    OBU[outline-budgeter]:::optional
    SM[section-mapper]
    OR[outline-refiner]
    PR2[pipeline-router]
    C2A{{Approve C2 (HUMAN)}}:::human
  end

  subgraph "C3 - Evidence [NO PROSE]"
    PT[pdf-text-extractor]
    PN[paper-notes]
    SB[subsection-briefs]
    CB[chapter-briefs]
  end

  subgraph "C4 - Citations + visuals [NO PROSE]"
    CV[citation-verifier]
    EB[evidence-binder]
    ED[evidence-draft]
    AS[anchor-sheet]
    WCP[writer-context-pack]
    CMR[claim-matrix-rewriter]
    TS[table-schema]
    TF[table-filler]
    SV[survey-visuals]
  end

  subgraph "C5 - Writing + PDF [PROSE after C2]"
    SW[subsection-writer]
    SLP[section-logic-polisher]
    TW[transition-weaver]
    MG[section-merger]
    CD[citation-diversifier]
    CI[citation-injector]
    DP[draft-polisher]
    GR[global-reviewer]
    PA[pipeline-auditor]
    LS[latex-scaffold]
    LCQ[latex-compile-qa]
  end

  WS --> PR0 --> LE --> DR --> TB --> OB --> SM --> OR --> PR2 --> C2A --> PT --> PN --> SB --> CB --> CV --> EB --> ED --> AS --> WCP --> CMR --> TS --> TF --> SV --> SW --> SLP --> TW --> MG --> CD --> CI --> DP --> GR --> PA --> LS --> LCQ
  KX -.-> LE
  SSH -.-> TB
  OB -.-> OBU -.-> SM
```

## lit-snapshot (C0–C2)

```mermaid
flowchart LR
  classDef optional stroke-dasharray: 5 5;

  subgraph "C0 - Init"
    WS[workspace-init]
    PR0[pipeline-router]
  end

  subgraph "C1 - Retrieval"
    KX[keyword-expansion]:::optional
    AS[arxiv-search]
    DR[dedupe-rank]
  end

  subgraph "C2 - Structure + snapshot [NO LONG PROSE]"
    TB[taxonomy-builder]
    OB[outline-builder]
    PW[prose-writer]
  end

  WS --> PR0 --> AS --> DR --> TB --> OB --> PW
  KX -.-> AS
```

## tutorial (C0–C3)

```mermaid
flowchart LR
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    WS[workspace-init]
    PR0[pipeline-router]
  end

  subgraph "C1 - Spec"
    TS[tutorial-spec]
  end

  subgraph "C2 - Structure [NO PROSE]"
    CG[concept-graph]
    MP[module-planner]
    EB[exercise-builder]
    C2A{{Approve C2 (HUMAN)}}:::human
  end

  subgraph "C3 - Writing [PROSE]"
    TMW[tutorial-module-writer]
  end

  WS --> PR0 --> TS --> CG --> MP --> EB --> C2A --> TMW
```

## systematic-review (C0–C4)

```mermaid
flowchart LR
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    WS[workspace-init]
    PR0[pipeline-router]
  end

  subgraph "C1 - Protocol"
    PR[protocol-writer]
    C1A{{Approve C1 (HUMAN)}}:::human
  end

  subgraph "C2 - Screening"
    SCM[screening-manager]
  end

  subgraph "C3 - Extraction"
    EF[extraction-form]
    BA[bias-assessor]
  end

  subgraph "C4 - Synthesis [PROSE]"
    SW[synthesis-writer]
  end

  WS --> PR0 --> PR --> C1A --> SCM --> EF --> BA --> SW
```

## peer-review (C0–C3)

```mermaid
flowchart LR
  subgraph "C0 - Init"
    WS[workspace-init]
    PR0[pipeline-router]
  end

  subgraph "C1 - Claims"
    CE[claims-extractor]
  end

  subgraph "C2 - Evidence audit"
    EA[evidence-auditor]
    NM[novelty-matrix]
  end

  subgraph "C3 - Rubric write-up"
    RW[rubric-writer]
  end

  WS --> PR0 --> CE --> EA --> RW
  CE --> NM --> RW
```
