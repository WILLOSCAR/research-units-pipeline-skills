# Claim–Evidence matrix

This artifact is bullets-only and is meant to make evidence explicit before writing.

Generated as a projection of `outline/evidence_drafts.jsonl` (evidence packs).

## 3.1 Agent loop and action spaces

- RQ: Which design choices in Agent loop and action spaces drive the major trade-offs, and how are those trade-offs measured?
- Claim: We introduce Structured Cognitive Loop (SCL), a modular architecture that explicitly separates agent cognition into five phases: Retrieval, Cognition, Control, Action, and Memory (R-CCAM).
  - Axes: mechanism / architecture; data / training setup; evaluation protocol (datasets / metrics / human); efficiency / compute; failure modes / limitations
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0022` [@Kim2025Bridging] — We introduce Structured Cognitive Loop (SCL), a modular architecture that explicitly separates agent cognition into five phases: Retrieval, Cognition, Control, Action, and Memory (R-CCAM). (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0022#method)
  - Evidence: `P0165` [@Zhao2025Achieving] — However, due to weak heuristics for auxiliary constructions, AI for geometry problem solving remains dominated by expert models such as AlphaGeometry 2, which rely heavily on large-scale data synthesis and search for both training and evaluation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0165#key_results[0])
  - Evidence: `P0085` [@Liu2025Mcpagentbench] — To address these limitations, we propose MCPAgentBench, a benchmark based on real-world MCP definitions designed to evaluate the tool-use capabilities of agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0085#limitations[1])
  - Evidence: `P0058` [@Li2025Agentswift] — Evaluated across a comprehensive set of seven benchmarks spanning embodied, math, web, tool, and game domains, AgentSwift discovers agents that achieve an average performance gain of 8.34\% over both existing automated agent search methods and manually designed agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0058#key_results[0])
  - Evidence: `P0070` [@Fumero2025Cybersleuth] — We benchmark four agent architectures and six LLM backends on 20 incident scenarios of increasing complexity, identifying CyberSleuth as the best-performing design. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0070#key_results[0])
  - Evidence: `P0081` [@Feng2025Group] — We evaluate GiGPO on challenging agent benchmarks, including ALFWorld and WebShop, as well as tool-integrated reasoning on search-augmented QA tasks, using Qwen2.5-1.5B/3B/7B-Instruct. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0081#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 3.2 Tool interfaces and orchestration

- RQ: Which design choices in Tool interfaces and orchestration drive the major trade-offs, and how are those trade-offs measured?
- Claim: We introduce MSC-Bench, a large-scale benchmark for evaluating multi-hop, end-to-end tool orchestration by LLM agents in a hierarchical Model-Context Protocol (MCP) ecosystem.
  - Axes: tool interface (function calling, schemas, protocols); tool selection / routing policy; sandboxing / permissions / observability; mechanism / architecture; data / training setup
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0086` [@Dong2025Bench] — We introduce MSC-Bench, a large-scale benchmark for evaluating multi-hop, end-to-end tool orchestration by LLM agents in a hierarchical Model-Context Protocol (MCP) ecosystem. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0086#method)
  - Evidence: `P0220` [@Li2025Dissonances] — Our evaluation of 66 real-world tools from the repositories of two major LLM agent development frameworks, LangChain and LlamaIndex, revealed a significant security concern: 75% are vulnerable to XTHP attacks, highlighting the prevalence of this threat. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0220#key_results[0])
  - Evidence: `P0040` [@Du2024Anytool] — We also revisit the evaluation protocol introduced by previous works and identify a limitation in this protocol that leads to an artificially high pass rate. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0040#limitations[1])
  - Evidence: `P0136` [@Fu2024Imprompter] — This attack shows a nearly 80% success rate in an end-to-end evaluation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0136#key_results[0])
  - Evidence: `P0032` [@Zhou2025Self] — Evaluation on two existing multi-turn tool-use agent benchmarks, M3ToolEval and TauBench, shows the Self-Challenging framework achieves over a two-fold improvement in Llama-3.1-8B-Instruct, despite using only self-generated training data. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0032#key_results[0])
  - Evidence: `P0076` [@Mohammadi2025Evaluation] — This survey provides an in-depth overview of the emerging field of LLM agent evaluation, introducing a two-dimensional taxonomy that organizes existing work along (1) evaluation objectives -- what to evaluate, such as agent behavior, capabilities, reliability, and safety -- and (2) evaluation process -- how to evaluate, including interaction modes, datasets and benchmarks, metric computation methods, and tooling. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0076#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 4.1 Planning and reasoning loops

- RQ: Which design choices in Planning and reasoning loops drive the major trade-offs, and how are those trade-offs measured?
- Claim: We introduce Structured Cognitive Loop (SCL), a modular architecture that explicitly separates agent cognition into five phases: Retrieval, Cognition, Control, Action, and Memory (R-CCAM).
  - Axes: control loop design (planner / executor, search); deliberation method (CoT / ToT / MCTS); action grounding (tool calls vs environment actions); mechanism / architecture; data / training setup
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0022` [@Kim2025Bridging] — We introduce Structured Cognitive Loop (SCL), a modular architecture that explicitly separates agent cognition into five phases: Retrieval, Cognition, Control, Action, and Memory (R-CCAM). (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0022#method)
  - Evidence: `P0121` [@Shang2024Agentsquare] — Extensive experiments across six benchmarks, covering the diverse scenarios of web, embodied, tool use and game applications, show that AgentSquare substantially outperforms hand-crafted agents, achieving an average performance gain of 17.2% against best-known human designs. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0121#key_results[0])
  - Evidence: `P0098` [@Choi2025Reactree] — To address this limitation, we propose ReAcTree, a hierarchical task-planning method that decomposes a complex goal into more manageable subgoals within a dynamically constructed agent tree. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0098#limitations[1])
  - Evidence: `P0001` [@Yao2022React] — On two interactive decision making benchmarks (ALFWorld and WebShop), ReAct outperforms imitation and reinforcement learning methods by an absolute success rate of 34% and 10% respectively, while being prompted with only one or two in-context examples. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0001#key_results[0])
  - Evidence: `P0114` [@Hu2025Training] — Experimental evaluation on the complex task planning benchmark demonstrates that our 1.5B parameter model trained with single-turn GRPO achieves superior performance compared to larger baseline models up to 14B parameters, with success rates of 70% for long-horizon planning tasks. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0114#key_results[0])
  - Evidence: `P0129` [@Shi2024Ehragent] — Experiments on three real-world multi-tabular EHR datasets show that EHRAgent outperforms the strongest baseline by up to 29.6% in success rate. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0129#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 4.2 Memory and retrieval (RAG)

- RQ: Which design choices in Memory and retrieval (RAG) drive the major trade-offs, and how are those trade-offs measured?
- Claim: In this paper, we propose a multi-agent system to localize bugs in large pre-existing codebases using information retrieval and LLMs.
  - Axes: memory type (episodic / semantic / scratchpad); retrieval source + index (docs / web / logs); write / update / forgetting policy; mechanism / architecture; data / training setup
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0028` [@Tawosi2025Meta] — In this paper, we propose a multi-agent system to localize bugs in large pre-existing codebases using information retrieval and LLMs. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0028#method)
  - Evidence: `P0028` [@Tawosi2025Meta] — Our system introduces a novel Retrieval Augmented Generation (RAG) approach, Meta-RAG, where we utilize summaries to condense codebases by an average of 79.8\%, into a compact, structured, natural language representation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0028#key_results[1])
  - Evidence: `P0116` [@Huang2025Retrieval] — SAFE demonstrates robust improvements in long-form COVID-19 fact-checking by addressing LLM limitations in consistency and explainability. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0116#limitations[1])
  - Evidence: `P0058` [@Li2025Agentswift] — Evaluated across a comprehensive set of seven benchmarks spanning embodied, math, web, tool, and game domains, AgentSwift discovers agents that achieve an average performance gain of 8.34\% over both existing automated agent search methods and manually designed agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0058#key_results[0])
  - Evidence: `P0001` [@Yao2022React] — On two interactive decision making benchmarks (ALFWorld and WebShop), ReAct outperforms imitation and reinforcement learning methods by an absolute success rate of 34% and 10% respectively, while being prompted with only one or two in-context examples. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0001#key_results[0])
  - Evidence: `P0029` [@Shi2025Progent] — Our extensive evaluation across various agent use cases, using benchmarks like AgentDojo, ASB, and AgentPoison, demonstrates that Progent reduces attack success rates to 0%, while preserving agent utility and speed. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0029#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 5.1 Self-improvement and adaptation

- RQ: Which design choices in Self-improvement and adaptation drive the major trade-offs, and how are those trade-offs measured?
- Claim: We demonstrate that large language model (LLM) agents can autonomously perform tensor network simulations of quantum many-body systems, achieving approximately 90% success rate across representative benchmark tasks.
  - Axes: training signal (SFT / preference / RL); data synthesis + evaluator / reward; generalization + regression control; mechanism / architecture; data / training setup
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0048` [@Li2026Autonomous] — We demonstrate that large language model (LLM) agents can autonomously perform tensor network simulations of quantum many-body systems, achieving approximately 90% success rate across representative benchmark tasks. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0048#method)
  - Evidence: `P0165` [@Zhao2025Achieving] — However, due to weak heuristics for auxiliary constructions, AI for geometry problem solving remains dominated by expert models such as AlphaGeometry 2, which rely heavily on large-scale data synthesis and search for both training and evaluation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0165#key_results[0])
  - Evidence: `P0040` [@Du2024Anytool] — We also revisit the evaluation protocol introduced by previous works and identify a limitation in this protocol that leads to an artificially high pass rate. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0040#limitations[1])
  - Evidence: `P0032` [@Zhou2025Self] — Evaluation on two existing multi-turn tool-use agent benchmarks, M3ToolEval and TauBench, shows the Self-Challenging framework achieves over a two-fold improvement in Llama-3.1-8B-Instruct, despite using only self-generated training data. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0032#key_results[0])
  - Evidence: `P0048` [@Li2026Autonomous] — Systematic evaluation using DeepSeek-V3.2, Gemini 2.5 Pro, and Claude Opus 4.5 demonstrates that both in-context learning and multi-agent architecture are essential. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0048#key_results[1])
  - Evidence: `P0001` [@Yao2022React] — On two interactive decision making benchmarks (ALFWorld and WebShop), ReAct outperforms imitation and reinforcement learning methods by an absolute success rate of 34% and 10% respectively, while being prompted with only one or two in-context examples. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0001#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 5.2 Multi-agent coordination

- RQ: Which design choices in Multi-agent coordination drive the major trade-offs, and how are those trade-offs measured?
- Claim: To bridge this gap, we introduce DEBATE, the first large-scale empirical benchmark explicitly designed to evaluate the authenticity of the interaction between multi-agent role-playing LLMs.
  - Axes: communication protocol + role assignment; aggregation (vote / debate / referee); stability (collusion, mode collapse, incentives); mechanism / architecture; data / training setup
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0187` [@Chuang2025Debate] — To bridge this gap, we introduce DEBATE, the first large-scale empirical benchmark explicitly designed to evaluate the authenticity of the interaction between multi-agent role-playing LLMs. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0187#method)
  - Evidence: `P0065` [@Silva2025Agents] — This study offers new insights into the strengths and failure modes of LLMs in physically grounded multi-agent collaboration tasks, contributing to future benchmarks and architectural improvements. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0065#key_results[1])
  - Evidence: `P0142` [@Shen2024Small] — While traditional works focus on training a single LLM with all these capabilities, performance limitations become apparent, particularly with smaller models. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0142#limitations[1])
  - Evidence: `P0181` [@Wu2025Agents] — We address this question through a controlled study using the Knight--Knave--Spy logic puzzle, which enables precise, step-wise evaluation of debate outcomes and processes under verifiable ground truth. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0181#key_results[0])
  - Evidence: `P0065` [@Silva2025Agents] — We systematically evaluate their performance using a suite of coordination-sensitive metrics, including task success rate, redundant actions, room conflicts, and urgency-weighted efficiency. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0065#key_results[0])
  - Evidence: `P0142` [@Shen2024Small] — Evaluation across various tool-use benchmarks illustrates that our proposed multi-LLM framework surpasses the traditional single-LLM approach, highlighting its efficacy and advantages in tool learning. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0142#key_results[1])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 6.1 Benchmarks and evaluation protocols

- RQ: Which design choices in Benchmarks and evaluation protocols drive the major trade-offs, and how are those trade-offs measured?
- Claim: We present MSB (MCP Security Benchmark), the first end-to-end evaluation suite that systematically measures how well LLM agents resist MCP-specific attacks throughout the full tool-use pipeline: task planning, tool invoc
  - Axes: tool interface (function calling, schemas, protocols); tool selection / routing policy; sandboxing / permissions / observability; task suites (web / code / embodied / tools); metrics (success, cost, reliability, safety)
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0083` [@Zhang2025Security] — We present MSB (MCP Security Benchmark), the first end-to-end evaluation suite that systematically measures how well LLM agents resist MCP-specific attacks throughout the full tool-use pipeline: task planning, tool invocation, and response handling. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0083#method)
  - Evidence: `P0083` [@Zhang2025Security] — MSB contributes: (1) a taxonomy of 12 attacks including name-collision, preference manipulation, prompt injections embedded in tool descriptions, out-of-scope parameter requests, user-impersonating responses, false-error escalation, tool-transfer, retrieval injection, and mixed attacks; (2) an evaluation harness that executes attacks by running real tools (both benign and malicious) via MCP rather than simulation; and (3) a robustness metric that quantifies the trade-off between security and performance: Net Resilient Performance (NRP). (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0083#key_results[0])
  - Evidence: `P0006` [@Plaat2025Agentic] — We note that there is risk associated with LLM assistants taking action in the real world-safety, liability and security are open problems-while agentic LLMs are also likely to benefit society. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0006#limitations[1])
  - Evidence: `P0096` [@Fu2025Eval] — RAS-Eval comprises 80 test cases and 3,802 attack tasks mapped to 11 Common Weakness Enumeration (CWE) categories, with tools implemented in JSON, LangGraph, and Model Context Protocol (MCP) formats. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0096#key_results[1])
  - Evidence: `P0099` [@Kale2025Reliable] — To this end, we systematize a monitor red teaming (MRT) workflow that incorporates: (1) varying levels of agent and monitor situational awareness; (2) distinct adversarial strategies to evade the monitor, such as prompt injection; and (3) two datasets and environments -- SHADE-Arena for tool-calling agents and our new CUA-SHADE-Arena, which extends TheAgentCompany, for computer-use agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0099#key_results[0])
  - Evidence: `P0083` [@Zhang2025Security] — We evaluate nine popular LLM agents across 10 domains and 400+ tools, producing 2,000 attack instances. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0083#key_results[1])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 6.2 Safety, security, and governance

- RQ: Which design choices in Safety, security, and governance drive the major trade-offs, and how are those trade-offs measured?
- Claim: We present MSB (MCP Security Benchmark), the first end-to-end evaluation suite that systematically measures how well LLM agents resist MCP-specific attacks throughout the full tool-use pipeline: task planning, tool invoc
  - Axes: threat model (prompt / tool injection, exfiltration); defense surface (policy, sandbox, monitoring); security evaluation protocol; mechanism / architecture; data / training setup
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0083` [@Zhang2025Security] — We present MSB (MCP Security Benchmark), the first end-to-end evaluation suite that systematically measures how well LLM agents resist MCP-specific attacks throughout the full tool-use pipeline: task planning, tool invocation, and response handling. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0083#method)
  - Evidence: `P0083` [@Zhang2025Security] — MSB contributes: (1) a taxonomy of 12 attacks including name-collision, preference manipulation, prompt injections embedded in tool descriptions, out-of-scope parameter requests, user-impersonating responses, false-error escalation, tool-transfer, retrieval injection, and mixed attacks; (2) an evaluation harness that executes attacks by running real tools (both benign and malicious) via MCP rather than simulation; and (3) a robustness metric that quantifies the trade-off between security and performance: Net Resilient Performance (NRP). (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0083#key_results[0])
  - Evidence: `P0193` [@Lichkovski2025Agent] — We encourage future work extending agentic safety benchmarks to different legal jurisdictions and to multi-turn and multilingual interactions. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0193#limitations[1])
  - Evidence: `P0099` [@Kale2025Reliable] — To this end, we systematize a monitor red teaming (MRT) workflow that incorporates: (1) varying levels of agent and monitor situational awareness; (2) distinct adversarial strategies to evade the monitor, such as prompt injection; and (3) two datasets and environments -- SHADE-Arena for tool-calling agents and our new CUA-SHADE-Arena, which extends TheAgentCompany, for computer-use agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0099#key_results[0])
  - Evidence: `P0096` [@Fu2025Eval] — RAS-Eval comprises 80 test cases and 3,802 attack tasks mapped to 11 Common Weakness Enumeration (CWE) categories, with tools implemented in JSON, LangGraph, and Model Context Protocol (MCP) formats. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0096#key_results[1])
  - Evidence: `P0083` [@Zhang2025Security] — We evaluate nine popular LLM agents across 10 domains and 400+ tools, producing 2,000 attack instances. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0083#key_results[1])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.
