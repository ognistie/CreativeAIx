## Visão geral

Servir um modelo de linguagem em escala é um problema de engenharia de sistemas com três grandezas que brigam entre si: qualidade da resposta, custo por pedido e latência percebida. Este tema junta duas famílias de técnicas que atacam esse conflito em camadas diferentes.

A primeira vive dentro do servidor de inferência. Ela parte de uma observação sobre como um modelo autorregressivo gera texto: o trabalho se divide em duas fases com perfis de hardware muito diferentes, a leitura do pedido (prefill) e a geração token a token (decode). Gerenciar bem a memória que liga as duas fases, o KV cache, e decidir se elas rodam na mesma máquina ou em máquinas separadas (serving desagregado) muda quantos pedidos um conjunto de GPUs atende dentro do prazo prometido.

A segunda vive antes do servidor, na aplicação. Roteamento dinâmico é decidir, pedido a pedido, qual modelo (ou nenhum) deve responder. Usar sempre o maior modelo é uma política fixa: simples, previsível e cara. Uma política condicionada à tarefa manda pedidos fáceis para caminhos baratos e reserva o modelo caro para quando ele faz diferença. O pré-requisito do tema é avaliação, e não por acaso: sem medir qualidade caso a caso, roteamento vira apenas uma forma elegante de piorar respostas para economizar.

Este texto cobre as duas camadas com profundidade suficiente para raciocinar sobre trade-offs, explica como medir cada uma e mostra onde o Creative AIx toca o tema. Adiantando a parte honesta: o app não serve modelos. Ele chama um provedor por API e não controla prefill, decode, batching nem KV cache. O que ele faz é a camada de roteamento e de medição de custo, e é por ela que passa o exercício prático.

## Anatomia de uma requisição: prefill e decode

Um modelo autorregressivo gera um token por vez, e cada token novo depende de todos os anteriores. Quando um pedido chega, o servidor precisa primeiro processar o prompt inteiro: isso é o prefill. Nessa fase todos os tokens do prompt são conhecidos de antemão, então o cálculo pode ser feito em paralelo, como grandes multiplicações de matrizes. O resultado do prefill é o primeiro token de saída e, igualmente importante, as chaves e valores de atenção de cada camada para cada token do prompt.

Depois vem o decode. A cada passo, o modelo processa só o token mais recente, consulta as chaves e valores de todos os tokens anteriores e produz o próximo. Isso se repete até o fim da resposta. Cada passo faz pouco cálculo por pedido, mas precisa ler da memória todos os pesos do modelo e todo o KV cache acumulado daquele pedido.

### Por que as fases têm perfis diferentes

O prefill é limitado por cálculo: há muitos tokens para processar de uma vez, e a GPU passa o tempo fazendo aritmética. O decode é limitado por banda de memória: para gerar um único token, o hardware precisa trazer os pesos e o cache da memória, e a aritmética feita com esses dados é pequena. A forma clássica de melhorar a eficiência do decode é agrupar muitos pedidos no mesmo passo (batching), para que a mesma leitura de pesos sirva a vários tokens.

Essa assimetria tem consequências diretas para quem usa o modelo:

| Fase | Recurso dominante | Métrica que afeta | Cresce com |
|---|---|---|---|
| Prefill | cálculo | tempo até o primeiro token (TTFT) | tamanho do prompt |
| Decode | banda de memória e capacidade do KV cache | tempo por token de saída (TPOT) | tamanho da resposta e número de pedidos simultâneos |

Para um agente, isso se traduz numa intuição útil: prompts longos pesam sobretudo no tempo até começar a responder; respostas longas, inclusive raciocínio interno, pesam no tempo total e no custo de saída.

### KV cache: a memória que cresce

O KV cache guarda, para cada pedido em andamento, as chaves e os valores de atenção de cada token já processado, em cada camada. Sem ele, cada passo do decode teria de recalcular tudo desde o início. Com ele, o custo de cada passo fica proporcional ao comprimento do contexto em leitura de memória, e não em recomputação.

O tamanho do cache por pedido segue uma conta simples, útil para estimar quantos pedidos cabem na GPU:

```python
def kv_cache_bytes(camadas, cabecas_kv, dim_cabeca, tokens, bytes_por_valor):
    # 2 = uma matriz de chaves e uma de valores por camada
    return 2 * camadas * cabecas_kv * dim_cabeca * tokens * bytes_por_valor

# Memória livre depois dos pesos / bytes por pedido = pedidos simultâneos possíveis.
# Contexto mais longo -> menos pedidos no batch -> decode menos eficiente.
```

Dois fatos saem dessa conta. Primeiro, o cache cresce linearmente com o número de tokens, então contextos longos competem diretamente com o número de pedidos simultâneos. Segundo, como o tamanho final de uma resposta não é conhecido de antemão, reservar memória contígua para o pior caso desperdiça espaço. É exatamente esse desperdício que o PagedAttention ataca.

## Como funciona por dentro

### Batching contínuo e interferência entre fases

Servidores modernos não esperam um lote inteiro terminar para começar outro. Eles agendam por iteração: a cada passo do decode, pedidos que terminaram saem do lote e pedidos novos entram. Isso mantém a GPU ocupada, mas cria um problema. Quando um pedido novo entra, seu prefill precisa rodar. Se o prefill roda no mesmo passo que os decodes dos outros pedidos, o passo fica mais lento e todos os pedidos em geração sentem um soluço no tempo por token. Se o servidor prioriza decodes, os pedidos novos esperam mais pelo primeiro token.

Isso é a interferência entre prefill e decode. Uma família de soluções mantém as duas fases na mesma máquina e as fatia com cuidado, por exemplo quebrando prefills longos em pedaços intercalados com passos de decode. Outra família separa as fases fisicamente. As duas são respostas legítimas ao mesmo problema; a escolha depende do perfil da carga e da infraestrutura.

### PagedAttention: memória virtual para o KV cache

O artigo do vLLM parte de uma analogia com sistemas operacionais. Em vez de alocar um bloco contíguo de memória para o cache de cada pedido, o PagedAttention divide o cache em blocos de tamanho fixo, alocados sob demanda conforme o pedido gera tokens. Uma tabela de blocos por pedido mapeia posições lógicas para blocos físicos, que não precisam ser vizinhos. O cálculo de atenção é adaptado para ler os blocos onde quer que estejam.

As consequências práticas são três. A fragmentação cai: um pedido só ocupa os blocos que de fato usa, e o desperdício fica restrito ao último bloco parcialmente cheio. Mais pedidos cabem ao mesmo tempo, o que aumenta o tamanho do lote e, portanto, a vazão do decode. E blocos podem ser compartilhados entre sequências, com cópia na escrita, o que ajuda quando várias saídas partem do mesmo prompt, como em amostragem paralela, ou quando muitos pedidos compartilham um prefixo. O artigo relata ganhos de vazão expressivos sobre os sistemas comparados, mantendo a latência no mesmo nível.

A ideia de compartilhar blocos de um prefixo comum tem uma consequência que chega até a aplicação. Se muitos pedidos começam com o mesmo texto (um prompt de sistema longo e estável, por exemplo), o trabalho de prefill desse trecho pode ser reaproveitado. Provedores expõem isso de formas variadas, como cache de prompt. A regra prática para quem escreve a aplicação é manter o prefixo estável no começo e colocar o que varia depois dele.

### Desagregar prefill e decode

O DistServe e o Splitwise propõem levar a separação das fases ao nível do hardware: um grupo de máquinas faz só prefill, outro faz só decode. Quando o prefill termina, o KV cache produzido é transferido para a máquina de decode, que continua a geração.

O argumento do DistServe é construído em torno de goodput: não basta atender muitos pedidos por segundo, é preciso atendê-los dentro de metas de latência para as duas fases, o tempo até o primeiro token e o tempo por token de saída. Com as fases juntas, otimizar uma meta prejudica a outra por causa da interferência. Separadas, cada grupo pode ter sua própria estratégia de paralelismo e sua própria quantidade de recursos, ajustada à meta que importa para aquela fase. O artigo também trata do posicionamento das instâncias levando em conta a banda disponível para mover o cache entre elas.

O Splitwise chega a uma conclusão parecida pelo lado do custo e da energia. Como a fase de geração não usa bem o poder de cálculo das GPUs mais recentes, ela pode rodar em hardware diferente, inclusive de outra geração, enquanto o prompt roda onde há mais cálculo. A transferência do estado entre as máquinas depende de interconexão rápida, e o desenho do sistema precisa esconder essa transferência o máximo possível.

O preço da desagregação é real e precisa entrar na conta:

- **Transferência do KV cache.** Para prompts longos, o cache é grande, e movê-lo consome banda e tempo. Sem interconexão rápida, o ganho pode desaparecer.
- **Balanceamento entre grupos.** A proporção certa entre máquinas de prefill e de decode depende da mistura de pedidos (prompts longos ou curtos, respostas longas ou curtas). Se a carga muda, um grupo fica ocioso enquanto o outro forma fila.
- **Mais peças para falhar.** Um pedido passa a depender de duas máquinas e de uma transferência. Falhas parciais e reintentos ficam mais complexos.
- **Agendamento mais difícil.** O escalonador precisa decidir onde cada fase roda e quando transferir, com metas para as duas.

### Exemplo passo a passo

Considere um pedido com um prompt longo (um documento a resumir) e uma resposta curta, chegando a um servidor sob carga.

1. **Chegada.** O roteador do servidor vê o tamanho do prompt e o envia ao grupo de prefill com menor fila.
2. **Prefill.** O prompt inteiro é processado em paralelo. Sai o primeiro token e o KV cache de todas as camadas. O tempo até aqui é o TTFT que a pessoa sente.
3. **Transferência.** O cache vai para uma máquina de decode com blocos livres suficientes. Com PagedAttention, ele ocupa blocos não contíguos alocados sob demanda.
4. **Decode.** O pedido entra num lote com outros pedidos em geração. A cada passo, um token novo. Os outros pedidos do lote não sofrem o soluço de um prefill longo, porque nenhum prefill roda ali.
5. **Término.** Ao gerar o token de fim, os blocos são liberados e voltam para o conjunto livre.
6. **Contabilidade.** O pedido conta para o goodput só se cumpriu as duas metas: TTFT e tempo por token dentro do prometido.

Num servidor sem desagregação, os passos 2 e 4 aconteceriam na mesma máquina, e o prefill desse documento longo atrasaria os tokens de todos os outros pedidos daquele lote enquanto rodasse.

## Métricas que importam no servidor

| Métrica | O que mede | Armadilha |
|---|---|---|
| Throughput | tokens ou pedidos por segundo | ignora se os pedidos cumpriram o prazo |
| TTFT | tempo até o primeiro token | média esconde a cauda; olhe percentis altos |
| TPOT | tempo médio por token de saída | soluços pontuais somem na média |
| Latência total | do envio ao último token | depende do tamanho da resposta; compare pedidos parecidos |
| Goodput | pedidos por segundo que cumprem as metas de latência | depende das metas escolhidas; declare-as |
| Uso de memória do KV cache | quanto da memória livre está ocupado por cache | alto demais gera preempção e reprocessamento |

A troca de throughput por goodput é a mudança mais importante de mentalidade do tema. Um sistema pode bater recorde de tokens por segundo e, mesmo assim, entregar uma experiência ruim, porque metade dos pedidos ficou acima da meta de primeiro token. Medir goodput obriga a escrever a meta de latência antes do experimento, o que já é metade do trabalho.

## Roteamento dinâmico de modelos

### Política fixa e política condicionada

Uma política fixa usa sempre o mesmo modelo, geralmente o mais capaz disponível. A vantagem é que a qualidade é previsível e não há decisão a errar. A desvantagem é pagar o preço do modelo grande também para pedidos que um caminho barato resolveria igualmente bem.

Uma política condicionada escolhe o caminho a partir do pedido. O espaço de caminhos é mais amplo do que "modelo grande ou modelo pequeno":

- **Nenhum modelo.** Pedidos com estrutura conhecida podem ser resolvidos por regra ou por rotina determinística. É o caminho mais barato e mais rápido, e o mais fácil de testar.
- **Mesmo modelo, menos esforço.** Muitos provedores permitem ajustar quanto o modelo raciocina antes de responder ou limitar o tamanho da saída. Isso também é roteamento: o mesmo modelo, configurado para a dificuldade do pedido.
- **Modelo menor.** Para tarefas de classificação, extração ou formatação simples.
- **Modelo maior.** Para geração longa, código, planos com várias etapas.

### Formas de roteador

**Regras.** Expressões regulares, dicionários de intenções, tamanho do pedido. São transparentes, baratas e determinísticas, mas cobrem só o que alguém previu. O cuidado é fazê-las conservadoras: quando há qualquer dúvida, devolver o pedido para o caminho completo.

**Classificador.** Um modelo pequeno, treinado ou instruído, que prevê se o pedido precisa do modelo forte. A qualidade depende inteiramente dos dados de treino e de quão bem eles representam os pedidos reais.

**Cascata.** Tenta o caminho barato, verifica a resposta e só sobe para o caro quando a verificação falha. A cascata troca custo por latência nos casos que escalam, porque esses pagam as duas chamadas.

**Roteador aprendido de preferências.** O RouteLLM treina roteadores a partir de dados de preferência humana entre respostas de um modelo forte e de um fraco, e estuda várias arquiteturas de roteador, de abordagens por similaridade a classificadores baseados em modelos de linguagem. O roteador produz uma estimativa de quanto o modelo forte é necessário, e um limiar ajustável define o ponto de operação entre custo e qualidade. O artigo relata reduções relevantes de custo mantendo a qualidade em benchmarks e discute a capacidade de generalizar para pares de modelos não vistos no treino. Para quem projeta, a lição central é que o roteador é um modelo como outro qualquer: precisa de dados representativos e de avaliação própria.

### Pseudocódigo de uma política condicionada com cascata

```python
def responder(pedido):
    plano = regra_sem_modelo(pedido)          # dicionário, rotina conhecida
    if plano and politicas_aprovam(plano):
        return executar(plano)                # custo de modelo: zero

    if parece_simples(pedido):
        r = modelo(pedido, tier="fast", esforco="low")
        if verificador_aprova(pedido, r):     # teste objetivo, não autoavaliação
            return r
        registrar_escalada(pedido, r)          # dado para recalibrar o roteador

    return modelo(pedido, tier="strong", esforco="high")
```

Três detalhes desse esqueleto carregam a maior parte do valor. O caminho sem modelo passa pelas mesmas políticas de aceite que um plano gerado por modelo, para não ser uma porta lateral. O verificador é um teste objetivo sempre que possível, e não o próprio modelo barato dizendo que acertou. E cada escalada vira registro, porque é exatamente o dado de que se precisa para ajustar o limiar depois.

### A conta da cascata

O custo esperado de uma cascata de dois níveis é aproximadamente o custo do nível barato, mais o custo do verificador, mais a fração de pedidos que escalam multiplicada pelo custo do nível caro. A cascata compensa quando essa soma fica abaixo do custo de mandar tudo para o nível caro e a qualidade final não cai. Se a fração de escalada é alta, a cascata pode custar mais do que a política fixa, além de ser mais lenta.

Em agentes, a conta tem uma camada extra. Um modelo mais barato que erra um passo pode causar reintentos, passos a mais ou uma tarefa refeita. Por isso a unidade certa é custo por tarefa concluída corretamente, e não custo por chamada. Um caminho barato por chamada pode ser caro por tarefa.

## Padrões e anti-padrões

| Padrão | Anti-padrão |
|---|---|
| Medir custo por tarefa concluída e verificada | Medir custo por chamada e comemorar a média |
| Olhar os casos que pioraram, um a um | Olhar só a taxa de acerto agregada |
| Rotas sem modelo conservadoras, que devolvem ao caminho completo na dúvida | Regras agressivas que capturam pedidos parecidos, mas diferentes |
| Verificador objetivo na cascata | Pedir ao modelo barato que avalie a própria resposta |
| Prefixo estável no começo do prompt | Colocar dados variáveis antes das instruções fixas |
| Declarar metas de latência antes de medir | Escolher a métrica depois de ver o resultado |
| Recalibrar o limiar com dados reais de uso | Ajustar uma vez num conjunto pequeno e esquecer |

## Como medir

Roteamento sem avaliação é um palpite. O protocolo mínimo tem quatro partes.

1. **Conjunto de casos representativo.** Pedidos reais, com a resposta certa ou o resultado esperado definidos de forma verificável. Pedidos que já têm caminho sem modelo devem ser separados, para não inflar a taxa de acerto.
2. **Comparação pareada.** Rode a política atual e a candidata nos mesmos casos. Conte quantos casos melhoraram, quantos pioraram e quantos ficaram iguais. Uma troca que economiza e piora poucos casos sem importância pode valer; uma que piora justamente os casos importantes não vale, mesmo com média boa.
3. **Custo e latência por caso.** Registre tokens de entrada, de saída e de cache, custo calculado e tempo. Olhe mediana e percentis altos, não só a média.
4. **Repetição.** Respostas de modelos variam entre execuções. Rode cada caso mais de uma vez quando a diferença entre políticas for pequena.

No lado do servidor, o equivalente é fixar metas de TTFT e TPOT, gerar carga com a mistura real de tamanhos de prompt e resposta, e medir goodput sob essa carga. Comparar sistemas com cargas diferentes não diz nada.

## Como aparece no Creative AIx

O app não roda servidor de inferência. Prefill, decode, batching, PagedAttention e desagregação acontecem do lado do provedor e não são visíveis nem configuráveis daqui. O que o app controla é a camada acima: qual caminho cada pedido segue, com que configuração de modelo, e quanto isso custou. Essa camada está bem representada no código.

**Tiers e configuração por agente.** Em `config.yaml`, a seção `models` define dois tiers, `fast` e `strong`, e `agent_models` diz qual tier cada agente usa. O comentário do próprio arquivo registra que hoje os dois tiers apontam para o mesmo modelo, `claude-sonnet-5`, e que eles continuam existindo para permitir trocar um deles sem mexer no código. Ou seja, a infraestrutura para política condicionada por modelo existe, mas a política atual por modelo é, na prática, fixa. `app/core/config.py` resolve isso em `get_model` e `get_effort`.

**Esforço e raciocínio como alavanca.** A diferenciação que o app usa de fato hoje é dentro do mesmo modelo. `agent_effort` em `config.yaml` define esforço baixo para roteamento e respostas curtas, médio para planos simples e alto para código, e o comentário chama o esforço de principal alavanca de custo. `agent_thinking` desliga o raciocínio prévio no Maestro, na voz, no resolvedor e na resposta. O mesmo arquivo registra a medição que justificou a escolha: com `app/scripts/eval_routing.py`, em 24 pedidos reais rodados duas vezes, o Maestro passou de 3,12 s para 1,69 s com o mesmo acerto, e na avaliação de voz os 54 casos acertaram nas duas configurações. É um exemplo direto de política condicionada validada com avaliação pareada. Em `app/core/ai_client.py`, `thinking_off_for` lê essa configuração, e o raciocínio só é desligado quando o modelo aceita e quando não há imagem na chamada. `limits` em `config.yaml` define tetos de tokens de saída diferentes para os tiers (`max_tokens_fast` e `max_tokens_strong`), com o aviso de que valores baixos truncam a resposta, porque o teto inclui o raciocínio.

**Rotas sem modelo.** `app/agents/maestro.py` tem caminhos que não chamam o modelo. `fast_open_plan` reconhece pedidos do tipo "abrir X" quando X é exatamente um app ou site do dicionário e monta o plano direto; `vault_plan` abre um cofre do Obsidian por link; `continue_plan` trata ações simples dentro de um alvo já aberto. Todos são conservadores: devolvem `None` quando há qualquer dúvida, e o Maestro planeja normalmente. E todos passam por `validate_plan` em `app/core/plan_validator.py`, as mesmas políticas de aceite aplicadas a um plano gerado pelo modelo. Há também uma checagem de ambiguidade antes de qualquer chamada, que pergunta em vez de adivinhar. `app/agents/app_routines.py` tem rotinas determinísticas para apps conhecidos e devolve `None` quando falta informação, deixando a decisão para o modelo.

**Para onde o pedido continua.** `app/core/routing.py` decide se um pedido continua num alvo já aberto e qual agente é o dono dele. O comentário do arquivo explica por que a decisão é única: o app e a avaliação de conversas usam a mesma função, para nunca divergirem. É roteamento de pedido para agente, não de modelo, mas o princípio de ter uma única fonte de verdade para a decisão vale para qualquer roteador.

**Cascata local antes da API.** `app/core/vision.py`, quando a descrição do alvo parece um texto literal (um botão "Enviar", uma aba "Chat"), tenta primeiro localizá-lo na tela com OCR local (`app/core/ocr_local.py`), sem custo de API, e só cai para o modelo de visão quando o OCR não acha o alvo ou acha com confiança abaixo de um limiar fixo no código. Alvos descritos por aparência vão direto para o modelo. É uma cascata de dois níveis com um verificador simples (confiança e posição fora da barra de tarefas).

**Prefixo estável e cache de prompt.** `app/core/ai_client.py` marca o prompt de sistema de cada agente para cache, tratando-o como o prefixo estável. No Maestro, as rotas da memória entram na mensagem do usuário e não no prompt de sistema, e o comentário explica o motivo: não invalidar o cache do prefixo. É a aplicação direta, do lado do cliente, da ideia de reaproveitar o trabalho sobre um prefixo comum. Como o provedor implementa esse cache internamente não é algo que o app vê.

**Custo real por chamada e por agente.** O mesmo `app/core/ai_client.py` calcula o custo de cada chamada contando tokens de entrada, de saída, de leitura e de escrita de cache, e agrega por modelo e por agente, incluindo o tempo de espera. Um limite honesto: o tempo registrado é o da chamada inteira, não o tempo até o primeiro token. O streaming permitiria separar os dois, mas a métrica guardada hoje é a total.

**Tela Atividade.** `app/core/activity.py` monta o resumo da tela Atividade (`ui/src/views/ActivityView.tsx`): custo do mês, custo por dia e divisão por agente. Leia o código antes de tirar conclusões finas: quando uma execução envolve mais de um agente, o custo dela é dividido igualmente entre os agentes da execução. É uma aproximação útil para visão geral, mas não atribui a cada agente o que ele realmente gastou.

**Medição fora da tela.** `app/scripts/bench_cost.py` roda tarefas reais no computador e registra cada chamada ao modelo com tokens e custo, o que dá custo por tarefa e não por chamada. `app/scripts/latency_report.py` lê o histórico e mostra mediana e P90 do tempo por tipo de pedido, com a divisão de onde o tempo foi gasto. `app/core/lab.py`, do AI Research Lab, permite rodar versões de agente com modelo, esforço e limite de tokens diferentes nos mesmos casos, com verificação independente do estado final, registrando a origem de cada métrica.

## Exercício prático no app

O exercício da ficha usa a tela Atividade como ponto de partida e pede uma proposta de roteamento com estimativa de economia baseada em números reais. Um roteiro que leva a uma proposta defensável:

1. **Levante o custo por agente.** Na tela Atividade, anote o custo do mês e a divisão por agente. Lembre da aproximação descrita acima: execuções com vários agentes têm o custo dividido em partes iguais. Se uma decisão depender de diferenças pequenas entre agentes, confirme com os dados por chamada.
2. **Separe por tipo de pedido.** Liste os pedidos do período e agrupe-os: abrir site ou app, continuar no que está aberto, planilha, código, arquivos, conversa. Para cada grupo, anote quantas execuções houve e o custo médio por execução.
3. **Proponha a regra.** A ficha sugere duas: tarefas de abrir site sem modelo, e planilhas com o modelo menor. Verifique primeiro quantos pedidos de abrir já caem no atalho sem modelo do Maestro, porque esses já não custam chamada ao planejador. Para planilhas, note que hoje os dois tiers apontam para o mesmo modelo; a proposta seria configurar o tier do agente de dados para um modelo diferente, ou reduzir seu esforço.
4. **Estime a economia.** Multiplique o número de pedidos afetados pela diferença de custo esperada por pedido. Seja explícito sobre as premissas: de onde vem a diferença de preço, se o modelo menor gastaria mais passos, se haveria escaladas.
5. **Defina o critério de aceite antes de testar.** Por exemplo: nenhum caso importante pode piorar, e a fração de casos que piora precisa ficar abaixo de um limite que você escreve antes.
6. **Teste antes de mudar.** Use o AI Research Lab para rodar a configuração atual e a proposta nos mesmos casos, onde o domínio permitir verificação independente. Compare caso a caso, não só a média. Só então mude `config.yaml`.

O resultado esperado não é só um número de economia. É uma decisão documentada: qual regra, qual economia estimada, quais casos pioraram, e por que vale ou não vale.

## Erros comuns

- **Trocar o modelo para economizar sem medir a perda de acertos.** A economia é imediata e visível; a perda aparece aos poucos, em reclamações.
- **Olhar só o custo médio.** A média esconde os casos que pioraram e os que escalaram.
- **Contar custo por chamada em vez de por tarefa.** Um modelo barato que precisa de mais passos ou reintentos pode sair mais caro.
- **Otimizar a latência do servidor e esquecer o tempo total.** A pessoa sente o tempo até a primeira resposta e o tempo até a tarefa terminar, não o tempo de uma chamada isolada.
- **Confundir throughput com goodput.** Vazão alta com metade dos pedidos fora do prazo não é um bom sistema.
- **Regra sem modelo agressiva demais.** Um atalho que captura pedidos parecidos mas diferentes erra com confiança e sem passar pelo planejador.
- **Invalidar o cache de prompt sem perceber.** Inserir um dado variável no começo do prompt de sistema faz cada chamada pagar o prefixo inteiro de novo.
- **Supor que o app controla o servidor.** Desagregação, KV cache e batching são do provedor; do lado do app, a alavanca é roteamento, esforço, tamanho de prompt e de resposta.

## Para ir além

As leituras da ficha, numa ordem que vai da memória ao roteamento:

- **Efficient Memory Management for Large Language Model Serving with PagedAttention (vLLM)** (Kwon, Li, Zhuang e outros). A base para entender por que o KV cache é o recurso escasso e como paginação reduz desperdício e permite compartilhar prefixos.
- **DistServe: Disaggregating Prefill and Decoding for Goodput-optimized LLM Serving** (Zhong, Liu, Chen e outros). Leia pela definição de goodput e pela forma como as metas de latência das duas fases orientam a alocação de recursos.
- **Splitwise: Efficient generative LLM inference using phase splitting** (Patel, Choukse, Zhang e outros). A mesma separação vista pelo ângulo de custo, energia e hardware heterogêneo.
- **RouteLLM: Learning to Route LLMs with Preference Data** (Ong, Almahairi, Wu e outros). Roteamento aprendido entre modelo forte e fraco, com limiar ajustável e discussão de generalização. Leia junto com o tema de avaliação, que é o pré-requisito: o roteador só é tão bom quanto a medição que o valida.
