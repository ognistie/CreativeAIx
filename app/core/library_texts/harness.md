## Visão geral

Um modelo de linguagem, sozinho, recebe texto e devolve texto. Ele não abre arquivos, não clica em botões e não sabe se o que disse aconteceu de fato. Tudo o que transforma essa saída em trabalho feito no mundo fica do lado de fora do modelo: as ferramentas que ele pode chamar, o código que decide se a chamada é permitida, o ambiente onde a ação acontece, o que volta para o modelo depois de cada passo e a verificação que diz se a tarefa terminou. A esse conjunto damos o nome de harness.

A palavra vem do equipamento de teste: o arnês que prende uma peça para que ela possa ser exercitada e medida com segurança. A analogia é boa porque deixa claro onde mora a responsabilidade. O modelo é a peça capaz e imprevisível; o harness é a estrutura que limita o que ela pode fazer, registra o que fez e confere o resultado. Dois sistemas com o mesmo modelo podem se comportar de maneiras muito diferentes só porque um tem um harness melhor que o outro.

Engenharia de harness é a disciplina de projetar essa estrutura. Ela não substitui a escolha do modelo nem a escrita de bons prompts, mas costuma ser o lugar onde a confiabilidade de um agente é construída. O motivo é simples: o prompt é uma sugestão que o modelo pode seguir ou não; o harness é código que roda sempre do mesmo jeito. Quando um comportamento precisa ser garantido, e não apenas provável, ele pertence ao harness.

Este texto explica as peças de um harness, como elas conversam entre si, os trade-offs de cada decisão, como medir se um harness está bom e onde cada ideia aparece no código do Creative AIx.

## Anatomia de um harness

Um jeito útil de pensar no harness é separá-lo em camadas. Cada camada responde a uma pergunta diferente, e a maior parte dos defeitos de agentes pode ser localizada em uma delas.

| Camada | Pergunta que responde | Exemplo de falha quando está fraca |
| --- | --- | --- |
| Ferramentas | O que o agente consegue fazer? | Uma ferramenta genérica demais permite qualquer coisa e não ensina nada |
| Política | Quem decide se a ação é permitida? | Uma regra escrita só no prompt é ignorada em um caso raro |
| Ambiente | Onde a ação acontece e com que isolamento? | Um teste que escreve fora da pasta prevista contamina o próximo |
| Observação | O que o agente vê depois de agir? | Um erro sem dica faz o modelo repetir a mesma tentativa |
| Estado | O que sobrevive entre passos e quedas? | Uma tarefa interrompida é refeita do zero e duplica um efeito |
| Término | Como provar que acabou? | O agente diz "pronto" e o arquivo nunca foi criado |

### Ferramentas

Ferramenta é a unidade de ação que o modelo pode pedir. O desenho dela define o espaço de erros possíveis. Uma ferramenta estreita, como "mover arquivo de origem para destino", tem poucos parâmetros, um efeito conhecido e uma resposta que dá para conferir. Uma ferramenta larga, como "executar qualquer comando", resolve qualquer problema e não controla nenhum: o executor não sabe o que o comando vai fazer, então não consegue autorizar nem verificar.

A pesquisa do SWE-agent tratou exatamente esse ponto sob o nome de interface agente-computador. Em vez de dar ao modelo um terminal cru, os autores desenharam comandos próprios para ver trechos de arquivo, buscar e editar, com respostas curtas e com uma checagem que recusa edições sintaticamente inválidas antes que elas entrem no arquivo. A conclusão central, medida em benchmarks de engenharia de software, é que a interface do ambiente muda o resultado do mesmo modelo. Ferramenta não é detalhe de implementação; é parte da inteligência do sistema.

### Política

Política é o código que decide se uma ação proposta pode acontecer. O ponto de projeto mais importante aqui é a separação entre quem propõe e quem autoriza. O modelo propõe um plano; o executor, que é código determinístico, decide. Essa separação tem uma consequência de segurança direta: se um texto lido de uma página tentar dar ordens ao agente, o máximo que ele consegue é influenciar a proposta. A autorização continua nas mãos de regras que não leem instruções de texto.

Uma política boa tem três propriedades. É determinística: a mesma entrada produz a mesma decisão. É explicável: cada recusa diz qual regra foi violada e por quê. E é anterior ao efeito: roda antes da ação, não depois.

### Ambiente

O ambiente é o lugar onde as ferramentas agem: o disco, o navegador, as janelas do sistema. Em produção, o ambiente é o computador real da pessoa. Em avaliação, ele precisa ser reproduzível e isolado, como uma pasta temporária criada para cada caso de teste e apagada no fim. Sem isolamento, um caso contamina o seguinte e a medição perde o sentido.

### Observação e feedback

Depois de cada ação, o modelo recebe uma observação. A qualidade dessa observação determina se o agente consegue se corrigir. Um "falhou" sem contexto produz uma nova tentativa igual à anterior. Um erro acionável, como "o caminho precisa estar dentro da pasta pedida", dá ao modelo a informação de que ele precisa para propor outra coisa. A mesma lógica vale para saídas longas: devolver uma tela inteira gasta contexto e esconde o que importa.

### Estado e progresso

Tarefas longas atravessam muitos passos, e às vezes uma queda do processo. O harness precisa guardar, fora do modelo, o que já foi feito. O texto da Anthropic sobre harnesses para agentes de longa duração insiste nesse ponto: manter um registro explícito de progresso, avançar em incrementos pequenos e deixar o ambiente em um estado limpo e compreensível ao fim de cada sessão, para que a próxima retome sem adivinhar. Estado guardado só na memória do modelo some quando a janela de contexto acaba.

### Critério de término

O critério de término é a regra que diz quando a tarefa está concluída. A distinção que importa é entre declarado e verificado. "O agente disse que terminou" é uma declaração. "O arquivo existe, tem três colunas e o cabeçalho certo" é uma verificação. Um harness confiável só marca uma tarefa como concluída com base em evidência independente do relato do agente.

## Como funciona por dentro

O núcleo de quase todo harness é um laço com quatro movimentos: propor, validar, executar e verificar. O pseudocódigo abaixo resume o formato usado no Creative AIx.

```python
def rodar(pedido):
    plano = modelo.planejar(pedido, contexto)
    checagem = validar_plano(pedido, plano)          # regras em código
    if not checagem.aprovado:
        plano = modelo.planejar(pedido, contexto, feedback=checagem.motivos)
        checagem = validar_plano(pedido, plano)      # uma única nova chance
        if not checagem.aprovado:
            return recusa(checagem.motivos)

    for etapa in plano.etapas:
        passos = agente(etapa).propor_passos()
        if not validar_passos(etapa, passos).aprovado:
            registrar_falha(etapa); continue
        for passo in passos:
            motivo = autorizar(agente, pedido, passo)  # ferramenta e efeito
            if motivo:
                pedir_confirmacao(motivo); break
            resultado = executor.rodar(passo)
            registrar(passo, resultado)

    return concluida_se(todos_os_passos_verificados())
```

Repare em três detalhes. Primeiro, a validação acontece duas vezes, em níveis diferentes: uma sobre o plano de alto nível (quais agentes, em que ordem, com que dependências) e outra sobre os passos concretos que cada agente propõe. Segundo, a nova tentativa depois de uma reprovação é limitada a uma, e recebe o motivo literal da reprovação. Isso transforma a política em feedback acionável sem abrir um laço infinito de replanejamento. Terceiro, o resultado final não depende do que o modelo disse, e sim de cada passo ter sido verificado.

### Um exemplo passo a passo

Considere o pedido "crie uma planilha com as colunas Data, Produto e Valor". O caminho dentro do app é aproximadamente este.

1. O Maestro lê o pedido, o resumo da conversa e o que o segundo cérebro sabe sobre pedidos parecidos, e propõe um plano com uma subtarefa para o agente de Dados.
2. As políticas de aceite conferem o plano. Há no máximo cinco subtarefas? O agente existe? Alguma subtarefa usa o resultado de outra sem declarar a dependência? Alguma subtarefa acrescenta um efeito, como enviar ou publicar, que o pedido não fez? Se algo falhar, o Maestro recebe a lista de violações com o identificador de cada política e replaneja uma vez.
3. O agente de Dados propõe os passos. A validação de passos aceita para esse agente apenas a ação declarativa de criar uma pasta de trabalho a partir de um manifesto. Qualquer outra ação, como rodar código, é reprovada antes de tocar no computador.
4. Na execução, o executor confere de novo se a ferramenta está na lista permitida para aquele agente. A conferência na hora da execução existe porque o passo pode ter sido montado por um caminho que não passou pelo validador; a regra fica nos dois lugares de propósito.
5. O construtor de planilhas grava o arquivo e, em seguida, o reabre e compara abas, células e gráficos com o manifesto. O resultado volta marcado como verificado pelo sistema de arquivos, com o caminho do arquivo como evidência.
6. A tarefa só é registrada como concluída e verificada se todos os passos voltaram verificados. Só então a rota usada pode entrar na memória de rotas como algo que funcionou.

Se você rodar o mesmo pedido em modo Simular, os passos 1 a 3 acontecem do mesmo jeito: o plano é proposto, validado, e os passos do agente passam pelas políticas. No passo 4, porém, o executor devolve uma marcação de simulação antes de chamar qualquer ferramenta, inclusive as de leitura, e o registro sai explicitamente como não verificado. Nenhum arquivo é criado, e por isso a execução simulada não conta como evidência para promover procedimentos na memória. Essa diferença é útil: o modo Simular mostra o plano e as decisões de política sem efeito colateral, mas não prova nada sobre o resultado.

## Decisões de projeto e trade-offs

### Fluxo de trabalho ou agente

O texto "Building effective AI agents" faz uma distinção que vale guardar: fluxos de trabalho são sistemas em que o caminho é definido por código, e agentes são sistemas em que o modelo decide dinamicamente os próprios passos. A recomendação é começar pelo mais simples que resolve e só acrescentar autonomia quando ela compensar o custo em latência, previsibilidade e dificuldade de depuração.

No Creative AIx essa ideia aparece como uma escada. Pedidos de abrir algo que existe são resolvidos por dicionário e código, sem chamar o modelo. Rotinas determinísticas vêm antes de automação por árvore de acessibilidade, e visão computacional fica como último recurso. Cada degrau a mais dá flexibilidade e cobra em previsibilidade. Um harness maduro sabe descer a escada sempre que possível.

### Regra no prompt ou regra no código

Escrever "nunca envie mensagens sem confirmação" no prompt é barato e quase sempre funciona. O problema é o "quase". Em um sistema que age no computador de alguém, o caso raro em que o modelo ignora a instrução é exatamente o caso que causa dano. A regra em código custa mais para escrever, exige pensar em como classificar o efeito de uma ação e pode gerar falsos positivos, mas é aplicada sempre.

O trade-off prático é decidir o que precisa ser garantia. Estilo, tom e prioridade podem ficar no prompt. Efeitos difíceis de desfazer, como pagar, enviar, publicar ou excluir, precisam de uma porta em código.

### Rigidez da política

Uma política rígida demais bloqueia tarefas legítimas e ensina a pessoa a desligar a proteção. Uma política frouxa demais não protege. Uma técnica para calibrar é o modo sombra: a política roda, registra o que bloquearia e não bloqueia nada. Depois de um período, você lê o registro e vê quantos bloqueios teriam sido corretos e quantos teriam atrapalhado. Só então liga o modo que efetivamente bloqueia.

### Quantidade de feedback

Devolver mais informação ao modelo nem sempre ajuda. Uma observação longa ocupa contexto, dilui a atenção e pode trazer texto não confiável para dentro do raciocínio. O equilíbrio é devolver o mínimo que permite o próximo passo correto: o resultado, o erro com uma dica de correção, e um indicador de que há mais para buscar, se houver.

### Autonomia mínima

Cada ponto de decisão entregue ao modelo é um ponto onde ele pode errar. Por isso vale perguntar, para cada etapa, se ela precisa mesmo de um modelo. Normalizar um caminho, extrair um termo de busca, conferir se um arquivo existe: tudo isso pode ser código determinístico, sem custo de tokens e sem variação entre execuções.

## Padrões e anti-padrões

Alguns padrões aparecem repetidamente em harnesses que funcionam.

- Propor e validar separados. O modelo escreve um plano estruturado; o código o confere contra regras nomeadas antes de qualquer efeito.
- Lista de ferramentas por papel. Cada agente recebe só as ferramentas do seu domínio. O agente de arquivos não navega; o agente de navegador não roda código.
- Autorização por efeito, não só por ferramenta. Uma ferramenta de clique é inofensiva até o rótulo do botão ser "Comprar". A classificação olha para o que a ação toca.
- Efeito sensível no máximo uma vez por tarefa. Repetir um envio exige nova confirmação, porque a causa mais comum de duplicação é o agente não perceber que já agiu.
- Registro durável antes e depois de cada passo. Um passo iniciado sem fim registrado tem resultado desconhecido e nunca é repetido às cegas.
- Verificação independente do relato. O verificador lê o estado do mundo, não a mensagem do agente.
- Feedback de política como texto acionável. A reprovação vira entrada para o replanejamento, com o identificador da regra.

E alguns anti-padrões que vale reconhecer cedo.

- Ferramenta coringa. Um "executar comando" ou "rodar Python" para tudo elimina a possibilidade de autorizar e verificar.
- Sucesso declarado. Marcar a tarefa como concluída porque o modelo disse "pronto".
- Laço de reparo sem fim. Replanejar enquanto houver erro consome tokens e tempo e, com frequência, converge para a mesma falha.
- Política escondida. Uma recusa que não diz qual regra foi violada não ensina o modelo nem a pessoa.
- Ambiente compartilhado entre testes. Resultados que dependem da ordem em que os casos rodaram.
- Esconder erros do modelo. Engolir exceções para "não assustar" o agente faz com que ele repita a mesma tentativa.

## Como medir

A métrica que importa é o estado final do mundo, conferido de forma independente. Tudo o mais é diagnóstico.

Comece separando três coisas que costumam ser confundidas: a seleção (o sistema escolheu o agente certo?), o processo (os passos rodaram sem erro?) e o resultado (o artefato existe e está correto?). Um processo pode terminar sem erro e produzir o arquivo errado; um processo com um erro intermediário pode, depois de uma recuperação, produzir o arquivo certo. Medir só o processo esconde as duas situações.

Para medir resultado, monte um conjunto de casos com estado inicial conhecido e uma especificação de estado final: quais arquivos devem existir, quais não devem, que texto cada um deve conter, e se algo foi escrito fora do lugar permitido. Rode cada caso em um ambiente novo e confira o estado final com código que não lê a saída do agente.

Ao comparar duas versões de um harness, compare caso a caso, não só a taxa agregada. Uma versão nova pode ter a mesma taxa de sucesso e, ao mesmo tempo, quebrar um caso que a anterior resolvia. Uma regra de promoção conservadora exige que a versão nova não piore em nenhum caso que a anterior passava e que a taxa geral não caia.

Além do resultado, vale acompanhar sinais de custo e de segurança: número de chamadas ao modelo por tarefa, latência, quantas vezes a política bloqueou e, desses bloqueios, quantos eram de efeitos que o pedido nem mencionava. Esse último número é um bom indicador de quanto a política está protegendo contra ações não pedidas.

Por fim, registre a origem de cada métrica. Um número medido com o provedor real e um número produzido por um planejador gravado para teste não são comparáveis, e misturá-los produz conclusões erradas.

## Como aparece no Creative AIx

O harness do app está espalhado por alguns arquivos com papéis bem definidos.

`app/agents/maestro.py` é o planejador de alto nível. O método `analyze` monta o contexto, pede o plano ao modelo e passa o resultado pelas políticas de aceite. Uma reprovação gera exatamente uma nova tentativa, com o texto das violações anexado ao pedido. Antes de chamar o modelo, há um portão de ambiguidade que devolve uma única pergunta quando o pedido é vago, e um atalho determinístico para pedidos de abrir algo, que passa pelas mesmas políticas.

`app/core/plan_validator.py` contém as políticas de aceite. `validate_plan` confere o plano do Maestro: limite de subtarefas, agentes conhecidos, dependências declaradas, conteúdo pedido que não pode ficar vazio nem ser eco do pedido, efeitos externos não pedidos e texto lido que nunca pode ir parar dentro de um endereço. `validate_steps` confere os passos de cada agente, como restringir os agentes de Código e Dados a artefatos declarativos e recusar ferramentas privilegiadas fora do domínio. Cada violação carrega um identificador de política (como POL-003 ou POL-009), e as políticas são descritas em notas de `vault/20 Politicas/`, com um painel que as reúne.

`app/core/action_policy.py` é a autorização por domínio na hora da execução. O dicionário `TOOLS` lista o que cada agente pode chamar, e `authorize` recusa qualquer ferramenta fora dessa lista, além de bloquear atalhos de teclado que abrem superfícies onde digitar executa comandos. O executor em `app/core/automation.py` chama essa autorização antes de cada ação.

`app/core/action_risk.py` é a autorização por efeito. Ela classifica o que uma ação toca (pagar, comprar, transferir, excluir, publicar, enviar, aceitar) e exige confirmação explícita no modo padrão. Os modos de operação ficam em `config.yaml`: desligado, sombra (só registra) e aplicado. A função `authorize_once` impede que o mesmo efeito aconteça duas vezes na mesma tarefa sem nova confirmação, e o registro guarda o rótulo do elemento, nunca o texto digitado.

`app/core/harness.py` é a camada que a pessoa ajusta sem código: instruções por agente, padrão de resposta e aparência, validadas por esquema e com versões para desfazer. O texto entra no contexto explicitamente marcado como preferência que não amplia permissões. Essa é a fronteira que vale entender: o Harness da barra lateral muda o que o modelo lê, não o que o executor permite.

`app/desktop/controller.py` amarra o laço: valida os passos de cada agente com `validate_steps`, registra cada passo no registro durável e só considera a execução verificada quando todos os registros de passo voltaram verificados. `app/core/task_ledger.py` é esse registro durável, gravado antes e depois de cada passo, e `app/core/retry_engine.py` cuida de novas tentativas com espera crescente.

Para o critério de término, `app/core/artifact_builder.py` mostra o padrão de verificação independente: depois de gravar uma planilha, ele a reabre e compara com o manifesto antes de declarar sucesso. `app/core/outcome_grader.py` faz o mesmo de forma offline, lendo artefatos de casos de teste e tratando o texto do trace como algo que não é evidência. `app/agents/subagents.py` mostra a autonomia mínima: ajudantes determinísticos que entendem, montam e conferem sem gastar tokens.

Para medir, `app/core/lab.py` implementa o AI Research Lab. Versões de agente são comparadas em conjuntos de avaliação versionados; cada caso roda numa pasta temporária, passa pela política real e pelo executor real, e o estado final é conferido no disco. A função `promotion_check` só libera a promoção de uma versão com um experimento real recente contra a versão publicada, sem nenhum caso que piorou e sem queda na taxa de sucesso. A nota `vault/00 Maestro/Fonte de verdade e precedencia.md` resume a hierarquia que o código implementa: políticas determinísticas acima do pedido, evidências da execução acima do relato dos agentes.

## Exercício prático no app

O objetivo é ver, na prática, a diferença entre o que o harness permite, o que o modelo propõe e o que de fato aconteceu.

1. Escolha uma tarefa com resultado verificável, por exemplo "crie uma planilha com as colunas Data, Produto e Valor e três linhas de exemplo".
2. Abra o Harness na barra lateral e escreva uma instrução para o agente de Dados, como "use sempre datas no formato dia/mês/ano". Salve. Observe que a instrução é uma preferência: ela entra no contexto do agente, mas não muda a lista de ferramentas.
3. Rode o pedido em modo Simular. Anote o plano: quantas subtarefas, qual agente, que passos. Confira se alguma política reprovou algo e com qual identificador.
4. Rode o mesmo pedido de verdade. Compare o plano com o da simulação. Pequenas diferenças são esperadas, porque o modelo não é determinístico; diferenças de estrutura merecem atenção.
5. Abra o arquivo gerado no disco e confira as colunas, o formato das datas e as linhas. Não use a mensagem de sucesso como prova. Se a mensagem disser que deu certo e o arquivo estiver diferente do pedido, você encontrou exatamente o tipo de falha que um critério de término mais forte pegaria.
6. Como variação, peça algo que o agente de Dados não deveria fazer, como rodar um script, e veja a reprovação e o motivo devolvido.

Se quiser ir um passo além, use o AI Research Lab para criar uma variante com outra instrução e compará-la com a versão publicada nos mesmos casos. Note que a promoção é bloqueada se a variante falhar em algum caso que a publicada resolvia.

## Erros comuns

Medir pela fala do agente. É o erro mais frequente e o mais caro, porque gera confiança onde não há evidência. Toda tarefa que importa precisa de um verificador que leia o estado do mundo.

Confiar no prompt para segurança. Instruções no prompt melhoram a média, mas não protegem a cauda. Efeitos irreversíveis precisam de uma porta em código.

Dar ferramentas genéricas. Uma ferramenta que faz tudo impede autorizar e verificar. Se o agente precisa de uma capacidade nova, prefira criar uma ferramenta específica.

Esconder ou resumir demais os erros. O agente só se corrige com o que vê. Um erro acionável vale mais do que um prompt mais longo.

Mudar várias coisas ao mesmo tempo. Trocar o modelo, a instrução e a ferramenta numa só rodada torna impossível saber o que ajudou. Mude uma variável por vez e compare caso a caso.

Confundir simulação com prova. O modo Simular mostra decisões, não resultados. Ele é ótimo para depurar o plano e a política, e inútil como evidência de que a tarefa funciona.

Repetir passos de resultado desconhecido. Se o processo caiu no meio de um envio, repetir o passo pode duplicar o efeito. O registro durável existe para que essa decisão seja consciente.

## Para ir além

Comece por "Building effective AI agents", da Anthropic. Ele organiza a diferença entre fluxos de trabalho e agentes, apresenta padrões como encadeamento, roteamento e orquestração, e defende começar simples. É a melhor base para decidir quanta autonomia um sistema precisa.

Depois leia "Effective harnesses for long-running agents", também da Anthropic, para ver como estado explícito de progresso, trabalho incremental e verificação ponta a ponta mantêm um agente produtivo ao longo de muitas sessões.

Por fim, "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering", de Yang, Jimenez, Wettig e colaboradores, publicado na NeurIPS 2024, mostra com medição que o desenho da interface entre agente e ambiente muda o desempenho do mesmo modelo. Ele é a ponte natural para o tema seguinte da Biblioteca, Agent-Computer Interface.
