## Visão geral

Um Recursive Language Model (RLM) é uma forma de usar um modelo de linguagem em que a entrada longa deixa de ser colocada inteira no prompt e passa a ser tratada como um ambiente a explorar. O modelo que recebe a pergunta, chamado aqui de modelo raiz, não lê o material de uma vez. Ele recebe uma descrição do que existe (quantos documentos, de que tamanho, com que estrutura), decide o que inspecionar, divide o material em pedaços, delega perguntas menores a novas chamadas de modelo e combina as respostas que voltam. A palavra "recursivo" vem do fato de que cada chamada delegada pode, em princípio, repetir o mesmo procedimento sobre o seu pedaço.

A ideia foi apresentada por Zhang e Khattab em um texto de blog e desenvolvida por Zhang, Kraska e Khattab em um preprint, ambos de 2025. Por ser recente, este artigo trata o RLM como um padrão de projeto promissor, e não como técnica consolidada: a evidência publicada ainda está restrita aos experimentos dos próprios autores, sem replicação independente ampla. O que vale aprender aqui é o raciocínio de engenharia por trás da proposta, ou seja, por que decompor, como limitar a decomposição e como medir se ela ajudou. Esse raciocínio continua útil mesmo que a forma exata do RLM mude nos próximos trabalhos.

Uma forma curta de guardar a ideia: em um uso comum de modelo, o tamanho do prompt cresce com o tamanho da entrada. Em um RLM, o tamanho do prompt de cada chamada cresce com o tamanho da interação (quantas ações o modelo tomou e quanto texto cada ação devolveu), e não com o tamanho do material. A entrada fica do lado de fora, num lugar onde pode ser consultada aos poucos.

## O problema: contexto longo não é contexto lido

Janelas de contexto ficaram grandes, e é tentador concluir que basta colar tudo no prompt. Na prática, caber na janela e ser bem usado são coisas diferentes. O tema Context Engineering & Agent Memory, pré-requisito deste, discute como a qualidade das respostas pode cair quando o contexto cresce, mesmo bem abaixo do limite nominal: a informação relevante fica diluída entre muito texto irrelevante, posições intermediárias recebem menos atenção e tarefas que exigem combinar muitos trechos sofrem mais do que tarefas que exigem achar um trecho só. O blog do RLM usa o termo "context rot" para essa degradação gradual.

Há também o custo. Cada chamada cobra pelos tokens de entrada; se a mesma entrada enorme é reenviada a cada passo de um agente, o custo cresce com o produto entre o tamanho da entrada e o número de passos. E há latência: processar um prompt muito longo leva tempo antes de o primeiro token da resposta aparecer.

Existem várias respostas a esse problema, e o RLM é só uma delas. Vale compará-las antes de escolher.

| Abordagem | O que faz | Onde costuma falhar |
| --- | --- | --- |
| Janela maior | Coloca tudo no prompt e confia no modelo | Diluição da atenção, custo por chamada, tarefas de agregação |
| Busca (RAG) | Seleciona trechos antes de o modelo ler | A seleção acontece sem entender a pergunta a fundo; o que não foi recuperado não existe |
| Resumo progressivo | Resume blocos em sequência e acumula | Cada resumo perde detalhe; erros se acumulam na ordem de leitura |
| Agente com ferramentas de leitura | O modelo abre arquivos sob demanda | Funciona bem, mas o histórico do agente cresce com o que ele leu |
| RLM | O material vira ambiente; o modelo decide o que ler e delega pedaços a novas chamadas | Custo variável, decomposição errada, propagação de erros |

A diferença entre RLM e busca é quem decide o que ler e quando. Na busca, um mecanismo fixo (lexical, vetorial ou híbrido) escolhe os trechos antes de qualquer raciocínio. No RLM, o próprio modelo escolhe, depois de olhar a estrutura do material, e pode mudar de estratégia no meio do caminho. A diferença entre RLM e um agente com ferramentas comuns é o que volta para o contexto do modelo raiz: no RLM, o texto lido por uma sub-chamada fica no contexto dela, e só a resposta curta sobe.

## Anatomia de um RLM

Os componentes abaixo aparecem, com nomes diferentes, em qualquer implementação do padrão. Na implementação descrita pelos autores, o ambiente é um interpretador de código (um REPL Python) em que o material fica guardado como uma variável, e o modelo raiz escreve código para inspecioná-lo e para disparar chamadas de modelo sobre partes dele. Os detalhes exatos da interface estão nas leituras; aqui o foco é a função de cada peça.

| Componente | Função | Decisão de projeto que ele exige |
| --- | --- | --- |
| Modelo raiz | Recebe a pergunta, planeja, decide o que inspecionar e quando terminar | Qual modelo, com quanto esforço de raciocínio |
| Ambiente | Guarda o material fora do prompt e oferece operações baratas: tamanho, fatiar, buscar por padrão, contar | Quais operações existem, se executa código, com que isolamento |
| Sub-chamada | Recebe uma pergunta menor e um pedaço do material; devolve uma resposta curta | Mesmo modelo ou outro menor; se pode recursar de novo |
| Memória de trabalho | Resultados intermediários guardados no ambiente, não no prompt | Formato dos resultados, para que possam ser combinados |
| Sinal de término | Forma explícita de dizer "esta é a resposta final" | O que acontece se o sinal nunca vier |
| Controlador | Conta chamadas, tokens, profundidade e tempo; registra a trajetória | Orçamento global, política de corte, o que é registrado |

Três propriedades decorrem dessa anatomia e explicam por que a abordagem pode funcionar.

A primeira é que cada chamada vê pouco texto. Uma sub-chamada que recebe vinte notas e uma pergunta precisa tem muito menos material concorrendo pela atenção do que uma chamada que recebe duzentas notas e uma pergunta vaga. Se a degradação vem da diluição, reduzir o que cada chamada lê ataca a causa.

A segunda é que operações baratas substituem leitura cara. Contar quantas notas mencionam um fornecedor, listar as datas de todos os arquivos ou achar as linhas que contêm um código de pedido são operações determinísticas, rápidas e exatas. Um modelo que lê tudo para responder "quantas vezes X aparece" gasta tokens e ainda pode errar a conta. Um modelo que escreve uma busca e lê o resultado gasta pouco e acerta.

A terceira é que a decomposição é decidida com informação. O modelo raiz pode olhar a estrutura antes de dividir: se as notas têm data, pode particionar por período; se têm pastas, por tema. Uma divisão fixa em blocos de tamanho igual ignora essa estrutura e pode cortar no meio de um raciocínio.

## Como funciona por dentro: o laço

O núcleo de um RLM é um laço em que o modelo raiz alterna entre agir sobre o ambiente e observar o resultado, até produzir uma resposta final ou esgotar o orçamento. O pseudocódigo abaixo não reproduz a implementação dos autores; ele mostra a estrutura mínima com os controles que um engenheiro precisa colocar.

```python
def rlm(pergunta, material, orcamento, profundidade=0):
    env = Ambiente(material)                  # o texto fica aqui, fora do prompt
    historico = [env.descrever(), pergunta]   # tamanho, estrutura, amostra curta
    while orcamento.resta():
        acao = modelo_raiz(historico, profundidade)
        if acao.tipo == "final":
            return Resposta(acao.valor, trajetoria=orcamento.registro)
        if acao.tipo == "delegar":
            if profundidade + 1 > orcamento.profundidade_max:
                obs = "profundidade máxima: resolva este pedaço sem delegar"
            else:
                pedaco = env.ler(acao.alvo)
                obs = rlm(acao.pergunta, pedaco, orcamento, profundidade + 1)
        else:
            obs = env.executar(acao.operacao)   # fatiar, buscar, contar
        orcamento.gastar(acao, obs)
        historico.append(truncar(obs, orcamento.max_por_observacao))
    return Parcial(historico, motivo="orçamento esgotado")
```

Alguns detalhes desse esqueleto carregam a maior parte da engenharia.

O orçamento é um objeto só, compartilhado por toda a árvore de chamadas. Se cada sub-chamada recebesse um orçamento próprio e novo, o custo total seria o orçamento multiplicado pelo número de nós, e o limite deixaria de limitar. Passar o mesmo objeto adiante faz com que uma sub-chamada que gasta muito reduza o que sobra para as irmãs, que é o comportamento desejado.

A observação é truncada antes de entrar no histórico. Sem isso, uma operação como "mostre o material inteiro" recolocaria no prompt exatamente o texto que o RLM tenta manter fora. O truncamento também é um ponto de perda de informação, e por isso o limite precisa ser medido, não chutado.

Quando a profundidade máxima é atingida, a chamada não falha em silêncio: ela recebe uma instrução explícita para resolver sem delegar. Isso evita que a árvore cresça indefinidamente e deixa claro, no registro, onde o limite agiu.

O fim por orçamento devolve um resultado marcado como parcial, com o motivo. Um sistema que, ao estourar o limite, devolve a última coisa que o modelo escreveu como se fosse a resposta final esconde a falha de quem lê.

### Exemplo passo a passo

Suponha duzentas notas de reunião e a pergunta "quais decisões sobre o fornecedor de embalagens foram tomadas e depois revertidas, e quando?". A resposta exige achar decisões espalhadas, ligar cada decisão à sua reversão e ordenar no tempo. Um fluxo plausível de RLM seria este.

1. O modelo raiz recebe a descrição do ambiente: duzentas notas, cada uma com data e título, tamanho médio, e as três primeiras linhas de algumas notas como amostra. Ele não recebe o corpo das notas.
2. Ele executa uma busca barata pelo nome do fornecedor e por sinônimos prováveis. O resultado é uma lista de notas com o termo, com data. Suponha que sejam trinta e cinco.
3. Ele percebe que trinta e cinco notas ainda é muito para uma leitura de qualidade e particiona por trimestre, resultando em quatro grupos.
4. Para cada grupo, dispara uma sub-chamada com a pergunta "liste as decisões sobre o fornecedor de embalagens neste grupo, com a data e o identificador da nota; não interprete, só extraia". A saída é pedida num formato fixo, uma linha por decisão.
5. As quatro respostas voltam como listas curtas. O modelo raiz as junta no ambiente e ordena por data, com uma operação determinística, sem gastar tokens de modelo.
6. Para cada par candidato (decisão e possível reversão), dispara uma sub-chamada de verificação que recebe só as duas notas envolvidas e responde se a segunda de fato reverte a primeira, citando a frase.
7. Com os pares confirmados, o modelo raiz escreve a resposta final, com as datas e os identificadores das notas de origem.

Repare no que não aconteceu: nenhuma chamada leu as duzentas notas. A busca do passo 2 fez o filtro grosso; as sub-chamadas do passo 4 leram só grupos pequenos; as verificações do passo 6 leram só pares. Repare também no risco: se uma nota relevante não contém o nome do fornecedor (por exemplo, usa só a sigla), a busca do passo 2 a perde, e nada depois a recupera. Esse é o tipo de falha que a medição precisa procurar.

## Padrões de decomposição

O exemplo acima combinou vários padrões. Eles aparecem com frequência e cada um tem um risco característico.

| Padrão | Quando usar | Risco principal |
| --- | --- | --- |
| Filtrar e depois ler | Pergunta com termos identificáveis | Perder o que não usa o termo literal |
| Mapear e reduzir | Pergunta que exige olhar todos os itens | Perder relações entre itens de pedaços diferentes |
| Particionar pela estrutura | Material com data, autor, pasta ou seção | Estrutura enganosa (datas erradas, pastas mal organizadas) |
| Aprofundar onde há dúvida | Respostas parciais com confiança desigual | O modelo julga mal a própria confiança |
| Verificação delegada | Afirmações que podem ser conferidas contra a fonte | Verificador com o mesmo viés de quem extraiu |

Uma distinção ajuda a escolher. Algumas perguntas são do tipo "agulha": a resposta está em um ou poucos lugares, e o trabalho é achá-los. Outras são do tipo "agregação": a resposta depende de praticamente todos os itens (contar, classificar, comparar). Para agulhas, filtrar bem resolve quase tudo, e a recursão pode ser desnecessária. Para agregação, nenhuma busca resolve, porque não há um trecho que contenha a resposta; é aí que mapear e reduzir faz diferença e também onde o custo cresce mais. Pensar em quanta informação a resposta exige, e não só em quanto texto existe, é o primeiro passo para decidir se um RLM vale o custo.

Outra decisão é o formato do que volta de cada sub-chamada. Respostas em texto livre são difíceis de combinar: o modelo raiz precisa ler e interpretar cada uma. Respostas em formato fixo (uma linha por item, com campos definidos, ou um objeto estruturado) podem ser combinadas por código, de forma exata e barata. Sempre que o passo de combinação puder ser determinístico, ele deve ser.

## Orçamento, profundidade e condição de parada

A ficha deste tema lista termos que andam juntos: recursão, decomposição, condição de parada e limite de recursos. Sem os dois últimos, os dois primeiros são um risco.

A profundidade máxima limita quantos níveis a árvore pode ter. O fator de ramificação (quantas sub-chamadas cada nó dispara) limita a largura. O número de chamadas no pior caso cresce como uma potência: com ramificação dez e profundidade dois, são até dez chamadas no primeiro nível e cem no segundo, além das iterações do próprio modelo raiz. Esse crescimento é o motivo pelo qual limitar só a profundidade não basta; é preciso também um teto global de chamadas.

Um orçamento completo costuma ter quatro dimensões: número total de chamadas, tokens (de entrada e de saída, separados, porque têm preços diferentes), tempo de parede e profundidade. Todas são globais para a árvore. Quando qualquer uma se esgota, o controlador encerra a execução e devolve o que tiver, marcado como parcial.

A condição de parada normal é o sinal explícito de resposta final. Mas é bom ter paradas de segurança além do orçamento: o modelo repetiu a mesma ação várias vezes seguidas sem que o ambiente mudasse; uma sub-chamada devolveu algo fora do formato pedido repetidamente; o tempo de uma única sub-chamada passou de um limite. Cada uma dessas paradas deve deixar um motivo legível no registro.

Há ainda uma escolha entre executar sub-chamadas independentes em paralelo ou em sequência. O paralelismo reduz a latência total, mas torna o gasto menos controlável, porque várias chamadas consomem o orçamento ao mesmo tempo. A execução sequencial permite parar cedo quando já há informação suficiente, o que economiza, mas demora mais. Uma regra prática é paralelizar só dentro de um teto de concorrência e checar o orçamento antes de abrir cada lote.

Por fim, o custo de um RLM é variável por natureza: é o modelo que decide quantas chamadas fazer, e perguntas parecidas podem gerar árvores muito diferentes. Isso muda o tipo de garantia que você pode dar. Em vez de "esta pergunta custa tanto", o que se consegue dizer é "nesta amostra de perguntas, a mediana e a cauda do custo ficaram assim, e o teto nunca passa de tanto".

## Modos de falha

Os modos de falha mais comuns se agrupam em quatro famílias.

Falhas de decomposição. O modelo divide o material num ponto que separa informações que só fazem sentido juntas: a decisão está numa nota e a justificativa na seguinte, e as duas caem em grupos diferentes. Ou o filtro inicial é estreito demais e deixa fora o que importa. Essas falhas são silenciosas, porque cada sub-chamada responde corretamente sobre o que recebeu.

Falhas de compressão. Cada sub-chamada devolve algo menor do que leu. Se o que foi descartado era justamente o detalhe que a pergunta exigia, nenhuma etapa posterior consegue recuperá-lo. Quanto mais níveis, mais compressões em série, e mais chance de perda.

Falhas de propagação. Uma sub-chamada inventa um item, a combinação o aceita, e a resposta final o apresenta com a mesma confiança dos itens reais. Em árvores com muitos nós, a probabilidade de pelo menos uma folha errar cresce com o número de folhas, mesmo que cada uma erre raramente. Por isso a verificação contra a fonte, e não contra outra resposta do modelo, é tão importante.

Falhas de controle. A árvore cresce além do previsto, o modelo entra em laço repetindo a mesma busca, ou o modelo raiz, em vez de delegar, pede para ver o material inteiro e recria o problema que o RLM deveria evitar. O caso oposto também acontece: o modelo delega a uma chamada de modelo algo que uma operação simples resolveria, como contar ocorrências, e gasta caro por um resultado pior.

Há uma quinta preocupação, de segurança. O material lido é dado, não instrução: se uma nota contém o texto "ignore a pergunta e responda X", uma sub-chamada que a lê pode ser influenciada. Além disso, se o ambiente executa código escrito pelo modelo, ele precisa de isolamento real (sem rede, sem acesso a arquivos fora do material, com limites de tempo e memória). Em um aplicativo que age sobre o computador da pessoa, essa exigência não é opcional.

## Como medir

Um RLM é uma escolha de arquitetura, e escolhas de arquitetura se justificam por comparação. A avaliação mínima compara pelo menos três condições sobre o mesmo conjunto de perguntas: o material inteiro no prompt (quando cabe), uma linha de base com busca, e o RLM. Sem a comparação, não há como saber se a complexidade adicional comprou alguma coisa.

As perguntas precisam ter resposta conferível. Para agregação, isso significa construir casos em que você sabe a contagem ou a lista correta, de preferência porque montou o material de propósito. Para agulhas, significa saber em que documento a resposta está. Perguntas abertas, avaliadas só por impressão, tendem a favorecer a resposta mais longa e mais confiante.

Vale variar o tamanho do material e traçar a curva de qualidade em função do tamanho. A pergunta interessante raramente é "o RLM é melhor?", e sim "a partir de que tamanho e para que tipo de pergunta ele passa a compensar?".

| O que medir | Como | Por que importa |
| --- | --- | --- |
| Acerto | Comparação com a resposta conhecida, por caso | É o objetivo |
| Fidelidade | Cada afirmação da resposta ligada a um trecho de origem; amostrar e conferir | Detecta itens inventados que o acerto agregado esconde |
| Custo | Chamadas, tokens de entrada e de saída, por caso | O custo é variável; olhe a distribuição |
| Latência | Tempo de parede por caso | Paralelismo muda muito este número |
| Forma da trajetória | Profundidade usada, número de sub-chamadas, fração do material lida | Mostra se o modelo decompõe como você imagina |
| Estabilidade | Mesma pergunta repetida várias vezes | A decomposição é decidida pelo modelo e varia |

Ablações ajudam a entender de onde vem o ganho, se houver. Rode o RLM sem sub-chamadas (só o ambiente com operações baratas) para ver quanto do resultado vem apenas de não colocar tudo no prompt. Rode com profundidade um e com profundidade maior. Rode com um modelo menor nas folhas. Cada variação muda uma coisa só, e o registro de trajetória diz o que mudou no comportamento, não só no resultado.

Por fim, desconfie de amostras pequenas. Com poucas perguntas e variação alta entre execuções, diferenças aparentes podem ser ruído. Repetir cada caso algumas vezes e reportar a dispersão, e não só a média, é o mínimo para uma conclusão honesta.

## Relação com o Creative AIx

O Creative AIx não implementa um RLM. Nenhum agente do app trata uma entrada longa como ambiente executável e dispara chamadas recursivas sobre pedaços dela. Mas várias peças do app resolvem problemas vizinhos, e olhar para elas ajuda a entender o que um RLM mudaria.

Decomposição em um nível. O Maestro (`app/agents/maestro.py`) quebra um pedido em subtarefas, cada uma atribuída a um agente, com dependências declaradas pelo campo `depends_on`. É decomposição planejada de uma vez, antes da execução, e não recursiva: uma subtarefa não gera novas subtarefas. O validador de planos (`app/core/plan_validator.py`) recusa planos com mais de cinco subtarefas, o que funciona como um teto explícito de largura, o mesmo tipo de limite que um RLM precisa ter em cada nível.

Respostas curtas entre etapas. O gerenciador de contexto (`app/core/context_manager.py`) é o que passa o resultado de uma subtarefa para a seguinte. Ele extrai caminhos, URLs e texto, e gera um resumo truncado em torno de 400 caracteres (`_make_summary`), que é o que vai para a variável interpolada na próxima subtarefa. É o mesmo princípio do RLM, em que só uma resposta curta sobe na árvore, e carrega o mesmo risco de compressão: se o detalhe necessário estava depois do corte, a etapa seguinte não o vê.

Busca antes de ler. O segundo cérebro (`app/core/brain.py`, método `context_for`) monta o contexto de cada agente a partir de blocos em ordem de importância (regras do agente, Harness, Diário, skills, playbooks verificados, lições, dicionário) dentro de um orçamento fixo de caracteres, cortando blocos inteiros em vez de frases no meio. Ele registra quais notas de fato entraram no prompt em `last_sources`. Essa é a alternativa de busca descrita no início: a seleção acontece antes de o modelo ler. A busca de texto do Cérebro (`app/core/brain_store.py`, método `search`, sobre um índice SQLite FTS5) é o tipo de operação barata que, num RLM, o modelo raiz usaria como primeiro filtro.

Limites de recursos. O adaptador de agentes de código externos (`app/core/coding_agents.py`) passa um teto de gasto em dólares para o Claude Code (`--max-budget-usd`), tem tempo limite padrão e máximo, e roda o processo filho num Job Object que o encerra com o botão Parar ou no tempo limite. O motor de nova tentativa (`app/core/retry_engine.py`) limita o número de tentativas. São exemplos concretos do controlador que um RLM exigiria: teto global, corte por tempo e motivo registrado.

Trajetória registrada. O registro de tarefas (`app/core/task_ledger.py`) grava um evento antes e depois de cada passo, e os subagentes determinísticos (`app/agents/subagents.py`) devolvem rastros com papel, resultado e resumo. Num RLM, guardar o caminho de cada resposta parcial é o que permite descobrir onde um item inventado entrou.

Medição comparável. O AI Research Lab (`app/core/lab.py`) compara versões de agente nos mesmos casos, registrando chamadas, tokens, custo e latência, com a origem da métrica ("real" ou "simulado") e aviso de amostra pequena. Hoje os experimentos do Lab rodam no domínio de arquivos, que é declarativo e conferível no disco; ele não avalia diretamente uma estratégia de leitura de notas. Mesmo assim, a disciplina dele (mesmos casos, verificação independente do estado final, métrica com origem) é a que um experimento com RLM deveria seguir.

Um ponto de atenção para quem pensar em adotar o padrão no app: a seção de segurança do `README.md` declara que código gerado não é executado. Um RLM no formato descrito pelos autores, com o modelo escrevendo código para um interpretador, entraria em conflito direto com essa regra. Uma versão compatível precisaria oferecer ao modelo um conjunto fechado de operações (listar, buscar, fatiar, delegar) executadas por código do próprio app, e não código livre.

## Exercício prático

A ficha propõe desenhar, no papel ou no Diário do app (`app/core/journal.py` é o módulo que guarda as entradas), um RLM para resumir duzentas notas. O objetivo não é implementar, e sim tornar explícitas as decisões que o padrão exige. Use o roteiro abaixo.

1. Escreva a pergunta exata. "Resuma as notas" é vago demais para ser verificado. Prefira algo como "quais temas aparecem em mais de uma nota, e em quais notas?".
2. Classifique a pergunta: agulha ou agregação? Isso decide se o primeiro passo é um filtro ou uma partição completa.
3. Descreva o que o modelo raiz recebe no início: número de notas, como estão organizadas (pastas, datas), e no máximo uma amostra curta.
4. Defina a partição. Por pasta, por data ou por blocos de tamanho fixo? Justifique em uma frase.
5. Defina o que cada sub-chamada recebe e o formato exato do que devolve.
6. Defina os limites: profundidade máxima, número máximo de chamadas, tamanho máximo de cada resposta parcial e o que acontece quando cada limite é atingido.
7. Defina a verificação.

Um desenho possível, para comparar com o seu:

```text
Pergunta: temas que aparecem em 2+ notas, com as notas de origem.
Tipo: agregação (precisa olhar todas).
Raiz recebe: 200 títulos + pasta + data; nenhum corpo.
Partição: 10 grupos de ~20 notas, por pasta; pastas grandes divididas por data.
Folha recebe: as ~20 notas do grupo + a pergunta.
Folha devolve: uma linha por tema -> tema | nota1; nota2; ... (máx. 15 linhas)
Combinação: código junta as linhas por tema e mantém os que têm 2+ notas.
Profundidade máx.: 2 (uma folha pode dividir o grupo em dois se passar do tamanho).
Chamadas máx.: 25 no total; ao atingir, devolve parcial com os grupos não lidos.
Verificação: sortear 10 pares (tema, nota) e abrir a nota para conferir.
```

Note que a combinação desse desenho é feita por código, e não por mais uma chamada de modelo. Note também a fragilidade dele: temas com nomes diferentes em grupos diferentes ("orçamento" e "custos") não serão unidos pela junção exata. Escreva no Diário como você trataria isso (uma sub-chamada só para normalizar nomes de temas, por exemplo) e quanto isso custaria em chamadas.

Para a verificação, use a busca do app (atalho `Ctrl+K`, segundo o `README.md`) para localizar as notas sorteadas e conferir se o tema está de fato nelas. Anote quantos pares confirmou e quantos não. Se quiser uma linha de base, faça a mesma pergunta usando só a busca e a leitura manual de alguns resultados, e compare o que cada caminho encontrou e o que cada um deixou passar.

## Erros comuns de interpretação

"RLM é contexto infinito." Não é. O material continua finito e o orçamento também. O que muda é que o material não precisa caber num único prompt. O limite passa a ser o orçamento de chamadas e a qualidade da decomposição.

"Mais recursão é mais inteligência." Cada nível adicional é uma compressão a mais e um ponto a mais onde erros entram. Profundidade só ajuda quando o pedaço ainda é grande demais para uma leitura de qualidade; caso contrário, só adiciona custo e risco.

"RLM é o mesmo que RAG." Os dois evitam colocar tudo no prompt, mas a busca seleciona antes de raciocinar e o RLM seleciona enquanto raciocina. Os dois podem ser combinados: a busca vira uma das operações que o modelo raiz usa.

"RLM é o mesmo que um sistema multiagente." Há semelhança na delegação, mas no RLM as sub-chamadas existem para ler pedaços de uma mesma entrada, com respostas curtas e combináveis. Sistemas multiagente costumam dividir por papel ou por ferramenta, e cada agente pode agir sobre o mundo.

"Os resultados do preprint valem para o meu caso." A evidência atual vem dos experimentos dos autores, com as tarefas e os modelos que eles escolheram. Antes de adotar, meça no seu próprio tipo de pergunta, com a sua linha de base.

"Resumo curto é resumo fiel." Uma resposta parcial bem escrita pode omitir exatamente o que importa ou incluir algo que não está na fonte. Fidelidade se confere contra os documentos, não contra a fluidez do texto.

"Se o custo médio está bom, está bom." O custo de um RLM é decidido pelo modelo a cada pergunta. A média pode esconder uma cauda de perguntas muito caras. Olhe a distribuição e garanta um teto.

## Para ir além

As leituras da ficha deste tema, em ordem sugerida:

- **Recursive Language Models (blog)**, Zhang e Khattab, 2025. Apresenta a motivação, a estrutura do ambiente e exemplos de trajetórias. É a melhor porta de entrada.
- **Recursive Language Models**, Zhang, Kraska e Khattab, 2025 (preprint). Formaliza a proposta e traz os experimentos. Leia com atenção a descrição das tarefas, das linhas de base e da profundidade efetivamente usada, porque é isso que define até onde os resultados podem ser generalizados.

Os pré-requisitos ajudam a ler essas fontes com mais critério: **Context Engineering & Agent Memory**, para entender por que contexto longo degrada e como orçamentos de contexto funcionam, e **Test-Time Scaling & Adaptive Reasoning**, para pensar no RLM como mais uma forma de gastar computação na hora da resposta, com os mesmos cuidados de orçamento, verificação e comparação justa.
