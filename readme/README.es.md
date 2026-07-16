# Centro de Documentación

> Documentación principal: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> Idiomas: [English](README.en.md) | [简体中文](README.zh-CN.md) | **Español** | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

Esta página es una navegación ligera para el mapa actual de workflows. La explicación completa del proyecto está en el README principal.

La interfaz del producto es `Goal -> Run -> Evidence -> Improve`; los workflows siguientes definen el trabajo de investigación dentro de un Run.

Usa directamente los nombres actuales de los workflows. Los alias antiguos ya no forman parte del enrutamiento activo.

## Executable Workflows

| Ruta | Uso principal | Entregable por defecto | Guía |
|---|---|---|---|
| `arxiv-survey` | surveys basados en evidencia antes de la entrega en PDF | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | el mismo workflow de survey con salida compilable en LaTeX/PDF | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| `research-brief` | comprensión rápida de un tema y ruta de lectura | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | crítica trazable de un paper o manuscrito | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | screening, extracción y síntesis con protocolo explícito | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | memo de direcciones de investigación con base bibliográfica | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | transformar fuentes múltiples en tutorial con PDF y slides | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |

## Overlays And Research-Stage Paths

| Ruta | Uso principal | Estado | Guía |
|---|---|---|---|
| trabajo o informe de curso, informe de seminario o informe tecnico basado en literatura | `arxiv-survey` or `arxiv-survey-latex` | bounded-report use-case overlay selecting the `course_paper` delivery profile | [Guide EN](arxiv-survey.md) |
| `graduate-paper` | reorganizar materiales de tesis china | research-stage path, not executable | [Guide EN](graduate-paper.md) |

## Tres Caminos de Juicio de Investigación

- `research-brief`: orientación rápida y qué leer primero
- `paper-review`: una sola obra, claims trazables y recomendación
- `evidence-review`: muchas obras, protocolo, screening y síntesis acotada

## Current Reliability Note

Seven workflows are executable and harness-backed, but semantic maturity differs
by path. See [Workflow Taxonomy](../docs/PIPELINE_TAXONOMY.md) and
[Harness Readiness](../docs/HARNESS_READINESS.md) for current proof boundaries.

Para la explicación completa, consulta [../README.md](../README.md).
Las guías detalladas enlazadas desde esta página están actualmente en inglés.
