# Evolução do AI Farm Agent — Entrega 2 (pré-requisito de segurança e Lab inicial)

> Briefing: [prompt-evolucao-ai-farm-agent.md](prompt-evolucao-ai-farm-agent.md). Entrega anterior: [evolucao-entrega-1.md](evolucao-entrega-1.md).
> Data: 2026-11-12. Escopo: limite operacional do Lab (isolamento do QML proposto) e etapa 4 (Lab inicial).

## 1. Pré-requisito de segurança: QML proposto não age fora

**Problema confirmado no código.** O gate do modo Desenvolvedor roda `scripts/smoke_ui.py` na worktree. O QML proposto carregava com a Bridge real e o Cérebro real, e podia, ao abrir:
- chamar slots de escrita (notas, Harness, Diário, iniciar tarefa);
- ler notas pessoais e enviá-las por `XMLHttpRequest`;
- abrir programas com `Qt.openUrlExternally`;
- gravar arquivos com `LocalStorage`.

**Correção em duas camadas:**

| Camada | O que faz |
|---|---|
| `desktop/qml_sandbox.py` (execução) | Bridge **negada por padrão**: só 25 slots de leitura listados funcionam, e um slot novo já nasce negado. Dados sintéticos: Cérebro, Diário, Lab, histórico e preferências numa pasta temporária. Motor QML sem rede: toda URL não local vira inválida. `openUrlExternally` é interceptado. `XMLHttpRequest` não lê nem grava arquivo. `LocalStorage` vai para a pasta temporária. Qualquer escrita negada, rede ou abertura externa ao carregar **reprova o smoke**. |
| `core/dev_mode.py` (`risky_lines`, revisão) | Uma proposta que **acrescenta** `XMLHttpRequest`, `openUrlExternally`, `LocalStorage`, `createQmlObject`, `Qt.include`, `WorkerScript` ou URL remota é reprovada antes de rodar o gate. |

**Prova de isolamento** (`tests/test_qml_sandbox.py` com `tests/fixtures/malicious_proposal.qml`). O QML hostil tenta seis coisas ao carregar, e o estado externo fica intacto:

| Tentativa | Resultado |
|---|---|
| Gravar no Diário, Harness, Cérebro e preferências; marcar a ajuda como vista | Negado e registrado |
| Iniciar a tarefa "apague a pasta Documentos" | Negado e registrado |
| Ler o Cérebro | Só dado sintético |
| Enviar o que leu para `example.invalid` | Bloqueado, com a URL registrada |
| Gravar um arquivo fora do workspace com `PUT file://` | Arquivo não existe depois |
| Abrir `calc.exe` e um site | Interceptado |
| `LocalStorage` | Só na pasta temporária |
| Pasta pessoal | Inalterada |

## 2. AI Research Lab (etapa 4)

Nova tela: Sistema → **AI Research Lab** (página 10), também na paleta Ctrl+K. O modo Desenvolvedor continua no Harness; o Lab não o substitui.

| Área | Entregue | Verificável hoje |
|---|---|---|
| **Versionamento** | A v1 de referência nasce da configuração atual. Variantes ficam isoladas (instruções, esforço, modelo), com hash, diff e recusa de duplicata. **Publicar** é explícito e grava no Harness, que guarda a versão anterior. Publicar a v1 restaura. | Todos os agentes |
| **Model Inspector** | Provedor, modelo, esforço, limite de tokens, ferramentas e instruções de cada versão, com validação: esforço low/medium/high, tokens de 256 a 32 000, nome de modelo sem espaço. A temperatura aparece como **não exposta** pelo cliente do app, sem fingir controle. | Todos os agentes |
| **Evaluation Center + Playground** | Conjunto versionado (`arquivos-basico`, 4 casos). Os mesmos casos rodam nas versões A e B, cada caso numa pasta temporária: **política real** (`action_policy`), **fronteira do experimento** (todo caminho dentro da pasta do caso) e **executor real** de arquivos. O **estado final é conferido no disco**, não pela mensagem. O resultado traz trace, latência, chamadas, tokens e custo **com a origem** ("real" ou "simulado"), além de avisos de amostra pequena e execução incompleta. | Agente de Arquivos, cujo domínio é declarativo |
| **Modos** | **Simulado:** reexecuta o último plano *real* gravado, sem custo; caso sem gravação fica indisponível, sem plano inventado. **Real:** o FileAgent com as instruções e parâmetros da versão. A Bridge exige confirmação e orçamento de até US$ 5,00, e o experimento para quando o orçamento acaba. | — |
| **Skills & Tools** | Contrato das ferramentas por agente (parâmetros e quem valida), skills do catálogo e as cinco ferramentas MCP (todas só leitura), com **Testar** usando entrada validada pelo esquema. | Todos os agentes |
| **Observability** | Registro de tarefas com filtro por agente e por estado. Cada evento fica ligado à tarefa original, os parâmetros aparecem só pelo nome e os segredos são mascarados. | Todas as tarefas |

**Bugs reais encontrados pelo aceite do Lab e corrigidos:**
1. **`expand()` do executor trocava todo `~` pela pasta do usuário.** O nome curto do Windows (`ABCDEF~1`, comum na pasta temporária) virava um caminho inválido, e o caminho *executado* deixava de ser o caminho *validado* pela política, que só expande o `~` inicial. Agora só o `~` inicial é expandido, e há teste de regressão.
2. **O escopo deduzido do texto do pedido depende de onde a pasta fica.** Dentro do repositório, a política aceitou um destino vizinho à pasta do caso. O Lab passou a ter fronteira própria, de modo que o resultado não depende mais disso. A política do app ficou como estava; o comportamento de escopo é anotado como pendência.

## 3. Aceite do Lab

| Critério | Cenário | Ambiente | Resultado observado | Evidência |
|---|---|---|---|---|
| Caso sintético em duas versões | 4 casos × v1 (planejador com erros) e v2 | Teste unitário, planejador de teste | v2 4/4 e v1 3/4: a cópia com nome errado falha no disco, e a fuga é bloqueada e não escreve fora | `tests/test_lab.py::test_same_cases_two_versions_with_state_checked_on_disk` |
| Configuração efetiva e traces | Variante com esforço baixo | Teste unitário | Esforço, ferramentas e versão corretos; trace planejado → bloqueado/executado → verificado | `test_effective_config_and_validation`, trace no caso acima |
| Restaurar a versão anterior | Publicar v2 e depois v1 | Teste unitário | O Harness volta às instruções da v1; só uma versão fica publicada | `test_versions_diff_publish_and_restore` |
| Cancelamento | Cancelar no 2º caso | Teste unitário | 2 cancelados; "execução incompleta" | `test_cancel_tool_failure_and_provider_unavailable` |
| Falha de ferramenta | Mover um arquivo inexistente | Teste unitário | Status "falha da ferramenta" | idem |
| Provedor indisponível | Planejador sem rede | Teste unitário | Status "indisponível"; taxa de sucesso não inventada (`None`) | idem |
| Escapar do workspace | Mover para fora da pasta do caso | Teste unitário, também com a pasta temporária dentro do repo | Bloqueado; nada escrito fora | `test_same_cases…` com TEMP no repo |
| Replay sem custo | Gravação real e depois simulado | Teste unitário | 4/4, US$ 0, origem "simulado"; versão sem gravação → 4 indisponíveis | `test_simulated_mode_replays…` |
| Orçamento | US$ 0,60 por caso, teto de US$ 1,00 | Teste unitário | Para no 2º caso, status "orcamento" | `test_budget_stops_a_real_run` |
| Ferramenta MCP | Nome desconhecido, obrigatório faltando, parâmetro fora do contrato | Teste unitário | Recusados; `task_status` responde | `test_skills_tools_and_mcp_contract` |
| Observabilidade | Duas tarefas, filtro por agente e por estado, segredo no resultado | Teste unitário | Filtros corretos; segredo mascarado | `test_observability_filters…` |
| Percurso pela tela | Lab → v1 × v2 → Rodar (simulado) | QML real fora da tela | 4/4 nas duas, origem simulado | `scripts/ui_flows.py` → `lab_experiment ok` |
| Real exige confirmação | `labRun` real com `confirmed: false` | QML real e Bridge | Recusado pela Bridge | `lab_experiment ok` |
| QML hostil | Escrita, leitura pessoal, rede, arquivo fora, abrir programa, LocalStorage | Subprocesso Qt | Nada aconteceu fora; tudo registrado | `tests/test_qml_sandbox.py` |
| Proposta arriscada | A proposta acrescenta `XMLHttpRequest` | Worktree git de teste | Reprovada antes do gate; não pode ser aplicada | `tests/test_dev_mode.py::test_proposal_adding_network…` |
| Regressão | Bateria completa | Gate | `CODE_READY True`; 12 fluxos; contraste 442/442 | `check_release.py` |

**Validação com o provedor (autorizada em 2026-11-12, teto de US$ 0,50).** O conjunto `arquivos-basico` rodou com a v1 (referência) e a v2 (instruções de caminhos explícitos) usando o FileAgent real.

| Rodada | v1 | v2 | Custo | O que mostrou |
|---|---|---|---|---|
| 1ª (sem chave no processo) | 4 "falha de planejamento" | idem | US$ 0 | **Bug no Lab:** provedor ausente contava como falha da versão. Corrigido: agora conta como "indisponível". Os dois registros enganosos foram apagados. |
| 2ª | 2/4 | 2/4 | US$ 0,047 | **Defeito real do agente de Arquivos:** em "mova…" e "copie…", o modelo só listava a pasta e parava, como o prompt manda ("liste primeiro e pare"); nada era movido. **Bug do Lab:** o replay perdia caminhos escritos na forma longa do Windows. |
| 3ª (depois das correções) | **4/4** | **4/4** | US$ 0,080 (14 chamadas) | Mover, copiar e organizar conferidos no disco. A diferença entre as versões aparece no trace: a v2 organiza por extensão (pasta `jpg/`), a v1 por categoria (`Imagens/`). O replay sem custo reproduziu 4/4. |

Total gasto: cerca de **US$ 0,13**. Correções que entraram por causa desse teste:

| Correção | Onde |
|---|---|
| Provedor ausente conta como "indisponível", não como falha | `core/lab.py` (`real_planner`) |
| Num pedido de ação, se o primeiro plano só inspeciona, a leitura validada roda localmente e o modelo planeja de novo com os nomes reais (no máximo uma rodada a mais) | `agents/file_agent.py` (`_act_after_looking`) |
| "mova" e "copie" passam a ser reconhecidos como operações | `agents/file_agent.py` |
| Plano gravado relativo à pasta do caso, aceitando a forma curta ou longa do caminho | `core/lab.py` (`_portable`) |

Testes de regressão: `tests/test_file_two_pass.py` e `tests/test_lab.py::test_real_mode_without_provider_key…`.

## 4. Arquivos

| Situação | Arquivos |
|---|---|
| Novos | `desktop/qml_sandbox.py`, `scripts/sandbox_escape_check.py`, `tests/fixtures/malicious_proposal.qml`, `tests/test_qml_sandbox.py`, `core/lab.py`, `desktop/qml/views/LabView.qml`, `tests/test_lab.py` |
| Alterados | `scripts/smoke_ui.py` (caixa de areia), `core/dev_mode.py` (`risky_lines`), `core/harness.py` (`instructions_override`, válido só dentro do experimento), `core/automation.py` (`expand`), `desktop/bridge.py` (`lab*`, sinais `labProgress`/`labFinished`), `desktop/qml/Main.qml` (página 10, paleta), `scripts/ui_flows.py`, `scripts/capture_ui.py` (`UI_SYNTHETIC=1`), `tests/test_dev_mode.py`, `tests/test_ui_flows.py` |

## 5. Pendências (etapa 5 e seguintes)

- **Code Workspace:** edição, terminal, Git, diff e debugging em workspace isolado. A base existe: worktree, gate e caixa de areia do modo Desenvolvedor.
- **Training & Optimization:** feedback e variantes de prompt já são possíveis via versões. O fine-tuning segue desligado até haver provedor, dados, permissão e orçamento definidos.
- **Autonomous Research:** depende de definir o escopo operacional e o orçamento.
- **Experimentos para outros agentes:** precisam de verificadores de estado final por domínio, por exemplo Dados (conteúdo da planilha) e Web (URL e conteúdo).
- **Política do app:** o escopo deduzido do texto pode ser mais largo que a pasta citada quando ela fica dentro de pastas conhecidas. Vale revisar em `core/file_contracts.request_roots`.
- **Revisão visual em tela real, escalas do Windows e navegação só por teclado nas telas novas.**
