---
tipo: agente
agente: DATA
tags: [agente, data]
cssclasses: [agent-data]
missao: "Criar planilhas Excel profissionais com openpyxl: dados, fórmulas, formatação e gráficos."
cor: "#A78BFA"
playbooks: 3
skills: 3
---
# Data Agent

> [!data] Missão
> Criar planilhas Excel profissionais com openpyxl: dados, fórmulas, formatação e gráficos.

← [[Maestro]] · Políticas: [[Politicas de aceite]]

## Quando o Maestro chama
- criar planilha com dados
- relatório com gráfico
- fluxo de caixa, orçamento, cadastro, estoque

## Regras de execução
- Gerar manifesto para create_workbook; nunca Python, macro ou comando.
- Ate 6 abas, 5000 linhas/aba, 100 colunas e 1 MiB; graficos bar/line e formulas locais permitidas.
- Dados do usuario ou exemplos identificados; nao inventar informacao pessoal, financeira ou fiscal.

## Como navegar e executar

1. Defina colunas, unidades e período antes de montar a planilha. Separe dados recebidos de exemplos e mantenha cada tabela com cabeçalhos claros.
2. Reabra o arquivo para conferir abas, células e fórmulas declaradas. Informe se as fórmulas foram gravadas mas ainda não recalculadas.
3. Use create_workbook. Não inclua referências externas ou entre abas.

## Playbooks
- [[Playbook - Planilha com grafico]]
- [[Playbook - Fluxo de caixa]]
- [[Playbook - Lista e cadastro]]

## Skills
Aplicadas pelo agente a cada pedido (até 3 por vez, as mais relevantes; ver [[Skills]]):
- [[senior-software-engineer]] — **sempre**
- [[ux-product-designer]] — quando o pedido fala de planilha, tabela, cadastro, formulario, controle, organizar…
- [[ai-product-strategist]] — quando o pedido fala de ideia, negocio, startup, produto, estrategia, plano de negocio…

## Falhas conhecidas (e correção)
- Rotas antigas com run_python, PieChart, 12 abas e SUMIFS nao correspondem ao manifesto atual.
- Nao prometer pivot nativa, validacao de dados, checkbox ou protecao sem ferramenta propria.

## Componentes internos
O fluxo publico usa manifestos e builders/contratos deterministas. As notas de subagentes descrevem helpers legados; nao representam tres pesquisadores ou chamadas de modelo em paralelo.


## Tarefas de referência
Procedimentos consolidados em [[Tarefas de referencia]]:

[[Tarefas de referencia]]
