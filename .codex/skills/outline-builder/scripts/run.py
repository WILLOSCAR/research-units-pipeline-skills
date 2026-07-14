from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = PACKAGE_ROOT / "assets" / "outline_defaults.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
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

    from tooling.common import (
        backup_existing,
        dump_yaml,
        load_yaml,
        parse_semicolon_list,
        read_jsonl,
        refinement_marker_is_current,
    )

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["outline/taxonomy.yml"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/outline.yml"]

    out_path = workspace / outputs[0]

    defaults = load_yaml(DEFAULTS_PATH) if DEFAULTS_PATH.exists() else None
    if not isinstance(defaults, dict):
        raise SystemExit(f"Invalid outline defaults asset: {DEFAULTS_PATH}")
    _validate_defaults(defaults)

    section_first_inputs = len(inputs) >= 2 and inputs[0].endswith("chapter_skeleton.yml") and inputs[1].endswith("section_briefs.jsonl")
    freeze_marker = out_path.parent / "outline.refined.ok"
    prerequisites = [out_path, DEFAULTS_PATH, Path(__file__), *[workspace / item for item in inputs]]
    if out_path.exists() and out_path.stat().st_size > 0:
        if refinement_marker_is_current(freeze_marker, prerequisites):
            return 0
        if freeze_marker.exists():
            freeze_marker.unlink()
        existing = out_path.read_text(encoding="utf-8", errors="ignore")
        if not _is_placeholder(existing):
            backup_existing(out_path)

    if section_first_inputs:
        chapter_skeleton_path = workspace / inputs[0]
        section_briefs_path = workspace / inputs[1]
        outline = _outline_from_section_first_inputs(
            chapter_skeleton_path=chapter_skeleton_path,
            section_briefs_path=section_briefs_path,
            defaults=defaults,
            load_yaml=load_yaml,
            read_jsonl=read_jsonl,
        )
    else:
        taxonomy_path = workspace / inputs[0]
        taxonomy = load_yaml(taxonomy_path) if taxonomy_path.exists() else None
        if not isinstance(taxonomy, list) or not taxonomy:
            raise SystemExit(f"Invalid taxonomy in {taxonomy_path}")
        outline = _outline_from_taxonomy(taxonomy=taxonomy, defaults=defaults)

    dump_yaml(out_path, outline)
    return 0


def _outline_from_taxonomy(*, taxonomy: list[dict[str, Any]], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    outline: list[dict[str, Any]] = [
        _fixed_section(defaults=defaults, key="intro_section"),
        _fixed_section(defaults=defaults, key="related_work_section"),
    ]

    section_no = 3
    for topic in taxonomy:
        if not isinstance(topic, dict):
            continue
        name = str(topic.get("name") or "").strip() or f"Topic {section_no}"
        topic_desc = str(topic.get("description") or "").strip()
        children = topic.get("children") or []
        section_id = str(section_no)

        section: dict[str, Any] = {
            "id": section_id,
            "title": name,
            "bullets": _section_meta_bullets(title=name, hint=topic_desc, defaults=defaults),
            "subsections": [],
        }

        subsection_no = 1
        for child in children if isinstance(children, list) else []:
            if not isinstance(child, dict):
                continue
            child_name = str(child.get("name") or "").strip() or f"Subtopic {section_id}.{subsection_no}"
            child_desc = str(child.get("description") or "").strip()
            subsection_id = f"{section_id}.{subsection_no}"
            section["subsections"].append(
                {
                    "id": subsection_id,
                    "title": child_name,
                    "bullets": _subsection_bullets(parent=name, title=child_name, hint=child_desc, defaults=defaults),
                }
            )
            subsection_no += 1

        outline.append(section)
        section_no += 1

    return outline


def _outline_from_section_first_inputs(
    *,
    chapter_skeleton_path: Path,
    section_briefs_path: Path,
    defaults: dict[str, Any],
    load_yaml,
    read_jsonl,
) -> list[dict[str, Any]]:
    skeleton = load_yaml(chapter_skeleton_path) if chapter_skeleton_path.exists() else None
    if not isinstance(skeleton, list) or not skeleton:
        raise SystemExit(f"Invalid chapter skeleton in {chapter_skeleton_path}")
    briefs = [row for row in read_jsonl(section_briefs_path) if isinstance(row, dict)] if section_briefs_path.exists() else []
    briefs_by_id = {str(row.get("section_id") or "").strip(): row for row in briefs}

    outline: list[dict[str, Any]] = [
        _fixed_section(defaults=defaults, key="intro_section"),
        _fixed_section(defaults=defaults, key="related_work_section"),
    ]
    for chapter in skeleton:
        if not isinstance(chapter, dict):
            continue
        section_id = str(chapter.get("id") or "").strip()
        title = str(chapter.get("title") or "").strip()
        rationale = str(chapter.get("rationale") or "").strip()
        if not section_id or not title:
            continue
        brief = briefs_by_id.get(section_id) or {}
        must_cover = [str(x).strip() for x in (brief.get("must_cover") or []) if str(x).strip()]
        section = {
            "id": section_id,
            "title": title,
            "bullets": _section_meta_bullets(title=title, hint=rationale or "; ".join(must_cover), defaults=defaults),
            "subsections": [],
        }
        subsection_seeds = brief.get("subsection_seeds") or []
        subsection_no = 1
        for seed in subsection_seeds:
            if not isinstance(seed, dict):
                continue
            child_name = str(seed.get("title") or "").strip()
            child_desc = str(seed.get("rationale") or "").strip()
            if not child_name:
                continue
            subsection_id = f"{section_id}.{subsection_no}"
            section["subsections"].append(
                {
                    "id": subsection_id,
                    "title": child_name,
                    "bullets": _subsection_bullets(parent=title, title=child_name, hint=child_desc, defaults=defaults),
                }
            )
            subsection_no += 1
        outline.append(section)
    return outline


def _validate_defaults(defaults: dict[str, Any]) -> None:
    for key in ("intro_section", "related_work_section", "section_defaults", "subsection_defaults"):
        if not isinstance(defaults.get(key), dict):
            raise SystemExit(f"Missing `{key}` in {DEFAULTS_PATH}")
    if not isinstance(defaults.get("comparison_axis_packs"), list):
        raise SystemExit(f"Missing `comparison_axis_packs` in {DEFAULTS_PATH}")
    if not str(defaults.get("fallback_comparison_axes") or "").strip():
        raise SystemExit(f"Missing `fallback_comparison_axes` in {DEFAULTS_PATH}")


def _fixed_section(*, defaults: dict[str, Any], key: str) -> dict[str, Any]:
    section = defaults.get(key)
    if not isinstance(section, dict):
        raise SystemExit(f"Missing `{key}` in {DEFAULTS_PATH}")
    title = str(section.get("title") or "").strip()
    bullets = [str(item).strip() for item in (section.get("bullets") or []) if str(item).strip()]
    if not title or not bullets:
        raise SystemExit(f"Invalid `{key}` config in {DEFAULTS_PATH}")
    return {
        "id": str(section.get("id") or "").strip() or ("1" if key == "intro_section" else "2"),
        "title": title,
        "bullets": bullets,
    }


def _hint_sentence(text: str, *, max_len: int = 220) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"\s+", " ", raw).strip()

    best = raw
    for sep in [".", "。", ";"]:
        idx = raw.find(sep)
        if idx > 40:
            best = raw[: idx + 1].strip()
            break

    if len(best) > int(max_len):
        best = best[: int(max_len)].rstrip()
    return best


def _render_template(template: str, **kwargs: str) -> str:
    return str(template or "").format(**kwargs).strip()


def _section_meta_bullets(*, title: str, hint: str = "", defaults: dict[str, Any]) -> list[str]:
    config = defaults.get("section_defaults") or {}
    if not isinstance(config, dict):
        raise SystemExit(f"Missing `section_defaults` in {DEFAULTS_PATH}")

    hint_short = _hint_sentence(hint)
    bullets = [
        _render_template(str(config.get("intent") or ""), title=title, hint_short=hint_short, parent=""),
        _render_template(str(config.get("rq") or ""), title=title, hint_short=hint_short, parent=""),
    ]
    scope_template = str(config.get("scope_cues") or "").strip()
    if hint_short and scope_template:
        bullets.append(_render_template(scope_template, title=title, hint_short=hint_short, parent=""))
    for key in ("evidence_needs", "expected_cites", "chapter_lead_plan"):
        bullets.append(_render_template(str(config.get(key) or ""), title=title, hint_short=hint_short, parent=""))
    return [bullet for bullet in bullets if bullet]


def _subsection_bullets(*, parent: str, title: str, hint: str = "", defaults: dict[str, Any]) -> list[str]:
    config = defaults.get("subsection_defaults") or {}
    if not isinstance(config, dict):
        raise SystemExit(f"Missing `subsection_defaults` in {DEFAULTS_PATH}")

    hint_short = _hint_sentence(hint)
    bullets = [
        _render_template(str(config.get("intent") or ""), title=title, parent=parent, hint_short=hint_short),
        _render_template(str(config.get("rq") or ""), title=title, parent=parent, hint_short=hint_short),
    ]
    scope_template = str(config.get("scope_cues") or "").strip()
    if hint_short and scope_template:
        bullets.append(_render_template(scope_template, title=title, parent=parent, hint_short=hint_short))
    for key in ("evidence_needs", "expected_cites", "concrete_comparisons", "evaluation_anchors"):
        bullets.append(_render_template(str(config.get(key) or ""), title=title, parent=parent, hint_short=hint_short))
    bullets.append(_comparison_axes_bullet(parent=parent, title=title, hint=hint, defaults=defaults))
    return [bullet for bullet in bullets if bullet]


def _comparison_axes_bullet(*, parent: str, title: str, hint: str = "", defaults: dict[str, Any]) -> str:
    text = " ".join([(title or ""), (hint or "")]).lower()
    packs = defaults.get("comparison_axis_packs") or []
    best_score = 0
    best_bullet = ""
    if isinstance(packs, list):
        for pack in packs:
            if not isinstance(pack, dict):
                continue
            keywords = [str(item).strip().lower() for item in (pack.get("keywords") or []) if str(item).strip()]
            if not keywords:
                continue
            score = sum(1 for keyword in keywords if keyword in text)
            if score <= 0:
                continue
            bullet = str(pack.get("bullet") or "").strip()
            if bullet and score > best_score:
                best_score = score
                best_bullet = bullet

    if best_bullet:
        return best_bullet

    fallback = str(defaults.get("fallback_comparison_axes") or "").strip()
    if fallback:
        return fallback
    raise SystemExit(f"Missing fallback comparison axes in {DEFAULTS_PATH}")


def _is_placeholder(text: str) -> bool:
    text = (text or "").strip().lower()
    if not text:
        return True
    if "(placeholder)" in text:
        return True
    if "<!-- scaffold" in text:
        return True
    if re.search(r"\b(?:todo|tbd|fixme)\b", text, flags=re.IGNORECASE):
        return True
    if re.search(r"(?m)^\s*#\s*outline\s*\(placeholder\)", text):
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
