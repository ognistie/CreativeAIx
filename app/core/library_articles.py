"""
Textos da Biblioteca: um artigo por tema, em portugues, para ler antes das referencias.

Cada artigo tem secoes curtas (titulo + paragrafos). O conteudo explica o conceito com as palavras do app e
aponta onde ele aparece no Creative AIx; as fontes primarias ficam no fim da pagina (core/library.py).
Afirmacoes sobre pesquisa sao gerais e as fontes estao listadas; numeros especificos so com fonte.
"""

ARTICLES = {
    "harness": [
        {"h": "O que é", "p": [
            "Um modelo de linguagem sozinho só produz texto. O que transforma esse texto em trabalho feito é o harness: "
            "o conjunto de ferramentas que o modelo pode chamar, as regras que limitam essas chamadas, o ambiente onde "
            "elas acontecem e o retorno que o modelo recebe depois de cada passo.",
            "Pense no harness como a bancada de um técnico. O técnico pode ser excelente, mas sem as ferramentas certas, "
            "sem luz e sem um jeito de medir o resultado, ele trabalha às cegas. Dois agentes com o mesmo modelo podem "
            "ter desempenhos muito diferentes só porque um tem uma bancada melhor que o outro.",
            "Por isso a engenharia de harness virou uma disciplina própria: ela cuida de tudo o que fica em volta do "
            "modelo, e é onde a maior parte da confiabilidade de um agente é construída."]},
        {"h": "As quatro partes", "p": [
            "Ferramentas: o que o agente pode fazer (abrir um site, mover um arquivo, criar uma planilha). Quanto mais "
            "claras e específicas, menos o modelo inventa. Uma ferramenta 'mover arquivo' com origem e destino é mais "
            "segura e mais fácil de acertar do que uma ferramenta 'rodar qualquer comando'.",
            "Regras: o que ele não pode fazer, e quem decide. No Creative AIx as regras ficam no código do executor; o "
            "modelo só propõe. Uma instrução no prompt pode ser ignorada ou contornada; uma regra no código não.",
            "Retorno: o que o agente vê depois de agir. Um erro com dica de correção ensina mais do que um 'falhou'. "
            "Quando o retorno é bom, o agente se corrige no passo seguinte em vez de repetir a mesma tentativa.",
            "Critério de término: como provar que acabou. 'O arquivo existe e tem 3 colunas' é um critério; 'o agente "
            "disse que terminou' não é."]},
        {"h": "Um exemplo passo a passo", "p": [
            "Imagine o pedido 'organize a pasta Downloads por tipo'. Sem harness, o modelo descreveria o que faria. Com "
            "harness, ele primeiro lista a pasta (ferramenta de leitura), recebe a lista real, propõe um plano com "
            "movimentos concretos e envia esse plano ao executor.",
            "O executor confere se cada caminho está dentro da pasta pedida, se nenhum arquivo vai ser sobrescrito e se "
            "alguma ação precisa da sua confirmação. Depois de mover, ele lista de novo e compara com o esperado. Só então "
            "a tarefa é marcada como concluída, com a evidência guardada no Histórico."]},
        {"h": "Como aparece no app", "p": [
            "O Harness da barra lateral é a parte do harness que você ajusta sem código: instruções por agente, padrão "
            "das respostas e aparência. As ferramentas e as regras de segurança ficam no executor e não mudam por "
            "preferência.",
            "No AI Research Lab você cria uma versão com outras instruções, compara com a atual nos mesmos casos e vê, no "
            "disco, qual acertou mais. Se a nova versão não piorar em nenhum caso, você pode promovê-la."]},
        {"h": "Erros comuns", "p": [
            "Medir pelo que o agente fala em vez do estado final. Dar ferramentas genéricas demais: um 'executar "
            "comando' resolve tudo e não controla nada. Esconder os erros do modelo, que então repete a mesma tentativa. "
            "E mudar várias coisas de uma vez, o que impede saber qual mudança ajudou."]},
    ],
    "context": [
        {"h": "O que é", "p": [
            "Contexto é tudo o que o modelo lê antes de responder: o pedido, a conversa, as regras, trechos de notas e o "
            "resultado das ferramentas. Engenharia de contexto é decidir o que entra, em que ordem e quanto espaço cada "
            "parte ocupa.",
            "Memória é o que sobrevive entre um passo e outro, ou entre sessões. Ela só é útil se der para saber de onde "
            "veio, corrigir quando estiver errada e apagar quando a pessoa pedir. Memória sem origem é um boato que o "
            "agente repete com confiança."]},
        {"h": "Por que menos pode ser mais", "p": [
            "Janelas de contexto grandes não garantem atenção uniforme. Pesquisas mostram que modelos aproveitam pior a "
            "informação que fica no meio de contextos longos. Por isso vale escolher poucos trechos relevantes e colocá-los "
            "perto do pedido, em vez de despejar tudo.",
            "Cada trecho também custa: tokens a mais significam respostas mais lentas e mais caras. E trechos irrelevantes "
            "não são neutros; eles competem com os relevantes e podem puxar a resposta para o lado errado."]},
        {"h": "Os tipos de memória", "p": [
            "Memória de trabalho: o que importa só nesta tarefa, como a lista de arquivos que o agente acabou de ler. "
            "Some quando a tarefa termina.",
            "Memória de longo prazo: preferências, regras e lições que valem para sempre, como 'prefiro respostas curtas' "
            "ou 'nunca mexa na pasta Fotos'. Precisa de origem, data e um jeito fácil de editar.",
            "Memória episódica: o que aconteceu em tarefas anteriores. Ajuda a não repetir erros, mas deve entrar resumida "
            "e só quando for parecida com o pedido atual."]},
        {"h": "Como aparece no app", "p": [
            "O Segundo Cérebro monta o contexto em blocos com orçamento: regras do agente, suas instruções do Harness, a "
            "seção Você, skills, playbooks e lições. Cada bloco guarda a origem, e a resposta mostra o que foi consultado.",
            "No Diário, a pasta 'Notas para os agentes' entra sempre no contexto; as outras pastas só quando você liga "
            "'Usado na Conversa'. Entradas privadas nunca entram, e tudo chega marcado como dado de referência: uma frase "
            "escrita no Diário nunca vira permissão."]},
        {"h": "Erros comuns", "p": [
            "Guardar memória sem origem, que depois não dá para corrigir. Misturar instruções com dados lidos de fora, "
            "abrindo espaço para que um texto de uma página dê ordens ao agente. E deixar a memória crescer sem limite até "
            "ocupar o espaço do pedido."]},
    ],
    "aci": [
        {"h": "O que é", "p": [
            "Agent-Computer Interface é o contrato entre o agente e as ferramentas: o nome de cada ação, os parâmetros, o "
            "formato da resposta e o jeito como os erros chegam. É o equivalente, para modelos, do design de interface "
            "para pessoas.",
            "Uma pessoa olha uma tela e entende o contexto pelo layout. Um modelo só tem o texto da descrição e o que a "
            "ferramenta devolve. Se essa conversa for confusa, o agente erra mesmo sendo capaz."]},
        {"h": "O que faz uma boa ferramenta", "p": [
            "Um nome que diz o que faz; poucos parâmetros, cada um com tipo e exemplo; uma resposta curta com o que "
            "importa; e erros acionáveis, que dizem o que corrigir ('o caminho precisa ser absoluto') em vez de só "
            "'inválido'.",
            "Ferramentas pensadas para humanos costumam devolver telas inteiras ou mensagens longas. Para um modelo isso "
            "vira ruído: ele gasta contexto e perde o fio. Uma boa ferramenta corta a resposta ao essencial e diz quando "
            "há mais para buscar."]},
        {"h": "Um exemplo de antes e depois", "p": [
            "Antes: uma ferramenta 'arquivo' com um parâmetro 'ação' que aceita qualquer texto e devolve o conteúdo "
            "inteiro da pasta. O modelo precisa adivinhar as ações válidas e se perde em listas enormes.",
            "Depois: ferramentas separadas para listar, mover e copiar, cada uma com os campos obrigatórios e exemplos. "
            "A listagem devolve no máximo algumas dezenas de itens e avisa quantos ficaram de fora. Um erro diz qual campo "
            "faltou e mostra um exemplo correto. O mesmo modelo passa a acertar mais, sem trocar nada nele."]},
        {"h": "Como aparece no app", "p": [
            "O agente de Arquivos usa ferramentas declarativas (listar, mover, copiar, criar pasta), cada uma com os "
            "campos que exige, validadas antes de rodar. O servidor MCP do app expõe ferramentas só de leitura para o "
            "Claude Code e o Codex, com esquema de entrada.",
            "No Harness, a ficha de cada agente lista as ferramentas que ele pode usar, para você saber o que esperar."]},
        {"h": "Erros comuns", "p": [
            "Parâmetros ambíguos como 'alvo'; saídas sem limite de tamanho; e erros que não dizem como seguir, fazendo o "
            "agente tentar de novo do mesmo jeito. Também é comum ter ferramentas demais com funções parecidas, o que "
            "confunde a escolha."]},
    ],
    "orchestration": [
        {"h": "O que é", "p": [
            "Orquestração é dividir um pedido entre agentes especializados: quem planeja, quem pesquisa, quem mexe em "
            "arquivos. Envolve roteamento (para quem vai cada parte), handoffs (a passagem de uma etapa para outra) e "
            "contratos (o que cada um recebe e entrega).",
            "Separar o cérebro das mãos significa que o modelo que pensa não é quem age. Ele propõe; um executor com "
            "regras próprias decide se aquela ação pode acontecer."]},
        {"h": "Por que separar", "p": [
            "Um modelo pode ser convencido por um texto que leu numa página. Se ele mesmo executasse, esse texto viraria "
            "ação. Com a separação, o executor confere o dono da ferramenta, o escopo e se o efeito precisa de "
            "confirmação, e nada disso depende do que o modelo achou.",
            "A separação também facilita testar: o plano é um objeto que dá para inspecionar, comparar e repetir, em vez "
            "de uma sequência de ações já feitas."]},
        {"h": "Quando usar vários agentes", "p": [
            "Vários agentes ajudam quando as partes do pedido exigem ferramentas e conhecimentos diferentes, como pesquisar "
            "na web e depois montar uma planilha. Cada agente recebe só as ferramentas da sua parte, o que reduz o estrago "
            "possível de um erro.",
            "Para pedidos simples, um agente só costuma ser melhor: menos passagens, menos lugares para perder informação "
            "e menos custo. A regra prática é começar simples e dividir só quando medir que dividir ajuda."]},
        {"h": "Como aparece no app", "p": [
            "O Maestro lê o pedido e monta o plano; cada etapa vai para um agente. O plano passa pelas políticas de aceite "
            "em código antes de rodar. Enviar, publicar, comprar, pagar e excluir pedem sua confirmação no executor, mesmo "
            "com o plano aprovado.",
            "Você também pode escolher no alto da Conversa quem atende o pedido: o Maestro decide, ou o pedido vai direto "
            "ao Claude Code ou ao Codex."]},
        {"h": "Erros comuns", "p": [
            "Agentes demais para tarefas simples; handoffs sem contrato, em que o próximo agente não sabe o que recebeu; e "
            "autorização escrita no prompt em vez de no código."]},
    ],
    "evals": [
        {"h": "O que é", "p": [
            "Avaliar um agente é verificar se ele fez o que devia. Há dois jeitos de olhar: pelo resultado (o estado "
            "final está certo?) e pela trajetória (os passos fizeram sentido?). Process Reward Models são modelos "
            "treinados para dar nota a cada passo intermediário, e não só ao final.",
            "Os dois olhares se completam. Um agente pode chegar ao resultado certo por sorte, com passos arriscados; ou "
            "seguir passos razoáveis e falhar no último detalhe."]},
        {"h": "Sucesso declarado não é sucesso", "p": [
            "Um agente pode dizer 'pronto' sem ter feito. A única prova é conferir o estado de forma independente: o "
            "arquivo existe, a planilha tem as colunas, a página certa está aberta.",
            "Avaliações sérias fixam os casos e os critérios antes de rodar, e repetem para ver a variação. Mudar o "
            "critério depois de ver o resultado é a forma mais comum de enganar a si mesmo."]},
        {"h": "Como montar um conjunto de casos", "p": [
            "Comece com casos reais e pequenos, que você consegue conferir à mão. Para cada um, escreva o pedido, o estado "
            "inicial e o que precisa existir no final. Inclua casos fáceis, casos de borda (pasta vazia, nome com acento) "
            "e casos que devem ser recusados.",
            "Separe os casos que você usa para ajustar o agente dos casos que usa para decidir se ele melhorou. Se ajustar "
            "olhando os mesmos casos que julgam, a melhora pode ser só decoreba."]},
        {"h": "Como aparece no app", "p": [
            "No AI Research Lab cada caso roda numa pasta temporária e o resultado é conferido no disco. Cada linha da "
            "comparação mostra se a versão passou, falhou no plano ou falhou na ferramenta, e abrir o caso mostra o que "
            "foi conferido.",
            "O Histórico mostra, por passo, se a evidência foi verificada ou só relatada."]},
        {"h": "Erros comuns", "p": [
            "Mudar o critério depois de ver o resultado; avaliar com poucos casos e tirar conclusão firme; usar um modelo "
            "como juiz sem conferir com avaliação humana; e comparar versões rodadas em condições diferentes."]},
    ],
    "test-time": [
        {"h": "O que é", "p": [
            "Em vez de usar sempre o mesmo esforço, dá para gastar mais computação na hora de responder: pensar mais, "
            "tentar várias vezes e escolher, ou conferir com um verificador. Raciocínio adaptativo decide quanto gastar "
            "conforme a dificuldade do pedido.",
            "A ideia é simples: uma conta de cabeça não merece o mesmo tempo que um planejamento com várias etapas. Gastar "
            "pouco no fácil sobra orçamento para o difícil."]},
        {"h": "As estratégias", "p": [
            "Mais raciocínio numa tentativa: o modelo escreve passos intermediários antes da resposta. Ajuda em problemas "
            "com várias etapas lógicas.",
            "Várias tentativas e voto da maioria (self-consistency): o modelo responde várias vezes e fica a resposta mais "
            "frequente. Funciona quando há uma resposta certa bem definida.",
            "Várias tentativas e um verificador: um teste, um compilador ou outro modelo escolhe a melhor. É a mais forte "
            "quando existe um bom verificador, e a mais cara."]},
        {"h": "Como decidir quanto gastar", "p": [
            "Meça antes. Rode os mesmos casos com esforço baixo e alto e veja onde o acerto realmente sobe. Muitas tarefas "
            "não melhoram com mais esforço; algumas melhoram muito.",
            "Uma política útil é começar barato e escalar só quando um sinal indicar dificuldade: o verificador recusou, a "
            "resposta veio incompleta, ou o pedido tem muitas etapas."]},
        {"h": "Como aparece no app", "p": [
            "Cada agente tem um nível de esforço configurável. No AI Research Lab, uma nova versão pode mudar só o esforço "
            "e ser comparada com a atual nos mesmos casos, com custo e tempo medidos lado a lado."]},
        {"h": "Erros comuns", "p": [
            "Aumentar o esforço em tudo e pagar caro por tarefas fáceis; comparar estratégias com orçamentos diferentes; e "
            "esquecer que mais tempo de resposta também é custo para quem espera."]},
    ],
    "rlm": [
        {"h": "O que é", "p": [
            "Um Recursive Language Model trata uma entrada enorme como um ambiente a explorar. Em vez de ler tudo de uma "
            "vez, o modelo olha partes, chama a si mesmo (ou outro modelo) sobre pedaços e junta os resultados.",
            "É parecido com como uma pessoa lê um relatório de mil páginas: ninguém lê tudo seguido. Você olha o sumário, "
            "abre as seções que importam, faz anotações e depois junta as anotações numa conclusão."]},
        {"h": "Quando faz sentido", "p": [
            "Quando a entrada não cabe bem no contexto ou quando ler tudo de uma vez degrada a qualidade. Também quando a "
            "pergunta exige combinar informação espalhada em muitos lugares.",
            "O preço é controlar a recursão: profundidade máxima, número de chamadas e uma condição clara de parada. Sem "
            "esses limites, o custo cresce rápido e o resultado pode nunca chegar."]},
        {"h": "Como funciona, passo a passo", "p": [
            "Primeiro o modelo recebe uma descrição da entrada, e não a entrada inteira: quantos itens há, como estão "
            "organizados. Depois decide o que abrir. Para cada pedaço aberto, pode chamar uma instância nova com uma "
            "pergunta menor. As respostas voltam curtas e são combinadas.",
            "O ponto importante é que cada chamada vê pouco texto, então presta atenção ao que vê."]},
        {"h": "Como pensar no app", "p": [
            "Resumir centenas de notas do Cérebro é um caso típico: cada chamada lê um grupo, devolve um resumo curto, e "
            "uma última chamada combina. A verificação é conferir o resumo contra as notas de origem, escolhendo algumas "
            "afirmações e procurando onde elas aparecem."]},
        {"h": "Limites", "p": [
            "É uma abordagem recente; a evidência ainda vem principalmente dos próprios autores. Erros de uma chamada "
            "podem se propagar para a combinação final, por isso guardar o caminho de cada resumo é essencial."]},
    ],
    "interpretability": [
        {"h": "O que é", "p": [
            "Interpretabilidade mecanicista tenta entender o que acontece dentro do modelo: quais componentes e caminhos "
            "internos produzem uma resposta. Circuit tracing monta grafos que ligam características internas ao "
            "resultado.",
            "Em vez de tratar o modelo como uma caixa preta, a pergunta passa a ser: que conceitos ele representa por "
            "dentro, e como esses conceitos se combinam para chegar à resposta?"]},
        {"h": "Saída versus mecanismo", "p": [
            "Testar a saída diz o que o modelo fez. Olhar o mecanismo diz como, e às vezes revela atalhos que nenhum "
            "teste de saída pegaria. Os dois se complementam.",
            "Um exemplo típico: um modelo acerta uma conta, mas por dentro usa uma heurística que falha com números "
            "maiores. O teste com números pequenos passa; a análise do mecanismo mostra o risco antes que ele apareça."]},
        {"h": "As ideias principais", "p": [
            "Características: direções no espaço interno do modelo que correspondem a conceitos reconhecíveis, como um "
            "idioma, um tema ou uma intenção.",
            "Circuitos: caminhos que ligam características entre camadas e produzem um comportamento. Quando dá para "
            "intervir num circuito e mudar a resposta de forma previsível, há evidência de que ele importa de verdade."]},
        {"h": "Acesso necessário", "p": [
            "Esse trabalho exige os pesos e as ativações do modelo. Os modelos usados pelo app por API não expõem isso, "
            "então a prática aqui é de leitura e reflexão, não de experimento. O hábito que fica é desconfiar de "
            "explicações que o modelo dá sobre si mesmo: o que ele diz que fez nem sempre é o que fez."]},
        {"h": "Limites", "p": [
            "Os métodos explicam partes do comportamento em casos estudados; não há garantia de cobertura de um modelo "
            "inteiro. E uma explicação convincente ainda precisa ser testada com intervenções."]},
    ],
    "world-models": [
        {"h": "O que é", "p": [
            "Um world model aprende como um ambiente muda: dado o estado atual e uma ação, prevê o próximo estado. Agentes "
            "que agem no mundo, simulado ou físico, usam essas previsões para planejar antes de agir.",
            "É a diferença entre tentar e errar de verdade e imaginar o resultado antes. Uma pessoa não precisa derrubar "
            "um copo para saber que ele vai quebrar."]},
        {"h": "Por que importa", "p": [
            "Prever antes de agir permite testar planos sem gastar tentativas reais. Em jogos e simulações isso já rende "
            "agentes fortes; no mundo físico ainda é pesquisa ativa.",
            "Para robôs e agentes que mexem em coisas caras ou irreversíveis, poder ensaiar na imaginação é o que torna o "
            "aprendizado seguro e barato."]},
        {"h": "Como funciona", "p": [
            "O modelo observa muitas sequências de estado, ação e resultado e aprende a regularidade. Depois, para decidir, "
            "o agente simula algumas ações possíveis dentro desse modelo, avalia os estados previstos e escolhe a melhor.",
            "Quanto melhor a previsão, melhor o plano. Quando a previsão erra, o agente planeja com confiança em cima de "
            "uma ilusão, por isso é preciso conferir o mundo real de tempos em tempos."]},
        {"h": "Como pensar no app", "p": [
            "Mesmo sem um modelo treinado, o hábito é útil: antes de pedir ao agente de Arquivos para organizar uma "
            "pasta, escreva o que você espera que exista depois e confira o resultado. A simulação do app faz algo "
            "parecido: mostra o plano antes de executar."]},
        {"h": "Limites", "p": [
            "Bons resultados em simulação nem sempre transferem para o mundo real. Pequenas diferenças entre o ambiente "
            "simulado e o real se acumulam ao longo de planos longos."]},
    ],
    "serving": [
        {"h": "O que é", "p": [
            "Servir modelos em escala é organizar a inferência para equilibrar qualidade, custo e latência. Uma técnica é "
            "separar as fases de leitura do pedido (prefill) e geração (decode) em máquinas diferentes. Outra é rotear: "
            "mandar cada pedido para o modelo que resolve com o menor custo aceitável.",
            "As duas fases têm perfis diferentes: ler o pedido é pesado em cálculo e acontece de uma vez; gerar é feito "
            "palavra por palavra e depende de memória. Separá-las deixa cada máquina fazer o que faz melhor."]},
        {"h": "Política fixa versus condicionada", "p": [
            "Usar sempre o maior modelo garante qualidade e custa caro. Rotear pelo tipo de tarefa mantém a qualidade "
            "gastando menos, desde que você meça. Abrir um site não precisa de modelo nenhum; uma planilha simples pode "
            "usar um modelo menor.",
            "O roteador pode ser uma regra simples, um classificador pequeno ou uma cascata: tenta o modelo barato e só "
            "sobe para o caro quando a resposta não passa num teste."]},
        {"h": "O que medir", "p": [
            "Custo por tarefa concluída, e não por chamada. Tempo até a primeira palavra, que é o que a pessoa sente. E, "
            "acima de tudo, quantos casos pioraram com a troca, e não só a média.",
            "Uma troca que economiza muito e piora poucos casos pode valer a pena; uma que piora justamente os casos "
            "importantes não vale, mesmo com média boa."]},
        {"h": "Como aparece no app", "p": [
            "Pedidos como 'abre o YouTube' já rodam sem chamar modelo. A tela Atividade mostra o custo por agente e por "
            "dia, que é o ponto de partida para decidir onde um modelo menor bastaria. O AI Research Lab permite testar "
            "essa decisão nos mesmos casos antes de mudar."]},
        {"h": "Erros comuns", "p": [
            "Trocar o modelo para economizar sem medir a perda de acertos; olhar só o custo médio e não os casos que "
            "pioraram; e otimizar a latência de servidor esquecendo o tempo total que a pessoa espera."]},
    ],
}


def reading_minutes(sections) -> int:
    words = sum(len(p.split()) for s in sections for p in s["p"])
    return max(1, round(words / 200))
