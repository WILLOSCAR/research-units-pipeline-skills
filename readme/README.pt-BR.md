# Hub de Documentação

> Documentação principal: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> Idiomas: [English](README.en.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | **Português (Brasil)** | [日本語](README.ja.md) | [한국어](README.ko.md)

Esta página é uma entrada curta para o mapa atual de workflows. A explicação completa do projeto está no README principal.

Use diretamente os nomes atuais dos workflows. Os aliases antigos não fazem mais parte do roteamento ativo.

## Mapa de Workflows

| Workflow | Uso principal | Entregável padrão | Guia |
|---|---|---|---|
| `arxiv-survey` | surveys orientados por evidência antes da entrega em PDF | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | o mesmo workflow de survey com saída compilável em LaTeX/PDF | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| course paper / term report | caso topic-to-report baseado em `arxiv-survey` ou `arxiv-survey-latex` | rascunho de relatório, PDF opcional | [Guide](arxiv-survey.md) |
| `research-brief` | entendimento rápido de um tema e rota de leitura | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | crítica rastreável de um paper ou manuscrito | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | screening, extração e síntese guiados por protocolo | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | memo de direções de pesquisa com base na literatura | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | transformar múltiplas fontes em tutorial com PDF e slides | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |
| `graduate-paper` | reorganizar materiais de tese chinesa em um workflow de tese | pipeline + thesis skill packages | [Guide](graduate-paper.md) |

## Três Produtos de Review em Paralelo

- `research-brief`: orientação rápida e o que ler primeiro
- `paper-review`: um manuscrito, claims rastreáveis e recomendação
- `evidence-review`: vários estudos, protocolo, screening e síntese limitada

Para a visão completa, consulte [../README.md](../README.md).
