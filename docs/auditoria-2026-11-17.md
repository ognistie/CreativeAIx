# Auditoria de arquitetura e UX — 2026-11-17

Rodada feita com `docs/prompts/auditoria-arquitetura-ux.md`, sobre o `main` (33e70cf) mais o redesenho local de
interface (não commitado). Nada foi corrigido nesta rodada. Nada pago foi executado e o desktop não foi operado.

## Status das correções (2026-11-17, mesma data)

| Achado | Estado | Teste |
| --- | --- | --- |
| S1 conversa perdida/corrompida | corrigido: pedido gravado antes da resposta; resposta presa ao pedido (`Session.set_reply`, `set_saved_reply`) | `tests/test_conversation_persistence.py` |
| S1 `click`/`vision_smart` sem porta | corrigido: `click` confere o elemento real (`_effect_at_point`); `vision_smart` removido; prompt sem `click(x,y)`/`run_python` | `tests/test_audit_2026_11_17.py` |
| S2 captura de tela | corrigido: ação declarativa `screenshot` na Área de Trabalho real | idem |
| S2 núcleo que não monta | corrigido: diálogo com o motivo e o app fecha; servidor não manda `hello` sem núcleo (fecha com 4503) | idem |
| S3 diálogos com prazo de 30 s | corrigido: `CoreClient.callWithin` (10 min nos diálogos) | `ui/src/lib/core.test.ts` |
| S3 histórico lido duas vezes | corrigido: uma leitura | `tests/test_audit_2026_11_17.py` |
| S4 gravações não atômicas | corrigido: `.tmp` único por gravação + `replace_file` | `tests/test_conversation_persistence.py` |
| Hipótese: repetir digitação | corrigido: só cliques repetem | `tests/test_audit_2026_11_17.py` |
| Hipótese: Enter no fallback de digitação | corrigido: recusa texto com quebra de linha | idem |
| Hipótese: gate escreve no histórico | descartada (o tamanho e a data não mudam); o gate gravava em `logs/actions.jsonl`: agora usa `CREATIVE_AIX_ACTION_LOG` temporário | idem |
| S3 voz descartada com tela ocupada | aberto: mexe em `App.tsx` (redesenho em andamento) | — |
| S3 smoke do redesenho | aberto: depende do redesenho | — |
| Hipótese `--restricted` | aberto: a CLI `claude` não está instalada nesta máquina | — |

## 1. Resumo executivo

O núcleo está bem cercado: o contrato da interface valida aridade e tipos, o servidor só escuta em 127.0.0.1 com
token por execução, a execução arbitrária (`run_python`, `run_command`, `pip_install`) está desligada no motor, e as
ações de arquivo passam por contrato. Os problemas mais sérios estão nas bordas: na persistência da conversa e na
porta de efeitos dos cliques por coordenada.

Os 5 problemas que mais afetam o usuário:
1. **S1** Abrir outra conversa (ou "Nova conversa") logo depois de um pedido apaga o pedido recém-feito e grava a
   resposta dele na conversa errada. Reproduzido.
2. **S1** Clique por coordenada (`click`) e `vision_smart` não passam pela porta de efeitos: um "Enviar" pode ser
   clicado sem confirmação.
3. **S2** "Tire um print da tela" sempre falha: o atalho gera `run_python`, que o validador reprova.
4. **S2** Se o núcleo falha ao montar (qualquer exceção em `Controller()`), a interface fica 120 s em "Conectando" e
   depois responde "núcleo ainda carregando" para sempre, sem explicação.
5. **S3** Escolher arquivos ou pasta por mais de 30 s perde a escolha: a chamada da interface expira enquanto o
   diálogo ainda está aberto.

Verificações gratuitas: `check_release.py --code-only` deu `CODE_READY False`, com o smoke em 22/23. A falha vem do
redesenho local (o teste procura `SettingsView` no `App.tsx`). O typecheck passou e `npm test` deu 19/19.

## 2. Achados

### [S1] Trocar de conversa logo após um pedido perde o pedido e corrompe outra conversa
- Área: confiabilidade
- Onde: `app/desktop/controller.py:223-267` (`_after_turn`), `controller.py:1022-1067` (`finally` de `_run`),
  `controller.py:196-221` (`new_session`, `open_conversation`), `app/core/session.py:243-270`
- O que acontece: o `finally` de `_run` desliga `running` e só depois o `_after_turn` dispara uma thread. Essa thread
  chama o modelo para compor a resposta (`core.reply.compose`, cerca de 1 a 3 s), faz `self.session.set_last_reply(...)`
  e só então `self.session.save()`. `new_session` e `open_conversation` só se recusam enquanto `running` for True. Por
  isso, durante a composição, a pessoa consegue trocar o conteúdo de `self.session` (que é o mesmo objeto).
- Como reproduzir: script sem rede (`race.py`, rodado no scratchpad), com `compose` demorando 1 s. Terminar o pedido
  da conversa A e chamar `open_conversation(B)` 0,2 s depois. Resultado:
  `A salva no disco: False` e `ultima resposta de B no disco: Resposta de A`.
- Impacto no usuário: o último pedido da conversa A some da barra lateral. A conversa B passa a mostrar uma resposta
  que pertence a A. Com "Nova conversa", o pedido de A também se perde, porque a sessão nova fica vazia e `save()`
  não grava nada.
- Correção sugerida: capturar a sessão antes da thread (`session = self.session`; ou um `snapshot` com o id) e, ao
  terminar, gravar só se o id ainda for o mesmo. Se não for, gravar a conversa original pelo id
  (`Session.read_saved` → atualizar a última resposta → gravar). Gravar a sessão no `finally`, antes da resposta, e
  só atualizar a resposta depois. Teste: o cenário do script, em `app/tests`.
- Confiança: alta (reproduzido no código real com `compose` simulado).

### [S1] Clique por coordenada e `vision_smart` escapam da porta de efeitos
- Área: segurança
- Onde: `app/core/action_risk.py:127-136` (`step_risk`), `app/core/automation.py:1385-1391` (`_click`),
  `automation.py:1245-1254` (`_vision_smart`), `app/core/action_policy.py:10-13` (ambos permitidos ao DESKTOP),
  `app/agents/desktop_agent.py:331,342` (o prompt de fallback ensina `click(x,y)`)
- O que acontece: para `click`, o risco vem só de `params.description`, texto escrito pelo modelo. O
  `_vision_click` confere os nomes reais do elemento na tela (`_effect_at_point`, `automation.py:950`); o `_click`
  não confere. O `vision_smart` deixa o modelo de visão escolher clicar ou digitar e não tem porta nenhuma: nem
  efeito, nem janela em primeiro plano antes do `pyautogui.write`.
- Como reproduzir: `validate_steps('DESKTOP', ...)` aprova `[{"action":"click","params":{"x":1800,"y":1000},"description":"Ponto"}, {"action":"vision_smart","params":{"goal":"mandar a mensagem"}}]`.
  Para os dois passos, `action_policy.authorize` volta `''` e `step_risk` volta `None`. O mesmo clique com
  `description: "Enviar"` volta `enviar`, o que mostra que a porta depende do rótulo escolhido pelo modelo.
- Impacto no usuário: uma mensagem pode ser enviada, ou um botão de compra ou exclusão clicado, sem a confirmação
  prometida pelo modo `enforce`. É exatamente o efeito que POL-009 e `action_risk` existem para impedir.
- Correção sugerida: no `execute`, para `click` usar `_effect_at_point(x, y)` (nomes UIA reais), como no
  `vision_click`. Tirar `vision_smart` do `TOOLS['DESKTOP']`, ou passá-lo pelo mesmo `_effect_at_point` e por
  `_ensure_app_focus`. Tirar `click(x,y)` e `run_python` do `PROMPT_FALLBACK`. Teste: `step_risk`/`execute` em dry
  com um elemento "Enviar" simulado em `names_at_point`.
- Confiança: média. O caminho de código está verificado; não foi verificado se o modelo produz esses passos na
  prática (exigiria chamada paga).

### [S2] "Tire um print da tela" sempre falha
- Área: confiabilidade
- Onde: `app/agents/desktop_agent.py:300-303` (atalho gera `run_python`), `app/core/plan_validator.py:206-208`
  (POL-008), `app/core/automation.py:582-584`
- O que acontece: o atalho determinístico de captura de tela monta um passo `run_python`. O validador reprova
  `run_python` para o DESKTOP, e o motor também recusa.
- Como reproduzir: `_utility_steps('tire um print da tela')` dá `['run_python']`, e `validate_steps` responde
  `reprovado: ferramenta privilegiada fora do dominio do agente`.
- Impacto no usuário: um pedido comum falha sempre, com uma mensagem técnica sobre política.
- Correção sugerida: uma ação declarativa `screenshot` com destino fixo (Área de Trabalho), que já existe como
  `_screenshot` (só precisa gravar no lugar certo e abrir a pasta). Teste: `validate_steps` aprova o atalho.
- Confiança: alta.

### [S2] Falha ao montar o núcleo deixa o app parado sem explicação
- Área: UX / confiabilidade
- Onde: `app/desktop/web_host.py:433-443` (`attach_core` sem `try`), `app/desktop/server.py:263-268`
  (`_authenticate` manda o `hello` mesmo quando `_attached.wait(120)` expira), `server.py:276-280`
- O que acontece: `WebBridge(server)` → `Bridge.__init__` → `_setup_core` → `Controller()`. Qualquer exceção ali
  (configuração corrompida, cofre inacessível, dependência ausente) sobe dentro do slot Qt, e `server.attach` nunca
  roda. A interface espera 120 s, recebe o `hello` e então toda chamada volta "nucleo ainda carregando".
- Como reproduzir: leitura do código. A chave ausente é barrada antes, em `main.py:111`, mas outras exceções não são.
- Impacto no usuário: o app abre, fica dois minutos em "Conectando ao núcleo" e depois não funciona, sem dizer por quê.
- Correção sugerida: `try/except` em `attach_core` e um evento ou método `coreFailed` com a mensagem; no servidor,
  só mandar o `hello` com o núcleo pronto, ou mandar um `hello` com `error`. Teste: um `Dispatcher` falso que falha
  ao montar → o cliente recebe o erro.
- Confiança: alta para o caminho; média para a frequência (não sei quais exceções acontecem na prática).

### [S3] Escolher arquivo ou pasta com calma perde a escolha
- Área: UX
- Onde: `ui/src/lib/core.ts:71` (timeout padrão de 30 s), `ui/src/lib/host.ts:56-68`,
  `app/desktop/web_host.py:216-227` (`_on_gui(wait=True)` espera até 600 s)
- O que acontece: o diálogo do Windows bloqueia a thread de RPC esperando a pessoa, mas a promessa do lado da
  interface expira em 30 s. A resposta que chega depois tem um id que já não existe e é descartada.
- Impacto no usuário: quem demora mais de 30 s navegando nas pastas escolhe o arquivo e nada é anexado (ou a pasta do
  projeto não é definida).
- Correção sugerida: deixar `call` aceitar um timeout por chamada e usar 10 minutos em `pickFiles`/`pickFolder`.
  Teste no `core.test.ts`.
- Confiança: alta (código); não testado com a mão.

### [S3] Comando de voz descartado em silêncio se a tela ainda está ocupada
- Área: UX
- Onde: `ui/src/App.tsx:160-166` (`if (!text || taskStore.get().busy) return;`), `app/desktop/voice.py:876-888`
- O que acontece: a voz publica `voiceCommand`. Se a interface ainda está `busy` (esperando o `executionFinished`
  do pedido anterior), o comando é ignorado sem aviso. A voz tenta de novo até 2 vezes e depois fala "start_fail".
  A execução por voz também depende da janela principal estar conectada: sem ela, nada executa.
- Impacto no usuário: atraso, ou uma fala de falha, em pedidos encadeados por voz.
- Correção sugerida: a interface responde ao `voiceCommand` (aceito ou recusado), ou o núcleo executa direto e só
  avisa a tela.
- Confiança: média (lógica verificada; tempos reais não medidos).

### [S3] Histórico lido inteiro duas vezes a cada abertura da tela, sem limite de tamanho
- Área: desempenho
- Onde: `app/desktop/history_store.py:80-113`, `app/desktop/bridge_core.py:941-946`, `bridge_core.py:345`
- O que acontece: `loadHistory` chama `list_all(200)` (lê o arquivo todo) e `stats()` (lê o arquivo todo de novo).
  `history.jsonl` só cresce; a rotação de `cleanup_old_files` não o inclui.
- Impacto no usuário: hoje imperceptível (24 KB); piora com meses de uso.
- Correção sugerida: uma leitura só, com estatísticas incrementais ou rotação por tamanho.
- Confiança: alta.

### [S3] Gate vermelho com o redesenho local
- Área: testes
- Onde: `app/scripts/smoke_code_agent.py:3219-3221`
- O que acontece: o smoke procura a string `SettingsView` no `App.tsx`. O redesenho levou Configurações para o
  `HarnessView`.
- Correção sugerida: quando o redesenho entrar, checar o comportamento (rota `settings` + `Ctrl+,`) em vez do nome
  do componente.
- Confiança: alta.

### [S4] Gravações sem atomicidade
- Área: confiabilidade
- Onde: `app/desktop/bridge_core.py:770-784` (`setIntroSeen` com `write_text` direto, exceções engolidas);
  `app/core/session.py:268` (todo `save` usa o mesmo `<id>.tmp`: dois saves simultâneos da mesma conversa podem
  colidir no `os.replace`)
- Impacto: raro; perda de preferência de introdução ou erro silencioso ao gravar.
- Correção sugerida: `core/atomic_io.py` (já existe) nos dois.
- Confiança: alta (código).

## 3. Hipóteses a confirmar

- **O gate pode escrever no histórico real.** `desktop/data/history.jsonl` e `logs/actions.jsonl` mudaram às 10:30,
  no fim da rodada do gate. Não li os arquivos (estado local fora do escopo). Para confirmar: rodar o gate e comparar
  o tamanho antes e depois, ou procurar nos testes escrita sem `tmp` em `history_store.HISTORY_FILE` ou
  `action_logger.LOG_FILE`.
- **A flag `--restricted` pode não existir no Claude Code.** `core/coding_agents.py:195-196` passa `--restricted`,
  e não reconheço essa flag na CLI. Se ela não existir, todo `/claude` sem acesso total falha. Para confirmar:
  `claude --help` na máquina do dono (a CLI não está no PATH do Git Bash).
- **Repetir `uia_type` ou `vision_type` pode digitar duas vezes.** `controller.py:861-866` repete
  `uia_type`/`vision_type` quando falham. Se a primeira tentativa digitou e só a conferência falhou, o texto sai
  duplicado. Para confirmar: teste com `InteractionLayer` simulado.
- **Enter no texto digitado.** O fallback de `_type_text` (`pyautogui.write`) e o de `_vision_type`
  (`pyautogui.press(ch)`) mandam `\n` como Enter: num app de mensagem, isso envia sem passar por `hotkey_risk`. Só
  acontece se a área de transferência falhar.
- **Interface presa em "executando".** Se o WebSocket cair no meio de uma tarefa, a interface pode ficar `busy` para
  sempre: só `executionFinished` limpa o estado. Para confirmar: ver se o `onStatus('closed')` reseta o `taskStore`.
- **Voz ao vivo** (barge-in, eco, promessa de ação não feita): não avaliada; exige `smoke_live_voice.py`, que é pago.

## 4. Mapa de riscos por módulo

| Módulo | Complexidade | Cobertura | Risco | Nota |
| --- | --- | --- | --- | --- |
| `desktop/controller.py` | alta (1067 linhas, `_run` com ~600) | média | alto | Estado compartilhado (`session`, `engine`) entre a thread da tarefa e a da resposta. |
| `core/automation.py` | alta (1455) | média | alto | Portas de efeito desiguais por ação (`vision_click` confere, `click`/`vision_smart` não). |
| `desktop/voice.py` | alta (981, muitas threads e timers) | média (avaliação paga) | alto | Fila com `RLock`, timers e dependência da tela para executar. |
| `core/action_risk.py` | média | boa | médio | Bem pensado; depende do rótulo correto vindo de quem chama. |
| `core/plan_validator.py` | média | boa | médio | Não cobre ações sem rótulo confiável. |
| `desktop/server.py` | baixa | boa (contrato congelado) | baixo | `hello` mesmo sem núcleo é o único ponto fraco. |
| `desktop/bridge_core.py` | média (946) | média | médio | Muitos `except: pass` em preferências. |
| `core/session.py` | baixa | média | alto | Simples, mas sem dono claro entre threads. |
| `desktop/history_store.py` | baixa | baixa | baixo | Cresce sem limite. |
| `ui/src/lib/core.ts` | baixa | boa | baixo | Timeout único para tudo. |
| `ui/src/lib/taskStore.ts` | média | boa (7 testes) | médio | `busy` só sai com `executionFinished`. |
| `scripts/smoke_code_agent.py` | alta (160 KB) | — | médio | Checagens por string no código-fonte quebram em refatorações. |

## 5. Plano sugerido (maior retorno primeiro)

1. Corrida da conversa: capturar a sessão e gravá-la antes da resposta — **P**
2. `click` com `_effect_at_point`; tirar `vision_smart` do DESKTOP e `click`/`run_python` do prompt — **P**
3. Atalho de captura de tela como ação declarativa — **P**
4. `attach_core` com erro visível e `hello` só com o núcleo pronto — **P/M**
5. Timeout por chamada no `CoreClient` (diálogos com 10 min) — **P**
6. Confirmar `--restricted` no Claude Code — **P**
7. Conferir se o gate escreve no histórico real; isolar `HISTORY_FILE`/`LOG_FILE` nos testes — **P**
8. Voz: o núcleo executa direto, ou a interface responde ao `voiceCommand` — **M**
9. Ajustar o smoke de navegação ao redesenho e trocar checagens por string por comportamento — **M**
10. Dividir `_run` do controller (resolver, planejar, executar subtarefa, finalizar) e `smoke_code_agent.py` — **G**

## 6. O que não foi avaliado

- Fluxos que chamam modelo pago (Maestro real, voz ao vivo, `eval_*.py`): não rodados, por regra.
- Interface visual (contraste sobre papéis de parede, teclado, leitor de tela, escala 125%/150%): o redesenho está em
  andamento em outro software, então avaliar agora seria medir algo que vai mudar.
- Janela sem moldura (arrastar, encaixar, redimensionar) e desfoque na GPU: precisam de teste manual.
- `followup.py`, `maestro.py`, `understand.py` e `live_session.py` foram lidos só por cima: não há achado verificado
  neles nesta rodada.
- Conteúdo de `desktop/data/` e `memory/`: fora do escopo por regra do repositório.
