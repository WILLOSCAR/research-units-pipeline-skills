# 문서 허브

> 기본 문서: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> 언어: [English](README.en.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | **한국어**

이 페이지는 현재 workflow 지도를 빠르게 보는 가벼운 내비게이션입니다. 전체 설명은 루트 README에 있습니다.

이제는 최신 workflow 이름을 그대로 사용하면 됩니다. 예전 alias 이름은 active routing에서 제거되었습니다.

## Workflow 및 Use-Case 지도

| 사용할 경로 | 주요 용도 | 기본 산출물 | 가이드 |
|---|---|---|---|
| `arxiv-survey` | PDF 이전 단계의 evidence-first survey 작성 | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | 같은 survey workflow 에서 compile-ready LaTeX/PDF 까지 필요한 경우 | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| 수업 리포트 / 기말 보고서 | Markdown이면 `arxiv-survey`, PDF까지 필요하면 `arxiv-survey-latex`를 사용. 별도 workflow는 아님 | 보고서 초안, 선택적 PDF | [Guide EN](arxiv-survey.md) |
| `research-brief` | 어떤 주제를 빠르게 이해하고 읽기 순서를 정리 | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | 단일 논문 / manuscript 를 추적 가능하게 평가 | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | protocol 기반 screening, extraction, bounded synthesis | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | 문헌 기반 연구 아이디어 메모 | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | 여러 소스를 tutorial 로 바꾸고 PDF / slides 도 생성 | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |
| `graduate-paper` | 중국어 thesis 자료 재구성. research-stage 이며 executable pipeline 은 아님 | thesis 설계 메모 + skill 패키지 | [Guide EN](graduate-paper.md) |

## 병렬인 3가지 Research Judgment Path

- `research-brief`: 빠른 이해와 먼저 읽을 것
- `paper-review`: 단일 manuscript, traceable claims, recommendation
- `evidence-review`: 여러 연구, protocol, screening, bounded synthesis

전체 설명은 [../README.md](../README.md)를 참고하세요.
이 페이지에서 연결되는 상세 가이드는 현재 주로 영어입니다.
