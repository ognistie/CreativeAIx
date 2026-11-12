# Modo Desenvolvedor (E3)

Entrega E3 de [coding-agents-and-studio-prompt.md](coding-agents-and-studio-prompt.md). Tudo fica em
Harness > Desenvolvedor; cada nível tem uma chave própria.

| Nível | O que muda | Onde | Proteção |
|---|---|---|---|
| 1 — Ajustes sem código | Saudação e dica da tela inicial (além de cor, paleta, tema, cantos e telas, que já existiam) | `core/harness.py` → `dev.greeting`, `dev.hint` | Esquema com limites; versões e desfazer do Harness |
| 2 — Extensões declarativas | Atalhos de tarefa (chips) e cartões da tela inicial em JSON: nome, ícone, pedido em linguagem natural | `dev.shortcuts`, `dev.cards` (até 8 cada) | Só viram pedidos normais, que passam pelo Maestro e pelas políticas; nada executa código novo |
| 3 — Mudança de código | O Claude Code ou o Codex (E1) altera QML numa worktree git separada | `core/dev_mode.py`, `Bridge.devPropose/devCheck/devAct` | Lista fixa de pastas, gate verde, aprovação explícita, merge sem fast-forward, revert em um clique |

## Nível 3, passo a passo

1. **Propor**: `git worktree add -b dev/<id> <fora do repo>/.ai-farm-agent-dev/<id>`; a CLI roda na pasta
   `ai-farm-agent` da worktree (o adaptador de E1 recusa a pasta do app de verdade, e a worktree fica fora dela).
2. **Conferência em código** (`path_violation`): todo caminho tocado precisa estar em `desktop/qml/views`,
   `desktop/qml/components` ou `desktop/qml/dev` e ser `.qml`, `.js` ou `.md`. `core/action_risk.py`,
   `core/action_policy.py`, `core/plan_validator.py`, `core/process_runner.py`, `main.py`, `desktop/bridge.py`,
   `config.yaml` e qualquer arquivo com cara de credencial reprovam a proposta inteira, e a worktree é removida.
3. **Diff** mostrado na tela (stat + diff completo, até 200 KB).
4. **Verificar**: `scripts/smoke_ui.py` e `scripts/check_release.py --code-only` rodam na worktree, num Job Object,
   com o interpretador do app. O resultado fica vinculado à árvore Git mostrada no diff e ao seu commit pai.
5. **Aplicar**: cria o commit com a árvore verificada e faz o merge pelo hash desse commit. Qualquer edição
   na worktree após a revisão exige uma nova proposta. A worktree sai e a branch fica.
6. **Desfazer**: `git revert -m 1` do commit de merge.

Estado das propostas em `ai-farm-agent/memory/dev_mode.json` (fora do git).

## Verificação

`tests/test_dev_mode.py`: esquema dos níveis 1 e 2 (limites, ícones inválidos, itens sem texto, máximo de 8);
regras de caminho; num repositório git de brinquedo com agente falso: arquivo proibido ou fora das pastas recusa
a proposta e remove a worktree; sem gate não aplica; gate reprovado não aplica; aplicar gera merge sem fast-forward
com os arquivos no repositório; desfazer restaura o conteúdo anterior; falha e descarte limpam a worktree.

Não verificado nesta entrega: o fluxo de nível 3 com a CLI real (o Claude Code não tem sessão nesta máquina; o
Codex foi validado na E1 fora do modo Desenvolvedor).
