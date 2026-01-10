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
    SM[section-mapper]
    C2A{{Approve C2 (HUMAN)}}:::human
  end

  subgraph "C3 - Evidence [NO PROSE]"
    PT[pdf-text-extractor]
    PN[paper-notes]
    SB[subsection-briefs]
  end

  subgraph "C4 - Citations + visuals [NO PROSE]"
    CV[citation-verifier]
    ED[evidence-draft]
    CMR[claim-matrix-rewriter]
    TS[table-schema]
    TF[table-filler]
    SV[survey-visuals]
  end

  subgraph "C5 - Writing [PROSE after C2]"
    TW[transition-weaver]
    PW[prose-writer]
    DP[draft-polisher]
    GR[global-reviewer]
    LS[latex-scaffold]:::optional
    LCQ[latex-compile-qa]:::optional
  end

  WS --> LE --> DR --> TB --> OB --> SM --> C2A --> PT --> PN --> SB --> CV --> ED --> CMR --> TS --> TF --> SV --> TW --> PW --> DP --> GR
  KX -.-> LE
  SSH -.-> TB
  GR -.-> LS -.-> LCQ
```

## arxiv-survey-latex (C0–C5)

```mermaid
flowchart LR
  classDef optional stroke-dasharray: 5 5;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    WS[workspace-init]
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
    SM[section-mapper]
    C2A{{Approve C2 (HUMAN)}}:::human
  end

  subgraph "C3 - Evidence [NO PROSE]"
    PT[pdf-text-extractor]
    PN[paper-notes]
    SB[subsection-briefs]
  end

  subgraph "C4 - Citations + visuals [NO PROSE]"
    CV[citation-verifier]
    ED[evidence-draft]
    CMR[claim-matrix-rewriter]
    TS[table-schema]
    TF[table-filler]
    SV[survey-visuals]
  end

  subgraph "C5 - Writing + PDF [PROSE after C2]"
    TW[transition-weaver]
    PW[prose-writer]
    DP[draft-polisher]
    GR[global-reviewer]
    LS[latex-scaffold]
    LCQ[latex-compile-qa]
  end

  WS --> LE --> DR --> TB --> OB --> SM --> C2A --> PT --> PN --> SB --> CV --> ED --> CMR --> TS --> TF --> SV --> TW --> PW --> DP --> GR --> LS --> LCQ
  KX -.-> LE
  SSH -.-> TB
```

## tutorial (C0–C3)

```mermaid
flowchart LR
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    WS[workspace-init]
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

  WS --> TS --> CG --> MP --> EB --> C2A --> TMW
```

## systematic-review (C0–C4)

```mermaid
flowchart LR
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    WS[workspace-init]
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

  WS --> PR --> C1A --> SCM --> EF --> BA --> SW
```

## peer-review (C0–C3)

```mermaid
flowchart LR
  subgraph "C0 - Init"
    WS[workspace-init]
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

  WS --> CE --> EA --> RW
  CE --> NM --> RW
```
