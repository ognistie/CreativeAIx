# Claude Code e Codex dentro do app (agente EXTCODE)

Entrega E1 de [coding-agents-and-studio-prompt.md](coding-agents-and-studio-prompt.md).

## O que faz

"Faz um README no projeto `C:\...\meu-site` com o Claude" ou "pede ao Codex para corrigir os testes":
o app chama a CLI oficial, já instalada e conectada pela pessoa, **só na pasta citada** (ou no projeto
aberto na conversa), mostra o andamento linha a linha e devolve um resumo com os arquivos novos,
alterados e removidos. Sem pasta no pedido nem na conversa, a resposta é uma pergunta.

## Peças

| Peça | Arquivo | Papel |
|---|---|---|
| Adaptadores | `core/coding_agents.py` | Descobre a CLI, confere a sessão, monta o comando, lê os eventos, compara a pasta antes/depois |
| Processo | `core/process_runner.stream_process` | Processo filho num Job Object (morre com o app, no Parar e no tempo limite), saída linha a linha, ambiente sem segredos |
| Agente | `agents/extcode_agent.py` | Plano de um passo `ext_code_task`, montado em código; atalho `extcode_plan` antes do Maestro |
| Política | `core/action_policy.py`, `core/plan_validator.py` (POL-010) | Só `ext_code_task`, só em pasta existente, nunca na pasta do próprio app |
| Motor | `core/automation.py` → `_ext_code_task` | Liga progresso e cancelamento do app ao adaptador |
| Configuração | `config.yaml` → `coding_agents` | Tempo limite, teto de custo, executáveis, pastas com acesso total |

## Comandos usados (versões conferidas pelo `--help` instalado)

- **Claude Code 2.1.321** (binário que o app Claude para Windows traz em `%APPDATA%\Claude\claude-code\<versão>\<hash>\claude.exe`, ou `claude` no PATH):
  `claude -p --output-format stream-json --verbose --permission-mode acceptEdits --max-budget-usd <teto> --restricted`,
  prompt pelo stdin. `--restricted` remove Bash/WebFetch e confina as ferramentas de arquivo à pasta de trabalho;
  `acceptEdits` aceita só edições nessa pasta. Sessão conferida com `claude auth status` (JSON `loggedIn`).
- **Codex 0.167** (`%LOCALAPPDATA%\OpenAI\Codex\bin\<hash>\codex.exe`, ou `codex` no PATH):
  `codex exec --json --color never --skip-git-repo-check --cd <pasta> --sandbox workspace-write`, prompt pelo stdin.
  Sessão conferida com `codex login status`.
- **Acesso total** (`coding_agents.full_access_projects`): só para pastas que a pessoa listou; tira o `--restricted` do
  Claude e usa `danger-full-access` no Codex. O app avisa no andamento quando está ligado.

## Regras

- O app nunca pede, lê, grava ou repassa chave ou token. O processo filho recebe só as variáveis de sistema
  (`USERPROFILE`, `APPDATA`, `PATH`...) e nenhuma com `KEY`, `TOKEN`, `SECRET`, `PASSWORD` ou `CREDENTIAL` no nome.
- Caminho fora da pasta nos eventos da CLI (Write/Edit do Claude, `file_change` do Codex) = falha, não sucesso.
- Pasta do próprio AI Farm Agent é recusada em três lugares (atalho, validador POL-010, motor). O modo Desenvolvedor (E3)
  entra por outra porta, com worktree e lista de pastas permitidas.
- O botão Parar e o atalho de parar cancelam pelo `should_stop` do motor; o Job Object derruba a árvore inteira.

## Verificação

- `tests/test_coding_agents.py`: CLI falsa que fala os dois formatos. Cobre pasta certa + progresso, cancelar mata
  o processo (batimento para), arquivo fora da pasta = falha, sem sessão = mensagem clara e nada roda,
  nenhum segredo chega ao filho, políticas (outros agentes não chamam `ext_code_task`; EXTCODE não roda outra coisa).
- Validação real (2026-11-10, autorizada): Codex criou `OLA.md` numa pasta descartável em 25 s, resultado verificado.
  O Claude Code embutido no app Claude respondeu `loggedIn: false` fora do app; é preciso entrar uma vez na CLI
  (`claude` → `/login`) para o AI Farm Agent usar a sessão.

## Servidor MCP de leitura (E1.5)

`ai-farm-agent/mcp_server.py` (stdio, JSON-RPC, sem dependências) expõe ao Claude Code e ao Codex cinco
ferramentas **só de leitura**: `brain_search`, `brain_read` (apenas `.md` do Cérebro, sem `..`), `task_status`,
`recent_tasks` e `list_projects`. Trechos com cara de chave são mascarados. Ligado por padrão
(`coding_agents.mcp` no config, e o interruptor em Configurações > Agentes de código, que vence o config):

- Claude: `--mcp-config {"mcpServers":{"aifarm":…}} --allowedTools mcp__aifarm` (só as ferramentas deste servidor
  dispensam pergunta).
- Codex: `-c mcp_servers.aifarm.command=… -c mcp_servers.aifarm.args=[…]`.

### Validação real (2026-11-10, autorizada)

- **Codex**: consultou `brain_search` do app e gravou um arquivo com os três títulos certos, verificado (26 s).
  A primeira tentativa achou um defeito do app: o Job Object das CLIs herdava o limite de 8 processos do worker de
  código, e o sandbox do Codex (helper de ACL + servidor MCP) não conseguia criar o 9º. Agora as CLIs rodam com 64
  processos e 4 GB; e um arquivo anunciado pela CLI que não existe no fim conta como falha (antes contava sucesso).
- **Claude Code**: sem login nesta máquina, mas com as flags exatas do app ele conectou ao MCP
  (`aifarm: connected`, 5 ferramentas), sem Bash (`--restricted`), e respondeu `Not logged in`, que o app traduz
  para a instrução de login.
