## Visão geral

Avaliar um agente é responder a uma pergunta que parece simples e quase nunca é: ele fez o que devia? Com um modelo que só responde texto, a pergunta costuma se reduzir a comparar a resposta com um gabarito. Com um agente que planeja, chama ferramentas, mexe em arquivos, abre páginas e conversa com uma pessoa, a resposta certa não está na fala final. Está no mundo depois que o agente terminou: o arquivo foi criado com o conteúdo pedido, a linha certa entrou no banco, nada foi escrito onde não devia.

Este texto trata de duas ideias que se complementam. A primeira é a avaliação agêntica por resultado: fixar tarefas, rodar o agente em condições controladas e conferir o estado final com um verificador independente. A segunda é a avaliação por processo, que olha os passos intermediários. Os Process Reward Models (PRMs) são a forma mais estudada dessa segunda ideia: modelos treinados para dar uma nota a cada passo de uma solução, e não só ao final.

A frase que resume a motivação está na ficha deste tema: agente que diz "pronto" não terminou necessariamente. Se a sua única medida é o que o agente relata, você está medindo a confiança dele, não o sucesso. Tudo o que vem a seguir é, no fundo, uma série de técnicas para separar essas duas coisas.

## Por que avaliar agentes é diferente

Há quatro diferenças que mudam o desenho de uma avaliação quando se passa de um modelo que responde para um agente que age.

A primeira é que o resultado tem efeito. Um agente que move um arquivo altera o disco; rodar o mesmo caso duas vezes sem restaurar o estado inicial produz casos diferentes. Por isso uma avaliação de agente precisa de isolamento: cada tentativa começa de um ambiente limpo e conhecido, e o que acontece nela não vaza para a próxima.

A segunda é que há muitos caminhos certos. Para "organize por tipo os arquivos desta pasta", um agente pode criar as subpastas primeiro e mover depois, ou mover criando as subpastas no caminho. Comparar a sequência de passos com uma sequência de referência pune soluções corretas e diferentes. Comparar o estado final é mais justo, porque é o que a pessoa de fato queria.

A terceira é o não determinismo. O mesmo pedido, ao mesmo modelo, com as mesmas instruções, pode gerar planos diferentes em execuções diferentes. Uma única execução bem-sucedida diz pouco: o agente pode acertar uma vez e errar na seguinte. A avaliação precisa repetir e olhar a distribuição, não só um ponto.

A quarta é que o agente narra o próprio trabalho. O texto final de um agente é produzido pelo mesmo modelo que tomou as decisões, e esse modelo tende a descrever o que pretendia fazer, não necessariamente o que aconteceu. Uma ferramenta que falhou em silêncio, um caminho escrito errado ou um arquivo truncado aparecem no relato como sucesso. É por isso que o texto da execução, por mais detalhado que seja, não é evidência.

## Anatomia de uma avaliação

Vale fixar um vocabulário antes de entrar nos mecanismos. Os nomes variam entre equipes, mas as peças são sempre as mesmas.

| Peça | O que é | Pergunta que responde |
|---|---|---|
| Tarefa (caso) | O pedido, o estado inicial e o critério de sucesso, escritos antes de rodar | O que exatamente estamos pedindo? |
| Ambiente | O mundo onde o agente age: uma pasta temporária, um banco de teste, um navegador isolado | Onde os efeitos ficam contidos? |
| Tentativa (trial) | Uma execução completa do agente numa tarefa | O que aconteceu desta vez? |
| Trajetória (trace) | O registro dos passos: planejado, bloqueado, executado, com parâmetros e resultados | Como o agente chegou lá? |
| Verificador (grader) | O código, modelo ou pessoa que confere o resultado | O estado final está certo? |
| Resultado | Passou, falhou, falhou por ferramenta, indisponível, cancelado | Como contar esta tentativa? |
| Conjunto | Um grupo versionado de tarefas, com a versão registrada em cada experimento | Contra o que estamos comparando? |

Duas observações sobre essa tabela. Primeiro, a tarefa inclui o critério de sucesso. Escrever o critério depois de ver o que o agente fez é a forma mais comum de enganar a si mesmo: sem perceber, você ajusta a régua ao que saiu. Segundo, o resultado tem mais estados do que "passou" e "falhou". Um caso que não rodou porque o provedor estava fora do ar não é uma falha da versão do agente; contá-lo como falha mistura problema de infraestrutura com problema de qualidade e distorce a comparação.

## Resultado e trajetória

A avaliação por resultado pergunta apenas se o estado final está certo. Ela é robusta a caminhos alternativos, fácil de automatizar quando o estado é observável e difícil de enganar quando o verificador é independente. O τ-bench, uma das leituras deste tema, segue essa linha num domínio realista: o agente conversa com um usuário simulado, segue as regras de um domínio de atendimento e chama ferramentas que alteram um banco de dados; o sucesso é medido comparando o estado final do banco com o estado esperado, não pelo que o agente disse na conversa. O mesmo trabalho chama atenção para a consistência: um agente útil precisa acertar a mesma tarefa repetidas vezes, e não só em alguma das tentativas.

A avaliação por resultado tem pontos cegos. Ela não vê um agente que chegou ao estado certo por sorte, depois de passos arriscados. Não vê um agente que apagou e recriou um arquivo quando bastava renomeá-lo. Não distingue um plano que falhou no último detalhe de um plano completamente sem sentido. Quando o objetivo é diagnosticar, ou quando os passos intermediários têm custo ou risco próprios, olhar a trajetória passa a ser necessário.

A avaliação por trajetória julga os passos. Na forma mais simples, são regras sobre o trace: nenhum passo tentou escrever fora da pasta autorizada, nenhum passo repetiu uma ação com efeito sem necessidade, o número de passos ficou dentro do limite. Na forma mais sofisticada, é um modelo que dá nota a cada passo. Aqui entram os PRMs.

### Process Reward Models

Um modelo de recompensa é um modelo que recebe uma solução e devolve uma nota. Um modelo de recompensa por resultado (às vezes chamado ORM) é treinado com rótulos sobre a resposta final: certo ou errado. Um PRM é treinado com rótulos por passo: este passo está correto, este é duvidoso, este está errado. Na hora de usar, o PRM produz uma nota para cada passo, e a nota da solução inteira é alguma agregação dessas notas, por exemplo a do passo mais fraco ou o produto das probabilidades de cada passo estar correto.

O trabalho "Let's Verify Step by Step", também listado na ficha, comparou as duas formas de supervisão em problemas de matemática. A configuração era a seguinte: um modelo gera muitas soluções para o mesmo problema, e o modelo de recompensa escolhe a melhor. A pergunta é qual modelo de recompensa escolhe a solução correta com mais frequência. No estudo, o modelo treinado com supervisão por processo, a partir de rótulos humanos para cada passo, foi mais confiável nessa escolha do que o treinado só com o resultado final. A intuição é que o rótulo por passo diz exatamente onde o raciocínio quebrou, enquanto o rótulo final só diz que quebrou em algum lugar, e uma solução com o passo errado pode até chegar à resposta certa por acaso.

Há três usos práticos para um PRM. O primeiro é reordenar: gerar várias soluções e ficar com a de nota mais alta. O segundo é guiar uma busca: em vez de gerar soluções inteiras, gerar um passo de cada vez, manter só os ramos com nota alta e expandir esses. O terceiro é servir de sinal de treino, recompensando o modelo por passos bons e não só por respostas certas. Os dois primeiros acontecem na hora de responder e se ligam diretamente ao tema seguinte da Biblioteca, Test-Time Scaling.

### Por que PRMs ainda são pesquisa ativa em agentes

A ficha registra o limite com clareza: PRMs foram mais estudados em matemática, e o uso em agentes com ferramentas ainda é pesquisa ativa. Vale entender o porquê, porque isso orienta o que dá para fazer hoje.

Em matemática, um passo é um texto, e a correção dele depende só do que veio antes no próprio texto. Em um agente, um passo é uma ação sobre um ambiente, e a correção depende do estado desse ambiente, que o PRM pode não ver. "Clicar no botão Salvar" é um bom passo se a janela certa está em foco e um passo ruim se um diálogo de confirmação está aberto na frente. Para julgar, o modelo precisa de uma observação do ambiente, e a observação tem custo e pode ser imprecisa.

Além disso, rotular passos de agente é caro e ambíguo. Um passo exploratório que não levou a nada pode ser razoável; um passo que funcionou pode ter sido imprudente. Diferentes avaliadores humanos discordam mais do que em matemática. E qualquer modelo usado como juiz pode ser explorado: se o agente for otimizado contra a nota do PRM, ele aprende a produzir passos que parecem bons para o PRM, o que não é o mesmo que passos bons.

A consequência prática é que, em agentes, a verificação por processo costuma ser feita com regras explícitas e verificadores pontuais por passo (o arquivo existe depois do passo de criar, a tela mostra o que devia depois do clique), e não com um PRM treinado. É exatamente o que o Creative AIx faz, como se verá adiante.

## Tipos de verificador

Qualquer avaliação depende da qualidade do verificador. Um verificador fraco produz números que parecem bons e não significam nada. Há três famílias, com trade-offs bem diferentes.

| Verificador | Pontos fortes | Pontos fracos | Quando usar |
|---|---|---|---|
| Código determinístico | Barato, rápido, reproduzível, difícil de enganar se lê o estado real | Só confere o que alguém pensou em conferir; frágil a formatos | Estado observável: arquivo, conteúdo, banco, código de saída |
| Modelo como juiz | Lida com saídas abertas, texto, estilo | Custa chamadas, varia entre execuções, tem vieses, pode ser enganado | Qualidade de texto, adequação a instruções, quando não há regra simples |
| Pessoa | Melhor referência para o que importa de fato | Lento, caro, inconsistente entre pessoas | Calibrar os outros dois, casos ambíguos, critérios novos |

O padrão que funciona bem é usar código sempre que o estado puder ser lido, modelo como juiz só onde não houver alternativa, e pessoas para calibrar o juiz: pegar uma amostra, comparar a nota do modelo com a nota humana e só confiar no juiz se as duas concordarem o bastante para a decisão em jogo. O texto didático da Anthropic sobre evals de agentes, primeira leitura da ficha, é um bom ponto de partida para organizar essas escolhas.

Um detalhe que costuma passar despercebido: existência não é correção. Conferir que o arquivo foi criado não confere que o conteúdo está certo. Um verificador que aceita "o arquivo existe" como sucesso deixa passar arquivo vazio, truncado ou com o conteúdo de outro pedido. Sempre que possível, o verificador deve conferir conteúdo: um hash, um trecho obrigatório, a estrutura esperada.

## Como funciona por dentro

O núcleo de um harness de avaliação para agentes cabe em poucas linhas. O que importa é a ordem e o que fica de fora.

```python
def rodar_caso(versao, caso, planejador):
    base = pasta_temporaria()                 # ambiente limpo a cada tentativa
    preparar(base, caso["setup"])             # estado inicial conhecido
    trace = []
    plano = planejador(versao, caso["tarefa"])
    for passo in plano["passos"]:
        motivo = politica.autorizar(passo)    # a mesma política do app real
        if motivo:
            trace.append(("bloqueado", passo, motivo))
            break
        ok, saida = executor.rodar(passo)
        trace.append(("executado" if ok else "falha_ferramenta", passo, saida))
        if not ok:
            break
    checks = conferir_estado(base, caso["espera"])   # lê o disco, ignora o trace
    trace.append(("verificado", checks))
    apagar(base)
    return classificar(checks, trace)
```

Repare em três escolhas. O verificador lê o disco e ignora o que o plano disse. A política que autoriza os passos é a mesma do app real, porque testar com uma política mais frouxa mede um agente que não existe. E a pasta é apagada no fim, para que a próxima tentativa não herde nada.

### Um exemplo passo a passo

Considere o caso "mover" do conjunto padrão do AI Research Lab: o pedido é mover `notas.txt` para a subpasta `arquivo`, dentro da pasta do caso. O estado inicial tem um único arquivo, `notas.txt`, com o texto "lista de compras". O critério, escrito antes de rodar, tem três partes: `arquivo/notas.txt` existe, `notas.txt` não existe mais na raiz, e `arquivo/notas.txt` contém "lista de compras".

1. O harness cria uma pasta temporária com duas subpastas, `caso` e `fora`, e grava `notas.txt` em `caso`.
2. O planejador recebe o pedido com o caminho real da pasta e devolve, digamos, um passo `move_file` com origem e destino.
3. A política do executor confere se o passo é permitido para o agente de arquivos e se o caminho está dentro do escopo do pedido. O harness acrescenta uma fronteira própria: todo caminho tem de ficar dentro de `caso`.
4. O executor real move o arquivo. O trace registra o passo como executado.
5. O verificador lê o disco: o destino existe, a origem não existe, o conteúdo bate. Os três checks passam e o caso conta como aprovado.

Agora imagine variações. Se o planejador escreveu o destino com a extensão errada, o passo executa sem erro, o agente diria "pronto", e o verificador reprova porque `arquivo/notas.txt` não existe. Se o planejador tentou mover para fora da pasta do caso, o passo é bloqueado, nada acontece no disco, e o verificador reprova pelo arquivo que continua na raiz. Se o provedor não respondeu, o caso fica indisponível e não entra na taxa de sucesso. Cada uma dessas situações tem uma etiqueta própria, porque cada uma pede uma ação diferente de quem está melhorando o agente.

## Padrões e anti-padrões

Alguns padrões aparecem em quase toda avaliação bem feita.

- **Critério antes da execução.** O caso é escrito com o que precisa existir no final antes de rodar qualquer versão.
- **Verificação independente.** O verificador não recebe o relato do agente como entrada, ou recebe mas não o usa como evidência.
- **Mesmos casos, mesmas condições.** Duas versões só são comparáveis se rodaram o mesmo conjunto, na mesma versão do conjunto, com o mesmo tipo de planejador.
- **Separação entre ajuste e decisão.** Os casos que você usa para melhorar o agente não são os mesmos que decidem se ele melhorou. Sem isso, a melhora pode ser só memorização.
- **Etiquetas de falha específicas.** "Falhou" esconde demais. Falha de planejamento, falha de ferramenta, bloqueio pela política e indisponibilidade pedem correções diferentes.
- **Casos negativos.** Inclua pedidos que o agente deve recusar ou que devem ser bloqueados. Um agente que passa em tudo porque faz tudo o que pedem é um risco, não um sucesso.

E alguns anti-padrões que valem a pena reconhecer de longe.

- **Sucesso declarado.** Contar como aprovado o caso em que o agente disse que terminou.
- **Existência como prova.** Aceitar que o arquivo existe sem conferir o conteúdo.
- **Critério móvel.** Ajustar o que conta como sucesso depois de ver os resultados.
- **Conclusão firme com amostra pequena.** Três casos e uma tentativa cada não sustentam "a versão nova é melhor".
- **Juiz sem calibração.** Usar um modelo para dar nota sem nunca conferir com avaliação humana.
- **Condições diferentes.** Comparar uma versão rodada hoje com o provedor real contra outra rodada semana passada com um planejador simulado.

## Como medir

A métrica principal de uma avaliação por resultado é a taxa de sucesso: casos aprovados sobre casos efetivamente executados. O denominador importa. Casos cancelados ou indisponíveis saem dele, e o relatório deve dizer quantos saíram, para que ninguém leia uma taxa alta calculada sobre metade dos casos.

A taxa sozinha esconde a variação. Rode cada caso mais de uma vez e olhe duas perguntas diferentes. Uma é se o agente consegue resolver o caso em alguma das tentativas, o que mede capacidade. A outra é se ele resolve em todas, o que mede confiabilidade. Para um assistente que age no computador de alguém, a segunda costuma ser a que importa: ninguém quer um agente que move o arquivo certo duas vezes em três.

Compare por caso, não só pela média. Uma versão nova pode ter a mesma taxa da antiga e ter trocado acertos: passou em dois casos novos e passou a falhar em dois que antes passavam. Essas regressões por caso são informação valiosa e somem na média. A regra conservadora é não promover uma versão que piorou em algum caso que a anterior resolvia, a menos que haja um motivo explícito.

Registre custo e latência junto com o acerto. Uma versão que acerta o mesmo número de casos com metade das chamadas é melhor; uma versão que acerta um caso a mais e triplica o tempo pode não ser. E registre a origem de cada número: medido contra o provedor real ou reproduzido a partir de uma gravação. Números simulados servem para testar o harness, não para decidir qual versão publicar.

Por fim, desconfie de amostras pequenas. Com poucos casos, uma diferença de um caso muda a taxa de forma visível e pode ser puro ruído. O relatório deve avisar quando a amostra é pequena, e a decisão deve exigir mais evidência quanto maior for a mudança proposta.

## Como aparece no Creative AIx

O app usa várias dessas ideias, em lugares diferentes. Vale ver cada um com o arquivo correspondente.

### AI Research Lab

O núcleo das avaliações está em `app/core/lab.py`. O Lab guarda versões de um agente (instruções, modelo, esforço, limite de tokens, ferramentas), cada uma com um hash, e conjuntos de avaliação versionados: editar um conjunto gera uma versão nova, e cada experimento registra qual versão usou.

A função `_run_case` implementa o laço descrito acima. Cada caso roda numa pasta temporária com as subpastas `caso` e `fora`. O plano passa pela política real do executor, `authorize` em `app/core/action_policy.py`, e por uma fronteira adicional do experimento que bloqueia qualquer caminho fora da pasta do caso. Os passos rodam no executor real de arquivos, de `app/core/automation.py`. O trace registra planejado, bloqueado, executado, falha de ferramenta e verificado.

A função `_verify` confere o estado final no disco, independente do que o plano disse: arquivos que precisam existir, arquivos que não podem existir, trechos que precisam estar no conteúdo e, no caso de contenção, se nada foi escrito na pasta `fora`. O caso padrão "nao-sair-da-pasta" existe exatamente para isso: um pedido que convida o agente a organizar arquivos, com o critério de que nada pode aparecer fora da pasta autorizada.

A função `summarize` produz, por versão, casos, aprovados, falhas, falhas de ferramenta, bloqueios, indisponíveis, cancelados, taxa de sucesso calculada só sobre os casos executados, latência média, custo e chamadas. Ela também acrescenta avisos: amostra pequena quando há menos casos executados que o mínimo definido em `SMALL_SAMPLE`, e execução incompleta quando algum caso não rodou. A exceção `ProviderUnavailable` garante que provedor fora do ar vira "indisponível", não "falhou".

A promoção de uma versão passa por `promotion_check`. Ela só aceita publicar com evidência: um experimento de origem real, com a versão candidata e a publicada, no conjunto em sua versão atual, com todos os casos rodados, sem nenhum caso que a publicada passou e a candidata falhou, e com taxa de sucesso pelo menos igual. A função `research` automatiza a geração de hipóteses (instruções novas propostas por um modelo a partir das falhas observadas), mas nunca publica: a promoção continua sendo uma decisão da pessoa, e uma rodada simulada não vale como evidência. O `replay_planner` reexecuta o último plano real gravado de cada caso, sem custo, e se não houver gravação o caso fica indisponível em vez de inventar um plano.

### O grader de aceitação offline

O arquivo `app/core/outcome_grader.py` é pequeno e didático. A função `grade` separa três julgamentos que costumam ser misturados: seleção (os agentes escolhidos foram os esperados?), processo (o status da execução está entre os aceitos?) e resultado (os artefatos conferem?). O comentário no topo diz que o texto do trace não é evidência. Na prática, o código lê os arquivos do fixture, recusa caminhos absolutos ou que saiam da raiz, limita o tamanho lido e confere hash ou trecho obrigatório. Há uma linha que resume bem uma das lições deste texto: quando o check não pede nem hash nem conteúdo, o resultado é falso, porque existência sozinha não substitui correção do arquivo. Os testes estão em `app/tests/test_outcome_grader.py`.

### Verificação por passo

No uso normal, fora do Lab, cada ação do executor em `app/core/automation.py` devolve um campo `verified` além de `success`. Mover um arquivo só conta como verificado se o destino existe e a origem não existe mais; criar uma pasta, se a pasta existe; enviar para a lixeira, se o caminho sumiu. Copiar é um caso interessante: o código observa a existência do destino, mas marca como não verificado, porque a igualdade do conteúdo de uma pasta copiada não foi conferida. É verificação por processo feita com regras, passo a passo, sem PRM.

Esse campo chega ao registro durável de tarefas, `app/core/task_ledger.py`. A função `replay` reconstrói o estado da tarefa só a partir dos eventos e separa evidência verificada de evidência apenas relatada. Ela também mantém a lista de passos incertos: passos que começaram e não têm fim registrado. O comentário do arquivo é explícito: um passo nessa situação pode ter tido efeito, então nunca é repetido às cegas. É a versão operacional do princípio "relato não é prova". O mesmo cuidado aparece em `app/core/coding_agents.py`, que trata como falha o caso em que uma ferramenta de código externa diz que gravou um arquivo que não existe no disco.

A verificação por passo no Creative AIx é feita sem um juiz visual a cada ação. Os pilotos de app e de navegador conferem o efeito pela árvore de acessibilidade (a janela ou a página mudou?), o clique por visão no navegador só conta como feito se a página mudar, e arquivos são conferidos no disco, com a marca `verified`. Um supervisor visual que tirava uma captura e perguntava ao modelo antes e depois de cada ação existiu e foi aposentado: custava uma chamada por passo, falhava aberto quando a própria verificação quebrava e chegava a sugerir passos de correção, o que contrariava a regra de que o Vision só olha. A lição vale para qualquer juiz: um verificador que falha fechado trava o agente quando quebra; um que falha aberto deixa passar erros. Conferir pelo estado real (acessibilidade, disco) é mais barato e mais confiável do que perguntar a um modelo o que a tela mostra.

O revisor de código gerado, em `app/agents/code_validators.py`, mostra outro padrão: separar checks que bloqueiam de checks que só avisam. Truncamento, sintaxe, caminho relativo, programa que não grava nada e violação de tecnologia bloqueiam, porque o código não funciona. Placeholders, tamanho de arquivo e vazamento de tema viram avisos. O comentário de `validate_all` explica a razão: quando todos os checks bloqueavam, o modelo ficava num vai e vem, corrigindo um e quebrando outro. Classificar a gravidade é parte do desenho do verificador.

### Scripts de avaliação

A pasta `app/scripts/` reúne avaliações que rodam fora da interface. Algumas merecem menção pelo padrão que ilustram.

- `app/scripts/eval_release_artifacts.py` tem dois conjuntos, `regression` e `holdout`, com pedidos parecidos e valores diferentes. É a separação entre casos de ajuste e casos de decisão. Cada tentativa é conferida lendo o artefato gerado: o HTML tem o título e o cabeçalho pedidos, a planilha tem exatamente as linhas esperadas e um gráfico. O cabeçalho do script avisa que os resultados não medem a capacidade geral do assistente.
- `app/scripts/eval_routing.py` tira o gabarito do histórico real de pedidos que deram certo, com os agentes que de fato resolveram, e mede acerto e tempo do roteamento.
- `app/scripts/eval_voice.py` e `app/scripts/eval_conversations.py` rodam o caminho real do app sem executar ações e conferem o resultado com regras escritas em código.
- `app/scripts/eval_user_layer.py` planta um marcador único nas instruções do usuário e confere se ele aparece na mensagem que seria enviada ao modelo, com casos negativos em que o marcador não pode aparecer. É verificação de estado final aplicada à montagem do prompt.
- `app/scripts/eval_live_turns.py` fixa cenários e critérios antes de comparar variantes e para a rodada antes de passar de um teto de gasto acumulado.

## Exercício prático no app

O exercício proposto na ficha usa o Histórico, e não exige rodar nada novo.

1. Abra o Histórico e escolha três tarefas já executadas. Prefira tarefas com resultado concreto: um arquivo criado, uma planilha montada, uma página aberta.
2. Para cada uma, escreva, antes de olhar o resultado, o que comprovaria o sucesso. Seja específico: o caminho do arquivo, uma coluna que precisa existir, um valor que precisa aparecer, a URL que devia estar aberta.
3. Agora confira o estado final por conta própria, fora do agente: abra a pasta, abra o arquivo, confira o valor.
4. Compare com o que o agente relatou e com a marcação de cada passo no Histórico: evidência verificada ou só relatada.
5. Marque quais tarefas disseram "pronto" sem comprovação, e quais tinham comprovação mas não atendiam ao critério que você escreveu.

Se quiser ir um passo além, abra o AI Research Lab, rode o conjunto padrão de arquivos e abra um caso: o trace mostra o que foi planejado, executado e conferido. Depois escreva um caso novo seu, com estado inicial e critério, e veja como ele se comporta. Repare que o Lab recusa casos cuja tarefa não cite a pasta do caso ou cujos arquivos de preparo saiam dela.

## Erros comuns

- **Medir o relato.** Ler o resumo do agente e contar como sucesso. O resumo é produzido pelo mesmo modelo que agiu.
- **Verificador que confia no trace.** Um verificador que lê a lista de passos executados, em vez do estado, herda todos os erros do agente.
- **Casos fáceis demais.** Um conjunto em que toda versão passa não distingue nada. Inclua casos de borda: pasta vazia, nome com acento, arquivo que já existe no destino.
- **Ignorar a variação.** Uma tentativa por caso esconde instabilidade. Repita, especialmente antes de publicar.
- **Misturar indisponibilidade com falha.** Provedor fora do ar não diz nada sobre a versão do agente.
- **Comparar em condições diferentes.** Versões diferentes do conjunto, origem real contra simulada, dias com instruções do usuário diferentes.
- **Confiar num juiz sem calibrar.** Um modelo como juiz precisa ser comparado com avaliação humana numa amostra antes de decidir alguma coisa.
- **Otimizar contra o verificador.** Se as instruções do agente são ajustadas repetidamente olhando o mesmo verificador, o agente aprende os pontos cegos dele.

## Limites

PRMs foram estudados principalmente em matemática, com passos textuais e respostas verificáveis. Em agentes com ferramentas, a correção de um passo depende do ambiente, a rotulagem é mais cara e mais ambígua, e o uso de PRMs treinados ainda é pesquisa ativa. Avaliação por resultado depende de estado observável: ela funciona bem para arquivos e bancos de dados, e pior para estados de interface gráfica, áudio ou efeitos fora do computador. O próprio `app/core/outcome_grader.py` declara que cobre arquivos e recusas, e não o estado de uma interface ao vivo nem a qualidade de áudio. Nenhum conjunto de casos cobre tudo; uma boa avaliação diz com clareza o que mede e o que deixa de fora.

## Para ir além

As leituras da ficha cobrem os três ângulos deste texto.

- **Demystifying evals for AI agents** (Anthropic): texto didático sobre como montar avaliações de agentes, com foco em tarefas, tentativas e verificadores.
- **τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains**: avaliação de agentes que conversam com um usuário e alteram um banco de dados, com o sucesso medido pelo estado final do banco e atenção à consistência entre tentativas.
- **Let's Verify Step by Step**: comparação entre supervisão por resultado e por processo para modelos de recompensa, em problemas de matemática.

O tema seguinte da Biblioteca, Test-Time Scaling & Adaptive Reasoning, parte daqui: quando existe um bom verificador, gastar mais computação na hora de responder passa a valer a pena, porque é possível gerar várias tentativas e escolher a boa.
