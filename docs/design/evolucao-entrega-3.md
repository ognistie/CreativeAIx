# Evolução do AI Farm Agent — Entrega 3 (pendências do briefing)

> Briefing: [prompt-evolucao-creative-aix.md](prompt-evolucao-creative-aix.md). Entregas anteriores: [1](evolucao-entrega-1.md), [2](evolucao-entrega-2.md).
> Data: 2026-11-12. Escopo: tudo o que as entregas 1 e 2 listaram como pendente, menos o que depende de requisitos externos (ver §6).

## 1. Segurança: escopo do agente de Arquivos

**Problema (achado no Lab).** O `PathResolver` procurava nomes de pastas conhecidas no texto inteiro, inclusive **dentro do caminho citado**. Com isso, o escopo autorizado crescia para pastas inteiras:

| Pedido | Escopo antes | Escopo agora |
|---|---|---|
| `…\Documents\GitHub\proj\caso` | a pasta citada **e** Documentos inteiro | só a pasta citada |
| `…\Downloads\fotos\viagem` | a pasta citada, Downloads **e Imagens** inteiros | só a pasta citada |
| "…da pasta documentos para C:\backup" | Documentos e `C:\backup` | igual: uma pasta conhecida citada no texto continua valendo |

**Correção:** `agents/subagents.py`, onde os nomes só contam fora dos caminhos. **Teste:** `tests/test_file_scope.py` (um vizinho da pasta citada fica fora do escopo).

## 2. Os seis prints

| Referência | Entregue |
|---|---|
| **Como usar** | Já era recolhível (entrega 1). Agora, com pouca altura, aparece recolhido sem mudar a escolha salva, e abre com um clique. |
| **Como os agentes trabalham** | O cartão de cada agente ganhou **Recebe**, **Ferramentas** (lidas da política do executor), **Limites** e **Exemplos**. Limites que falam de confirmação só aparecem com a trava em `enforce`, para a ficha não prometer o que não está ligado. Em janela estreita o cartão já virava uma coluna. |
| **Aparência** | A nota corrigida diz o comportamento real: muda e salva na hora (antes dizia "Salve para manter"). "Respostas" e "Barra lateral" agora avisam que valem depois de Salvar. A cor escolhida ganhou um ✓ e o leitor de tela anuncia "escolhida". |
| **Histórico** | Título, números e busca alinhados; filtros por estado; lista com ícone e texto do estado, horário, duração, agentes e custo; **painel de detalhes** com métricas, plano, passos com evidência (registro de tarefas, segredos mascarados) e resultado; "Usar de novo" sempre visível; navegação por teclado. |
| **Atividade** | Período no título ("desde 1º de …"), rótulo e datas das barras diárias, legenda de intensidade do mapa de calor com o pico, e **definição de cada métrica**. O texto do custo diz que ele é "dividido igualmente entre os agentes do plano", o que foi conferido no código. |
| **Configurações** | Nova seção **Provedores**: Anthropic (agentes) e OpenAI (voz). Mostra só se a chave está configurada, nunca o valor, com a próxima ação ao lado. Teste: a chave falsa não aparece nem em parte. |

## 3. Diário

- **Navegação por data:** calendário do mês com marca nos dias que têm entrada. Um clique filtra o dia; clicar de novo tira o filtro.
- **Resumo por IA, opcional:** "Resumir com IA" avisa **antes** o que vai para o provedor (só o título e o texto daquela entrada, com a contagem de caracteres). Entrada privada nunca vai. O resumo fica ligado à versão: se a entrada muda, ele aparece como "desatualizado". O prompt trata o texto como dado. Testes em `tests/test_journal.py`; nenhuma outra entrada é enviada.

## 4. AI Research Lab, etapa 5

| Área | Entregue |
|---|---|
| **Code Workspace** (aba Código) | O modo Desenvolvedor dentro do Lab: pedir mudança ao Claude Code ou ao Codex, acompanhar, ver o diff colorido, rodar o gate (em caixa de areia), aplicar com confirmação (merge do conteúdo verificado), desfazer e descartar. **Rota para quem já usa:** o botão "Abrir no AI Research Lab (aba Código)" no Harness → Desenvolvedor. Terminal interativo e debugger não foram feitos (§6). |
| **Training & Optimization** (aba Otimização) | **Anotações** em cada caso de um experimento. **Promoção com trava:** só publica com um experimento **real** recente contra a versão publicada, no conjunto atual, com todos os casos rodados, sem piorar em nenhum caso e com taxa de sucesso igual ou maior. Um experimento simulado não conta. |
| **Autonomous Research** | Objetivo, depois as falhas e anotações da versão publicada, depois uma hipótese do modelo (instruções novas, sem ferramentas nem permissões novas), depois uma variante isolada, e por fim os **mesmos casos** nas duas versões, com veredito. **Nunca publica:** a decisão é sua e passa pela trava de promoção. Exige confirmação e orçamento (até US$ 5). Por enquanto só com o agente de Arquivos. |
| **Fine-tuning** | Aparece como **indisponível**, com os requisitos que faltam e o que já dá para fazer. |

Testes: `tests/test_lab.py` (15 testes): feedback, promoção com e sem evidência, regressão bloqueada, pesquisa que propõe e testa sem publicar, e fine-tuning indisponível.

## 5. Aceite visual e acessibilidade

| Critério | Cenário | Resultado |
|---|---|---|
| Janela reduzida | 900×650 (cerca de 620 px de conteúdo), GPU, dados sintéticos | Histórico, Diário, Biblioteca e Lab cortavam à direita. Agora, abaixo de 860 px, os controles descem e as duas colunas viram uma (lista em cima, com altura limitada). O formulário do Lab rola. A ajuda aparece recolhida. |
| Escala do Windows 150% | `QT_SCALE_FACTOR=1.5`, 1280×720 lógicos (um monitor 1920×1080) | As seis abas do Lab não cabiam ao lado do título. Agora descem abaixo de 1180 px. As outras telas cabem. |
| Teclado | `Button`, `Chip`, `NavItem` e `TogglePill` **não aceitavam teclado** (só o `IconButton`) | Os quatro recebem Tab, acionam com Enter ou Espaço e mostram anel de foco (`focusRing`). Pílulas cujo estado vem do app (Conversa, Diário ligado, Privada) usam o modo `manual` e só pedem a troca. Fluxo `keyboard_controls` e teste estrutural. |
| Movimento reduzido | "Luzes paradas" | Continua coberto pelo teste que proíbe duração solta: componentes novos usam `Theme.dur`, e a orbe e o brilho de voz param com `Theme.motion`. |
| Contraste | Todos os temas e paletas | 442/442 AA |

**Instabilidade encontrada e corrigida:** o fluxo de teclado apertava Enter na pílula "Conversa", e o pedido chegava à ponte de verdade, que **ligava a conversa ao vivo** (microfone e threads de áudio) dentro do teste. O processo caía ao encerrar em cerca de 1 de cada 4 rodadas. Achei a causa por bisseção dos fluxos. Agora esse slot só registra durante o passo; foram 9 rodadas seguidas sem queda. Não houve chamada paga, porque o processo de teste não carrega o `.env`.

## 6. O que não foi feito e por quê

- **Terminal interativo e debugger no Code Workspace:** dariam execução arbitrária de comandos na máquina. O caminho seguro existente (worktree, só arquivos de interface, gate em caixa de areia, aplicar só o conteúdo verificado) foi mantido. Um terminal pede um desenho de isolamento próprio, que é uma decisão sua.
- **Fine-tuning:** falta provedor com suporte, conjunto de dados com permissão e orçamento.
- **Experimentos e pesquisa para outros agentes além de Arquivos:** precisam de verificadores de estado final por domínio (planilha, página web, janela).
- **Revisão na sua tela real:** as capturas foram feitas na GPU, mas fora da área visível.

## 7. Verificação final

Gate `check_release.py`: `CODE_READY True` com 445 testes. 14 fluxos de interface fora da tela (9 rodadas seguidas sem queda). Smoke em caixa de areia. Contraste 442/442.
