"""Regression: idea-brainstorm harvest keywords stay on the goal topic.

A read of an idea-brainstorm Run on a clinical-summarization goal ("trustworthy
clinical note summarization with large language models") produced a memo whose
every direction was about LLM AGENTS (ReAct, planners, tool loops), not clinical
summarization — 79 agent mentions vs 7 clinical, and it drew on none of the
clinical corpus papers.

Two coupled causes, both fixed:
1. `_topic_tokens` truncated the goal to its first 6 raw tokens, cutting
   "...summarization with large [language models]" to "...with large" and keeping
   the filler "with". Fixed: drop function-word fillers BEFORE the 6-token cap.
2. `query_bucket_templates` appended LLM-agent jargon ("{topic} agent evaluation
   reliability", "{topic} adaptation planning memory"). That injected "agent" into
   queries.md, which — with "language model" already in the goal — tripped the
   `llm_agents` domain pack's trigger (group_a="agent" AND group_b="language
   model"), hijacking the offline harvest to agent papers. Fixed: topic-neutral
   discussion axes with no domain word.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "_idea_brief_run", REPO_ROOT / ".codex" / "skills" / "idea-brief" / "scripts" / "run.py"
)
_IB = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_IB)

_CONTRACT = json.loads(
    (REPO_ROOT / ".codex" / "skills" / "idea-brief" / "assets" / "brief_contract.json").read_text()
)
_LLM_AGENTS_PACK = json.loads(
    (REPO_ROOT / ".codex" / "skills" / "arxiv-search" / "assets" / "domain_packs" / "llm_agents.json").read_text()
)


def _pack_matches(pack: dict, haystack: str) -> bool:
    trig = pack.get("topic_triggers", {})
    ga = [t.lower() for t in trig.get("trigger_group_a", [])]
    gb = [t.lower() for t in trig.get("trigger_group_b", [])]
    low = haystack.lower()
    return any(t in low for t in ga) and any(t in low for t in gb)


def test_topic_tokens_not_truncated_at_filler() -> None:
    toks = _IB._topic_tokens("trustworthy clinical note summarization with large language models")
    # The filler "with" is dropped; the meaningful topic words survive the cap.
    assert "with" not in toks, toks
    assert "summarization" in toks and "language" in toks, toks


def test_topic_tokens_keeps_distribution_shift() -> None:
    toks = _IB._topic_tokens("reliable adaptation of embodied agents under distribution shift")
    assert "distribution" in toks and "shift" in toks, toks
    assert "of" not in toks and "under" not in toks, toks


def test_query_templates_carry_no_agent_domain_jargon() -> None:
    templates = " ".join(_CONTRACT["query_bucket_templates"]).lower()
    for jargon in ("agent", "planning memory", "governance"):
        assert jargon not in templates, (jargon, templates)


def test_clinical_goal_does_not_trip_llm_agents_pack() -> None:
    # Reproduce the harvest keyword line the pipeline writes to queries.md.
    topic = " ".join(_IB._topic_tokens("trustworthy clinical note summarization with large language models"))
    queries = [t.format(topic=topic) for t in _CONTRACT["query_bucket_templates"]]
    goal = "Brainstorm research directions on trustworthy clinical note summarization with large language models."
    haystack = goal + " " + " ".join(queries)
    # With neutral templates, the injected text no longer adds "agent", so the
    # llm_agents pack (needs group_a "agent"/"agentic") must NOT match a clinical goal.
    assert not _pack_matches(_LLM_AGENTS_PACK, haystack), (
        "clinical goal should not select the llm_agents domain pack",
        [t for t in _LLM_AGENTS_PACK["topic_triggers"]["trigger_group_a"] if t.lower() in haystack.lower()],
    )


def test_agent_goal_still_reaches_llm_agents_pack_via_its_own_topic() -> None:
    # A genuine agent goal supplies "agent" + "llm" from its OWN topic words, so the
    # pack still matches without any template jargon.
    topic = " ".join(_IB._topic_tokens("reliability of llm agents and agentic tool use"))
    queries = [t.format(topic=topic) for t in _CONTRACT["query_bucket_templates"]]
    goal = "Brainstorm research directions on reliability of llm agents and agentic tool use."
    haystack = goal + " " + " ".join(queries)
    assert _pack_matches(_LLM_AGENTS_PACK, haystack), haystack
