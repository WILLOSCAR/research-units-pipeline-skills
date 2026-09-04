from __future__ import annotations

import re


CLAIM_PATTERNS = (
    "we propose",
    "we present",
    "we introduce",
    "we show",
    "we demonstrate",
    "we find",
    "our method",
    "our approach",
    "our framework",
    "our model",
    "contribution",
    "improves",
    "outperforms",
    "achieves",
)

EMPIRICAL_HINTS = (
    "%",
    "benchmark",
    "dataset",
    "metric",
    "accuracy",
    "success rate",
    "results",
    "experiment",
    "evaluation",
    "outperforms",
    "improves",
    "achieves",
)


def split_sentences(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", str(text or "").strip())
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+", clean)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # A single sentence that enumerates multiple distinct contributions
        # inline ("Our contributions are threefold: (1) ...; (2) ...; (3) ...")
        # must become one claim per contribution — a referee assesses each
        # separately. Expand it; otherwise keep the sentence as-is.
        expanded = _split_enumerated_items(part)
        out.extend(expanded if expanded else [part])
    return out


# Inline enumerators that mark distinct list items within one sentence:
# "(1)"/"(2)", "(i)"/"(ii)", "1)"/"2)", or "first,"/"second,". Used to split an
# enumerated contributions sentence into one claim per item.
_INLINE_ENUM = re.compile(
    r"(?:^|[\s;,])\(?(?:\d{1,2}|[ivx]{1,4}|first|second|third|fourth|fifth)\)"
    r"|(?:^|[\s;])(?:first|second|third|fourth|fifth)[,:]",
    flags=re.IGNORECASE,
)


def _split_enumerated_items(sentence: str) -> list[str] | None:
    """Split a sentence enumerating >=2 distinct contributions into per-item
    claims, or None when it is not such an enumeration.

    "Our contributions are threefold: (1) we introduce X; (2) we design Y; (3) we
    release Z." -> ["Our contributions include: we introduce X",
    "Our contributions include: we design Y", "Our contributions include: we
    release Z"]. The lead-in before the first marker is prefixed to each item so
    every claim stands alone. Requires a ':' lead-in and >=2 markers to avoid
    splitting incidental parentheticals like "the model (1) shown in Fig 2".
    """

    colon = sentence.find(":")
    if colon == -1:
        return None
    lead_in = sentence[:colon].strip()
    body = sentence[colon + 1 :].strip()
    # Find enumerator marker positions in the body.
    markers = [m.start() for m in re.finditer(
        r"(?:^|[\s;,])\(?(?:\d{1,2}|[ivx]{1,4}|first|second|third|fourth|fifth)[)\.]",
        body,
        flags=re.IGNORECASE,
    )]
    if len(markers) < 2:
        return None
    # The lead-in should look like a contributions/summary announcement, else this
    # is likely an incidental in-text list, not a claim enumeration.
    if not re.search(r"(?i)\b(contribution|contributions|propose|present|introduce|threefold|twofold|as follows|following|summariz)", lead_in):
        return None
    items: list[str] = []
    for idx, start in enumerate(markers):
        end = markers[idx + 1] if idx + 1 < len(markers) else len(body)
        chunk = body[start:end]
        # Strip the leading marker token itself.
        chunk = re.sub(
            r"^[\s;,]*\(?(?:\d{1,2}|[ivx]{1,4}|first|second|third|fourth|fifth)[)\.]\s*",
            "",
            chunk,
            flags=re.IGNORECASE,
        ).strip(" ;,.")
        if len(chunk) < 8:
            continue
        prefix = f"{lead_in}: " if lead_in else ""
        items.append(f"{prefix}{chunk}".strip())
    return items if len(items) >= 2 else None


def heading_context_sentences(text: str) -> list[dict[str, str]]:
    section = "Document"
    page = ""
    out: list[dict[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        # Join a paragraph's soft-wrapped lines before splitting, so a sentence
        # that wraps across lines is not truncated at the line break (which
        # otherwise yields fragment "claims" like "...improves F1 by 5.1 over the"
        # and mislabels metric-bearing claims as underspecified downstream).
        if not buffer:
            return
        paragraph = " ".join(buffer)
        buffer.clear()
        for sentence in split_sentences(paragraph):
            if len(sentence) < 30:
                continue
            out.append({"section": section, "page": page, "sentence": sentence})

    lines = (text or "").splitlines()
    for raw in lines:
        line = raw.strip()
        # Strip markdown image markup: a claim is assertion text, not figure
        # markup. Drop a line that is ONLY an image reference; strip an inline
        # "![alt](url)" from a line that also carries caption/assertion text.
        if line:
            stripped = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", line).strip()
            if not stripped:
                # The line was only image markup — treat as a paragraph break.
                flush()
                continue
            line = re.sub(r"\s+", " ", stripped)
        if not line:
            flush()
            continue
        if line.startswith("#"):
            flush()
            section = line.lstrip("#").strip() or section
            continue
        page_match = re.fullmatch(r"\[page\s+([0-9]+)\]", line, flags=re.IGNORECASE)
        if page_match:
            flush()
            page = page_match.group(1)
            continue
        buffer.append(line)
    flush()
    return out


def classify_claim(sentence: str) -> str:
    """Empirical iff the sentence asserts a MEASURED RESULT.

    A bare number or benchmark token is not enough: a contribution/definition
    ("we claim a confidence-gated policy, a cache-coherent memory"), an
    experimental-protocol statement ("we report over five seeds with 95%
    confidence intervals"), or a limitation/caveat ("the evaluation is limited to
    four benchmarks; ... confounding attribution") all mention numbers or
    benchmarks yet assert no result — they are conceptual. Empirical requires a
    result-assertion (improves/reaches/outperforms/reduces/gains ...) together
    with a quantity or comparison.
    """
    low = sentence.lower()

    # Non-result framings take precedence even when a number is present.
    if _CONTRIBUTION_FRAMING.search(low) and not _RESULT_ASSERTION.search(low):
        return "conceptual"
    # An analytical/design claim (complexity bound, parameter-count reduction, a
    # proven theoretical property) is NOT a measured empirical result, even when
    # it pairs a result verb like "reduce" with asymptotic notation. Type
    # it conceptual so the evidence-auditor does not demand a dataset/metric it
    # was never going to have.
    if _is_analytical_claim(sentence):
        return "conceptual"
    if (
        _PROTOCOL_FRAMING.search(low)
        and not _RESULT_ASSERTION.search(low)
        and not _METRIC_RESULT.search(low)
    ):
        return "conceptual"
    if _LIMITATION_FRAMING.search(low) and not _RESULT_ASSERTION.search(low):
        return "conceptual"

    has_quantity = bool(re.search(r"\b[0-9]+(\.[0-9]+)?\b", sentence)) or "%" in sentence
    if _RESULT_ASSERTION.search(low) and (has_quantity or _COMPARISON.search(low)):
        return "empirical"
    # A measurement/benchmark hint with a quantity, and no non-result framing,
    # still reads empirical (e.g. "accuracy 0.914 on TCGA"). An ablation delta
    # ("Ablations remove the gate (-4.1)") is a measured result too.
    if has_quantity and (
        any(token in low for token in EMPIRICAL_HINTS) or "ablation" in low
    ):
        return "empirical"
    # A quantified COMPARISON with numbers on both sides ("trains in 8 GPU-hours
    # versus 31 GPU-hours", "60 FPS vs 22 FPS") is a measured result even when the
    # verb is not one of the canonical result verbs. Requires >=2 numeric quantities
    # AND a comparison cue so a single incidental number does not qualify.
    if _COMPARISON.search(low) and len(re.findall(r"\b[0-9]+(?:\.[0-9]+)?\b", sentence)) >= 2:
        return "empirical"
    # An explicit measured-metric phrase with a value ("mean absolute error of
    # 5.06 meV/atom", "RMSE of 0.03", "accuracy of 91%", "F1 of 0.82") is a
    # reported result even without a canonical result verb or an EMPIRICAL_HINT
    # token — the metric name + number IS the result.
    if has_quantity and _METRIC_RESULT.search(low):
        return "empirical"
    return "conceptual"


# Named error/accuracy metrics that, stated with a value, are a measured result.
_METRIC_RESULT = re.compile(
    r"(?i)\b(?:mean absolute error|mean squared error|root mean squared? error|"
    r"\bm[as]e\b|\brmse\b|\bmape\b|absolute error|prediction error|test error|"
    r"error of|error rate|accuracy of|\bf1\b|precision of|recall of|auc|"
    r"\bbleu\b|\brouge\b|\bmiou\b|perplexity of|meV/atom|meV/[A-Za-zÅ]+)\b"
)


_RESULT_ASSERTION = re.compile(
    r"(?i)\b(?:improve|improves|improved|reach|reaches|reached|outperform|outperforms|"
    r"achieve|achieves|achieved|reduce|reduces|reduced|increase|increases|increased|"
    r"gain|gains|gained|boost|boosts|halv(?:e|es|ed|ing)|drop|drops|dropped|"
    r"raises?|lowers?|beats?|surpass(?:es|ed)?)\b"
)
_COMPARISON = re.compile(r"(?i)\b(?:vs\.?|versus|over the|compared (?:to|with)|relative to|than the)\b")
_CONTRIBUTION_FRAMING = re.compile(
    r"(?i)\b(?:we (?:claim|propose|present|introduce|develop|contribute|design)|"
    r"our (?:contribution|method|approach|framework|model)|is a|is the|consists of|"
    r"we describe)\b"
)
_PROTOCOL_FRAMING = re.compile(
    r"(?i)\b(?:we report|we evaluate|we measure|we run|over (?:five|[0-9]+) seeds|"
    r"confidence intervals?|experimental setup|we use the|following the protocol)\b"
)
_LIMITATION_FRAMING = re.compile(
    r"(?i)\b(?:limited to|limitation|confound(?:s|ing)?|assumes?|is tuned per|"
    r"does not|cannot|caveat|restricted to)\b"
)

# Analytical / design claims that assert a THEORETICAL or DESIGN property, not a
# measured experimental result — even when they use a result verb like "reduce"
# with a number. Asymptotic-complexity notation (O(L^6) -> O(L^4)), a reduction
# in the "number of parameters", or a "we prove ..." theorem statement are
# analytical: the number is a symbol/bound, not a measurement on a dataset. The
# evidence-auditor should not flag these as "underspecified empirical claims with
# no metric/dataset" — that produces a spurious major concern.
_COMPLEXITY_NOTATION = re.compile(
    r"(?i)(?:\bO\s*\(|\\mathcal\{?O\}?\s*\(|\\big[oO]\b|"
    r"\b(?:time|space|computational|memory)\s+complexity\b|"
    r"\bnumber of parameters\b|\bparameter count\b|\basymptotic\b)"
)
_PROOF_FRAMING = re.compile(
    r"(?i)\b(?:we prove|we show that|it follows that|theorem|lemma|corollary|"
    r"universality|uniform bound|upper bound(?:ed)?|we derive)\b"
)


def _is_analytical_claim(sentence: str) -> bool:
    """A theoretical/design claim (complexity bound, parameter-count reduction,
    proven property) rather than a measured experimental result."""
    low = sentence.lower()
    if _PROOF_FRAMING.search(low):
        return True
    if _COMPLEXITY_NOTATION.search(sentence):
        # Only analytical when there is no separately-measured metric result in
        # the same sentence (e.g. "... reduces error to 0.03 MAE" stays empirical).
        if not _METRIC_RESULT.search(low) and "accuracy" not in low and "%" not in sentence:
            return True
    return False


def pick_claim_candidates(text: str, *, limit: int = 8) -> list[dict[str, str]]:
    candidates = heading_context_sentences(text)
    scored: list[tuple[int, dict[str, str]]] = []
    for item in candidates:
        sent = item["sentence"]
        low = sent.lower()
        score = 0
        if any(pattern in low for pattern in CLAIM_PATTERNS):
            score += 4
        section_low = item["section"].lower()
        if section_low in {"abstract", "introduction"}:
            score += 3
        elif section_low in {"experiments", "results", "conclusion"}:
            score += 1
        if classify_claim(sent) == "empirical":
            score += 1
        scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["section"], pair[1]["sentence"]))

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    seen_token_sets: list[frozenset[str]] = []
    for _, item in scored:
        sentence = item["sentence"]
        norm = re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()
        if not norm or norm in seen:
            continue
        # Also drop a NEAR-duplicate: the same assertion restated across sections
        # with different surrounding words (e.g. the abstract and experiments both
        # stating the identical result). Exact-string dedup misses these, so
        # compare significant content-token sets and skip a claim whose tokens are
        # nearly identical to one already kept (highest-scored survives).
        tokens = frozenset(t for t in norm.split() if len(t) >= 3 and t not in _CLAIM_STOPWORDS)
        if tokens and any(_token_set_near_duplicate(tokens, kept) for kept in seen_token_sets):
            continue
        seen.add(norm)
        if tokens:
            seen_token_sets.append(tokens)
        out.append(item)
        if len(out) >= limit:
            break
    return out or candidates[:limit]


# Function words / generic tokens that should not drive claim-similarity.
_CLAIM_STOPWORDS = {
    "the", "and", "for", "over", "with", "that", "this", "from", "into", "onto",
    "than", "then", "same", "our", "its", "was", "are", "were", "has", "have",
    "which", "while", "also", "such", "these", "those", "their", "they",
}


def _token_set_near_duplicate(a: frozenset[str], b: frozenset[str], *, threshold: float = 0.8) -> bool:
    """True when two content-token sets are near-identical (Jaccard >= threshold).

    Targets the same assertion restated in different sections; a high threshold
    avoids merging genuinely distinct claims that merely share vocabulary.
    """
    if not a or not b:
        return False
    inter = len(a & b)
    union = len(a | b)
    return union > 0 and (inter / union) >= threshold


def parse_item_blocks(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if line.startswith("### "):
            if current:
                records.append(current)
            current = {"id": line[4:].strip()}
            continue
        if not current or not line.lstrip().startswith("- ") or ":" not in line:
            continue
        payload = line.lstrip()[2:]
        key, value = payload.split(":", 1)
        current[key.strip().lower().replace(" ", "_").replace("/", "_")] = value.strip()
    if current:
        records.append(current)
    return records


def text_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", str(value or "").lower()) if len(token) >= 3}


def extract_related_works(text: str) -> list[str]:
    lines = (text or "").splitlines()
    in_refs = False
    works: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.lower().startswith("## references") or line.lower().startswith("# references"):
            in_refs = True
            continue
        if in_refs and line.startswith("## "):
            break
        if in_refs and line.startswith("- "):
            works.append(line[2:].strip())
    if works:
        return works
    # Fallback: no References bullet list. Extract "Surname et al." citations from
    # the Related Work section PROSE (very common manuscript shape), so a paper
    # that cites prior work only in prose still yields related works for novelty
    # positioning instead of zero.
    return _prose_related_works(_related_work_section(text))


def _prose_related_works(section: str) -> list[str]:
    """Ordered, de-duplicated prior-work citations from prose.

    Captures both "Surname et al." and the two-author "Surname and Surname" form
    ("Behler and Parrinello"), so a two-author prior work is not dropped from the
    novelty positioning. Requires both surnames capitalized (a citation-like
    context), so lowercase coordinations ("energy and force") are not matched.
    """
    if not section:
        return []
    works: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            works.append(name)

    # Scan left-to-right so the "et al." and two-author forms interleave in prose
    # order. A single combined pattern keeps ordering deterministic.
    pattern = re.compile(
        r"\b([A-Z][A-Za-z\-']+(?:\s+[A-Z][A-Za-z\-']+){0,2})\s+et al\.?"
        r"|\b([A-Z][A-Za-z\-']+)\s+and\s+([A-Z][A-Za-z\-']+)\b"
    )
    for match in pattern.finditer(section):
        if match.group(1):
            _add(f"{match.group(1)} et al.")
        else:
            _add(f"{match.group(2)} and {match.group(3)}")
    return works


def _related_work_section(text: str) -> str:
    """Return the manuscript's Related Work section prose (empty if absent)."""
    lines = (text or "").splitlines()
    buf: list[str] = []
    in_rw = False
    for raw in lines:
        line = raw.strip()
        heading = re.match(r"^#{1,3}\s+(.*\S)\s*$", line)
        if heading:
            title = heading.group(1).lower()
            if "related work" in title:
                in_rw = True
                continue
            if in_rw:  # next heading ends the section
                break
            continue
        if in_rw:
            buf.append(line)
    return " ".join(b for b in buf if b).strip()


def _work_surname(work: str) -> str:
    """First author surname / lead token from a reference string."""
    w = str(work or "").strip()
    # Strip a leading list marker and take the first alphabetic token.
    m = re.match(r"[^A-Za-z]*([A-Z][A-Za-z\-']+)", w)
    return m.group(1) if m else ""


def _work_author_regex(work: str) -> str:
    """Regex fragment matching how the manuscript names this work's author(s).

    For a first-author work ("Bartok et al.") this is just the surname. For a
    two-author work ("Behler and Parrinello") the manuscript may write the author
    phrase in full ("the delta over Behler and Parrinello is ...") OR abbreviate to
    the first author ("delta over Behler is ..."), so the fragment matches the first
    surname with an OPTIONAL " and <Second>" tail — otherwise a manuscript-stated
    delta over a two-author work is missed (the pattern searched only "over Behler
    is"). Returns "" when no surname is parseable.
    """
    surname = _work_surname(work)
    if not surname:
        return ""
    m = re.match(
        r"[^A-Za-z]*[A-Z][A-Za-z\-']+\s+and\s+([A-Z][A-Za-z\-']+)", str(work or "").strip()
    )
    if m:  # two-author work — allow the optional " and <Second>" tail
        return rf"{re.escape(surname)}(?:\s+and\s+{re.escape(m.group(1))})?"
    return re.escape(surname)


def related_work_delta(paper_text: str, work: str) -> tuple[str, str]:
    """Manuscript-stated (overlap, delta) for a specific related work.

    Reads the Related Work prose and pulls the sentence(s) mentioning this
    work's lead author, preferring an explicit "the delta over <Author> is ..."
    clause. Returns ("", "") when the manuscript states nothing specific — the
    caller then falls back to a conservative generic phrasing.
    """
    surname = _work_surname(work)
    if not surname:
        return "", ""
    author_re = _work_author_regex(work)
    rw = _related_work_section(paper_text)
    if not rw or surname.lower() not in rw.lower():
        return "", ""
    # Protect abbreviations so the sentence splitter does not break "Kumar et al.
    # study ... both of which X combines." into a bare "Kumar et al." fragment that
    # loses the delta clause. IMPORTANT: only guard an "et al." that is mid-sentence
    # (followed by a lowercase word); an "et al." that ENDS a sentence ("developed
    # by Bartok et al. More recent ...") is a real boundary — guarding it merges the
    # next work's sentence into this one, so a downstream work's overlap cell would
    # wrongly name unrelated methods.
    guarded = re.sub(r"(?i:et al)\.(?=\s+[a-z])", "et al<DOT>", rw)
    # A citation of the form "Thong et al. (2022) developed ..." must NOT split at
    # the "et al." — the parenthesized YEAR marks it as one citation, not a
    # sentence boundary. Without this, the sentence fragments into a bare "Thong
    # et al." whose overlap cell becomes just the work name, rendering the
    # doubled "Thong et al. (Thong et al.)" in the Novelty note. The year pattern
    # is the discriminator, so a real sentence-ending "et al. More recent ..."
    # still splits (only "et al. (19xx|20xx)" is protected).
    guarded = re.sub(r"(?i:et al)\.(?=\s+\((?:19|20)\d{2}\))", "et al<DOT>", guarded)
    for abbr, repl in (("e.g.", "e<DOT>g<DOT>"), ("i.e.", "i<DOT>e<DOT>")):
        guarded = re.sub(re.escape(abbr), repl, guarded, flags=re.IGNORECASE)
    sentences = [
        s.replace("<DOT>", ".").strip()
        for s in re.split(r"(?<=[.!?])\s+", guarded)
        if s.strip()
    ]
    mentions = [s for s in sentences if surname.lower() in s.lower()]
    delta = ""
    overlap = ""
    for s in mentions:
        m = re.search(
            rf"(?i)delta over {author_re}\s+is\s+(.+?)(?:[.;,]|$)", s
        )
        if m and not delta:
            delta = m.group(1).strip()
        # "Kumar et al. study X ... both of which <method> combines" -> the work
        # is combined rather than differentiated.
        if not delta and re.search(r"(?i)both of which\b.*\bcombines?\b", s):
            delta = "combined by this method rather than contrasted"
        # An overlap cue: what this work addresses/studies/updates.
        o = re.search(
            rf"(?i){author_re}[^.;]*?\b(?:address(?:es)?|study|studies|update[s]?|propose[s]?)\b\s+(.+?)(?:[.;,]|$)",
            s,
        )
        if o and not overlap:
            overlap = o.group(1).strip()
    if not overlap and mentions:
        # Fall back to the first mention sentence trimmed as the overlap context.
        # When that sentence names OTHER works too ("NequIP by Batzner et al. and
        # MACE by Batatia et al."), narrow it to this work's own clause so each
        # work's overlap cell is row-specific rather than a shared multi-work blob.
        clause = re.sub(r"\s+", " ", _isolate_work_clause(mentions[0], surname))
        # The overlap cell describes what the work DOES; it must not restate the
        # work's own citation, which the caller already prints alongside it (else
        # the Novelty note reads "Thong et al. (Thong et al. (2022) developed ...)").
        clause = _strip_leading_citation(clause, surname)
        overlap = clause[:160].rstrip(" ,;:.")
    return overlap, delta


def _strip_leading_citation(clause: str, surname: str) -> str:
    """Drop a leading "<Surname> et al. (Year)" / "<Surname> (Year)" citation.

    The overlap cell is rendered next to the work name, so a leading self-citation
    duplicates it. Strip only when the clause STARTS with this work's citation;
    leave the descriptive remainder (with a leading verb like "developed").
    """
    pattern = re.compile(
        rf"^\s*{re.escape(surname)}(?:\s+(?:et al\.?|and\s+\w+))?\s*(?:\((?:19|20)\d{{2}}[a-z]?\))?\s*",
        re.IGNORECASE,
    )
    stripped = pattern.sub("", clause, count=1).strip()
    return stripped or clause.strip()


# A citation anchor in prose: "Surname et al." or a two-author "Surname and Surname".
_CITE_ANCHOR = re.compile(
    r"\b[A-Z][A-Za-z\-']+\s+et al\.?|\b[A-Z][A-Za-z\-']+\s+and\s+[A-Z][A-Za-z\-']+\b"
)


def _isolate_work_clause(sentence: str, surname: str) -> str:
    """Narrow a multi-citation sentence to the clause naming `surname`.

    "More recent graph-based approaches include NequIP by Batzner et al. and MACE
    by Batatia et al." -> for Batzner, "More recent graph-based approaches include
    NequIP by Batzner et al"; for Batatia, "MACE by Batatia et al". A sentence with
    at most one citation anchor (e.g. a single two-author work "Behler and
    Parrinello") is returned whole.
    """
    if len(_CITE_ANCHOR.findall(sentence)) <= 1:
        return sentence.strip()
    segments = re.split(r"(?:,\s+and\s+|\s+and\s+|;\s+|,\s+)", sentence)
    mine = [seg.strip(" ,;:.") for seg in segments if surname.lower() in seg.lower()]
    return " ".join(mine).strip() if mine else sentence.strip()
