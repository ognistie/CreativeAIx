# Evolução do harness

Revisão de 26/11/2026 sobre `ae17a38`. A referência remota `refs/heads/main` foi consultada e corresponde
ao checkout. Não havia alterações locais no início. Windows, Python 3.11 e dependências existentes.

## Diagnóstico e ordem de entrega

O documento de revisão foi lido integralmente. Seus achados são hipóteses; o código atual já contém
extrações do controller/executor, planos tipados, chat com ferramentas de leitura e perfis reais do Lab.
Não há justificativa para refazer esses mecanismos.

| Achado | Evidência atual | Estado / consequência |
| --- | --- | --- |
| Ledger ignora erros de escrita | `TaskLedger._write`, `Controller._ledger_call` | Confirmado; uma confirmação podia liberar envio mesmo sem trilha durável. Primeiro incremento. |
| Autorização compartilhada por executor e pilotos | `AutomationEngine._authorize_ui`, `AppPilot._check`, `BrowserPilot._check` | Existente; integrar aqui evita um segundo runtime. |
| Executor já dividido | `automation_files.py`, `automation_web.py` | Achado de monólito parcialmente superado. |
| Planos já tipados | `plan_schema.py`, `plan_validator.py` | Existente; preservar contrato e políticas. |
| Aprendizado usa sucesso operacional | `controller.py`: `get_learned().observe(..., all_success)` | Confirmado; promoção não exige o mesmo `verified` usado no resultado final. Pendente endurecer evidência por domínio. |
| Lab aplica perfis a pedidos reais | `lab_drafts.profile_for`, `maestro.profile_plan` | Existente; preservar permissões do agente-base. |
| Métricas contínuas locais | `quality_metrics.py` | Existente; não executar a leitura de histórico pessoal nesta revisão. |

## Incremento 1: intenção e decisão duráveis

Responsável: agente de engenharia desta entrega. Dependências: ledger JSONL e porta de efeitos existentes.
Saída verificável: nenhuma autorização interativa sensível liberada quando a gravação exigida falha.

`TaskLedger.effect` grava `effect` com tarefa, sessão, `action_id` único por tentativa, agente, operação,
classe de efeito e fase (`intent`, `approved`, `declined`, `cancelled`). Não grava texto da mensagem,
rótulo, parâmetros nem token de aprovação. `flush` e `fsync` precisam terminar antes de retornar.
Identificadores de tarefa não podem ser caminhos.

No fluxo interativo do Controller, `_authorize_ui` persiste intenção antes de perguntar e decisão antes
de liberar o chamador. Vale também para efeitos reconhecidos dentro dos pilotos e nos modos shadow/off.
Ledger desativado, escopo ausente ou falha de gravação bloqueiam o efeito. Leituras continuam sem essa
dependência. O executor verifica cancelamento novamente depois da autorização.

Os eventos são aditivos: leitores antigos ignoram o tipo desconhecido; não há migração de notas, UI,
preferências ou contrato RPC. Reversão: retirar a integração e o método novo juntos. Não há flag para
contornar uma falha de persistência no fluxo protegido.

Uma aprovação registrada **não prova execução**. Em falha de `fsync`, uma linha pode estar visível mesmo
sem confirmação de durabilidade. Nenhum desses eventos autoriza replay automático ou comprova resultado.
Permanece uma janela entre a última checagem e o efeito externo; não se promete atomicidade com GUI.

## Fronteiras inventariadas

| Entrada / superfície | Caminho de execução e controle atual |
| --- | --- |
| Texto / voz | Controller → atalhos/perfis/planos aprendidos/chat/Maestro → validação → executor |
| Chat local / web | `chat_tools.ReadScope`, `ChatAgent.tools(allow_actions)`; mutações delegadas ao Controller |
| Filesystem / CODE / DATA | `action_policy`, `file_contracts`, handlers declarativos, staging/hashes onde existentes |
| GUI / teclado / clipboard | executor, checagem de foco, `action_risk`; classificação reconhecida chega à porta compartilhada |
| Pilotos de app / web | `_check` → callback `_authorize_ui`; mesmo ledger exigido para efeitos classificados |
| Claude Code / Codex | POL-011, pasta validada, `coding_agents`/`process_runner`; permissões reais continuam as do usuário |
| MCP | servidor de leitura; não foi ampliado nesta entrega |
| Lab / memória | preferências não ampliam ferramentas; políticas em código continuam obrigatórias |

Limites: o caminho legado sem callback interativo preserva a autorização inline anterior e ainda precisa
de migração. Ícones não classificados, identidade de conta/documento, aprovação vinculada ao hash do
conteúdo/alvo, egress/offline e retenção não estão resolvidos por este incremento. Job Objects não são sandbox.

## Verificação

Fixtures sintéticas e pastas temporárias, sem API paga ou desktop pessoal. `test_durable_effect_gate.py`
confere ordem intenção/pergunta/decisão, falhas de `fsync` nas duas fases, ledger desligado, escopo ausente,
cancelamento, IDs distintos em repetição, leitura sem ledger, shadow/off, traversal e handler não chamado
em falha ou dry-run. Testes existentes de vault e confirmação usam ledger temporário.

Não houve benchmark de latência nem avaliação de inteligência com modelos nesta entrega. A escrita
durável acrescenta duas sincronizações por tentativa sensível; o custo de disco não foi medido.

Comparação sintética executada carregando `automation.py` de `ae17a38` e a candidata: com o mesmo
`fsync` lançando `OSError`, a versão base retornou autorização liberada; a candidata bloqueou.
Não foi executado envio real. Os 12 testes novos, 6 testes de memória envenenada e 25 testes de
delegação/confirmação de voz passaram. Interface: typecheck, 63 testes e `build:check` aprovados.
Contrato TypeScript e tokens gerados em dia; vault sem erros. A primeira tentativa do gate no
sandbox foi interrompida; a validação completa exige execução sem a restrição de subprocessos.

Rodada completa sobre fontes estabilizados: 741 testes, 5 erros em `DevWorktreeTests.setUp`, todos
no `git init` de repositórios temporários (código 128), antes da execução do caso. Os 7 testes do
módulo passam isoladamente, inclusive com o mesmo TMP/TEMP do gate. A causa dessa diferença ainda
não foi determinada. Dependências, compilação, smoke, vault e whitespace passaram; `source_unchanged`
foi verdadeiro. Resultado global: **CODE_READY False**. Não é uma entrega certificada para publicação.

## Próximos incrementos e gates

1. **P0 — aprovação específica:** contrato com alvo/recurso, conteúdo por hash, validade, consumo único;
   migrar chamadores legados. Gate: troca de foco/conta/conteúdo e replay recusados em fixtures.
2. **P0 — privacidade e baseline:** política de egress e offline em todas as saídas, retenção compatível;
   fixtures de segredos e inventário completo. Sem leitura de dados pessoais para demonstrar o mecanismo.
3. **P1 — runtime comum headless:** extrair fluxo com dependências explícitas preservando atalhos e Bridge;
   gate de paridade texto/voz/simulação e tarefa composta. Depois grafo, orçamento e reconciliação.
4. **P2 — memória/contexto:** exigir evidência independente na promoção, proveniência e invalidação;
   comparar memória ligada/desligada com corpus separado antes de recuperação semântica.
5. **P2 — provedores:** encapsular Anthropic sem mudar comportamento; outro adaptador depende de contratos
   comuns e política de egress, com testes fake separados de live.
6. **P3 — Lab:** runtime compartilhado, graders por domínio e holdout obrigatório antes de ampliar promoção.

## Phase II — implementação local

| Área | Mudança entregue | Cobertura e limite |
| --- | --- | --- |
| Baseline | As fixtures do Modo Desenvolvedor usam `GIT_CONFIG_COUNT=0` no seu escopo. O helper Git informa stderr e tem timeout. | O gate anterior reproduzia cinco erros antes dos testes, com `missing config value GIT_CONFIG_VALUE_0`. Os comandos de criação, worktree, aplicação e rollback continuam na suíte. |
| P0: autorização | O executor compara parâmetros, janela observável, ação, agente, sessão e tarefa antes e depois de confirmação interativa. A confirmação do Controller verifica o prazo ao retornar. O executor descarta o marcador interno de efeito vindo do plano. | Fixtures cobrem alteração de alvo/conteúdo, marcador forjado e falhas do ledger. Ainda faltam identidade semântica universal, versão da política no registro e migração do caminho inline e de todos os cliques dos pilotos. |
| P0: privacidade | `privacy.offline: true` bloqueia chamadas Anthropic e voz remota nos transportes controlados e usa cache local do Whisper. | Fixtures confirmam ausência de chamada ao transporte. O flag não controla a rede de aplicativos externos ou CLIs. Isolamento de rede do processo, classificação completa e retenção seguem pendentes. |
| P1: estado | `TaskSchedule` tira do Controller a decisão sequencial sobre dependências. O ledger guarda o último cursor versionado por subtarefa e preserva passos incertos na reconstrução. | O scheduler roda sem Qt. O cursor não contém plano retomável e nenhuma ação externa é repetida na recuperação. Grafo adaptativo, budget hierárquico e reconciliação de estado externo seguem pendentes. |
| P2: evidência | O Controller alimenta moldes só com resultados verificados, ignora simulação e deduplica IDs recentes por molde. Mudanças no código de política ou de execução invalidam moldes antigos. | A promoção exige três execuções verificadas. Alguns handlers não verificam o efeito e deixam de ensinar. O contexto e o contrato de provedores ainda não foram extraídos. |
| P3: promoção | O Lab exige casos reservados numa comparação real com a versão ativa. Resultados duplicados são recusados e as taxas são recalculadas a partir dos resultados da rodada. | A regra vale para os graders existentes. A validação usa fixtures, inclusive no teste de rollback, e não comprova novos domínios reais ou um holdout com acesso segregado. |

As mudanças preservam os RPCs e a UI. `privacy.offline` vem desativado. Eventos do ledger e proveniência
dos moldes são aditivos. Remover as alterações de código restaura a política anterior sem migrar a
memória. Moldes anteriores ficam inativos no código novo e podem voltar a ser elegíveis após reversão.

Verificação final: `check_release.py --code-only` retornou `CODE_READY True` e `MAIN_READY True`,
com 747 regressões Python aprovadas. Os cinco casos de worktree antes interrompidos no `git init`
passaram no gate completo. A checagem literal do laço de subtarefas passou a conferir a propagação
real do pulo e a disponibilidade de um ramo independente. Typecheck, 63 testes de UI,
`build:check`, contrato da Bridge e tokens também passaram. Casos de egress, aprovação e recuperação
usaram dados sintéticos e transportes substituídos. Não foi feita medição de desempenho ou chamada paga.

## Phase III — execução de passos e evidência

O ponto de partida é a Phase II validada no checkout sobre `ae17a38`. No executor anterior, um prefixo
de erro do clique disparava uma segunda tentativa mesmo sem evidência de que a primeira parou antes
do efeito. No caminho de visão, uma aprovação baseada na descrição também podia dispensar uma nova
checagem após localizar o elemento. Esses caminhos foram os primeiros a mudar.

| Entrega | Integração e comportamento |
| --- | --- |
| Autorização de cliques | Executor e pilotos classificam a ação no ponto efetivo. A aprovação da descrição deixa de ser reaproveitada como autorização de um elemento localizado depois. A confirmação é invalidada se mudar a janela, a classificação do alvo ou o modo da política durante a espera. O ledger registra a versão e o modo. Em visão, o piloto passa uma checagem interna de página ou janela antes do clique. |
| Execução sem Qt | `StepRuntime` faz a mesma admissão de passos no Controller e no Lab de arquivos. O desktop, que também recebe pedidos de voz, começa cada execução com até 100 despachos em 300 s após o roteiro inicial. O Lab de arquivos admite até 40 operações por caso e usa o prazo do experimento quando há orçamento ativo. A admissão entre chamadas não interrompe uma operação já em andamento. |
| Recuperação | Até uma tentativa adicional para uma falha observada antes do efeito. A prova atual vem do localizador de visão quando ele não achou o alvo. Outros erros ficam sem repetição automática. Cancelamento e prazo são verificados antes de cada despacho. O replay do ledger continua preservando o passo incerto. |
| Evidência e métricas | `verified_success` distingue sucesso de verificação e é usada na entrada de aprendizado e nas rotas de memória. As métricas locais incluem sucesso verificado, custo por sucesso verificado, tokens, tentativas e recuperação, além da latência existente. O Lab registra contagem de ações em FILE. |
| Contexto | A conversa considera até 36 turnos anteriores. Preserva a prioridade dos três últimos, seleciona demais pares pela sobreposição lexical com o pedido e restaura a ordem cronológica. O limite de 24 mil bytes se aplica ao histórico, como aproximação de custo, e não à requisição inteira nem à tokenização de um modelo. |
| Provedor | `AIClient` aceita um transporte injetado. O caminho padrão usa o mesmo SDK, credencial e timeouts da Anthropic. A interface do transporte ainda tem o formato Anthropic. |

Comparação reproduzível com fixtures em `test_adaptive_step_runtime.py`: o critério antigo aceita
repetir um resultado de clique incerto prefixado por ❌. A candidata despacha uma vez nesse cenário,
recupera a fixture com falha comprovadamente anterior ao efeito e recusa despachos após o teto.
O teste de contexto compara a seleção anterior por recência com a nova seleção de um par relevante
mais antigo, dentro do limite. As métricas são implementadas para futuras execuções. Não foram
estimados ganhos de latência ou economia com base nesses testes.

Os checkpoints existentes continuam aditivos. A fase ainda precisa de identidade semântica mais
forte para ícones e controles sem rótulo, migração da aprovação inline legada, orçamento global
de planejamento, retomada com reconciliação externa, replanejamento por modelo, CLI do runtime,
verificadores de resultado específicos para GUI, interface normalizada para múltiplos provedores
e comparação de estratégias do Lab com separação de acesso ao holdout. O Lab permanece com as
fronteiras de isolamento existentes e não executa uma estratégia de runtime com efeitos reais.

Gate final da Phase III com Python 3.11 no Windows: 753 testes de regressão aprovados, smoke,
vault e whitespace aprovados, `CODE_READY True` e `MAIN_READY True`. Contrato TypeScript, tokens e
`build:check` também passaram. Os testes novos comparam tentativa incerta, recuperação pré-efeito,
cancelamento, prazo, seleção de histórico e injeção do transporte do provedor. A validação desta
fase foi offline, com fixtures e sem automação do desktop pessoal.

## Revisão da Phase III — recuperação guiada por evidência

Baseline da revisão: checkout da Phase III sobre `ae17a38`, com 753 testes aprovados.
Os casos abaixo usam adaptadores e janelas simulados, arquivos em diretórios temporários e
transporte de modelo substituído.

| Ponto confirmado | Mudança e evidência |
| --- | --- |
| 1. Visão direta exigia foco configurado por um passo anterior. | `AutomationEngine._vision_request_window` admite a janela da frente se ela corresponder ao único app citado no pedido. O ponto deve pertencer à janela alvo e a sessão começa sem herdar o HWND da tarefa anterior. `test_task_window_resolution_refuses_unrelated_foreground` cobre Paint e uma janela de navegador incompatível. |
| 2. O prazo fixo de 300 s interrompia o próximo despacho mesmo com progresso. | `execution.run_limit_s` passa a ser opcional, com zero por padrão. O vigia de inatividade continua ativo. `test_no_absolute_limit_still_honors_cancel_and_action_limit` simula 3.600 s e verifica ação e cancelamento. |
| 3. A identidade comparava títulos e nomes de apresentação. | A normalização cobre apenas o contador inicial do WhatsApp. A janela, o identificador UIA e o estado observado continuam vinculados quando disponíveis. Pilotos vinculam o controle ou o campo e, em envio de texto, o conteúdo. A confirmação inline do executor foi desativada. `test_whatsapp_unread_counter_preserves_window_binding`, `test_changed_target_or_payload_invalidates_confirmation` e `test_expired_approval_never_releases_effect` cobrem essas decisões. |
| 4. Alterações em implementações inteiras invalidavam moldes e esperas neutras impediam promoção. | `planner_version` combina a revisão de compatibilidade, o prompt e as políticas. A migração invalida uma vez os moldes do esquema antigo. `verified_success` aceita esperas bem-sucedidas somente quando os demais passos têm evidência. `test_learning_ignores_successful_wait_only_when_an_outcome_was_verified` protege contra promoção baseada apenas em espera. |
| 5. Desligar o ledger comum desligava a persistência obrigatória. | `TaskLedger.effect` persiste intenção e decisão com telemetria desligada. Falha de disco, escopo ausente ou ID inválido continua bloqueando o efeito. `test_disabled_task_telemetry_keeps_effect_decisions` e `test_shadow_and_off_cannot_bypass_durability` cobrem a separação. |
| 6. UIA e navegador perderam a repetição segura, enquanto adaptadores internos ainda podiam repetir depois do despacho. | Os adaptadores declaram falha anterior ao clique onde conseguem comprová-la. O runtime admite uma tentativa adicional nesse caso. Resultado incerto fica no ledger e interrompe a sequência. `test_click_adapters_only_recover_from_known_pre_dispatch_failure` e `test_written_uncertain_outcome_is_not_a_confirmed_failure` cobrem as duas situações. |

O orçamento compartilhado pelo Controller e pelo cliente de modelo é optativo via `execution.model_budget_usd`.
Aplica-se no planejamento e na conversa ao contar os tokens da requisição e reservar a saída. A conversa
também reserva o custo máximo das buscas remotas declaradas. Com o teto ativo, o SDK desliga novas
tentativas automáticas. `test_conversation_budget_counts_tools_and_reserves_server_search_cost` confirma
que chamadas acima do orçamento são barradas antes do streaming. A reserva é estimada e reconciliada com
o uso informado. CLIs externas, operações já iniciadas e trabalhos em threads separadas ficam fora desse escopo.

O verificador de links lê novamente a URL depois do clique. A mudança de título, sozinha, conta como
sucesso operacional. O destino conta como verificado quando a URL lida corresponde ao link escolhido.
Redirecionamentos e ações sem URL continuam sem essa evidência. A pesquisa automática antiga agora só
observa e executa casos de desenvolvimento da mesma revisão do conjunto. O snapshot da rodada mostra
apenas os casos executados e mantém o hash do conjunto arquivado. Validação explícita ainda pode executar
holdout. O isolamento se aplica ao fluxo do Lab, com arquivo e acesso local compartilhados.

### Comparação offline

- `test_baseline_retries_uncertain_failure_candidate_stops` reproduz a decisão antiga de repetir erro
  de clique por prefixo. A candidata despacha uma vez quando o resultado é incerto.
- `test_click_adapters_only_recover_from_known_pre_dispatch_failure` mostra uma recuperação em dois
  despachos nas fixtures de UIA e navegador, seguida de um único despacho para o cenário incerto.
- `test_browser_link_dispatch_and_independent_destination_check` usa três observações por fixture.
  A verificação só passa quando o destino solicitado é observado. Cada cenário despacha um clique.
- `test_research_proposes_tests_and_never_publishes` compara os mesmos três casos de desenvolvimento.
  A baseline passa 2 de 3 e a variante 3 de 3 com planejadores sintéticos. O caso reservado fica fora da rodada.
- A rodada focada de runtime, autorizações e Lab passou 71 testes. Nenhum modelo real foi chamado
  e nenhuma interface pessoal foi automatizada. As fixtures não estimam ganhos de latência, tokens ou custo.

Executando o mesmo planejador de `LabOptimization.planner_by_instructions` com `origin="simulado"`,
`split="development"` e `repeats=5`, o Lab registrou 15 pares, 5 melhorias e nenhuma regressão.
A baseline passou 10 de 15 e a candidata 15 de 15, com 15 ações de arquivo em cada versão e nenhuma
intervenção humana. A mediana local foi 19 ms e 18 ms, respectivamente, em uma única rodada.
Tokens (1.000 e 1.500) e custos (US$ 0,010 e US$ 0,015) são valores fornecidos pelo planejador sintético.
O gasto de API foi zero. Esses números caracterizam a fixture e o fluxo de verificação.

Gate final no Windows com Python 3.11: `CODE_READY True`, `MAIN_READY True`, 764 testes na
suíte de regressão, smoke, vault e whitespace aprovados, zero exclusões pendentes no vault.
Na interface, `typecheck`, os 63 testes e `build:check` passaram.

### Limites remanescentes

O replanejamento geral por objetivo, a retomada com reconciliação externa, o runtime headless compartilhado
com CLI e o contexto unificado de ponta a ponta continuam pendentes. A evidência ainda cobre poucos
resultados de GUI, e ícones sem identidade acessível exigem trabalho adicional. A autorização nesta rodada
cobre rotas de clique e verificações de alvo dos pilotos. A revisão de destinos de arquivo, hotkeys,
comandos e outros caminhos legados ainda precisa de testes de integração próprios. O ledger mínimo também
precisa de política de retenção para instalações sem telemetria. A recuperação de contexto permanece
lexical com recência e limite de bytes. O segundo provedor, a normalização do protocolo de modelos,
a comparação de estratégias do runtime no Lab e um holdout com controle de acesso separado ainda não
foram entregues. As comparações com modelos reais dependem de uma rodada autorizada.

## Phase IV — recuperação adaptativa de cópias

A baseline histórica é o checkout da Phase III sobre `ae17a38`, com 764 regressões, 63 testes de
interface e os dois gates aprovados. O início da Phase IV preservou todas as mudanças que já
estavam no checkout. SHA-256 do runtime inicial `d96fb831a3fc65193c7905200366ad41465ba0a51c4bf3156fa7f9ad6ca15a12`.
Para isolar o efeito do replanejamento, a comparação abaixo usa os mesmos verificadores e
políticas da Phase IV nos dois braços. A chave `runtime_strategies` desliga a alternativa
para o braço `fixed` e liga para `adaptive`.

| Arquivos | Integração |
| --- | --- |
| `core/run_context.py`, `desktop/controller.py`, `core/step_runtime.py`, `core/ai_client.py`, `core/lab_budget.py` | O Controller cria o contexto antes de resolver e planejar o pedido. O objetivo original, escopo de arquivos da conversa, orçamento, cancelamento, deadline, grafo, evidências e referência ao ledger têm o mesmo ciclo de vida. A inatividade é um limite separado do prazo absoluto opcional. O prazo é compartilhado por chamadas na thread e pela admissão das ações. |
| `core/file_recovery.py`, `core/automation_files.py`, `core/verification.py` | Se uma cópia não encontra a origem antes de produzir efeito, o runtime pode observar até 256 entradas dentro da pasta autorizada e tentar uma origem alternativa. Exige o nome literal no objetivo, uma opção única e o mesmo destino, com nova passagem pela autorização. Caminhos específicos do usuário, links, junções, ambiguidade, simulação, negação, cancelamento e resultados incertos impedem a adaptação. O destino de arquivo é aberto com criação exclusiva. O verificador confere conteúdo de arquivos regulares de até 16 MiB e estabilidade da origem. |
| `core/automation.py`, `core/task_ledger.py` | A aprovação de exclusão vincula a identidade observada do recurso e o executor reconfere após aprovação. O ledger registra o replanejamento antes da alternativa e distingue resultado verificado, operacional, falha pré-efeito, parcial, incerto e bloqueio de política. |
| `core/lab.py`, `core/lab_report.py`, `desktop/bridge_core.py` | O Lab aceita um mapa opcional de versão para estratégia pelo payload existente, registra o protocolo e preserva promoção manual e rollback. Um experimento de estratégias não serve para promover instruções. |
| `test_phase_four_runtime.py`, `test_durable_effect_gate.py`, `test_task_ledger.py`, `test_lab.py` | Corpus pareado, impedimentos à alternativa, troca de arquivo após a pergunta de confirmação, integração do Controller com ledger e cancelamento durante o planejamento no Lab. |

Num pedido de cópia, o runtime usa a falha anterior ao efeito como observação. A estratégia
alternativa procura uma origem única dentro do escopo, despacha o mesmo tipo de ação pelo
executor regular e verifica o artefato depois. A observação e a nova ação consomem do teto de
ações. Há no máximo uma alternativa por passo. O teste do Controller confirma que preparar o
diretório de destino continua registrado uma única vez e que só a cópia é replanejada.

### Comparação pareada e ablação

O corpus está em `app/tests/test_phase_four_runtime.py`. Execute com
`python -m unittest app.tests.test_phase_four_runtime` na raiz. O plano é idêntico para os dois
braços. O Lab alterna a ordem, aplica as mesmas políticas e confere o estado final em diretórios
temporários independentes. São cinco casos de desenvolvimento com três repetições. O sexto caso
fica reservado e foi excluído desta comparação. Hash do conjunto
`c5dc777697b80412f0be0f7a8f2f98a04d808dac3e2d4fd5d904682bb02ae16a`.

| Métrica | Fixo | Adaptativo |
| --- | ---: | ---: |
| Resultado verificado | 12/15 | 15/15 |
| Falhas recuperadas | 0 | 3 |
| Ações admitidas, incluindo observação | 12 | 21 |
| Latência mediana local por caso | 17 ms | 17 ms |
| Tokens e custo de API | 0 e US$ 0 | 0 e US$ 0 |
| Intervenções humanas no corpus | 0 | 0 |
| Efeitos fora do escopo no caso adversarial | 0 | 0 |

As três melhorias são repetições do mesmo cenário de subpasta. Os resultados demonstram
recuperação para esse cenário. O corpus sintético e pequeno não estima desempenho de produção
nem melhora em tarefas com modelos reais. Duas execuções do mesmo planejamento também podem
divergir fora deste protocolo.

O verificador da skill Agent Evals Engineer recebeu os IDs previamente fixados e os resultados
dos verificadores de disco em uma coleção separada das propostas. Ele confirmou `pass@1` macro
de 0,8 no braço fixo e 1,0 no adaptativo, sem tarefas incompletas.

Gate final no Windows com Python 3.11: `CODE_READY True`, `MAIN_READY True`, 770 regressões,
smoke, vault e whitespace aprovados. Typecheck, 63 testes de interface, contrato da Bridge
e carimbo do build passaram. Nenhuma chamada paga foi feita.

### Limites e próximos incrementos

- O replanejamento geral por objetivo, a retomada com reconciliação externa e a execução
  headless nos demais canais ainda dependem de verificadores e de autorização por ferramenta.
  Resultados parciais ou incertos interrompem a sequência e exigem conferência. Operações já
  iniciadas e tarefas em outras threads ainda podem ultrapassar o prazo.
- A identidade de exclusão é baseada em metadados de arquivo e ainda tem uma janela entre
  checagem e despacho. O restante dos caminhos legados e a autorização de árvores com links
  precisam de validação própria. A verificação forte nova cobre cópias regulares pequenas.
- O próximo incremento de contexto precisa comparar recuperação semântica e compactação com
  a baseline lexical antes de adoção. Obsidian e a política de egress continuam como estavam.
- A normalização do protocolo de modelos e o segundo provedor continuam pendentes.
  O orçamento da thread usa o contador do provedor existente quando configurado.
- O holdout fica separado do planejamento automático pelo protocolo do Lab. Um coletor
  independente com armazenamento e acesso segregados, e uma avaliação real expressamente
  autorizada, ainda são necessários para evidência de promoção além das fixtures.

### Phase IV — contexto, provedor, reconciliação e isolamento da pesquisa

| Arquivos | Resultado e fronteira |
| --- | --- |
| `core/context_engine.py`, `agents/chat_agent.py`, `core/ai_client.py`, `config.yaml` | A conversa pode combinar sobreposição lexical e conceitos locais e compactar turnos mais antigos em trechos com origem e índice. Os trechos são dados citados, com delimitadores escapados. Com `chat.context_input_tokens` definido, a conversa conta a requisição montada, incluindo ferramentas, e compacta o histórico inicial ou bloqueia a chamada se ela exceder o teto. Busca sob demanda no Obsidian e no Cérebro continua no fluxo existente. |
| `core/model_provider.py`, `core/ai_client.py`, `app/requirements.txt` | O adaptador Ollama usa o mesmo cliente de mensagens e conversa, com streaming, saída estruturada, imagens incorporadas, chamadas de ferramentas locais, uso e erro de protocolo. A Anthropic continua sendo a escolha padrão. Seleção explícita por `ollama:<tag>` e `providers.ollama_enabled`. O endpoint é fixo em loopback, sem proxies ambientais ou redirects. O modo de privacidade offline continua bloqueando o envio e limites que exigem contagem exata antecipada são recusados pelo adaptador Ollama. |
| `core/verification.py`, `core/task_ledger.py`, `core/automation_files.py`, `desktop/controller.py`, `scripts/reconcile_copy.py` | O executor pode registrar um compromisso de conteúdo e destino antes de uma cópia regular de até 16 MiB. A reconciliação compara o destino informado com o vínculo e o conteúdo registrado. Só resolve aquela etapa, preserva o estado global da tarefa e não despacha ações. Cópia de árvore recusa links ou junções observados durante a enumeração. |
| `core/uia_driver.py`, `core/interaction_layer.py`, `core/automation.py` | Digitação por UIA e visão passa pelo mesmo foco de um campo identificado. O texto é colado literalmente. A sintaxe de teclas no conteúdo não vira comando e a rota de visão deixa de clicar em coordenadas sem confirmar um campo. |
| `core/lab.py`, `test_phase_four_completion.py` | A pesquisa automática lê apenas a projeção física `development/`, com IDs e resultados da parte de desenvolvimento. Replays e inspeção pelo operador continuam com os arquivos de avaliação. Rodadas de holdout puro e experimentos de estratégia não entram no aprendizado da pesquisa. Rodadas históricas sem projeção ficam fora dos sinais automáticos. |

Para reconciliar uma etapa registrada, execute
`python app/scripts/reconcile_copy.py <id-da-tarefa> <etapa> <destino-absoluto>`. Destino ausente,
trocado ou com conteúdo divergente preserva a incerteza. O registro contém hashes, sem acrescentar
o texto dos arquivos ou o caminho em claro. A correspondência prova o estado do artefato, sem
identificar qual processo o criou. Cópias anteriores à mudança, diretórios e arquivos maiores
ainda exigem conferência manual.

Ative Ollama somente com um servidor local configurado para operar sem os recursos de nuvem
e um modelo já instalado. O aplicativo não administra o daemon ou o firewall do host. Consulte
[configuração local do Ollama](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)
e [contrato de chat](https://docs.ollama.com/api/chat). O contrato foi verificado offline com
transporte HTTP simulado, sem um modelo instalado nesta sessão. O adaptador local permanece
desligado por padrão. A contagem configurável tem suporte no transporte Anthropic e inclui
histórico, mensagem atual, sistema e ferramentas. Os limites de orçamento continuam independentes.

Na ablação de contexto, o lexical recuperou 1 de 5 turnos relevantes e o híbrido 5 de 5.
Ambos recusaram o caso negativo. O corpus foi construído para cobrir as relações do vocabulário
local e mede seleção, não qualidade da resposta do modelo. O teste de integração da conversa
também reproduz a ausência da dotação no braço lexical, sua recuperação sob outro termo e
sua retirada quando a contagem ultrapassa o teto. A estratégia segue optativa.

A ferramenta `buscar_na_conversa` recupera trechos sob demanda no mesmo histórico autorizado.
Após a leitura, as chamadas seguintes desse turno ficam sem busca remota. A regressão reproduz
as duas voltas e confere os trechos e a remoção da ferramenta de busca.

Gate final no Windows com Python 3.11: `CODE_READY True` e `MAIN_READY True`.
A suíte de 781 testes Python passou, assim como typecheck, 63 testes de interface, contrato
TypeScript, carimbo do build e smoke offline. O gasto em API foi zero.

Os riscos residuais incluem replanejamento ainda restrito a estratégias declaradas, reconciliação
automática indisponível para efeitos externos e verificação limitada nos controles de GUI sem
identidade acessível. A projeção do Lab separa o caminho de leitura da pesquisa automática.
Um usuário ou processo com acesso integral à pasta do Lab ainda pode ler o holdout. Uma avaliação
com modelos reais, isolamento por credenciais separadas e avaliação de contexto fora da
taxonomia local continuam sem evidência nesta rodada.

## Phase V — decisão compartilhada e replanejamento de leitura

O prompt da Phase V foi lido integralmente. O arquivo avulso `harness-evolution(4).md` não foi
encontrado em Downloads, Documentos ou Desktop. O relatório versionado acima foi usado como
referência. O ponto de partida real foi a candidata IV do checkout, sobre `ae17a38`, incluindo
arquivos novos. Foram conferidos o fluxo do Controller, os passos do Lab, o verificador de cópia,
o provedor e as fronteiras de egress. O gate da baseline passou. As 14 regressões focadas de
cópia e contexto passaram, assim como typecheck, os 63 testes de UI, contrato, tokens e build.

A cópia temporária inicial inventariou 502 arquivos e produziu o manifesto SHA-256
`2e0f34cf35c8769dd7fb336d0991cd1820b5100c645a352e5021e86caf620839`.
A pasta temporária isolada perdeu disponibilidade após a chamada. O ZIP da baseline
não está disponível como artefato persistente. A referência Git, o hash e os resultados do gate
permanecem registrados. O commit Git, sozinho, não contém a candidata IV completa.

| Gate ou requisito | Implementação e evidência |
| --- | --- |
| 0. Baseline e corpus | Revisão local e gate reproduzidos antes das mudanças de código. [Protocolo prévio](phase-v-protocol.md), SHA-256 `0c3338fabfdddfcf1973593590f131ecd755b9520f4932600c6d31640eba5ec4`. O controle de avaliação usa a variante comportamental Phase IV no runtime candidato. A retenção do snapshot exato e o corpus reservado por credencial permanecem pendentes. |
| 1. Autoridade e limites | `action_policy.py` bloqueia rotas de aplicação externa sem isolamento no modo offline e recusa parâmetros FILE de rede antes da resolução. Uma alternativa FILE preserva nome contratado, operação e destino e exige nova autorização. A identidade da origem é conferida imediatamente antes do novo despacho. O orçamento de passos admite uma operação de cada vez e até quatro replans por execução. Os testes exercitam cancelamento, troca de origem, orçamento, código de janela injetado e recusa de escopo. |
| 2. Runtime | `run_context.py`, `step_runtime.py`, `task_schedule.py`, Controller, Lab FILE e `scripts/read_objective.py` usam a mesma admissão e decisão por passo. O patch tipado modifica parâmetros de um passo pendente, registra a observação e mantém o objetivo original. As duas novas alternativas cobrem leitura FILE e WEB de página já aberta. O primeiro arquivo da composição FILE + DATA fica preservado, e o conteúdo da planilha é conferido por releitura no disco. |
| 3. Reconciliação | `task_ledger.py` rejeita IDs de leitura inválidos e recusa reconciliar com registros corrompidos ou truncados. A visualização tolerante preserva a etapa incerta. A CLI de cópia aceita `--inspect` para mostrar estado, etapas e checkpoint, sem divulgar o conteúdo do pedido no resumo. A reconciliação continua sem despacho de ações nem extensão de autorizações. |
| 4. Provedor e contexto | Funcionamento anterior preservado e testes offline aprovados. Não foi encontrado executável Ollama ou listener na porta 11434 na inspeção. Inferência real, tokenizer local e avaliação semântica independente continuam sem validação. |
| 5. Lab e ciência | A ablação offline cobre dois domínios. O Lab FILE usa o mesmo serviço de decisão do Controller. A fixture WEB substitui as observações de UIA em memória e executa o adaptador real por esse serviço. Acesso negado por ACL do holdout, corpus maior e avaliação com modelos reais continuam pendentes. |

### Comparação e reprodução

Execute na raiz `python -m unittest discover -s app/tests -p test_phase_five_runtime.py`.
Para exportar as linhas, execute com `PYTHONPATH=app` e chame
`app.tests.test_phase_five_runtime.compare()`. O controle `phase_iv` conserva a adaptação
de cópia e desativa as duas alternativas novas. Assim, mantém os demais controles comuns
da candidata e mede o efeito das alternativas, sem alegar execução de uma cópia exata do binário IV.

| Métrica | Controle IV | Candidata V |
| --- | ---: | ---: |
| Critérios satisfeitos no corpus | 4/6 | 6/6 |
| Tipos de falha novos recuperados | 0 | 2 |
| Ações e observações admitidas | 6 | 13 |
| Efeitos fora do escopo nas fixtures | 0 | 0 |
| Chamadas a modelos | 0 | 0 |

O caso FILE recupera o nome literal em subpasta por enumeração limitada. O caso WEB
usa a superfície de texto visível depois de uma leitura vazia e exige a mesma URL
literal e janela observadas. Troca da URL e bloqueio encerram a tentativa. Os seis
casos incluem testes negativos de segurança e medem integração. Não estimam latência,
generalização ou qualidade de inferência real. A composição adicional e os testes
adversariais são relatados à parte, sem ampliar o denominador.

### Operação, reversão e limites

`execution.objective_replan: false` retorna o Controller ao comportamento adaptativo
da Phase IV e preserva as verificações de segurança novas. Eventos de replan são aditivos.
O leitor anterior não usa eventos novos para aprovar efeitos. O rollback não reexecuta
etapas incompletas nem concede autorização por causa da configuração.

A extração é do serviço por passo. Planejamento do Maestro e coordenação integral ainda
passam pelo Controller. A CLI headless `python app/scripts/read_objective.py --root <pasta> <nome>`
cobre leitura FILE com prazo de 30 s e teto de três ações. A inspeção usa
`python app/scripts/reconcile_copy.py <id> --inspect`. Hoje a reconciliação cobre o conteúdo
de cópia regular na fronteira definida na IV. Retomada automática de tarefas depois de
crash, replan por modelo, verificação universal de conta/documento, quotas de ferramentas
aninhadas e isolamento de SO não foram entregues. A janela de troca de alvo entre a última
checagem e o acesso não é eliminada, e o bloqueio de aplicações externas em offline não
controla processos ou serviços do sistema já ativos.

Digest da candidata para o gate de código: `ea1530547171e8e49f0715f0e17675862e3448963bf2e6976643d55912288cf4`.
O ensaio WEB final usa a árvore simulada de acessibilidade como entrada. A leitura por
intervalo e a captura de texto visível executam o código real do adaptador.

Gate final no Windows com Python 3.11: `CODE_READY True`, `MAIN_READY True`,
`source_unchanged=true`, 789 testes Python, smoke, vault e whitespace aprovados.
Typecheck, 63 testes de interface, contrato, tokens e carimbo do build aprovados.
O primeiro gate da candidata passou nos testes, mas não aprovou o snapshot porque
a fixture WEB mudou durante a execução. O gate final validou as fontes estabilizadas.
O recibo do gate e o JSON pareado ficaram na pasta temporária persistente da sessão.

### Phase V — replanejamento restrito por modelo e retomada de leitura

| Entrega | Código e aceitação |
| --- | --- |
| Resultado literal WEB | `core/run_context.py` e `core/automation.py` reconhecem um pedido explícito de conferência com um único trecho entre aspas e uma URL literal. Uma leitura que não contém o trecho deixa de contar como sucesso do objetivo. URL e janela permanecem vinculadas à observação inicial. |
| Escolha pelo modelo | `core/objective_replanner.py`, `core/run_context.py` e o Controller oferecem apenas ampliar a leitura, mudar a representação do mesmo documento ou parar. O modelo recebe o tipo de falha e as opções, sem conteúdo de página, URL ou trecho. O runtime mantém a política, transforma a escolha em parâmetros próprios e rejeita chaves extras. O Controller exige `execution.model_replan: true`, orçamento, prazo absoluto e modo online. O padrão continua desligado. |
| Retomada headless | `core/read_checkpoint.py` e `scripts/read_objective.py` usam o ledger e o serviço de passos existentes. Guardam a vinculação à ordem dos nomes, identidade da pasta e hashes das leituras confirmadas. Um lock de arquivo impede dois executores concorrentes no mesmo lote. A retomada exige novo fornecimento da mesma pasta e da mesma lista, sob a política atual. |
| Contabilidade compartilhada | `core/lab_budget.py` serializa reserva e liquidação de tokens, custo e chamadas. Duas threads tentando admitir uma chamada sob limite de uma resultam em uma reserva. O dispatcher da tarefa já impede execução simultânea sobre a mesma instância de passos. |

Reprodução offline na raiz, com `python -m unittest discover -s app/tests -p test_phase_five_recovery.py`.
O teste de ablação usa um adaptador WEB simulado com o mesmo objetivo. A leitura inicial,
mesmo disponível, não contém o trecho pedido. Sem replanejador, há uma leitura e o objetivo
falha. Com a escolha simulada pela leitura ampliada, o trecho aparece e é verificado na segunda
leitura da mesma janela. Respostas com URL extra, estratégia desconhecida ou JSON inválido
não são despachadas. O cenário mede um único caso de recuperação, sem chamada real nem custo de API.

Quando o orçamento compartilhado registra esgotamento, o próximo despacho de ferramenta
é bloqueado com `budget_limit`. Esse resultado é distinto de cancelamento e falha comum.

Exemplo de retomada:
`python app/scripts/read_objective.py --root <pasta-absoluta> --task-id <id> primeiro.txt segundo.txt`.
Depois de interrupção confirmada, passe os mesmos argumentos com `--resume`. O teste cria um
subprocesso, interrompe-o após o primeiro resultado durável e verifica que a segunda execução
despacha apenas o passo pendente. O primeiro é conferido pelo hash, sem repetir a leitura pelo executor.
Retomada recusa etapa iniciada sem resultado, registro malformado, mudança do conteúdo anterior,
ordem diferente, tarefa já encerrada ou presença de uma aprovação externa. Leituras anteriores
encontradas por adaptação, cujo caminho inicial não comprova o artefato, não habilitam retomada.
Há 30 s de prazo por invocação. Cada nome tem no máximo uma tentativa adaptativa por passagem.

O rollback operacional desliga `execution.model_replan` e deixa de usar `--task-id` em novas
leituras CLI. A política e as validações anteriores continuam. Nenhum checkpoint concede
permissão a outra rotina. Os eventos novos são aditivos e não mudam a reconciliação de cópia.

**Aceitação ainda aberta.** Não foi identificado binário Ollama nem listener em 11434. Não houve
instalação nem inferência real. A retomada cobre lotes CLI de leitura, não as tarefas gerais
do Controller ou efeitos externos. Permanecem pendentes a separação do holdout com negação
comprovada pelo sistema operacional, o corpus independente de 30 tarefas de desenvolvimento
e 20 reservadas, a avaliação real do provedor, a verificação universal de conta/documento e
orçamentos hierárquicos para ferramentas aninhadas. O manifesto da candidata IV está registrado
acima, e o ZIP original continua indisponível. Nenhuma política nem credencial do host foi alterada.

Durante a validação integral apareceu `WinError 5` na substituição do arquivo temporário
de planos aprendidos. O teste passou isoladamente. A gravação agora usa `core.atomic_io.replace_file`,
o helper de recuperação limitada que já existia. Falha persistente continua visível e
preserva o arquivo anterior. Os testes do helper, do ciclo de aprendizagem e da retomada passaram.

Gate final estável no Windows com Python 3.11: `CODE_READY True` e `MAIN_READY True`,
com 795 testes Python. Typecheck, 63 testes de interface, build e contrato TypeScript aprovados.
Digest de código `27ff56708cf778e01e97ab9f44339595c4f0a60f2f5b3a2b26efc4578952f419`.
O recibo, o console e o snapshot redigido desta candidata estão juntos na pasta temporária
persistente da entrega. Nenhum dos testes executou uma chamada paga.

## Phase VI.4 — provedores de modelo escolhidos pela pessoa

Pedido do dono: usar DeepSeek, Ollama e qualquer outro modelo dentro da plataforma, só com uma chave ou
créditos. Implementado sobre o contrato de provedor da Phase IV, sem segundo cliente nem novo runtime.

| Peça | Arquivo | Comportamento |
| --- | --- | --- |
| Registro | `core/provider_registry.py` | Modelo como `provedor:modelo`; sem prefixo continua Anthropic. Prontos: OpenAI, DeepSeek, OpenRouter, Groq, Mistral, Together, Ollama e LM Studio. Outros por `providers.custom` (HTTPS, ou HTTP só em loopback). Capacidades declaradas por provedor (imagens, ferramentas, JSON nativo, busca do servidor). |
| Adaptador | `core/model_provider.py` (`OpenAICompatProvider`) | Chat/completions em streaming: texto, ferramentas do app com argumentos em pedaços, JSON (schema nativo ou `json_object`), uso de tokens, cancelamento, erros 401/402/404/429 legíveis. Chamada de ferramenta cortada pelo limite nunca é executada; ferramenta não oferecida é recusada. |
| Cliente | `core/ai_client.py` | Roteia pelo prefixo; mesma contagem de chamadas, métricas e cancelamento. Sem preço em `providers.prices` o custo fica 0 (desconhecido); sob orçamento estrito do Lab a chamada é recusada. O app abre sem chave da Anthropic quando outro provedor está escolhido; chave adicionada depois vale sem reiniciar. |
| Chaves | `core/secret_store.py` | DPAPI do usuário Windows em `memory/provider_keys.json` (fora do git). A chave nunca volta pela Bridge nem vai para logs. Alternativa: variável do `.env` (`DEEPSEEK_API_KEY`...). |
| Escolha | `core/user_settings.py`, `core/config.py` | Modelo principal (`strong`) e rápido (`fast`) escolhidos na tela valem por cima do `config.yaml`. |
| Tela | `ui/src/views/ModelProviders.tsx` | Configurações > Modelos: modelo por nível, chave por provedor (salvar/remover), "Testar" (GET `/models`, sem gerar texto) e lista para escolher. |
| Privacidade | `core/ai_client._gate` | Offline estrito bloqueia todos os provedores, inclusive locais (decisão da Phase V). `privacy.allow_local_models: true` libera só os de loopback. |
| Conversa | `agents/chat_agent.py` | A busca na web (ferramenta do servidor da Anthropic) só é oferecida quando o modelo a suporta. |

Verificação: `test_model_providers.py` (27 casos, transportes simulados, nenhuma rede) cobre contrato do adaptador,
roteamento, preço, chave ausente, offline, orçamento, ida e volta de ferramenta, DPAPI (cifrado em repouso,
entrada inválida, blob adulterado), validação da escolha de modelo e Bridge sem eco da chave. Tela conferida no
modo demonstração (`?demo`): seção renderizada e "Testar" listando modelos, sem erro no console. Gate com
`CODE_READY True` e `MAIN_READY True`; 63 testes de UI, build e contrato TypeScript em dia.

Não verificado: nenhuma chamada real a DeepSeek, OpenRouter, Ollama ou outro provedor (sem chave/servidor
autorizado nesta sessão). Qualidade dos agentes com outros modelos não foi medida: prompts e planos foram
ajustados para Claude, e modelos sem ferramentas ou sem JSON confiável podem falhar em Maestro/agentes.
Próximo passo científico: rodar `eval_agents_live.py` com o mesmo corpus por provedor, com orçamento aprovado.

## Phase VI e VII — incremento de 26/11 (tela de provedores, Cérebro para todos, RSI supervisionado)

### Provedores: tela no formato de conexões e API personalizada
A seção Configurações > Modelos virou cartões de conexão (nome, estado, Editar) e um painel com duas abas:
**Provedor do catálogo** (provedor, chave com aviso quando a variável do ambiente não existe, configurações
personalizadas, Testar conexão) e **API personalizada** (nome curto, nome exibido, endereço, chave). Provedores
personalizados ficam em `settings.json` (`custom_providers`), sem a chave; a chave vai para o DPAPI. HTTPS, ou HTTP
só em loopback; o nome não pode tomar o lugar de um provedor pronto. RPC novos: `providerCustomSave`,
`providerCustomRemove` (contrato e fixture atualizados).

Correção encontrada pelos testes: `user_settings.load/save` fixavam o caminho padrão na importação, então um teste
que trocava `PATH` gravava no arquivo real. O caminho agora é lido na hora da chamada.

### Cérebro para todos os agentes e provedores
Todos os agentes recebem o Cérebro pelo prompt (`brain_guide`/`context_for`), sem depender do provedor; a conversa
consulta sob demanda com `buscar_no_cerebro`/`ler_nota_do_cerebro`, que são ferramentas do app e funcionam em
qualquer modelo com tool calling; Claude Code e Codex consultam pelo MCP. Provas em `test_model_providers.py`:
um modelo DeepSeek simulado chama `buscar_no_cerebro`, recebe a nota e responde com ela; o prompt de planejamento
enviado ao Groq leva a direção do Cérebro. A busca na web da Anthropic não é oferecida a outros provedores.

### VI.2 — verificação independente
`core/verification.independent_check`: segunda conferência do estado final, fora do handler, para criar pasta,
mover, copiar (SHA-256), gravar arquivo (hash do conteúdo pedido), planilha (reabre e confere abas) e projeto
(arquivos presentes). Ligada no Controller depois de cada passo dado como verificado: divergência tira o
"verificado", conta `false_successes` e nunca alimenta aprendizado. Ações sem verificador ficam como estavam.
Testes: `test_independent_verification.py`.

`objective_replanner` passou a aceitar falhas de qualquer provedor (antes só `APIError` da Anthropic); a validação
estrita da resposta continua no `RunContext` (chave extra recusa a resposta inteira).

### VII-A/B — RSI supervisionado sobre o Lab (headless)
`core/rsi.py` acrescenta governança ao ciclo que já existia em `lab.py` (variante, rodada pareada, `promotion_check`
com holdout, promoção humana, rollback): `ExperimentSpec` (objetivo, categoria, limites fixos: até 3 propostas,
até US$ 5, aprovação do operador), admissão por regra fixa (recusa código, ferramenta privilegiada, dispensa de
confirmação, desligar política/limite/validação, citar políticas em código, avaliador/holdout ou credenciais),
`EvaluationRecord`, `PromotionDecision` e `ScientificMemory` (`science.jsonl`, inclui resultados negativos e
impede repetir hipótese refutada ou rejeitada). Invariante verificada: a rodada nunca muda a versão ativa.
Rodada simulada nunca vale como evidência. `test_rsi_lab.py` cobre a trajetória completa em fixture: hipótese,
candidata isolada, avaliação, recusa sem holdout, avaliação reservada, decisão humana, versão rastreável e rollback.

### Matriz

| Requisito | Estado | Evidência / limite |
| --- | --- | --- |
| VI.4 provedores reais | Parcial | Contratos e tela prontos; nenhuma inferência real (sem chave/servidor autorizado). |
| VI.2 verificação | Parcial | FILE/DATA/projeto independentes; WEB/DESKTOP/VOZ sem verificador independente. |
| VI.1 loop adaptativo | Parcial | Replanejamento de leitura (FILE/WEB) da Phase V; FILE→DATA e WEB→DATA compostos não demonstrados. |
| VI.3 contexto/memória | Parcial | Contexto híbrido da Phase V; sem corpus independente de avaliação. |
| VI.5 Computer Use | Bloqueado | Requer VM e contas de fixture aprovadas. |
| Gate VI (30/20, +10 p.p.) | Bloqueado | Corpus independente e inferência real pendentes; nenhuma meta alegada. |
| VII-A governança | Atendido (headless) | Contratos, limites, admissão, memória científica, decisão humana. Holdout separado por pasta, não por identidade do SO (bloqueio registrado em todo relatório). |
| VII-B piloto prompt | Atendido em fixture | Trajetória completa com rollback; avaliação real depende de modelo autorizado. |
| VII-C estratégias de runtime | Não iniciado | Categoria `runtime_strategy` declarada e recusada até haver publicação segura. |
| VII-D UI do RSI | Não iniciado | Fluxo provado headless; superfície no Lab é o próximo passo. |

Gate desta entrega: `CODE_READY True`, `MAIN_READY True`; 63 testes de UI, build e contrato TypeScript em dia.
Nenhuma chamada paga; nenhum dado pessoal lido.

## Consolidação e validação de inteligência

O relatório avulso `harness-evolution(6).md` não foi encontrado nas pastas Downloads,
Documentos e Desktop. A análise utilizou este relatório versionado e o checkout local,
incluindo `rsi.py`, os adaptadores e as alterações de configuração dos modelos.

| Achado confirmado | Incremento e evidência |
| --- | --- |
| Capacidades eram iguais para todos os modelos de um provedor. | `provider_registry.capabilities` admite contratos específicos em `providers.model_capabilities`, com campos booleanos validados. O transporte compatível usa o contrato do modelo escolhido. Os defaults anteriores permanecem e ainda precisam de conformidade real. `test_consolidation.ModelContract` testa modelos distintos e recusa configuração inválida. |
| Custo remoto sem tabela chegava como zero sem marcador. | O cliente adiciona `cost_known`, `cost_status` e `unknown_cost_calls`. O campo numérico anterior permanece por compatibilidade. Consumidores que exibem totais precisam usar o marcador para evitar apresentar o subtotal como custo completo. Testes de provedor verificam explicitamente o estado desconhecido. |
| RSI admitia texto por filtros, sem uma operação tipada de escrita. | `InstructionMutation` admite somente `replace_instructions` para agente e baseline correspondentes. Campos extras, operações de política e baseline de outro agente são recusados antes da criação da variante. Mantém avaliação, promoção manual e rollback do Lab. A validação de texto continua como defesa adicional. |
| A memória científica não tinha acesso pela interface. | `ScientificHistory.tsx` aparece na área de experimentos e usa os RPCs `rsiHistory` e `rsiDecide`. Exibe objetivos, versões, taxas, resultados negativos e decisões. A confirmação da candidata é explícita, e a promoção usa o gate existente. A geração e execução de rodadas RSI permanece headless. |
| A segunda verificação DATA validava somente abas. | `independent-v2` reabre a planilha com fórmulas e compara as células declaradas. O teste com abas certas e conteúdo errado perde `verified` e não ensina. O método ainda não recalcula fórmulas nem prova requisitos que não estejam no manifesto. |

Os 50 testes focados de RSI, provedores e verificação independente passaram. Typecheck,
63 testes UI e build passaram. Os contratos Bridge/RPC foram regenerados. A superfície
RSI usa os componentes existentes. Validação visual no Qt e inferência real continuam
sem execução nesta rodada.

O snapshot de código inicial desta consolidação, com 368 arquivos, ficou em
`creativeaix-consolidation-wx6ubu2v` no TEMP persistente, com manifesto e ZIP.
Seu digest foi `66c45813bb798b29003eefecf6c5d08d6dfb331fd4fcccfa389d0c2152cd3459`.
Esse snapshot antecede o reforço da verificação DATA e não representa o fechamento final.

### Matriz de aceitação

| Requisito | Estado e limite |
| --- | --- |
| Runtime e RunContext ponta a ponta | Parcial. Decisão por passo compartilhada e CLI de leitura. Coordenação integral e retomada composta geral ainda no roadmap. |
| Orçamento hierárquico | Parcial. Reserva atômica compartilhada e teto de passos existentes. Suborçamentos de delegação ainda pendentes. |
| Provedores com inferência real | Bloqueado nesta rodada por ausência de autorização e orçamento explícitos. Nenhuma chamada de modelo realizada. |
| Descoberta automática por modelo | Pendente. Registro por modelo foi integrado. Os presets não constituem evidência de capacidades medidas. |
| Verification Engine | DATA reforçado. FILE e artefatos preservados. Prova independente de objetivo geral WEB, CODE funcional e DESKTOP segue parcial. |
| Memória | Memória científica navegável. Taxonomia episódica/semântica/procedural, utilidade e autorização de egress por nota seguem sem consolidação completa. |
| RSI | Operação de escrita tipada e consulta/decisão na UI integradas. Rodadas pela interface, isolamento OS e publicação de estratégias permanecem pendentes. |
| Corpus e holdout | Corpus pequeno sintético existente. 30 tarefas independentes e 20 reservadas sob identidade de menor privilégio continuam pendentes. |

Nenhum teste desta rodada comprova inteligência de modelo real ou isolamento por ACL.
Promoção de instruções e execução experimental continuam dependentes dos controles do Lab.

Gate final desta consolidação em fontes estáveis: `CODE_READY True`, `MAIN_READY True`,
845 testes Python aprovados, smoke, vault e whitespace aprovados. Typecheck, os 63 testes
UI e o build também passaram. O gate anterior teve testes aprovados e foi repetido
porque a verificação DATA mudou durante a execução. A rodada não usou inferência real.

### Revisão de publicação

Os três achados da revisão receberam correções e testes de regressão.

- `rsi.run_round` cria um orçamento compartilhado antes de chamar o proponente.
  Saldo zero impede gerar a proposta. Proponente e planejadores recebem a mesma
  reserva prévia de chamadas, tokens e custo, com prazo de 600 s. Uma rodada dentro
  de outro orçamento é recusada até existir delegação explícita de suborçamento.
  Simulação recebe saldo de API zero. Falhas e consumo reservado permanecem visíveis.
- O streaming compatível exige marcador de término e motivo final válido.
  Fluxo sem término, ferramenta sem confirmação e respostas inconsistentes
  produzem erro antes de disponibilizar uma chamada de ferramenta.
- O marcador `cost_known` acompanha observação, métricas de caso, resumo e JSON
  exportado. A interface mostra custo desconhecido quando o resumo não comprova preço.
  Campos numéricos existentes continuam representando o subtotal conhecido.

As reproduções agora conferem ausência de chamada com saldo zero ou insuficiente,
mesma reserva durante proposta/avaliação, rejeição de ferramentas em fluxo incompleto
e preservação de custo desconhecido na exportação. Nenhuma chamada paga foi realizada.
As limitações científicas e os gates de implantação listados acima continuam aplicáveis.

Validação final para publicação: `CODE_READY True`, `MAIN_READY True`,
849 testes Python aprovados, smoke, vault e whitespace aprovados. Typecheck,
63 testes de interface, build e contrato TypeScript passaram. As reproduções
dos três achados foram incorporadas à suíte. Esta validação foi offline.
