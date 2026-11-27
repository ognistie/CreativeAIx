# Observatório cognitivo 3D

O panorama do PR #4 evolui sobre os mesmos componentes. A anatomia é uma analogia funcional: regiões de
entendimento, planejamento e contexto; hipocampo para recuperação; medula para distribuição; ramificações
motoras para os agentes; plasticidade para planos aprendidos e memória científica. Não representa equivalência
biológica, pensamentos internos de um modelo ou um novo motor de execução.

## Fonte de verdade

| Região / sinal | Ponto instrumentado | O que comprova |
| --- | --- | --- |
| Estímulo e entendimento | Controller / eventos `resolved` | Pedido iniciado e interpretação concluída |
| Memória | `Brain.context_for`, Maestro e `context_engine.retrieve` | Referências selecionadas e quantidade; não seu conteúdo |
| Contexto | seleção de blocos no Brain e montagem do contexto do Maestro | Caracteres selecionados, explicitamente diferentes de tokens |
| Planejamento e decisão | Controller / revisão de plano e confirmação de efeitos | Planejamento iniciado, espera ou aprovação; não sucesso da tarefa |
| Medula e execução | despacho de subtarefa e início do passo | Agente e nome da ação, sem argumentos |
| Modelos | AIClient | Modelo chamado e tokens reportados na conclusão |
| MCP / CLI | eventos estruturados da CLI de código | Nome de ferramenta observado; comandos, argumentos e saídas não entram |
| Verificação | resultado de `apply_independent_check` | Verificado, apenas concluído, falha, bloqueio ou incerteza |
| Recuperação | `RunContext.execute_step` | Avaliação de estratégia alternativa; o resultado vem da verificação |
| Plasticidade | registro de rota e promoção de plano | Escrita efetivamente realizada; o Lab mantém aprovação e rollback existentes |

`ActivityTrace`, em `core/panorama.py`, observa a execução por ContextVar. O leitor de stdout captura um callback
restrito à telemetria; nenhuma permissão ou contexto de execução é delegado. Sequências são protegidas por lock.
Falhas do observador não alteram decisões nem a execução. A cena não pode chamar ferramentas ou aprovar ações.

O sinal `cognitiveActivity` atravessa EventBus → BridgeCore → Bridge/servidor autenticado → taskStore. O reducer
recusa outra execução, sequências duplicadas e eventos inválidos. Até 256 eventos são mantidos por operação;
excesso é contado e apresentado como registro parcial. Esses metadados acompanham a entrada do histórico
existente; não há banco ou executor paralelo. Nomes de notas podem ser pessoais: permanecem no mesmo histórico
local e no RPC autenticado, sem envio adicional a provedores.

`harnessPanorama` agrega as últimas 200 execuções e oferece até 12 operações para replay. Operações antigas sem
eventos permanecem sem replay cognitivo: sucesso global não é transformado em evidência de memória ou aprendizado.
O replay lê metadados e nunca reexecuta ações. As contagens históricas por agente continuam sendo resultados da
operação que o envolveu, e não uma certificação independente de cada agente.

## Navegação e renderização

Cinco vistas: Geral, Atividade, Contexto, Memória e Evolução. Arrastar gira 360°; roda e +/- aproximam;
setas inclinam/giram; WASD e Q/E deslocam o foco; zero restaura a vista. Selecionar uma região permite entrar
nela. Agentes e notas preservam a navegação e edição existentes; sinapses mostram seus extremos e peso.

Canvas mantém projeção e picking tridimensionais. Feixes são múltiplos traços da mesma conexão técnica,
não neurônios artificiais adicionais. Não há atividade ambiente inventada nem giro automático. Impulsos duram
até 1,2 segundo após um evento; câmera só se move por comando do usuário. Preferência de redução de movimento
é observada também quando muda durante a sessão.

Renderização limitada a cerca de 30 quadros/s, DPR máximo 2, curvas pré-calculadas e detalhe menor em painéis
estreitos. Quadros idênticos não redesenham o canvas; cenas fora da viewport suspendem o loop. O grafo apresenta
até 28 notas por agente, 22 notas comuns e 24 ferramentas/modelos observados. Todas as notas continuam disponíveis
no editor. Esses limites controlam o desenho, sem truncar o conhecimento do agente.

## Verificação reproduzível

```powershell
.\.venv\Scripts\python.exe app/scripts/check_release.py --code-only
cd ui
npm run typecheck
npm test
npm run build
npm run build:check
# Em outro terminal, na pasta ui:
npm run dev -- --port 5178
# Na raiz, com o Vite ativo:
.\.venv\Scripts\python.exe ui/scripts/probe_cognitive_ui.py
```

A prova visual usa QtWebEngine fora da tela, perfil descartável e dados fictícios explicitamente identificados.
Confere replay temporal, abertura de notas, tema claro/escuro, painel compacto, redução de movimento, ausência de
redesenho ocioso e erros JavaScript. Capturas vão para a pasta temporária; não acessa histórico pessoal, não inicia
voz, não executa ferramentas e não chama modelos. Testes de Controller confirmam separadamente a persistência e
correlação dos eventos com a execução; testes de contrato conferem o transporte pelo Bridge.

Antes, o trecho Maestro → políticas somava novamente os encaminhamentos da conversa: uma operação produzia peso 2.
Agora o peso é 1. Antes, cristais/órbita continuavam animando com movimento desativado; o relógio de animação agora
é zero nesse modo. O teste cobre também timestamp de RAF anterior ao efeito React, que antes podia produzir um
índice negativo e interromper o desenho.

## Limites de evidência

Validação desta entrega: `CODE_READY True` e `MAIN_READY True`; suíte Python completa, smoke, dependências,
compilação, cofre e whitespace aprovados. UI: 75 testes aprovados, TypeScript e build/carimbo aprovados.
A prova Qt passou as cinco verificações sem erros JavaScript e mediu zero chamadas de redesenho do canvas
durante a amostra ociosa de 600 ms. O resultado é sintético e não estima o consumo total do aplicativo.

Fixtures visuais não demonstram inteligência nem desempenho em tarefas reais. Não houve avaliação paga.
O runtime atual executa passos serialmente: a cena não inventa paralelismo. Atividade de componentes externos
sem evento estruturado continua não observada. Históricos anteriores não são reconstruídos artificialmente.
Referências ambíguas não iluminam uma nota específica. O contexto da conversa e fontes não expostas pelo runtime
não são inferidos pela visualização. Não há garantia de cobertura de todo evento interno de cada provedor/CLI.

O gate anterior atingiu timeout em ambiente restrito. O teste isolado da CLI fictícia passou fora dessa restrição;
a suíte completa também passou com os mesmos critérios. Essa diferença não é apresentada como ganho de velocidade
do código candidato. Validação em operações nativas reais continua distinta da prova visual sintética.
