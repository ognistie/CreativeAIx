# Prompt — Nova interface Tauri 2 para o Creative AIx

Prompt para colar numa sessão do Claude Code aberta na raiz do repositório.
O trabalho é dividido em fases. Cada fase termina num ponto estável: o app abre, a CI passa, e dá para parar ali.

---

## Skills por fase

| Fase | Skills |
| --- | --- |
| 0. Leitura e plano | `investigate-first`, `full-stack-architect`, `tech-lead` |
| 1. Servidor de eventos em Python | `senior-software-engineer`, `safe-refactor`, `security-and-guardrails-engineer` |
| 2. Casca Tauri e protocolo | `senior-software-engineer`, `frontend-experience-engineer` |
| 3. Design system (de `Theme.qml` para tokens web) | `design-system-architect`, `premium-ui-designer`, `ui-ux-pro-max` |
| 4. Telas e mini chat | `frontend-experience-engineer`, `ux-product-designer`, `apple-design` (revisão) |
| 5. Empacotamento e desempenho | `performance-and-reliability-engineer`, `supply-chain-security` |
| Sempre, ao fechar cada fase | `verify-and-stop`, `/code-review` |

---

## Prompt

```text
Contexto
O Creative AIx (ver README.md) é um assistente multiagente para Windows. O núcleo é Python 3.11:
ai-farm-agent/core, ai-farm-agent/agents e o cofre AI-Farm-agents/. A interface atual é PySide6 + QML
(ai-farm-agent/desktop). A ligação entre núcleo e interface passa por três peças:
- desktop/event_bus.py: pub/sub thread-safe; o Controller publica eventos (phase, plan_ready, step_start,
  step_done, task_done, log, ...)
- desktop/controller.py: orquestra as execuções
- desktop/bridge.py: QObject que repassa os eventos para o QML como Signals e expõe @Slots ao QML

Objetivo
Criar uma nova interface em Tauri 2 + React + TypeScript (Vite, Tailwind, shadcn/ui, Framer Motion) que
converse com o núcleo Python rodando como sidecar. A meta é ter uma interface melhor e um desempenho
igual ou melhor que o atual. É uma melhoria, não uma reescrita: a estrutura existente continua
funcionando durante toda a migração.

Regras que não podem ser quebradas
1. Não alterar a lógica de ai-farm-agent/core, ai-farm-agent/agents nem o cofre AI-Farm-agents/.
   Mudanças no núcleo só para expor dados que já existem, sempre aditivas, e justificadas no PR.
2. A interface PySide6/QML continua sendo o padrão e continua funcionando até a nova ter paridade.
   A escolha entre as duas é feita por flag/config (ex.: `ui: qt | tauri` no config.yaml e
   `--ui tauri` no main.py), com padrão `qt`.
3. O contrato da interface é o que o Bridge já expõe: os Signals e @Slots de desktop/bridge.py.
   Não inventar outro. A nova camada é um espelho desse contrato pela rede.
4. A CI precisa continuar verde: `python ai-farm-agent/scripts/check_release.py --code-only`, testes em
   ai-farm-agent/tests e pip-audit. Testes novos entram em ai-farm-agent/tests.
5. Segurança: o servidor local escuta apenas em 127.0.0.1, em porta aleatória, e exige um token aleatório
   por sessão que o Tauri recebe na inicialização do sidecar. Validar a origem. As capabilities do Tauri
   ficam no mínimo: sem shell aberto, sem fs amplo. As políticas e validadores em Python continuam sendo
   a única autoridade sobre o que pode ser executado; a interface nunca contorna isso.
6. Nada de segredos no frontend. As chaves de API ficam no .env, lidas pelo Python.
7. Commits pequenos, um por passo lógico, com testes e com o app abrindo. Sem commits na main: trabalhar
   numa branch `feat/tauri-ui`.

Fases (parar e me mostrar o resultado ao fim de cada uma)

Fase 0 — Leitura e plano
- Ler desktop/bridge.py, controller.py, event_bus.py, window_mode.py, titlebar.py, voice.py, main.py e
  qml/Main.qml.
- Produzir docs/architecture/tauri-ui.md com:
  a) a tabela completa do contrato: cada Signal (nome, payload JSON de exemplo) e cada @Slot (nome,
     argumentos, retorno);
  b) o mapa tela a tela: views/*.qml e components/*.qml, e o componente React equivalente;
  c) os riscos e as decisões em aberto.
- Não escrever código nesta fase.

Fase 1 — Servidor de eventos (Python, aditivo)
- Criar ai-farm-agent/desktop/server.py: servidor WebSocket assíncrono que assina o EventBus e expõe
  os mesmos métodos dos @Slots em JSON-RPC 2.0 (request/response e notificações de evento).
- Reaproveitar a lógica do Bridge sem duplicá-la. Se for preciso, extrair para uma classe sem Qt, como
  BridgeCore, que o Bridge (Qt) e o server usam igualmente. O comportamento do Bridge não muda.
- Novo modo de execução headless: `python ai-farm-agent/main.py --ui tauri --headless` sobe só o núcleo
  e o servidor, imprime no stdout `{"port":..., "token":...}` e fica ouvindo.
- Testes: handshake com token, token inválido recusado, um evento do bus chegando ao cliente, e uma
  chamada de método com retorno.

Fase 2 — Casca Tauri
- Nova pasta na raiz: desktop-tauri/ (src-tauri em Rust + src em React/TS). Não mexer na estrutura atual.
- O Rust sobe o sidecar Python (em desenvolvimento, o venv; em release, o binário Nuitka), lê porta e
  token, repassa ao frontend e mata o sidecar ao fechar. Se o sidecar cair, mostrar o erro na UI e
  oferecer reiniciar.
- Cliente TS tipado gerado a partir da tabela do contrato (ex.: src/lib/bridge.ts), com reconexão.
- Janela principal com titlebar própria, como no titlebar.py atual, e Mica/acrylic no Windows 11.

Fase 3 — Design system
- Converter qml/components/Theme.qml em tokens (CSS variables + config Tailwind) com claro e escuro.
- Portar os componentes base: Button, IconButton, Chip, AppField, AppDialog, AppMenu, Segmented,
  TogglePill, Spinner, Skeleton, StatusDot, ToolTipHint, GlassPanel, EmptyState.
- A identidade atual se mantém (BrandMark, cores, tipografia Segoe UI Variable); o acabamento sobe.
  Acessibilidade: foco visível, contraste AA, navegação por teclado, prefers-reduced-motion.

Fase 4 — Telas e mini chat
- Ordem: TaskView (Composer, PlanCard, PhaseStepper, TaskOrb), depois o MiniChat, depois HistoryView,
  ActivityView, SettingsView, e por fim as demais (Brain, Library, Journal, Lab, Harness, You, About).
- O MiniChat deve repetir o comportamento de window_mode.py: janela separada, transparente, sempre no
  topo, no canto inferior direito; com tarefa rodando, não pega foco (focusable: false) e ignora o mouse
  (set_ignore_cursor_events). A janela principal sai da frente quando o agente vai para outro app.
- Ctrl+Alt+X para parar a tarefa de qualquer lugar, via plugin global-shortcut. Manter o atalho de
  entrada rápida que já existe no Bridge.
- Voz: a captura continua no Python (voice.py). A UI só mostra estado, nível (VoiceGlow) e transcrição
  a partir dos eventos voiceState/voiceLevel/voiceHeard.
- Ao fim de cada tela: checklist de paridade com a versão QML (mesmas ações, mesmos estados de vazio,
  carregando e erro).

Fase 5 — Empacotamento e desempenho
- Sidecar empacotado com Nuitka, instalador NSIS ou MSI pelo Tauri, auto-update com assinatura.
- Medir e registrar em docs/architecture/tauri-ui.md, comparando com a versão Qt: tempo até a primeira
  janela, RAM ociosa e com tarefa rodando, tamanho do instalador, latência entre um evento do bus e a
  tela. A nova interface não pode ser pior em nenhuma dessas métricas sem justificativa.
- Adicionar à CI um job que roda `npm ci`, lint, typecheck, testes do frontend e `cargo check`, sem
  remover nenhum passo existente.

Critério de pronto
- `--ui qt` funciona exatamente como antes. `--ui tauri` tem paridade de funcionalidades e métricas
  iguais ou melhores. CI verde. Docs atualizadas.
- Só depois disso, numa decisão separada que é minha, trocar o padrão para `tauri`.
  A remoção do QML não faz parte desta tarefa.
```
