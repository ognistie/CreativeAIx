## Visão geral

Agent-Computer Interface (ACI) é o conjunto de coisas que um agente de linguagem enxerga e pode fazer quando opera um sistema: o nome de cada ferramenta, a descrição, o esquema de parâmetros, o formato do que volta depois de cada chamada e o jeito como os erros chegam. O termo ganhou força com o trabalho do SWE-agent, que tratou o modelo como um novo tipo de usuário final e perguntou que interface esse usuário precisa. A ideia central é simples e tem consequências grandes: a mesma capacidade de raciocínio rende mais ou menos dependendo da interface que a cerca. Trocar a forma como um arquivo é mostrado, como uma edição é aplicada ou como uma busca devolve resultados muda a taxa de sucesso do agente sem tocar no modelo.

A analogia com design de interface para pessoas ajuda, mas engana se for levada longe demais. Uma pessoa olha uma tela, percebe o layout, ignora o que não interessa e volta atrás quando se perde. Um modelo recebe tudo como texto, sem hierarquia visual, e cada palavra devolvida por uma ferramenta ocupa espaço na janela de contexto que também precisa caber o pedido, o histórico e o raciocínio. Ele não pode "passar o olho": tudo o que chega é lido. E não tem memória fora do que está escrito ali. Por isso uma ferramenta excelente para humanos, como um terminal que despeja milhares de linhas ou uma API com dezenas de parâmetros opcionais, pode ser péssima para um agente.

O ponto prático é que muitas falhas atribuídas ao "modelo" são falhas de interface. O agente chamou a ferramenta errada porque duas tinham descrições parecidas. Passou um caminho relativo porque nada dizia que precisava ser absoluto. Repetiu a mesma ação três vezes porque o erro dizia só "inválido". Leu uma página inteira e esqueceu o objetivo porque a observação não tinha limite. Cada um desses casos tem conserto do lado da ferramenta, e esse conserto costuma ser mais barato e mais estável do que trocar de modelo ou engordar o prompt.

Este texto trata a ACI como engenharia: quais são as partes de um contrato de ferramenta, como a observação funciona como canal de percepção, o que torna um erro acionável, como a interface se cruza com segurança e como medir se uma mudança de interface ajudou. Os exemplos vêm do código do Creative AIx.

## Anatomia de um contrato de ferramenta

Um contrato de ferramenta responde a cinco perguntas que o modelo faz implicitamente a cada turno: o que existe, para que serve, como chamo, o que recebo de volta e o que faço se der errado. A especificação do Model Context Protocol formaliza boa parte disso. Uma ferramenta MCP tem `name`, um `title` legível, `description`, um `inputSchema` em JSON Schema, opcionalmente um esquema de saída e anotações como `readOnlyHint` e `openWorldHint`. A especificação deixa claro que as anotações são dicas: um cliente não deve confiar nelas para decidir segurança quando o servidor não é confiável. Isso já antecipa um tema que volta mais abaixo: o contrato descreve, mas quem garante é o código.

| Parte do contrato | Pergunta que responde | Falha típica quando é mal feita |
| --- | --- | --- |
| Nome | Qual ferramenta escolher | Nomes genéricos ("executar", "arquivo") que se sobrepõem |
| Descrição | Quando usar e quando não usar | Descreve a implementação, não a intenção; omite limites |
| Esquema de parâmetros | Como montar a chamada | Campo livre onde deveria haver enum; ausência de `required` |
| Observação | O que aconteceu | Saída longa demais, sem ordem, ou vazia sem explicação |
| Erro | Como corrigir | "Inválido", stack trace, mensagem em outra língua |
| Efeito declarado | Se a ação muda o mundo | Ferramenta de leitura que também grava; efeito escondido |

O nome e a descrição são, na prática, um prompt. O artigo da Anthropic sobre escrever ferramentas para agentes insiste nisso: a descrição deve ser escrita como se fosse para um colega novo no time, explicitando convenções implícitas, formatos esperados e o que cada parâmetro significa. Um parâmetro chamado `user` é ambíguo; `user_id` com uma linha dizendo de onde vem esse id não é. O mesmo artigo recomenda agrupar ferramentas relacionadas por prefixo ou namespace quando o catálogo cresce, porque a escolha entre ferramentas parecidas é um ponto de erro frequente.

O esquema de parâmetros é a parte em que a máquina pode ajudar. Tipos, `minimum` e `maximum`, `enum`, `required` e `additionalProperties: false` transformam uma classe inteira de erros em rejeições imediatas e explicáveis. Mas há uma armadilha: o esquema só protege se alguém o valida. Um servidor que anuncia `maximum: 20` e depois aceita silenciosamente 500, cortando para 20 sem avisar, criou uma divergência entre o que o modelo acha que pediu e o que recebeu. Essa divergência é invisível no transcript e difícil de depurar.

### Granularidade: quantas ferramentas e de que tamanho

Existe uma tensão permanente entre primitivas de baixo nível e ferramentas de alto nível. Primitivas (clicar em coordenada, digitar, apertar tecla) são flexíveis e cobrem qualquer caso, mas exigem muitos turnos, cada um com chance de erro, e obrigam o modelo a planejar detalhes mecânicos. Ferramentas de alto nível (criar uma planilha a partir de um esquema, mover um conjunto de arquivos) resolvem em uma chamada, são fáceis de validar e de auditar, mas cobrem só o que foi previsto.

O artigo da Anthropic sugere uma heurística útil: em vez de embrulhar cada endpoint de uma API, construa ferramentas que correspondam a tarefas que o agente de fato faz, consolidando passos que sempre andam juntos. O SWE-agent seguiu caminho parecido: em vez de dar ao modelo um shell cru, ofereceu comandos próprios para abrir um arquivo numa janela de linhas, rolar, buscar dentro do arquivo e no repositório, e editar um intervalo de linhas. Esses comandos são poucos, têm saída compacta e foram desenhados em torno do que um agente precisa para navegar código.

A regra que sai disso não é "sempre alto nível". É: a granularidade certa é a menor que permite ao agente concluir a tarefa com poucas decisões arriscadas, e cada ferramenta deve ter uma razão de existir que não se confunda com a de outra.

## A observação é metade da interface

Fala-se muito do lado de entrada (como chamar) e pouco do lado de saída (o que volta). Só que a observação é o único canal de percepção do agente. Se ela for ruim, o agente decide no escuro, e nenhuma descrição bem escrita compensa isso.

Quatro propriedades separam uma boa observação de uma ruim.

Orçamento. A saída tem tamanho limitado e, quando corta, diz que cortou e como ver o resto. O artigo da Anthropic recomenda paginação, filtros e truncamento com padrões sensatos, e mensagens que orientem o agente a fazer buscas mais específicas em vez de pedir tudo. O SWE-agent mostra um arquivo em janelas de linhas, com indicação de quantas linhas existem acima e abaixo, em vez do arquivo inteiro.

Estrutura estável. O mesmo tipo de informação aparece sempre no mesmo lugar e no mesmo formato. Isso permite que o modelo aprenda, dentro da própria conversa, onde procurar.

Referências acionáveis. Se a próxima ação precisa apontar para algo que apareceu na observação, a observação deve dar um identificador que a ferramenta aceite de volta. Ids numerados curtos funcionam melhor que coordenadas de tela ou identificadores opacos longos; o artigo da Anthropic observa que agentes lidam melhor com nomes e identificadores semânticos do que com UUIDs crípticos.

Silêncio explícito. Uma ação bem-sucedida sem saída precisa dizer isso. No SWE-agent, um comando que não imprime nada devolve uma mensagem explícita de que rodou sem saída, porque um retorno vazio é ambíguo: deu certo, falhou em silêncio ou ainda não terminou?

### Exemplo: a página como o piloto do navegador a enxerga

O piloto do navegador do Creative AIx (`app/core/browser_pilot.py`) é um bom estudo de caso de observação desenhada para modelo. A cada turno ele lê a página aberta pela árvore de acessibilidade do Windows, por meio de `app/core/browser_uia.py`, e monta um texto com título, URL e os elementos interativos numerados, agrupados por região (cabeçalho, principal, laterais). Cada elemento vira uma linha como `[12] link "Nome do vídeo" -> https://...`. Textos não clicáveis da região principal entram intercalados em ordem de leitura, prefixados por `·`, para que preço, data e a marca "Patrocinado" fiquem junto do card a que pertencem. Anúncios recebem a marca `[ANUNCIO]`. Quando há elementos abaixo da área visível, a observação termina com uma linha dizendo que a página continua e que é preciso rolar.

Repare nas escolhas. O modelo aponta elementos pelo número, não por coordenada nem por seletor CSS, o que reduz o espaço de erro a "escolher o número certo". O texto da região principal tem um orçamento de caracteres, então uma página enorme não engole o contexto. A ordem de leitura resolve pedidos posicionais como "o segundo resultado", que seriam ambíguos numa lista solta. E a linha final sobre conteúdo abaixo é exatamente o aviso de truncamento recomendado na literatura.

O mesmo desenho aparece no piloto de aplicativos (`app/core/app_pilot.py`), que lê uma janela qualquer pela mesma camada e expõe ações parecidas, mais algumas próprias de apps, como `double_click` para abrir itens de lista e `write` para digitar onde o cursor já está.

## Erros acionáveis

Um erro acionável responde a três perguntas: o que falhou, por que falhou e o que fazer agora. "Inválido" responde só à primeira, e mal. O agente que recebe "inválido" tem duas opções ruins: tentar de novo do mesmo jeito ou chutar uma variação. As duas gastam turnos e, em ferramentas com efeito, podem causar dano.

O validador de planos de arquivos do app (`app/core/file_contracts.py`) mostra mensagens curtas e diretas: "Caminhos devem ser absolutos.", "Pattern deve ser apenas um nome, sem caminho.", "Parametro obrigatorio: destination.", "Caminho fora do escopo do pedido: ..." e "Informe a pasta ou caminho a operar; nao vou inferir um escopo.". Cada uma aponta o campo e a regra. A última é especialmente boa: além de recusar, explica que o sistema não vai adivinhar, o que orienta o agente (ou a pessoa) a fornecer o dado que falta em vez de tentar outra pasta.

Compare com um caso do servidor MCP do app (`app/mcp_server.py`). A ferramenta `brain_read` rejeita caminhos com `..` com uma mensagem que já diz o que fazer: "caminho invalido (use um caminho .md devolvido por brain_search)". Mas quando o caminho não tem `..` e mesmo assim aponta para fora do cofre, quem decide é `_inside` em `app/core/brain_store.py`, que devolve `None`, e o resultado chega ao modelo como "nota nao encontrada". A mensagem é verdadeira, mas mistura três situações diferentes: a nota não existe, foi removida da camada pessoal ou o caminho está fora do cofre. Para o agente, a ação corretiva em cada caso é diferente.

### Erro de protocolo e erro de ferramenta

A especificação do MCP separa dois tipos de erro, e a separação é uma decisão de ACI. Erros de protocolo (método inexistente, ferramenta desconhecida, JSON malformado) voltam como erro JSON-RPC: são problemas do cliente, não do raciocínio do modelo. Erros de execução da ferramenta voltam como resultado normal com `isError: true` e o texto do erro no conteúdo, justamente para que o modelo os veja e possa corrigir a chamada. O `handle` em `app/mcp_server.py` segue essa regra: uma ferramenta desconhecida devolve erro `-32602`; uma exceção dentro de `call_tool` vira um resultado com `isError: True` e o texto "Erro: ...". O comentário no código diz o motivo: o erro volta como resultado para o modelo corrigir.

Uma consequência dessa escolha é que a qualidade do texto da exceção vira parte do contrato. Se `int()` falhar ao converter um `limit` que veio como texto, o modelo recebe a mensagem padrão do Python, em inglês e sem dizer qual campo estava errado. Nada quebrou no protocolo, mas a interface piorou.

## Como funciona por dentro: o ciclo observação–ação

Por trás de quase todo agente que opera um computador há o mesmo laço, descendente direto do padrão ReAct: observar, decidir uma ação, executar, observar de novo. A ACI define o que entra e sai em cada volta. Uma versão simplificada do laço do piloto do navegador ajuda a ver onde cada decisão de interface atua:

```python
def pilot(goal, llm, max_turns):
    history = []
    for turn in range(1, max_turns + 1):
        snap = observe()                         # elementos numerados + texto com orçamento
        if snap.blocked:                         # CAPTCHA, verificação humana
            return ask_user(snap.blocked)
        prompt = render(goal, history[-8:], snap)
        decision = parse_json(llm(SYSTEM, prompt))
        if decision is invalid:
            decision = parse_json(llm(SYSTEM, prompt + "Responda só o JSON de UMA ação."))
        if decision.action in ("done", "fail", "ask_user"):
            return decision
        if same_action_on_same_page(decision, snap, times=3):
            history.append("repetido sem efeito, escolha outro caminho")
            continue
        outcome = act(decision, snap)            # valida id, checa efeito, executa, compara antes/depois
        history.append(f"{decision.label} -> {outcome}")
    return fail("limite de turnos")
```

Cada linha corresponde a uma escolha de interface. O histórico tem janela fixa, para o contexto não crescer sem limite. A resposta inválida ganha uma segunda chance com instrução literal do formato. A repetição é detectada comparando a ação e a página, e o aviso vai para o histórico em linguagem que o modelo entende. O resultado de cada ação é uma frase curta ("página mudou", "clicado (URL/título iguais)", "id inexistente nesta página") e não um despejo do estado.

### Passo a passo: "abra o YouTube, pesquise vídeos de skate e abra o segundo"

1. Turno 1. A observação mostra uma aba em branco e o histórico diz "aba nova aberta (em branco): abra o site com goto". O modelo escolhe `goto` com a URL de busca do próprio YouTube, que o prompt do sistema ensina como atalho. Antes de navegar, `_check_destination` confere se o site está na lista de destinos permitidos: buscadores conhecidos e sites que a pessoa citou no pedido. O YouTube está, então segue sem perguntar.
2. Turno 2. A observação traz a página de resultados: campo de busca no cabeçalho, filtros, e na região principal os cards na ordem de leitura, com os anúncios marcados. O modelo conta os cards de vídeo ignorando anúncios e playlists, escreve a contagem em `reason` e escolhe `click` no id do segundo.
3. Ainda no turno 2, dentro de `_act`, o piloto resolve o id para o elemento real, classifica o rótulo pelo risco de efeito, clica e espera a página mudar. A observação de retorno inclui "página mudou | CONFERIDO: o titulo da pagina nova corresponde ao item clicado", gerada por `_title_check`.
4. Turno 3. Com o título conferido, se o modelo tentar um `back` só para "verificar", o piloto bloqueia e explica no histórico que a ordem da lista muda ao recarregar. O caminho esperado é terminar com `done` e uma frase curta em `say`.

Se no turno 2 o modelo tivesse devolvido um id que não existe, a resposta seria "id inexistente nesta página": curta, verdadeira e com a ação corretiva óbvia. Se tivesse clicado no mesmo elemento duas vezes, o resultado ganharia um aviso para escolher outro elemento da região principal.

## Segurança faz parte da interface

A ACI decide o que o agente pode tentar; a camada de autorização decide o que de fato acontece. As duas precisam ser desenhadas juntas, porque um contrato frouxo empurra a responsabilidade toda para o prompt, e prompt não é barreira.

No Creative AIx, três camadas de código fazem esse trabalho. Em `app/core/action_policy.py`, `TOOLS` lista quais ações cada domínio de agente pode usar, e `authorize` recusa qualquer outra com uma mensagem que nomeia a ferramenta e o agente. O docstring do módulo resume a regra: passos gerados pelo modelo não escolhem o próprio dono. A mesma função bloqueia atalhos que abrem superfícies onde digitar executa comandos (Executar, menu Win+X) e, para o domínio de arquivos, chama o validador de `app/core/file_contracts.py`. Em `app/core/action_risk.py`, cada ação é classificada pelo efeito que tem fora do computador (enviar, publicar, comprar, pagar, transferir, excluir, aceitar), a partir do rótulo do elemento, do tipo de campo e da tecla. E nos pilotos, antes de um clique sensível, o código confere se o elemento e a página ainda estão no mesmo estado da observação; se mudaram, a ação para com "O alvo do clique mudou antes da execução.".

Esse último detalhe é uma questão de interface que costuma passar despercebida. Entre a observação e a ação existe uma janela de tempo. A página pode ter mudado, um diálogo pode ter aparecido, o foco pode ter ido para outra janela. Se a ferramenta aceita um id e age às cegas, o agente pode clicar em algo diferente do que viu. Validar o estado no momento da ação é o equivalente, para agentes, à checagem de condição de corrida entre verificação e uso.

Por fim, o conteúdo lido é dado, nunca instrução. O prompt dos pilotos diz isso, mas o código não depende do prompt: o `ContentGuard` em `app/agents/subagents.py` corta o texto lido da web a um tamanho máximo e marca padrões típicos de injeção; o gate de efeito decide pelo rótulo do elemento e pelo pedido da pessoa, não pelo que o modelo concluiu; e o destino de um `goto` fora dos sites citados pela pessoa passa pela mesma porta, para que um texto injetado não consiga mandar dados de uma aba logada para outro domínio dentro da URL.

## Padrões e anti-padrões

Padrões que costumam funcionar:

- Uma ferramenta por intenção, com nome que diz o verbo e o objeto (`move_file`, `brain_search`).
- Esquema estrito: `required`, tipos, `enum` para conjuntos fechados, `additionalProperties: false`, limites numéricos que o código realmente aplica.
- Observação com orçamento, estrutura estável e aviso explícito de truncamento.
- Identificadores curtos e locais à observação (ids numerados) em vez de coordenadas.
- Erros que nomeiam o campo, a regra e a correção, de preferência com um exemplo válido.
- Separação explícita entre ferramentas de leitura e de efeito, com a autorização de efeito fora do modelo.
- Resultado de ação expresso como diferença ("página mudou", "nada mudou") em vez do estado inteiro.

Anti-padrões recorrentes:

- Ferramenta canivete com um parâmetro `acao` de texto livre. O modelo precisa adivinhar valores válidos e o validador não tem o que conferir.
- Saída sem limite. Uma listagem de pasta com milhares de entradas consome o contexto e empurra o objetivo para fora da janela.
- Coerção silenciosa. Limitar `limit` a 20 sem avisar, transformar `0` em padrão, aceitar caminho relativo e resolver contra uma pasta qualquer.
- Erro genérico ou técnico demais. Stack trace, código numérico sem texto, mensagem da biblioteca subjacente.
- Ferramentas quase iguais. Duas formas de abrir um site, três formas de ler uma página, sem dizer quando usar cada uma.
- Descrição que promete o que o código não garante, como uma anotação de "só leitura" numa ferramenta que grava cache em disco.

## Como medir

Mudanças de interface são hipóteses e precisam de medição, porque intuição sobre o que "parece claro" engana. O princípio é manter o modelo fixo e variar só a interface, rodando o mesmo conjunto de tarefas antes e depois. O SWE-agent usou esse tipo de comparação para mostrar que componentes da interface, como a forma de visualizar arquivos e a validação de edições, afetavam o resultado. O artigo da Anthropic descreve um ciclo parecido: escrever tarefas realistas, rodar o agente, ler os transcripts e usar o próprio agente para sugerir melhorias nas ferramentas, sempre conferindo contra um conjunto separado para não ajustar demais.

Métricas que capturam qualidade de ACI, além da taxa de sucesso final:

| Métrica | O que revela |
| --- | --- |
| Chamadas inválidas por tarefa | Esquema ou descrição confusos |
| Correção na primeira tentativa após erro | Se as mensagens de erro são acionáveis |
| Ações repetidas sem mudança de estado | Observação que não mostra o efeito |
| Turnos até concluir | Granularidade e qualidade da observação |
| Tamanho médio da observação | Orçamento e risco de diluir o contexto |
| Escolha da ferramenta errada | Sobreposição entre ferramentas |
| Bloqueios por efeito não pedido | Se a interface empurra o agente para ações sensíveis |

Ler transcripts é parte do método, não um complemento. Números agregados dizem que algo piorou; o transcript mostra em que turno o agente se perdeu e o que ele estava vendo naquele momento.

No Creative AIx há instrumentos prontos. `app/core/action_logger.py` grava cada ação em JSONL com duração e resultado. `app/core/task_ledger.py` registra eventos antes e depois de cada passo, inclusive repetições. A porta de efeito em `app/core/action_risk.py` tem um modo `shadow`, que só registra o que seria bloqueado, e um relatório (`python app/core/action_risk.py`) que conta bloqueios por tipo e quantas vezes o pedido nem mencionava aquele efeito. E `app/scripts/eval_conversations.py` percorre cenários do resolvedor ao plano do agente e às políticas, sem executar os passos, o que permite comparar versões de prompt e de ferramentas no mesmo conjunto. A suíte `app/tests/test_mcp_server.py` cobre o servidor MCP e é o lugar natural para fixar, como teste, o texto de um erro que você melhorou.

## Como aparece no Creative AIx

| Arquivo | Papel na interface agente–computador |
| --- | --- |
| `app/mcp_server.py` | Servidor MCP só de leitura para Claude Code e Codex: esquemas de entrada, anotações, erros como `isError` |
| `app/core/file_contracts.py` | Contrato declarativo do domínio de arquivos: campos obrigatórios, caminhos absolutos, escopo do pedido |
| `app/core/action_policy.py` | Quais ferramentas cada agente pode chamar e atalhos bloqueados |
| `app/core/action_risk.py` | Classificação do efeito de cada ação e porta de confirmação |
| `app/core/browser_pilot.py` | Ciclo observação–ação no navegador, prompt com ações e regras, detecção de repetição |
| `app/core/browser_uia.py` | Observação da página: elementos numerados por região, texto com orçamento, marca de anúncio |
| `app/core/app_pilot.py` | O mesmo ciclo para qualquer janela de aplicativo |
| `app/core/uia_driver.py` | Acesso a controles por nome e tipo pela acessibilidade do Windows |
| `app/core/interaction_layer.py` | Ordem de estratégias: acessibilidade primeiro, visão como recurso |
| `app/agents/subagents.py` | `ContentGuard`, que limita e marca o texto lido antes de seguir |

A ordem de estratégias em `app/core/interaction_layer.py` também é uma decisão de ACI. Interagir por controle nomeado é preciso e verificável; interagir por visão, localizando um elemento numa imagem e clicando em coordenadas, é mais frágil e mais caro. Por isso a visão entra só quando a árvore de acessibilidade não expõe o alvo, como num canvas ou numa imagem sem texto. O README do repositório descreve a mesma hierarquia no nível do app: rotina determinística primeiro, UI Automation em seguida, visão só como último recurso.

## Exercício prático no app

O objetivo é sentir, na prática, a diferença entre um erro que só recusa e um erro que orienta. Você vai chamar as ferramentas do servidor MCP diretamente, sem passar por nenhum agente, e anotar o que volta.

Na pasta `app`, com o ambiente do projeto ativo, abra um interpretador Python e chame o `handle` do servidor com mensagens JSON-RPC montadas à mão:

```python
from mcp_server import handle

def call(name, args):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": name, "arguments": args}}
    return handle(msg)["result"]

print(call("brain_search", {"query": ""}))
print(call("brain_search", {"query": "planilha " * 400}))
print(call("brain_search", {"query": "excel", "limit": "muitos"}))
print(call("brain_read", {"path": "../config.yaml"}))
print(call("brain_read", {"path": "C:/Windows/notas.md"}))
```

Para cada chamada, registre três coisas numa tabela: o texto devolvido, o valor de `isError` e o que um agente faria a seguir só com aquela informação.

Algumas perguntas para guiar a análise. A busca vazia devolve "Erro: query vazia". Ela diz o que fazer? Uma versão melhor poderia dizer que a busca precisa de pelo menos uma palavra e dar um exemplo. A busca muito longa provavelmente não dá erro nenhum, porque o esquema não define tamanho máximo para `query`: isso é bom ou ruim para o agente? Um `limit` com texto produz a mensagem padrão do Python: o agente consegue saber qual campo corrigir? O caminho com `..` recebe uma mensagem que já indica a ação correta. O caminho absoluto fora do cofre provavelmente recebe "nota nao encontrada", porque a recusa acontece na camada de armazenamento: o agente sabe que deveria usar um caminho relativo devolvido por `brain_search`?

Depois, reescreva cada mensagem no papel seguindo o formato "o que falhou, por quê, o que fazer". Para o caminho fora do cofre, algo como: "Caminho fora do cofre. Use um caminho relativo, como os devolvidos por brain_search (ex.: '10 Agentes/Code/Code Agent.md')." Se quiser levar a mudança para o código, faça numa branch própria, acrescente um teste em `app/tests/test_mcp_server.py` que fixe o novo texto e rode a suíte.

## Erros comuns

Tratar a descrição da ferramenta como documentação para humanos. Ela é lida pelo modelo a cada chamada e decide a escolha entre ferramentas. Detalhes que um engenheiro deduziria (formato de data, unidade, se o caminho é absoluto) precisam estar escritos.

Confiar no esquema sem validá-lo no servidor. O modelo pode mandar qualquer coisa; o esquema anunciado é uma promessa que só vale se o código a cumpre.

Corrigir com prompt o que é problema de ferramenta. Acrescentar "lembre-se de usar caminho absoluto" ao prompt do sistema funciona às vezes; rejeitar caminho relativo com uma mensagem clara funciona sempre e não gasta contexto em todas as chamadas.

Esquecer o custo da observação. Cada ferramenta que devolve muito texto empurra o histórico e o objetivo para mais longe. Orçamento de saída é requisito, não otimização.

Misturar leitura e efeito na mesma ferramenta. Uma ferramenta que lê e, em certos casos, grava torna impossível autorizar por tipo de ação.

Medir só o sucesso final. Duas interfaces podem ter a mesma taxa de sucesso e custos muito diferentes em turnos, tokens e chamadas inválidas. Sem essas métricas, uma regressão de interface fica escondida.

## Para ir além

"Writing effective tools for AI agents" (Anthropic, 2025) é o guia mais direto sobre como escolher, nomear, descrever e avaliar ferramentas, com ênfase em respostas econômicas, erros úteis e no ciclo de melhoria guiado por avaliação.

"SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering" (Yang, Jimenez, Wettig et al., NeurIPS 2024) introduz o termo ACI e mostra, com experimentos de ablação, como comandos desenhados para o modelo (visualização de arquivo em janelas, busca, edição com verificação) mudam o desempenho de um mesmo modelo.

"Model Context Protocol — Specification (2025-06-18)" define o formato de ferramentas, esquemas, anotações e a separação entre erro de protocolo e erro de execução. Vale ler a seção de ferramentas junto com `app/mcp_server.py`, que implementa um subconjunto dela.
