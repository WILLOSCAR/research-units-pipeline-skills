# Hub de Documentação

> Documentação principal: [Repo README](../README.md) | [中文主页](../README.zh-CN.md)
>
> Idiomas: [English](README.en.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | **Português (Brasil)** | [日本語](README.ja.md) | [한국어](README.ko.md)

Esta página é uma navegação curta para o mapa atual de workflows. A explicação completa do projeto está no README principal.

Use diretamente os nomes atuais dos workflows. Os aliases antigos não fazem mais parte do roteamento ativo.

## Mapa de Workflows e Casos de Uso

| Caminho | Uso principal | Entregável padrão | Guia |
|---|---|---|---|
| `arxiv-survey` | surveys orientados por evidência antes da entrega em PDF | `output/DRAFT.md` | [Guide](arxiv-survey.md) |
| `arxiv-survey-latex` | o mesmo workflow de survey com saída compilável em LaTeX/PDF | `output/DRAFT.md`, `latex/main.pdf` | [Guide](arxiv-survey.md) |
| trabalho de curso / relatório final | use `arxiv-survey` para Markdown ou `arxiv-survey-latex` para PDF; não é um workflow separado | rascunho de relatório, PDF opcional | [Guide EN](arxiv-survey.md) |
| `research-brief` | entendimento rápido de um tema e rota de leitura | `output/SNAPSHOT.md` | [Guide](research-brief.md) |
| `paper-review` | crítica rastreável de um paper ou manuscrito | `output/REVIEW.md` | [Guide](paper-review.md) |
| `evidence-review` | screening, extração e síntese guiados por protocolo | `output/SYNTHESIS.md` | [Guide](evidence-review.md) |
| `idea-brainstorm` | memo de direções de pesquisa com base na literatura | `output/REPORT.md` | [Guide](idea-brainstorm.md) |
| `source-tutorial` | transformar múltiplas fontes em tutorial com PDF e slides | `output/TUTORIAL.md`, `latex/main.pdf`, `latex/slides/main.pdf` | [Guide](source-tutorial.md) |
| `graduate-paper` | reorganizar materiais de tese chinesa; estágio de design, não executável | notas de design de tese + pacotes de skills | [Guide EN](graduate-paper.md) |

## Três Caminhos de Julgamento de Pesquisa

- `research-brief`: orientação rápida e o que ler primeiro
- `paper-review`: um manuscrito, claims rastreáveis e recomendação
- `evidence-review`: vários estudos, protocolo, screening e síntese limitada

Para a visão completa, consulte [../README.md](../README.md).
As guias detalhadas vinculadas aqui estão atualmente principalmente em inglês.
