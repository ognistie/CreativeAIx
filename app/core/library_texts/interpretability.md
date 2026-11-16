## Visão geral

Interpretabilidade mecanicista é a tentativa de explicar o comportamento de uma rede neural a partir do que acontece dentro dela: quais representações internas existem, como elas são calculadas e como se combinam até produzir a saída. A pergunta deixa de ser "o modelo acertou?" e passa a ser "que cálculo o modelo fez para chegar aqui, e esse cálculo vai continuar certo em casos que eu não testei?".

Circuit tracing é uma família de métodos dentro dessa área. A ideia é montar, para uma entrada específica, um grafo que liga unidades internas interpretáveis (chamadas de features) entre si e à saída, mostrando por quais caminhos a informação passou. Os relatórios técnicos da Anthropic listados na ficha deste tema descrevem um desses métodos (grafos de atribuição) e o aplicam a vários comportamentos de um modelo de linguagem de produção.

Antes de entrar nos detalhes, duas observações sobre o alcance do que segue. Primeiro, as três leituras da ficha são relatórios técnicos, sem revisão por pares; são documentos cuidadosos, mas a validação independente ainda está em andamento. Segundo, como diz a própria ficha, os métodos explicam parte do comportamento em casos estudados, e não há garantia de cobertura completa de um modelo. Uma explicação mecanicista é sempre uma explicação de um recorte: uma entrada, um comportamento, uma parte do cálculo. Tratar esse recorte como descrição do modelo inteiro é o erro mais comum de quem chega à área.

## Três coisas diferentes: saída, explicação e mecanismo

Quando alguém diz que "entende" por que um modelo respondeu algo, pode estar falando de três coisas diferentes, e misturá-las causa confusão.

A saída é o que o modelo produziu. Testes de comportamento (evals) olham para ela: dado este pedido, a resposta está correta, segura, no formato certo? Esses testes são indispensáveis, mas dizem o que aconteceu, não como.

A explicação verbal é o que o modelo diz sobre o próprio raciocínio, seja numa cadeia de pensamento, seja quando perguntado "como você chegou nisso?". Ela também é saída. É texto gerado pelo mesmo processo que gerou a resposta, e não há garantia de que descreva o cálculo que de fato aconteceu. Um dos casos estudados em On the Biology of a Large Language Model mostra justamente isso para aritmética: o modelo, quando perguntado, descreve o algoritmo escolar de somar com "vai um", enquanto o grafo de atribuição sugere uma combinação de caminhos paralelos, um que estima a ordem de grandeza e outro que acerta o último dígito.

O mecanismo é o cálculo interno: quais ativações, em quais camadas e posições, influenciaram quais outras, até a saída. Só ele permite afirmar "este caminho interno produziu X". E, mesmo assim, só com evidência de intervenção: mostrar que alterar o caminho altera a saída de forma prevista.

| Nível | Pergunta que responde | Como se obtém | Limite |
| --- | --- | --- | --- |
| Saída | O que o modelo fez? | Testes de comportamento | Não generaliza para casos não testados |
| Explicação verbal | O que o modelo diz que fez? | Perguntar, ler a cadeia de pensamento | Pode não corresponder ao cálculo |
| Mecanismo | Que cálculo produziu a saída? | Acesso a ativações, atribuição, intervenção | Cobre um recorte, com erro de aproximação |

## Conceitos centrais

Os termos da ficha (ativação, feature, superposição, circuito, grafo de atribuição) formam uma cadeia. Vale fixar cada um com precisão.

Ativação é o valor numérico que uma parte do modelo produz para uma entrada. Num transformer, o mais importante é o fluxo residual: um vetor por posição de token que atravessa as camadas, e no qual cada bloco de atenção e cada MLP lê e escreve. Tudo o que o modelo "sabe" sobre a entrada num dado ponto está, de alguma forma, codificado nesse vetor.

Feature é uma propriedade da entrada que o modelo representa internamente, como "o texto está em francês", "este token é parte de um nome próprio" ou "a frase fala de uma capital". A hipótese de trabalho da área é que features correspondem, aproximadamente, a direções no espaço de ativações: quanto mais a ativação aponta naquela direção, mais intensa é a feature. Isso é uma hipótese útil, não um fato garantido para todo conceito.

Neurônio é uma coordenada do espaço de ativações (por exemplo, uma unidade de um MLP). Seria conveniente se cada neurônio correspondesse a uma feature. Em geral, não corresponde: muitos neurônios são polissemânticos, ativando para várias coisas sem relação aparente.

Superposição é a explicação proposta em Toy Models of Superposition para essa polissemantia. Se o modelo precisa representar mais features do que tem dimensões, e se cada feature é rara (esparsa), ele pode guardar várias features em direções que não são ortogonais entre si. Como raramente estão ativas ao mesmo tempo, a interferência entre elas custa pouco na média. O preço é que nenhuma coordenada isolada fica limpa.

Circuito é um subconjunto do cálculo do modelo, formado por features e pelas conexões entre elas, que implementa um comportamento reconhecível. Grafo de atribuição é a representação de um circuito para uma entrada específica: nós são features (e outros elementos que veremos adiante), arestas são influências diretas medidas entre eles.

## Superposição por dentro

Toy Models of Superposition estuda o fenômeno em modelos pequenos o bastante para serem entendidos por inteiro. A configuração básica é simples: um vetor de entrada com várias features, cada uma ausente na maior parte do tempo; uma projeção para um espaço de dimensão menor; e uma reconstrução de volta para o espaço original, com uma não linearidade no fim. Cada feature tem uma importância, que pesa o erro de reconstrução.

O relatório mostra que, quando as features são densas (aparecem quase sempre), o modelo tende a representar apenas as mais importantes, uma por dimensão, e ignorar o resto. Quando as features ficam esparsas, o modelo passa a guardar mais features do que dimensões, em arranjos geométricos regulares, aceitando alguma interferência. A não linearidade é essencial: ela permite descartar pequenas interferências negativas, o que torna a superposição vantajosa. O relatório também descreve transições bruscas entre regimes conforme esparsidade e importância variam.

O código abaixo é uma versão simplificada dessa configuração, para rodar num ambiente Python separado com PyTorch. Ele não reproduz os resultados do relatório com garantia; serve para ver o fenômeno com as próprias mãos.

```python
import torch

n, m = 5, 2                          # 5 features, 2 dimensões internas
importancia = 0.9 ** torch.arange(n) # a primeira feature importa mais
W = torch.nn.Parameter(torch.randn(m, n) * 0.1)
b = torch.nn.Parameter(torch.zeros(n))
opt = torch.optim.Adam([W, b], lr=1e-2)
prob_zero = 0.9                      # esparsidade: chance de cada feature ser 0

for passo in range(5000):
    ativa = torch.rand(1024, n) > prob_zero
    x = torch.rand(1024, n) * ativa
    x_hat = torch.relu((x @ W.T) @ W + b)    # projeta e reconstrói
    perda = (importancia * (x - x_hat) ** 2).mean()
    opt.zero_grad(); perda.backward(); opt.step()

print("norma por feature:", W.norm(dim=0).detach())  # quem ganhou espaço
print("interferência:\n", (W.T @ W).detach())        # fora da diagonal = sobreposição
```

Rode duas vezes, uma com `prob_zero` baixo e outra alto, e compare. A norma de cada coluna de `W` indica se a feature foi representada; os valores fora da diagonal de `W.T @ W` indicam quanto duas features compartilham direção. O que importa aqui não é o número exato, e sim o raciocínio: o arranjo interno depende da estatística dos dados, e olhar uma coordenada isolada pode enganar.

A consequência prática para o resto do tema é direta. Se features vivem em superposição, ler neurônios um a um não revela os conceitos do modelo. É preciso um método que recupere as features a partir das ativações.

## Do neurônio à feature: dicionários esparsos e transcoders

A resposta mais usada é aprender um dicionário: um conjunto grande de direções tal que cada ativação do modelo possa ser escrita como a soma de poucas delas. A esparsidade é imposta no treino, de modo que, para cada entrada, só algumas entradas do dicionário fiquem ativas. A esperança é que cada direção corresponda a uma feature interpretável.

O método descrito em Circuit Tracing usa uma variante chamada transcoder entre camadas (cross-layer transcoder). Em vez de só reconstruir a ativação de um ponto, ele aprende features que leem o fluxo residual em uma camada e escrevem nas saídas dos MLPs daquela camada e das seguintes, imitando o que os MLPs do modelo fazem. O objetivo é substituir os MLPs por algo cujo funcionamento interno seja composto de features esparsas e interpretáveis.

Três ressalvas acompanham qualquer dicionário desse tipo. A reconstrução não é perfeita: sobra um erro, que é a parte do cálculo que o dicionário não captura. As features que aparecem dependem de escolhas de treino, como o tamanho do dicionário e a força da esparsidade; dicionários diferentes podem dividir o mesmo conceito de formas diferentes. E o rótulo de cada feature ("esta é a feature de capitais") é dado por pessoas, olhando exemplos que a ativam, o que é uma interpretação, não uma medida.

## Circuit tracing por dentro

Com o transcoder treinado, o método monta o grafo de atribuição para uma entrada específica. Os passos, descritos em termos gerais, são estes.

1. Construir o modelo de substituição. Os MLPs do modelo original são trocados pelo transcoder. Esse modelo de substituição se aproxima do original, mas não é igual.
2. Torná-lo local e exato para a entrada estudada. Para aquele prompt, os padrões de atenção e as normalizações observados no modelo original são congelados, e a diferença entre a saída real de cada MLP e a reconstrução do transcoder é adicionada como um nó de erro. Com isso, nesse prompt, o modelo de substituição local produz exatamente a mesma saída que o original.
3. Calcular as influências diretas. Com a atenção congelada, as interações entre features ficam lineares, e é possível calcular quanto cada feature ativa contribui diretamente para cada outra e para a saída de interesse.
4. Montar e podar o grafo. Os nós são os tokens de entrada, as features ativas em cada posição, os nós de erro e a saída (por exemplo, a probabilidade do próximo token). As arestas são as influências diretas. Como o grafo completo é enorme, ele é podado para manter os nós e arestas que mais contribuem para a saída.
5. Interpretar. Pesquisadores inspecionam cada feature relevante, olham os exemplos que a ativam, dão rótulos e agrupam features parecidas em supernós.
6. Validar com intervenções. A hipótese lida no grafo é testada no modelo original: suprimir ou amplificar features específicas e verificar se a saída e as features seguintes mudam como o grafo previa.

O passo 6 é o que separa uma história plausível de uma explicação com evidência. O pseudocódigo abaixo mostra a estrutura de um teste de intervenção em um modelo aberto; os nomes são genéricos e não correspondem a uma biblioteca específica.

```python
def testar_hipotese(modelo, prompt, camada, direcao, alvo_esperado):
    base = modelo.distribuicao_proximo_token(prompt)

    def suprimir(h):                       # remove a componente da feature
        return h - (h @ direcao) * direcao # direcao normalizada

    alterado = modelo.distribuicao_proximo_token(prompt, gancho=(camada, suprimir))
    controle = modelo.distribuicao_proximo_token(
        prompt, gancho=(camada, suprimir_direcao_aleatoria))
    return {
        "queda_no_alvo": base[alvo_esperado] - alterado[alvo_esperado],
        "queda_no_controle": base[alvo_esperado] - controle[alvo_esperado],
    }
```

Note o controle: suprimir uma direção aleatória de mesma norma. Sem ele, não dá para saber se o efeito vem da feature específica ou de qualquer perturbação naquela camada.

### Exemplo passo a passo: uma pergunta de dois saltos

Um dos casos discutidos em On the Biology of a Large Language Model é do tipo "a capital do estado onde fica a cidade X é...". Para responder, o modelo precisa de dois saltos: da cidade para o estado, do estado para a capital. Em termos gerais, o caso se desenrola assim.

1. A entrada é processada e features ligadas à cidade mencionada ficam ativas nas posições correspondentes.
2. O grafo mostra features intermediárias que representam o estado, ativadas a partir das features da cidade.
3. Features de "capital" (vindas da palavra na pergunta) e as do estado convergem para promover o token da capital correta na saída.
4. Além desse caminho em dois saltos, o grafo também mostra um atalho mais direto da cidade para a resposta. Os dois coexistem.
5. A validação: ao substituir a representação intermediária do estado pela de outro estado, a resposta do modelo muda para a capital do estado inserido. É essa mudança previsível que sustenta a leitura de que o passo intermediário existe e é usado.

O exemplo ilustra o que o método oferece: evidência de que há um passo intermediário no cálculo, e não só uma associação direta memorizada. E ilustra o que ele não oferece: o grafo vale para aquele prompt; não prova que o modelo faz raciocínio em dois saltos em todos os casos parecidos.

## O que os estudos de caso sugerem

On the Biology of a Large Language Model aplica o método a vários comportamentos. Sem entrar em números, alguns achados descritos no relatório ajudam a calibrar a intuição.

Planejamento antes de escrever. Em versos rimados, o relatório descreve features que representam a palavra que deve rimar ativas antes de a linha começar, influenciando a escolha das palavras anteriores. Intervir nessas features muda o final da linha. Isso contraria a ideia simples de que o modelo só decide uma palavra de cada vez sem nenhum plano.

Representações compartilhadas entre idiomas. O relatório descreve features de conceitos que aparecem em vários idiomas, com circuitos específicos de idioma na entrada e na saída. Isso sugere que parte do conhecimento é armazenada de forma independente da língua.

Alucinação e reconhecimento de entidades. O relatório descreve um caminho padrão que leva o modelo a dizer que não sabe, inibido quando features de "entidade conhecida" ficam ativas. Quando essas features disparam por familiaridade sem que haja conhecimento real por trás, o modelo responde com confiança algo falso.

Cadeia de pensamento nem sempre fiel. Em alguns casos, o raciocínio escrito pelo modelo não corresponde ao cálculo interno, por exemplo quando o modelo parece trabalhar de trás para frente a partir de uma resposta sugerida. Esse achado é o mais relevante para quem constrói agentes: o texto do raciocínio não é registro confiável do mecanismo.

Leia esses achados como o relatório os apresenta: observações em casos específicos, com as ressalvas do método, e não leis gerais sobre modelos de linguagem.

## Limites do método

A ficha resume: os métodos explicam parte do comportamento em casos estudados, e não há garantia de cobertura completa. Os relatórios detalham de onde vêm esses limites.

O erro de reconstrução nunca é zero. Os nós de erro representam a parte do cálculo que o transcoder não explicou. Quando eles carregam muita influência no grafo, a explicação está incompleta exatamente onde talvez importasse.

A atenção fica congelada. O grafo mostra como a informação flui dados os padrões de atenção observados, mas não explica por que a atenção foi para aquele lugar. Uma parte importante do cálculo de um transformer fica, portanto, fora da explicação.

Cada grafo é local. Ele descreve uma entrada. Generalizar exige muitos grafos e, ainda assim, é indução, não prova.

A interpretação é humana. Rótulos de features e agrupamentos em supernós são decisões de quem analisa. Duas pessoas podem contar histórias diferentes a partir do mesmo grafo, e a intervenção é o que decide entre elas.

O custo é alto. Treinar dicionários grandes, montar grafos e analisá-los exige acesso total ao modelo, computação e tempo de especialistas. Os próprios relatórios indicam que, mesmo para os prompts estudados, nem sempre se chega a uma explicação satisfatória.

## Como avaliar uma explicação mecanicista

Ao ler um resultado de interpretabilidade, ou ao produzir um, estas perguntas ajudam a separar evidência de narrativa.

| Critério | Pergunta | Sinal de alerta |
| --- | --- | --- |
| Fidelidade | O modelo de substituição reproduz o original nesta entrada? Quanto passa pelos nós de erro? | Muito peso em erro, pouco comentado |
| Necessidade | Suprimir o caminho muda a saída? | Explicação sem nenhuma intervenção |
| Suficiência | O caminho sozinho basta para o comportamento? | Caminho que só funciona junto com partes não explicadas |
| Especificidade | O efeito some com uma intervenção de controle aleatória? | Ausência de controle |
| Generalização | Vale para variações da entrada? | Um único prompt escolhido a dedo |
| Rótulos | Os rótulos das features se sustentam em exemplos variados, inclusive negativos? | Rótulo baseado só nos exemplos de maior ativação |

Uma explicação forte passa na maior parte desses critérios e diz claramente onde não passa. Uma explicação fraca apresenta um grafo bonito, rótulos sugestivos e nenhuma intervenção.

## Relação com o Creative AIx

O Creative AIx não faz interpretabilidade mecanicista, e não poderia fazer com os modelos que usa. Todas as chamadas a modelo passam pelo cliente central (`app/core/ai_client.py`), que fala com a API do provedor. Uma API devolve texto e metadados de uso, não pesos nem ativações. Sem acesso a ativações, não há features para extrair, grafos para montar nem intervenções internas para testar. A ficha do tema registra isso de forma explícita.

Há, porém, uma lição do tema que o app já aplica, e algumas ferramentas que são o análogo mais próximo no nível do sistema, desde que não sejam confundidas com interpretabilidade do modelo.

A lição é desconfiar da explicação verbal. O cliente central extrai a resposta só dos blocos de texto e não usa os blocos de raciocínio como fonte de verdade. O avaliador de resultados (`app/core/outcome_grader.py`) declara no próprio cabeçalho que o texto do rastro não é evidência: ele confere os artefatos no disco, de forma independente. O AI Research Lab (`app/core/lab.py`) segue o mesmo princípio, e um sucesso declarado pelo agente não conta; conta o estado final verificado. É a mesma separação entre "o modelo disse X" e "X aconteceu" que os relatórios de interpretabilidade fazem entre explicação verbal e mecanismo.

As ferramentas de observação do app registram o comportamento do sistema, não o interior do modelo.

- Os subagentes determinísticos (`app/agents/subagents.py`) devolvem rastros (`Trace`) com papel, resultado e resumo de cada etapa.
- O registro de tarefas (`app/core/task_ledger.py`) grava um evento antes e depois de cada passo; o Lab expõe esses eventos filtrados por agente e estado (função `observe`).
- O registro de ações (`app/core/action_logger.py`) guarda cada ação executada, com os nomes dos parâmetros, não os valores.
- Os experimentos do Lab registram, por caso, o rastro planejado, bloqueado, executado e verificado, com métricas e a origem de cada métrica.

Há também um análogo, em nível de sistema, da atribuição. O segundo cérebro (`app/core/brain.py`) guarda em `last_sources` quais notas de fato entraram no prompt de cada agente. Isso é proveniência da entrada: diz o que o modelo recebeu, não o que influenciou a resposta. Para saber se uma nota influenciou, o caminho disponível no app é uma intervenção na entrada: criar no Lab uma variante que muda uma única coisa (uma instrução, por exemplo) e comparar o resultado nos mesmos casos. Esse é um teste causal de comportamento, o equivalente externo de uma ablação. É útil e honesto, mas não diz nada sobre qual caminho interno mudou.

Por fim, o porteiro de memória (`app/core/memory_gate.py`) aplica a mesma disciplina de evidência do tema a outro problema: similaridade lexical entre uma nota e um pedido é filtro, nunca prova; só evidência independente de execução atualiza o estado de um procedimento. Correlação não é mecanismo, em nenhuma das duas escalas.

## Exercício prático

A ficha propõe um exercício guiado, porque o tema exige os pesos de um modelo aberto e os modelos usados pelo app não expõem ativações. O exercício é ler a seção de método de Circuit Tracing e escrever a diferença entre "o modelo disse X" e "este caminho interno produziu X". O roteiro abaixo transforma isso em algo verificável.

1. Escolha um comportamento concreto. Por exemplo: um agente do app recusou um plano, ou respondeu algo correto com uma justificativa estranha.
2. Escreva a afirmação de saída: "dado o pedido P, o modelo respondeu R". Isso você pode verificar no histórico ou no registro de tarefas.
3. Escreva a explicação verbal que o modelo deu, se houver, e marque-a como saída, não como mecanismo.
4. Escreva como seria uma afirmação mecanicista sobre o mesmo comportamento, no formato: "na entrada P, as features A e B, na camada L, influenciam diretamente a feature C, que promove o token R; suprimir A reduz a probabilidade de R, e suprimir uma direção aleatória de mesma norma não reduz".
5. Liste o que você precisaria para sustentar essa afirmação: acesso aos pesos, um dicionário treinado, o grafo daquele prompt, a intervenção e o controle. Marque o que está disponível para você hoje.
6. Escreva qual teste de comportamento, possível no app, chega mais perto. Normalmente é uma variante no Lab que muda uma única entrada, rodada nos mesmos casos. Escreva o que esse teste prova e o que ele não prova.

Se quiser ir além da leitura, rode o modelo de brinquedo da seção sobre superposição num ambiente Python separado e registre no Diário o que mudou entre esparsidade baixa e alta. É o único experimento deste tema que não exige um modelo grande nem acesso especial.

## Erros comuns de interpretação

"O modelo explicou o raciocínio, então sei como ele pensou." A explicação é saída. Os relatórios descrevem casos em que o raciocínio escrito não corresponde ao cálculo interno.

"Achei o neurônio de X." Por causa da superposição, neurônios costumam ser polissemânticos. Uma unidade que ativa para X pode ativar para várias outras coisas. Features recuperadas por dicionários esparsos são candidatas melhores, mas também precisam de validação.

"O grafo mostra o modelo inteiro." O grafo mostra um prompt, com atenção congelada e uma parte do cálculo dentro dos nós de erro. É uma fotografia local e aproximada.

"O rótulo da feature é o que ela faz." O rótulo é uma interpretação humana baseada em exemplos. Ele pode ser estreito demais, largo demais ou simplesmente errado em casos não olhados.

"Correlação entre feature e comportamento é explicação." Sem intervenção, uma feature que acompanha um comportamento pode ser efeito, não causa. A intervenção com controle é o que transforma correlação em evidência causal.

"Um achado num modelo vale para todos." Os estudos de caso são de um modelo específico e de comportamentos escolhidos. Mecanismos podem mudar entre modelos, tamanhos e versões.

"Se não dá para fazer interpretabilidade, não dá para ter rigor." No nível do sistema, testes de comportamento bem desenhados, verificação independente do resultado e intervenções na entrada dão rigor real. Só não respondem à pergunta sobre o mecanismo interno, e não devem fingir que respondem.

## Para ir além

As leituras da ficha deste tema, em ordem sugerida:

- **Toy Models of Superposition**, Elhage et al. (Anthropic), 2022. Relatório técnico, sem revisão por pares. É a base conceitual: por que neurônios são polissemânticos e por que features podem ser direções não ortogonais. Leia primeiro as seções que definem a configuração do modelo e os regimes de superposição.
- **Circuit Tracing: Revealing Computational Graphs in Language Models**, Ameisen et al. (Anthropic), 2025. Relatório técnico. Descreve o transcoder entre camadas, o modelo de substituição local, os grafos de atribuição, as intervenções de validação e as limitações. É a leitura central para o exercício prático.
- **On the Biology of a Large Language Model**, Lindsey et al. (Anthropic), 2025. Relatório técnico. Aplica o método a vários comportamentos e discute o que foi e o que não foi possível explicar. Leia cada estudo de caso junto com as ressalvas que o próprio texto faz.
