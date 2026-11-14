# Prompt de desenvolvimento — Claude Code e Codex dentro do AI Farm Agent, modo Desenvolvedor e novo visual (v1)

> Para: Claude Fable 5.1 (`claude-fable-5-1`), trabalhando no repositório `AI-Farm-Agent`.
> Leia este documento inteiro antes de mudar qualquer arquivo. Ele é o contrato de trabalho e o critério de aceite.

---

## 1. Papel

Você é o engenheiro principal do AI Farm Agent, um app desktop Windows (Python 3.11, PySide6/QML) em que a
pessoa pede tarefas em linguagem natural (texto ou voz) e um Maestro distribui o trabalho entre agentes
(Web, Desktop, Code, Data, File). Você vai entregar quatro coisas, nesta ordem, sem regressão.

## 2. Contexto que você precisa conhecer (leia o código, não suponha)

- Entrada do app: `app/main.py` → `desktop/main.py` → `desktop/qml/Main.qml`; ponte Python↔QML em `desktop/bridge.py`.
- Execução: `desktop/controller.py` (resolve, Maestro, agentes, motor `core/automation.py`), registro durável `core/task_ledger.py`.
- Segurança já existente, que **não pode enfraquecer**: `core/action_policy.py` (ferramentas por agente),
  `core/action_risk.py` (porta de efeito em `enforce`, uma vez por tarefa), `core/plan_validator.py` (POL-000…009),
  `core/process_runner.py` (processos filhos em Job Object).
- Interface: tokens em `desktop/qml/components/Theme.qml` (paletas, acento, ambiente, fontes), fundo `Ambient.qml`,
  painéis `GlassPanel.qml`, ícones vetoriais `Icon.qml`, telas em `desktop/qml/views/`.
- Personalização do usuário: Harness validado por esquema em `core/harness.py` (com versões e desfazer), camada
  pessoal fora do repositório em `core/brain_store.py`.
- Documentos de referência: `docs/architecture/second-brain.md`, `voice-execution-bridge.md`, `evolution-baseline.md`.

## 3. Entregas

### E1. Agentes de código externos: Claude Code e Codex como agentes do app

**Objetivo:** a pessoa pede, dentro do AI Farm Agent, "faça X no projeto Y com o Claude" (ou "com o Codex"),
acompanha o andamento e recebe o resultado, sem sair do app.

**Desenho exigido (o mais simples que funciona):**
1. `core/coding_agents.py` — adaptadores para as CLIs oficiais já instaladas e autenticadas pela própria pessoa:
   - Claude Code em modo não interativo (`claude -p ... --output-format stream-json`), na pasta do projeto;
   - Codex CLI em modo não interativo (`codex exec ...`), na pasta do projeto.
   Descubra os executáveis e as flags exatas pela documentação oficial e pelo `--help` da versão instalada. Não invente flags.
2. Um agente novo `EXTCODE` (ou um modo do agente Code) registrado no Maestro, em `core/action_policy.py` e no `plan_validator`.
3. Execução pelo `process_runner` (processo filho morre com o app), com tempo limite, cancelamento pelo botão Parar e pelo
   atalho, e progresso transmitido linha a linha para a tela e para o registro de tarefas.
4. **Isolamento:** o agente externo só trabalha numa pasta de projeto que a pessoa escolheu (ou numa *worktree* git nova).
   Nunca na pasta do próprio AI Farm Agent fora do modo Desenvolvedor (E3). O resultado volta como diff + resumo.
5. **Opcional, só depois de E1.1–E1.4 aceitos:** um servidor MCP local (`app/mcp_server.py`, stdio) que expõe
   ferramentas *de leitura* do app ao Claude Code e ao Codex (consultar o Cérebro, o andamento das tarefas, a lista de
   projetos). Nenhuma ferramenta MCP executa ação no computador nesta versão.

**Regras:**
- Credenciais: o app **nunca** pede, lê, grava ou repassa chave de API ou token dessas ferramentas. Usa a sessão que a pessoa
  já fez na CLI. Se não houver sessão, mostra como entrar e para.
- O que essas CLIs fizerem fora da pasta autorizada é falha, não sucesso: confira o estado final (arquivos alterados só dentro da pasta).
- Respeite as permissões das próprias CLIs; não use flags que pulem todas as confirmações sem que a pessoa ligue isso
  explicitamente por projeto, com aviso claro.

### E2. Interface: app desktop sofisticado e futurista

**Referências (anexadas pela pessoa):** dois conceitos de app com vidro escuro sobre fotografia (barra lateral translúcida,
cartões de vidro, compositor central com ações, chips de atalho, botão flutuante com brilho). Use-as como **direção de arte**,
não copie layout, marca, textos ou ícones de terceiros.

**Direção:**
- Tema **escuro de vidro** como novo padrão, mantendo o claro atual como opção (o Harness já troca paletas e aparência).
- Vidro real sobre o papel de parede: desfoque do fundo atrás dos painéis (`MultiEffect`/`ShaderEffectSource`) com
  *fallback* sem shader para o renderizador por software (o smoke de QML roda sem GPU e precisa continuar passando).
- Hierarquia: barra lateral recolhível, cabeçalho com seletor de agente/modelo e ações, área central com saudação e compositor
  amplo, chips de ação e cartões de recurso (Cérebro, Você, Harness, Desenvolvedor).
- Microinterações discretas (hover, foco, entrada de cartões), respeitando "luzes paradas" e movimento reduzido.
- Contraste AA em todo texto sobre vidro (meça; escureça o vidro se a foto for clara).
- Tudo por tokens no `Theme.qml`; nenhuma cor solta nas telas.

### E3. Modo Desenvolvedor

**Objetivo:** a pessoa (ou o Claude/Codex a pedido dela) muda a plataforma de dentro dela, com segurança.

**Três níveis, nesta ordem, cada um atrás de uma chave no Harness:**
1. **Ajustes sem código (sempre seguros):** tokens visuais, ordem e visibilidade de telas, textos de introdução, atalhos,
   cartões da tela inicial. Validados por esquema (estenda `core/harness.py`), com versões e desfazer. Mudam ao vivo.
2. **Extensões declarativas:** "atalhos de tarefa" e "cartões" definidos em JSON validado (nome, ícone, pedido em linguagem
   natural que vira tarefa normal). Nada executa código novo.
3. **Mudança de código pelo Claude Code/Codex (E1):** só em uma *worktree* git separada do app; a lista de pastas permitidas é
   fixa (`desktop/qml/views`, `desktop/qml/components`, novos arquivos em `desktop/qml/dev/`). Proibido: `core/action_risk.py`,
   `core/action_policy.py`, `core/plan_validator.py`, `core/process_runner.py`, `main.py`, `desktop/bridge.py`, `config.yaml`,
   qualquer arquivo de credencial. Antes de aplicar: diff mostrado, `scripts/smoke_ui.py` e `scripts/check_release.py --code-only`
   verdes na worktree, aprovação explícita da pessoa. Aplicar = merge local; desfazer = um clique (reverte o commit).

### E4. Catálogo de papéis de parede

- A pessoa anexa as imagens junto com este prompt (três pinturas de paisagem: veleiro em baía ensolarada, cidade costeira
  à noite, vale de montanha sob tempestade). Elas vêm **com o app**, disponíveis para todos escolherem, em
  `app/desktop/assets/wallpapers/`.
- **Licença antes de empacotar (o repositório é público):** para cada imagem, registre em
  `desktop/assets/wallpapers/CREDITS.md` título, autor, ano, fonte e licença. Só entra no repositório imagem em domínio
  público ou com licença que permita redistribuição (ex.: pintura de autor falecido há mais de 70 anos em reprodução fiel,
  CC0, CC BY com crédito). Se a licença de alguma não puder ser confirmada, **não a inclua**: avise a pessoa, deixe-a
  disponível apenas pela opção "importar imagem" (camada pessoal, fora do git) e siga com as demais.
- Otimize para distribuição: WebP/JPEG de alta qualidade na resolução de tela comum (ex.: 2560 px de largura) e uma
  miniatura; mantenha o tamanho total do catálogo enxuto.
- Para cada imagem, gere em código uma **paleta harmônica** (k-means ou média por regiões): base, 3 tons de luz,
  acento, cor de texto e opacidade do vidro com contraste AA medido. O tema inteiro deriva dela.
- Tratamento: versão em resolução da tela, leve desfoque e escurecimento opcionais para leitura; nunca esticar sem proporção.
- Tela de escolha no Harness > Aparência: miniaturas, "importar imagem" (PNG/JPG/WebP até 15 MB, validada) e "sem foto"
  (volta às luzes atuais). O fundo da abertura acompanha a escolha.

## 4. Restrições inegociáveis

- **Sem regressão**: `tests/`, `scripts/smoke_code_agent.py`, `scripts/smoke_ui.py`, `scripts/eval_brain_retrieval.py --compare`,
  `scripts/eval_user_layer.py` e o gate `scripts/check_release.py --code-only` verdes a cada entrega (use o `.venv` do projeto).
- **Segurança**: nada enfraquece a porta de efeito, as políticas ou o isolamento de processos. O modo Desenvolvedor não pode
  desligar proteções nem editar os arquivos proibidos, mesmo a pedido da IA.
- **Privacidade**: repositório público. Nada pessoal em testes, docs ou commits (nomes, contatos, pastas, cofres, imagens da pessoa).
- **Custo**: a pessoa **autorizou chamadas reais ao Claude Code e ao Codex** para validar a E1. Use poucas, curtas e numa
  pasta de teste descartável; a suíte automática continua com CLIs simuladas (o gate não pode depender de rede nem de
  login). GPT-Live e outros serviços pagos seguem precisando de autorização.
- **Foco**: não roube o foco nem tire capturas da tela da pessoa; verifique a interface com renderização fora da tela.
- **Git**: commit e push só quando a pessoa pedir; nunca reescreva histórico publicado.

## 5. Aceite por entrega

| Entrega | Aceite (teste que falharia sem ela) |
|---|---|
| E1 | Adaptadores com CLI falsa: tarefa roda na pasta certa, progresso chega à tela e ao registro, cancelar mata o processo, arquivo alterado fora da pasta = falha; sem sessão = mensagem clara e nenhuma credencial lida |
| E2 | Capturas fora da tela de todas as telas no tema escuro e claro, revisadas; contraste AA medido; smoke QML sem aviso no renderizador por software |
| E3 | Nível 1 e 2 validados por esquema com desfazer; nível 3 recusa diff que toca arquivo proibido; gate na worktree antes de aplicar; reverter restaura o estado |
| E4 | Paleta extraída é determinística; contraste AA garantido; imagem inválida ou grande demais é recusada; toda imagem empacotada tem crédito e licença em `CREDITS.md`; imagens importadas pela pessoa nunca vão para o git |

## 6. Forma de trabalhar

1. Comece medindo: rode o gate e salve a linha de base.
2. Entregue E1 → E2 → E3 → E4, cada uma com testes, capturas revisadas e gate verde antes da próxima.
3. Em cada entrega, diga o que foi verificado, o que não foi e por quê. Nunca declare um teste como passado sem tê-lo rodado.
4. Pergunte só quando a escolha mudar escopo, risco ou algo irreversível; no resto, decida e registre a decisão.
