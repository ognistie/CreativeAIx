## Visão geral

Orquestração multiagente é a disciplina de dividir um pedido entre vários agentes e juntar o resultado sem perder controle no caminho. Ela tem três peças. Roteamento decide quem cuida de cada parte. Handoff é a passagem de uma etapa para a seguinte, com o que precisa ir junto. Contrato define o que cada agente recebe, o que pode fazer e o que deve entregar. Quando essas peças são explícitas, o sistema fica previsível; quando ficam implícitas no prompt, ele parece funcionar até o dia em que um texto lido numa página muda o plano.

O segundo tema deste texto, o desacoplamento entre cérebro e mãos, é o que torna a orquestração segura. O cérebro é o modelo que interpreta o pedido e propõe ações. As mãos são o executor: o código que de fato clica, digita, grava arquivos e chama serviços, com permissões próprias. Separar os dois significa que o modelo pode propor qualquer coisa, mas quem decide se a ação acontece é código determinístico que não lê o raciocínio do modelo como autoridade. A ficha deste tema resume a consequência: é isso que impede um texto lido de virar uma ação não pedida.

As duas ideias se reforçam. Vários agentes especializados só são mais seguros que um agente generalista se cada um tiver um conjunto restrito de ferramentas, e essa restrição só vale se for aplicada no executor. Do outro lado, um executor com regras claras permite trocar o modelo, mudar o prompt ou acrescentar um agente sem reescrever as garantias.

Este texto percorre os conceitos, as topologias mais comuns, o funcionamento interno do pipeline do Creative AIx, os modos de falha típicos e como medir se dividir o trabalho ajudou.

## Conceitos centrais

### Roteamento

Roteamento é a decisão de qual agente atende cada parte do pedido. Pode ser feito por um modelo (um orquestrador lê o pedido e escolhe), por regras (expressões, dicionários, alvo já aberto na conversa) ou pela pessoa (um seletor que manda o pedido direto a um agente). Na prática, sistemas maduros combinam os três: regras para os casos óbvios e baratos, modelo para o resto, e a pessoa como última palavra quando quer.

O roteamento tem custo dos dois lados. Errar o agente desperdiça o trabalho inteiro da subtarefa. Chamar um modelo para decidir algo que uma regra resolveria acrescenta latência e uma nova chance de erro a cada pedido.

### Handoff

Handoff é a transferência de controle entre agentes. A documentação de handoffs do OpenAI Agents SDK descreve um formato comum: para o modelo, o handoff aparece como mais uma ferramenta, do tipo "transferir para o agente X", e o desenvolvedor pode filtrar o histórico que segue para o próximo agente e anexar dados estruturados à transferência. A pergunta de engenharia em todo handoff é a mesma: o que exatamente passa adiante? A conversa inteira carrega ruído e, pior, carrega conteúdo não confiável. Um resumo carrega menos, mas pode perder o detalhe de que o próximo agente precisava.

### Contrato

O contrato de um agente é o que o torna substituível e testável: entradas aceitas, ferramentas permitidas, formato da saída e critérios de reprovação. O artigo da Anthropic sobre o sistema de pesquisa multiagente relata que instruções vagas para subagentes produziam trabalho duplicado e lacunas, e que cada delegação funcionava melhor com objetivo, formato de saída, orientação sobre ferramentas e fontes, e limites claros da tarefa. Isso é contrato, escrito em linguagem natural. A versão mais robusta é escrever a parte verificável do contrato em código.

### Proposta e ação

Uma proposta é um objeto: um plano, uma lista de passos, uma chamada de ferramenta ainda não executada. Uma ação é um efeito no mundo. O ponto de separação entre as duas é onde a política se aplica. Se o modelo produz ações diretamente, não há onde aplicar política além do prompt. Se produz propostas, há um momento, antes do efeito, em que código pode inspecionar, recusar, pedir confirmação ou pedir outra proposta.

### Permissão no executor

Permissão no executor significa que a decisão final de autorizar uma ação mora no componente que age, e não no componente que pensa. O executor conhece o agente que está ativo, o pedido original da pessoa, a janela em primeiro plano, o rótulo real do botão. O modelo conhece apenas o que leu, e o que leu pode ter sido escrito por um atacante.

## Cérebro e mãos: por que desacoplar

O padrão ReAct mostrou o valor de intercalar raciocínio e ação: o modelo pensa, age, observa o resultado e pensa de novo. É uma ideia poderosa, mas em sua forma ingênua o mesmo laço que raciocina também executa. Tudo o que entra na observação pode influenciar a próxima ação, inclusive instruções escondidas numa página ou num arquivo.

Separar cérebro e mãos resolve isso por construção. Há pelo menos quatro ganhos.

Segurança. Instrução injetada pode convencer o modelo, mas não convence uma checagem determinística sobre o nome da ferramenta, o escopo do caminho ou o rótulo do botão. O executor não precisa entender a injeção para bloqueá-la; basta que a ação resultante esteja fora do que foi autorizado.

Substituibilidade. O texto da Anthropic sobre agentes gerenciados com interfaces estáveis trata exatamente da separação entre o "cérebro" e as "mãos" do agente: quando a fronteira entre eles é uma interface estável, cada lado pode evoluir sem quebrar o outro. Trocar o modelo do orquestrador não deveria exigir revisar as regras de exclusão de arquivo.

Testabilidade. Um plano é um dado. Dá para validá-lo, compará-lo com o anterior, gravá-lo, reproduzi-lo em modo simulado. Uma sequência de ações já executadas só pode ser auditada depois do fato.

Contenção de dano. Se cada mão só tem as ferramentas do seu domínio, um erro do cérebro tem alcance limitado. Um agente de pesquisa web que nunca teve acesso a exclusão de arquivos não exclui arquivos, por mais confuso que esteja.

O custo do desacoplamento é real: mais componentes, mais formatos intermediários, mais lugares onde o plano pode ser recusado e o pedido ficar sem resposta. Por isso a recusa precisa voltar com motivo legível, para o modelo replanejar ou para a pessoa entender.

## Topologias

| Topologia | Como funciona | Quando ajuda | Custo e risco |
| --- | --- | --- | --- |
| Agente único em laço | Um modelo raciocina e chama ferramentas até concluir | Tarefas curtas, um domínio | Contexto cresce; todas as ferramentas no mesmo lugar |
| Orquestrador e trabalhadores | Um agente planeja e delega partes a agentes especializados | Partes independentes, domínios diferentes | Mais chamadas de modelo; perda de contexto entre etapas |
| Handoff em cadeia | Um agente transfere o controle ao próximo | Atendimento em etapas com especialistas | Histórico mal filtrado vaza ruído ou injeção |
| Pipeline com dependências | Subtarefas com ordem declarada e saídas encadeadas | Resultado de uma etapa alimenta a seguinte | Uma falha bloqueia as dependentes |
| Hierárquica | Orquestradores que delegam a outros orquestradores | Problemas muito amplos | Difícil de depurar; erros se acumulam |

O artigo da Anthropic sobre pesquisa multiagente descreve o padrão orquestrador e trabalhadores aplicado a pesquisa ampla: um agente líder decompõe a pergunta, cria subagentes que buscam em paralelo, cada um com o próprio contexto, e condensa o que eles trazem. O mesmo texto é franco sobre os limites. Sistemas multiagente gastam muito mais tokens do que uma conversa simples, então só compensam em tarefas valiosas o bastante e paralelizáveis. E tarefas em que todos precisam do mesmo contexto ou que têm muitas dependências entre as partes, como boa parte das tarefas de programação, se encaixam mal nesse formato.

Daí vem a regra prática que aparece em quase todo guia sério: comece com um agente só e divida quando medir que dividir ajuda.

## Como funciona por dentro: o pipeline do Creative AIx

O Creative AIx usa uma combinação de pipeline com dependências e orquestrador com trabalhadores. O orquestrador é o Maestro (`app/agents/maestro.py`). Os trabalhadores são os agentes de domínio: Desktop, Web, Data, Code, File e o agente externo que aciona Claude Code ou Codex numa pasta escolhida pela pessoa. Quem conduz a execução é o `Controller` em `app/desktop/controller.py`, e quem toca o computador é o motor em `app/core/automation.py`.

O fluxo, simplificado, é este:

```python
def run(task, session):
    plan = (vault_plan(task) or existing_plan(task, session) or extcode_plan(task, session)
            or continue_plan(task, session)          # atalhos sem modelo, validados igual
            or maestro.analyze(task))                 # gate de ambiguidade + LLM + validate_plan
    if plan.needs_clarification:
        return ask(plan.question)
    if settings.plan_review and not wait_for_user_approval(plan):
        return cancel()
    for sub in plan.subtasks:
        if depends_on_failed(sub):
            continue
        sub.params.pop("continue", None)              # capacidade vem da sessão, nunca do modelo
        agent = agents[sub.agent]
        steps = agent.plan(sub)                       # o agente propõe passos
        if not validate_steps(sub.agent, sub, steps, task).approved:
            continue
        for step in steps:
            result = engine.execute(step)             # action_policy + action_risk + confirmação
            if result.status == "needs_confirmation":
                return stop_and_ask(result)
            result = agent.review_step(step, result)  # ex.: ContentGuard no texto lido
```

Cada etapa merece um comentário.

### Atalhos sem modelo

Antes de chamar o Maestro, o controller tenta caminhos determinísticos. Abrir um cofre do Obsidian, abrir algo que já existe no projeto da conversa (`app/core/existing_targets.py`), mandar um pedido que cita Claude Code ou Codex ao agente externo (`app/agents/extcode_agent.py`) e continuar uma interação simples no alvo já aberto (`continue_plan` em `app/agents/maestro.py`). Dentro do Maestro, `fast_open_plan` resolve "abrir X" quando X é exatamente um app ou site do dicionário. Esses atalhos são roteamento por regra: rápidos, baratos e auditáveis. O detalhe importante é que eles passam pelas mesmas políticas de aceite que um plano do modelo. Atalho não é porta dos fundos.

### Gate de ambiguidade

O Maestro começa com `_detect_ambiguity`, uma heurística determinística para pedidos vagos como "envia para ele". Se o pedido é ambíguo, a resposta é uma única pergunta, sem chamar o modelo. O prompt do Maestro reforça a regra para os casos que a heurística não pega: no máximo uma pergunta por turno, nunca executar várias hipóteses em paralelo. Isso é uma decisão de orquestração: em vez de deixar a ambiguidade descer até um agente que vai chutar, ela é resolvida no topo.

### Plano do modelo e políticas de aceite

Quando o Maestro chama o modelo, o plano volta como JSON com uma lista de subtarefas, cada uma com `agent`, `task`, `params` e `depends_on`. Esse objeto passa por `validate_plan` em `app/core/plan_validator.py`, que aplica políticas com identificadores rastreáveis (as notas correspondentes ficam em `vault/20 Politicas/`). Alguns exemplos do que é checado:

- No máximo cinco subtarefas, cada uma um objeto com tipos corretos (POL-000).
- Agente precisa existir (POL-005).
- `depends_on` só aponta para subtarefa anterior, e variáveis como `{output_summary_1}` só podem ser usadas com dependência declarada (POL-004).
- Texto lido numa subtarefa nunca vai dentro de uma URL, porque um texto injetado poderia mandar abrir um endereço do atacante com o conteúdo de uma aba logada na query (POL-004).
- O plano não pode acrescentar um efeito externo que o pedido não fez, como transformar "escreva Oi na conversa" em "escreva e envie" (POL-009).

Se o plano é reprovado, o Maestro ganha uma única nova tentativa, com o motivo literal das violações anexado ao pedido. Uma tentativa, não um laço: replanejar indefinidamente gasta tokens e tende a produzir variações do mesmo erro. Se a segunda versão também falha, a tarefa termina com a mensagem de reprovação, e o plano rejeitado volta junto no resultado, disponível para análise.

### Revisão do plano pela pessoa

Com a opção "Revisar o plano" ligada nas Configurações, pedidos digitados param antes de executar e mostram as subtarefas para aprovação. A pessoa pode aprovar, recusar ou pular passos específicos. A aprovação usa um token gerado por tarefa em `app/desktop/controller.py`, para que um clique atrasado não aprove o plano errado.

### Proposta do agente e validação dos passos

Cada agente recebe sua subtarefa e devolve passos concretos. Esses passos passam por `validate_steps`, que é mais específico por domínio. Code e Data só aceitam artefatos declarativos. File passa pelo contrato de `app/core/file_contracts.py`, que exige caminhos absolutos dentro das pastas citadas no pedido e confirmação explícita para excluir. O agente externo aceita um único passo `ext_code_task`, numa pasta que existe e que não é a do próprio app (`folder_error` em `app/core/coding_agents.py`). Web e Desktop não podem conter execução arbitrária nem atalhos que abrem superfícies de comando.

### Permissão no executor

A última barreira está em `engine.execute`. Primeiro, execução arbitrária (`run_python`, `run_command`, `pip_install`) é recusada sempre. Depois, `authorize` em `app/core/action_policy.py` confere se a ação pertence ao conjunto do agente ativo. O agente ativo é definido pelo controller, não pelo passo: o docstring do módulo diz que passos gerados pelo modelo não escolhem o próprio dono. Em seguida, `step_risk` em `app/core/action_risk.py` classifica o efeito da ação, olhando inclusive o título da janela em primeiro plano lido do sistema, e `_authorize_ui` decide se pode seguir.

No modo padrão (`enforce`), um efeito sensível como enviar, publicar, comprar, pagar, transferir, excluir ou aceitar termos para e pergunta. No app, a confirmação inline no texto do pedido não é aceita quando existe um canal de confirmação ao vivo: o executor pausa naquela ação exata, mostra a pergunta e espera a resposta, com token próprio e, na voz, um código falado. Além disso, cada efeito acontece no máximo uma vez por tarefa; repetir pede nova confirmação. O comentário em `authorize_once` explica a origem dessa regra: um piloto viu o campo vazio depois de enviar, achou que não tinha enviado e reenviou.

Os pilotos de navegador e de aplicativos (`app/core/browser_pilot.py`, `app/core/app_pilot.py`) recebem a mesma porta de efeito como parâmetro. Antes de clicar num elemento sensível, conferem se o elemento e a página ainda estão no estado observado. Antes de navegar para um site que a pessoa não citou, perguntam.

### Passo a passo: "pesquise sobre o Palmeiras e envie no Teams para o João"

1. O controller não encontra atalho; o Maestro é chamado. Não há ambiguidade detectável: destinatário e canal estão no pedido.
2. O modelo propõe duas subtarefas: Web pesquisa e lê o resultado; Desktop envia `{output_summary_1}` para João no Teams, com `depends_on: 1`.
3. `validate_plan` aprova: a dependência aponta para trás, a variável está na lista permitida, o efeito "enviar" foi pedido pela pessoa, então POL-009 não dispara.
4. Se a revisão de plano estiver ligada, a pessoa vê as duas linhas e aprova.
5. O agente Web propõe passos, `validate_steps` aprova e a página é lida. Quando a leitura passa por uma ação de leitura (`web_read` ou `browser_read`), o `ContentGuard` corta o texto a um tamanho máximo e marca padrões de injeção antes de o resultado seguir; quando passa pelo piloto, o prompt dele trata o conteúdo como dado e a porta de efeito continua valendo.
6. O gerenciador de contexto (`app/core/context_manager.py`) substitui `{output_summary_1}` pelo resumo sanitizado da subtarefa 1.
7. O agente Desktop propõe abrir o Teams, localizar a conversa e digitar. Quando o passo que envia chega ao executor, `step_risk` classifica o efeito como "enviar". Mesmo com o plano aprovado, o executor pausa e pergunta. A mensagem só sai depois da confirmação.

O ponto do exemplo está no passo 7. A aprovação do plano diz "este é o caminho que eu aceito". A confirmação no executor diz "este efeito, com este conteúdo, agora". São decisões diferentes, tomadas em momentos diferentes e com informação diferente.

## Subagentes determinísticos

Nem toda divisão de trabalho precisa de mais chamadas de modelo. Em `app/agents/subagents.py`, cada agente de domínio tem três ajudantes com papéis fixos: entender (normalizar o pedido e os parâmetros), montar (produzir o insumo da execução) e conferir (revisar o que foi proposto ou executado). A maioria é determinística e não gasta tokens; a exceção declarada é o construtor do agente de código, que é a própria chamada ao modelo. O docstring resume o princípio: a menor autonomia que resolve, e nenhum subagente amplia permissões.

Cada ajudante devolve um `Trace` com nome, papel, se passou e um resumo curto, e o controller junta esses rastros numa linha de log por agente. Esse padrão é útil fora do app também: muita "orquestração" pode ser feita com funções puras, com rastro, deixando o modelo só para o que exige linguagem.

## Padrões e anti-padrões

Padrões que funcionam:

- Roteamento em camadas: regras para o óbvio, modelo para o resto, pessoa com a palavra final.
- Plano como dado validado por código antes de qualquer efeito, com identificadores de política rastreáveis.
- Uma nova tentativa com o motivo literal da reprovação, não um laço aberto.
- Ferramentas restritas por domínio, aplicadas no executor.
- Capacidades (alvo de continuação, pasta de trabalho, agente ativo) vindas da sessão e do pedido, nunca de parâmetros do modelo. No controller, o parâmetro `continue` é apagado de qualquer subtarefa antes de a sessão decidir.
- Handoff com variáveis nomeadas e conteúdo resumido, em vez de repassar a conversa inteira.
- Confirmação de efeito no executor, por ação, mesmo com plano aprovado.

Anti-padrões:

- Autorização escrita no prompt ("nunca envie sem confirmar") sem verificação em código.
- Agentes demais para tarefas simples. Cada salto acrescenta latência, custo e um ponto de perda de informação.
- Handoff sem contrato, em que o próximo agente recebe um texto livre e precisa adivinhar o que é instrução e o que é dado.
- Orquestrador que também executa. Ele lê tudo, então tudo o que leu pode virar ação.
- Permissão herdada por delegação: o subagente ganha as ferramentas do orquestrador "por conveniência".
- Paralelismo sem fronteiras claras, produzindo trabalho duplicado ou partes que ninguém cobre.

## Modos de falha

Acúmulo de erro. Em sistemas com várias etapas, um erro pequeno no início se propaga. O artigo da Anthropic sobre pesquisa multiagente destaca que agentes com estado e execução longa tornam falhas menores capazes de desviar a trajetória inteira. No app, a regra de que uma subtarefa dependente não roda se a anterior falhou evita que um resultado vazio alimente um envio.

Telefone sem fio. Cada handoff resume, e resumos perdem detalhe. Uma mitigação descrita no mesmo artigo é deixar subagentes gravarem resultados em armazenamento externo e passar referências, em vez de reescrever tudo pelo orquestrador. No app, `original_task` acompanha cada subtarefa para que agentes que precisam do tema exato não dependam da reformulação do Maestro.

Deputado confuso. Um agente com permissões amplas age a partir de conteúdo que outro agente leu de uma fonte não confiável. A defesa é tratar tudo o que veio de fora como dado e decidir efeitos pelo pedido da pessoa, não pelo conteúdo. Por isso `requested` e `confirmed` em `app/core/action_risk.py` olham o texto do pedido, e POL-004 impede que texto lido entre numa URL.

Efeito repetido. Um piloto que não percebe que já agiu repete a ação. A defesa é estado no executor (`authorize_once`) e não memória do modelo.

Escalada por replanejamento. Um plano reprovado volta, o modelo "corrige" acrescentando passos, a nova versão passa numa política e falha em outra. Limitar a uma nova tentativa e devolver o plano rejeitado junto com o motivo transforma o problema em dado para análise em vez de laço.

Deriva de roteamento. Mudanças no prompt do orquestrador mudam silenciosamente para onde vão pedidos que funcionavam. Sem um conjunto de regressão de roteamento, isso aparece como queixa de usuário semanas depois.

## Como medir

Orquestração tem três camadas de qualidade que precisam ser medidas separadamente: seleção (o agente certo foi escolhido?), processo (os passos foram válidos e seguros?) e resultado (o estado final está certo?). Misturar as três esconde problemas. Um resultado certo com o agente errado é sorte; um processo impecável com resultado errado é uma lacuna de capacidade.

O avaliador offline em `app/core/outcome_grader.py` adota essa separação de forma explícita: seleção, status do processo e resultado do artefato são medidos à parte, e o texto do rastro não conta como evidência do resultado. Para roteamento, `app/scripts/eval_routing.py` monta um gabarito a partir de pedidos reais que deram certo e compara configurações do Maestro por acerto e tempo. Para o caminho inteiro, `app/scripts/eval_conversations.py` percorre cenários do resolvedor ao Maestro, ao alvo de continuação, ao plano do agente e às políticas, usando o mesmo código do app e sem executar os passos.

Na camada de autorização, o modo `shadow` de `app/core/action_risk.py` permite medir antes de impor: o relatório conta quantos efeitos seriam bloqueados, por tipo, e quantas vezes o pedido da pessoa nem mencionava aquele efeito. Esse último número é um sinal direto de agentes acrescentando ações que ninguém pediu.

Outras métricas que valem acompanhar:

| Métrica | Pergunta que responde |
| --- | --- |
| Taxa de reprovação de plano por política | Quais regras o orquestrador mais viola |
| Sucesso após a única nova tentativa | Se o feedback das políticas é acionável |
| Subtarefas bloqueadas por dependência | Quanto uma falha inicial derruba o resto |
| Confirmações pedidas e recusadas | Se o sistema propõe efeitos que a pessoa não quer |
| Latência e custo por salto | Quanto cada agente extra custa |
| Comparação com agente único | Se dividir o trabalho de fato ajudou |

A última linha é a mais negligenciada. A pergunta "multiagente é melhor?" só tem resposta para uma distribuição específica de tarefas, comparando as duas arquiteturas no mesmo conjunto. O artigo da Anthropic sugere começar a avaliar cedo, com poucos casos representativos, porque no início as mudanças têm efeitos grandes e fáceis de ver, e usar avaliação por estado final quando o caminho até ele pode variar legitimamente.

## Como aparece no Creative AIx

| Arquivo | Papel |
| --- | --- |
| `app/agents/maestro.py` | Orquestrador: gate de ambiguidade, atalhos sem modelo, plano por LLM, uma nova tentativa com feedback |
| `app/core/plan_validator.py` | Políticas de aceite do plano e dos passos de cada agente |
| `app/desktop/controller.py` | Condução: atalhos, revisão do plano, laço de subtarefas, dependências, confirmação de efeito |
| `app/core/routing.py` | Decisão única de onde um pedido continua, compartilhada com a avaliação de conversas |
| `app/core/action_policy.py` | Ferramentas permitidas por agente, aplicadas no executor |
| `app/core/action_risk.py` | Porta de efeito: classificação, modos, uma vez por tarefa, relatório |
| `app/core/automation.py` | Executor: recusa de execução arbitrária, autorização e chamada de cada ação |
| `app/core/context_manager.py` | Saídas de uma subtarefa como variáveis para as dependentes |
| `app/agents/subagents.py` | Ajudantes determinísticos entender, montar e conferir, com rastro |
| `app/agents/base_agent.py` | Interface comum dos agentes, modelo e esforço vindos da configuração |
| `app/core/coding_agents.py` | Claude Code e Codex como agentes, confinados à pasta escolhida |
| `app/core/file_contracts.py` | Contrato declarativo do domínio de arquivos |

Na interface, o seletor no alto da Conversa ("Quem atende o pedido") deixa a pessoa escolher entre "Automático", em que o Maestro decide, ou mandar o pedido direto ao Claude Code ou ao Codex. É roteamento manual, e convive com o automático sem mudar as garantias do executor.

## Exercício prático no app

O exercício tem duas partes e serve para ver, na prática, a diferença entre aprovar um plano e autorizar um efeito.

Primeira parte: delegação. Na Conversa, com "Automático" selecionado no seletor do alto, faça um pedido que precise de dois agentes, por exemplo: "pesquise o preço de três notebooks de entrada e monte uma planilha comparando". Acompanhe o registro da tarefa. Observe quantas subtarefas o Maestro criou, para quais agentes, se a segunda declarou dependência da primeira e a linha "Subagentes:" de cada agente, com os ajudantes que passaram ou reprovaram. Anote o que a planilha recebeu da pesquisa e o que se perdeu no caminho.

Segunda parte: permissão no executor. Ligue "Revisar o plano" nas Configurações. Peça algo com efeito externo para um contato seu de teste, como "escreva 'teste do app' para mim mesmo no WhatsApp e envie". Aprove o plano quando ele aparecer. Observe que, ao chegar no passo que envia, o executor pausa de novo e pede confirmação daquele efeito específico. Recuse e veja a tarefa parar antes do envio. Depois, repita sem a palavra "envie" e observe se o plano tenta enviar mesmo assim; se tentar, a política POL-009 deve reprovar.

Para fechar, rode `python app/core/action_risk.py` na raiz do repositório e leia o resumo do registro de autorização: quantos bloqueios houve, de que tipo, e se algum envolveu um efeito que o pedido não mencionava. Responda por escrito: em qual camada cada uma das decisões que você viu foi tomada, e o que aconteceria se aquela camada estivesse só no prompt.

## Erros comuns

Dividir cedo demais. Vários agentes parecem organizados no diagrama, mas cada salto custa latência, tokens e informação. Sem medição contra um agente único, a divisão é aposta.

Confiar na aprovação do plano como autorização de efeitos. O plano diz o que será tentado; o executor vê o rótulo real do botão, a janela real em primeiro plano e o conteúdo real que vai sair. Só ele pode autorizar o efeito.

Deixar o modelo escolher capacidades. Parâmetros como "continue nesta janela", "trabalhe nesta pasta" ou "aja como este agente" devem vir da sessão e do pedido, não de um campo que o modelo preenche.

Repassar a conversa inteira em cada handoff. Além do custo, isso leva conteúdo não confiável para agentes com mais permissões.

Replanejar em laço. Cada nova tentativa sem limite é uma chance a mais de o modelo achar uma forma de passar pelas regras sem cumprir o pedido.

Não versionar as políticas. Uma política sem identificador e sem nota explicando o incidente que a originou vira regra arbitrária, e alguém acaba removendo.

## Para ir além

"ReAct: Synergizing Reasoning and Acting in Language Models" (Yao, Zhao, Yu et al., ICLR 2023) apresenta o laço de raciocínio, ação e observação que está na base de quase todo agente com ferramentas, e ajuda a entender por que separar quem raciocina de quem executa importa.

"How we built our multi-agent research system" (Anthropic, 2025) descreve o padrão orquestrador e trabalhadores em produção, com lições sobre delegação, custo, avaliação e confiabilidade.

"Scaling Managed Agents with stable interfaces" (Anthropic, 2026) trata da separação entre o "cérebro" e as "mãos" do agente por meio de interfaces estáveis.

"Handoffs — OpenAI Agents SDK" (OpenAI, 2025) documenta handoffs como ferramentas, com filtros de histórico e dados estruturados na transferência, um bom contraponto ao pipeline com dependências usado no Creative AIx.
