# Master Engineering · candidato local

## Revisão da aba Memória

O panorama agora oferece um mapa arquitetural em nove camadas e uma seleção de notas mais legível. Um teste de
projeção cobre a sobreposição que fazia um marcador na frente interceptar cliques em outra nota. O protótipo
antigo de iluminação por status global só era chamado por seus próprios testes e foi retirado. A iluminação
continua coberta pelas regressões de `traceLit`, que usa os eventos observados.

Os guias Web, Desktop, Data, File e Code foram condensados nas seções efetivamente recuperadas pelo Brain.
Eles orientam a conferir alvo, escopo, resultado e evidência, com critérios por domínio. Playbooks e referências
foram preservados porque são fontes pesquisáveis e possuem vínculos no cofre. A revisão não mede ganho de
qualidade de resposta nem de RSI com modelos reais. A arquitetura tem gates e fronteiras por domínio, mas segue
experimental nas áreas que dependem de execução nativa, isolamento do SO ou inferência medida.

Validação local desta revisão: `CODE_READY=True`, `MAIN_READY=True`, zero exclusões pendentes do cofre,
74 testes de interface, TypeScript, build e carimbo aprovados. A prova Qt com dados fictícios passou nos sete
cenários, incluindo seleção de regiões e abertura de nota a partir de “Memória e contexto”, sem erros JavaScript.

## Continuação · reconexão e proveniência

O cliente solicita `answerSnapshot(run_id)` ao retornar ao estado conectado, quando ainda acompanha uma execução.
O RPC autenticado recupera o último texto transmitido, com sequência, para reparar a lacuna imediatamente.
A Bridge guarda no máximo 512 mil caracteres para uma execução e descarta o snapshot ao trocar de execução
ou sessão. A recuperação usa o identificador já conhecido pela interface. Recarregar a janela por inteiro
ou reconciliar o estado final de uma tarefa encerrada durante a queda continua fora dessa recuperação.

A promoção do Lab exige um comprovante em memória produzido ao concluir uma avaliação pareada pelo planejador
oficial, com chamadas de inferência observadas. O digest vincula dataset, versões, resultados, ambiente e
orçamento registrados. Feedback editorial posterior fica fora do digest. Uma sessão reiniciada exige
uma nova avaliação para promover. Relatórios antigos continuam consultáveis. O comprovante é consumido
depois da publicação e o rollback existente continua disponível. Isso protege o gate contra a etiqueta
`real` isolada e alterações no relatório, dentro da fronteira do processo. Ainda falta validar inferência
real e executar o avaliador e o holdout sob uma identidade isolada pelo sistema operacional.

O teste da Bridge exercita EventBus, cache, Dispatcher e invalidação por sessão, com o núcleo em memória.
Os testes do Lab usam fixtures explícitas na fronteira de inferência e exercitam tentativa por etiqueta,
alteração do relatório, reabertura em nova instância, promoção válida, empate e rollback.

Validação desta continuação no digest Python `ff78edc11c4b0db103190f6e4f22700d7d52d84f9d7e70fb4ddc122905d3b93b`.
Suíte completa aprovada em 166,69 s, com smoke, cofre e whitespace aprovados. `CODE_READY=True`,
`MAIN_READY=True` e `PRODUCTION_READY=False`. TypeScript, 76 testes de interface, build e carimbo aprovados.
A prova Qt mencionada abaixo pertence ao candidato anterior.

Base e HEAD: `2b50072949881339c0472e5551e1c21cc87ec605`. A árvore estava limpa no início. O candidato é o diff local sobre esse commit, inclusive o build gerado da UI. Windows NT 10.0.26200, 12 processadores lógicos, Python 3.11.9, Node 24.21.0. A verificação de interface rodou com o Node local. O workflow do projeto usa Node 22.

Para reconstruir a base, use um checkout isolado do commit acima e os locks versionados. SHA-256 do lock Python: `82b631ddbfe86f38cc8b1814ac49dc046765f5142007ee8766220b02adb8e2f1`. Lock Node: `e848cb8574a9a48591cf7bd2bd94a4511470b37345b0cb111fa689a4135a9343`. Digest do gate Python da base: `10b93cb09e750fb05e43a9053024fb14f0bbfba43c055183e29a6753d8e58f5d`. Os cenários abaixo usam fixtures e não dependem de configuração pessoal.

O candidato final tem digest Python `ea65be7b85ba2811e0de8cdde0f6c4cf81189e91d102c642b7630fd938876317`. Base e candidato tiveram `CODE_READY=True`, `MAIN_READY=True` e `PRODUCTION_READY=False`. As seis verificações passaram, com zero exclusões pendentes de notas e zero arquivos suspeitos no scanner do gate. A suíte Python levou 125,27 s na base e 151,77 s no candidato, com 860 casos descobertos na suíte final. Uma execução de cada lado, em ambiente compartilhado, não sustenta atribuir a diferença de tempo ao código nem medir desempenho do produto. A prova Qt final passou cinco verificações, sem erro JavaScript e com zero redesenhos ociosos na janela do teste. Contratos gerados, build e carimbo da UI aprovados.

| Cenário | Base | Candidato | Método |
| --- | --- | --- | --- |
| Cópia adaptativa, destino divergente após despacho | Verificação `destination_present` aprovada e uma recuperação contabilizada | Comparação SHA-256 contra a origem efetiva reprova e contabiliza zero recuperações | Teste em `test_independent_verification.py` |
| Cópia adaptativa correta | Origem efetiva usada pela ferramenta, origem planejada usada na conferência | Origem efetiva usada também na conferência, uma recuperação verificada | Mesmo teste, braço sem divergência |
| Leitura adaptativa CLI, composição FILE → DATA, WEB recuperável | Testes preexistentes aprovados no gate | Testes focados aprovados com a fronteira atualizada | `test_phase_five_runtime.py`, `test_phase_five_recovery.py`, `test_phase_four_runtime.py` |
| Retry após texto visível | Evento final com `descartadofinal 🧠`, resposta persistida `final 🧠` | UI e histórico com `final 🧠` | ChatAgent com cliente de fixture, ReplyMixin real |
| Resposta longa | 1.428.025 bytes em 97 eventos | 93.806 bytes em 97 eventos, −93,4% | 96 blocos de 20 repetições de `síntese 🧠\n`, relógio simulado de 100 ms por leitura, JSON UTF-8 da Bridge. Mede payload de evento, sem framing WebSocket |
| Custo desconhecido | US$ 0 por sucesso verificado | Métrica indisponível e cobertura explícita | `test_quality_metrics.py` |
| RSI com taxa empatada | Elegível pelos critérios antigos | Recusado pelo RSI, versão ativa preservada | `test_rsi_lab.py`, dois braços determinísticos |
| Interface | 75 testes, TypeScript e carimbo aprovados | 76 testes, TypeScript, build e carimbo aprovados | Vitest e Vite |

A cópia e a leitura são verificadas no `RunContext`, com um snapshot dos parâmetros enviados pelo dispatcher. Assim Desktop, CLI de leitura e Lab de arquivos compartilham a conferência. Falha da segunda conferência vira `false_success`, encerra a cadeia dependente e fica fora de aprendizado e recuperação verificada. O ledger e o evento de conclusão recebem a classificação final. O teste de clique mantém a exigência de falha pré-efeito para retry e agora conta separadamente a tentativa e a recuperação verificada. Verificadores baseados em reabertura observam o recurso naquele instante e não estabelecem sua identidade em operações futuras.

Em `ChatAgent`, rollback do texto do turno restaura o checkpoint antes de retransmitir. `ReplyMixin` publica `append` com sequência e offset em UTF-16, e `replace`/ `final` com snapshots. O reducer descarta sequências repetidas, lacunas e eventos de outra execução. O próximo checkpoint, texto final ou snapshot solicitado na reconexão repara lacunas. Respostas curtas podem ter maior overhead por evento, como a fixture de retry, 125 → 320 bytes.

O histórico e a tela de tarefa exibem custo desconhecido. A agregação calcula subtotal apenas das execuções com valor utilizável e só publica médias sobre o conjunto completo quando há cobertura integral. Isso ainda depende da disponibilidade de uso e preços reportados. O valor pode ser estimado e não equivale à fatura.

O RSI exige um aumento estrito na taxa de sucesso dos casos do experimento avaliado, que precisa incluir o conjunto reservado. O fluxo manual de manutenção do Lab conserva os critérios anteriores. A condição é conferida novamente dentro da operação de promoção. O teste de empate usa fixture para alcançar a fronteira e demonstra o critério, sem comprovar origem ou ganhos com inferência real.

## Inventário

| ID | Estado | Evidência e limite |
| --- | --- | --- |
| A01 · G1 | VERIFIED | Parâmetros efetivos usados antes da classificação e da contagem de recuperação. Cópia divergente e alternativa correta reproduzidas. Verificação integral de pilotos faz parte de A09/A10. |
| A02 · G8 | PARTIAL | Planejador oficial e chamadas observadas vinculados a digest no processo. Etiqueta sem evidência, relatório alterado e registro reaberto foram recusados. Falta avaliador sob identidade isolada e integração real. |
| A03 · G4 | BLOCKED | `AIClient._local` conserva bloqueio em orçamento estrito. Falta provar reserva de tokens e custo antes de usar modelo real alternativo. |
| A04 · G4 | VERIFIED | Controller, histórico e agregados distinguem ausência de cobertura. Falhas com faturamento sem uso reportado e reconciliação com a fatura seguem abertas. |
| A05 · G4 | PARTIAL | `context_engine.retrieve` usa léxico e conceitos fixos, com opt-in em `config.yaml`. Falta comparação semântica com modelo local autorizado. |
| A06 · G3 | VERIFIED | Fixture reproduz retry com texto parcial na Bridge e igualdade com histórico. Recarga integral do cliente segue aberta. |
| A07 · G3/G6 | VERIFIED | 93,4% menos bytes no cenário longo pareado. Latência de primeiro conteúdo, CPU e heap reais ainda sem medição comparável. |
| A08 · G3 | PARTIAL | Fast paths do Controller/Maestro existem. Falta avaliação pareada de redundância e qualidade de intenção. |
| A09 · G5 | PARTIAL | `browser_pilot.run` mantém teto de turnos e verificações locais. A declaração `done` ainda não verifica o objetivo livre. |
| A10 · G5 | PARTIAL | `browser_uia` tem snapshot limitado e checks de destino. Falta identidade de aba/conta e teste nativo em ambiente dedicado. |
| A11 · G4/G5 | VERIFIED_EXISTING | `ChatAgent.tools` condiciona a busca ao modelo e restringe combinação com leitura local. Pesquisa independente de provedor permanece pendente. |
| A12 · G2 | PARTIAL | `TaskSchedule`, `RunContext`, ledger e CLI de leitura compartilham mecanismos. O Controller ainda coordena o ciclo completo. |
| A13 · G2 | PARTIAL | Reservas e limite de ações exercitados em fixtures. Orçamento de delegações e reconciliação de efeitos de CLIs incompletos. |
| A14 · G1/G7 | BLOCKED | Políticas e registro durável existentes, com cobertura parcial. Faltam isolamento do SO, identidade GUI, retenção, criptografia abrangente e confirmação de revogação. |
| A15 · G8 | BLOCKED | Corpus independente 30/20 e separação comprovada por identidade do SO não demonstrados. |
| A16 · G8 | PARTIAL | `rsi.py` tem fluxo de hipóteses e promoção manual de instruções. O experimento empatado não pode promover via RSI. Proveniência, isolamento e novas categorias continuam pendentes. |
| A17 · G6 | VERIFIED_EXISTING | `probe_cognitive_ui.py` exercita threads de interface, replay e redução de movimento com dados fictícios. Perfil de consumo real continua pendente. |
| A18 · G7 | BLOCKED | Gate local e workflow existentes. Faltam matriz nativa, distribuição assinada, ensaios de migração/rollback e beta consentido. |

## Reprodução

```powershell
.\.venv\Scripts\python.exe app/scripts/check_release.py --code-only
.\.venv\Scripts\python.exe app/scripts/export_ui_contract.py --check
.\.venv\Scripts\python.exe app/scripts/export_theme_tokens.py --check
$env:PYTHONPATH = 'app'
.\.venv\Scripts\python.exe -m unittest app.tests.test_independent_verification app.tests.test_phase_five_runtime app.tests.test_phase_five_recovery app.tests.test_phase_four_runtime app.tests.test_chat_agent app.tests.test_quality_metrics app.tests.test_adaptive_step_runtime
.\.venv\Scripts\python.exe -m unittest discover -s app/tests -p test_rsi_lab.py
Push-Location ui
npm run typecheck
npm test
npm run build
npm run build:check
Pop-Location
git diff --check
```

Para a prova Qt use o Vite em `127.0.0.1:5178` e execute `ui/scripts/probe_cognitive_ui.py` com o Python do projeto. A prova usa perfil descartável.

Para repetir a medição de payload em cada checkout, com `PYTHONPATH=app`, execute o trecho abaixo na
entrada padrão do Python. O cliente e o relógio são fixtures. O cronômetro não mede latência real.

```python
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agents.chat_agent import ChatAgent
from desktop.bridge_core import _to_json
from desktop.controller_reply import ReplyMixin
from tests.test_chat_agent import config, reply

def converse(*args, on_text, **kwargs):
    for _ in range(96):
        on_text("síntese 🧠\n" * 20)
    return reply()

events = []
controller = SimpleNamespace(
    _tls=SimpleNamespace(run_id=1),
    _emit=lambda name, payload: events.append(payload) if name == "answer_delta" else None,
    _emit_usage=lambda: None, _alive=lambda: True,
    session=SimpleNamespace(turns=[], files=[]),
    chat=ChatAgent(client=Mock(converse=converse), config=config()),
)
with patch("desktop.controller_reply.time.monotonic", side_effect=(i / 10 for i in range(1, 10000))):
    ReplyMixin._run_chat(controller, "oi", "oi", {})
print(len(events), sum(len(_to_json(event).encode("utf-8")) for event in events))
```

As mudanças ficam no runtime, Controller/ReplyMixin, ChatAgent, métricas/histórico, reducer React e build derivado. Rollback de código consiste em voltar à versão publicada e ao seu build correspondente em checkout isolado. Os campos acrescentados a histórico e RPC são aditivos e não exigem migração. A UI preserva recepção do formato anterior.

L1–L5 permanecem experimentais para liberação. Validação adicional requer um Windows dedicado com aplicativos, contas e arquivos de fixture para operação nativa. Inferência comparativa requer modelos e orçamento aprovados. Para promoção científica, a próxima dependência é um avaliador sob identidade separada com corpus reservado protegido. Para certificar produção, também é necessária confirmação de revogação das credenciais históricas pelo proprietário. Esta rodada não publicou o candidato.
