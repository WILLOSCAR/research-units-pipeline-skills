# Hub de Documentação

> Documentação principal: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> Idiomas: [English](README.en.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | **Português (Brasil)** | [日本語](README.ja.md) | [한국어](README.ko.md)

Esta página é uma navegação curta para o mapa atual de workflows. A explicação completa do projeto está no README principal.

A interface do produto é `Goal -> Run -> Evidence -> Improve`; os workflows abaixo definem o trabalho de pesquisa dentro de um Run.

Use diretamente os nomes atuais dos workflows. Os aliases antigos não fazem mais parte do roteamento ativo.

## Executable Workflows

| Caminho | Uso principal | Entregável padrão | Guia |
|---|---|---|---|
| `arxiv-survey` | surveys orientados por evidência antes da entrega em PDF | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | o mesmo workflow de survey com saída compilável em LaTeX/PDF | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| `research-brief` | entendimento rápido de um tema e rota de leitura | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | crítica rastreável de um paper ou manuscrito | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | screening, extração e síntese guiados por protocolo | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | memo de direções de pesquisa com base na literatura | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | transformar múltiplas fontes em tutorial com PDF e slides | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |

## Overlays And Research-Stage Paths

| Caminho | Uso principal | Status | Guia |
|---|---|---|---|
| trabalho ou relatorio de curso, seminario ou relatorio tecnico baseado em literatura | `arxiv-survey` or `arxiv-survey-latex` | bounded-report use-case overlay selecting the `course_paper` delivery profile | [Guide EN](arxiv-survey.md) |
| `graduate-paper` | reorganizar materiais de tese chinesa | research-stage path, not executable | [Guide EN](graduate-paper.md) |

## Três Caminhos de Julgamento de Pesquisa

- `research-brief`: orientação rápida e o que ler primeiro
- `paper-review`: um manuscrito, claims rastreáveis e recomendação
- `evidence-review`: vários estudos, protocolo, screening e síntese limitada

## Current Reliability Note

Seven workflows are executable and harness-backed, but semantic maturity differs
by path. See [Workflow Taxonomy](../docs/PIPELINE_TAXONOMY.md) and
[Harness Readiness](../docs/HARNESS_READINESS.md) for current proof boundaries.

Para a visão completa, consulte [../README.md](../README.md).
As guias detalhadas vinculadas aqui estão atualmente principalmente em inglês.
