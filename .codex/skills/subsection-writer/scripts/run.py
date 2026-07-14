from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


_ASSET_ROOT = Path(__file__).resolve().parents[1] / 'assets'
_BOOTSTRAP_TEMPLATES_PATH = _ASSET_ROOT / 'bootstrap_paragraph_templates.json'
_PARAGRAPH_JOB_TEMPLATES_PATH = _ASSET_ROOT / 'paragraph_job_templates.json'
_LEADING_ENUM_RE = re.compile(r'^(?:\(?\d+\)?[.)]\s*)+')
_LEADING_CUE_RE = re.compile(r'(?i)^(?:however|yet|further|furthermore|additionally|meanwhile|overall|notably|empirically|specifically|for example|in practice|then|further|besides|this raises a central question)\s*[:,-]\s*')
_LEADING_AUTHOR_RESULT_RE = re.compile(r'(?i)^(?:we|the authors)\s+(?:also\s+|further\s+)?(?:show|find|demonstrate|report|observe|note)\s+that\s+')
_LEADING_AUTHOR_ACTION_RE = re.compile(r'(?i)^(?:to (?:fill|address|bridge|tackle|study|understand) this gap,\s*)?(?:here,\s*)?(?:we|the authors)\s+(?:present|introduce|propose|develop|describe|provide|review|summarize|offer|open-?source|release)\b[^,]{0,120},\s*')
_TRAILING_FRAGMENT_RE = re.compile(r'(?i)(?:\.\.\.|[,;:]\s*$|\bvs\.$|\b(?:and|or|to|of|in|on|with|for|from|across|between|into|than|that|which|while|because|under|over|at|by)\.?$)')
_TRAILING_AUX_FRAGMENT_RE = re.compile(r'(?i)\b(?:is|are|was|were|has|have|had|be|been|being)\.?$')
_LEADING_AUXILIARY_FRAGMENT_RE = re.compile(r'(?i)^(?:is|are|was|were|does|do|did|can|could|should|would|will|may|might|must)\s+(?:the|a|an|this|these|those|our|their|its)\b')
_LEADING_ZERO_FRAGMENT_RE = re.compile(r'^0{2,}\d*\b')
_LEADING_EXAMPLE_FRAGMENT_RE = re.compile(r'(?i)^(?:such as|for example|for instance|e\.g\.)\b')
_META_SNIPPET_RE = re.compile(r'(?i)\b(?:github\.io|project\s+page|code\s+is\s+available|open-?source|repository|website)\b')
_SUMMARY_STYLE_RE = re.compile(
    r'(?i)^(?:after a detailed summary|our main contribution is|this paper bridges that gap|'
    r'we conclude by identifying|we provide a review|we present an in-depth review|the paper concludes by|'
    r'this document is a practical framework|motivated by these limitations|evaluation mentions include|'
    r'our contributions are|when comparing results, anchor the paragraph with|'
    r'prefer head-to-head comparisons only when|avoid underspecified model|'
    r'if a claim relies on a single reported number|if budgets or environments differ across papers|'
    r'use conservative language)\b'
)
_SURVEY_META_RE = re.compile(
    r'(?i)^(?:this|our)\s+(?:survey|review|paper|study)\b|'
    r'^in\s+this\s+(?:survey|review)\b|'
    r'^(?:we\s+comprehensively\s+analy(?:s|z)e|through\s+a\s+critical\s+review|after\s+a\s+detailed\s+summary)\b'
)
_GENERIC_EVAL_SHOW_RE = re.compile(
    r'(?i)^(?:our\s+|comprehensive\s+)?(?:extensive|comprehensive)\s+evaluation(?:s)?'
    r'(?:\s*\([^)]*\))?(?:\s+(?:in|across|on)\s+[^,]{0,160})?\s+shows?\b'
)
_WRITER_UNSAFE_SUPPORT_RE = re.compile(
    r'(?i)^molmospaces-bench\s+exhibits\s+strong\s+sim-to-real\s+correlation\b.*\bconfirm\b.*\bidentify\b|'
    r'^these\s+models\s+can\s+simulate\s+realistic\s+visual\s+outcomes\b|'
    r'^general\s+visual\s+representations\s+learned\s+from\s+web-scale\s+datasets\b|'
    r'^vision-language-action\s*\(vla\)\s+models?\s+achieve\s+strong\s+generalization\b|'
    r'^robot\s+learning\s+from\s+interacting\s+with\s+the\s+physical\s+world\s+is\s+fundamentally\s+bottlenecked\b|'
    r'^language-guided\s+long-horizon\s+mobile\s+manipulation\s+has\s+long\s+been\s+a\s+grand\s+challenge\b|'
    r'^simulation\s+has\s+great\s+potential\s+in\s+supplementing\s+large-scale\s+data\b|'
    r'^a\s+robotic\s+foundation\s+model\s+built\s+upon\b|'
    r'^agentworld\s+is\s+an\s+interactive\s+simulation\s+platform\b|'
    r'^it\s+typically\s+relies\s+on\s+large\s+amounts\s+of\s+human\s+demonstration\s+data\b|'
    r'^recent\s+approaches\s+attempt\s+to\s+mitigate\s+these\s+limitations\b|'
    r'^existing\s+manipulation\s+datasets\s+remain\s+costly\s+to\s+curate\b|'
    r'^learning\s+visuomotor\s+policy\s+for\s+multi-task\s+robotic\s+manipulation\s+has\s+been\s+a\s+long-standing\s+challenge\b|'
    r'^training\s+vision-language-action\s*\(vla\)\s+models\s+for\s+generalist\s+robots\s+typically\s+requires\b|'
    r'^robot\s+learning\s+is\s+witnessing\s+a\s+significant\s+increase\b|'
    r'^the\s+acquisition\s+of\s+large-scale\s+physical\s+interaction\s+data\b|'
    r'^despite\s+rapid\s+advances\s+in\s+learning-based\s+planning\s+and\s+control\b|'
    r'^three\s+fundamental\s+limitations\s+hinder\s+progress\b|'
    r'^while\s+vlm\s+backbones\s+endow\s+vlas\s+with\s+robust\s+perceptual\s+understanding\b|'
    r'^video\s+models\s+enable\s+photorealistic,\s+physically\s+consistent\s+deformable-body\s+simulation\b|'
    r'^prior\s+works\s+have\s+explored\s+leveraging\s+human\s+demonstrations\b|'
    r'^building\s+a\s+generalist\s+robot\s+that\s+can\s+perceive,\s+reason,\s+and\s+act\s+across\s+diverse\s+tasks\s+remains\s+an\s+open\s+challenge\b|'
    r'^offering\s+great\s+potential\s+in\s+robotic\s+manipulation\b|'
    r'^i\s+will\s+discuss\s+selected\s+works\s+on\s+two\s+domains\b|'
    r'^to\s+support\s+systematic\s+training\s+and\s+evaluation,\s+we\s+curate\s+two\s+benchmarks\b|'
    r'^all\s+demonstrations\s+are\s+gathered\s+using\s+a\s+consistent\s+robotic\s+embodiment\b|'
    r'^developing\s+mllms?\s+for\s+real-world\s+robots?\s+is\s+challenging\b|'
    r'^recent\s+progress\s+in\s+robotic\s+world\s+models\s+has\s+leveraged\b|'
    r'^a\s+compelling\s+alternative\s+is\s+to\s+co-train\s+the\s+policy\b|'
    r'^due\s+to\s+the\s+scarcity\s+of\s+large-scale\s+3d\s+data\b|'
    r'^built\s+upon\s+this\s+human-centric\s+foundation\b|'
    r'^this\s+raises\s+a\s+central\s+question\b|'
    r'^this\s+brings\s+up\s+a\s+notably\s+difficult\s+challenge\s+for\s+robots\b|'
    r'^extensive\s+experiments\s+across\s+simulated\s+and\s+real-world\s+benchmarks\s+show\s+that\s+FASTerVQ\b.*\bFASTerVLA\s+further\b|'
    r'^strap\s+outperforms\s+both\s+prior\s+retrieval\s+algorithms\b.*\blearn\s+robust\b|'
    r'^large\s+policies\s+pretrained\s+on\s+diverse\s+robot\s+datasets\b.*\byet\b|'
    r'^we\s+experimentally\s+confirm\s+that\s+our\s+dreaming\s+model\s+enables\s+robot\s+learning\s+of\s+policies\s+that\s+transfer\s+to\s+the\s+real-world\b|'
    r'^being-h0\.5:.*only\s+abstract-level\s+evidence\s+is\s+available\s+here\b|'
    r'^.*\bverify\s+evaluation\s+protocol,\s+baselines,\s+and\s+failure\s+cases\b'
)
_MALFORMED_RESULT_RE = re.compile(
    r'(?i)\b(?:exhibits?|shows?|demonstrates?|reveals?|achieves?)\b[^.]{0,220},\s*(?:confirm|confirms|identify|identifies|show|shows)\b'
)
_GENERIC_LIMIT_RE = re.compile(r'(?i)\b(?:open challenges?|future work|research directions?|provide a review|offer a quantitative comparison|summarize|review of|benchmark suite|comprehensive simulation benchmark)\b')
_LIMIT_SIGNAL_RE = re.compile(
    r'(?i)\b(?:limit\w*|challenge(?:s)?|risk\w*|fail\w*|fragil\w*|bottleneck\w*|cost\w*|latency|'
    r'partial\s+observability|out-of-distribution|ood|generalization\s+(?:gap|limit|challenge)|'
    r'under-specif\w*|unclear|sensitive|constraint\w*|caveat\w*|unsafe|deployment\s+constraint)\b'
)
_EVENT_CHALLENGE_RE = re.compile(
    r"(?i)\b(?:this|the)\s+(?:year(?:'s)?\s+)?challenge\s+"
    r"(?:introduces?|includes?|features?|uses?|asks?|invites?|requires?)\b|"
    r"\b(?:shared|benchmark|competition|track)\s+challenge\b"
)
_POSITIVE_COST_RE = re.compile(
    r'(?i)\bcost[-\s]?effectiv(?:e|eness|ely)\b|'
    r'\b(?:lower|reduced?|decreased?|minimal|optimal)\s+(?:computational\s+)?costs?\b'
)
_BAD_FALLBACK_PREFIX_RE = re.compile(
    r'(?i)^(?:including|then|consequently|subsequently|providing|categorizing|third|finally|on the other side|as well as|'
    r'our main contribution|the main contribution|dataset scale|26 foundational datasets|2\)|3\)|\(\d+\))\b'
)
_LISTLIKE_EVAL_VERB_RE = re.compile(r'(?i)\b(?:compare|benchmark|evaluate|assessment?|measure|measured|metric|success|accuracy|latency|robust|generaliz|transfer|cost|throughput|real-world|simulation)\b')
_EVIDENCE_VERB_RE = re.compile(r'(?i)\b(?:is|are|was|were|becomes?|remains?|shows?|demonstrates?|reports?|finds?|observes?|argues?|indicates?|improves?|reduces?|increases?|achieves?|enables?|supports?|validates?|reveals?|suggests?|depends?|requires?|offers?|bridges?|addresses?|outperforms?|fails?|limits?|constrains?)\b')
_CONCRETE_MARKER_RE = re.compile(
    r"\b\d+(?:\.\d+)?%?\b|"
    r"\b[A-Z]{2,}(?:-[A-Z0-9]+)*\b|"
    r"\b[A-Z][a-z]+[A-Z][A-Za-z0-9-]*\b|"
    r"\b[A-Z][A-Za-z0-9]+-[A-Z0-9][A-Za-z0-9-]*\b"
)
_CONCRETE_CONTEXT_RE = re.compile(
    r"(?i)\b(?:benchmark|dataset|task|real-world|simulation|robot|robotic|policy|action|control|embod|"
    r"manipulation|navigation|transfer|generaliz|latency|cost|failure|robust|deployment|safety|baseline)\b"
)
_LABEL_REWRITES = {
    'recent representative works': 'recent systems',
    'additional mapped works': 'other mapped systems',
    'earlier / related works': 'earlier related studies',
    'earlier and related works': 'earlier related studies',
    'mapped subset a': 'one mapped subset',
    'mapped subset b': 'another mapped subset',
    'mapped subset': 'the mapped subset',
    'mapped subset alt': 'an alternate mapped subset',
    'evaluation / benchmark-focused works': 'benchmark-driven studies',
    'evaluation and benchmark-focused works': 'benchmark-driven studies',
    'control / conditioning interfaces': 'control and conditioning schemes',
    'control and conditioning interfaces': 'control and conditioning schemes',
    'planning / reasoning loops': 'planning-centric systems',
    'planning and reasoning loops': 'planning-centric systems',
    'video / temporal generation': 'video-conditioned systems',
    'video and temporal generation': 'video-conditioned systems',
    'agent frameworks / architectures': 'agent-style systems',
    'agent frameworks and architectures': 'agent-style systems',
    'memory / retrieval augmentation': 'memory-augmented systems',
    'memory and retrieval augmentation': 'memory-augmented systems',
    'tool-use and function calling': 'tool-use systems',
    'transformer-based generators': 'transformer-based policies',
}


def _refinement_marker_is_current(marker_path: Path, prerequisites: list[Path]) -> bool:
    if not marker_path.exists():
        return False
    marker_mtime = marker_path.stat().st_mtime_ns
    existing = [path for path in prerequisites if path.exists()]
    if not existing:
        return True
    return marker_mtime >= max(path.stat().st_mtime_ns for path in existing)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding='utf-8', errors='ignore') as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


_BOOTSTRAP_TEMPLATES = _load_json(_BOOTSTRAP_TEMPLATES_PATH)
_PARAGRAPH_JOB_TEMPLATES = _load_json(_PARAGRAPH_JOB_TEMPLATES_PATH)


def _tmpl(group: str, key: str) -> str:
    section = _BOOTSTRAP_TEMPLATES.get(group) or {}
    if not isinstance(section, dict):
        return ''
    value = section.get(key)
    if isinstance(value, list):
        options = [str(item or '').strip() for item in value if str(item or '').strip()]
        return options[0] if options else ''
    return str(value or '').strip()


def _render(group: str, key: str, **kwargs: str) -> str:
    template = _tmpl(group, key)
    if not template:
        raise KeyError(f'missing template {group}.{key}')
    return template.format(**kwargs)


def _pick_option(seed: str, value: Any) -> str:
    if isinstance(value, list):
        options = _ordered_options(seed, value)
        return options[0] if options else ''
    return str(value or '').strip()


def _render_seeded(group: str, key: str, *, seed: str, **kwargs: str) -> str:
    section = _BOOTSTRAP_TEMPLATES.get(group) or {}
    if not isinstance(section, dict):
        raise KeyError(f'missing template group {group}')
    template = _pick_option(seed, section.get(key))
    if not template:
        raise KeyError(f'missing template {group}.{key}')
    return template.format(**kwargs)


class _BlankFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ''


def _job_template_options(*keys: str, fallback: list[str] | None = None, **kwargs: Any) -> list[str]:
    node: Any = _PARAGRAPH_JOB_TEMPLATES
    for key in keys:
        if not isinstance(node, dict):
            node = None
            break
        node = node.get(key)

    raw_options: list[str] = []
    if isinstance(node, list):
        raw_options = [str(item or '').strip() for item in node if str(item or '').strip()]
    elif isinstance(node, str):
        raw_options = [str(node).strip()] if str(node).strip() else []
    elif fallback:
        raw_options = [str(item or '').strip() for item in fallback if str(item or '').strip()]

    fmt = _BlankFormatDict({k: str(v or '') for k, v in kwargs.items()})
    rendered: list[str] = []
    for option in raw_options:
        try:
            text = option.format_map(fmt)
        except Exception:
            continue
        text = re.sub(r'\s+', ' ', str(text or '').strip())
        if text:
            rendered.append(text)
    return rendered


def _ordered_options(seed: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        single = str(value or '').strip()
        return [single] if single else []
    options = [str(item or '').strip() for item in value if str(item or '').strip()]
    if not options:
        return []
    digest = hashlib.sha1(str(seed or '').encode('utf-8', errors='ignore')).hexdigest()
    idx = int(digest[:12], 16) % len(options)
    return options[idx:] + options[:idx]


def _clean(text: str, *, limit: int = 220) -> str:
    s = str(text or '').strip()
    s = s.replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('|', ', ')
    s = s.replace('/', ' and ')
    s = s.strip(' "\'`')
    if len(s) <= limit:
        return s
    sentence_ends = [m.end() for m in re.finditer(r'[.!?](?=\s|$)', s[:limit + 1])]
    if sentence_ends:
        cut = sentence_ends[-1]
        if cut >= int(limit * 0.55):
            return s[:cut].strip()
    clipped = s[:limit].rsplit(' ', 1)[0].strip()
    return clipped if clipped else s[:limit].strip()


def _sentence(text: str, *, limit: int = 220) -> str:
    s = _clean(text, limit=limit).strip()
    return s.strip(' ,;:')


def _clause(text: str, *, limit: int = 220) -> str:
    s = _sentence(text, limit=limit)
    s = re.sub(r'(?i)^(?:however|moreover|furthermore|additionally|finally|in practice|notably)\s*[:,-]\s*', '', s)
    s = re.sub(r'(?i)^(?:however|moreover|furthermore|additionally|finally|in practice|notably)\s+', '', s)
    s = re.sub(r'(?i)^that\s+', '', s)
    s = re.sub(r'(?i)^there is a significant gap exists between\s+', 'a significant gap remains between ', s)
    s = s.rstrip('.')
    if not s:
        return ''
    if re.match(r'^[A-Z]{2,}\b', s) or re.match(r'^\d', s):
        return s
    return s[0].lower() + s[1:] if s[0].isalpha() else s


def _sentence_initial(text: Any) -> str:
    s = re.sub(r'\s+', ' ', str(text or '').strip())
    if not s:
        return ''
    return s[0].upper() + s[1:] if s[0].isalpha() else s


def _mid_sentence_label(text: Any) -> str:
    s = re.sub(r'\s+', ' ', str(text or '').strip())
    if not s:
        return ''
    if re.match(r'^[A-Z]{2,}\b', s):
        return s
    return s[0].lower() + s[1:] if s[0].isalpha() else s


def _normalize_label(text: Any) -> str:
    s = _clean(_deslash(text or ''), limit=80)
    if not s:
        return ''
    low = s.lower()
    if low in _LABEL_REWRITES:
        return _LABEL_REWRITES[low]
    s = re.sub(r'(?i)\bworks\b', 'studies', s)
    s = re.sub(r'(?i)\bmethods\b', 'approaches', s)
    s = re.sub(r'(?i)\s+', ' ', s).strip(' ,;:')
    return s[0].lower() + s[1:] if s and s[0].isupper() else s


def _normalize_axis(text: Any) -> str:
    s = _clean(_deslash(text or ''), limit=90)
    if not s:
        return ''
    s = re.sub(r'(?i)\bversus\b', 'versus', s)
    s = re.sub(r'(?i)\s+', ' ', s).strip(' ,;:')
    return s[0].lower() + s[1:] if s and s[0].isupper() else s


def _label_group_text(label: str, *, collective: bool = False) -> str:
    clean = _normalize_label(label)
    if not clean:
        return 'this cluster' if collective else 'papers in this cluster'
    if collective:
        return f'the {clean} cluster'
    return f'papers grouped under {clean}'


def _is_fragmentary(text: str) -> bool:
    s = str(text or '').strip()
    if not s:
        return True
    if len(s) < 20:
        return True
    if _LEADING_ZERO_FRAGMENT_RE.search(s):
        return True
    if _META_SNIPPET_RE.search(s):
        return True
    if _LEADING_AUXILIARY_FRAGMENT_RE.search(s) and '?' not in s:
        return True
    if _LEADING_EXAMPLE_FRAGMENT_RE.search(s):
        return True
    if re.search(r'(?i)^\s*including\b', s):
        return True
    if re.search(r'(?i)^\s*by\s+\w+', s):
        return True
    if re.search(r';\s*\(\d+\)', s):
        return True
    if s.count('(') != s.count(')'):
        return True
    if _TRAILING_FRAGMENT_RE.search(s):
        return True
    if _TRAILING_AUX_FRAGMENT_RE.search(s):
        return True
    return False


def _normalize_punctuation_spacing(text: Any) -> str:
    return re.sub(r'([,;:])(?=[A-Za-z(])', r'\1 ', str(text or ''))


def _has_limit_signal(text: Any) -> bool:
    candidate = _POSITIVE_COST_RE.sub('', str(text or ''))
    candidate = _EVENT_CHALLENGE_RE.sub('', candidate)
    return bool(_LIMIT_SIGNAL_RE.search(candidate))


def _normalize_evidence_text(text: Any, *, limit: int = 240) -> str:
    from tooling.common import bounded_complete_text

    bounded = bounded_complete_text(_deslash(text or ''), max_chars=limit, overflow_factor=3.0)
    s = _clean(bounded, limit=max(limit, len(bounded)))
    if not s:
        return ''
    if _SURVEY_META_RE.search(s) or _GENERIC_EVAL_SHOW_RE.search(s):
        return ''
    s = _LEADING_ENUM_RE.sub('', s)
    s = _LEADING_CUE_RE.sub('', s)
    s = _LEADING_AUTHOR_RESULT_RE.sub('', s)
    s = _LEADING_AUTHOR_ACTION_RE.sub('', s)
    s = _neutralize_author_voice(s)
    s = re.sub(r'(?i)^(?:in|throughout)\s+(?:this|our)\s+(?:thesis|paper|study|manuscript),?\s*', '', s)
    s = re.sub(r'(?i)\bour\s+', 'the ', s)
    s = re.sub(r'(?i)\bwe\s+(?:also\s+|further\s+)?(?:show|find|demonstrate|report|observe|note)\s+that\s+', '', s)
    s = re.sub(r'(?i)\bwe\s+(?:also\s+|further\s+)?can\s+', '', s)
    s = re.sub(r'(?i)\bempirically:\s*', '', s)
    s = re.sub(r'(?i)\bhowever:\s*', '', s)
    s = re.sub(r'(?i)\bthen:\s*', '', s)
    s = re.sub(r'(?i)\bEvaluation System,\s+for evaluating\b', 'Evaluation System for evaluating', s)
    s = re.sub(r'(?i)^(?:while|but|and|yet|however|nevertheless|in contrast)\s+', '', s)
    s = re.sub(r'(?i)\(\d+\)\s*', '', s)
    s = re.sub(r'(?i)\b(\d+)\)\s*', '', s)
    s = re.sub(r'(?i),\s*(?:supports?|enables?|provides?|including)\b[^.]{0,40}$', '', s)
    s = _normalize_punctuation_spacing(s)
    s = re.sub(r'\s+', ' ', s).strip(' ,;:')
    if not s:
        return ''
    if _SURVEY_META_RE.search(s) or _GENERIC_EVAL_SHOW_RE.search(s):
        return ''
    if re.search(r'(?i)\b(?:we|our)\b', s):
        return ''
    if re.search(r'(?i)^is a significant gap exists\b', s):
        return ''
    if re.match(r'(?i)^[a-z-]+ing\b', s) and not _EVIDENCE_VERB_RE.search(s):
        return ''
    if not _EVIDENCE_VERB_RE.search(s):
        return ''
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if _is_fragmentary(s):
        return ''
    return s


def _soft_evidence_clause(text: Any, *, limit: int = 260) -> str:
    from tooling.common import bounded_complete_text

    bounded = bounded_complete_text(_deslash(text or ''), max_chars=limit, overflow_factor=3.0)
    s = _clean(bounded, limit=max(limit, len(bounded)))
    if not s:
        return ''
    if _SURVEY_META_RE.search(s) or _GENERIC_EVAL_SHOW_RE.search(s):
        return ''
    s = _LEADING_ENUM_RE.sub('', s)
    s = _LEADING_CUE_RE.sub('', s)
    s = _LEADING_AUTHOR_RESULT_RE.sub('', s)
    s = _LEADING_AUTHOR_ACTION_RE.sub('', s)
    s = _neutralize_author_voice(s)
    s = re.sub(r'(?i)^(?:through|across|from)\s+[^,]{0,80},\s*we\s+(?:show|demonstrate|find)\s+that\s+', '', s)
    s = re.sub(r'(?i)\bour\s+(?:experiments?|results?|analysis)\s+(?:show|demonstrate|find)\s+that\s+', '', s)
    s = re.sub(r'(?i)\bwe\s+(?:show|demonstrate|find|observe|report)\s+that\s+', '', s)
    s = re.sub(r'(?i)\bhowever:\s*', '', s)
    s = re.sub(r'(?i)\byet:\s*', '', s)
    s = re.sub(r'(?i)\bcrucially:\s*', '', s)
    s = re.sub(r'(?i)\bthird:\s*', '', s)
    s = re.sub(r'(?i)\bEvaluation System,\s+for evaluating\b', 'Evaluation System for evaluating', s)
    s = _normalize_punctuation_spacing(s)
    s = re.sub(r'\s+', ' ', s).strip(' ,;:')
    if not s:
        return ''
    if _SURVEY_META_RE.search(s) or _GENERIC_EVAL_SHOW_RE.search(s):
        return ''
    if re.search(r'(?i)\b(?:we|our)\b', s):
        return ''
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if _is_fragmentary(s):
        return ''
    return s


def _best_highlight_text(highlights: list[dict[str, Any]]) -> str:
    for item in highlights[:4]:
        excerpt = _normalize_evidence_text(item.get('excerpt') or '', limit=240)
        if excerpt:
            return excerpt
    return ''


def _best_fresh_highlight(
    highlights: list[dict[str, Any]],
    stem_counts: dict[str, int] | None,
) -> tuple[str, list[str], str]:
    for item in highlights[:4]:
        excerpt = _normalize_evidence_text(item.get('excerpt') or '', limit=240)
        if not excerpt:
            continue
        stem = _record_stem(excerpt)
        if stem_counts is not None and stem_counts.get(stem, 0) > 0:
            continue
        citations = [str(x).strip() for x in (item.get('citations') or []) if str(x).strip()]
        return excerpt, citations, stem
    return '', [], ''


def _valid_clause(text: str) -> str:
    clause = _clause(text, limit=280)
    if not clause or _is_fragmentary(clause):
        return ''
    return clause


def _inline_proposition(text: Any, *, kind: str = 'fact', limit: int = 260) -> str:
    clause = _support_text(text, kind=kind)
    if not clause:
        clause = _normalize_evidence_text(text, limit=limit) or _soft_evidence_clause(text, limit=limit)
    clause = re.sub(r'\s+', ' ', str(clause or '').strip()).strip(' .;:')
    clause = re.sub(r'(?i)^that:\s*', '', clause)
    clause = re.sub(r'(?i)^(?:this|that|it)\s+(?:means|shows|suggests|indicates|implies)\s+that\s+', '', clause)
    if not clause:
        return ''
    if re.search(r'(?i)^(?:we|our)\b', clause):
        return ''
    first_word = re.match(r'^([A-Za-z][A-Za-z-]*)', clause)
    if first_word:
        head = first_word.group(1)
        lowerable_heads = {
            'a', 'an', 'the', 'this', 'these', 'those', 'in', 'on', 'for', 'with', 'without',
            'under', 'over', 'across', 'by', 'from', 'modern', 'current', 'emerging', 'existing',
            'recent', 'previous', 'task', 'scalable', 'indoor', 'compared', 'built', 'collecting',
            'evaluation', 'hydrodynamic', 'while', 'when', 'because', 'although', 'if', 'once',
            'after', 'before', 'where', 'whereas', 'as', 'during', 'despite', 'building'
        }
        if head.lower() in lowerable_heads and (len(head) == 1 or not head.isupper()):
            clause = head.lower() + clause[len(head):]
    return clause


def _has_concrete_marker(text: str) -> bool:
    s = str(text or '')
    return bool(_CONCRETE_MARKER_RE.search(s) or _CONCRETE_CONTEXT_RE.search(s))


def _deslash(text: str) -> str:
    s = re.sub(r'\s*/\s*', ' and ', str(text or ''))
    s = re.sub(r'\band\s+and\b', 'and', s)
    return re.sub(r'\s+', ' ', s).strip()


def _neutralize_author_voice(text: Any) -> str:
    s = re.sub(r'\s+', ' ', str(text or '').strip())
    s = re.sub(r'(?i)^our\s+main\s+findings\s+show\s+that\s+', 'The findings indicate that ', s)
    s = re.sub(r'(?i)^our\s+findings\s+show\s+that\s+', 'The findings show that ', s)
    s = re.sub(r'(?i)^our\s+benchmarking\b', 'Benchmarking', s)
    s = re.sub(r'(?i)^our\s+approach\b', 'The evaluated approach', s)
    s = re.sub(
        r'(?i)^we\s+term\s+(?:this\s+)?([^:]{2,100}):\s*',
        lambda match: f"{match.group(1).strip()} describes ",
        s,
    )
    s = re.sub(r'(?i)\bwe\s+have\s+found\s+', 'the evidence indicates ', s)
    s = re.sub(r'(?i)\bwe\s+argue\s+that\s+', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def _strip_title_prefix(text: str, title: str) -> str:
    s = str(text or '').strip()
    if not s:
        return ''
    title_pat = re.escape(str(title or '').strip())
    if title_pat:
        s = re.sub(rf'(?i)^in\s+{title_pat}\s*,\s*', '', s)
        s = re.sub(rf'(?i)^{title_pat}\s+highlights\s+', '', s)
    return s.strip()


def _normalize_thesis(text: str, title: str) -> str:
    s = _strip_title_prefix(text, title)
    title_pat = re.escape(str(title or '').strip())
    if title_pat:
        s = re.sub(rf'(?i)^in\s+{title_pat}\s*,\s*', '', s)
        s = re.sub(rf'(?i)^for\s+{title_pat}\s*,\s*', '', s)
    s = re.sub(r'(?i)^this\s+subsection\s+', '', s)
    s = re.sub(r'(?i)^the\s+subsection\s+', '', s)
    s = _clean(_deslash(s), limit=260)
    s = s.rstrip(' .;:')
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


def _normalize_tension(text: str, title: str) -> str:
    s = _strip_title_prefix(text, title)
    title_pat = re.escape(str(title or '').strip())
    if title_pat:
        s = re.sub(
            rf'(?i)^(?:a|the)\s+(?:central|main|recurring|key)\s+tension\s+in\s+{title_pat}\s+is\s+(?:the\s+trade-off\s+between\s+)?',
            '',
            s,
        )
    s = re.sub(
        r'(?i)^(?:a|the)\s+(?:central|main|recurring|key)\s+tension\s+in\s+[^,:]{1,160}\s+is\s+(?:the\s+trade-off\s+between\s+)?',
        '',
        s,
    )
    s = re.sub(r'(?i)^(?:a|the)\s+(?:central|main|recurring|key)\s+tension\s+is\s+', '', s)
    s = re.sub(r'(?i)^(?:a|the)\s+tension\s+around\s+[^,:]+[:,-]\s*', '', s)
    s = re.sub(r'(?i)^(?:a|the)\s+tension\s+between\s+[^,:]+[:,-]\s*', '', s)
    s = re.sub(r'(?i)^(?:the\s+)?main\s+interpretive\s+risk\s+is\s+that\s+', '', s)
    s = re.sub(r'(?i)^reported\s+gains\s+stay\s+readable\s+only\s+when\s+', '', s)
    s = re.sub(r'(?i),?\s*motivating a protocol-aware synthesis rather than per-paper summaries\.?$', '', s).strip()
    if ':' in s:
        left, right = s.split(':', 1)
        right = right.strip()
        if right and _EVIDENCE_VERB_RE.search(right):
            s = right
    return _clean(_deslash(s), limit=260).rstrip(' .;:')


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        v = str(item or '').strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _cites(keys: list[str], *, max_keys: int = 3) -> str:
    vals = _uniq(keys)[:max_keys]
    return f"[@{'; '.join(vals)}]" if vals else ''


def _first_sentence_no_cites(text: str) -> str:
    blob = re.sub(r"\[@[^\]]+\]", "", text or "")
    blob = re.sub(r"\s+", " ", blob).strip()
    if not blob:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", blob)
    return (parts[0] if parts else blob).strip()


def _stem(text: str, *, n_words: int = 4) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9']+", (text or "").lower()) if w]
    return " ".join(words[: int(n_words)])


def _normalized_opener_stem(text: str, title: str) -> str:
    base = _first_sentence_no_cites(text)
    title_low = str(title or '').strip().lower()
    if title_low:
        base = re.sub(re.escape(title_low), '', base.lower())
    base = re.sub(
        r'(?i)\b(?:work on|the literature on|a stable reading of|what matters in|the most consequential contrast in)\b',
        '',
        base,
    )
    base = re.sub(r'\s+', ' ', base).strip(' ,.;:')
    return _stem(base, n_words=6)


def _opener_specificity_score(text: str) -> int:
    s = _clean(text, limit=320)
    if not s:
        return -10
    score = 0
    if _CONCRETE_MARKER_RE.search(s):
        score += 3
    if _CONCRETE_CONTEXT_RE.search(s):
        score += 2
    if re.search(r'(?i)\b(?:because|whereas|while|under|across|latency|real-world|benchmark|transfer)\b', s):
        score += 1
    if re.search(r'(?i)\b(?:only becomes comparable once|is best read through|most informative when read through)\b', s):
        score -= 2
    if re.search(r'(?i)^(?:that comparison weakens once|a recurring constraint is|the reported gains are less stable when)\b', s):
        score -= 4
    if re.search(r'(?i)^the most consequential contrast in\b', s):
        score -= 2
    return score


def _render_seeded_opener(
    *,
    seed: str,
    title: str,
    stem_counts: dict[str, int] | None,
    max_repeats: int = 1,
    **kwargs: str,
) -> str:
    section = _BOOTSTRAP_TEMPLATES.get('paragraphs') or {}
    if not isinstance(section, dict):
        raise KeyError('missing template group paragraphs')
    options = _ordered_options(seed, section.get('opener'))
    if not options:
        raise KeyError('missing template paragraphs.opener')
    context = dict(kwargs)
    context.setdefault('title', title)
    if stem_counts is None:
        return options[0].format(**context)

    best_rendered = ''
    best_stem = ''
    best_count: int | None = None
    for template in options:
        rendered = template.format(**context)
        stem = _normalized_opener_stem(rendered, title)
        count = stem_counts.get(stem, 0)
        if best_count is None or count < best_count:
            best_rendered = rendered
            best_stem = stem
            best_count = count
        if stem and count < int(max_repeats):
            stem_counts[stem] = count + 1
            return rendered

    if best_rendered:
        if best_stem:
            stem_counts[best_stem] = stem_counts.get(best_stem, 0) + 1
        return best_rendered
    raise KeyError('missing template paragraphs.opener')


def _pick_text_candidate(*, seed: str, title: str, options: list[str], stem_counts: dict[str, int] | None) -> str:
    cleaned = [str(option or '').strip() for option in options if str(option or '').strip()]
    if not cleaned:
        return ''
    ordered = _ordered_options(seed, cleaned)
    if stem_counts is None:
        return ordered[0]

    best = ordered[0]
    best_stem = _normalized_opener_stem(best, title)
    best_count = stem_counts.get(best_stem, 0) if best_stem else 0
    best_score = _opener_specificity_score(best)
    for option in ordered:
        stem = _normalized_opener_stem(option, title)
        count = stem_counts.get(stem, 0) if stem else 0
        score = _opener_specificity_score(option)
        if count < best_count or (count == best_count and score > best_score):
            best = option
            best_stem = stem
            best_count = count
            best_score = score
        if stem and count == 0 and score >= best_score:
            stem_counts[stem] = 1
            return option
    if best_stem:
        stem_counts[best_stem] = stem_counts.get(best_stem, 0) + 1
    return best


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists() or path.stat().st_size <= 0:
        return out
    for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _item_from_comp(card: dict[str, Any], title: str) -> tuple[str, list[str]]:
    axis = _normalize_axis(card.get('axis') or '') or _tmpl('fallbacks', 'comparison_axis')
    a_label = _normalize_label(card.get('A_label') or '') or _tmpl('fallbacks', 'a_label')
    b_label = _normalize_label(card.get('B_label') or '') or _tmpl('fallbacks', 'b_label')
    a_hls = [x for x in (card.get('A_highlights') or []) if isinstance(x, dict)]
    b_hls = [x for x in (card.get('B_highlights') or []) if isinstance(x, dict)]
    a_excerpt = _best_highlight_text(a_hls)
    b_excerpt = _best_highlight_text(b_hls)
    a_clause = _valid_clause(a_excerpt)
    b_clause = _valid_clause(b_excerpt)
    citations: list[str] = [str(x).strip() for x in (card.get('citations') or []) if str(x).strip()]
    for pool in [a_hls, b_hls]:
        for item in pool[:2]:
            for k in item.get('citations') or []:
                citations.append(str(k).strip())
    if not a_clause and not b_clause:
        return '', []
    if a_clause and b_clause and a_clause != b_clause:
        sentence = _render_seeded(
            'items',
            'comparison',
            seed=f"comparison:{title}:{axis}:{a_label}:{b_label}",
            title_lower=title.lower(),
            axis=axis,
            a_label=a_label,
            b_label=b_label,
            a_excerpt=_clean(a_excerpt, limit=220),
            b_excerpt=_clean(b_excerpt, limit=220),
            a_clause=a_clause,
            b_clause=b_clause,
            cite_all=_cites(citations, max_keys=4),
        )
        return sentence, citations

    dominant_label = a_label if a_clause else b_label
    counterpart_label = b_label if a_clause else a_label
    dominant_clause = a_clause or b_clause
    sentence = (
        f"{_axis_frame(axis)}, {dominant_label} are the better-grounded side of the current comparison: {dominant_clause}, "
        f"whereas reports for {counterpart_label} remain thinner or less directly comparable {_cites(citations, max_keys=4)}."
    )
    return sentence, citations


def _item_from_anchor(anchor: dict[str, Any], title: str) -> tuple[str, list[str]]:
    text = _normalize_evidence_text(anchor.get('text') or '', limit=240)
    text_clause = _valid_clause(text)
    if not text_clause:
        return '', []
    if not _has_concrete_marker(text_clause):
        return '', []
    citations = [str(x).strip() for x in (anchor.get('citations') or []) if str(x).strip()]
    sentence = _render_seeded(
        'items',
        'anchor',
        seed=f"anchor:{title}:{text}",
        title_lower=title.lower(),
        text=text,
        text_clause=text_clause,
        cite_all=_cites(citations, max_keys=4),
    )
    return sentence, citations


def _item_from_claim(item: dict[str, Any], title: str) -> tuple[str, list[str]]:
    text = _normalize_evidence_text(item.get('claim') or '', limit=240)
    if not text:
        text = _soft_evidence_clause(item.get('claim') or '', limit=240)
    text_clause = _valid_clause(text)
    if not text_clause:
        return '', []
    citations = [str(x).strip() for x in (item.get('citations') or []) if str(x).strip()]
    sentence = _render_seeded(
        'items',
        'anchor',
        seed=f"claim:{title}:{text}",
        title_lower=title.lower(),
        text=text,
        text_clause=text_clause,
        cite_all=_cites(citations, max_keys=4),
    )
    return sentence, citations


def _item_from_eval(item: dict[str, Any], title: str) -> tuple[str, list[str]]:
    bullet = _normalize_eval_bullet(item.get('bullet') or '') or _tmpl('fallbacks', 'evaluation_bullet')
    bullet_clause = _valid_clause(bullet)
    if not bullet_clause:
        return '', []
    citations = [str(x).strip() for x in (item.get('citations') or []) if str(x).strip()]
    sentence = _render_seeded(
        'items',
        'evaluation',
        seed=f"evaluation:{title}:{bullet}",
        title_lower=title.lower(),
        bullet=bullet,
        bullet_clause=bullet_clause,
        cite_all=_cites(citations, max_keys=4),
    )
    return sentence, citations


def _normalize_eval_bullet(value: Any) -> str:
    bullet = _sentence(_deslash(value or ''), limit=240)
    if not bullet:
        return ''
    low = bullet.lower()
    if low.startswith('evaluation mentions include:'):
        rest = bullet.split(':', 1)[1].strip().strip(' .')
        return f"benchmarks and settings such as {rest}"
    if low.startswith('evaluation mentions include'):
        rest = bullet[len('evaluation mentions include'):].strip(' :.')
        return f"benchmarks and settings such as {rest}"
    return _normalize_evidence_text(bullet, limit=240)


def _keep_eval_item(item: dict[str, Any]) -> bool:
    bullet = _clean(_deslash(item.get('bullet') or ''), limit=220).lower()
    if not bullet:
        return False
    if bullet.startswith('evaluation mentions include'):
        return True
    blocked = (
        'when comparing results, anchor the paragraph with',
        'prefer head-to-head comparisons only when',
        'avoid underspecified model',
        'if a claim relies on a single reported number',
        'if budgets or environments differ across papers',
        'use conservative language',
    )
    if any(bullet.startswith(prefix) for prefix in blocked):
        return False
    tokens = [tok for tok in re.findall(r"[A-Za-z0-9-]+", bullet) if re.search(r"[A-Za-z]", tok)]
    if bullet.count(',') >= 3:
        if not _LISTLIKE_EVAL_VERB_RE.search(bullet):
            return False
        shortish = sum(1 for tok in tokens if len(tok) <= 6 or tok.isupper())
        if tokens and shortish / max(1, len(tokens)) >= 0.7:
            return False
    return True


def _item_from_limit(item: dict[str, Any], title: str) -> tuple[str, list[str]]:
    raw_text = item.get('excerpt') or item.get('bullet') or ''
    if _GENERIC_LIMIT_RE.search(str(raw_text or '')):
        return '', []
    text = _normalize_evidence_text(raw_text, limit=240)
    text_clause = _valid_clause(text)
    if not text_clause:
        return '', []
    if not _has_concrete_marker(text_clause):
        return '', []
    citations = [str(x).strip() for x in (item.get('citations') or []) if str(x).strip()]
    sentence = _render_seeded(
        'items',
        'limitation',
        seed=f"limitation:{title}:{text}",
        title_lower=title.lower(),
        text=text,
        text_clause=text_clause,
        cite_all=_cites(citations, max_keys=4),
    )
    return sentence, citations


def _synthesis_items_from_cards(cards: list[dict[str, Any]], title: str) -> list[tuple[str, list[str]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    order: list[tuple[str, str]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        a_label = _normalize_label(card.get('A_label') or '')
        b_label = _normalize_label(card.get('B_label') or '')
        key = (a_label, b_label)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(card)

    out: list[tuple[str, list[str]]] = []
    for a_label, b_label in order[:2]:
        group = groups.get((a_label, b_label)) or []
        if len(group) < 2:
            continue
        axes = [_normalize_axis(card.get('axis') or '') for card in group if _normalize_axis(card.get('axis') or '')]
        axes = _uniq(axes)
        axis_text = ", ".join(axes[:3]) if len(axes) <= 3 else ", ".join(axes[:2]) + f", and {axes[2]}"

        a_clause = ''
        b_clause = ''
        citations: list[str] = []
        for card in group:
            if not a_clause:
                raw_a = _best_highlight_text([x for x in (card.get('A_highlights') or []) if isinstance(x, dict)])
                a_clause = _valid_clause(raw_a) or _valid_clause(_soft_evidence_clause(raw_a))
            if not b_clause:
                raw_b = _best_highlight_text([x for x in (card.get('B_highlights') or []) if isinstance(x, dict)])
                b_clause = _valid_clause(raw_b) or _valid_clause(_soft_evidence_clause(raw_b))
            citations.extend([str(x).strip() for x in (card.get('citations') or []) if str(x).strip()])
        if not axis_text:
            continue
        if not a_clause and not b_clause:
            continue
        if not a_clause:
            a_clause = f"{a_label} remain less directly specified in the current evidence"
        if not b_clause:
            b_clause = f"{b_label} remain less directly specified in the current evidence"

        sentence = (
            f"The most useful contrast here is between {a_label} and {b_label}: "
            f"{a_label} tend to look strongest when {a_clause}, whereas {b_label} are more convincing when {b_clause} "
            f"{_cites(citations, max_keys=5)}."
        )
        out.append((sentence, citations))
    return out


def _bundle_sentences(sentences: list[str], *, target: int) -> list[str]:
    items = [str(s or '').strip() for s in sentences if str(s or '').strip()]
    if not items:
        return []
    target = max(1, min(int(target), len(items)))
    base = len(items) // target
    remainder = len(items) % target
    bundles: list[list[str]] = []
    cursor = 0
    for idx in range(target):
        size = base + (1 if idx < remainder else 0)
        if size <= 0:
            continue
        bundles.append(items[cursor: cursor + size])
        cursor += size
    while cursor < len(items):
        bundles[-1].append(items[cursor])
        cursor += 1
    return [' '.join(chunk).strip() for chunk in bundles if chunk]


def _series(items: list[str]) -> str:
    values = [re.sub(r'\s+', ' ', str(item or '').strip()) for item in items if str(item or '').strip()]
    if not values:
        return ''
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f'{values[0]} and {values[1]}'
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _normalized_axis_series(items: list[str], *, limit: int = 3) -> str:
    axes = [_normalize_axis(item) for item in items if _normalize_axis(item)]
    return _series(axes[:limit])


def _axis_frame(axis: Any) -> str:
    text = _normalize_axis(axis or '')
    if not text:
        return 'Along the key comparison dimension'
    if ' vs. ' in text:
        left, right = [part.strip() for part in text.split(' vs. ', 1)]
        if left and right:
            return f'Along the {left} versus {right} dimension'
    return f'Along the {text} dimension'


def _sentence_with_cites(text: str, citations: list[str], *, max_keys: int = 4) -> str:
    sentence = re.sub(r'\s+', ' ', str(text or '').strip()).strip(' .;:')
    if not sentence:
        return ''
    cite_text = _cites(citations, max_keys=max_keys)
    if cite_text:
        return f'{sentence} {cite_text}.'
    return f'{sentence}.'


def _seeded_text(seed: str, options: list[str]) -> str:
    ordered = _ordered_options(seed, options)
    return ordered[0] if ordered else ''


def _body_char_count(paragraphs: list[str]) -> int:
    text = ' '.join(str(p or '') for p in paragraphs)
    text = re.sub(r'\[@[^\]]+\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return len(text)


def _role_axes(plan_item: dict[str, Any], available_axes: list[str]) -> list[str]:
    if not available_axes:
        return []
    focus_blob = ' '.join(str(x or '') for x in (plan_item.get('focus') or []))
    focus_low = focus_blob.lower()
    picked: list[str] = []
    for axis in available_axes:
        axis_low = axis.lower()
        tokens = [tok for tok in re.findall(r'[A-Za-z][A-Za-z0-9-]+', axis_low) if len(tok) >= 4]
        if axis_low in focus_low:
            picked.append(axis)
            continue
        hits = sum(1 for tok in tokens[:4] if tok in focus_low)
        if hits >= 2 or (hits >= 1 and len(tokens) <= 2):
            picked.append(axis)
    return _uniq(picked)[:2] or available_axes[:2]


def _support_text(value: Any, *, kind: str) -> str:
    if kind == 'limit':
        text = _soft_evidence_clause(value, limit=260) or _normalize_evidence_text(value, limit=260) or _clean(_deslash(value or ''), limit=260)
    else:
        text = _normalize_evidence_text(value, limit=240) or _soft_evidence_clause(value, limit=240)
    text = re.sub(r'\s+', ' ', str(text or '').strip())
    if kind == 'limit' and re.search(r'(?i)\b(?:abstract-level evidence|title-only evidence)\b', text):
        return ''
    if text and _SUMMARY_STYLE_RE.search(text):
        return ''
    if text and (_SURVEY_META_RE.search(text) or _GENERIC_EVAL_SHOW_RE.search(text)):
        return ''
    if text and (_WRITER_UNSAFE_SUPPORT_RE.search(text) or _MALFORMED_RESULT_RE.search(text)):
        return ''
    if not text:
        return ''
    if text.endswith('?'):
        return ''
    if _is_fragmentary(text):
        return ''
    if text.startswith('(') and ')' in text[:8]:
        text = re.sub(r'^\(\d+\)\s*', '', text).strip()
    if re.search(r'(?i)^however\b', text):
        text = re.sub(r'(?i)^however[: ,\-]*', '', text).strip()
    if re.search(r'(?i)^that[: ,\-]+', text):
        text = re.sub(r'(?i)^that[: ,\-]+', '', text).strip()
    if _BAD_FALLBACK_PREFIX_RE.search(text):
        return ''
    if _SURVEY_META_RE.search(text) or _GENERIC_EVAL_SHOW_RE.search(text):
        return ''
    if kind == 'limit' and not _has_limit_signal(text):
        return ''
    return text


def _normalize_support_record(value: Any, citations: list[str], *, kind: str, axis: str = '') -> dict[str, Any]:
    text = _support_text(value, kind=kind)
    cites = _uniq([str(x).strip() for x in citations if str(x).strip()])
    return {'text': text, 'citations': cites, 'axis': axis}


def _first_nonempty(records: list[dict[str, Any]]) -> dict[str, Any]:
    for record in records:
        if str(record.get('text') or '').strip():
            return record
    return {}


def _take(records: list[dict[str, Any]], state: dict[str, int], key: str, count: int) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    start = int(state.get(key, 0))
    picked = records[start:start + count]
    state[key] = start + len(picked)
    return [record for record in picked if str(record.get('text') or '').strip()]


def _take_with_fallback(
    primary: list[dict[str, Any]],
    primary_state: dict[str, int],
    primary_key: str,
    fallback: list[dict[str, Any]],
    fallback_state: dict[str, int],
    fallback_key: str,
    count: int,
) -> list[dict[str, Any]]:
    picked = _take(primary, primary_state, primary_key, count)
    if len(picked) >= count:
        return picked
    extra = _take(fallback, fallback_state, fallback_key, count - len(picked))
    return picked + extra


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        text = re.sub(r'\s+', ' ', str(record.get('text') or '').strip())
        cites = _uniq([str(x).strip() for x in (record.get('citations') or []) if str(x).strip()])
        key = f"{text.lower()}||{'|'.join(cites)}"
        if not text or key in seen:
            continue
        seen.add(key)
        cleaned = dict(record)
        cleaned['text'] = text
        cleaned['citations'] = cites
        out.append(cleaned)
    return out


def _evidence_text_key(text: Any) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', str(text or '').lower()).strip()


def _matches_seen_evidence_key(key: str, seen: set[str]) -> bool:
    if not key:
        return False
    for prior in seen:
        if key == prior:
            return True
        if len(key) >= 80 and len(prior) >= 80 and (key in prior or prior in key):
            return True
    return False


def _dedupe_evidence_sentences_in_paragraphs(paragraphs: list[str]) -> list[str]:
    from tooling.common import split_sentences

    out: list[str] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        kept: list[str] = []
        for sentence in split_sentences(paragraph):
            without_cites = re.sub(r'\[@[^\]]+\]', '', sentence)
            compact = re.sub(r'\s+', ' ', without_cites).strip()
            key = _evidence_text_key(compact)
            evidence_sized = len(compact) >= 80 and len(key.split()) >= 12
            if evidence_sized and _matches_seen_evidence_key(key, seen):
                continue
            if evidence_sized:
                seen.add(key)
            kept.append(sentence.strip())
        rebuilt = ' '.join(part for part in kept if part).strip()
        if rebuilt:
            out.append(rebuilt)
    return out


def _record_quality_score(record: dict[str, Any]) -> int:
    text = re.sub(r'\s+', ' ', str(record.get('text') or '').strip())
    score = 0
    if not text:
        return -100
    reuse_count = int(record.get('global_reuse_count') or 0)
    score -= reuse_count * 3
    if len(text) >= 120:
        score += 2
    elif len(text) < 70:
        score -= 2
    if _has_concrete_marker(text):
        score += 2
    if re.search(r'(?i)\b(?:benchmark|dataset|evaluation|metric|latency|success|generalization|transfer|real-world|simulation)\b', text):
        score += 1
    if _BAD_FALLBACK_PREFIX_RE.search(text):
        score -= 6
    if _WRITER_UNSAFE_SUPPORT_RE.search(text) or _MALFORMED_RESULT_RE.search(text):
        score -= 8
    if _is_fragmentary(text):
        score -= 4
    if re.search(r'(?i)\b(?:survey|review|taxonomy)\b', text):
        score -= 1
    score += min(2, len(_uniq([str(x).strip() for x in (record.get('citations') or []) if str(x).strip()])))
    return score


def _record_stem(text: str, *, n_words: int = 8) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9']+", re.sub(r'\s+', ' ', str(text or '').strip().lower())) if w]
    return ' '.join(words[: int(n_words)])


def _rephrase_reused_text(text: str, *, reuse_count: int) -> str:
    s = re.sub(r'\s+', ' ', str(text or '').strip()).strip(' .;:')
    low = s.lower()
    target = 'naively pooling heterogeneous robot datasets often induces negative transfer rather than gains, underscoring the fragility of indiscriminate data scaling'
    if target in low:
        options = [
            'Naively pooling heterogeneous robot datasets can induce negative transfer rather than gains, exposing the fragility of indiscriminate data scaling',
            'Heterogeneous robot mixtures do not automatically help: naive pooling can create negative transfer instead of the expected gains, which reveals how fragile indiscriminate scaling remains',
            'The evidence around embodiment mixtures shows that simply pooling heterogeneous robot datasets can backfire, producing negative transfer instead of broader gains',
        ]
        return options[min(reuse_count, len(options) - 1)]
    return s


def _citation_keys_in_paragraphs(paragraphs: list[str]) -> set[str]:
    keys: set[str] = set()
    for paragraph in paragraphs:
        for match in re.finditer(r'\[@([^\]]+)\]', str(paragraph or '')):
            keys.update(re.findall(r'[A-Za-z0-9:_-]+', match.group(1) or ''))
    return keys


def _cluster_labels(pack: dict[str, Any], cards: list[dict[str, Any]]) -> tuple[str, str]:
    cluster_a = ''
    cluster_b = ''
    plan = pack.get('paragraph_plan') or []
    if isinstance(plan, list):
        for item in plan:
            if not isinstance(item, dict):
                continue
            role = str(item.get('argument_role') or '').strip()
            use_clusters = [_normalize_label(x) for x in (item.get('use_clusters') or []) if _normalize_label(x)]
            if not use_clusters:
                continue
            if not cluster_a and ('cluster_A' in role or role.endswith('_A')):
                cluster_a = use_clusters[0]
            if not cluster_b and ('cluster_B' in role or role.endswith('_B')):
                cluster_b = use_clusters[0]
    if not cluster_a or not cluster_b:
        for card in cards:
            if not cluster_a:
                cluster_a = _normalize_label(card.get('A_label') or '')
            if not cluster_b:
                cluster_b = _normalize_label(card.get('B_label') or '')
            if cluster_a and cluster_b:
                break
    return cluster_a or _tmpl('fallbacks', 'a_label'), cluster_b or _tmpl('fallbacks', 'b_label')


def _build_cluster_profiles(
    *,
    cards: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    limits: list[dict[str, Any]],
    cluster_a: str,
    cluster_b: str,
    cluster_specs: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    profiles: dict[str, dict[str, Any]] = {
        'A': {'label': cluster_a, 'axes': [], 'facts': [], 'anchors': [], 'claims': [], 'limits': [], 'citation_pool': []},
        'B': {'label': cluster_b, 'axes': [], 'facts': [], 'anchors': [], 'claims': [], 'limits': [], 'citation_pool': []},
    }
    global_support: dict[str, list[dict[str, Any]]] = {'anchors': [], 'claims': [], 'limits': []}
    cluster_citation_pool = {'A': set(), 'B': set()}
    for spec in cluster_specs or []:
        if not isinstance(spec, dict):
            continue
        label = _normalize_label(spec.get('label') or '')
        if label == _normalize_label(cluster_a):
            cluster_citation_pool['A'].update(str(x).strip() for x in (spec.get('bibkeys') or []) if str(x).strip())
        if label == _normalize_label(cluster_b):
            cluster_citation_pool['B'].update(str(x).strip() for x in (spec.get('bibkeys') or []) if str(x).strip())

    for card in cards:
        axis = _normalize_axis(card.get('axis') or '')
        for side in ('A', 'B'):
            label_key = 'A' if side == 'A' else 'B'
            profile = profiles[label_key]
            if axis:
                profile['axes'] = _uniq(profile['axes'] + [axis])
            highlights = [x for x in (card.get(f'{side}_highlights') or []) if isinstance(x, dict)]
            for highlight in highlights[:2]:
                highlight_cites = [str(x).strip() for x in (highlight.get('citations') or []) if str(x).strip()]
                card_cites = [str(x).strip() for x in (card.get('citations') or []) if str(x).strip()]
                record = _normalize_support_record(highlight.get('excerpt') or '', highlight_cites or card_cites, kind='fact', axis=axis)
                if not record.get('text') or not record.get('citations'):
                    continue
                profile['facts'].append(record)
                profile['citation_pool'] = _uniq(profile['citation_pool'] + record['citations'])

    def assign_to_profile(raw_records: list[dict[str, Any]], *, kind: str, text_field: str) -> None:
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            cites = _uniq([str(x).strip() for x in (item.get('citations') or []) if str(x).strip()])
            if not cites:
                continue
            record = _normalize_support_record(item.get(text_field) or '', cites, kind=kind)
            if not record.get('text'):
                continue
            best_side = ''
            best_overlap = 0
            for side in ('A', 'B'):
                overlap = len(set(cites) & set(profiles[side]['citation_pool']))
                if overlap > best_overlap:
                    best_side = side
                    best_overlap = overlap
            if best_side:
                profiles[best_side][f'{kind}s'].append(record)
            elif cluster_citation_pool['A'] or cluster_citation_pool['B']:
                overlap_a = len(set(cites) & set(cluster_citation_pool['A']))
                overlap_b = len(set(cites) & set(cluster_citation_pool['B']))
                if overlap_a > overlap_b and overlap_a > 0:
                    profiles['A'][f'{kind}s'].append(record)
                elif overlap_b > overlap_a and overlap_b > 0:
                    profiles['B'][f'{kind}s'].append(record)
                else:
                    global_support[f'{kind}s'].append(record)
            else:
                global_support[f'{kind}s'].append(record)

    assign_to_profile(anchors, kind='anchor', text_field='text')
    assign_to_profile(claims, kind='claim', text_field='claim')
    assign_to_profile(limits, kind='limit', text_field='excerpt')

    for side in ('A', 'B'):
        profiles[side]['facts'] = _dedupe_records(profiles[side]['facts'])
        profiles[side]['anchors'] = _dedupe_records(profiles[side]['anchors'])
        profiles[side]['claims'] = _dedupe_records(profiles[side]['claims'])
        profiles[side]['limits'] = _dedupe_records(profiles[side]['limits'])
    for key in ('anchors', 'claims', 'limits'):
        global_support[key] = _dedupe_records(global_support[key])
    return profiles, global_support


def _evaluation_support(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    benchmark_records: list[dict[str, Any]] = []
    protocol_citations: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        bullet = _clean(_deslash(item.get('bullet') or ''), limit=240)
        citations = _uniq([str(x).strip() for x in (item.get('citations') or []) if str(x).strip()])
        if not bullet or not citations:
            continue
        kind = re.sub(r'\s+', ' ', str(item.get('kind') or '').strip()).lower()
        low = bullet.lower()
        if kind == 'benchmark_inventory' or low.startswith('evaluation mentions include'):
            continue
        else:
            protocol_citations.extend(citations)
    return benchmark_records, _uniq(protocol_citations)


def _compose_setup_paragraph(
    *,
    title: str,
    thesis: str,
    tension: str,
    opener_mode: str,
    cluster_a: str,
    cluster_b: str,
    axes: list[str],
    citations: list[str],
    seed_record: dict[str, Any],
    stem_counts: dict[str, int] | None = None,
) -> str:
    axis_text = _normalized_axis_series(axes, limit=3) or _tmpl('fallbacks', 'lens')
    title_lower = title.lower()
    mode = str(opener_mode or '').strip().lower()
    opener_options = _job_template_options(
        'setup',
        'opener_by_mode',
        mode if mode in {'decision-first', 'contrast-first', 'protocol-first', 'failure-first', 'lens-first'} else 'default',
        fallback=[
            'The literature on {title_lower} becomes hard to compare when papers keep {axis_text} under the same label but change their actual assumptions',
            'In {title_lower}, neighboring papers often look closer than they really are because they change {axis_text} while preserving the same headline vocabulary',
        ],
        title=title,
        title_lower=title_lower,
        cluster_a=cluster_a,
        cluster_b=cluster_b,
        axis_text=axis_text,
    ) or _job_template_options(
        'setup',
        'opener_by_mode',
        'default',
        title=title,
        title_lower=title_lower,
        cluster_a=cluster_a,
        cluster_b=cluster_b,
        axis_text=axis_text,
    )
    sentences = [
        _sentence_with_cites(
            _pick_text_candidate(
                seed=f'setup:{title}:{mode}:{axis_text}',
                title=title,
                options=opener_options,
                stem_counts=stem_counts,
            ),
            [],
            max_keys=0,
        ),
        _sentence_with_cites(thesis, citations, max_keys=4),
    ]
    if tension:
        tension_options = _job_template_options(
            'setup',
            'tension_followup',
            fallback=['The comparison becomes unstable because {tension}'],
            tension=tension,
        )
        sentences.append(
            _sentence_with_cites(
                _pick_text_candidate(
                    seed=f'setup:tension:{title}:{mode}:{axis_text}',
                    title=title,
                    options=tension_options,
                    stem_counts=stem_counts,
                ),
                citations,
                max_keys=4,
            )
        )
    if seed_record.get('text'):
        sentences.append(_sentence_with_cites(seed_record['text'], seed_record.get('citations') or [], max_keys=3))
    return ' '.join(s for s in sentences if s).strip()


def _compose_cluster_paragraph(
    *,
    title: str,
    plan_item: dict[str, Any],
    profile: dict[str, Any],
    other_label: str,
    kind: str,
    facts: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    limits: list[dict[str, Any]],
    benchmarks: list[dict[str, Any]],
    protocol_citations: list[str],
    stem_counts: dict[str, int] | None = None,
    evidence_stem_counts: dict[str, int] | None = None,
) -> str:
    label = str(profile.get('label') or '').strip() or 'one route'
    label_group = _label_group_text(label)
    label_cluster = _label_group_text(label, collective=True)
    axes = _role_axes(plan_item, profile.get('axes') or [])
    axis_text = _normalized_axis_series(axes, limit=2) or _normalized_axis_series(profile.get('axes') or [], limit=2) or _tmpl('fallbacks', 'lens')
    title_lower = title.lower()
    role = str(plan_item.get('argument_role') or '')
    format_kwargs = {
        'title': title,
        'title_lower': title_lower,
        'label': label,
        'label_group': label_group,
        'label_cluster': label_cluster,
        'axis_text': axis_text,
        'other_label': other_label,
    }
    if kind == 'mechanism':
        if 'B' in role:
            lead_options = _job_template_options(
                'cluster',
                'mechanism',
                'lead_B',
                fallback=[
                    'By contrast, another route in {title_lower} organizes the comparison around {label}, so the main disagreement shifts toward {axis_text}',
                    'The contrasting cluster in {title_lower} is defined by {label}, which changes how {axis_text} should be read relative to {other_label}',
                ],
                **format_kwargs,
            )
        else:
            lead_options = _job_template_options(
                'cluster',
                'mechanism',
                'lead_A',
                fallback=[
                    'A first route in {title_lower} organizes the evidence around {label}, making {axis_text} part of the mechanism rather than background context',
                    'One stable cluster in {title_lower} is defined by {label}, so differences in {axis_text} immediately change what the system is actually optimizing',
                ],
                **format_kwargs,
            )
        closing_options = _job_template_options(
            'cluster',
            'mechanism',
            'closing',
            fallback=[
                'That is why papers in this cluster treat {axis_text} as the main source of methodological variation',
                'Under this lens, what matters in {label} is the subset of assumptions that keeps the surrounding evidence coherent once {axis_text} begin to shift',
                'What {label} helps fix here is which parts of {axis_text} remain stable enough to compare across neighboring systems',
            ],
            **format_kwargs,
        )
    elif kind == 'implementation':
        lead_key = 'lead_B' if 'B' in role else 'lead_A'
        lead_options = _job_template_options(
            'cluster',
            'implementation',
            lead_key,
            fallback=[
                'What looks like one method family in {title_lower} often separates only once the implementation stack reveals how {axis_text} are actually wired',
                'The implementation split becomes visible once {axis_text} are traced through the actual training, control, or data stack',
            ],
            **format_kwargs,
        )
        closing_options = _job_template_options(
            'cluster',
            'implementation',
            'closing',
            fallback=[
                'The implementation story therefore turns on how {axis_text} are operationalized in training, control, or data construction',
                'What survives comparison here is the concrete way {label_group} operationalize {axis_text}, not the headline label itself',
            ],
            **format_kwargs,
        )
    else:
        lead_key = 'lead_B' if 'B' in role else 'lead_A'
        lead_options = _job_template_options(
            'cluster',
            'evaluation',
            lead_key,
            fallback=[
                'In {title_lower}, evidence for {label} is only persuasive when benchmark scope and metric choice stay aligned with {axis_text}',
                'The evaluation record for {label} in {title_lower} depends less on headline gains than on whether {axis_text} are measured under comparable constraints',
            ],
            **format_kwargs,
        )
        closing_options = _job_template_options(
            'cluster',
            'evaluation',
            'closing',
            fallback=[
                'For {label}, benchmark scope, metric choice, and deployment constraints remain part of the claim rather than detachable metadata',
                'That is also where the comparison with {other_label} becomes fragile if protocol detail is under-specified',
            ],
            **format_kwargs,
        )

    sentences = [
        _sentence_with_cites(
            (
                lambda lead_text: (
                    f"In contrast, {lead_text[0].lower() + lead_text[1:]}"
                    if 'B' in role and lead_text and not re.search(r'(?i)\b(?:however|whereas|in contrast|by contrast|unlike)\b', lead_text)
                    else lead_text
                )
            )(
                _pick_text_candidate(
                    seed=f'{kind}:{title}:{label}:{axis_text}',
                    title=title,
                    options=lead_options,
                    stem_counts=stem_counts,
                )
            ),
            [],
            max_keys=0,
        )
    ]
    evidence_records = _dedupe_records(facts + anchors + claims)
    if kind == 'evaluation':
        evidence_records = _dedupe_records(anchors + facts + claims)
    evidence_records = sorted(evidence_records, key=_record_quality_score, reverse=True)
    selected_records: list[dict[str, Any]] = []
    if evidence_stem_counts is None:
        selected_records = evidence_records[:2]
    else:
        ordered = sorted(
            evidence_records,
            key=lambda rec: (
                evidence_stem_counts.get(_record_stem(rec.get('text') or ''), 0),
                -_record_quality_score(rec),
            ),
        )
        for record in ordered:
            if len(selected_records) >= 2:
                break
            stem = _record_stem(record.get('text') or '')
            reuse_count = evidence_stem_counts.get(stem, 0)
            chosen = dict(record)
            if reuse_count > 0:
                original = re.sub(r'\s+', ' ', str(chosen.get('text') or '').strip()).strip(' .;:')
                rewritten = _rephrase_reused_text(original, reuse_count=reuse_count)
                if re.sub(r'\s+', ' ', rewritten).strip(' .;:').lower() == original.lower():
                    continue
                chosen['text'] = rewritten
            selected_records.append(chosen)
            if stem:
                evidence_stem_counts[stem] = reuse_count + 1
    has_support = bool(selected_records)
    if kind == 'evaluation' and (benchmarks or limits or protocol_citations):
        has_support = True
    if not has_support:
        return ''
    evidence_sentence_count = 0
    for record in selected_records:
        record_text = _support_text(record.get('text') or '', kind='fact')
        if record_text:
            sentences.append(_sentence_with_cites(record_text, record.get('citations') or [], max_keys=4))
            evidence_sentence_count += 1
    if kind == 'evaluation':
        benchmark = _first_nonempty(benchmarks)
        benchmark_text = _support_text(benchmark.get('text') or '', kind='fact') if benchmark else ''
        if benchmark_text:
            sentences.append(_sentence_with_cites(benchmark_text, benchmark.get('citations') or [], max_keys=4))
            evidence_sentence_count += 1
        if limits:
            limit_text = _inline_proposition(limits[0].get('text') or '', kind='limit', limit=220)
            seen_limit_texts = {
                _evidence_text_key(_support_text(record.get('text') or '', kind='fact'))
                for record in selected_records
                if str(record.get('text') or '').strip()
            }
            if benchmark_text:
                seen_limit_texts.add(_evidence_text_key(benchmark_text))
            limit_key = _evidence_text_key(limit_text)
            if limit_text and limit_key and limit_key not in seen_limit_texts:
                limit_options = _job_template_options(
                    'cluster',
                    'evaluation',
                    'limit',
                    fallback=['A narrower reading is warranted here: {limit_text}'],
                    limit_text=limit_text,
                )
                limit_sentence = _pick_text_candidate(
                    seed=f'evaluation:limit:{title}:{label}',
                    title=title,
                    options=limit_options,
                    stem_counts=stem_counts,
                )
                sentences.append(_sentence_with_cites(limit_sentence, limits[0].get('citations') or [], max_keys=4))
                evidence_sentence_count += 1
        elif protocol_citations:
            limit_options = _job_template_options(
                'cluster',
                'evaluation',
                'limit_fallback',
                fallback=['Those gains remain provisional whenever task, metric, and deployment constraints are not stated together'],
            )
            limit_sentence = _pick_text_candidate(
                seed=f'evaluation:limit:fallback:{title}:{label}',
                title=title,
                options=limit_options,
                stem_counts=stem_counts,
            )
            sentences.append(_sentence_with_cites(limit_sentence, protocol_citations, max_keys=4))
    if evidence_sentence_count == 0:
        return ''
    include_closing = len(selected_records) == 0
    if kind == 'evaluation' and (limits or protocol_citations):
        include_closing = False
    if include_closing:
        sentences.append(
            _sentence_with_cites(
                _pick_text_candidate(
                    seed=f'{kind}:closing:{title}:{label}',
                    title=title,
                    options=closing_options,
                    stem_counts=stem_counts,
                ),
                [],
                max_keys=0,
            )
        )
    unique_sentences: list[str] = []
    seen_sentence_keys: set[str] = set()
    for sentence in sentences:
        cleaned = re.sub(r'\s+', ' ', str(sentence or '').strip())
        key = re.sub(r'\[@[^\]]+\]', '', cleaned)
        key = re.sub(r'[^a-z0-9]+', ' ', key.lower()).strip()
        if not cleaned or not key or key in seen_sentence_keys:
            continue
        seen_sentence_keys.add(key)
        unique_sentences.append(cleaned)
    return ' '.join(unique_sentences).strip()


def _compose_synthesis_paragraph(
    *,
    title: str,
    plan_item: dict[str, Any],
    cluster_a: dict[str, Any],
    cluster_b: dict[str, Any],
    cards: list[dict[str, Any]],
    stem_counts: dict[str, int] | None = None,
    evidence_stem_counts: dict[str, int] | None = None,
) -> str:
    axes = _role_axes(plan_item, _uniq((cluster_a.get('axes') or []) + (cluster_b.get('axes') or [])))
    axis_text = _normalized_axis_series(axes, limit=3) or _tmpl('fallbacks', 'lens')
    lead_options = _job_template_options(
        'synthesis',
        'lead',
        fallback=[
            'Read as a pair, the contrast between {cluster_a} and {cluster_b} is really about {axis_text}, not about a single headline score',
            'Across {title_lower}, the decisive difference between {cluster_a} and {cluster_b} lies in {axis_text} rather than in one isolated benchmark win',
        ],
        title=title,
        title_lower=title.lower(),
        cluster_a=str(cluster_a.get('label') or '').strip(),
        cluster_b=str(cluster_b.get('label') or '').strip(),
        axis_text=axis_text,
    )
    lead_sentence = _sentence_with_cites(
        _pick_text_candidate(
            seed=f'synthesis:{title}:{axis_text}',
            title=title,
            options=lead_options,
            stem_counts=stem_counts,
        ),
        [],
        max_keys=0,
    )
    sentences: list[str] = []
    seen_evidence_pairs: set[str] = set()
    for card in cards[:2]:
        axis = _normalize_axis(card.get('axis') or '') or axis_text
        a_text, a_cites, a_stem = _best_fresh_highlight(
            [x for x in (card.get('A_highlights') or []) if isinstance(x, dict)],
            evidence_stem_counts,
        )
        b_text, b_cites, b_stem = _best_fresh_highlight(
            [x for x in (card.get('B_highlights') or []) if isinstance(x, dict)],
            evidence_stem_counts,
        )
        a_phrase = _support_text(a_text, kind='fact')
        b_phrase = _support_text(b_text, kind='fact')
        cites = _uniq(
            a_cites
            + b_cites
            + [str(x).strip() for x in (card.get('citations') or []) if str(x).strip()]
        )
        if a_phrase and b_phrase:
            a_prop = _inline_proposition(a_phrase, kind='fact')
            b_prop = _inline_proposition(b_phrase, kind='fact')
        else:
            a_prop = ''
            b_prop = ''
        if a_prop and b_prop:
            pair_key = f"{_record_stem(a_prop)}||{_record_stem(b_prop)}"
            if pair_key in seen_evidence_pairs:
                continue
            seen_evidence_pairs.add(pair_key)
            sentences.append(
                _sentence_with_cites(
                    f'{_axis_frame(axis)}, the case for {cluster_a.get("label")} is best supported by evidence that {a_prop}, whereas the case for {cluster_b.get("label")} is better supported by evidence that {b_prop}',
                    cites,
                    max_keys=5,
                )
            )
            if evidence_stem_counts is not None:
                if a_stem:
                    evidence_stem_counts[a_stem] = evidence_stem_counts.get(a_stem, 0) + 1
                if b_stem:
                    evidence_stem_counts[b_stem] = evidence_stem_counts.get(b_stem, 0) + 1
    if not sentences and evidence_stem_counts is not None:
        fallback_cites = _uniq(
            [str(x).strip() for card in cards[:2] for x in (card.get('citations') or []) if str(x).strip()]
        )
        if fallback_cites:
            return _sentence_with_cites(lead_sentence, fallback_cites, max_keys=5)
    if not sentences:
        a_fallback = _first_nonempty(cluster_a.get('facts') or [])
        b_fallback = _first_nonempty(cluster_b.get('facts') or [])
        if a_fallback.get('text') and b_fallback.get('text'):
            a_clause = _inline_proposition(str(a_fallback.get('text') or '').strip(), kind='fact', limit=220)
            b_clause = _inline_proposition(str(b_fallback.get('text') or '').strip(), kind='fact', limit=220)
            fallback_cites = _uniq((a_fallback.get('citations') or []) + (b_fallback.get('citations') or []))
            if a_clause and b_clause:
                fallback_options = _job_template_options(
                    'synthesis',
                    'fallback',
                    fallback=['At a higher level, {cluster_a} emphasize {a_text}, whereas {cluster_b} emphasize {b_text}'],
                    cluster_a=str(cluster_a.get('label') or '').strip(),
                    cluster_b=str(cluster_b.get('label') or '').strip(),
                    a_text=a_clause,
                    b_text=b_clause,
                )
                sentences.append(
                    _sentence_with_cites(
                        _seeded_text(
                            f'synthesis:fallback:{title}:{axis_text}',
                            fallback_options,
                        ),
                        fallback_cites,
                        max_keys=5,
                    )
                )
    if not sentences:
        return ''
    sentences.insert(0, lead_sentence)
    return ' '.join(s for s in sentences if s).strip()


def _compose_decision_paragraph(
    *,
    title: str,
    cluster_a: dict[str, Any],
    cluster_b: dict[str, Any],
    a_record: dict[str, Any],
    b_record: dict[str, Any],
    benchmark_records: list[dict[str, Any]],
    protocol_citations: list[str],
    stem_counts: dict[str, int] | None = None,
) -> str:
    a_axis = _normalized_axis_series(cluster_a.get('axes') or [], limit=2) or _tmpl('fallbacks', 'lens')
    b_axis = _normalized_axis_series(cluster_b.get('axes') or [], limit=2) or _tmpl('fallbacks', 'lens')
    a_label = _sentence_initial(cluster_a.get('label') or '')
    b_label = _sentence_initial(cluster_b.get('label') or '')
    lead_options = _job_template_options(
        'decision',
        'lead',
        fallback=[
            'In {title_lower}, the practical decision is less about choosing a winner than about deciding which constraint the target setting will not relax',
            'For builders working on {title_lower}, the meaningful choice is which side of the trade-off must survive under the target protocol',
        ],
        title=title,
        title_lower=title.lower(),
        a_axis=a_axis,
        b_axis=b_axis,
    )
    sentences = [
        _sentence_with_cites(
            _pick_text_candidate(
                seed=f'decision:{title}:{a_axis}:{b_axis}',
                title=title,
                options=lead_options,
                stem_counts=stem_counts,
            ),
            [],
            max_keys=0,
        )
    ]
    evidence_found = False
    if a_record.get('text') and b_record.get('text'):
        a_clause = _inline_proposition(a_record.get('text') or '', kind='fact', limit=220)
        b_clause = _inline_proposition(b_record.get('text') or '', kind='fact', limit=220)
        both_cites = _uniq((a_record.get('citations') or []) + (b_record.get('citations') or []))
        if a_clause and b_clause:
            evidence_found = True
            sentences.append(
                _sentence_with_cites(
                    f'The case for {a_label} is best supported by evidence that {a_clause}, whereas the case for {_mid_sentence_label(b_label)} is better supported by evidence that {b_clause}',
                    both_cites,
                    max_keys=5,
                )
            )
    benchmark = _first_nonempty(benchmark_records)
    if benchmark:
        benchmark_clause = _clause(benchmark.get('text') or '', limit=220)
        if benchmark_clause:
            evidence_found = True
            sentences.append(_sentence_with_cites(benchmark_clause, benchmark.get('citations') or [], max_keys=4))
    if protocol_citations:
        evidence_found = True
        protocol_options = _job_template_options(
            'decision',
            'protocol',
            fallback=['Whichever route is preferred, the comparison only holds when benchmark scope, metric choice, and deployment constraints are matched across papers'],
            title=title,
            title_lower=title.lower(),
            a_axis=a_axis,
            b_axis=b_axis,
        )
        sentences.append(
            _sentence_with_cites(
                _pick_text_candidate(
                    seed=f'decision:protocol:{title}:{a_axis}:{b_axis}',
                    title=title,
                    options=protocol_options,
                    stem_counts=stem_counts,
                ),
                protocol_citations,
                max_keys=4,
            )
        )
    if not evidence_found:
        return ''
    return ' '.join(s for s in sentences if s).strip()


def _compose_limitation_paragraph(
    *,
    title: str,
    cluster_a: dict[str, Any],
    cluster_b: dict[str, Any],
    limits: list[dict[str, Any]],
    protocol_citations: list[str],
    rq: str,
    stem_counts: dict[str, int] | None = None,
) -> str:
    title_lower = title.lower()
    lead_options = _job_template_options(
        'limitation',
        'lead',
        fallback=[
            'Several issues still block a clean ranking across {title_lower}',
            'The main unresolved issue in {title_lower} is not just which route performs better, but which parts of the evidence can actually be compared without distortion',
        ],
        title=title,
        title_lower=title_lower,
    )
    sentences = [
        _sentence_with_cites(
            _seeded_text(
            f'limits:{title}:{rq}',
            lead_options,
            ),
            [],
            max_keys=0,
        )
    ]
    for record in limits[:2]:
        limit_text = _support_text(record.get('text') or '', kind='limit')
        if limit_text:
            sentences.append(_sentence_with_cites(limit_text, record.get('citations') or [], max_keys=4))
    if protocol_citations:
        protocol_options = _job_template_options(
            'limitation',
            'protocol',
            fallback=[
                'A firmer answer will require papers to report task, metric, and constraint choices consistently enough to compare {cluster_a} and {cluster_b} on the same basis',
                'The gap will narrow only when later work keeps task, metric, and deployment assumptions explicit enough for {cluster_a} and {cluster_b} to be read side by side',
            ],
            cluster_a=str(cluster_a.get('label') or '').strip(),
            cluster_b=str(cluster_b.get('label') or '').strip(),
        )
        sentences.append(
            _sentence_with_cites(
                _pick_text_candidate(
                    seed=f'limits:protocol:{title}:{cluster_a.get("label")}:{cluster_b.get("label")}',
                    title=title,
                    options=protocol_options,
                    stem_counts=stem_counts,
                ),
                protocol_citations,
                max_keys=4,
            )
        )
    elif rq:
        rq_options = _job_template_options(
            'limitation',
            'rq_fallback',
            fallback=['A useful open question is therefore how future work can answer the subsection question, `{rq}`, under protocols that remain aligned across neighboring settings.'],
            rq=rq,
        )
        sentences.append(_seeded_text(f'limits:rq:{title}:{rq}', rq_options))
    return ' '.join(s for s in sentences if s).strip()


def _compose_evidence_breadth_paragraph(
    *,
    title: str,
    current_citations: set[str],
    records_a: list[dict[str, Any]],
    records_b: list[dict[str, Any]],
    global_records: list[dict[str, Any]],
    axes: list[str],
    stem_counts: dict[str, int] | None = None,
) -> tuple[str, set[str]]:
    selected: list[dict[str, Any]] = []
    new_keys: set[str] = set()
    for pool in (records_a, records_b, global_records):
        for record in pool:
            cites = [str(x).strip() for x in (record.get('citations') or []) if str(x).strip()]
            unseen = [cite for cite in cites if cite not in current_citations and cite not in new_keys]
            if not unseen:
                continue
            picked = dict(record)
            picked['citations'] = unseen[:3]
            selected.append(picked)
            new_keys.update(unseen)
            if len(selected) >= 3 or len(current_citations | new_keys) >= 12:
                break
        if len(selected) >= 3 or len(current_citations | new_keys) >= 12:
            break
    if len(selected) < 2:
        return '', set()
    axis_text = _normalized_axis_series(axes, limit=3) or _tmpl('fallbacks', 'lens')
    lead_options = _job_template_options(
        'breadth',
        'lead',
        fallback=[
            'Related work around {title_lower} widens the record by varying {axis_text} without removing the setup differences that still matter most',
            'Neighboring studies on {title_lower} revisit the comparison by changing {axis_text} while keeping the same broad question in view',
        ],
        title=title,
        title_lower=title.lower(),
        axis_text=axis_text,
    )
    body_options = _job_template_options(
        'breadth',
        'body',
        fallback=[
            'Read together, those studies show how choices about {axis_text} reshape what the same headline result can mean',
            'Across that broader slice, the comparison still turns on how {axis_text} are fixed rather than on one isolated mechanism',
        ],
        axis_text=axis_text,
    )
    intro_options = lead_options + body_options
    intro = _sentence_with_cites(
        _pick_text_candidate(
            seed=f'breadth:intro:{title}:{axis_text}',
            title=title,
            options=intro_options,
            stem_counts=stem_counts,
        ),
        [],
        max_keys=0,
    )
    body: list[str] = []
    for record in selected:
        record_text = _support_text(record.get('text') or '', kind='fact')
        if record_text:
            body.append(_sentence_with_cites(record_text, record.get('citations') or [], max_keys=3))
    paragraph = ' '.join([intro] + [line for line in body if line]).strip()
    return paragraph, new_keys


def _make_paragraphs(
    pack: dict[str, Any],
    title: str,
    *,
    opener_stem_counts: dict[str, int] | None = None,
    evidence_stem_counts: dict[str, int] | None = None,
) -> list[str]:
    thesis = _normalize_thesis(pack.get('thesis') or '', title) or _render('fallbacks', 'thesis', title=title)
    tension = _normalize_tension(pack.get('tension_statement') or '', title) or _tmpl('fallbacks', 'tension_statement')
    rq = _clean(_deslash(pack.get('rq') or ''), limit=220) or _tmpl('fallbacks', 'rq')
    pack_axes = [str(a).strip() for a in (pack.get('axes') or []) if str(a).strip()]
    contrast_hook = _normalize_axis(pack.get('contrast_hook') or '')
    plan = [item for item in (pack.get('paragraph_plan') or []) if isinstance(item, dict)]
    raw_cards = [x for x in (pack.get('comparison_cards') or []) if isinstance(x, dict)]
    cards: list[dict[str, Any]] = []
    seen_axes: set[tuple[str, str, str]] = set()
    for card in raw_cards:
        axis = _normalize_axis(card.get('axis') or '') or 'axis'
        a_label = _normalize_label(card.get('A_label') or '') or 'a'
        b_label = _normalize_label(card.get('B_label') or '') or 'b'
        key = (axis, a_label, b_label)
        if key in seen_axes:
            continue
        seen_axes.add(key)
        cards.append(card)
        if len(cards) >= 8:
            break

    anchors = [x for x in (pack.get('anchor_facts') or []) if isinstance(x, dict)][:10]
    claims = [x for x in (pack.get('claim_candidates') or []) if isinstance(x, dict)][:8]
    limits = [x for x in (pack.get('limitation_hooks') or []) if isinstance(x, dict)][:8]
    evals = [x for x in (pack.get('evaluation_protocol') or []) if isinstance(x, dict)]

    cluster_a, cluster_b = _cluster_labels(pack, cards)
    profiles, global_support = _build_cluster_profiles(
        cards=cards,
        anchors=anchors,
        claims=claims,
        limits=limits,
        cluster_a=cluster_a,
        cluster_b=cluster_b,
        cluster_specs=[x for x in (pack.get('clusters') or []) if isinstance(x, dict)],
    )
    preferred_axes = pack_axes[:3] or ([contrast_hook] if contrast_hook else [])
    if not profiles['A'].get('axes'):
        profiles['A']['axes'] = preferred_axes[:3]
    if not profiles['B'].get('axes'):
        profiles['B']['axes'] = preferred_axes[:3]
    benchmark_records, protocol_citations = _evaluation_support(evals)

    seed_cites = _uniq(
        [str(x).strip() for card in cards[:3] for x in (card.get('citations') or []) if str(x).strip()]
        + [str(x).strip() for item in anchors[:2] for x in (item.get('citations') or []) if str(x).strip()]
        + [str(x).strip() for item in claims[:2] for x in (item.get('citations') or []) if str(x).strip()]
    )

    paragraphs: list[str] = []
    states = {
        'A': {'facts': 0, 'anchors': 0, 'claims': 0, 'limits': 0},
        'B': {'facts': 0, 'anchors': 0, 'claims': 0, 'limits': 0},
        'global': {'anchors': 0, 'claims': 0, 'limits': 0, 'benchmarks': 0},
    }

    setup_seed = _first_nonempty(global_support['claims']) or _first_nonempty(global_support['anchors']) or _first_nonempty(profiles['A']['facts']) or _first_nonempty(profiles['B']['facts'])
    thin_pack = any(
        re.search(r'(?i)(?:too few comparison cards|too few usable claim candidates|upstream blocker)', str(msg or ''))
        for msg in (pack.get('pack_warnings') or [])
    )
    if plan:
        setup_paragraph = _compose_setup_paragraph(
            title=title,
            thesis=thesis,
            tension=tension,
            opener_mode=str(pack.get('opener_mode') or ''),
            cluster_a=cluster_a,
            cluster_b=cluster_b,
            axes=_uniq((profiles['A'].get('axes') or []) + (profiles['B'].get('axes') or []) + preferred_axes),
            citations=seed_cites,
            seed_record=setup_seed,
            stem_counts=opener_stem_counts,
        )
        if setup_paragraph:
            paragraphs.append(setup_paragraph)
            if evidence_stem_counts is not None and setup_seed.get('text'):
                setup_stem = _record_stem(setup_seed.get('text') or '')
                if setup_stem:
                    evidence_stem_counts[setup_stem] = evidence_stem_counts.get(setup_stem, 0) + 1

    for item in plan[1:] if plan else []:
        role = str(item.get('argument_role') or '').strip()
        paragraph = ''
        if role in {'mechanism_cluster_A', 'implementation_cluster_A', 'evaluation_cluster_A'}:
            facts = _take(profiles['A']['facts'], states['A'], 'facts', 2 if role != 'evaluation_cluster_A' else 0)
            anchors_local = _take_with_fallback(profiles['A']['anchors'], states['A'], 'anchors', global_support['anchors'], states['global'], 'anchors', 2)
            claims_local = _take_with_fallback(profiles['A']['claims'], states['A'], 'claims', global_support['claims'], states['global'], 'claims', 2 if role in {'mechanism_cluster_A', 'implementation_cluster_A'} else 0)
            limits_local = _take_with_fallback(profiles['A']['limits'], states['A'], 'limits', global_support['limits'], states['global'], 'limits', 1 if role == 'evaluation_cluster_A' else 0)
            benchmarks = _take(benchmark_records, states['global'], 'benchmarks', 1 if role == 'evaluation_cluster_A' else 0)
            paragraph = _compose_cluster_paragraph(
                title=title,
                plan_item=item,
                profile=profiles['A'],
                other_label=profiles['B']['label'],
                kind='mechanism' if role == 'mechanism_cluster_A' else ('implementation' if role == 'implementation_cluster_A' else 'evaluation'),
                facts=facts,
                anchors=anchors_local,
                claims=claims_local,
                limits=limits_local,
                benchmarks=benchmarks,
                protocol_citations=protocol_citations,
                stem_counts=opener_stem_counts,
                evidence_stem_counts=evidence_stem_counts,
            )
        elif role in {'contrast_cluster_B', 'implementation_cluster_B', 'evaluation_cluster_B'}:
            facts = _take(profiles['B']['facts'], states['B'], 'facts', 2 if role != 'evaluation_cluster_B' else 0)
            anchors_local = _take_with_fallback(profiles['B']['anchors'], states['B'], 'anchors', global_support['anchors'], states['global'], 'anchors', 2)
            claims_local = _take_with_fallback(profiles['B']['claims'], states['B'], 'claims', global_support['claims'], states['global'], 'claims', 2 if role in {'contrast_cluster_B', 'implementation_cluster_B'} else 0)
            limits_local = _take_with_fallback(profiles['B']['limits'], states['B'], 'limits', global_support['limits'], states['global'], 'limits', 1 if role == 'evaluation_cluster_B' else 0)
            benchmarks = _take(benchmark_records, states['global'], 'benchmarks', 1 if role == 'evaluation_cluster_B' else 0)
            paragraph = _compose_cluster_paragraph(
                title=title,
                plan_item=item,
                profile=profiles['B'],
                other_label=profiles['A']['label'],
                kind='mechanism' if role == 'contrast_cluster_B' else ('implementation' if role == 'implementation_cluster_B' else 'evaluation'),
                facts=facts,
                anchors=anchors_local,
                claims=claims_local,
                limits=limits_local,
                benchmarks=benchmarks,
                protocol_citations=protocol_citations,
                stem_counts=opener_stem_counts,
                evidence_stem_counts=evidence_stem_counts,
            )
        elif role == 'cross_paper_synthesis':
            paragraph = _compose_synthesis_paragraph(
                title=title,
                plan_item=item,
                cluster_a=profiles['A'],
                cluster_b=profiles['B'],
                cards=cards,
                stem_counts=opener_stem_counts,
                evidence_stem_counts=evidence_stem_counts,
            )
        elif role == 'decision_guidance':
            a_decision = _first_nonempty(_take_with_fallback(profiles['A']['claims'], states['A'], 'claims', profiles['A']['anchors'], states['A'], 'anchors', 1)) or _first_nonempty(profiles['A']['facts'])
            b_decision = _first_nonempty(_take_with_fallback(profiles['B']['claims'], states['B'], 'claims', profiles['B']['anchors'], states['B'], 'anchors', 1)) or _first_nonempty(profiles['B']['facts'])
            benchmarks = _take(benchmark_records, states['global'], 'benchmarks', 1)
            paragraph = _compose_decision_paragraph(
                title=title,
                cluster_a=profiles['A'],
                cluster_b=profiles['B'],
                a_record=a_decision,
                b_record=b_decision,
                benchmark_records=benchmarks,
                protocol_citations=protocol_citations,
                stem_counts=opener_stem_counts,
            )
        elif role == 'limitations_open_questions':
            lims = _take_with_fallback(profiles['A']['limits'], states['A'], 'limits', profiles['B']['limits'], states['B'], 'limits', 1)
            lims += _take_with_fallback(global_support['limits'], states['global'], 'limits', profiles['B']['limits'], states['B'], 'limits', 1)
            paragraph = _compose_limitation_paragraph(
                title=title,
                cluster_a=profiles['A'],
                cluster_b=profiles['B'],
                limits=lims,
                protocol_citations=protocol_citations,
                rq=rq,
                stem_counts=opener_stem_counts,
            )
        if paragraph:
            paragraphs.append(paragraph)

    if not paragraphs:
        opener_seed_cites = _cites(seed_cites, max_keys=4)
        fallback = _render_seeded_opener(
            seed=f"opener:{title}:{thesis}:{tension}",
            title=title,
            stem_counts=opener_stem_counts,
            title_lower=title.lower(),
            thesis=thesis,
            seed_cites=opener_seed_cites,
            tension=tension,
            rq=rq,
        )
        if fallback:
            paragraphs.append(fallback)

    citation_keys = _citation_keys_in_paragraphs(paragraphs)
    remaining_a = _dedupe_records(
        profiles['A']['anchors']
        + profiles['A']['claims']
        + profiles['A']['facts']
        + profiles['A']['limits']
    )
    remaining_b = _dedupe_records(
        profiles['B']['anchors']
        + profiles['B']['claims']
        + profiles['B']['facts']
        + profiles['B']['limits']
    )
    remaining_global = _dedupe_records(
        global_support['anchors']
        + global_support['claims']
        + global_support['limits']
        + [
            _normalize_support_record(item.get('text') or '', [str(x).strip() for x in (item.get('citations') or []) if str(x).strip()], kind='anchor')
            for item in anchors
            if isinstance(item, dict)
        ]
        + [
            _normalize_support_record(item.get('claim') or '', [str(x).strip() for x in (item.get('citations') or []) if str(x).strip()], kind='claim')
            for item in claims
            if isinstance(item, dict)
        ]
        + [
            _normalize_support_record(item.get('excerpt') or '', [str(x).strip() for x in (item.get('citations') or []) if str(x).strip()], kind='limit')
            for item in limits
            if isinstance(item, dict)
        ]
    )
    extra_breadth_budget = 1 if (len(paragraphs) < 9 or _body_char_count(paragraphs) < 3600) else 0
    while not thin_pack and extra_breadth_budget > 0:
        extra_paragraph, new_keys = _compose_evidence_breadth_paragraph(
            title=title,
            current_citations=citation_keys,
            records_a=remaining_a,
            records_b=remaining_b,
            global_records=remaining_global,
            axes=_uniq((profiles['A'].get('axes') or []) + (profiles['B'].get('axes') or [])),
            stem_counts=opener_stem_counts,
        )
        if not extra_paragraph or not new_keys:
            break
        insert_at = len(paragraphs) - 1 if len(paragraphs) >= 2 else len(paragraphs)
        paragraphs.insert(insert_at, extra_paragraph)
        citation_keys.update(new_keys)
        extra_breadth_budget -= 1

    paragraphs = _dedupe_evidence_sentences_in_paragraphs(paragraphs)
    cleaned: list[str] = []
    seen_keys: set[str] = set()
    for paragraph in paragraphs:
        text = re.sub(r'\s+', ' ', str(paragraph or '').strip())
        key = re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()
        if not text or not key or key in seen_keys:
            continue
        seen_keys.add(key)
        cleaned.append(text)

    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--unit-id', default='')
    parser.add_argument('--inputs', default='')
    parser.add_argument('--outputs', default='')
    parser.add_argument('--checkpoint', default='')
    parser.add_argument('--rewrite', action='store_true', help='rewrite existing H3 files instead of bootstrapping missing ones only')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, backup_existing, decisions_has_approval, ensure_dir, load_yaml, now_iso_seconds, parse_semicolon_list, refresh_sections_manifest, upsert_checkpoint_block
    from tooling.pipeline_text import slug_unit_id
    from tooling.quality_gate import check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or 'U100').strip() or 'U100'
    inputs = parse_semicolon_list(args.inputs)
    outputs = parse_semicolon_list(args.outputs) or ['sections/sections_manifest.jsonl', 'sections/h3_bodies.refined.ok']

    out_rel = next((x for x in outputs if x.endswith('sections_manifest.jsonl')), 'sections/sections_manifest.jsonl')
    marker_rel = next((x for x in outputs if x.endswith('.refined.ok')), 'sections/h3_bodies.refined.ok')
    out_path = workspace / out_rel
    marker_path = workspace / marker_rel
    sections_dir = out_path.parent
    # Deprecated soft-freeze marker kept some workspaces pinned to stale prose
    # even during explicit unit reruns. Only honor the new hard-freeze marker.
    freeze_marker = sections_dir / 'h3_bodies.freeze.hard.ok'
    ensure_dir(sections_dir)
    prerequisite_relpaths = inputs or [
        'DECISIONS.md',
        'outline/outline.yml',
        'outline/writer_context_packs.jsonl',
        'outline/evidence_drafts.jsonl',
        'outline/evidence_bindings.jsonl',
        'citations/ref.bib',
    ]
    prerequisites = [workspace / rel for rel in prerequisite_relpaths]
    prerequisites.append(Path(__file__).resolve())
    marker_is_current = _refinement_marker_is_current(marker_path, prerequisites)
    if marker_path.exists() and not marker_is_current:
        marker_path.unlink()

    decisions_path = workspace / 'DECISIONS.md'
    if not decisions_has_approval(decisions_path, 'C2'):
        block = '\n'.join([
            '## C5 section writing request',
            '',
            '- This unit writes prose into per-section files under `sections/`.',
            '- Please tick `Approve C2` in `DECISIONS.md`, then rerun this unit.',
            '',
        ])
        upsert_checkpoint_block(decisions_path, 'C5', block)
        return 2

    outline = load_yaml(workspace / 'outline' / 'outline.yml') if (workspace / 'outline' / 'outline.yml').exists() else []
    packs = {str(r.get('sub_id') or '').strip(): r for r in _load_jsonl(workspace / 'outline' / 'writer_context_packs.jsonl') if str(r.get('sub_id') or '').strip()}
    if not packs:
        briefs = {str(r.get('sub_id') or '').strip(): r for r in _load_jsonl(workspace / 'outline' / 'subsection_briefs.jsonl') if str(r.get('sub_id') or '').strip()}
        evidence = {str(r.get('sub_id') or '').strip(): r for r in _load_jsonl(workspace / 'outline' / 'evidence_drafts.jsonl') if str(r.get('sub_id') or '').strip()}
        for sid, brief in briefs.items():
            pack = dict(brief)
            pack.update(evidence.get(sid) or {})
            pack.setdefault('comparison_cards', pack.get('concrete_comparisons') or [])
            pack.setdefault('anchor_facts', [])
            pack.setdefault('limitation_hooks', pack.get('failures_limitations') or [])
            packs[sid] = pack

    records: list[dict[str, Any]] = []
    generated_at = now_iso_seconds()
    opener_stem_counts: dict[str, int] = {}
    evidence_stem_counts: dict[str, int] = {}

    def add_record(rec: dict[str, Any]) -> None:
        p = workspace / str(rec.get('path') or '')
        exists = p.exists() and p.stat().st_size > 0
        rec['exists'] = bool(exists)
        rec['generated_at'] = generated_at
        if exists:
            text = p.read_text(encoding='utf-8', errors='ignore')
            rec['citations'] = _uniq(re.findall(r'\[@([^\]]+)\]', text))
            rec['bytes'] = p.stat().st_size
        records.append(rec)

    for name, title in [('abstract', 'Abstract'), ('discussion', 'Discussion'), ('conclusion', 'Conclusion')]:
        add_record({'kind': 'global', 'id': name, 'title': title, 'path': f'sections/{name}.md'})

    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get('id') or '').strip()
            sec_title = str(sec.get('title') or '').strip()
            subs = [sub for sub in (sec.get('subsections') or []) if isinstance(sub, dict)]
            if subs and sec_id:
                lead_path = sections_dir / f'{slug_unit_id(sec_id)}_lead.md'
                add_record({'kind': 'h2_lead', 'id': sec_id, 'title': sec_title, 'section_id': sec_id, 'section_title': sec_title, 'path': str(lead_path.relative_to(workspace))})
            elif sec_id:
                add_record({'kind': 'h2', 'id': sec_id, 'title': sec_title, 'section_id': sec_id, 'section_title': sec_title, 'path': f'sections/{slug_unit_id(sec_id)}.md'})

            for sub in subs:
                sub_id = str(sub.get('id') or '').strip()
                title = str(sub.get('title') or '').strip()
                if not sub_id or not title:
                    continue
                path = sections_dir / f'{slug_unit_id(sub_id)}.md'
                should_write = True
                if (freeze_marker.exists() or marker_is_current) and path.exists() and path.stat().st_size > 0:
                    should_write = False
                if should_write:
                    pack = packs.get(sub_id) or {'title': title}
                    text = '\n\n'.join(
                        _make_paragraphs(
                            pack,
                            title,
                            opener_stem_counts=opener_stem_counts,
                            evidence_stem_counts=evidence_stem_counts,
                        )
                    ).rstrip() + '\n'
                    if path.exists() and path.stat().st_size > 0:
                        backup_existing(path)
                    atomic_write_text(path, text)
                add_record({'kind': 'h3', 'id': sub_id, 'title': title, 'section_id': sec_id, 'section_title': sec_title, 'path': str(path.relative_to(workspace))})

    atomic_write_text(out_path, '\n'.join(json.dumps(r, ensure_ascii=False) for r in records).rstrip() + '\n')
    refresh_sections_manifest(workspace, out_rel)

    issues = check_unit_outputs(skill='subsection-writer', workspace=workspace, outputs=[out_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill='subsection-writer', issues=issues)
        return 2
    if not marker_is_current:
        print(
            f'Bootstrap H3 bodies generated. Review and refine them, then create `{marker_rel}` '
            'after semantic QA before rerunning this unit.'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
