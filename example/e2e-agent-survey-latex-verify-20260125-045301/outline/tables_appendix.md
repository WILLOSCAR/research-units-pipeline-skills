**Appendix Table A1. Representative agent designs (loop + interface assumptions).**

| Work | Core idea | Loop and interface assumption | Key refs |
|---|---|---|---|
| AgentSwift | Automated agent discovery across diverse tasks | Closed-loop agent evaluated across multiple benchmark families | [@Li2025Agentswift] |
| AgentSquare | Unified evaluation across web, embodied, tool, and game settings | Environment/task suite treated as a shared action-space substrate | [@Shang2024Agentsquare] |
| ReAct | Interleave reasoning traces with actions | Prompted loop that alternates deliberation and tool/environment steps | [@Yao2022React] |
| Structured Cognitive Loop (SCL) | Modularize cognition into explicit phases | Loop decomposed into named stages (e.g., retrieval → reasoning → action) | [@Kim2025Bridging] |
| Progent | Defense wrapper for tool-using agents | Plugs into existing agents without changing internals (minimal integration) | [@Shi2025Progent] |
| Agent Distillation | Transfer full agent behavior to smaller models | Student learns task-solving behavior beyond single-step reasoning traces | [@Kang2025Distilling] |
| SAFE (fact-checking) | Retrieval-augmented agent for long-form verification | Loop couples retrieval with structured extraction/evaluation steps | [@Huang2025Retrieval] |
| Self-Challenging (tool use) | Stress-test + improve tool-use robustness | Iterative interaction where the agent generates and resolves harder tool calls | [@Zhou2025Self] |
| MemTool | Autonomous memory management for tool use | Memory operations are explicit actions; evaluated over long interaction traces | [@Lumer2025Memtool] |
| SkyRL-Agent | Multi-turn, long-horizon agent training/evaluation | Training and evaluation framed as long-horizon interaction episodes | [@Cao2025Skyrl] |

**Appendix Table A2. Benchmarks and evaluation protocols (task + metric + constraints).**

| Benchmark / setting | Task + metric (short) | Key protocol constraints | Key refs |
|---|---|---|---|
| MCPAgentBench | MCP tool-use capability; task success | Real-world MCP definitions; tool schema fidelity | [@Liu2025Mcpagentbench] |
| ETOM | Multi-hop end-to-end tool orchestration; success rate | Hierarchical MCP ecosystem; multi-step orchestration | [@Dong2025Etom] |
| ToolBench | Tool-use tasks; task completion | Tool availability + API behavior; model/tool mismatch | [@Zhou2026Beyond] |
| BFCL | Function-calling/tool-use; correctness | Long trajectories possible; cost/energy sensitivity under attacks | [@Zhou2026Beyond] |
| M3ToolEval | Multi-turn tool use; task success | Multi-turn interaction; tool calling under constraints | [@Zhou2025Self] |
| TauBench | Multi-turn tool use; task success | Multi-turn protocol; robustness across turns | [@Zhou2025Self] |
| ScaleMCP | Memory management in tool use; accuracy + tool removal ratio | Long interaction horizon; explicit memory operations | [@Lumer2025Memtool] |
| AgentDojo, ASB, and AgentPoison | Agent security; attack success vs utility | Threat-model assumptions; defense integration cost | [@Shi2025Progent] |
| RAS-Eval | Safety attack suite; robustness under attacks | CWE-mapped attack categories; tool-implemented adversaries | [@Fu2025Eval] |
| MSB (MCP Security Benchmark) | MCP-specific attacks; resistance | Name-collision/prompt-injection style attacks via tool metadata | [@Zhang2025Security] |
