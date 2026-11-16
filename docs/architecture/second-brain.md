# Segundo Cérebro próprio — prompt de desenvolvimento (v1)

Este documento é o contrato de trabalho para construir o segundo cérebro **dentro** do AI Farm Agent.
Ele serve como prompt para quem implementa (pessoa ou agente) e como critério de aceite de cada etapa.

---

## 1. Papel e objetivo

Você é o engenheiro responsável por transformar o vault Obsidian `vault/` num segundo cérebro
nativo do app desktop (PySide6 + QML), que o usuário edita por inteiro dentro da plataforma e que os
agentes (Maestro, Web, Desktop, Code, Data, File) usam como fonte de contexto das tarefas.

**Resultado esperado:** o usuário deixa de precisar do Obsidian para ver, buscar, criar, editar, ligar e
remover notas; descreve a si mesmo numa seção **Você**; ajusta como os agentes trabalham e como a
plataforma se parece num **Harness** editável; e tudo isso numa interface com identidade visual própria,
derivada da tela de abertura.

## 2. Requisitos do usuário (fonte da verdade)

1. **Totalmente editável e funcional:** criar, editar, renomear, mover e remover notas e pastas;
   adicionar e retirar contexto; editar caminhos (procedimentos) e nós/ligações (`[[links]]`).
2. **Seção Você:** o segundo cérebro do usuário — rotinas, tarefas que mais usa, jeito de falar,
   skills para os agentes, padrão de respostas, etc. Os agentes usam isso como preferência.
3. **Harness editável** (inspirado no "Creator Mode" do DeepSeek Harness): mudar como os agentes
   interagem, instruções por agente, padrão de resposta, módulos e aparência da plataforma.
4. **Visual moderno, futurista e clean:** a tela de abertura (degradê pêssego, âmbar e lilás com luzes
   em deriva lenta, marca de quatro quadrados com um azul) vira a identidade de toda a plataforma;
   cores e botões personalizáveis; mais interação e criatividade sem perder a leitura.

## 3. Restrições inegociáveis

- **Sem regressão.** Sem camada pessoal, o comportamento dos agentes é idêntico ao atual. Os testes
  (`tests/`), o smoke (`scripts/smoke_code_agent.py`), o QML (`scripts/smoke_ui.py`) e o gate
  (`scripts/check_release.py --code-only`) continuam verdes a cada etapa.
- **Privacidade (repo público).** O conteúdo do usuário mora **fora do repositório** (camada pessoal,
  por padrão `Documentos/AI Farm Agent/Cérebro`). Editar uma nota de fábrica cria uma cópia pessoal;
  o arquivo do repositório nunca é alterado pela interface. Nada pessoal em testes, docs ou commits.
- **Nota é dado, não instrução.** O que vem do cérebro entra no prompt como referência marcada; as
  permissões e bloqueios continuam em código (`plan_validator`, `action_risk`, `memory_gate`).
  Instruções do Harness ajustam estilo e prioridade, nunca ampliam o que um agente pode fazer.
- **Falha do cérebro nunca bloqueia uma tarefa** (mesma regra do `core/brain.py`).
- **Mudanças pequenas e reversíveis**: cada etapa entra atrás de dados opcionais (sem pasta pessoal,
  sem Harness = comportamento antigo). Versões do Harness permitem desfazer.
- **Custo zero de API** nesta frente: nada de teste pago.

## 4. Arquitetura

```
             ┌──────────── Interface (QML) ────────────┐
             │ Cérebro · Você · Harness · tema/ambiente │
             └───────────────┬─────────────────────────┘
                             │ Bridge (slots JSON)
             ┌───────────────▼─────────────────────────┐
             │ core/brain_store.py  (ponto único)       │
             │  camada base  : vault/ (repo,   │
             │                 só leitura pela UI)      │
             │  camada pessoal: Documentos/.../Cérebro  │
             │                 (vence a base; escrita)  │
             │  .cerebro/removidas.json (ocultas)       │
             │  .cerebro/indice.sqlite  (FTS5, links)   │
             └───────┬──────────────────────┬──────────┘
                     │                      │
          core/brain.py (agentes)   core/harness.py (+ versões)
          context_for(): notas,     instruções por agente,
          skills, referências,      padrão de resposta,
          lições, dicionário,       módulos, aparência
          + Você + Harness
```

- **Fonte:** arquivos Markdown (portáveis, legíveis, abrem no Obsidian se o usuário quiser).
- **Índice:** SQLite FTS5 derivado, reconstruído por data de modificação; pode ser apagado sem perda.
- **Sobreposição:** `resolve(rel)` devolve a nota pessoal se existir, senão a de fábrica, salvo se
  estiver na lista de removidas. "Restaurar original" apaga a cópia pessoal.
- **Remoção:** nota pessoal vai para `.lixeira/`; nota de fábrica fica oculta (recuperável).
- **Ligações:** `[[Nota]]` e `[[Nota|apelido]]`; ao renomear, os links são atualizados.
- **Você:** pasta `Você/` na camada pessoal com modelos guiados; o bloco "Sobre você" entra no
  contexto dos agentes com limite de tamanho e só com o que o usuário preencheu.
- **Harness:** `.cerebro/harness.json` com histórico em `.cerebro/harness_versoes/`.

## 5. Etapas e critérios de aceite

| Etapa | Entrega | Aceite |
|---|---|---|
| 0. Linha de base | `scripts/eval_brain_retrieval.py` grava as notas que cada agente recupera em pedidos fixos | Relatório salvo antes de qualquer mudança |
| 1. Ponto único + camadas | `core/brain_store.py`; `brain`, `skills`, `lexicon` e `persona` leem por ele | Sem pasta pessoal, recuperação idêntica à linha de base; testes de sobreposição, remoção, renomear e índice |
| 2. Você + Harness (núcleo) | `core/harness.py`; bloco Você e instruções por agente no `context_for` | Bloco só aparece com conteúdo; limite respeitado; Harness inválido cai no padrão; versões desfazem |
| 3. Identidade visual | `Ambient.qml` (fundo da abertura) em todo o app, superfícies de vidro, cor de destaque e intensidade do ambiente personalizáveis, movimento reduzido opcional | Contraste AA do texto sobre as superfícies; smoke QML sem avisos; captura revisada |
| 4. Telas | **Cérebro** (pastas, busca, editor com prévia, ligações e backlinks, mapa de nós, criar/renomear/remover/restaurar), **Você** (cartões guiados), **Harness** (agentes, respostas, aparência, versões) | Fluxos completos com estados vazio/erro; ações destrutivas confirmadas e reversíveis |
| 5. Criação por linguagem natural | "Descreva a mudança": o modelo propõe um patch do Harness ou notas novas, o usuário aprova | Nada aplicado sem aprovação; patch validado por esquema |
| 6. Aprendizado proposto | Agentes sugerem lições e procedimentos; entram como hipótese até o usuário aprovar | Regras do `memory_gate` preservadas |

## 6. Verificação em cada etapa

1. `python -m unittest discover -s tests` e o gate `scripts/check_release.py --code-only`.
2. `scripts/eval_brain_retrieval.py --compare`: mesmas notas recuperadas sem camada pessoal.
3. `scripts/smoke_ui.py` e inspeção da captura `memory/ui-release.png`.
4. Varredura de dado pessoal no diff antes de qualquer push.

## 7. Estado (2026-11-10)

Etapas 0 a 6 entregues. Etapa 5: `core/creator.py` (prompt `creator-v2`; a proposta validada fica no app e só ela é aplicada). Etapa 6: `core/suggestions.py` (fila em `.cerebro/sugestoes.json`; aprovar = verificação humana, a mesma que o `memory_gate` aceita). Testes: `tests/test_brain_store.py` e `tests/test_creator_suggestions.py` (modelo simulado, casos adversariais). Falta medir o criador com o modelo real: precisa de autorização para chamadas pagas.

`scripts/eval_user_layer.py` (também em `tests/test_user_layer_eval.py`) confere que Harness e Você chegam ao prompt do Maestro, de cada agente e da resposta final, com marcadores e cliente simulado. Ela achou que o Maestro não recebia nem as instruções dele nem o Você; corrigido em `agents/maestro.py`.

## 8. Fora do escopo agora

Busca por significado (embeddings) até a busca por texto se mostrar insuficiente na medição;
sincronização em nuvem; plugins com código arbitrário (o Harness só aceita dados validados).
