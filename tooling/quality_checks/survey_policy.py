from __future__ import annotations

from pathlib import Path


def pipeline_profile_name(workspace: Path) -> str:
    from tooling.common import pipeline_profile
    return pipeline_profile(workspace)


def draft_profile(workspace: Path) -> str:
    """Return the draft strictness profile from `queries.md` (best-effort).

    Supported values: `survey`, `deep`, and `course_paper`.
    """
    from tooling.common import pipeline_query_default

    profile = pipeline_profile_name(workspace)
    default = str(pipeline_query_default(workspace, "draft_profile", "" if profile != "arxiv-survey" else "survey") or "").strip().lower()
    default = default.replace("-", "_")
    if default not in {"survey", "deep", "course_paper"}:
        default = "survey" if profile == "arxiv-survey" else "default"

    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key != "draft_profile":
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower().replace("-", "_")
            if value in {"survey", "deep", "course_paper"}:
                return value
            return default
    except Exception:
        return default
    return default


def citation_target(workspace: Path) -> str:
    """Return whether citation loops target the hard or recommended budget."""

    from tooling.common import pipeline_query_default

    profile = pipeline_profile_name(workspace)
    default = str(
        pipeline_query_default(
            workspace,
            "citation_target",
            "" if profile != "arxiv-survey" else "recommended",
        )
        or ""
    ).strip().lower()
    if default not in {"recommended", "hard"}:
        default = "recommended" if profile == "arxiv-survey" else "hard"

    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            if key.strip().lower().replace(" ", "_") != "citation_target":
                continue
            normalized = value.split("#", 1)[0].strip().strip('"').strip("'").lower()
            if normalized in {"recommended", "rec"}:
                return "recommended"
            if normalized in {"hard", "min", "minimum"}:
                return "hard"
            return default
    except Exception:
        return default
    return default


def global_citation_min_subsections(workspace: Path) -> int:
    """Return the minimum subsection-mapping count for treating a bibkey as globally in-scope.

    Config (queries.md): `- global_citation_min_subsections: <int>`

    Rationale: some works are legitimately cross-cutting (foundations/benchmarks/surveys).
    This threshold lets the pipeline stay strict by default while allowing controlled flexibility.
    """

    from tooling.common import pipeline_query_default

    default = int(pipeline_query_default(workspace, "global_citation_min_subsections", 4) or 4)
    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key != "global_citation_min_subsections":
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip()
            if not value:
                return default
            try:
                n = int(value)
            except Exception:
                return default
            if n <= 0:
                return default
            return n
    except Exception:
        return default
    return default


def _query_int(workspace: Path, *, keys: set[str], default: int) -> int:
    """Best-effort read an int value from `queries.md`."""
    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return int(default)

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key not in keys:
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip()
            if not value:
                return int(default)
            try:
                n = int(value)
            except Exception:
                return int(default)
            return n if n > 0 else int(default)
    except Exception:
        return int(default)
    return int(default)


def core_size(workspace: Path) -> int:
    """Core set size contract (default: A150++ = 300 for arxiv-survey pipelines)."""
    from tooling.common import pipeline_query_default

    profile = pipeline_profile_name(workspace)
    default = int(pipeline_query_default(workspace, "core_size", 300 if profile == "arxiv-survey" else 0) or 0)
    return _query_int(workspace, keys={"core_size"}, default=default)


def per_subsection(workspace: Path) -> int:
    """Per-H3 mapping contract (default: A150++ = 28 for arxiv-survey pipelines)."""
    from tooling.common import pipeline_query_default

    profile = pipeline_profile_name(workspace)
    default = int(pipeline_query_default(workspace, "per_subsection", 28 if profile == "arxiv-survey" else 3) or 0)
    return _query_int(workspace, keys={"per_subsection"}, default=default)


def quality_contract_int(workspace: Path, *, keys: tuple[str, ...], default: int) -> int:
    from tooling.common import pipeline_quality_contract_value

    value = pipeline_quality_contract_value(workspace, *keys, default=default)
    try:
        parsed = int(value)
    except Exception:
        return int(default)
    return parsed if parsed > 0 else int(default)


def survey_citation_policy(workspace: Path, *, bibliography_size: int, h3_count: int) -> dict[str, int | float | str]:
    """Resolve one citation budget for all survey-family producers and gates."""
    from tooling.common import pipeline_quality_contract_value

    profile = draft_profile(workspace)
    defaults: dict[str, dict[str, int | float]] = {
        "survey": {
            "unique_hard_floor": 150,
            "unique_recommended": 165,
            "global_budget_per_h3": 14,
            "base": 35,
            "bibliography_fraction": 0.50,
            "recommended_fraction": 0.55,
        },
        "deep": {
            "unique_hard_floor": 165,
            "unique_recommended": 165,
            "global_budget_per_h3": 16,
            "base": 40,
            "bibliography_fraction": 0.60,
            "recommended_fraction": 0.60,
        },
        "course_paper": {
            "unique_hard_floor": 24,
            "unique_recommended": 32,
            "global_budget_per_h3": 3,
            "base": 6,
            "bibliography_fraction": 0.35,
            "recommended_fraction": 0.45,
        },
    }
    selected = defaults.get(profile, defaults["survey"])

    def _number(key: str) -> int | float:
        fallback = selected[key]
        value = pipeline_quality_contract_value(
            workspace,
            "citation_policy",
            "by_profile",
            profile,
            key,
            default=fallback,
        )
        try:
            return float(value) if isinstance(fallback, float) else int(value)
        except (TypeError, ValueError):
            return fallback

    floor = int(_number("unique_hard_floor"))
    recommended_floor = int(_number("unique_recommended"))
    global_budget_per_h3 = int(_number("global_budget_per_h3"))
    base = int(_number("base"))
    fraction = float(_number("bibliography_fraction"))
    recommended_fraction = float(_number("recommended_fraction"))

    structural = base + global_budget_per_h3 * max(0, int(h3_count))
    bibliography_target = int(max(0, bibliography_size) * fraction)
    hard = max(floor, bibliography_target)
    recommended = max(hard, recommended_floor, int(max(0, bibliography_size) * recommended_fraction))
    if bibliography_size > 0:
        hard = min(hard, bibliography_size)
        recommended = min(recommended, bibliography_size)

    return {
        "profile": profile,
        "hard": hard,
        "recommended": recommended,
        "structural": structural,
        "bibliography_target": bibliography_target,
        "bibliography_fraction": fraction,
        "recommended_fraction": recommended_fraction,
    }


def evidence_mode(workspace: Path) -> str:
    from tooling.common import pipeline_query_default

    default = str(pipeline_query_default(workspace, "evidence_mode", "abstract") or "").strip().lower()
    if default not in {"abstract", "fulltext"}:
        default = "abstract"

    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key != "evidence_mode":
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value in {"abstract", "fulltext"}:
                return value
            return default
    except Exception:
        return default
    return default
