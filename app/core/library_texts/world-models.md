## Visão geral

Um world model, ou modelo de mundo, é um modelo que aprende como um ambiente muda. A pergunta que ele responde é simples de enunciar: dado o estado em que o mundo está agora e uma ação que o agente pretende tomar, como o mundo vai estar depois? Quando essa resposta é boa o bastante, o agente ganha uma capacidade que muda o jogo: ele pode ensaiar antes de agir. Em vez de tentar uma ação no mundo real, ver o que acontece e só então corrigir, ele imagina algumas alternativas, compara os resultados previstos e escolhe a melhor.

Agentes incorporados (embodied AI) são agentes que agem num ambiente com corpo e consequência: um robô que pega objetos, um personagem num jogo, um carro numa pista. Para eles, cada tentativa real custa tempo, desgaste, energia ou risco. É por isso que a ideia de aprender a dinâmica do ambiente e treinar ou planejar dentro dela atrai tanto interesse. O ganho prometido é menos tentativa e erro no mundo real.

Este texto explica o conceito com o nível de detalhe que um engenheiro precisa para raciocinar sobre ele: o que exatamente é aprendido, como o agente usa o modelo para planejar ou para treinar uma política, onde tudo isso quebra e como medir se um modelo de mundo presta. No fim, mostra onde ideias parecidas aparecem no Creative AIx e, com a mesma clareza, o que o app não faz: ele não treina nenhum modelo de mundo. O que existe nele é um ciclo de observar a tela, agir e conferir o efeito, que é a parte de engenharia mais próxima do tema e a que dá para exercitar no dia a dia.

## O problema que um modelo de mundo resolve

Pense num agente aprendendo por reforço puro, sem modelo. Ele age, recebe uma recompensa, ajusta a política e repete. Esse caminho funciona, mas costuma exigir uma quantidade enorme de interações. Em simulação isso é aceitável, porque interação é barata. No mundo físico, ou em qualquer sistema em que uma ação errada tem custo (apagar um arquivo, enviar uma mensagem, mover um braço mecânico contra uma mesa), não é.

O modelo de mundo separa duas coisas que o aprendizado sem modelo mistura: entender como o ambiente funciona e decidir o que fazer nele. A primeira parte pode ser aprendida a partir de qualquer experiência, inclusive de dados coletados por outra política ou de vídeos. A segunda parte pode então usar o modelo como um simulador interno. Uma mesma experiência real passa a render muitas experiências imaginadas.

Há uma segunda vantagem, menos óbvia: previsão é um sinal de treino rico. Uma recompensa é um número por passo, muitas vezes zero. Prever o próximo estado obriga o modelo a representar posição, velocidade, contato, oclusão, o que está aberto e o que está fechado. Essa representação costuma servir para muitas tarefas diferentes no mesmo ambiente.

## Anatomia: estado, observação, ação, dinâmica

Os termos-chave do tema formam um vocabulário pequeno e preciso. Vale fixá-los antes de entrar no mecanismo.

| Termo | O que é | Exemplo num robô | Exemplo numa interface gráfica |
|---|---|---|---|
| Estado | Tudo o que importa para prever o futuro | posições e velocidades das juntas e dos objetos | janelas abertas, conteúdo dos campos, foco do teclado |
| Observação | O que o agente consegue ver do estado | imagem da câmera, sensores de força | captura de tela, árvore de acessibilidade, texto lido por OCR |
| Ação | O que o agente pode fazer | torque em cada motor | clicar, digitar, apertar uma tecla |
| Dinâmica | Como o estado muda com a ação | física | lógica do aplicativo |
| Simulação | Rodar a dinâmica sem tocar no mundo real | simulador físico ou modelo aprendido | um ensaio mental do que o clique vai causar |
| Planejamento | Escolher ações usando previsões | buscar a trajetória que leva o objeto ao alvo | escolher a sequência de cliques que chega à tela certa |

### Observação parcial e estado latente

Quase nunca o agente vê o estado inteiro. A câmera não vê o que está atrás do objeto; a captura de tela não mostra a aba de trás, nem o que está fora da rolagem, nem se um salvamento terminou no disco. Na linguagem formal isso é um processo de decisão parcialmente observável: o agente recebe observações, não estados.

A resposta padrão dos modelos de mundo modernos é aprender um estado latente: um vetor compacto que resume tudo o que o agente já observou e que é suficiente para prever o que vem a seguir. Esse estado é atualizado a cada passo com a nova observação e a ação tomada. Em vez de prever pixels a partir de pixels, o modelo prevê o próximo estado latente a partir do latente atual e da ação, e só decodifica para observação quando precisa (para treinar ou para inspecionar).

Prever no espaço latente é mais barato e mais estável do que prever pixels, porque o modelo não precisa gastar capacidade reproduzindo detalhes irrelevantes, como a textura do chão. O preço é que o latente pode descartar justamente um detalhe que importa para a tarefa, e isso só aparece quando o agente falha.

### Recompensa, término e incerteza

Para planejar, não basta prever o próximo estado. O agente precisa saber se aquele estado é bom. Por isso muitos modelos de mundo aprendem também uma cabeça de recompensa (quanto vale o estado) e uma de término (o episódio acabou?). Sem elas, a imaginação produz trajetórias, mas não diz qual escolher.

A terceira peça, muitas vezes esquecida, é a incerteza. O ambiente pode ser genuinamente aleatório (o dado pode cair em qualquer face), e isso se chama incerteza aleatória. Ou o modelo pode simplesmente não saber, porque nunca viu aquela situação, e isso se chama incerteza epistêmica. As duas pedem tratamentos diferentes: a primeira pede que o modelo preveja uma distribuição e não um valor único; a segunda pede que o agente desconfie das previsões em regiões pouco exploradas.

## Como funciona por dentro

### Aprender a dinâmica

O treino de um modelo de mundo começa com dados de sequências: observação, ação, próxima observação, recompensa. O modelo é treinado para, dada a história até o passo t e a ação do passo t, prever o passo t+1. A função de perda combina reconstruir a observação (ou prever sua representação), prever a recompensa e manter o estado latente bem comportado.

Uma decisão de projeto importante é se a transição é determinística, estocástica ou as duas coisas. Modelos puramente determinísticos tendem a prever a média de futuros possíveis, o que gera imagens borradas e estados que não correspondem a nenhum futuro real. Modelos com componente estocástica conseguem representar que, do mesmo estado, coisas diferentes podem acontecer. A linha de trabalho que culmina no DreamerV3 usa um modelo recorrente de espaço de estados que combina um caminho determinístico, que carrega memória ao longo do tempo, com uma variável estocástica, que representa o que não dá para prever com certeza.

### Planejar com o modelo

Com o modelo treinado, há duas famílias principais de uso. A primeira é planejar online: a cada passo, o agente imagina várias sequências de ações curtas, avalia cada uma pelo retorno previsto, executa só a primeira ação da melhor sequência e repete tudo no passo seguinte, já com a observação nova. Isso se chama controle preditivo por modelo, e o detalhe de executar só a primeira ação e replanejar é o que dá robustez: o erro do modelo não tem tempo de se acumular por muitos passos sem correção.

```python
def planejar(modelo, estado, horizonte=10, candidatos=200, elite=20, iteracoes=4):
    """Busca por amostragem com refinamento (estilo CEM), dentro do modelo aprendido."""
    media, desvio = zeros(horizonte), uns(horizonte)
    for _ in range(iteracoes):
        planos = [amostrar(media, desvio) for _ in range(candidatos)]
        notas = []
        for plano in planos:
            s, total = estado, 0.0
            for acao in plano:
                s, recompensa = modelo.prever(s, acao)   # nenhum contato com o mundo real
                total += recompensa
            notas.append(total)
        melhores = top_k(planos, notas, elite)
        media, desvio = media_de(melhores), desvio_de(melhores)
    return media[0]   # executa só a primeira ação; no próximo passo, replaneja
```

Os valores dos parâmetros acima são apenas ilustrativos. O ponto é a estrutura: o custo dessa abordagem está todo no momento da decisão, com muitas trajetórias imaginadas por passo. Para tarefas que pedem resposta rápida, isso pode não caber no orçamento de tempo.

### Aprender dentro da imaginação

A segunda família move o custo para o treino. Em vez de planejar a cada passo, o agente treina uma política inteira dentro do modelo de mundo e, na hora de agir, só consulta essa política. É a ideia central de World Models, de Ha e Schmidhuber: um componente de visão comprime cada quadro num código compacto, um componente de memória recorrente prevê o próximo código, e um controlador pequeno decide a ação a partir dos dois. O controlador pode ser treinado inteiramente dentro do sonho gerado pelo modelo e depois transferido para o ambiente real.

O mesmo artigo descreve um problema que todo praticante encontra: se o controlador é treinado só dentro do modelo, ele aprende a explorar as falhas do modelo. Ele descobre ações que, na imaginação, levam a recompensas altas por causa de um erro de previsão, e que no ambiente real não funcionam. A mitigação discutida ali é tornar o sonho mais incerto do que o real, aumentando a aleatoriedade das previsões, para que o controlador não consiga contar com brechas.

O DreamerV3 leva a ideia de aprender na imaginação mais longe. O agente alterna entre coletar experiência real, atualizar o modelo de mundo com ela e treinar um ator e um crítico em trajetórias imaginadas a partir de estados reais. A contribuição que o artigo enfatiza é a robustez: um único conjunto de hiperparâmetros funcionando em domínios muito diferentes, graças a técnicas de normalização e transformação de escala de sinais como recompensas e valores. Para um engenheiro, a lição é que boa parte da dificuldade prática não está na ideia de imaginar, e sim em manter o treino estável quando as escalas mudam de um ambiente para outro.

### Modelos de mundo generativos e ações latentes

Uma limitação das abordagens acima é que elas precisam de dados com ações rotuladas: para aprender que apertar para a direita move o personagem, é preciso saber quando a tecla foi apertada. O Genie ataca exatamente isso. Ele é treinado a partir de vídeos sem rótulos de ação e aprende, sem supervisão, um conjunto pequeno de ações latentes que explicam a diferença entre um quadro e o seguinte. Depois, uma pessoa ou um agente pode escolher essas ações quadro a quadro e o modelo gera o ambiente de forma interativa.

A mudança conceitual é grande: o modelo de mundo deixa de ser apenas uma ferramenta interna do agente e passa a ser um gerador de ambientes, potencialmente útil para criar cenários de treino em quantidade. Ao mesmo tempo, isso torna ainda mais importante perguntar se as ações aprendidas correspondem a algo controlável no mundo real, ou só a regularidades visuais dos vídeos de treino.

### Exemplo passo a passo

Para tornar o mecanismo concreto, use um mundo pequeno e totalmente observável: uma pasta de teste com cinco arquivos (`a.pdf`, `b.pdf`, `foto.jpg`, `notas.txt`, `planilha.xlsx`). O estado é o conjunto de caminhos. A ação é uma operação de arquivo. A dinâmica, neste caso, é determinística, o que ajuda a ver cada peça isoladamente.

1. Estado inicial observado: os cinco arquivos na raiz da pasta.
2. Ação proposta: organizar por tipo.
3. Previsão: existirão `Documentos/a.pdf`, `Documentos/b.pdf`, `Imagens/foto.jpg`, `Documentos/notas.txt` (ou `Textos/notas.txt`, há incerteza sobre a categoria) e `Planilhas/planilha.xlsx`; a raiz ficará sem arquivos soltos.
4. Execução no mundo real.
5. Nova observação: listar a pasta de novo.
6. Comparação: quais previsões acertaram, quais erraram e por quê. Se `notas.txt` foi para outra pasta, o erro não é de física, é de modelo: a regra de categorização era diferente da imaginada.
7. Atualização: da próxima vez, a previsão para `.txt` passa a seguir a regra observada.

Os passos 3, 5 e 6 são o coração de qualquer modelo de mundo. A diferença em relação a um sistema aprendido é que, num modelo treinado, o passo 7 é feito por gradiente e em uma quantidade enorme de exemplos. O formato do raciocínio é o mesmo.

## Modos de falha

Conhecer onde modelos de mundo quebram é o que separa usar a ideia com responsabilidade de usá-la como enfeite.

- **Erro composto.** Um erro pequeno por passo vira um erro grande em trajetórias longas, porque cada previsão alimenta a seguinte. É o motivo de horizontes de imaginação curtos e de replanejamento frequente.
- **Exploração do modelo.** O otimizador encontra brechas do modelo, não soluções do mundo. Sinais típicos: retorno imaginado muito acima do retorno real, ou políticas com comportamento estranho que só funciona na simulação.
- **Mudança de distribuição.** O modelo foi treinado com dados de uma política e é usado para avaliar outra. Quando a nova política visita estados nunca vistos, as previsões perdem valor sem avisar.
- **Detalhe pequeno, consequência grande.** Um objeto pequeno, um botão desabilitado, um aviso discreto: o modelo pode ignorá-los por ocuparem poucos pixels e mesmo assim eles decidem o resultado.
- **Assincronia.** No mundo real, o efeito de uma ação nem sempre é imediato. Uma janela abre segundos depois; um arquivo grande demora a copiar. Se a observação acontece cedo demais, a comparação conclui que a ação falhou quando ela só não terminou, ou que funcionou quando ainda vai falhar.
- **Distância entre simulação e realidade.** A limitação registrada na ficha deste tema vale aqui com força: os resultados fortes estão em jogos e simulação, e a transferência para o mundo físico segue em pesquisa. Atrito, iluminação, desgaste e variação entre unidades não aparecem nos dados de simulação, e pequenas diferenças se acumulam em planos longos.

## Padrões e anti-padrões

| Padrão | Por que funciona | Anti-padrão correspondente |
|---|---|---|
| Replanejar a cada passo com observação nova | O erro do modelo é corrigido antes de se acumular | Executar um plano longo inteiro de olhos fechados |
| Horizonte curto de imaginação | Limita o erro composto | Imaginar muitos passos à frente e confiar no fim |
| Representar incerteza | O agente evita regiões em que o modelo não sabe | Previsão pontual tratada como fato |
| Conferir o efeito depois de agir | Transforma o modelo em hipótese testável | Considerar que agiu porque mandou agir |
| Ação irreversível só com estado verificado | Erro de previsão não vira dano | Mesmo cuidado para clicar em menu e para enviar mensagem |
| Separar erro de observação de erro de dinâmica | Cada um tem correção diferente | Um único contador de falhas |

O padrão de conferir depois de agir merece destaque. Mesmo quando não há nenhum modelo aprendido, escrever explicitamente a previsão antes da ação e comparar depois transforma o comportamento do agente em algo auditável. Um agente que diz "cliquei em Salvar" sem verificar se o arquivo existe está tratando sua intenção como observação.

Outro padrão útil é distinguir ações reversíveis de irreversíveis já no desenho do agente. Para uma ação reversível, uma previsão errada custa uma correção. Para uma irreversível, custa o dano. Faz sentido, portanto, exigir mais evidência sobre o estado atual antes da segunda: confirmar que o alvo é o mesmo que foi observado, que o foco está no lugar certo, que nada mudou entre a leitura e o gesto.

## Como medir

Medir um modelo de mundo exige separar três níveis, porque um modelo pode ir bem num e mal nos outros.

1. **Previsão de um passo.** Dado estado e ação reais, quão perto a previsão fica do próximo estado real. É a métrica mais fácil e a menos informativa sozinha.
2. **Previsão em trajetória aberta.** Comece de um estado real e deixe o modelo prever vários passos seguidos, alimentando-se das próprias previsões. Meça como o erro cresce com o horizonte. A forma dessa curva diz até onde vale imaginar.
3. **Desempenho a jusante.** O que realmente importa: a política treinada ou o planejador que usa o modelo resolve a tarefa no ambiente real? Compare o retorno previsto pelo modelo com o retorno obtido. Uma diferença grande e sistemática é o sinal clássico de exploração do modelo.

Além disso, vale medir calibração (quando o modelo diz estar pouco confiante, ele erra mais?) e controlabilidade (ações diferentes produzem previsões diferentes de forma coerente, ou o modelo ignora a ação e só extrapola o vídeo?). Esta última é especialmente relevante em modelos generativos de ambiente, em que um vídeo plausível pode esconder que a ação quase não influencia o resultado.

Num agente prático sem modelo aprendido, as mesmas ideias viram métricas simples: fração de ações cujo efeito previsto foi confirmado; fração de ações sem efeito visível; quantas vezes o agente repetiu uma ação que não mudou nada; e quantas tarefas terminaram com estado final conferido de forma independente, e não apenas declarado. Essas contagens não exigem nenhum aprendizado de máquina e já revelam onde o agente está agindo às cegas.

## Como aparece no Creative AIx

Primeiro, o que o app não faz. O Creative AIx não treina modelo de mundo, não aprende dinâmica de aplicativos a partir de dados e não roda simulação de ambiente. Os modelos que ele chama por API são usados como planejadores e leitores de tela; nenhum peso é ajustado pelo app. Qualquer leitura deste texto que sugira o contrário estaria errada.

O que o app tem é o ciclo de engenharia que um modelo de mundo pressupõe: observar o estado, escolher uma ação com uma expectativa de efeito, agir e conferir. Esse ciclo aparece em vários lugares, com graus diferentes de explicitação.

**Observação do estado.** Os pilotos leem a janela pela acessibilidade do Windows em `app/core/browser_uia.py` (função `snapshot`, que devolve elementos numerados, regiões e textos visíveis). Quando o aplicativo expõe pouco, entram `app/core/ocr_local.py`, que lê texto da tela localmente, e `app/core/vision.py`, que pede ao modelo de visão para localizar um elemento numa captura. A configuração dessas leituras fica em `config.yaml`, nas seções `interaction`, `waits` e `ocr`.

**Agir e conferir o efeito.** `app/core/app_pilot.py` e `app/core/browser_pilot.py` implementam o mesmo ciclo: a cada turno o piloto lê a janela, o modelo escolhe uma ação pelo número do elemento, o piloto executa e lê de novo. Em `app_pilot.py`, a função `_view` calcula uma assinatura do que está visível (título, nomes dos elementos, textos principais) e `_changed` espera um curto intervalo verificando se essa assinatura mudou. O resultado de cada ação volta para o histórico do piloto como "janela mudou" ou "sem mudança visível", e o modelo vê isso no turno seguinte. Note o limite honesto dessa verificação: ela testa se algo mudou, não se mudou do jeito previsto. É uma checagem de efeito, não uma comparação com um estado previsto.

**Ação repetida sem efeito.** O mesmo arquivo guarda uma assinatura da última ação junto com a vista da janela. Se a mesma ação é proposta repetidas vezes sobre a mesma vista, o piloto deixa de executá-la e registra no histórico que ela não teve efeito, pedindo outro caminho. É uma defesa direta contra um modo de falha descrito acima: insistir num plano que o mundo já mostrou que não funciona.

**Estado na hora de agir igual ao estado observado.** Antes de ações sensíveis, os pilotos comparam o estado do elemento no momento da observação com o estado no momento da execução (`element_state` e `focused_state` em `app/core/browser_uia.py`). Se o alvo mudou entre ler e agir, a execução para com `NeedsConfirmation`, definida em `app/core/action_risk.py`. Isso trata o problema da assincronia: a observação que fundamentou a decisão pode estar velha. A classificação do que é sensível (enviar, comprar, excluir, publicar) também vive em `app/core/action_risk.py`.

**Verificação contra um estado esperado.** `app/core/vision.py` tem `verify_state(expected)`: recebe a descrição de um estado esperado e pergunta ao modelo de visão se a tela atual corresponde a ela, devolvendo um veredito e a descrição do estado real. O executor expõe isso como a ação `vision_verify` em `app/core/automation.py`. Esse é o ponto do código mais próximo de "prever e conferir" no sentido literal: alguém escreve o que espera ver, e a tela é comparada com isso.

**Um modelo de transição escrito à mão.** `app/core/state_machine.py` carrega mapas JSON de `app/state_maps/` (há mapas `chrome.json`, `excel.json`, `explorer.json`, `teams.json` e `vscode.json`). Cada mapa lista estados de um aplicativo, os indicadores que permitem reconhecê-los (textos de acessibilidade e de OCR) e as transições, isto é, quais ações levam de um estado a outro. Em `app/state_maps/excel.json`, por exemplo, a tela inicial leva à planilha aberta com um clique em "Blank workbook". Isso é, literalmente, um modelo de dinâmica tabular e determinístico, com estimação de estado por contagem de indicadores visíveis. A diferença para um world model aprendido é total: ninguém aprende esses mapas, eles são escritos por pessoas, cobrem poucos estados e não têm incerteza. Também é importante dizer que, no código atual, nenhum agente importa `StateMachine` fora do próprio módulo; ele está disponível, mas não participa do caminho principal de execução.

**Esperas e o risco de otimismo.** `app/core/wait_engine.py` espera condições como uma janela existir ou um elemento ficar visível, o que ataca a assincronia. Ele também ilustra um modo de falha: quando `wait_for_condition` recebe uma condição que não conhece, ele espera um tempo fixo e devolve sucesso. Na linguagem deste texto, isso é tratar a ausência de observação como confirmação da previsão. Vale ter esse padrão em mente ao ler ou estender qualquer código de espera.

**Crença sobre o que ficou aberto.** `app/core/observer.py` atualiza a sessão (`app/core/session.py`) depois de cada etapa com o que ficou aberto: a aba, a janela, a pasta, os itens visíveis. É o equivalente a manter um estado latente entre pedidos, para que "abre o segundo vídeo" faça sentido. O observer só anota uma aba se ela corresponder ao site que o pedido abriu, e só anota uma janela se o título bater com o aplicativo esperado: quando a observação contradiz a expectativa, ele prefere não atualizar a crença a adotar o estado errado.

**Olhar antes de planejar.** No agente de Arquivos, `app/agents/file_agent.py` tem `_act_after_looking`: quando o modelo propõe só listar a pasta num pedido de ação, o app roda essa leitura localmente (só leitura, no escopo já validado) e pede um novo plano com os nomes reais. É observação usada para corrigir um plano feito às cegas.

**Simulação e revisão do plano.** O executor em `app/core/automation.py` aceita `dry_run`, em que cada passo devolve um texto marcado com "[SIM]" sem tocar no sistema. E `app/desktop/controller.py`, com a opção `plan_review` de `app/core/user_settings.py`, mostra o plano e espera aprovação antes de mexer no computador. Os dois mostram o que o agente pretende fazer. Nenhum dos dois prevê o estado resultante: a simulação do app lista ações, não calcula consequências. Essa distinção é exatamente a diferença entre um plano e um modelo de mundo.

**Conferir o estado final de forma independente.** `app/core/lab.py`, que sustenta o AI Research Lab, roda experimentos no domínio de arquivos numa pasta temporária e confere o estado final de forma independente: o arquivo existe, o conteúdo bate. `app/core/outcome_grader.py` faz o mesmo em avaliação offline e registra no próprio código que existência sozinha não prova que o arquivo está certo. É a disciplina do terceiro nível de medição: o que conta é o estado real, não o sucesso declarado.

## Exercício prático no app

O exercício proposto na ficha do tema transforma você no modelo de mundo do agente de Arquivos. A ideia é fazer explicitamente, por escrito, o que um modelo aprendido faria internamente, e medir o próprio erro.

1. **Prepare um ambiente controlado.** Crie uma pasta de teste fora de qualquer pasta importante, com uma dezena de arquivos de tipos variados, incluindo alguns casos ambíguos: um `.txt` com nome de planilha, um arquivo sem extensão, dois arquivos com o mesmo nome em subpastas diferentes. Liste o conteúdo e guarde essa lista como estado inicial.
2. **Escreva a previsão antes de cada pedido.** Para cada pedido ao agente de Arquivos (por exemplo, "organiza a pasta por tipo de arquivo" ou "copia os PDFs para uma subpasta Arquivo"), escreva a lista completa de caminhos que você espera que existam depois. Marque com um sinal as previsões de que você não tem certeza. Esse sinal é sua incerteza explícita.
3. **Se quiser, use a revisão do plano.** Com `plan_review` ligado, o app mostra o plano antes de executar. Compare o plano com a sua previsão antes de aprovar. Repare que o plano diz quais operações serão feitas, mas não lista o estado final: transformar um no outro é trabalho do modelo de mundo, no caso, você.
4. **Execute e observe.** Depois da execução, liste a pasta de novo. Não confie na mensagem de conclusão do agente; o estado real é a observação.
5. **Compare e classifique os erros.** Para cada diferença entre previsto e real, decida se foi erro de dinâmica (você não sabia a regra que o agente usaria), erro de observação (você não tinha visto um arquivo, ou leu um nome errado) ou mudança de plano (o agente fez algo diferente do pedido). As três categorias pedem correções diferentes.
6. **Repita e meça.** Faça uma sequência de pedidos. Anote a fração de caminhos previstos corretamente em cada rodada e veja se ela sobe. Anote também se as previsões que você marcou como incertas erraram mais do que as outras: essa é uma medida rudimentar de calibração.

Uma variação útil é fazer uma previsão de vários passos de uma vez (o estado depois de três pedidos) e só então executar os três. Compare a taxa de acerto com a de previsões passo a passo. Se ela for pior, você terá sentido na prática o erro composto. Se for igual, pergunte se os pedidos eram independentes entre si, porque o erro composto só aparece quando cada passo depende do anterior.

## Erros comuns

- **Confundir plano com previsão.** Um plano diz o que fazer; uma previsão diz como o mundo vai ficar. Revisar o plano não substitui conferir o estado.
- **Tratar ausência de evidência como sucesso.** Uma espera que expira e devolve sucesso, um clique que não dá erro, um agente que diz que terminou: nenhum deles é observação do estado.
- **Comparar cedo demais.** Ações com efeito assíncrono precisam de espera por condição, não de comparação imediata.
- **Medir só o erro de um passo.** Um modelo excelente para o próximo quadro pode ser inútil depois de muitos passos.
- **Acreditar no retorno imaginado.** Se o agente acha que vai muito bem na simulação e vai mal no real, o problema é quase sempre o modelo, não a política.
- **Generalizar resultados de jogos para o mundo físico.** A própria ficha do tema registra que a transferência segue em pesquisa.
- **Supor que o app aprende dinâmica.** Os mecanismos do Creative AIx descritos aqui são verificação, espera e regras escritas à mão. Nenhum deles aprende com o tempo como os aplicativos se comportam.

## Para ir além

As leituras da ficha estão numa ordem que faz sentido seguir.

- **World Models** (Ha e Schmidhuber). O artigo que popularizou a separação entre visão, memória preditiva e controlador, e a ideia de treinar dentro do sonho. Leia com atenção a discussão sobre o controlador explorar falhas do modelo e o uso de mais aleatoriedade na imaginação.
- **Mastering Diverse Domains through World Models (DreamerV3)** (Hafner, Pasukonis, Ba e outros). Mostra o aprendizado na imaginação com um modelo recorrente de espaço de estados e foca na estabilidade com hiperparâmetros fixos entre domínios. Bom para entender por que os detalhes de normalização importam tanto quanto a arquitetura.
- **Genie: Generative Interactive Environments** (Bruce, Dennis, Edwards e outros). Modelos de mundo aprendidos de vídeo sem rótulos de ação, com ações latentes e geração interativa de ambientes. Leia pensando em controlabilidade: o que prova que a ação aprendida controla algo?

Ao ler os três, mantenha à vista a ressalva do tema: os resultados fortes estão em jogos e simulação. Para quem constrói agentes que agem em computadores ou no mundo físico, o aprendizado que transfere com mais segurança hoje é o de engenharia: observar antes, prever explicitamente, conferir depois e nunca tomar ação irreversível com base num estado que não foi verificado.
