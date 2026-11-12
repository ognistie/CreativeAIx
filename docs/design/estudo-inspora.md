# Estudo de design: Inspora como biblioteca de referência

> Fonte: https://www.inspora.design (acervo curado de design recente). Estudado em 2026-11-11: o próprio site
> (tokens medidos no código da página) e ~20 peças da categoria Produto ligadas ao que o AI Farm Agent faz.
> As peças são de terceiros: usamos como **direção e padrão de interação**, nunca copiando layout, marca ou texto.

## 1. O que o site ensina pela própria construção

Medido no CSS da página (`:root` e estilos calculados):

| Token | Valor | Leitura |
|---|---|---|
| `--ink` | `#262626` | um só preto para texto e ação primária |
| `--muted` | `#767676` | texto secundário (AA sobre branco) |
| `--line` | `#f0f0f0` | divisória quase invisível |
| `--surface` | `#fafafa` | superfície de controle (abas, filtros) |
| `--paper` | `#ffffff` | fundo |
| `--radius-surface` | `6px` | **um** raio para tudo |
| fonte | Inter 13–14 px, `letter-spacing: 0.2px` | uma família, dois tamanhos no cromado |
| movimento | `150ms cubic-bezier(0.4,0,0.2,1)` (cor) e `150ms ease-out` (escala da imagem no hover) | uma curva, uma duração |

Princípios que saem daí:
1. **Contenção**: cinco neutros, um raio, uma fonte, uma curva. O cromado some; o conteúdo é o protagonista.
2. **Filtros quietos**: abas em `#fafafa` com texto `muted`; a ativa vira tinta cheia (`ink` + branco). Sem borda.
3. **Ficha em pares chave/valor** (Indústrias / Cores / Estilos) separados por linha fina: metadados escaneáveis.
4. **Esqueleto no carregamento**: silhuetas cinza no lugar do conteúdo, nunca um spinner solto.
5. **Grade em alvenaria** com miniaturas que crescem levemente no hover (150 ms).

## 2. Checklist de engenharia de design (visto em *Sidebar Active State*)

A peça mostra a navegação de um guia de "detalhes de interface". Os tópicos viraram nosso checklist:

| Detalhe | O que significa | Situação no AI Farm Agent |
|---|---|---|
| Raio aninhado | raio interno = raio externo − espaçamento | **falta**: cartões dentro de cartões usam raios soltos (8/12/15/20/22) |
| Áreas de toque | alvo clicável ≥ 32–40 px mesmo com ícone pequeno | parcial (chips 30 px, ícones 16 px sem área maior) |
| Esmaecimento na rolagem | bordas de listas roláveis somem em gradiente | **falta** (lista de conversas, Cérebro, Harness) |
| Sombras, não bordas | separar por profundidade suave, não por contorno | **ao contrário**: quase tudo tem `hairline` |
| OKLCH | escalas de cor perceptualmente uniformes | paletas em hex escolhidas à mão |
| Ruído | grão sutil dá materialidade a vidro e gradiente | só nos papéis de parede (textura de tela) |
| Contorno de imagem | 1 px interno translúcido em toda imagem | **falta** nas miniaturas |
| Morfose de ícone | play ↔ stop, + ↔ × animados | ícones trocam sem transição |
| Pressão de botão | `scale(0.97)` ao pressionar | só no Chip |
| Curvas (easings) | entrada `ease-out`, saída `ease-in`, cor `standard` | `durFast/Normal/Slow` sem curvas nomeadas |
| Entrada escalonada | itens entram com 30–50 ms de diferença | só nos cartões da tela inicial |
| Interrompível | animação muda de alvo no meio sem "pular" | `Behavior` do Qt já ajuda; falta regra |

## 3. Padrões de produto que servem ao nosso app

| Peça | Padrão | Onde aplicar |
|---|---|---|
| **Agent Plan** | plano como lista com ícone por passo e selo de estado ("Planejado"); o passo em foco abre descrição + **Aprovar / Pular**; rodapé "0 de 5 decididos", **Aprovar tudo** e **Executar** (desabilitado até decidir) | revisão do plano (hoje um bloco simples em `TaskView`) |
| **Coding Agent** | cartão com estado no cabeçalho ("Lendo arquivo"), título da tarefa com progresso `0/5`, lista de passos com spinner no atual, estado ocioso "Pronto quando você estiver", chips de contexto (GitHub, Arquivos…), rodapé com **tokens · custo · tempo · modelo** e **Pausar / ×** | execução, sobretudo Claude Code / Codex (EXTCODE) |
| **Agent cards** (Parsing / Planning / Reasoning) | uma cor viva por fase, métrica ao vivo grande (97 %, tokens, latência) | indicador de fase (Entendendo → Planejando → Executando → Conferindo) |
| **AI agent dashboard** | widgets: *Agentes rodando*, *Trabalhando agora*, *Precisa de você*, *Linha do tempo* (raias), *Quando seus agentes trabalham* (mapa de calor) | nova tela **Atividade** com dados que já existem (`task_ledger`, `history_store`) |
| **Usage meter** | número grande + barra segmentada por categoria + legenda com %, barras diárias, "restante" no rodapé | custo/uso (histórico, cota do GPT-Live) |
| **Soft glass workspace picker** | escolha em blocos de vidro com ícone, selo ✓ no escolhido e uma linha de ajuda | tema, paleta, papel de parede, agente preferido |
| **Sidebar active state** | seções agrupadas com ícone colorido no título, selo "Novo", ativo = ponto + peso, **sem pílula pesada** | barra lateral (a pílula branca do ativo incomoda no claro) |
| **Morphing nav** | navegação em pílula flutuante; o ativo mostra rótulo, os outros só ícone | barra lateral recolhida / mini chat |
| **Chat component** | compositor mínimo; ações como texto + ícone ("Pedir aprovação"); bandeja embaixo "Conectar apps" com ícones | compositor: bandeja de conectores (Claude Code, Codex, MCP) com estado |
| **Deploy pipeline / Sandbox boot** | estágios na horizontal, estado vazio com uma frase e **uma** ação primária escura | progresso da tarefa e estados vazios |
| **Task card** | título editorial grande (serifa) num cartão limpo | resultado de uma tarefa / resumo do Cérebro |

## 4. Diagnóstico do AI Farm Agent hoje

Pontos fortes: tokens centralizados (`Theme.qml`), contraste AA medido, tema escuro e claro, vidro real, papéis de parede.

Onde a referência mostra o caminho:
1. **Excesso de contorno**: borda `hairline` em quase todo componente → ruído visual. A referência separa por superfície e sombra.
2. **Raios sem regra**: 8, 12, 15, 17, 20, 22 px convivendo; cartões aninhados não seguem raio externo − espaçamento.
3. **Ativo pesado na barra lateral**: pílula branca com borda e filete; a referência usa ponto + peso tipográfico.
4. **Execução como log**: a tarefa em andamento é uma lista de linhas; falta o "cartão do agente" com passos, estado, custo e controles.
5. **Revisão do plano sem decisão por passo**: aprova-se tudo ou nada.
6. **Sem visão de atividade**: os dados existem (registro de tarefas, histórico, uso), mas não há painel.
7. **Movimento sem gramática**: durações soltas; sem pressão, sem morfose, pouca entrada escalonada.
8. **Carregamentos e vazios genéricos**: spinners e textos; sem esqueleto e sem a "uma ação" do estado vazio.

## 5. Plano de melhoria (sem implementar ainda)

Cada fase é independente, tem aceite verificável e não muda comportamento de execução nem segurança.

| Fase | Entrega | Aceite |
|---|---|---|
| **F1 Fundamentos** | tokens novos: escala de neutros (5 níveis por tema), raios `r1..r4` com função de raio aninhado, elevação (`shadow1..3` no claro; brilho interno no escuro) no lugar de bordas, movimento (`ease.standard/out/in`, `dur.fast 150 / base 220 / slow 400`), números tabulares para métricas | `check_contrast.py` cobre os novos neutros; teste proíbe duração/curva solta e borda `hairline` fora de campos de texto |
| **F2 Casca** | barra lateral em grupos (*Trabalho*, *Conhecimento*, *Sistema*), ativo = ponto + peso, esmaecimento nas bordas da lista; filtros/abas no estilo "quieto"; contorno interno em toda imagem | capturas nos dois temas; fluxo de hover sem flash (teste existente) |
| **F3 Componentes de agente** | `PlanCard` (aprovar/pular por passo, aprovar tudo, executar), `AgentRunCard` (estado, passos com spinner, contexto, rodapé tokens·custo·tempo·modelo, pausar/parar), `PhaseStepper` | `ui_flows.py` ganha: aprovar 2 de 3 passos executa só os aprovados; parar pelo cartão cancela |
| **F4 Atividade** | tela com widgets: rodando agora, precisa de você (perguntas e confirmações pendentes), linha do tempo do dia, uso do mês (medidor segmentado), mapa de calor por hora | dados vêm só de `task_ledger`/`history_store`; teste com registro de brinquedo |
| **F5 Escolhas e detalhes** | seletores em blocos de vidro com ✓ (tema, paleta, papel de parede, agente); fichas chave/valor (perfil do agente, detalhe do histórico); esqueletos; estados vazios com uma ação | capturas; nenhum spinner solto em carregamento de lista |
| **F6 Movimento** | pressão `0.97` em todo botão, morfose play↔stop e +↔×, entrada escalonada 40 ms em listas, transições interrompíveis; tudo respeita "luzes paradas" | teste: com movimento desligado, durações efetivas = 0 |

Ordem sugerida: F1 → F2 (base visual, risco baixo) → F3 (maior ganho de experiência) → F4 → F5 → F6.

## 6. Skills para executar

`design-system-architect` (F1), `premium-ui-designer` + `apple-design` (F2, F5, revisão das capturas),
`frontend-experience-engineer` (F3, F4, F6 em QML), `process-verifier` (aceite de cada fase).

## 7. Execução (2026-11-11)

As seis fases foram implementadas a partir do estado deixado pelo Codex (bateria verde antes e depois).

| Fase | Feito | Verificação |
|---|---|---|
| F1 | `Theme.qml`: `r1..r4`, `nested()`, `edge`/`shadowSoft`/`edgeWidth`, `dur()`, `easeStandard/Out/In`, `press`, `stagger`, `tabular`; `GlassPanel` com sombra em camadas (claro) e borda de luz (escuro) | `tests/test_design_system.py`; contraste AA 272/272 |
| F2 | barra lateral em grupos com rótulo mono, ativo = ponto + peso, esmaecimento na lista de conversas; chips no estilo quieto | capturas nos dois temas; teste de hover sem cinza |
| F3 | `PlanCard` (aprovar/pular por passo), cartão do agente com `PhaseStepper`, rodapé tabular e Parar; backend pula passos e dependentes | `ui_flows.py`: aprovar 1 e 3, pular 2 → a ponte recebe `[2]`; teste do controlador |
| F4 | tela Atividade (página 7) com rodando agora, precisa de você, uso do mês, mapa de calor e hoje | `core/activity.py` testado com histórico de brinquedo; `ui_flows.py` abre a tela |
| F5 | `ChoiceTile` (tema), `KeyValue`, `Skeleton`, `EmptyState` | capturas |
| F6 | pressão em botões, morfose de ícone, entrada escalonada; todas as durações por `Theme.dur` | teste proíbe duração solta |

Não feito nesta rodada: OKLCH nas paletas e textura de ruído no vidro (itens do checklist sem ganho claro no
renderizador por software); revisão das capturas na tela real com GPU.
