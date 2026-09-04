"""Regression: no-heading prose sources yield teachable concept noun-phrases.

A review ran source-tutorial on a prose source with NO ## headings (RAG notes). The
concept extractor fell all the way back to sentence fragments and produced
malformed titles:

  - "Retriever Selects Candidate Passages From"  (SVO clause, dangling "From")
  - "Generator Conditions On Those Passages"      (SVO clause)
  - "Into Passages Before Indexing"               (leads with preposition "Into")

Both were traced to `tooling/tutorial_workflows.py`:
  1. the comma-fallback kept subject-verb *clauses* (the finite verbs "selects" /
     "conditions" were not clause markers), and `_clean_phrase`'s 5-token cap
     re-exposed the trailing preposition; and
  2. an action pattern `\\bdocuments?` false-fired on the OBJECT noun "documents"
     in "Chunking splits documents into passages ...", bypassing the concept
     guard so the leading preposition "into" survived.

The fix salvages the SUBJECT noun-phrase from an SVO clause ("A retriever selects
..." -> "Retriever"), skips an action-word match that is really this clause's
object, and trims prepositions from both ends (and after truncation). Genuine
post-action-verb enumerations ("The repo documents X, Y, Z") are unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import (
    _clean_phrase,
    _collect_phrase_candidates,
    _finite_verb_index,
    _sentence_fragments,
)


_RAG_NOTES = """# Retrieval-Augmented Generation Notes

Retrieval-augmented generation grounds a language model's output in retrieved
passages. A retriever selects candidate passages from a corpus, and the
generator conditions on those passages when producing an answer.

Chunking splits documents into passages before indexing. Evaluation of a
retrieval-augmented system separates retrieval quality from generation
faithfulness, because a fluent answer can still be unfaithful to the evidence.
"""


def _bundle():
    return [
        {
            "source_id": "rag",
            "kind": "markdown",
            "title": "Retrieval-Augmented Generation Notes",
            "text": _RAG_NOTES,
        }
    ]


def test_no_heading_source_yields_clean_concept_titles() -> None:
    displays = {c["display"] for c in _collect_phrase_candidates(_bundle())}
    # The three malformed fragment titles are gone.
    for junk in (
        "Retriever Selects Candidate Passages From",
        "Generator Conditions On Those Passages",
        "Into Passages Before Indexing",
    ):
        assert junk not in displays, junk
    # No surviving concept title dangles on a preposition or leads with one.
    for title in displays:
        tokens = title.split()
        assert tokens[0].lower() != "into", title
        assert tokens[-1].lower() not in {"from", "into", "before", "of", "on", "to"}, title
    # The subject noun-phrases are salvaged from the SVO clauses.
    assert "Retriever" in displays
    assert "Generator" in displays


def test_svo_clause_reduced_to_subject_noun_phrase() -> None:
    frags = _sentence_fragments(
        "A retriever selects candidate passages from a corpus, and the generator "
        "conditions on those passages when producing an answer."
    )
    cleaned = [_clean_phrase(f) for f in frags]
    assert "Retriever" in cleaned
    assert "Generator" in cleaned
    # The verb-clause forms must NOT appear.
    assert "Retriever Selects Candidate Passages From" not in cleaned
    assert "Generator Conditions On Those Passages" not in cleaned


def test_object_noun_action_word_does_not_mine_a_fragment() -> None:
    # "documents" here is the OBJECT of "splits", not a governing verb, so the
    # action pattern must not fire and produce "Into Passages Before Indexing".
    frags = _sentence_fragments("Chunking splits documents into passages before indexing.")
    cleaned = [_clean_phrase(f) for f in frags]
    assert "Into Passages Before Indexing" not in cleaned
    assert not any(c.lower().startswith("into") for c in cleaned), cleaned


def test_genuine_post_action_verb_enumeration_is_unchanged() -> None:
    # "The repo documents A, B, C" — here "documents" IS the governing verb, so
    # the enumeration after it is still mined as concepts (no regression).
    frags = _sentence_fragments(
        "The repo documents dataset schema, training configuration, checkpointing, "
        "and evaluation scripts."
    )
    cleaned = [_clean_phrase(f) for f in frags]
    assert "Dataset Schema" in cleaned
    assert "Training Configuration" in cleaned
    assert "Checkpointing" in cleaned
    assert "Evaluation Scripts" in cleaned


def test_finite_verb_index_ignores_plural_and_derived_nouns() -> None:
    # 3rd-person-singular present verbs with a subject before them are found.
    assert _finite_verb_index(["a", "retriever", "selects", "passages"]) == 2
    assert _finite_verb_index(["the", "generator", "conditions", "on", "those"]) == 2
    # Base-form technical verbs with a subject before them are found.
    assert _finite_verb_index(["graph", "indexes", "connect", "each", "vector"]) == 2
    assert _finite_verb_index(["embeddings", "encode", "the", "content"]) == 1
    # Plural / derived "-s" nouns are NOT verbs.
    assert _finite_verb_index(["minimum", "leaf", "size"]) == -1
    assert _finite_verb_index(["candidate", "passages"]) == -1
    assert _finite_verb_index(["generation", "faithfulness"]) == -1
    assert _finite_verb_index(["shallow", "trees"]) == -1
    assert _finite_verb_index(["graph", "indexes"]) == -1
    assert _finite_verb_index(["approximate", "nearest", "neighbor", "indexes"]) == -1


def test_clean_phrase_trims_dangling_prepositions_both_ends() -> None:
    assert _clean_phrase("into passages before indexing") == "Passages Before Indexing"
    assert _clean_phrase("candidate passages from") == "Candidate Passages"
    # Truncation past 5 tokens must not re-expose a trailing preposition.
    assert not _clean_phrase(
        "retriever selects candidate passages from a corpus"
    ).lower().endswith("from")


# ---------------------------------------------------------------------------
# comma-free declarative source (near-zero coverage + clause fragments)
# ---------------------------------------------------------------------------

_VDB_NOTES = """# Vector Database Field Notes

Vector databases store dense embeddings and answer nearest-neighbor queries at
scale. Embeddings encode the semantic content of a document as a fixed-length
vector, and similar documents map to nearby points in the vector space.

Approximate nearest neighbor indexes trade a little recall for a large speedup.
Graph indexes connect each vector to its close neighbors and walk the graph
greedily at query time. Product quantization compresses vectors into short codes
so that a large index fits in memory.

Filters restrict a search to vectors whose metadata matches a predicate. Hybrid
search combines dense similarity with sparse keyword scores.
"""


def _vdb_bundle():
    return [
        {
            "source_id": "vdb",
            "kind": "markdown",
            "title": "Vector Database Field Notes",
            "text": _VDB_NOTES,
        }
    ]


def test_comma_free_declaratives_yield_subject_concepts() -> None:
    # Before the fix, comma-free sentences produced NO concept at all (the
    # extractor gated on a comma), so a prose source collapsed to near-zero
    # coverage plus a couple of clause fragments. Each declarative now yields its
    # subject noun-phrase concept.
    displays = {c["display"] for c in _collect_phrase_candidates(_vdb_bundle())}
    for concept in (
        "Vector Databases",
        "Embeddings",
        "Approximate Nearest Neighbor Indexes",
        "Graph Indexes",
        "Product Quantization",
        "Filters",
        "Hybrid Search",
    ):
        assert concept in displays, (concept, sorted(displays))


def test_comma_free_source_has_no_clause_fragment_titles() -> None:
    displays = {c["display"] for c in _collect_phrase_candidates(_vdb_bundle())}
    # None of the earlier verb-clause fragments survive.
    for junk in (
        "Similar Documents Map To Nearby",
        "Filters Restrict A Search",
        "Vector Database Field Notes Vector",  # H1 glued to the first body sentence
    ):
        assert junk not in displays, junk
    # No title dangles on / leads with a function word.
    for title in displays:
        toks = title.split()
        assert toks[0].lower() not in {"as", "into", "with", "of", "to"}, title
        assert toks[-1].lower() not in {"from", "into", "to", "on", "of", "as", "nearby"}, title


def test_h1_heading_not_glued_to_first_body_sentence() -> None:
    from tooling.tutorial_workflows import _split_sentences

    first = _split_sentences(_VDB_NOTES)[0]
    assert not first.lstrip().startswith("#"), first
    assert "Field Notes Vector databases" not in first, first


def test_ambiguous_verb_before_complement_marks_subject() -> None:
    from tooling.tutorial_workflows import _fragment_concept

    # "documents MAP TO ...", "trees ACT AS ..." — ambiguous verb + complement
    # marker => the tokens before it are the subject noun-phrase.
    assert _fragment_concept("similar documents map to nearby points") == "similar documents"
    assert _fragment_concept("shallow trees act as weak learners") == "shallow trees"
    # But an ambiguous word heading a subject that is followed by a real verb is
    # NOT split at the ambiguous word ("Hybrid search combines ..." -> subject).
    assert _fragment_concept("hybrid search combines dense similarity") == "hybrid search"


# ---------------------------------------------------------------------------
# FAQ-style source (questions + imperatives)
# ---------------------------------------------------------------------------

_FAQ_NOTES = """# Prompt Caching FAQ

What is prompt caching? Prompt caching stores the model's internal state for a
repeated prefix so that a later request reusing that prefix skips recomputation.

How do you cache a prefix? Mark the stable portion of the prompt as cacheable,
send it once, and reuse the returned cache handle on subsequent requests.

Configure the time-to-live so that an idle entry expires before it wastes memory.
Measure the cache hit rate before and after enabling it to confirm a real speedup.
"""


def _faq_bundle():
    return [
        {
            "source_id": "pc",
            "kind": "markdown",
            "title": "Prompt Caching FAQ",
            "text": _FAQ_NOTES,
        }
    ]


def test_imperative_sentences_yield_object_noun_phrases() -> None:
    from tooling.tutorial_workflows import _fragment_concept

    # An imperative clause reduces to its OBJECT noun-phrase, not the instruction.
    assert _fragment_concept("Configure the time-to-live so that an idle entry expires") == "time-to-live"
    assert _fragment_concept("Measure the cache hit rate before and after enabling") == "cache hit rate"
    assert _fragment_concept("Mark the stable portion of the prompt as cacheable") == "stable portion"
    assert _fragment_concept("reuse the returned cache handle on subsequent requests") == "returned cache handle"
    assert _fragment_concept("Avoid caching when the prefix changes on every request") == "caching"


def test_faq_source_covers_imperative_objects_without_instruction_titles() -> None:
    displays = {c["display"] for c in _collect_phrase_candidates(_faq_bundle())}
    # The imperative objects surface as concepts (previously dropped or mangled).
    for concept in ("Time-To-Live", "Cache Hit Rate", "Stable Portion"):
        assert concept in displays, (concept, sorted(displays))
    # No imperative-instruction titles survive.
    for junk in (
        "Mark The Stable Portion",
        "Reuse The Returned Cache Handle",
        "Avoid Caching When The Prefix",
    ):
        assert junk not in displays, junk


def test_question_sentences_produce_no_concept() -> None:
    from tooling.tutorial_workflows import _sentence_fragments

    # A question is not a teachable concept and yields nothing.
    assert _sentence_fragments("What is prompt caching?") == []
    assert _sentence_fragments("How do you cache a prefix?") == []
    assert _sentence_fragments("When should you avoid it?") == []


# ---------------------------------------------------------------------------
# table-only source (markdown comparison/reference table, no prose)
# ---------------------------------------------------------------------------

_TABLE_ONLY = """# Optimizer Comparison Reference

| Optimizer | Update rule | Typical use | Key hyperparameter |
|-----------|-------------|-------------|--------------------|
| SGD | Step against the gradient | Large-batch vision training | learning rate |
| Momentum | Accumulate a velocity term | Smoother descent on ravines | momentum coefficient |
| Adam | Adapt per-parameter step sizes | Default for transformers | beta1, beta2 |
| AdamW | Adam with decoupled weight decay | Regularized transformer training | weight decay |
| Adafactor | Factorized second moments | Memory-constrained large models | relative step |
"""


def _table_bundle():
    return [
        {
            "source_id": "opt",
            "kind": "markdown",
            "title": "Optimizer Comparison Reference",
            "text": _TABLE_ONLY,
        }
    ]


def test_table_row_subjects_extracted() -> None:
    from tooling.tutorial_workflows import _table_row_subjects

    subjects = [s for s, _ in _table_row_subjects(_TABLE_ONLY)]
    assert subjects == ["SGD", "Momentum", "Adam", "AdamW", "Adafactor"], subjects


def test_table_only_source_covers_row_subjects_not_header_fragments() -> None:
    displays = {c["display"] for c in _collect_phrase_candidates(_table_bundle())}
    # Each optimizer row-subject is a concept.
    for concept in ("SGD", "Momentum", "Adam", "Adamw", "Adafactor"):
        assert concept in displays, (concept, sorted(displays))
    # No header-concatenation or garbled cross-cell fragment survives.
    for junk in (
        "Optimizer Update Rule Typical Use",
        "Beta2 Adamw Adam With Decoupled",
    ):
        assert junk not in displays, junk


def test_table_rows_excluded_from_sentence_split() -> None:
    from tooling.tutorial_workflows import _split_sentences

    # A table-only source yields no pseudo-sentences (rows are handled separately).
    assert _split_sentences(_TABLE_ONLY) == []


def test_prose_and_table_source_yields_both() -> None:
    mixed = (
        "# Retrieval Notes\n\n"
        "A retriever selects candidate passages from a corpus. Re-ranking reorders the top results.\n\n"
        "| Component | Role |\n"
        "|-----------|------|\n"
        "| Bi-encoder | Fast candidate retrieval |\n"
        "| Cross-encoder | Precise re-ranking |\n"
    )
    displays = {
        c["display"]
        for c in _collect_phrase_candidates(
            [{"source_id": "mix", "kind": "markdown", "title": "Retrieval Notes", "text": mixed}]
        )
    }
    # Prose subject NPs AND table row subjects both appear.
    assert "Retriever" in displays, sorted(displays)
    assert "Bi-Encoder" in displays, sorted(displays)
    assert "Cross-Encoder" in displays, sorted(displays)


# ---------------------------------------------------------------------------
# bulleted-list source ("Term: definition" bullets, no prose/table)
# ---------------------------------------------------------------------------

_BULLET_ONLY = """# Kubernetes Primitives

- Pod: the smallest deployable unit, one or more containers sharing a network namespace
- Deployment: manages a replica set and rolls out updates to pods declaratively
- Service: gives a stable virtual IP and DNS name to a dynamic set of pods
- ConfigMap: injects non-secret configuration into pods as env vars or files
- Ingress: routes external HTTP traffic to services based on host and path rules
"""


def _bullet_bundle():
    return [
        {
            "source_id": "k8s",
            "kind": "markdown",
            "title": "Kubernetes Primitives",
            "text": _BULLET_ONLY,
        }
    ]


def test_list_item_subjects_extracts_term_before_colon() -> None:
    from tooling.tutorial_workflows import _list_item_subjects

    subjects = [s for s, _ in _list_item_subjects(_BULLET_ONLY)]
    assert subjects == ["Pod", "Deployment", "Service", "ConfigMap", "Ingress"], subjects


def test_bullet_only_source_covers_terms_not_fragments() -> None:
    displays = {c["display"] for c in _collect_phrase_candidates(_bullet_bundle())}
    for concept in ("Pod", "Deployment", "Service", "Configmap", "Ingress"):
        assert concept in displays, (concept, sorted(displays))
    # No garbled mid-bullet fragment survives.
    for junk in ("One Or More", "Rolls Out", "DNS Name To A Dynamic", "Pod The Smallest Deployable Unit"):
        assert junk not in displays, junk


def test_bullet_lines_excluded_from_sentence_split() -> None:
    from tooling.tutorial_workflows import _split_sentences

    assert _split_sentences(_BULLET_ONLY) == []


def test_prose_and_bullets_source_yields_both() -> None:
    mixed = (
        "# Training Tips\n\n"
        "Training a model well requires care with data and optimization.\n\n"
        "- Learning rate: the single most important hyperparameter to tune first\n"
        "- Batch size: trades gradient noise against memory and throughput\n"
    )
    displays = {
        c["display"]
        for c in _collect_phrase_candidates(
            [{"source_id": "tt", "kind": "markdown", "title": "Training Tips", "text": mixed}]
        )
    }
    assert "Learning Rate" in displays, sorted(displays)
    assert "Batch Size" in displays, sorted(displays)
    # A prose subject NP is still present too.
    assert any("Training" in d for d in displays), sorted(displays)


# ---------------------------------------------------------------------------
# numbered-step procedure source ("1. ... 2. ...", a how-to)
# ---------------------------------------------------------------------------

_NUMBERED_STEPS = """# Deploying a Model to Production

1. Export the trained checkpoint to ONNX and verify the output parity against the PyTorch model.
2. Build a container image that bundles the ONNX runtime and a thin HTTP serving layer.
3. Run a load test at expected peak traffic and record p99 latency and error rate.
4. Roll out to a canary that receives 5% of traffic while monitoring the golden metrics.
5. Promote to full traffic once the canary holds for 24 hours without regression.
"""


def _numbered_bundle():
    return [
        {
            "source_id": "deploy",
            "kind": "markdown",
            "title": "Deploying a Model to Production",
            "text": _NUMBERED_STEPS,
        }
    ]


def test_numbered_steps_no_bare_number_concepts() -> None:
    displays = {c["display"] for c in _collect_phrase_candidates(_numbered_bundle())}
    # No bare step-number concept titles survive.
    for junk in ("1", "2", "3", "4", "5"):
        assert junk not in displays, (junk, sorted(displays))


def test_numbered_steps_yield_object_noun_phrases() -> None:
    displays = {c["display"] for c in _collect_phrase_candidates(_numbered_bundle())}
    # Each imperative step reduces to its object noun-phrase concept.
    for concept in ("Trained Checkpoint", "Container Image", "Load Test", "Canary", "Full Traffic"):
        assert concept in displays, (concept, sorted(displays))
    # No verb particle leaked as a concept ("Roll out ..." must not yield "Out").
    assert "Out" not in displays, sorted(displays)


def test_numbered_lines_excluded_from_sentence_split() -> None:
    from tooling.tutorial_workflows import _split_sentences

    assert _split_sentences(_NUMBERED_STEPS) == []


def test_list_line_body_strips_bullet_and_number_markers() -> None:
    from tooling.tutorial_workflows import _list_line_body

    assert _list_line_body("1. Export the checkpoint") == "Export the checkpoint"
    assert _list_line_body("2) Build the image") == "Build the image"
    assert _list_line_body("- Pod: the smallest unit") == "Pod: the smallest unit"
    # A plain prose line is not a list item.
    assert _list_line_body("This is a normal sentence.") is None
