## Visão geral

Durante muito tempo, a forma mais direta de melhorar a resposta de um modelo de linguagem foi usar um modelo maior ou treinar melhor. Test-time scaling é a outra alavanca: gastar mais computação na hora de responder. Em vez de uma única passada rápida, o sistema pode deixar o modelo raciocinar por mais tempo, gerar várias tentativas e escolher entre elas, ou conferir cada tentativa com um verificador e tentar de novo quando ela for reprovada.

Raciocínio adaptativo é a parte que decide quanto gastar. Uma pergunta trivial não merece o mesmo orçamento que um plano de várias etapas, e um esforço fixo erra para os dois lados: desperdiça no fácil e falta no difícil. Como a ficha deste tema lembra, custo e latência entram na conta. Cada token de raciocínio é cobrado e cada tentativa extra é tempo que alguém passa esperando.

Este texto explica os mecanismos de computação em teste, o que cada um exige para funcionar, como decidir quanto gastar, como medir se o gasto vale a pena, e onde essas escolhas aparecem no Creative AIx. Ele pressupõe o tema anterior da Biblioteca, sobre avaliações e verificadores, porque quase toda estratégia de computação em teste depende de saber reconhecer uma resposta boa.

## Os três eixos

Há três formas básicas de gastar computação na hora de responder. Elas podem ser combinadas, mas têm propriedades diferentes e convém separá-las.

| Eixo | Como funciona | O que exige | Custo típico |
|---|---|---|---|
| Sequencial | Uma tentativa mais longa: raciocínio intermediário antes da resposta, revisão do próprio rascunho | Um modelo que se beneficie de pensar antes; limite de tokens que comporte o raciocínio | Cresce com o tamanho do raciocínio; latência cresce junto |
| Paralelo | Várias tentativas independentes, depois agregação: voto da maioria ou escolha por um verificador | Diversidade entre as tentativas; uma forma de comparar ou julgar respostas | Multiplica pelo número de tentativas; pode rodar em paralelo, então a latência cresce menos |
| Busca guiada | Gerar passo a passo, avaliar ramos parciais e expandir só os promissores | Um verificador que julgue passos intermediários, como um PRM | Alto e difícil de prever; exige infraestrutura própria |

O eixo sequencial é o que a maioria das pessoas encontra primeiro: o modelo escreve passos intermediários antes da resposta final. Ele ajuda em problemas com várias etapas lógicas, em que errar uma etapa compromete o resto. Os modelos atuais costumam fazer isso internamente, num bloco de raciocínio separado do texto da resposta, e as APIs expõem algum controle sobre quanto desse raciocínio é permitido.

O eixo paralelo troca profundidade por amplitude. Em vez de uma tentativa longa, várias tentativas, possivelmente curtas, e uma regra para escolher. A regra mais simples é o voto. A mais forte é um verificador externo.

A busca guiada é o eixo mais sofisticado e o menos comum em produto. Ela depende de julgar soluções incompletas, o que remete aos Process Reward Models do tema anterior. Em matemática há bastante pesquisa sobre isso; em agentes que agem no computador, julgar um passo parcial exige observar o ambiente, e o custo de cada julgamento cresce.

## Self-consistency: o voto da maioria

A primeira leitura da ficha, sobre self-consistency, formalizou uma ideia simples. Em vez de pedir uma resposta com raciocínio passo a passo uma única vez, o sistema amostra vários raciocínios diferentes para a mesma pergunta e fica com a resposta final mais frequente. A intuição é que um problema com resposta certa admite vários caminhos de raciocínio que chegam a ela, enquanto os erros tendem a se espalhar por respostas diferentes. Somar os caminhos favorece a resposta em que eles convergem. No trabalho, a técnica melhorou o desempenho em relação a uma única cadeia de raciocínio em tarefas de aritmética e de raciocínio de senso comum.

Três condições precisam valer para o voto funcionar.

A primeira é que a resposta final seja extraível e comparável. Votar entre números, opções de múltipla escolha ou rótulos curtos é direto. Votar entre cinco versões de um e-mail, ou cinco planos de ação diferentes, não é: duas respostas igualmente boas raramente são iguais palavra por palavra, e decidir se são equivalentes já é um problema de avaliação.

A segunda é que haja diversidade real entre as tentativas. Se o modelo responde sempre da mesma forma, cinco amostras são uma amostra repetida cinco vezes, pagas cinco vezes. A diversidade costuma vir da amostragem com temperatura acima de zero, e é por isso que o controle dessa temperatura importa para quem quer usar voto.

A terceira, menos óbvia, é que os erros não sejam correlacionados. Se o modelo tem uma confusão sistemática, por exemplo uma interpretação errada recorrente do enunciado, a maioria das amostras erra do mesmo jeito e o voto confirma o erro com convicção. Voto reduz ruído, não viés.

Um efeito colateral útil do voto é a medida de concordância. Se quatro de cinco amostras concordam, a resposta é mais confiável do que se as cinco discordam entre si. Essa concordância pode servir de sinal para o raciocínio adaptativo: discordância alta indica pergunta difícil e justifica gastar mais, ou pedir ajuda.

```python
from collections import Counter

def voto(pedido, n):
    respostas = [extrair_final(gerar(pedido)) for _ in range(n)]
    contagem = Counter(normalizar(r) for r in respostas if r is not None)
    if not contagem:
        return None, 0.0
    resposta, votos = contagem.most_common(1)[0]
    return resposta, votos / n          # a concordância vira sinal de confiança
```

Repare em `normalizar`. Sem ela, "10", "10,0" e "dez" contam como respostas diferentes e o voto se fragmenta. A função de normalização é, na prática, parte do verificador, e erros nela distorcem o resultado tanto quanto erros do modelo.

## Verificadores e best-of-N

Quando existe um verificador, o eixo paralelo fica mais forte. Em vez de votar, o sistema gera N tentativas e escolhe a que o verificador aprova, ou a de nota mais alta. Um teste automatizado, um compilador, um validador de esquema ou um modelo de recompensa podem cumprir esse papel. A relação com o tema anterior é direta: a qualidade do resultado fica limitada pela qualidade do verificador.

Se o verificador é perfeito, cada tentativa extra aumenta a chance de pelo menos uma passar, e o ganho é real. Se o verificador é imperfeito, mais tentativas aumentam também a chance de encontrar uma resposta errada que o verificador aprova. Com N grande, o sistema passa a otimizar contra os pontos cegos do verificador: fica com a resposta que melhor engana o juiz, não com a melhor resposta. É o mesmo fenômeno do tema de evals, visto do outro lado.

Há uma variante mais barata do best-of-N que funciona bem quando o verificador explica a reprovação: gerar, verificar e, se falhar, gerar de novo com o motivo da falha anexado ao pedido. Isso é sequencial, não paralelo, e costuma precisar de menos tentativas porque cada nova tentativa sabe o que corrigir. O custo é a latência: as tentativas não podem rodar ao mesmo tempo.

## Escalar com o problema: o que a pesquisa sugere

O segundo trabalho da ficha, sobre escalar a computação em teste de forma ótima, olha a questão do ponto de vista da alocação. Ele estuda dois mecanismos principais: buscar entre várias soluções com a ajuda de um verificador que avalia o processo, e deixar o modelo revisar a própria resposta de forma sequencial. A conclusão central é que a melhor estratégia depende da dificuldade do problema. Em problemas mais fáceis, revisar sequencialmente tende a render mais; em problemas mais difíceis, explorar alternativas em paralelo ou com busca tende a ser melhor. Uma política que escolhe a estratégia conforme uma estimativa de dificuldade usa a computação de forma mais eficiente do que aplicar a mesma estratégia em tudo.

O trabalho também compara gastar computação em teste com usar um modelo maior. A mensagem geral é que, em parte dos problemas, computação em teste bem alocada pode compensar um modelo maior, mas que essa vantagem diminui nos problemas mais difíceis, em que um modelo mais capaz continua fazendo diferença. Os resultados vêm de problemas de matemática com respostas verificáveis.

O terceiro trabalho, s1, ataca o eixo sequencial de forma direta. Ele mostra uma técnica chamada budget forcing para controlar quanto o modelo raciocina na hora de responder. Para encurtar, o sistema força o fim do raciocínio quando o orçamento acaba. Para alongar, quando o modelo tenta encerrar o raciocínio, o sistema impede o encerramento e acrescenta uma palavra como "Wait", o que leva o modelo a continuar e, com frequência, revisar o que tinha feito. O trabalho combina isso com um ajuste fino sobre um conjunto pequeno e curado de exemplos de raciocínio e observa que o desempenho cresce com o orçamento de raciocínio permitido, nas tarefas de matemática e ciências que avaliou.

Duas lições práticas saem dessas leituras. Primeiro, não existe um nível de esforço certo para tudo: a decisão boa é por tarefa ou por classe de tarefa. Segundo, mais raciocínio só vale se houver para onde crescer: se o modelo já acerta com pouco esforço, ou se o problema exige um conhecimento que ele não tem, gastar mais não ajuda.

## Como funciona por dentro: uma política adaptativa

Uma política de raciocínio adaptativo tem quatro peças: uma estimativa inicial de dificuldade, um verificador barato, uma regra de escalonamento e um orçamento que encerra o laço.

```python
def responder(pedido, orcamento):
    esforco = esforco_inicial(pedido)        # sinal a priori: tipo e tamanho do pedido
    gasto, feedback, erros = 0, "", []
    while gasto < orcamento:
        resposta, custo = gerar(pedido + feedback, esforco)
        gasto += custo
        ok, motivo = verificar(resposta)     # independente do texto que o modelo escreveu
        if ok:
            return resposta, {"esforco": esforco, "gasto": gasto, "erros": erros}
        erros.append(motivo)
        if motivo == "truncado":
            esforco = mais_baixo(esforco)    # pensou demais e a resposta não coube
        else:
            esforco = mais_alto(esforco)
        feedback = f"\nTentativa anterior reprovada: {motivo}. Corrija."
    return None, {"esforco": esforco, "gasto": gasto, "erros": erros}
```

Os sinais a priori são o que se sabe antes de chamar o modelo: o tipo do pedido, o tamanho, se é uma continuação de algo já feito, se o agente responsável costuma precisar de raciocínio. Os sinais a posteriori aparecem depois de uma tentativa: o verificador reprovou, a resposta veio truncada, várias amostras discordaram, o modelo devolveu um formato inválido. Uma boa política usa os dois: começa com uma estimativa razoável e corrige com o que observa.

O detalhe do truncamento merece atenção. Em muitas APIs, o limite de tokens da resposta inclui o raciocínio. Um esforço alto num pedido de saída longa pode consumir o limite pensando e cortar a resposta no meio. Nesse caso, a correção certa é reduzir o esforço ou pedir uma resposta mais enxuta, não aumentar. Raciocínio adaptativo não é só subir o esforço; às vezes a decisão certa é descer.

### Um exemplo passo a passo

Imagine um pedido para gerar uma planilha com linhas exatas e uma fórmula de total, e um verificador que abre o arquivo e confere as células.

1. O sistema classifica o pedido como geração de artefato estruturado. A estimativa a priori é esforço médio: há estrutura a respeitar, mas não um raciocínio longo.
2. A primeira tentativa volta com JSON válido, mas uma linha a mais com dados de exemplo. O verificador reprova e explica o motivo.
3. A segunda tentativa recebe o motivo anexado. Volta sem a linha extra. O verificador aprova.
4. O sistema registra duas tentativas, o esforço usado e o motivo da primeira reprovação.

Agora uma variação: o pedido é um site com muitas páginas. Com esforço alto, a primeira tentativa raciocina longamente e a resposta é cortada no limite de tokens. O verificador não consegue nem ler o JSON. Subir o esforço pioraria. A política reduz o esforço, pede uma versão mais enxuta e tenta de novo. Se a segunda também for cortada, ela para e diz à pessoa que o pedido ficou grande demais para uma vez só, em vez de continuar gastando.

## Agentes com ferramentas: o que muda

As leituras deste tema medem principalmente matemática e código, e a ficha avisa que esses resultados nem sempre valem para tarefas com ferramentas. Há motivos concretos para isso.

O primeiro é o efeito colateral. Gerar cinco respostas para uma conta e votar não custa nada além de tokens. Executar cinco vezes uma ação que envia uma mensagem, move um arquivo ou faz uma compra é inaceitável. Em agentes, a computação em teste paralela precisa acontecer no plano, não na ação: gera-se várias propostas de plano, avalia-se cada uma sem executar, e só uma é executada. Isso exige um verificador que julgue planos, o que é mais difícil do que julgar resultados.

O segundo é a resposta aberta. Um plano de ação raramente é igual a outro, mesmo quando os dois estão certos. Voto direto não se aplica; é preciso uma noção de equivalência ou um juiz.

O terceiro é o ambiente que muda. Uma tentativa que falhou pode ter alterado o estado, e a próxima tentativa parte de outro lugar. Repetir às cegas um passo cujo resultado é desconhecido pode duplicar um efeito. Por isso, em agentes, a tentativa extra vem acompanhada de cuidado com idempotência e de registro do que já aconteceu.

O quarto é a latência humana. Em uma conversa por voz ou num pedido rápido, a pessoa está esperando. Uma estratégia que triplica a qualidade em teoria e triplica o tempo de resposta na prática pode piorar a experiência.

## Padrões e anti-padrões

Padrões que costumam funcionar:

- **Esforço por classe de tarefa.** Roteamento e respostas curtas com pouco raciocínio; geração de código e planos complexos com mais.
- **Começar barato e escalar com sinal.** Escalonamento disparado por reprovação do verificador, discordância entre amostras ou formato inválido, e não por padrão.
- **Tentativa nova com o motivo da falha.** Quando o verificador explica a reprovação, a tentativa seguinte deve saber o que corrigir.
- **Teto explícito.** Um número máximo de tentativas e um orçamento em dinheiro ou tempo, com uma saída honesta quando ele acaba.
- **Amostrar planos, não ações.** Em agentes, tentativas múltiplas acontecem antes da execução; a execução é única e passa pela política de permissões.
- **Registrar o gasto real.** Esforço usado, tentativas, motivos de falha, tokens, custo e tempo, para que a política possa ser revista com dados.

Anti-padrões que aparecem com frequência:

- **Esforço máximo em tudo.** Paga caro por tarefas que não melhoram e aumenta a latência de todas.
- **Voto em resposta aberta.** Votar entre textos que nunca são iguais produz empates ou escolhas arbitrárias.
- **Mais tentativas com verificador fraco.** Aumenta a chance de aceitar uma resposta errada que engana o verificador.
- **Retentativa sem mudança.** Repetir a mesma chamada, com o mesmo pedido e o mesmo esforço, esperando outro resultado, quando o erro é sistemático.
- **Subir esforço quando a resposta foi cortada.** Piora o problema quando o limite inclui o raciocínio.
- **Comparar estratégias com orçamentos diferentes.** "Três tentativas com voto" contra "uma tentativa com esforço baixo" não diz nada sobre a estratégia; diz que três chamadas custam mais que uma.

## Como medir

A pergunta certa não é "esta estratégia acerta mais?", e sim "esta estratégia acerta mais pelo mesmo custo?", ou "quanto custa cada acerto a mais?". Toda comparação precisa fixar o orçamento ou reportar o custo ao lado do acerto.

1. **Use casos com resposta conferível.** Sem um verificador confiável, você não sabe se a estratégia melhorou o resultado ou só mudou a forma da resposta.
2. **Fixe o orçamento.** Se a comparação é entre uma tentativa com mais esforço e três tentativas com voto, conte as chamadas e os tokens dos dois lados e reporte ambos.
3. **Meça por caso.** A média esconde onde o ganho está. Muitas tarefas não melhoram com mais esforço; algumas melhoram muito. É essa distribuição que orienta a política adaptativa.
4. **Repita.** Com amostragem, o mesmo caso pode dar resultados diferentes. Uma rodada só não separa efeito de ruído.
5. **Meça latência como distribuição.** Mediana e um percentil alto, porque a cauda é o que a pessoa sente nos piores momentos.
6. **Calcule custo por sucesso.** O custo total dividido pelo número de casos aprovados captura de uma vez o trade-off entre gastar mais e acertar mais.

Uma forma útil de visualizar é uma curva: no eixo horizontal, o gasto (chamadas, tokens ou dinheiro); no vertical, a taxa de acerto. Cada estratégia vira um ponto ou uma linha. A estratégia boa é a que fica acima das outras para o gasto que você aceita pagar. Se duas estratégias se cruzam, a escolha depende do orçamento, e uma política adaptativa pode usar uma em cada faixa.

## Como aparece no Creative AIx

O app não implementa voto da maioria nem busca guiada. O que ele faz é escolher o esforço por agente, desligar o raciocínio onde ele não ajuda, ajustar o esforço por tipo de tarefa em pontos específicos, repetir com o motivo da falha quando um verificador reprova, e medir o resultado com custo e tempo. Cada uma dessas decisões está num arquivo concreto.

### Esforço e raciocínio por agente

O ponto de partida é o `config.yaml` na raiz do repositório. A seção `agent_effort` define o esforço de cada agente: baixo para roteamento, supervisão visual, narração, navegação web e reparo de JSON; médio para planejamento, dados, desktop e arquivos; alto para código. O comentário da seção resume a lógica: baixo para roteamento e respostas curtas, médio para planos simples, alto para código, e o esforço é descrito como a principal alavanca de custo.

A seção `agent_thinking` vai além: para o Maestro, a voz, o resolvedor e a resposta final, o raciocínio é desligado, e a resposta sai direta. O comentário registra que essa decisão foi medida com `app/scripts/eval_routing.py` e com a avaliação de voz, comparando acerto e tempo, e que geração de planilha e código, leitura de arquivo e pilotos continuam com raciocínio, porque ali a qualidade depende dele. É raciocínio adaptativo na forma mais simples: por classe de tarefa, decidido com medição e não por intuição.

Quem aplica essas escolhas é `app/core/ai_client.py`. O cliente só envia o parâmetro de esforço para modelos que o aceitam, e só desliga o raciocínio quando o agente está marcado como "off", o modelo permite e a chamada não tem imagem. Quando o modelo não aceita desligar o raciocínio, o comentário explica que o "off" vira apenas esforço baixo. O cliente também conta respostas cortadas no limite de tokens, num contador de truncamento, e estima o custo de cada chamada incluindo leitura e escrita de cache. O `config.yaml` lembra, nos limites, que o limite de tokens inclui o raciocínio e que valores baixos cortam a resposta no meio do JSON.

### Esforço ajustado pela tarefa e retentativa com verificador

O exemplo mais completo de política adaptativa está em `app/agents/artifact_planner.py`, que gera projetos de código e planilhas como dados estruturados. Três decisões ali correspondem ao que foi descrito neste texto.

A primeira é a estimativa a priori. Para o agente de código, se a análise do pedido indica um site estático ou um script Python pequeno, o esforço cai para médio em vez do alto padrão. O comentário explica o motivo: site estático não ganha com raciocínio longo, e o raciocínio só consumia o limite antes do JSON.

A segunda é o verificador com retentativa. Cada resposta é lida como JSON e passa por um validador de projeto ou de planilha, em `app/core/artifact_builder.py`. Se o validador reprova, o motivo é anexado ao pedido e o modelo tenta mais uma vez, no máximo duas tentativas no total.

A terceira é a descida de esforço por truncamento. Se a reprovação aconteceu porque a resposta foi cortada no limite, o planejador não sobe o esforço: ele reduz para baixo e pede uma versão mais enxuta, com menos arquivos e menos comentários. Se mesmo assim a resposta for cortada, ele para e diz à pessoa que o projeto ficou grande demais para gerar de uma vez. O retorno registra o esforço usado, o número de tentativas e os erros de cada tentativa, o que permite medir a política depois.

O revisor de código, em `app/agents/code_validators.py` e chamado pelo subagente `Reviewer` de `app/agents/subagents.py`, é outro verificador que decide se uma tentativa serve. Ele separa os checks que bloqueiam (truncamento, sintaxe, caminho relativo, programa que não grava nada) dos que só avisam (placeholders, tamanho, vazamento de tema). Essa separação tem efeito direto no gasto: quando todo check bloqueava, o modelo ficava num vai e vem entre correções, consumindo tentativas sem convergir.

### Retentativas na execução

Em `app/core/retry_engine.py` está a retentativa no nível das ações, depois que o plano já existe. Ela não é raciocínio do modelo, mas segue os mesmos princípios de orçamento. Há um número máximo de tentativas e espera crescente entre elas. Um diagnóstico do erro decide a estratégia: esperar e tentar de novo, fechar um diálogo que bloqueia, recuperar o estado, pedir uma ação diferente ao chamador, escalar para outro método ou abortar, como no caso de permissão negada. E há uma memória de falhas: se a mesma ação já falhou repetidamente na sessão, o motor escala direto, sem repetir. É o anti-padrão "retentativa sem mudança" tratado no código.

O registro de tarefas, `app/core/task_ledger.py`, complementa isso com um evento próprio para retentativas e a regra de que um passo iniciado sem fim registrado nunca é repetido às cegas, porque pode ter tido efeito. É a forma como o app lida com a diferença entre tentar de novo uma resposta e tentar de novo uma ação.

### Verificação como custo

O supervisor visual, em `app/agents/vision_maestro.py`, mostra que verificar também é computação em teste. Cada verificação antes ou depois de uma ação de tela custa uma captura e uma chamada ao modelo, com esforço baixo definido no `config.yaml`. Para não pagar isso onde não precisa, o código mantém listas de ações que pulam a verificação visual, como escrever ou ler arquivo, cujo efeito é conferido de outro jeito. A decisão de onde verificar é uma decisão de orçamento.

### Medir no AI Research Lab e nos scripts

O AI Research Lab, em `app/core/lab.py`, permite criar uma versão de um agente que muda só o esforço, entre os valores definidos em `EFFORTS`, ou só o limite de tokens, dentro da faixa aceita por `validate_params`. Essa variante roda os mesmos casos que a versão publicada, numa pasta temporária, e o resumo mostra lado a lado acertos, chamadas, tokens, custo e latência, com a origem de cada métrica. Um experimento pode ter um orçamento em dólares: quando o gasto acumulado chega ao teto, os casos restantes são cancelados e o experimento registra que parou por orçamento.

Entre os scripts, `app/scripts/eval_routing.py` compara o roteamento com e sem raciocínio, reportando acerto, mediana e percentil alto do tempo. `app/scripts/eval_release_artifacts.py` registra, em cada tentativa, o esforço configurado, o esforço efetivamente usado e os erros de cada tentativa interna, com um número de tentativas limitado. `app/scripts/eval_live_turns.py` mantém um teto de gasto acumulado e não começa uma sessão que possa estourá-lo. Todos seguem a mesma regra: custo e tempo andam junto com o acerto.

Uma observação sobre o que o app não expõe: o `effective_config` do Lab anota que a temperatura não é exposta pelo cliente do app, e que o modelo usa o padrão do provedor. Para quem quiser experimentar voto da maioria, isso significa que a diversidade entre as tentativas depende desse padrão, e vale conferir na prática se as respostas realmente variam antes de pagar por várias.

## Exercício prático no app

A ficha propõe um exercício com orçamento fixo, que é a forma correta de comparar estratégias.

1. Escolha cinco pedidos com resposta conferível. Bons candidatos são perguntas sobre arquivos que você mesmo criou, contas com resultado conhecido ou planilhas pequenas cujo total você sabe. Escreva a resposta certa de cada um antes de começar.
2. Defina o orçamento: três chamadas por pedido.
3. Estratégia A: uma única tentativa com mais esforço. No AI Research Lab, crie uma variante do agente que muda só o esforço para alto, ou use um agente que já roda com esforço alto.
4. Estratégia B: três tentativas com o esforço padrão (faça o mesmo pedido três vezes, cada uma partindo do mesmo estado), e a resposta final decidida por voto. Normalize as respostas antes de votar e anote quantas concordaram.
5. Para cada pedido e cada estratégia, registre: acertou ou não, quantas chamadas foram feitas, o custo e os tokens quando o app os mostrar (o resumo do Lab mostra os dois), e o tempo total.
6. Compare por pedido, não só pela soma. Anote em quais pedidos alguma estratégia fez diferença e em quais as duas acertaram ou erraram juntas.

Ao analisar, preste atenção a três coisas. Se as três tentativas da estratégia B quase sempre deram a mesma resposta, o voto não teve diversidade para trabalhar e você pagou três vezes pela mesma resposta. Se a estratégia A acertou os mesmos pedidos que o esforço padrão já acertava, mais esforço não ajudou naquela classe de tarefa. E se alguma estratégia acertou mais, confira se o ganho compensa o tempo de espera.

## Erros comuns

- **Confundir esforço com qualidade.** Mais raciocínio ajuda em problemas com várias etapas; em pedidos simples, só custa.
- **Medir sem orçamento fixo.** Qualquer estratégia que gasta mais tende a parecer melhor se o custo não aparece na comparação.
- **Ignorar a latência.** Mais tempo de resposta é custo para quem espera, especialmente em voz.
- **Votar sem normalizar.** Respostas equivalentes escritas de formas diferentes fragmentam o voto.
- **Confiar num verificador fraco com muitas tentativas.** Quanto mais tentativas, mais o sistema encontra os pontos cegos do verificador.
- **Repetir ações com efeito.** Em agentes, tentativas múltiplas valem para planos e respostas, não para ações que mudam o mundo.
- **Subir o esforço quando a resposta foi cortada.** Se o limite de tokens inclui o raciocínio, a correção é encurtar, não pensar mais.
- **Generalizar de matemática para ferramentas.** Ganhos medidos em problemas com resposta única não se transferem automaticamente para tarefas abertas com ambiente.

## Limites

Os ganhos de computação em teste variam por tarefa e por modelo. Os resultados das leituras foram medidos principalmente em matemática, ciências e código, com respostas verificáveis, e nem sempre valem para tarefas com ferramentas, em que a resposta é aberta, o ambiente muda e as ações têm efeito. O parâmetro de esforço de uma API orienta quanto o modelo raciocina, mas não é um orçamento exato: o modelo decide quanto de fato usa, e o resultado precisa ser medido, não presumido. Estimar a dificuldade de um pedido antes de responder também é imperfeito; uma política adaptativa depende tanto dos sinais que observa depois de cada tentativa quanto da estimativa inicial.

## Para ir além

As leituras da ficha cobrem os três eixos discutidos aqui.

- **Self-Consistency Improves Chain of Thought Reasoning in Language Models**: o voto da maioria sobre vários raciocínios amostrados, e as condições em que ele ajuda.
- **Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters**: alocação da computação em teste conforme a dificuldade, comparando revisão sequencial e busca com verificador, e a comparação com modelos maiores.
- **s1: Simple test-time scaling**: controle do tamanho do raciocínio na hora de responder com budget forcing, e a relação entre orçamento de raciocínio e desempenho.

Para a parte de verificadores, que sustenta quase tudo aqui, volte ao tema anterior da Biblioteca, Agentic Evals & Process Reward Models.
