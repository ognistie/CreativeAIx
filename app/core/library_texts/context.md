## Visão geral

A cada passo, um modelo de linguagem só sabe o que está escrito na entrada daquela chamada. Não existe memória escondida entre uma chamada e outra: se uma regra, uma preferência ou o resultado de uma ferramenta não está no texto enviado, para o modelo ele não existe. Esse texto é o contexto, e a disciplina de decidir o que entra nele, em que ordem e com que tamanho é a engenharia de contexto.

Memória é o outro lado da mesma moeda. É tudo aquilo que o sistema guarda fora do modelo para poder colocar de volta no contexto mais tarde: o que aconteceu no passo anterior, o que a pessoa disse ontem, um procedimento que funcionou na semana passada. Memória não é um recurso do modelo; é uma decisão de engenharia sobre o que persistir, com que origem, por quanto tempo e sob quais regras de atualização e remoção.

As duas coisas se encontram num ponto: a montagem do contexto. Um sistema de memória excelente que despeja tudo no prompt piora o agente. Um contexto enxuto que esquece a regra mais importante também. Este texto trata dos mecanismos que regem esse equilíbrio, dos modos de falha mais comuns, de como medir a qualidade do que entra no contexto e de como tudo isso aparece no Creative AIx.

## O contexto é um recurso finito

A primeira ideia a internalizar é que janela grande não é o mesmo que atenção uniforme. O texto "Effective context engineering for AI agents", da Anthropic, descreve o contexto como um orçamento de atenção: cada token a mais compete com os outros, e à medida que o contexto cresce a capacidade do modelo de recuperar e usar com precisão uma informação específica tende a cair. O conselho prático que sai daí é procurar o menor conjunto de informação de alto sinal que permita o comportamento desejado.

A pesquisa "Lost in the Middle: How Language Models Use Long Contexts", de Liu, Lin, Hewitt e colaboradores, deu uma forma concreta a esse problema. Em tarefas em que a resposta dependia de um trecho colocado em posições diferentes de um contexto longo, os modelos usaram melhor a informação que estava no início ou no fim do que a que estava no meio. A consequência para quem monta contexto é direta: posição importa. O que é essencial para o passo atual deve ficar perto das bordas, especialmente perto do pedido, e não enterrado entre blocos de referência.

Há também o custo. Contexto maior significa mais tokens processados a cada chamada, o que se traduz em latência e em gasto. Em agentes que fazem muitas chamadas por tarefa, esse custo se multiplica. E trechos irrelevantes não são neutros: eles competem com os relevantes e podem puxar a resposta para o lado errado, por exemplo quando uma nota antiga sobre um caso parecido sugere um caminho que não serve para o pedido atual.

Por fim, existe a questão do cache de prompt. Muitos provedores conseguem reaproveitar o processamento de um prefixo idêntico entre chamadas. Isso recompensa uma organização específica: o que é estável (instruções de sistema, descrição das ferramentas) vem primeiro e não muda; o que é dinâmico (pedido, trechos recuperados, conversa) vem depois. Misturar um trecho dinâmico no meio do prefixo estável invalida o reaproveitamento a cada chamada.

## Anatomia do contexto de um passo

Vale olhar o contexto como uma pilha de camadas, cada uma com uma função e uma regra de inclusão própria.

| Camada | Função | Regra típica de inclusão |
| --- | --- | --- |
| Instruções de sistema | Papel do agente, formato de saída, princípios | Sempre; estável para aproveitar cache |
| Regras do agente | O que fazer e o que evitar neste domínio | Sempre, com limite de tamanho |
| Preferências da pessoa | Estilo, prioridades, informações pessoais | Só se a pessoa escreveu; marcadas como preferência |
| Conhecimento recuperado | Procedimentos, lições, termos | Só o que for relevante ao pedido e verificado |
| Estado da conversa | Pedidos recentes, o que está aberto, pergunta pendente | Os mais recentes; os antigos saem primeiro |
| Resultados de etapas | O que a etapa anterior produziu | Só quando a etapa atual declara depender dela |
| Pedido atual | O que fazer agora | Sempre, perto do fim |

Duas observações sobre essa tabela. A primeira é que cada camada tem um dono diferente: as instruções de sistema são do desenvolvedor, as preferências são da pessoa, o conhecimento recuperado é de uma base curada, e os resultados de etapas vêm do mundo, que pode conter texto não confiável. A segunda é que essa diferença de dono precisa aparecer no próprio texto. Um trecho do diário da pessoa ou o conteúdo de uma página não podem ser lidos pelo modelo como se fossem instruções do sistema.

## Memória: tipos e ciclo de vida

O artigo curto desta Biblioteca separa memória em três tipos. Vale aprofundar, porque cada tipo tem um ciclo de vida diferente e falha de um jeito diferente.

Memória de trabalho é o que importa só nesta tarefa: a lista de arquivos que o agente acabou de ler, o resultado da busca da etapa anterior, o identificador da janela que ficou aberta. Ela nasce e morre com a tarefa. O risco aqui é o vazamento: um resultado longo de ferramenta que é carregado inteiro para todos os passos seguintes, ocupando espaço e trazendo texto externo para perto das decisões.

Memória episódica é o registro do que aconteceu em tarefas anteriores. É útil para não repetir erros, mas é perigosa como guia: o registro de que algo "deu certo" pode ter sido uma declaração do agente e não um fato verificado. Um sistema saudável guarda o registro completo como log e só promove a orientação o que passou por verificação.

Memória procedimental e semântica é o que vale por muito tempo: como fazer um tipo de tarefa, o que nunca fazer, como a pessoa costuma falar, quais são as preferências dela. É a camada que mais influencia o comportamento, e por isso a que mais precisa de proveniência: de onde veio cada item, quando foi atualizado, quem confirmou.

O trabalho "MemGPT: Towards LLMs as Operating Systems", de Packer, Wooders, Lin e colaboradores, propõe olhar esse problema pela lente de um sistema operacional. O contexto do modelo é tratado como memória principal, pequena e rápida, e há armazenamentos externos maiores de onde a informação é trazida e para onde é devolvida por meio de chamadas de função, num movimento parecido com a paginação. A contribuição conceitual é separar claramente o que está no contexto agora do que está guardado, e tornar explícito o mecanismo que move informação entre os dois. Mesmo sem adotar a arquitetura completa, a ideia de camadas com regras de entrada e saída é útil para qualquer agente.

O ciclo de vida de um item de memória durável deveria ter cinco etapas reconhecíveis: registrar com origem, processar (extrair o que interessa), recuperar sob demanda, atualizar sem duplicar e remover ou tornar privado quando a pessoa pedir. Se alguma dessas etapas não existe, o sistema acumula itens que não dá para corrigir, e a memória vira um boato repetido com confiança.

## Como funciona por dentro

A montagem de contexto com orçamento é, no fundo, um problema de seleção sob restrição. Há mais candidatos do que espaço, e é preciso escolher quais entram, em que ordem e o que fazer com o que não cabe. O pseudocódigo abaixo descreve a estratégia usada pelo segundo cérebro do app.

```python
def montar_contexto(agente, pedido, compacto=False):
    blocos = []                                  # já em ordem de importância
    blocos += regras_do_agente(agente)           # com limite por seção
    blocos += instrucoes_da_pessoa(agente)       # marcadas: não ampliam permissões
    blocos += diario_relevante(pedido)           # nunca entradas privadas
    blocos += skills_relevantes(agente, pedido)
    blocos += procedimentos_verificados(pedido)  # só os comprovados
    blocos += licoes(pedido)
    limite = ORCAMENTO // (2 if compacto else 1)
    usados, fontes, tamanho = [], [], 0
    for texto, origem in blocos:
        if tamanho + len(texto) > limite:
            if usados:
                continue                         # pula o bloco inteiro
            texto = cortar_no_fim_de_linha(texto, limite)
        usados.append(texto); fontes += origem; tamanho += len(texto)
    registrar_fontes(agente, fontes)             # só o que entrou de fato
    return "\n\n".join(usados)
```

Algumas decisões merecem explicação. O orçamento é aplicado por bloco inteiro, e não cortando o texto no meio: um bloco cortado pela metade pode perder justamente a frase que dava sentido ao resto, e uma regra truncada é pior do que regra nenhuma. Os blocos são avaliados em ordem de importância, então quando falta espaço quem sai é o menos importante. Um bloco que não cabe é pulado, mas o laço continua, de modo que um bloco menor e posterior ainda pode entrar. E as fontes registradas são só as que de fato foram para o prompt; registrar o que foi considerado, mas descartado, faria a resposta citar uma origem que o modelo nunca leu.

O orçamento é medido em caracteres, não em tokens. É uma aproximação deliberada: contar caracteres é barato, determinístico e não depende do tokenizador do provedor. O preço é alguma imprecisão, que se compensa deixando folga no limite.

### Um exemplo passo a passo

Suponha que a pessoa tenha escrito no Diário, na pasta Notas para os agentes, uma entrada dizendo que a prioridade da semana é o relatório da estufa, e depois peça "monte uma planilha com as tarefas da semana".

1. O agente de Dados vai planejar. Antes de chamar o modelo, o app monta o contexto dele.
2. Entram primeiro as regras do agente, lidas da nota do agente de Dados no vault, com limite por seção.
3. Se a pessoa escreveu instruções para o agente de Dados no Harness, elas entram com um cabeçalho que diz que são preferência de estilo e prioridade e não ampliam permissões.
4. O Diário é consultado. A busca é lexical: compara as palavras do pedido com as de cada parágrafo e do título, calcula uma pontuação, descarta o que fica abaixo de um limiar e pega no máximo um trecho por entrada, para dar variedade. Entradas privadas são ignoradas sempre. Como a entrada está na pasta Notas para os agentes, ela é considerada mesmo com a integração geral do Diário desligada.
5. O trecho recuperado entra com a data e o título da entrada, debaixo de um cabeçalho que diz que aquilo é dado escrito pela pessoa, não instrução, e que nenhuma ação sensível fica autorizada por ele.
6. Entram skills do catálogo relevantes, procedimentos verificados parecidos com o pedido e lições aprendidas, enquanto houver orçamento.
7. As fontes que entraram ficam registradas. Elas vão para a nota do plano no vault, numa linha que lista o que o agente consultou, e o trecho chega ao modelo já com data e título, o que permite à resposta dizer de onde veio a informação sobre a estufa.

Se a pessoa marcar a entrada do Diário como privada, o passo 4 deixa de encontrá-la na próxima montagem. Não é preciso apagar índice nem esperar sincronização: a regra de exclusão roda a cada recuperação.

## Proveniência e o porteiro da memória

Proveniência é saber de onde veio cada item de memória e com que grau de confiança. Ela serve para três coisas: mostrar à pessoa por que o agente fez o que fez, permitir corrigir o item na origem e permitir removê-lo.

Um ponto sutil é que proveniência sozinha não basta; é preciso também uma regra sobre o que pode orientar o agente. Um registro automático de execução diz "esta tarefa terminou com sucesso", mas esse sucesso pode ter sido declarado e não verificado. Se esse registro virar receita, um erro passa a ser repetido com a autoridade de um procedimento. Por isso um bom sistema distingue tipos de memória pela confiabilidade, e não só pelo assunto. Registros ficam como log. Hipóteses ficam fora da recuperação. Procedimentos só orientam depois de comprovados por um verificador independente, como o sistema de arquivos, a árvore de acessibilidade ou uma pessoa. E procedimentos que passam a falhar mais do que funcionam são rebaixados.

Esse desenho tem um custo: memória útil demora mais para virar orientação, porque precisa de evidência. O benefício é que a memória deixa de ser um amplificador de erros.

## Contexto e segurança: dado não é instrução

Todo texto que entra no contexto pode, em princípio, influenciar o modelo. Isso inclui o conteúdo de uma página aberta pelo agente, o texto de um arquivo lido, uma nota do vault e o diário da pessoa. Se esse texto contiver algo que parece uma ordem, o modelo pode segui-la. É o mecanismo básico da injeção de instruções.

A engenharia de contexto não resolve esse problema sozinha, mas ajuda de duas formas. A primeira é rotular: o bloco entra com um cabeçalho que diz o que ele é e que não autoriza ações. No app, a direção do segundo cérebro, as instruções do Harness, a seção Você e os trechos do Diário chegam ao modelo com esse tipo de rótulo. A segunda é limitar o fluxo: texto lido numa etapa não pode ser usado como parte de um endereço na etapa seguinte, porque isso permitiria que uma página injetada fizesse o agente vazar conteúdo pela URL. A proteção definitiva continua sendo o executor, que autoriza ações por regras em código e não por texto. O contexto rotulado reduz a chance de o modelo propor algo errado; o executor garante que a proposta errada não vira efeito.

## Padrões e anti-padrões

Padrões que funcionam:

- Ordem por importância e orçamento por bloco. Quando falta espaço, sai o menos importante, inteiro.
- Prefixo estável, sufixo dinâmico. Instruções fixas primeiro, para aproveitar cache; pedido e recuperação depois.
- Recuperação sob demanda. Em vez de carregar toda a base, buscar o que o pedido menciona. O texto da Anthropic chama isso de recuperação no momento certo, em contraste com pré-carregar tudo.
- Resumo na passagem entre etapas. A etapa seguinte recebe um resumo curto e campos estruturados (caminho, pasta, URL), não a saída bruta.
- Conversa com janela deslizante. Os pedidos mais antigos saem primeiro; o último pedido, o que está aberto e a pergunta pendente nunca saem.
- Rótulo de origem em cada bloco. O modelo e a pessoa sabem de onde veio cada trecho.
- Memória de caminho, não de conteúdo. Lembrar qual rota de agentes funcionou, e não o texto que foi gerado, evita respostas repetidas e evita guardar dados pessoais sem necessidade.

Anti-padrões a evitar:

- Despejar tudo. Carregar o vault inteiro, o histórico completo e todas as saídas de ferramenta porque a janela comporta.
- Cortar no meio. Truncar blocos por caracteres sem respeitar fronteiras de frase ou de item.
- Memória sem origem. Itens que não dá para rastrear, corrigir ou apagar.
- Log virando receita. Registros automáticos usados como procedimento sem verificação.
- Instrução e dado no mesmo nível. Texto externo sem rótulo, lado a lado com as regras do sistema.
- Crescimento sem limite. Memória que só acumula, até ocupar o espaço do pedido.

## Como medir

Medir engenharia de contexto é mais difícil do que medir um harness, porque o efeito aparece no comportamento do modelo, que é ruidoso. Ainda assim, há medições baratas e determinísticas que pegam a maior parte das regressões.

A primeira é a linha de base de recuperação. Para um conjunto fixo de pedidos, grave o contexto que cada agente receberia e as fontes usadas. Toda mudança no código de recuperação ou no vault pode ser comparada com essa linha de base sem chamar o modelo e sem custo. Se uma mudança fez um pedido de planilha passar a receber lições sobre navegador, isso aparece na comparação.

A segunda é a cobertura e a precisão das fontes. Para cada pedido de teste, defina quais notas deveriam ser recuperadas. Meça quantas das esperadas apareceram e quantas das que apareceram eram esperadas. As duas métricas puxam em direções opostas: aumentar o orçamento melhora a cobertura e piora a precisão.

A terceira é a ocupação. Acompanhe o tamanho do contexto por agente e por tipo de pedido, e quanto do orçamento cada camada usa. Uma camada que cresce sem motivo é um sinal de problema.

A quarta são testes de exclusão. Entradas privadas nunca devem aparecer; procedimentos não verificados nunca devem aparecer; registros de execução nunca devem aparecer. Esses testes são binários e devem rodar a cada mudança.

Por fim, há a medição de ponta a ponta: o resultado da tarefa com e sem uma camada de contexto. Ela é a mais cara e a mais ruidosa, e deve ser feita com os mesmos cuidados de uma avaliação de harness, comparando caso a caso e conferindo o estado final.

## Como aparece no Creative AIx

`app/core/brain.py` é o centro da montagem. O método `context_for` reúne, em ordem de importância, as regras e falhas conhecidas do agente, as instruções do Harness, a seção Você, o Diário, as skills, os procedimentos verificados, as lições e termos do dicionário, e aplica o orçamento por bloco inteiro, com metade do limite no modo compacto. As fontes que entraram ficam em `last_sources`, e `append_agent_plan` as escreve na nota do plano como a lista do que o agente consultou. O mesmo arquivo define limites por tipo de conteúdo e deixa claro, no comentário sobre registros de execução, que o log não entra no prompt. `find_references` só devolve procedimentos marcados como verificados e ignora notas retiradas pela curadoria.

`app/agents/maestro.py` mostra a preocupação com cache. As rotas da memória, referências, lições e trechos do Diário vão na mensagem do usuário, e não no prompt de sistema, para não invalidar o prefixo estável. `app/core/ai_client.py` marca esse prefixo para cache. `app/agents/base_agent.py` mostra como cada agente recebe a direção do segundo cérebro com o rótulo de referência que não amplia permissões.

`app/core/session.py` cuida da conversa. O método `context_block` monta os pedidos recentes, o que está aberto e a pergunta pendente; os pedidos mais recentes saem com menos corte, e quando o texto passa do limite os mais antigos são removidos primeiro, nunca o último. `app/core/observer.py` anota na sessão o que ficou aberto depois de cada etapa, que é o que permite resolver referências como "esse segundo vídeo".

`app/core/context_manager.py` é a memória de trabalho entre subtarefas. Ele extrai de cada etapa caminhos, URLs e um resumo curto, e só os injeta na etapa que declara depender daquela. Variáveis que não puderam ser resolvidas viram uma marcação explícita de conteúdo indisponível, em vez de ficarem no texto. A política que impede texto lido de ir para dentro de um endereço fica em `app/core/plan_validator.py`.

`app/core/journal.py` implementa o Diário com o ciclo completo: registro atômico com identificador e versão, extração local, recuperação lexical com limiar, atualização que recalcula os derivados, e privacidade que tira a entrada da recuperação na hora. O bloco que vai para o contexto declara que o texto é dado da pessoa e não autoriza ações.

`app/core/memory_gate.py` é o porteiro. Ele define os tipos de memória (procedimento, restrição, vocabulário, registro e hipótese) e só aceita atualizar um procedimento com evidência de um verificador independente que identifique aquele procedimento. Execução simulada não conta. Falhas repetidas rebaixam o procedimento. `app/core/suggestions.py` complementa: uma lição ou procedimento sugerido pelo app fica pendente, fora do prompt, até a pessoa aprovar, e a aprovação conta como verificação humana. `app/core/vault_curation.py` mantém um manifesto de notas retiradas para que arquivos antigos não desfaçam a curadoria.

`app/agents/memory_agent.py` guarda a memória de rotas: lembra o caminho de agentes, não o conteúdo, redige dados pessoais e deixa esfriar o que não é usado. `app/core/brain_store.py` organiza as duas camadas do vault, a de fábrica e a pessoal, com a pessoal vencendo, e mantém um índice de busca derivado que pode ser apagado sem perda. `app/core/skills.py` escolhe as skills do catálogo pelas palavras do pedido, com limite de tamanho por skill.

Para medir, `app/scripts/eval_brain_retrieval.py` grava a linha de base do contexto que cada agente receberia para pedidos fixos e compara o estado atual com ela, saindo com erro quando algo muda. As notas que alimentam tudo isso estão em `vault/`: regras dos agentes em `vault/10 Agentes/`, procedimentos em `vault/30 Tarefas de referencia/`, skills em `vault/30 Skills/`, lições em `vault/60 Aprendizados/` e o dicionário em `vault/70 Dicionario/`. A ordem de precedência entre essas fontes está em `vault/00 Maestro/Fonte de verdade e precedencia.md`.

## Exercício prático no app

O objetivo é acompanhar um item de memória do registro até o contexto, ver a proveniência e confirmar que a privacidade funciona.

1. Abra o Diário e ligue a opção "Usar na Conversa".
2. Crie uma entrada com uma prioridade fictícia e específica, por exemplo "Prioridade da semana: revisar o inventário da estufa 3". Use palavras que você vai repetir no pedido.
3. Na Conversa, faça um pedido que mencione o assunto, como "monte uma lista das tarefas da semana para a estufa 3".
4. Observe na resposta de onde veio o trecho: a entrada do Diário chega ao modelo com data e título, e a nota do plano em `vault/40 Execucoes/` registra na linha de consultas o que o agente leu. Se a entrada não aparecer, tente um pedido com mais palavras em comum: a recuperação é lexical e tem um limiar mínimo.
5. Volte ao Diário e marque a entrada como privada.
6. Repita o mesmo pedido. A entrada não deve mais aparecer nas fontes nem influenciar a resposta.
7. Como variação, mova uma entrada para a pasta Notas para os agentes, desligue o uso do Diário na Conversa e repita. Essa pasta é considerada mesmo com a integração desligada, desde que a entrada não seja privada.

Ao final, reflita sobre o que você viu: o trecho entrou rotulado como dado, com origem; a privacidade foi aplicada na recuperação, não depois; e em nenhum momento o texto do Diário mudou o que o agente tinha permissão de fazer.

## Erros comuns

Achar que janela grande resolve. Caber não é o mesmo que ser bem usado. Informação no meio de contextos longos tende a ser aproveitada pior, e o excesso tem custo de latência e de dinheiro.

Guardar memória sem origem. Sem data, fonte e versão, um item errado não pode ser corrigido na raiz e continua influenciando respostas.

Promover log a receita. Registro automático de execução é evidência de que algo foi tentado, não de que funcionou. Só verificação independente deve transformar um registro em orientação.

Misturar instrução com dado. Texto lido de uma página, de um arquivo ou do diário precisa entrar rotulado e nunca pode conceder permissão.

Truncar sem critério. Cortar blocos no meio produz regras pela metade. Prefira tirar blocos inteiros, em ordem de importância.

Deixar a memória crescer sem limite. Sem decaimento, curadoria e limites por camada, a memória acaba ocupando o espaço do pedido.

Quebrar o cache por descuido. Inserir um trecho dinâmico no prompt de sistema faz cada chamada pagar de novo pelo prefixo inteiro.

Esquecer o direito de apagar. Se a pessoa não consegue tornar privado ou excluir um item e ver o efeito na próxima resposta, o sistema de memória não está completo.

## Para ir além

Comece por "Effective context engineering for AI agents", da Anthropic. Ele trata o contexto como orçamento de atenção e discute instruções de sistema, ferramentas, recuperação no momento certo e técnicas para tarefas longas, como compactação e notas estruturadas.

Em seguida, leia "Lost in the Middle: How Language Models Use Long Contexts", de Liu, Lin, Hewitt e colaboradores, publicado na TACL. É a referência para entender por que a posição de uma informação no contexto afeta o quanto ela é usada.

Por fim, "MemGPT: Towards LLMs as Operating Systems", de Packer, Wooders, Lin e colaboradores, é um preprint que propõe memória em camadas inspirada em sistemas operacionais. Mesmo que você não adote a arquitetura, a separação entre o que está no contexto e o que está guardado, com um mecanismo explícito para mover informação entre os dois, é uma boa ferramenta mental para projetar a memória de qualquer agente.

Como pré-requisito, se ainda não leu, vale passar pelo tema Harness Engineering desta Biblioteca: o contexto é uma das partes do harness, e muitas das garantias descritas aqui só funcionam porque o executor decide as ações por regras em código.
