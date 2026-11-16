# Arquitetura do Creative AIx

Estado em 2026-11-15 (versão `0.1.0-internal`). Um app só: `python app/main.py`.

## Visão geral

```
python.exe (Qt / PySide6)
├─ desktop/web_host.py ── janela principal (sem moldura) + mini chat, QtWebEngine, esquema app://
│     página: ui/dist (React)  ──ws://127.0.0.1:<porta> (token por execução, JSON-RPC 2.0)──┐
├─ desktop/server.py ── EventServer (asyncio, thread própria) + Dispatcher (métodos permitidos)  │
├─ desktop/bridge.py ── Bridge(QObject, BridgeCore): Signals Qt + métodos de janela ◄─────────────┘
│     desktop/bridge_core.py ── a lógica dos métodos, sem Qt
├─ desktop/controller.py ── executa um pedido: resolve a conversa, planeja, valida, roda, observa
│     agents/maestro.py → agents/*_agent.py → core/automation.py (motor de ações)
├─ desktop/voice.py ── voz: gravação, conversa ao vivo (GPT-Live), entendimento, fila de pedidos
└─ desktop/window_mode.py + core/voice/hotkey.py ── mini chat e atalhos globais
```

## Fluxo de um pedido

1. **Interface** (`ui/src`) chama `executeTask` pelo WebSocket. Fala transcrita chega como evento `voiceCommand` e a
   interface chama o mesmo método.
2. **Controller** resolve a conversa (`core/followup.py`: continuação, resposta a pergunta pendente, pedido novo),
   tenta atalhos sem modelo (`existing_targets`, `extcode_agent`, `vault_plan`, `continue_plan`) e só então o Maestro.
3. **Políticas em código** validam o plano antes de qualquer ação (`core/plan_validator.py`, `action_policy.py`,
   `action_risk.py`). Efeitos sensíveis (enviar, pagar, apagar, publicar) pedem confirmação.
4. **Agentes** geram passos; o motor (`core/automation.py`) executa: rotina determinística, depois UI Automation, e
   visão só como último recurso. Claude Code e Codex rodam como CLIs numa pasta escolhida (`core/coding_agents.py`).
5. **Observação** (`core/observer.py`) anota na sessão o que ficou aberto; o resultado volta à interface por eventos
   e ao segundo cérebro como lição/procedimento, só com aprovação.

## Estado e memória

| O quê | Onde | Observação |
| --- | --- | --- |
| Conversa (pedidos, alvos abertos, pergunta pendente) | `core/session.py` | `context_block()` = últimos 6 pedidos detalhados + `done_log()` com tudo o que foi feito |
| Histórico de execuções | `desktop/data/history.jsonl` | ignorado pelo git |
| Segundo cérebro | `vault/` (fábrica) + `Documentos/AI Farm Agent` (pessoal) | `core/brain_store.py`; escrita só na camada pessoal |
| Preferências e Harness | `core/user_settings.py`, `core/harness.py` | validados por esquema |
| Aparência | `app/design/theme.json` → `ui/src/styles/tokens.css` | contraste AA conferido no gate |

## Contrato da interface

- Métodos: `desktop/server.py` `RPC_METHODS` (os do BridgeCore) + `HOST_METHODS` (diálogos e janela, só no host Qt).
- Eventos: os Signals do Bridge, congelados em `app/tests/fixtures/bridge_contract.txt`.
- `ui/src/lib/contract.gen.ts` é gerado por `app/scripts/export_ui_contract.py` (CI confere com `--check`).
- O servidor só aceita a origem `app://ui` (e o Vite com `--dev`), exige o token no primeiro frame e só manda o
  `hello` quando o núcleo terminou de carregar.

## Inicialização

`web_host.run()`: instância única (mutex do Windows + servidor local) → servidor → janela com a abertura (~1 s) →
núcleo importado numa thread (`_CoreLoader`) → Bridge montado na thread da interface → `server.attach()` (~3–5 s).

## Segurança (resumo)

- Ações com efeito passam por políticas em código, não por prompt. Texto de páginas e arquivos é dado, nunca ordem.
- O app nunca lê nem repassa chaves das CLIs; usa a sessão que a pessoa já fez nelas. Variáveis com cara de segredo não
  chegam aos processos filhos (`core/process_runner.py`).
- Modo Desenvolvedor: a CLI muda só `ui/src/views|components|dev` numa worktree; gate verde e clique antes de aplicar.
- Detalhes: [SECURITY.md](../../SECURITY.md), [security-review.md](../security-review.md).

## Dívidas conhecidas

- `Bridge.setTitleBarColor` e `desktop/titlebar.py` ficaram sem efeito com a janela sem moldura; continuam no contrato.
- `smoke_code_agent.py` é um arquivo único de 160 KB com muitos cenários; merece ser dividido em testes por área.
- A execução por voz ao vivo (GPT-Live) é validada por avaliação de entendimento (`scripts/eval_voice.py`), não por
  teste de ponta a ponta com execução real.
