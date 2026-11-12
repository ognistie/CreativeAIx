---
tipo: agente
agente: EXTCODE
tags: [agente, extcode]
cssclasses: [agent-code]
missao: "Chamar o Claude Code ou o Codex para trabalhar numa pasta de projeto escolhida pela pessoa."
cor: "#A78BFA"
playbooks: 0
skills: 0
---
# ExtCode Agent

> [!code] Missão
> Chamar o Claude Code ou o Codex (as CLIs oficiais, já conectadas pela pessoa) para trabalhar só na pasta de projeto que ela escolheu.

← [[Maestro]] · Políticas: [[Politicas de aceite]]

## Quando o Maestro chama
- "faz X no projeto Y com o Claude" / "pede ao Codex para corrigir os testes em Z"
- continuar, com um deles, no projeto que já está aberto na conversa
- sem pasta no pedido nem na conversa: pergunta qual pasta usar (nunca chuta)

## Regras de execução
- Um único passo `ext_code_task(tool, folder, prompt)`; a pasta vem do pedido ou da conversa, nunca do modelo (POL-010).
- A pasta precisa existir e nunca é a pasta do próprio AI Farm Agent (isso é o modo Desenvolvedor).
- O app nunca pede, lê, grava ou repassa chave ou token: usa a sessão da CLI; sem sessão, explica como entrar e para.
- Claude Code roda com `--restricted` (sem Bash, arquivos só na pasta) e `acceptEdits`; Codex com sandbox `workspace-write`.
- Arquivo tocado fora da pasta (pelos eventos da CLI) = falha, não sucesso.
- O processo vive num Job Object: morre com o app, no botão Parar, no atalho e no tempo limite.

## Como navegar e executar
- `core/coding_agents.py`: descobre a CLI, confere a sessão, roda com o prompt pelo stdin, lê os eventos linha a linha.
- Progresso: cada linha útil vai para a tela e para o registro de tarefas; o resultado traz o resumo e os arquivos novos/alterados/removidos.
