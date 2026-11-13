# Interface Tauri: contrato, mapa de telas e riscos (Fase 0)

> Status: Fase 0 (leitura e plano). Nenhum código foi alterado. O prompt de origem está em
> [prompt-migracao-tauri.md](prompt-migracao-tauri.md).

## 1. Como a interface fala com o núcleo hoje

```
core/ + agents/  ──>  desktop/controller.py  ──bus.emit──>  desktop/event_bus.py
                                                                  │ bus.on
                                                                  ▼
                       QML  <──Signal(str JSON)──  desktop/bridge.py (QObject)
                       QML  ──@Slot(...)─────────>  bridge.py ──> Controller / core
```

O que a leitura confirmou:

- **O núcleo não depende de Qt.** `core/` e `agents/` não importam PySide6; as duas ocorrências
  são strings de prompt. `controller.py`, `voice.py`, `history_store.py` e `event_bus.py` também
  são Python puro e só usam o `bus`.
- **Qt fica restrito a cinco arquivos:** `bridge.py`, `main.py`, `window_mode.py`, `titlebar.py`
  e `instance.py` (instância única via `QLocalServer`).
- **Os atalhos globais já são Python puro.** `core/voice/hotkey.py` usa `RegisterHotKey` do
  Win32 numa thread própria. `Ctrl+Alt+X` (parar), `Alt+Space` (acesso rápido) e o atalho de voz
  continuam funcionando sem Qt. **Decisão:** no modo Tauri eles continuam no Python. O plugin
  `global-shortcut` do Tauri não é usado para esses atalhos, porque registrar duas vezes faria
  o segundo registro falhar com "em uso".
- **Todo payload já é JSON.** Cada Signal leva uma string JSON; cada Slot recebe tipos simples e
  devolve string JSON ou `bool`. O contrato passa por WebSocket sem conversão de tipos.
- **Oito Signals não vêm do bus.** O Bridge os emite direto, de dentro dos próprios Slots ou de
  threads que ele abre: `conversationsChanged` (só em parte), `quickEntry`, `codingStatus`,
  `journalSummary`, `labProgress`, `labFinished`, `devChanged`, `creatorReady`. O servidor novo
  precisa dar a esses o mesmo caminho dos eventos do bus (ver §4).
- `runningChanged` é um estado derivado: vira `true` no primeiro `phase` e `false` em
  `execution_finished` (ou em `error` com o controller parado).

## 2. Contrato

### 2.1 Eventos (Signals)

O payload é o `dict` publicado no bus, serializado com `json.dumps(ensure_ascii=False, default=str)`.
Os formatos exatos estão em quem publica (`controller.py`, `voice.py`). A Fase 1 deve gerar os tipos
TS a partir de payloads reais capturados nos testes, não escrevê-los à mão.

| Signal (Qt) | Evento do bus / origem | Nome proposto no RPC | Observação |
| --- | --- | --- | --- |
| `phaseChanged` | `phase` | `phase` | também liga `runningChanged(true)` |
| `planReady` | `plan_ready` | `plan_ready` | |
| `stepStart` | `step_start` | `step_start` | |
| `stepDone` | `step_done` | `step_done` | pode trazer caminho de screenshot |
| `apiUsage` | `api_usage` | `api_usage` | |
| `contextExtracted` | `context_extracted` | `context_extracted` | |
| `taskDone` | `task_done` | `task_done` | |
| `executionFinished` | `execution_finished` | `execution_finished` | liga `runningChanged(false)` |
| `reportReady` | `report_ready` | `report_ready` | |
| `cancelled` | `cancelled` | `cancelled` | |
| `errorRaised` | `error` | `error` | encerra a execução se o controller estiver parado |
| `logEntry` | `log` | `log` | alto volume (ver §5) |
| `historyChanged` | `history_changed` | `history_changed` | |
| `resolved` | `resolved` | `resolved` | |
| `answerReady` | `answer` | `answer` | |
| `sessionReset` | `session_reset` | `session_reset` | |
| `voiceState` | `voice_state` | `voice_state` | |
| `voiceLevel` | `voice_level` | `voice_level` | alta frequência (ver §5) |
| `voiceHeard` | `voice_heard` | `voice_heard` | |
| `voiceCommand` | `voice_command` | `voice_command` | |
| `voiceReply` | `voice_reply` | `voice_reply` | |
| `voiceChat` | `voice_chat` | `voice_chat` | |
| `planReview` | `plan_review` | `plan_review` | carrega o `token` usado por `approvePlan` |
| `assistantMessage` | `assistant_message` | `assistant_message` | |
| `conversationsChanged` | `conversations_changed` + direto em rename/delete | `conversations_changed` | |
| `quickEntry` | direto (hotkey `Alt+Space`) | `quick_entry` | sem payload |
| `creatorReady` | direto (thread `creator`) | `creator_ready` | |
| `devChanged` | direto | `dev_changed` | |
| `codingStatus` | direto (thread) | `coding_status` | |
| `labProgress` | direto (callback do lab) | `lab_progress` | |
| `labFinished` | direto (thread) | `lab_finished` | |
| `journalSummary` | direto (thread) | `journal_summary` | |
| `runningChanged` | derivado | `running_changed` | `bool` |

### 2.2 Métodos (Slots)

Legenda da coluna Qt: **puro** = só chama Controller/core e pode ir como está para o
`BridgeCore`; **janela** = mexe em janela ou cursor e precisa de equivalente no Tauri.

**Execução e conversa**

| Slot | Args | Retorno | Qt | Telas |
| --- | --- | --- | --- | --- |
| `executeTask` | task: str, dry_run: bool, generate_report: bool | — | puro | TaskView |
| `forceStop` | — | — | puro | TaskView, MiniChat, Main |
| `newSession` | — | — | puro | TaskView |
| `approvePlan` | ok: bool, token: str | — | puro | TaskView |
| `approvePlanSteps` | token: str, skipped_json: str | — | puro | TaskView |
| `attachFiles` | payload: str (JSON lista de caminhos) | str | puro | Composer |
| `loadConversations` | — | str | puro | Main |
| `openConversation` | sid: str | str | puro | Main |
| `renameConversation` | sid: str, title: str | bool | puro | Main |
| `deleteConversation` | sid: str | bool | puro | Main |
| `loadHistory` | — | str | puro | HistoryView |
| `historyDetail` | task_id: str | str | puro | HistoryView |
| `activitySummary` | — | str | puro | ActivityView |

**Voz**

| Slot | Args | Retorno | Qt | Telas |
| --- | --- | --- | --- | --- |
| `voiceRecordToggle` | — | — | puro | TaskView, MiniChat |
| `voiceRecordCancel` | — | — | puro | TaskView, MiniChat |
| `setLiveConversation` | on: bool | — | puro | TaskView, MiniChat |

**Janela e aparência**

| Slot | Args | Retorno | Qt | Equivalente no Tauri |
| --- | --- | --- | --- | --- |
| `uiSettings` | — | str | puro | igual |
| `restoreMain` | — | — | janela | comando Rust `restore_main` |
| `closeMini` | — | — | janela | comando Rust `close_mini` |
| `mainActivated` | — | — | janela | evento `focus` da janela principal |
| `cursorPos` | — | list[int] | janela | `cursor_position()` do Tauri |
| `setTitleBarColor` | color: str | — | janela | titlebar própria em CSS, sem DWM |
| `appearance` | — | str | puro | igual |
| `introSeen` / `setIntroSeen` | — / key: str, seen: bool | str / — | puro | igual |
| `getSettings` / `saveSettings` | — / payload: str | str / str | puro | igual |
| `providerStatus` | — | str | puro | igual |
| `codingAgentsCheck` | — | — (responde por `coding_status`) | puro | igual |
| `openBrainFolder` | — | — | puro (`os.startfile`) | igual |

**Segundo cérebro, Você e sugestões**: todos puros e com retorno `str` JSON `{ok, error?}`.
`brainOverview`, `brainRead(rel)`, `brainSave(rel, text)`, `brainCreate(rel, text)`,
`brainCreateFolder(rel)`, `brainRename(old, new)`, `brainDelete(rel)`, `brainRestore(rel)`,
`brainSearch(query)`, `brainGraph`, `youProfile`, `youSave(section, text)`, `suggestionsList`,
`suggestionApprove(sid, title, body)`, `suggestionDismiss(sid)`.

**Harness, criador, dev e papéis de parede**: todos puros. `harnessGet`,
`harnessSave(payload, label)`, `harnessRestore(version_id)`, `agentProfile(agent)`,
`creatorPropose(text)` (responde por `creator_ready`), `creatorApply(pid)`, `creatorDiscard(pid)`,
`devPropose(request, tool)`, `devCheck(pid)`, `devList`, `devDiff(pid)`, `devAct(pid, action)`,
`wallpapersList`, `wallpaperInfo(wallpaper)`, `wallpaperImport(url)`, `wallpaperRemove(wallpaper)`.

**Diário**: todos puros. `journalList(query, tag, day)`, `journalFolders`,
`journalListIn(folder, query, tag, day)`, `journalGet(id)`, `journalSave(payload)`,
`journalSetPrivate(id, private)`, `journalDelete(id)`, `journalDates`,
`journalSummarize(id)` (responde por `journal_summary`), `journalUseInBrain(on)`.

**Lab e Biblioteca**: todos puros. `labVersions(agent)`, `labCreateVariant(payload)`,
`labDiff(a, b)`, `labPublish(id)`, `labEvalSets`, `labRuns`, `labRunDetail(id)`, `labSkills(agent)`,
`labToolTest(name, args_json)`, `labObserve(agent, state)`, `labRun(payload)` (progresso por
`lab_progress`/`lab_finished`), `labFeedback(payload)`, `labPromotionCheck(id)`, `labPromote(id)`,
`labTraining`, `labResearch(payload)`, `labCancel`, `librarySearch(query, level, kind)`.

Total: 83 nomes distintos `Bridge.*` usados no QML (Slots + handlers de Signal).

## 3. Mapa de telas

Linhas de QML hoje: 10.607. A ordem segue a Fase 4 do prompt.

| QML | Linhas | Componente React | Slots usados | Prioridade |
| --- | --- | --- | --- | --- |
| `Main.qml` (shell, sidebar, conversas) | 665 | `app/Shell.tsx`, `Sidebar.tsx` | conversas, `uiSettings`, `setTitleBarColor`, janela | 1 |
| `views/TaskView.qml` | 1119 | `views/Task.tsx` | execução, voz, plano | 1 |
| `components/Composer.qml` | 507 | `components/Composer.tsx` | `attachFiles` | 1 |
| `components/PlanCard.qml`, `PhaseStepper.qml`, `TaskOrb.qml` | 135 / – / 235 | `PlanCard.tsx`, `PhaseStepper.tsx`, `TaskOrb.tsx` | eventos | 1 |
| `components/MiniChat.qml` | 500 | janela `mini` + `views/MiniChat.tsx` | voz, `forceStop`, `cursorPos` | 2 |
| `views/HistoryView.qml` | 300 | `views/History.tsx` | `loadHistory`, `historyDetail` | 3 |
| `views/ActivityView.qml` | 323 | `views/Activity.tsx` | `activitySummary` | 3 |
| `views/SettingsView.qml` | 428 | `views/Settings.tsx` | settings, provider, coding | 3 |
| `views/BrainView.qml` (+ `NoteMap`, `FolderCard`) | 939 | `views/Brain.tsx` | brain*, suggestion* | 4 |
| `views/HarnessView.qml` | 1278 | `views/Harness.tsx` | harness*, creator*, dev*, wallpaper* | 4 |
| `views/JournalView.qml` | 511 | `views/Journal.tsx` | journal* | 4 |
| `views/LabView.qml` | 397 | `views/Lab.tsx` | lab* | 4 |
| `views/LibraryView.qml` | 313 | `views/Library.tsx` | `librarySearch` | 4 |
| `views/YouView.qml` | 194 | `views/You.tsx` | `youProfile`, `youSave` | 4 |
| `views/AboutView.qml` | 173 | `views/About.tsx` | — | 4 |
| `components/Splash*.qml` | 146 + | `Splash.tsx` (enquanto o sidecar sobe) | — | 2 |
| `components/Ambient.qml`, `ShaderWallpaper.qml` | 163 + | `Ambient.tsx` (CSS/WebGL) | — | 3 |
| Base: `Button`, `IconButton`, `Chip`, `AppField`, `AppDialog`, `AppMenu(Item)`, `Segmented`, `TogglePill`, `Spinner`, `Skeleton`, `StatusDot`, `ToolTipHint`, `GlassPanel`, `EmptyState`, `Icon`, `NavItem`, `PageHeader`, `ScrollPage`, `KeyValue`, `Eyebrow`, `ChoiceTile`, `IntroCard`, `CommandPalette`, `VoiceGlow`, `BrandMark`, `Enter` | – | `components/ui/*` (shadcn/ui + tokens) | — | Fase 3 |

## 4. Decisões propostas para a Fase 1

1. **Extrair `BridgeCore` sem Qt** (`desktop/bridge_core.py`). Ele recebe a lógica dos Slots
   puros e emite eventos por um callback `emit(name, payload)`. O `Bridge` (Qt) passa a delegar
   a ele e converte `emit` em Signals. Assim o comportamento do Qt não muda e não há duplicação.
   Esse é o único refactor dentro do código existente, e é coberto por testes antes e depois.
2. **Os Signals diretos passam pelo mesmo `emit`**: `BridgeCore` publica `creator_ready`,
   `lab_progress` e os outros, e tanto o Bridge Qt quanto o servidor WebSocket assinam.
3. **`desktop/server.py`**: WebSocket com JSON-RPC 2.0. Os métodos têm o mesmo nome dos Slots
   (`executeTask`, `brainRead`...), e os eventos vão como notificações
   `{"jsonrpc":"2.0","method":"event","params":{"name":..., "payload":...}}`. Escuta em
   `127.0.0.1`, porta 0 (aleatória), com token de 32 bytes exigido no primeiro frame e verificação
   do header `Origin` (`tauri://localhost` / `http://tauri.localhost`).
4. **Biblioteca**: usar `websockets` (asyncio, sem dependências nativas) numa thread com o próprio
   event loop. A dependência entra no `requirements.txt` e no lock, e passa pelo `pip-audit` da CI.
5. **Modo headless**: `main.py --ui tauri --headless` não importa PySide6, sobe o `BridgeCore` e o
   servidor, imprime uma linha `{"port":..,"token":..}` no stdout e mantém os atalhos globais em
   Python. Os Slots de janela viram eventos para o Tauri (`window_request` com
   `restore_main` | `close_mini` | `enter_mini` | `quick_entry`).
6. **Mini chat sai de `window_mode.py` e vai para o Rust.** A detecção de "o agente foi para outro
   app" (`foreign_foreground`) fica no Python, que publica `window_request: enter_mini`. Posicionar,
   não pegar foco, ignorar o mouse e excluir da captura (`SetWindowDisplayAffinity`) ficam no Rust.
7. **Instância única no headless**: `QLocalServer` não existe sem Qt. Proposta: o plugin
   `single-instance` do Tauri na casca, e um mutex nomeado do Win32 no sidecar.
8. **Tokens de design**: `Theme.qml` continua sendo a fonte única, porque `scripts/check_contrast.py`
   mede o AA lendo esse arquivo. Um script (`scripts/export_theme_tokens.py`) gera
   `desktop-tauri/src/styles/tokens.css` a partir dele, e a CI confere se o arquivo gerado está em dia.

## 5. Riscos

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Refactor do Bridge quebrar o QML | alto | testes de contrato no Bridge antes de mexer; extração mecânica; `--ui qt` validado manualmente a cada passo |
| `voice_level` e `log` em alta frequência saturarem o WebSocket/React | médio | throttle de `voice_level` no servidor (~30 Hz); `log` em lote a cada 100 ms; renderização fora do estado global |
| Atalho registrado duas vezes (Python e Tauri) | médio | atalhos só no Python (§1) |
| Foco roubado pelo mini chat durante a tarefa | alto (o agente digita no app errado) | `focusable: false` + `WS_EX_NOACTIVATE` no Rust; teste manual com o Bloco de Notas recebendo digitação |
| Porta local acessível por outro processo do usuário | médio | token por sessão + Origin + só loopback; nenhum Slot dá acesso a algo que o QML já não tenha |
| Sidecar Python lento para subir (whisper, imports) | médio | splash na casca; imports pesados já são preguiçosos no Bridge (voz carrega 4 s depois) |
| Empacotar Python com Nuitka (faster-whisper, piper, pywin32) | alto | spike isolado na Fase 5; o instalador atual (venv + `iniciar.cmd`) continua valendo |
| Duas UIs para manter durante a migração | médio | contrato único (`BridgeCore`); o QML não ganha funcionalidade nova enquanto houver migração |

## 6. Decisões (fechadas em 2026-11-13)

1. **Frontend: React 18 + TypeScript + Vite**, com Tailwind, shadcn/ui (Radix) e Framer Motion.
   Ecossistema maior para os componentes que o projeto usa (diálogo, menu, paleta de comandos,
   markdown, grafo de notas).
2. **WebSocket: `websockets`.** Puro Python, asyncio, sem dependência nativa. Combina com o resto
   das threads do núcleo e não puxa um framework web inteiro como o `aiohttp`.
3. **Mini chat: redesign a partir do atual.** Mesmo comportamento (canto inferior direito, sem foco,
   ignora o mouse durante a tarefa, orbe, voz, parar) e a mesma identidade visual, com o acabamento
   novo do design system.
4. **Rust e Node: requisitos só de desenvolvimento da interface.** O `scripts/setup.ps1` ganha um
   modo opcional (`-WithTauri`) que confere `node`, `npm` e `cargo` e instala as dependências de
   `desktop-tauri/`. Quem só usa o app continua sem precisar de nenhum dos dois.

## 7. Fase 1 — feito

O que mudou em relação à proposta do §4:

- **Eventos usam o nome do Signal** (`planReady`, `voiceLevel`...), não os nomes `snake_case` da
  coluna "Nome proposto" do §2.1. Assim o QML e o React falam o mesmo vocabulário, e o teste de
  contrato compara um com o outro diretamente.
- **`BridgeCore` é um mixin**, não um objeto que o Bridge guarda (`Bridge(QObject, BridgeCore)`).
  O estado fica em `self`, então `scripts/smoke_ui.py`, `capture_ui.py` e `sandbox_escape_check.py`,
  que montam o Bridge com `__new__`, continuam funcionando sem mudança. O `BridgeCore` não tem
  `__init__` (a preparação fica em `_setup_core()`), porque o `QObject.__init__` é cooperativo e
  chamaria esse init pela MRO.

Arquivos:

| Arquivo | O que é |
| --- | --- |
| `desktop/bridge_core.py` | a lógica dos Slots, sem Qt, gerada mecanicamente a partir do `bridge.py` original |
| `desktop/bridge.py` | Signals, `@Slot`s que repassam para o core e o que é de janela Qt (mini chat, titlebar, cursor) |
| `desktop/server.py` | `Dispatcher` (JSON-RPC com aridade e tipos conferidos), `EventServer` (WebSocket), `HeadlessBridge`, `serve_headless` |
| `main.py` | `--ui qt\|tauri`, `--headless`, `--dev`; padrão vem de `ui.shell` no `config.yaml` (`qt`) |
| `tests/fixtures/bridge_contract.txt` | as 125 assinaturas Qt do Bridge, congeladas antes da extração |
| `tests/test_bridge_contract.py` | Qt inalterado, RPC = Slots públicos, eventos = Signals, core sem Qt |
| `tests/test_event_server.py` | token, silêncio, Origin, tipos, eventos, throttle de `voiceLevel`, linha de handshake |

Handshake do modo headless: uma única linha no stdout,
`CREATIVE_AIX_READY {"port": .., "token": .., "protocol": 1}`. Todo o resto vai para `logs/app.log`,
então o token nunca é gravado em log. Quando a casca fecha o stdin, o núcleo encerra.

Medido no smoke (`main.py --ui tauri --headless` real): handshake em 4,7 s, `providerStatus`,
`uiSettings`, `loadConversations` e `librarySearch` respondidos pelo WebSocket, e saída limpa (código 0)
ao fechar o stdin.

Pendente para a Fase 4: `foreign_foreground()` (`window_mode.py`) compara com o PID do próprio
processo. No modo Tauri as janelas são de outro processo, então o sidecar precisa receber o PID da
casca (variável de ambiente) para decidir quando pedir `windowRequest: enter_mini`.

## 8. Fase 2 — feito (Rust ainda sem compilar)

- `desktop-tauri/`: Tauri 2 + React 18 + TS + Vite 6 + Tailwind 4. Duas janelas: `main`, sem moldura e
  com titlebar própria, e `mini`, transparente, sempre no topo, fora da barra de tarefas, sem pegar
  foco e oculta até a Fase 4.
- `src-tauri/src/sidecar.rs`: sobe `main.py --ui tauri --headless` (com `--dev` em debug) sem janela
  de console, lê a linha `CREATIVE_AIX_READY`, guarda as últimas 20 linhas de stderr para mostrar se
  o núcleo cair, reinicia e encerra (fecha o stdin e mata depois de 5 s). Passa
  `CREATIVE_AIX_SHELL_PID` para a Fase 4.
- Comandos Rust: `core_info` (espera o anúncio, até 60 s) e `restart_core`. Instância única pelo
  plugin `single-instance`.
- CSP: `connect-src` só para `ws://127.0.0.1:*`. Capabilities mínimas, sem shell e sem fs.
- `src/lib/core.ts`: cliente JSON-RPC tipado pelo `contract.gen.ts`. Espera a conexão abrir, casa
  as respostas por id, tem timeout por chamada e reconecta com backoff pedindo porta e token de novo
  (o núcleo reiniciado tem um token novo). 7 testes (vitest).
- `scripts/export_tauri_contract.py` gera os tipos TS a partir do Python. `--check` roda na CI e em
  `tests/test_bridge_contract.py`.
- CI: novo job `tauri-ui` (contrato, `npm ci`, typecheck, testes, build e `cargo check`).
- `scripts/setup.ps1 -WithTauri` confere `node`, `npm` e `cargo` e roda `npm ci`.

**Compilação:** `cargo check` passou na CI (job `tauri-ui`, Windows). O `Cargo.lock` está commitado
e a CI usa `--locked`. Nesta máquina o Rust e o Build Tools estão instalados, mas o Controle
Inteligente de Aplicativos do Windows bloqueia os scripts de build sem assinatura que o cargo gera
(os error 4551). Por isso a casca ainda não foi aberta localmente (`npm run tauri dev`): só compila
pela CI até o bloqueio ser resolvido.

## 9. Fase 3 — feito

- `scripts/export_theme_tokens.py` lê o `Theme.qml` com o mesmo parser do `check_contrast.py` e gera
  `desktop-tauri/src/styles/tokens.css`: os dois temas, as 13 paletas (escuro e claro), espaçamento,
  raios com escala, tipografia e durações. Também gera `src/lib/icons.gen.ts` com os 60 desenhos do
  `Icon.qml`. O `Theme.qml` continua sendo a fonte única e o AA medido nele (442 medidas) vale para as
  duas interfaces. `--check` roda na CI e em `tests/test_bridge_contract.py`.
- A aparência salva no Harness (`Bridge.appearance`) vira atributos no `<html>` (`data-theme`,
  `data-palette`, `data-radius`, `data-motion`) e a variável `--accent`, com a mesma validação do
  `Theme.applyAppearance`.
- Componentes base em `src/components/ui/`, com Radix por baixo no padrão shadcn/ui (cva +
  tailwind-merge): `Button`, `IconButton`, `Chip`, `TogglePill`, `Segmented`, `Field`, `Spinner`,
  `Skeleton`, `StatusDot`, `EmptyState`, `GlassPanel`, `AppDialog`, `AppMenu`, `Hint`, `Icon`. Foco
  visível, teclado e leitor de tela vêm do Radix. O `StatusDot` sempre mostra ícone junto da cor.
  Movimento respeita `data-motion="off"` e `prefers-reduced-motion`.
- Galeria em `#galeria` (`npm run dev` e abrir `http://127.0.0.1:1420/#galeria`): todos os
  componentes nos dois temas, nas paletas e nos três estilos de canto, sem precisar do núcleo.
- Mudança em relação ao QML: o botão `danger` usa fundo translúcido com texto na cor de perigo, porque
  texto branco sobre `#FF6B5F` não chega a 4.5:1.

## 10. Fase 4 — parte 1 (tarefa, mini chat, histórico, configurações)

- `src/lib/taskStore.ts`: o estado da TaskView.qml como reducer puro, com os mesmos eventos e as mesmas
  regras (arquivar o pedido anterior, perguntas e limitações, revisão do plano, notas só de avisos e
  erros durante a execução). 7 testes.
- Shell (`App.tsx`): barra lateral com navegação, conversas (abrir, renomear, apagar), busca e os
  atalhos do QML (Ctrl+N, Ctrl+H, Ctrl+B, Ctrl+, , Ctrl+\, Esc para parar).
- Tela de Tarefa: saudação e sugestões, Composer (Enter envia, Simular, Relatório, Conversa,
  microfone com nível e tempo), conversa anterior, etapas, plano, passos ao vivo, revisão do plano,
  resultado com arquivos criados, uso e custo.
- Histórico (resumo, filtros, busca, passos e evidência de cada execução) e Configurações (núcleo e
  provedores, instruções, execução, voz, Claude Code/Codex, interface, atalhos).
- Mini chat com redesign a partir do atual:
  - Python: `desktop/foreground.py` (sem Qt) sai de `window_mode.py`; o `HeadlessBridge` observa o
    primeiro plano durante a tarefa e pede `windowRequest: enter_mini` uma vez por execução,
    contando o PID da casca como nosso.
  - Rust (`src-tauri/src/mini_window.rs`): mostrar sem ativar (`SW_SHOWNOACTIVATE` +
    `WS_EX_NOACTIVATE`), ignorar cliques durante a tarefa, minimizar a principal sem ativar, posição no
    canto da área de trabalho, acesso rápido com foco.
  - A principal manda o estado da tarefa ao mini chat por evento Tauri e recebe dele os pedidos.
- Modo demonstração (`?demo`, também em `mini.html?demo`): núcleo falso para revisar as telas no
  navegador, sem Python. Usado para conferir a tela de Tarefa, o Histórico, as Configurações e o mini
  chat.

Pendente na Fase 4: Atividade, Cérebro, Você, Diário, Biblioteca, AI Research Lab, Harness e Sobre
(mostram um aviso de "ainda só na interface Qt"); anexar arquivos no Composer (precisa do diálogo de
arquivos do Tauri); a paleta de comandos (Ctrl+K). O comportamento real das janelas (foco, cliques,
posição) só pode ser conferido com a casca aberta, o que nesta máquina depende do Smart App Control.

## 11. Próximo passo

Fase 4, parte 2: as telas restantes, na ordem Atividade, Cérebro, Diário, Harness, Lab, Biblioteca,
Você e Sobre.
