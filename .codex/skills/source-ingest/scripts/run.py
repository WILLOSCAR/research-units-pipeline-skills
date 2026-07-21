from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


SUPPORTED_KINDS = {"webpage", "pdf", "markdown", "repo", "docs_site", "video"}
MAX_REPO_FILES = 24
MAX_DOCS_SITE_PAGES = 12
DOCS_SITE_MAX_DEPTH = 2


@dataclass
class SourceResult:
    source_id: str
    kind: str
    status: str
    title: str
    canonical_url: str
    local_path: str
    content_chars: int
    extracted_at: str
    extractor: str
    warning: str = ""
    required: bool = False


class _HTMLTextAndLinksParser(HTMLParser):
    def __init__(self, *, base_url: str):
        super().__init__()
        self.base_url = base_url
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(urllib.parse.urljoin(self.base_url, href))
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = (data or "").strip()
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)

    @property
    def title(self) -> str:
        return _normalize_space(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return _normalize_space("\n".join(self.text_parts))


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

    from tooling.common import atomic_write_text, ensure_dir, load_yaml, now_iso_seconds, parse_semicolon_list, write_jsonl

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ["sources/index.jsonl", "sources/provenance.jsonl"]
    index_path = workspace / outputs[0]
    prov_path = workspace / (outputs[1] if len(outputs) > 1 else "sources/provenance.jsonl")
    ensure_dir(index_path.parent)
    ensure_dir(prov_path.parent)
    ensure_dir(workspace / "sources" / "normalized")

    manifest_path = workspace / "sources" / "manifest.yml"
    if not manifest_path.exists():
        print(f"Missing manifest: {manifest_path}", file=sys.stderr)
        return 2

    data = load_yaml(manifest_path)
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list) or not sources:
        print("Manifest has no usable `sources:` entries.", file=sys.stderr)
        return 2

    extracted_at = now_iso_seconds()
    index_records: list[dict[str, Any]] = []
    provenance_records: list[dict[str, Any]] = []
    successes = 0
    failed_required_ids: list[str] = []

    for rec in sources:
        if not isinstance(rec, dict):
            continue
        source_id = str(rec.get("source_id") or "").strip()
        kind = str(rec.get("kind") or "").strip()
        required = bool(rec.get("required", False))
        if not source_id or kind not in SUPPORTED_KINDS:
            if required:
                failed_required_ids.append(source_id or "<missing-source-id>")
            continue

        try:
            result, prov = _ingest_one(workspace=workspace, rec=rec, extracted_at=extracted_at)
        except Exception as exc:
            result = SourceResult(
                source_id=source_id,
                kind=kind,
                status="failed",
                title=str(rec.get("label") or source_id),
                canonical_url=str(rec.get("locator") or ""),
                local_path="",
                content_chars=0,
                extracted_at=extracted_at,
                extractor=kind,
                warning=f"{type(exc).__name__}: {exc}",
                required=required,
            )
            prov = []

        index_records.append(result.__dict__)
        provenance_records.extend(prov)
        if result.status == "success":
            successes += 1
        elif required:
            failed_required_ids.append(source_id)

    write_jsonl(index_path, index_records)
    write_jsonl(prov_path, provenance_records)

    if successes == 0:
        print("No sources were ingested successfully.", file=sys.stderr)
        return 2
    if failed_required_ids:
        print(
            "Required sources failed ingestion: " + ", ".join(failed_required_ids),
            file=sys.stderr,
        )
        return 2
    return 0


def _ingest_one(*, workspace: Path, rec: dict[str, Any], extracted_at: str) -> tuple[SourceResult, list[dict[str, Any]]]:
    kind = str(rec.get("kind") or "").strip()
    if kind == "webpage":
        return _ingest_webpage(workspace=workspace, rec=rec, extracted_at=extracted_at)
    if kind == "pdf":
        return _ingest_pdf(workspace=workspace, rec=rec, extracted_at=extracted_at)
    if kind == "markdown":
        return _ingest_markdown(workspace=workspace, rec=rec, extracted_at=extracted_at)
    if kind == "repo":
        return _ingest_repo(workspace=workspace, rec=rec, extracted_at=extracted_at)
    if kind == "docs_site":
        return _ingest_docs_site(workspace=workspace, rec=rec, extracted_at=extracted_at)
    if kind == "video":
        return _ingest_video(workspace=workspace, rec=rec, extracted_at=extracted_at)
    raise ValueError(f"Unsupported kind: {kind}")


def _ingest_webpage(*, workspace: Path, rec: dict[str, Any], extracted_at: str) -> tuple[SourceResult, list[dict[str, Any]]]:
    url = str(rec.get("locator") or "").strip()
    provider = _video_provider(url)
    if provider in {"youtube", "bilibili"}:
        raise ValueError(f"video page detected for `{provider}`; use `kind: video` and provide transcript support")
    html = _fetch_url_text(url)
    title, text, _links = _extract_html_text(url, html)
    rel = Path("sources") / "normalized" / f"{rec['source_id']}.md"
    abs_path = workspace / rel
    _write_text(abs_path, _render_source_markdown(title=title or str(rec.get("label") or rec["source_id"]), body=text, locator=url))
    result = SourceResult(
        source_id=str(rec["source_id"]),
        kind="webpage",
        status="success",
        title=title or str(rec.get("label") or rec["source_id"]),
        canonical_url=url,
        local_path=rel.as_posix(),
        content_chars=len(text),
        extracted_at=extracted_at,
        extractor="urllib+htmlparser",
        required=bool(rec.get("required", False)),
    )
    provenance = [
        {
            "source_id": str(rec["source_id"]),
            "pointer": rel.as_posix(),
            "origin_url_or_path": url,
            "local_path": rel.as_posix(),
            "hash": "",
            "note": "webpage body extraction",
        }
    ]
    return result, provenance


def _ingest_pdf(*, workspace: Path, rec: dict[str, Any], extracted_at: str) -> tuple[SourceResult, list[dict[str, Any]]]:
    from tooling.common import ensure_dir

    locator = str(rec.get("locator") or "").strip()
    raw_dir = workspace / "sources" / "raw"
    ensure_dir(raw_dir)
    if _is_remote(locator):
        pdf_path = raw_dir / f"{rec['source_id']}.pdf"
        _download_binary(locator, pdf_path)
        canonical_url = locator
    else:
        pdf_path = _resolve_local_locator(workspace, locator)
        canonical_url = locator

    text = _pdftotext(pdf_path)
    rel = Path("sources") / "normalized" / f"{rec['source_id']}.md"
    _write_text(workspace / rel, _render_source_markdown(title=str(rec.get("label") or rec["source_id"]), body=text, locator=canonical_url))
    result = SourceResult(
        source_id=str(rec["source_id"]),
        kind="pdf",
        status="success",
        title=str(rec.get("label") or rec["source_id"]),
        canonical_url=canonical_url,
        local_path=rel.as_posix(),
        content_chars=len(text),
        extracted_at=extracted_at,
        extractor="pdftotext",
        required=bool(rec.get("required", False)),
    )
    provenance = [
        {
            "source_id": str(rec["source_id"]),
            "pointer": rel.as_posix(),
            "origin_url_or_path": canonical_url,
            "local_path": rel.as_posix(),
            "hash": "",
            "note": "pdf text extraction",
        }
    ]
    return result, provenance


def _ingest_markdown(*, workspace: Path, rec: dict[str, Any], extracted_at: str) -> tuple[SourceResult, list[dict[str, Any]]]:
    locator = str(rec.get("locator") or "").strip()
    if _is_remote(locator):
        text = _fetch_url_text(locator)
        canonical = locator
    else:
        path = _resolve_local_locator(workspace, locator)
        text = path.read_text(encoding="utf-8", errors="ignore")
        canonical = locator
    rel = Path("sources") / "normalized" / f"{rec['source_id']}.md"
    _write_text(workspace / rel, text if text.startswith("# ") else _render_source_markdown(title=str(rec.get("label") or rec["source_id"]), body=text, locator=canonical))
    result = SourceResult(
        source_id=str(rec["source_id"]),
        kind="markdown",
        status="success",
        title=str(rec.get("label") or rec["source_id"]),
        canonical_url=canonical,
        local_path=rel.as_posix(),
        content_chars=len(text),
        extracted_at=extracted_at,
        extractor="text-copy",
        required=bool(rec.get("required", False)),
    )
    provenance = [
        {
            "source_id": str(rec["source_id"]),
            "pointer": rel.as_posix(),
            "origin_url_or_path": canonical,
            "local_path": rel.as_posix(),
            "hash": "",
            "note": "markdown/text copy",
        }
    ]
    return result, provenance


def _ingest_repo(*, workspace: Path, rec: dict[str, Any], extracted_at: str) -> tuple[SourceResult, list[dict[str, Any]]]:
    from tooling.common import ensure_dir

    locator = str(rec.get("locator") or "").strip()
    cleanup_dir: Path | None = None
    if _is_remote(locator):
        tmp_root = Path(tempfile.mkdtemp(prefix="source-repo-"))
        cleanup_dir = tmp_root
        subprocess.run(["git", "clone", "--depth", "1", locator, str(tmp_root / "repo")], check=True, capture_output=True, text=True)
        repo_root = tmp_root / "repo"
    else:
        repo_root = _resolve_local_locator(workspace, locator)

    files = _collect_repo_docs(repo_root)
    if not files:
        raise ValueError("no README/docs files found in repo source")

    rel_dir = Path("sources") / "normalized" / str(rec["source_id"])
    abs_dir = workspace / rel_dir
    ensure_dir(abs_dir)

    provenance: list[dict[str, Any]] = []
    total_chars = 0
    for src in files[:MAX_REPO_FILES]:
        rel_src = src.relative_to(repo_root)
        target = abs_dir / rel_src.with_suffix(".md")
        _write_text(target, _render_source_markdown(title=rel_src.as_posix(), body=src.read_text(encoding="utf-8", errors="ignore"), locator=locator))
        rel_target = target.relative_to(workspace).as_posix()
        text = target.read_text(encoding="utf-8", errors="ignore")
        total_chars += len(text)
        provenance.append(
            {
                "source_id": str(rec["source_id"]),
                "pointer": rel_target,
                "origin_url_or_path": f"{locator}::{rel_src.as_posix()}",
                "local_path": rel_target,
                "hash": "",
                "note": "repo README/docs file",
            }
        )

    if cleanup_dir:
        shutil.rmtree(cleanup_dir, ignore_errors=True)

    result = SourceResult(
        source_id=str(rec["source_id"]),
        kind="repo",
        status="success",
        title=str(rec.get("label") or rec["source_id"]),
        canonical_url=locator,
        local_path=rel_dir.as_posix(),
        content_chars=total_chars,
        extracted_at=extracted_at,
        extractor="git+file-copy",
        warning="" if len(files) <= MAX_REPO_FILES else f"trimmed to first {MAX_REPO_FILES} docs files",
        required=bool(rec.get("required", False)),
    )
    return result, provenance


def _ingest_video(*, workspace: Path, rec: dict[str, Any], extracted_at: str) -> tuple[SourceResult, list[dict[str, Any]]]:
    locator = str(rec.get("locator") or "").strip()
    transcript_locator = str(rec.get("transcript_locator") or "").strip()
    provider = _video_provider(locator)

    title = str(rec.get("label") or rec["source_id"])
    body = ""
    note = ""

    if transcript_locator:
        title, body = _ingest_explicit_transcript(workspace=workspace, locator=locator, transcript_locator=transcript_locator, fallback_title=title)
        note = "explicit transcript locator"
    elif provider == "bilibili":
        title, body = _ingest_bilibili_transcript(locator=locator, fallback_title=title)
        note = "bilibili subtitle api"
    elif provider == "youtube":
        raise ValueError("youtube video ingest requires `transcript_locator` in the current environment")
    else:
        raise ValueError("video ingest requires `transcript_locator` unless provider-specific subtitle support exists")

    rel = Path("sources") / "normalized" / f"{rec['source_id']}.md"
    _write_text(workspace / rel, _render_source_markdown(title=title, body=body, locator=locator))
    result = SourceResult(
        source_id=str(rec["source_id"]),
        kind="video",
        status="success",
        title=title,
        canonical_url=locator,
        local_path=rel.as_posix(),
        content_chars=len(body),
        extracted_at=extracted_at,
        extractor=f"video:{provider or 'generic'}",
        warning="",
        required=bool(rec.get("required", False)),
    )
    provenance = [
        {
            "source_id": str(rec["source_id"]),
            "pointer": rel.as_posix(),
            "origin_url_or_path": locator,
            "local_path": rel.as_posix(),
            "hash": "",
            "note": note,
        }
    ]
    return result, provenance


def _ingest_docs_site(*, workspace: Path, rec: dict[str, Any], extracted_at: str) -> tuple[SourceResult, list[dict[str, Any]]]:
    from tooling.common import ensure_dir

    root_url = str(rec.get("locator") or "").strip()
    parsed_root = urllib.parse.urlparse(root_url)
    root_origin = f"{parsed_root.scheme}://{parsed_root.netloc}"
    queue: list[tuple[str, int]] = [(root_url, 0)]
    visited: set[str] = set()

    rel_dir = Path("sources") / "normalized" / str(rec["source_id"])
    abs_dir = workspace / rel_dir
    ensure_dir(abs_dir)

    provenance: list[dict[str, Any]] = []
    page_count = 0
    total_chars = 0
    first_title = str(rec.get("label") or rec["source_id"])

    while queue and page_count < MAX_DOCS_SITE_PAGES:
        url, depth = queue.pop(0)
        norm_url = _normalize_url(url)
        if norm_url in visited or depth > DOCS_SITE_MAX_DEPTH:
            continue
        visited.add(norm_url)

        html = _fetch_url_text(norm_url)
        title, text, links = _extract_html_text(norm_url, html)
        if page_count == 0 and title:
            first_title = title
        target = abs_dir / f"page-{page_count + 1:02d}.md"
        _write_text(target, _render_source_markdown(title=title or norm_url, body=text, locator=norm_url))
        rel_target = target.relative_to(workspace).as_posix()
        provenance.append(
            {
                "source_id": str(rec["source_id"]),
                "pointer": rel_target,
                "origin_url_or_path": norm_url,
                "local_path": rel_target,
                "hash": "",
                "note": f"docs page depth={depth}",
            }
        )
        total_chars += len(text)
        page_count += 1

        for link in links:
            parsed = urllib.parse.urlparse(link)
            if f"{parsed.scheme}://{parsed.netloc}" != root_origin:
                continue
            if parsed.path == parsed_root.path and not parsed.fragment:
                continue
            queue.append((link, depth + 1))

    if page_count == 0:
        raise ValueError("docs site crawl produced no pages")

    result = SourceResult(
        source_id=str(rec["source_id"]),
        kind="docs_site",
        status="success",
        title=first_title,
        canonical_url=root_url,
        local_path=rel_dir.as_posix(),
        content_chars=total_chars,
        extracted_at=extracted_at,
        extractor="urllib+htmlparser",
        warning="" if page_count < MAX_DOCS_SITE_PAGES else f"trimmed to first {MAX_DOCS_SITE_PAGES} pages",
        required=bool(rec.get("required", False)),
    )
    return result, provenance


def _collect_repo_docs(repo_root: Path) -> list[Path]:
    patterns = ["README*", "docs/**/*.md", "docs/**/*.rst", "docs/**/*.txt", "doc/**/*.md", "doc/**/*.rst", "doc/**/*.txt"]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(repo_root.glob(pattern)))
    uniq: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        if not path.is_file():
            continue
        if path in seen:
            continue
        seen.add(path)
        uniq.append(path)
    return uniq


def _fetch_url_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "source-tutorial-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="ignore")


def _extract_html_text(url: str, html: str) -> tuple[str, str, list[str]]:
    parser = _HTMLTextAndLinksParser(base_url=url)
    parser.feed(html)
    return parser.title, parser.text, parser.links


def _ingest_explicit_transcript(*, workspace: Path, locator: str, transcript_locator: str, fallback_title: str) -> tuple[str, str]:
    if _is_remote(transcript_locator):
        text = _fetch_url_text(transcript_locator)
    else:
        path = _resolve_local_locator(workspace, transcript_locator)
        text = path.read_text(encoding="utf-8", errors="ignore")
    body = _parse_transcript_text(text)
    if not body:
        raise ValueError("explicit transcript is empty after parsing")
    return fallback_title, body


def _ingest_bilibili_transcript(*, locator: str, fallback_title: str) -> tuple[str, str]:
    bvid = _extract_bilibili_bvid(locator)
    if not bvid:
        raise ValueError("could not extract Bilibili BV id from locator")

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"}
    pagelist = _fetch_json(f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}", headers=headers)
    pages = pagelist.get("data") or []
    if not pages:
        raise ValueError("bilibili pagelist returned no pages")
    cid = pages[0].get("cid")
    if not cid:
        raise ValueError("bilibili pagelist did not include cid")

    player = _fetch_json(f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}", headers=headers)
    subtitle = ((player.get("data") or {}).get("subtitle") or {})
    subtitles = subtitle.get("subtitles") or []
    if not subtitles:
        raise ValueError("bilibili video has no public subtitles")
    chosen = subtitles[0]
    subtitle_url = str(chosen.get("subtitle_url") or "").strip()
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    if not subtitle_url:
        raise ValueError("bilibili subtitle entry has no subtitle_url")
    sub_json = _fetch_json(subtitle_url, headers=headers)
    body = _parse_bilibili_subtitle_json(sub_json)
    if not body:
        raise ValueError("bilibili subtitle JSON parsed to empty transcript")
    return fallback_title, body


def _pdftotext(path: Path) -> str:
    cmd = ["pdftotext", "-layout", str(path), "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "pdftotext failed")
    text = _normalize_space(proc.stdout)
    if not text:
        raise ValueError("pdftotext produced empty text")
    return text


def _download_binary(url: str, path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "source-tutorial-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    path.write_bytes(data)


def _fetch_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "source-tutorial-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload from {url} is not an object")
    return payload


def _render_source_markdown(*, title: str, body: str, locator: str) -> str:
    title = title or locator
    body = _normalize_space(body)
    return f"# {title}\n\nSource: {locator}\n\n{body}\n"


def _write_text(path: Path, content: str) -> None:
    from tooling.common import atomic_write_text, ensure_dir

    ensure_dir(path.parent)
    atomic_write_text(path, content.rstrip() + "\n")


def _resolve_local_locator(workspace: Path, locator: str) -> Path:
    path = Path(locator)
    if not path.is_absolute():
        path = (workspace / path).resolve()
    if not path.exists():
        raise FileNotFoundError(locator)
    return path


def _normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    clean = parsed._replace(fragment="")
    return clean.geturl()


def _normalize_space(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_remote(locator: str) -> bool:
    return str(locator or "").startswith(("http://", "https://"))


def _video_provider(locator: str) -> str:
    host = urllib.parse.urlparse(locator).netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    return ""


def _parse_transcript_text(text: str) -> str:
    raw = text.strip()
    if not raw:
        return ""
    if raw.startswith("WEBVTT"):
        return _parse_vtt(raw)
    if re.search(r"(?m)^\d+\s*$", raw) and "-->" in raw:
        return _parse_srt(raw)
    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except Exception:
            return _normalize_space(raw)
        if isinstance(payload, dict):
            body = _parse_bilibili_subtitle_json(payload)
            if body:
                return body
    return _normalize_space(raw)


def _parse_vtt(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped == "WEBVTT" or "-->" in stripped:
            continue
        if stripped.isdigit():
            continue
        lines.append(stripped)
    return _normalize_space("\n".join(lines))


def _parse_srt(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or "-->" in stripped or stripped.isdigit():
            continue
        lines.append(stripped)
    return _normalize_space("\n".join(lines))


def _parse_bilibili_subtitle_json(payload: dict[str, Any]) -> str:
    body = payload.get("body") or []
    parts: list[str] = []
    for rec in body:
        if not isinstance(rec, dict):
            continue
        content = str(rec.get("content") or "").strip()
        if content:
            parts.append(content)
    return _normalize_space("\n".join(parts))


def _extract_bilibili_bvid(locator: str) -> str:
    m = re.search(r"(BV[0-9A-Za-z]+)", locator or "")
    return m.group(1) if m else ""


if __name__ == "__main__":
    raise SystemExit(main())
