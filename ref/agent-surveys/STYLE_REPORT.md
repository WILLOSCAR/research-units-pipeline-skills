# Agent survey style report (auto)

- Papers: 11 (ok=11, error=0)

## Detected top-level section counts

- min/median/max: 3/6/10

## Per-paper detected headings (best-effort)

| arXiv | pages | #sections | headings (first 8) |
|---|---:|---:|---|
| 2508.17281 | 20 | 8 | 1 Introduction; 2 Related works; 3 Methodology; 5 External tool integration across; 6 Frameworks for building LLM; 7 Reasoning, planning, and memory; 8 Impact of prompting, fine-tuning,; 9 Evaluation |
| 2508.17692 | 20 | 4 | 1 Introduction; 2 Related Surveys; 3 Methods; 4 Scenarios |
| 2509.16325 | 12 | 8 | 1 Introduction; 2 Related Work; 3 Dimensions of Overhearing; 4 User Interaction With Overhearing Agents; 5 Overhearing System Architecture; 6 Developing Overhearing Agents; 7 Research Challenges and Future Directions; 8 Conclusion |
| 2509.16330 | 20 | 4 | 1 Introduction; 2 LLM-based Agents and Ecosystems; 3 Measuring LLM-based Agent Generalizability; 4 Improving LLM-Based Agent Generalizability via the Backbone LLM |
| 2512.22256 | 20 | 7 | 1 Introduction; 2 Background; 3 Survey Methodology; 4 Benchmarks; 5 Techniques; 9 Exec Filter; 13 Techniques |
| 2510.16720 | 20 | 3 | 1 Introduction; 2 Algorithm: RL for LLM; 3 Core Capability: Planning |
| 2510.17491 | 20 | 7 | 1 Empowering Real-World: A Survey on the; 3 Memory; 4 Industry Agent; 5 Memory Mechanism; 7 Planning Mechanism; 11 Process Execution Systems; 15 Evaluation of Fundamental Abilities |
| 2510.10991 | 20 | 6 | 1 A Survey on Agentic Multimodal Large; 2 Taxonomy; 3 MLLM Agent; 4 AGENTIC MLLM; 7 CHALLENGES AND FUTURE DIRECTIONS; 8 CONCLUSION |
| 2510.04023 | 20 | 5 | 1 INTRODUCTION; 2 BACKGROUND; 3 METHODOLOGY; 4 TAXONOMY OF AGENTIC AI SYSTEMS FOR DATA SCIENCE; 5 AGENTIC CAPABILITIES ACROSS THE DATA SCIENCE LIFECYCLE |
| 2509.18970 | 20 | 4 | 1 LLM-based Agents Suffer from Hallucinations: A; 5 Planning; 10 Knowledge Utilization; 12 Agent Hallucination |
| 2511.18538 | 20 | 10 | 1 Introduction; 2 Code Foundation Models; 3 Code Tasks, Benchmarks, and Evaluation; 5 Software Engineering Agents; 6 Code for Generalist Agents; 7 Safety of Code LLMs; 8 Training Recipes for Code Large Language Model; 9 Code Large Language Model for Applications … |

## How to use (for pipeline tuning)

- Target paper-like structure: ~6–8 top-level sections with fewer, thicker subsections.
- Front matter (Intro/Related Work) typically has higher citation density than a single H3 subsection.
- Use this report to sanity-check whether your generated outline and section sizing resembles real surveys.
