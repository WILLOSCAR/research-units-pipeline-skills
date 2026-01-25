# Claim–Evidence matrix

This artifact is bullets-only and is meant to make evidence explicit before writing.

Generated as a projection of `outline/evidence_drafts.jsonl` (evidence packs).

## 3.1 Agent loop and action spaces

- RQ: Which design choices in Agent loop and action spaces drive the major trade-offs, and how are those trade-offs measured?
- Claim: Evaluated across a comprehensive set of seven benchmarks spanning embodied, math, web, tool, and game domains, AgentSwift discovers agents that achieve an average performance gain of 8.34\% over both existing automated a
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; tool interface contract (schemas / protocols); tool selection / routing policy; sandboxing / permissions / observability
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0070` [@Li2025Agentswift] — Evaluated across a comprehensive set of seven benchmarks spanning embodied, math, web, tool, and game domains, AgentSwift discovers agents that achieve an average performance gain of 8.34\% over both existing automated agent search methods and manually designed agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0070#key_results[0])
  - Evidence: `P0099` [@Liu2025Mcpagentbench] — To address these limitations, we propose MCPAgentBench, a benchmark based on real-world MCP definitions designed to evaluate the tool-use capabilities of agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0099#method)
  - Evidence: `P0099` [@Liu2025Mcpagentbench] — To address these limitations, we propose MCPAgentBench, a benchmark based on real-world MCP definitions designed to evaluate the tool-use capabilities of agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0099#limitations[1])
  - Evidence: `P0136` [@Shang2024Agentsquare] — Extensive experiments across six benchmarks, covering the diverse scenarios of web, embodied, tool use and game applications, show that AgentSquare substantially outperforms hand-crafted agents, achieving an average performance gain of 17.2% against best-known human designs. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0136#key_results[0])
  - Evidence: `P0095` [@Feng2025Group] — We evaluate GiGPO on challenging agent benchmarks, including ALFWorld and WebShop, as well as tool-integrated reasoning on search-augmented QA tasks, using Qwen2.5-1.5B/3B/7B-Instruct. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0095#key_results[0])
  - Evidence: `P0181` [@Xi2026Toolgym] — Comprehensive evaluation of state-of-the-art LLMs reveals the misalignment between tool planning and execution abilities, the constraint following weakness of existing LLMs, and DeepSeek-v3.2's strongest robustness. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0181#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 3.2 Tool interfaces and orchestration

- RQ: Which design choices in Tool interfaces and orchestration drive the major trade-offs, and how are those trade-offs measured?
- Claim: Across six LLMs on the ToolBench and BFCL benchmarks, our attack expands tasks into trajectories exceeding 60,000 tokens, inflates costs by up to 658x, and raises energy by 100-560x.
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; tool interface contract (schemas / protocols); tool selection / routing policy; sandboxing / permissions / observability
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0011` [@Zhou2026Beyond] — Across six LLMs on the ToolBench and BFCL benchmarks, our attack expands tasks into trajectories exceeding 60,000 tokens, inflates costs by up to 658x, and raises energy by 100-560x. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0011#key_results[0])
  - Evidence: `P0085` [@Dong2025Etom] — We introduce ETOM, a five-level benchmark for evaluating multi-hop, end-to-end tool orchestration by LLM agents within a hierarchical Model-Context Protocol (MCP) ecosystem. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0085#method)
  - Evidence: `P0046` [@Du2024Anytool] — We also revisit the evaluation protocol introduced by previous works and identify a limitation in this protocol that leads to an artificially high pass rate. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0046#limitations[1])
  - Evidence: `P0036` [@Zhou2025Self] — Evaluation on two existing multi-turn tool-use agent benchmarks, M3ToolEval and TauBench, shows the Self-Challenging framework achieves over a two-fold improvement in Llama-3.1-8B-Instruct, despite using only self-generated training data. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0036#key_results[0])
  - Evidence: `P0128` [@Liu2025Toolscope] — Evaluations on three state-of-the-art LLMs and three open-source tool-use benchmarks show gains of 8.38% to 38.6% in tool selection accuracy, demonstrating ToolScope's effectiveness in enhancing LLM tool use. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0128#key_results[0])
  - Evidence: `P0046` [@Du2024Anytool] — Experiments across various datasets demonstrate the superiority of our AnyTool over strong baselines such as ToolLLM and a GPT-4 variant tailored for tool utilization. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0046#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 4.1 Planning and reasoning loops

- RQ: Which design choices in Planning and reasoning loops drive the major trade-offs, and how are those trade-offs measured?
- Claim: Our extensive evaluation across various agent use cases, using benchmarks like AgentDojo, ASB, and AgentPoison, demonstrates that Progent reduces attack success rates to 0%, while preserving agent utility and speed.
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; tool interface contract (schemas / protocols); tool selection / routing policy; sandboxing / permissions / observability
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0033` [@Shi2025Progent] — Our extensive evaluation across various agent use cases, using benchmarks like AgentDojo, ASB, and AgentPoison, demonstrates that Progent reduces attack success rates to 0%, while preserving agent utility and speed. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0033#key_results[0])
  - Evidence: `P0024` [@Kim2025Bridging] — We introduce Structured Cognitive Loop (SCL), a modular architecture that explicitly separates agent cognition into five phases: Retrieval, Cognition, Control, Action, and Memory (R-CCAM). (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0024#method)
  - Evidence: `P0033` [@Shi2025Progent] — Thanks to our modular design, integrating Progent does not alter agent internals and only requires minimal changes to the existing agent implementation, enhancing its practicality and potential for widespread adoption. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0033#limitations[1])
  - Evidence: `P0130` [@Hu2025Training] — Experimental evaluation on the complex task planning benchmark demonstrates that our 1.5B parameter model trained with single-turn GRPO achieves superior performance compared to larger baseline models up to 14B parameters, with success rates of 70% for long-horizon planning tasks. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0130#key_results[0])
  - Evidence: `P0001` [@Yao2022React] — On two interactive decision making benchmarks (ALFWorld and WebShop), ReAct outperforms imitation and reinforcement learning methods by an absolute success rate of 34% and 10% respectively, while being prompted with only one or two in-context examples. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0001#key_results[0])
  - Evidence: `P0144` [@Shi2024Ehragent] — Experiments on three real-world multi-tabular EHR datasets show that EHRAgent outperforms the strongest baseline by up to 29.6% in success rate. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0144#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 4.2 Memory and retrieval (RAG)

- RQ: Which design choices in Memory and retrieval (RAG) drive the major trade-offs, and how are those trade-offs measured?
- Claim: Structural drawings are widely used in many fields, e.g., mechanical engineering, civil engineering, etc.
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; tool interface contract (schemas / protocols); tool selection / routing policy; sandboxing / permissions / observability
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0030` [@Zhang2025Large] — Structural drawings are widely used in many fields, e.g., mechanical engineering, civil engineering, etc. In civil engineering, structural drawings serve as the main communication tool between architects, engineers, and builders to avoid conflicts, act as legal documentation, and provide a reference for future maintenance or evaluation needs. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0030#key_results[0])
  - Evidence: `P0084` [@Kang2025Distilling] — In this work, we propose Agent Distillation, a framework for transferring not only reasoning capability but full task-solving behavior from LLM-based agents into sLMs with retrieval and code tools. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0084#method)
  - Evidence: `P0131` [@Huang2025Retrieval] — SAFE demonstrates robust improvements in long-form COVID-19 fact-checking by addressing LLM limitations in consistency and explainability. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0131#limitations[1])
  - Evidence: `P0104` [@Abbineni2025Muallm] — To evaluate MuaLLM, we introduce two custom datasets: RAG-250, targeting retrieval and citation performance, and Reasoning-100 (Reas-100), focused on multistep reasoning in circuit design. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0104#key_results[1])
  - Evidence: `P0032` [@Tawosi2025Meta] — Our system introduces a novel Retrieval Augmented Generation (RAG) approach, Meta-RAG, where we utilize summaries to condense codebases by an average of 79.8\%, into a compact, structured, natural language representation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0032#key_results[1])
  - Evidence: `P0131` [@Huang2025Retrieval] — This study presents SAFE (system for accurate fact extraction and evaluation), an agent system that combines large language models with retrieval-augmented generation (RAG) to improve automated fact-checking of long-form COVID-19 misinformation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0131#key_results[1])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 5.1 Self-improvement and adaptation

- RQ: Which design choices in Self-improvement and adaptation drive the major trade-offs, and how are those trade-offs measured?
- Claim: This survey provides an in-depth overview of the emerging field of LLM agent evaluation, introducing a two-dimensional taxonomy that organizes existing work along (1) evaluation objectives -- what to evaluate, such as ag
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; communication protocol / roles; aggregation (vote / debate / referee); stability / robustness
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0089` [@Mohammadi2025Evaluation] — This survey provides an in-depth overview of the emerging field of LLM agent evaluation, introducing a two-dimensional taxonomy that organizes existing work along (1) evaluation objectives -- what to evaluate, such as agent behavior, capabilities, reliability, and safety -- and (2) evaluation process -- how to evaluate, including interaction modes, datasets and benchmarks, metric computation methods, and tooling. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0089#key_results[0])
  - Evidence: `P0055` [@Li2026Autonomous] — We demonstrate that large language model (LLM) agents can autonomously perform tensor network simulations of quantum many-body systems, achieving approximately 90% success rate across representative benchmark tasks. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0055#method)
  - Evidence: `P0046` [@Du2024Anytool] — We also revisit the evaluation protocol introduced by previous works and identify a limitation in this protocol that leads to an artificially high pass rate. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0046#limitations[1])
  - Evidence: `P0036` [@Zhou2025Self] — Evaluation on two existing multi-turn tool-use agent benchmarks, M3ToolEval and TauBench, shows the Self-Challenging framework achieves over a two-fold improvement in Llama-3.1-8B-Instruct, despite using only self-generated training data. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0036#key_results[0])
  - Evidence: `P0057` [@Zhang2026Evoroute] — Experiments on challenging agentic benchmarks such as GAIA and BrowseComp+ demonstrate that EvoRoute, when integrated into off-the-shelf agentic systems, not only sustains or enhances system performance but also reduces execution cost by up to $80\%$ and latency by over $70\%$. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0057#key_results[0])
  - Evidence: `P0055` [@Li2026Autonomous] — Systematic evaluation using DeepSeek-V3.2, Gemini 2.5 Pro, and Claude Opus 4.5 demonstrates that both in-context learning and multi-agent architecture are essential. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0055#key_results[1])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 5.2 Multi-agent coordination

- RQ: Which design choices in Multi-agent coordination drive the major trade-offs, and how are those trade-offs measured?
- Claim: Evaluating each MemTool mode across 13+ LLMs on the ScaleMCP benchmark, we conducted experiments over 100 consecutive user interactions, measuring tool removal ratios (short-term memory efficiency) and task completion ac
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; tool interface contract (schemas / protocols); tool selection / routing policy; sandboxing / permissions / observability
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0101` [@Lumer2025Memtool] — Evaluating each MemTool mode across 13+ LLMs on the ScaleMCP benchmark, we conducted experiments over 100 consecutive user interactions, measuring tool removal ratios (short-term memory efficiency) and task completion accuracy. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0101#key_results[0])
  - Evidence: `P0122` [@Cao2025Skyrl] — We introduce SkyRL-Agent, a framework for efficient, multi-turn, long-horizon agent training and evaluation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0122#method)
  - Evidence: `P0158` [@Shen2024Small] — While traditional works focus on training a single LLM with all these capabilities, performance limitations become apparent, particularly with smaller models. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0158#limitations[1])
  - Evidence: `P0158` [@Shen2024Small] — Evaluation across various tool-use benchmarks illustrates that our proposed multi-LLM framework surpasses the traditional single-LLM approach, highlighting its efficacy and advantages in tool learning. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0158#key_results[1])
  - Evidence: `P0188` [@Zhao2025Achieving] — However, due to weak heuristics for auxiliary constructions, AI for geometry problem solving remains dominated by expert models such as AlphaGeometry 2, which rely heavily on large-scale data synthesis and search for both training and evaluation. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0188#key_results[0])
  - Evidence: `P0041` [@Ji2025Tree] — Experiments across 11 datasets and 3 types of QA tasks demonstrate the superiority of the proposed tree-based RL over the chain-based RL method. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0041#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 6.1 Benchmarks and evaluation protocols

- RQ: Which design choices in Benchmarks and evaluation protocols drive the major trade-offs, and how are those trade-offs measured?
- Claim: RAS-Eval comprises 80 test cases and 3,802 attack tasks mapped to 11 Common Weakness Enumeration (CWE) categories, with tools implemented in JSON, LangGraph, and Model Context Protocol (MCP) formats.
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; tool interface contract (schemas / protocols); tool selection / routing policy; sandboxing / permissions / observability
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0111` [@Fu2025Eval] — RAS-Eval comprises 80 test cases and 3,802 attack tasks mapped to 11 Common Weakness Enumeration (CWE) categories, with tools implemented in JSON, LangGraph, and Model Context Protocol (MCP) formats. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0111#key_results[1])
  - Evidence: `P0111` [@Fu2025Eval] — To address the absence of standardized evaluation benchmarks for these agents in dynamic environments, we introduce RAS-Eval, a comprehensive security benchmark supporting both simulated and real-world tool execution. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0111#method)
  - Evidence: `P0098` [@Wang2025Flow] — To overcome these limitations, we introduce MCP-Flow, an automated web-agent-driven pipeline for large-scale server discovery, data synthesis, and model training. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0098#limitations[1])
  - Evidence: `P0033` [@Shi2025Progent] — Our extensive evaluation across various agent use cases, using benchmarks like AgentDojo, ASB, and AgentPoison, demonstrates that Progent reduces attack success rates to 0%, while preserving agent utility and speed. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0033#key_results[0])
  - Evidence: `P0089` [@Mohammadi2025Evaluation] — This survey provides an in-depth overview of the emerging field of LLM agent evaluation, introducing a two-dimensional taxonomy that organizes existing work along (1) evaluation objectives -- what to evaluate, such as agent behavior, capabilities, reliability, and safety -- and (2) evaluation process -- how to evaluate, including interaction modes, datasets and benchmarks, metric computation methods, and tooling. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0089#key_results[0])
  - Evidence: `P0136` [@Shang2024Agentsquare] — Extensive experiments across six benchmarks, covering the diverse scenarios of web, embodied, tool use and game applications, show that AgentSquare substantially outperforms hand-crafted agents, achieving an average performance gain of 17.2% against best-known human designs. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0136#key_results[0])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.

## 6.2 Safety, security, and governance

- RQ: Which design choices in Safety, security, and governance drive the major trade-offs, and how are those trade-offs measured?
- Claim: MSB contributes: (1) a taxonomy of 12 attacks including name-collision, preference manipulation, prompt injections embedded in tool descriptions, out-of-scope parameter requests, user-impersonating responses, false-error
  - Axes: evaluation protocol (datasets, metrics, human evaluation); compute and latency constraints; tool interface contract (schemas / protocols); tool selection / routing policy; sandboxing / permissions / observability
  - Evidence levels: fulltext=0, abstract=18, title=0.
  - Evidence: `P0097` [@Zhang2025Security] — MSB contributes: (1) a taxonomy of 12 attacks including name-collision, preference manipulation, prompt injections embedded in tool descriptions, out-of-scope parameter requests, user-impersonating responses, false-error escalation, tool-transfer, retrieval injection, and mixed attacks; (2) an evaluation harness that executes attacks by running real tools (both benign and malicious) via MCP rather than simulation; and (3) a robustness metric that quantifies the trade-off between security and performance: Net Resilient Performance (NRP). (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0097#key_results[0])
  - Evidence: `P0097` [@Zhang2025Security] — We present MSB (MCP Security Benchmark), the first end-to-end evaluation suite that systematically measures how well LLM agents resist MCP-specific attacks throughout the full tool-use pipeline: task planning, tool invocation, and response handling. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0097#method)
  - Evidence: `P0219` [@Lichkovski2025Agent] — We encourage future work extending agentic safety benchmarks to different legal jurisdictions and to multi-turn and multilingual interactions. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0219#limitations[1])
  - Evidence: `P0111` [@Fu2025Eval] — RAS-Eval comprises 80 test cases and 3,802 attack tasks mapped to 11 Common Weakness Enumeration (CWE) categories, with tools implemented in JSON, LangGraph, and Model Context Protocol (MCP) formats. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0111#key_results[1])
  - Evidence: `P0114` [@Kale2025Reliable] — To this end, we systematize a monitor red teaming (MRT) workflow that incorporates: (1) varying levels of agent and monitor situational awareness; (2) distinct adversarial strategies to evade the monitor, such as prompt injection; and (3) two datasets and environments -- SHADE-Arena for tool-calling agents and our new CUA-SHADE-Arena, which extends TheAgentCompany, for computer-use agents. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0114#key_results[0])
  - Evidence: `P0097` [@Zhang2025Security] — We evaluate nine popular LLM agents across 10 domains and 400+ tools, producing 2,000 attack instances. (provenance: paper_notes | papers/paper_notes.jsonl:paper_id=P0097#key_results[1])
  - Caveat: Evidence is not full-text grounded for this subsection; treat claims as provisional and avoid strong generalizations.
