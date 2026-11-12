# Prompt dedicado ao redesign do AI Farm Agent

## Missão

Observe o AI Farm Agent em execução, entenda como a pessoa realmente navega e trabalha, e redesenhe a interface existente em PySide6 e QML. O usuário já recebeu uma primeira entrega visual e ainda percebe uma estética genérica de IA. O trabalho desta rodada é localizar essa sensação em problemas observáveis de hierarquia, layout, densidade, acabamento e interação, e corrigir as causas no aplicativo atual.

Entregue mudanças aplicadas na plataforma e verificadas visualmente. Mudanças em tokens, fontes, cores e animações são parte do trabalho quando sustentam uma melhoria de composição. O aceite depende do resultado das telas completas, da clareza dos fluxos e da comparação com a versão inicial.

Este briefing cobre o redesign da plataforma existente, inclusive as telas já presentes de Lab, Biblioteca e Diário. O [briefing geral de evolução](prompt-evolucao-ai-farm-agent.md) serve como contexto de produto. Funcionalidades futuras, treinamento de agentes, conteúdo editorial novo e mudanças nas regras de execução ficam fora desta rodada. Preserve os dados, as configurações salvas e os contratos de integração. Use a experiência existente como base para decidir o que manter, reorganizar, simplificar ou redesenhar.

## 1. Abra e observe toda a plataforma antes de editar

1. Identifique a revisão e as mudanças locais. Leia as instruções do repositório e preserve as alterações em andamento. Consulte a [auditoria anterior](DESIGN_AUDIT.md), o [relatório de implementação visual](DESIGN_IMPLEMENTATION_REPORT.md) e os [relatos da primeira entrega](evolucao-entrega-1.md) e da [entrega do Lab](evolucao-entrega-2.md) como histórico. Valide cada afirmação na versão executada.
2. Abra o app desktop no Windows usando o ponto de entrada do projeto. Use um perfil ou dados de teste para percorrer os fluxos sem expor dados pessoais, acionar serviços pagos ou executar ações externas. Inspecione primeiro a janela em seu tamanho usual e depois em uma janela estreita suportada.
3. Navegue pela barra lateral expandida e recolhida, pelos atalhos e pela paleta de comandos. Visite cada página que o shell expõe. Abra menus, diálogos e painéis. Faça pelo menos a ação principal de cada tela usando dados sintéticos. Confira volta, fechamento, cancelamento, foco e preservação de rascunho onde se aplicarem.
4. Capture a linha de base com o QML real e registre tema, fundo, dimensões, escala e conteúdo de teste. Use o script de capturas existente com dados sintéticos para cobrir as páginas. Complete as capturas com observação interativa para validar navegação, teclado, scroll, redimensionamento, estados de voz simulados e comportamento da janela. Se algum cenário exigir hardware, microfone, conta ou ambiente indisponível, registre a lacuna e prossiga com as observações verificáveis.
5. Cruze a observação visual com os arquivos QML e os contratos do Bridge. Distinga um defeito do componente compartilhado de um problema localizado na composição da página. Mapeie dimensões implícitas, restrições de largura, donos do scroll, estilos definidos localmente, estados que dependem de sinais e elementos que aparecem apenas em certos temas ou modos de janela.

### Inventário mínimo

Percorra as páginas **Conversa, Histórico, Sobre, Configurações, Segundo Cérebro, Você, Harness, Atividade, Diário, Biblioteca e AI Research Lab**, confirmando os nomes e rotas na revisão aberta. Inclua as superfícies transversais **abertura, barra de título, barra lateral, paleta de comandos, mini chat, Composer, menus, diálogos, seletores e notificações**. Avalie a tela inicial, uma execução em andamento e um resultado concluído em Conversa. Use simulação para confirmar que ações sensíveis e cancelamento mantêm seu comportamento.

### Diagnóstico obrigatório

Para cada página, registre **tarefa principal, captura inicial, problema observável, impacto, causa provável em QML, mudança proposta e critério visual de aceite**. Use estados representativos, como uma lista com dados, uma descrição longa, um formulário com erro ou um histórico vazio. Para um elemento que já funciona visualmente, anote o motivo para preservá-lo.

Baseie as mudanças em evidências específicas. Exemplos de diagnóstico são uma tabela com texto diretamente sobre uma área clara do papel de parede, uma seleção indicada só pela cor, um título que desloca a primeira ação para fora da janela, uma linha truncada sem caminho para ler o valor completo ou dois painéis com larguras que não seguem a mesma grade. Registre se cada caso foi de fato observado antes de tratá-lo como defeito.

## 2. Defina uma direção única para a interface

Use como direção um aplicativo desktop compacto, com hierarquia editorial e superfícies de trabalho legíveis. Preserve a identidade do AI Farm Agent, incluindo temas, cores de destaque, papéis de parede e modos de fundo existentes. Faça a identidade aparecer na composição, no comportamento dos componentes e na consistência entre as páginas.

### Hierarquia, densidade e composição

- Use um título claro por página. Mantenha texto introdutório quando ele orientar uma decisão real. Coloque busca, filtro ou ação principal perto do conteúdo a que se aplicam.
- Use alinhamento consistente para título, barra de ações e conteúdo. Defina largura de leitura para textos e editor. Permita que listas, tabelas e workspaces usem a largura disponível quando isso melhorar o trabalho.
- Dê funções distintas a botão primário, ação secundária, ação em linha e ação destrutiva. Em listas, exponha a ação frequente e organize ações menos usadas no menu correspondente. Preserve o feedback e a confirmação de cada operação.
- Use linhas para registros repetidos, seções para agrupar controles relacionados e cards quando houver uma unidade de conteúdo ou interação que precise de separação. Revise onde caixas aninhadas, cabeçalhos repetidos, numeração decorativa ou etiquetas sem função tornam a leitura mais lenta.
- Use superfícies de leitura que mantenham contraste sobre fundo liso, malha e fotografia. Reserve o vidro e o desfoque às áreas onde ajudam na composição. Garanta um fallback legível com renderização por software. Evite que o papel de parede determine a legibilidade de uma linha ou a visibilidade de um estado.
- Dê tratamento consistente a foco, hover, seleção, pressionamento, desabilitado e erro. Estados importantes precisam ser distinguíveis por texto, ícone, forma ou posição além da cor. O foco deve permanecer visível e voltar a um lugar previsível após fechar uma sobreposição.
- Use movimento para explicar origem, troca de estado ou continuidade espacial. Respeite a preferência de movimento reduzido e preserve a operação por teclado durante transições.

### Traduza as referências em decisões

- **Refero.** Use como referência para tipografia, densidade e componentes discretos. Observe botões, divisores e bordas finas e adapte esses princípios aos tokens do app. [Refero Styles](https://styles.refero.design/style/dc541737-8bf2-4b31-b729-0352f696e82f)
- **Raycast.** Use a paleta existente como ponto de partida. Confira abertura, busca, seleção por setas, execução com Enter, saída com Esc, atalhos visíveis e devolução de foco. Preserve as permissões das ações abertas pela paleta. [Raycast](https://www.raycast.com/)
- **Scrolltide.** Use a navegação com transição como referência de continuidade do item selecionado. Adapte a ideia a QML e aos estados da barra lateral. Preserve contraste, leitura imediata e a opção de navegação estática. [Scrolltide Components](https://www.scrolltide.co/components#c-morph-navbar)

Registre quais decisões vieram da observação do app e quais vieram das referências. Use a identidade e os componentes do próprio produto na implementação.

## 3. Aplique mudanças precisas por superfície

As direções abaixo partem dos seis prints da conversa e das páginas presentes no repositório. Confirme cada hipótese na versão atual. Preserve soluções que já atendam ao objetivo e mude o que ainda prejudica o fluxo.

| Superfície | Mudança que deve ser investigada e aplicada quando pertinente | Aceite observável |
|---|---|---|
| **Shell e navegação** | Organizar grupos, seleção, largura da barra, cabeçalhos e área de conteúdo. Revisar atalho, posição e foco da paleta já implementada. | A página ativa é identificada de imediato nos estados expandido e recolhido. Teclado e mouse abrem o mesmo destino, e fechar a paleta devolve o foco. |
| **Conversa e mini chat** | Tornar o Composer o ponto de ação principal. Reorganizar área inicial, mensagens, progresso, passos, confirmação e resultado. Distinguir visualmente estado da voz e estado da tarefa. | A caixa de entrada permanece previsível. Uma transição de estado preserva texto e cursor. A ação pendente e os comandos de parar e responder continuam acessíveis. |
| **Harness e “Como usar”** | Reduzir o peso do painel introdutório e mover a ajuda extensa para contexto. Tornar o fluxo Você → Maestro → Agentes navegável, com detalhes no painel do agente selecionado. | A primeira ação útil aparece cedo na tela. A pessoa abre a ajuda quando precisa e encontra os controles do agente sem percorrer blocos repetidos. |
| **Aparência** | Reorganizar tema, paleta, cor, papel de parede e movimento. Revisar seleção, rótulos, amostras cortadas e indicação de persistência. | A seleção fica explícita, a grade se adapta à largura e a pessoa distingue prévia, aplicação imediata e configurações salvas conforme o comportamento real. |
| **Histórico** | Agrupar título, busca, filtros e lista na mesma grade. Dar superfície própria às linhas e manter plano, passos e evidência em detalhes acessíveis. | Texto e metadados continuam legíveis com a fotografia ativa. Busca, estado vazio, seleção e leitura dos detalhes são verificáveis. |
| **Atividade** | Colocar execuções ativas e itens aguardando a pessoa antes do consumo. Dar base legível a gráficos e listas e usar rótulos, unidades e períodos reais. | O próximo passo fica claro com ou sem tarefa ativa. Valores indisponíveis têm estado próprio e as métricas exibidas correspondem aos dados de teste. |
| **Configurações** | Substituir blocos excessivos por seções e linhas de configuração. Aproximar estado da conexão, versão e ação corretiva nas integrações. | É possível localizar a configuração desejada e entender o próximo passo de uma integração indisponível sem expor credenciais. |
| **Segundo Cérebro e Você** | Revisar organização entre busca, navegação, mapa, visualização e editor. Ajustar layout quando não houver espaço para painéis simultâneos. | A pessoa encontra uma nota e volta à lista, lê e edita com largura suficiente e distingue origem, estado de edição e informações pessoais. |
| **Diário** | Priorizar escrita, prioridades e navegação por data. Mostrar salvamento, privacidade e indexação no contexto da nota. | Dá para criar, salvar e reabrir uma entrada de teste. Os estados de privacidade e recuperação são legíveis e coerentes com a integração existente. |
| **Biblioteca** | Dar hierarquia a busca, filtros, trilha e leitura. Usar listas de materiais com nível e tipo legíveis e página de leitura com largura confortável. | A pessoa encontra um tema, abre um material e volta preservando o contexto da busca quando o fluxo existente permitir. |
| **AI Research Lab** | Organizar seleção de agente e versão, tarefa atual e inspetor. Usar espaço de trabalho, listas e painéis conforme a densidade técnica. Mostrar estados das capacidades já existentes. | A primeira ação do Lab é clara, parâmetros e resultados são legíveis e capacidades indisponíveis têm indicação real. Os controles existentes continuam acessíveis. |
| **Sobre, abertura e componentes auxiliares** | Harmonizar título, tipografia, ícones, menus, diálogos e mensagens com o restante do app. | A abertura e o fechamento mantêm seus fluxos e a identidade se mantém em janelas e sobreposições. |

## 4. Implemente no QML existente e revise em ciclos

1. Comece com um recorte representativo de **Conversa, Histórico e Configurações**. Ele precisa exercitar composição, leitura de dados e controles. Implemente as primeiras correções e renderize as três telas. Ajuste o sistema até que as diferenças de hierarquia e legibilidade apareçam nas capturas em condições idênticas às da linha de base.
2. Consolide a direção nos componentes realmente compartilhados. Inspecione `Main.qml`, `Theme.qml`, `PageHeader.qml`, `GlassPanel.qml`, `NavItem.qml`, `Button.qml`, `AppField.qml`, `Composer.qml`, `CommandPalette.qml` e os componentes que o inventário apontar. Introduza variantes quando houver uma necessidade repetida e migre os usos pertinentes.
3. Aplique mudanças de composição nas páginas existentes. Teste o QML após cada grupo de mudanças. Ajuste as restrições de layout, quebra de texto, largura de leitura, altura de linhas e rolagem a partir do que for observado em janela normal e estreita.
4. Verifique as superfícies auxiliares e as interações depois de atualizar as páginas. Preserve atalhos, destinos de navegação, dados salvos, sinais do Bridge e políticas de execução. Se a interface precisar de um novo dado, explique a dependência e use o menor ajuste necessário no contrato.
5. Faça uma última inspeção comparativa da plataforma completa. Retorne aos seis prints, registre o que mudou em cada área e corrija as inconsistências que ainda aparecerem. Um componente aprovado em isolamento precisa funcionar também no contexto real da página.

## 5. Evidência e critérios de aceite

- **Comparação visual.** Gere antes e depois com o mesmo tamanho, tema, fundo e dados sintéticos. Cubra todas as rotas. Para cada mudança relevante, indique a diferença observável e o arquivo onde foi aplicada. Registre as áreas preservadas e o motivo.
- **Matriz representativa.** Cubra claro e escuro, fotografia clara e escura, janela normal e estreita, escala comum e ampliada no Windows e movimento reduzido. Priorize as combinações que expõem problemas de leitura, quebra e foco. Registre limitações de renderização ou de hardware.
- **Uso real da interface.** Percorra navegação, busca, menus, campos, estados vazios, erro, cancelamento e confirmações em ambiente de teste. Verifique ordem de Tab, foco visível, atalhos e devolução do foco. Teste labels longos, valores ausentes e listas cheias.
- **Legibilidade.** Verifique o contraste nos tokens e também no resultado renderizado com fundos e transparências. Confirme que títulos, ações e conteúdo importante não ficam cortados, sobrepostos ou escondidos no tamanho mínimo suportado.
- **Regressão.** Use as verificações existentes de QML, fluxos da interface e contraste. No repositório atual, procure `capture_ui.py`, `smoke_ui.py`, `ui_flows.py` e `check_contrast.py`. Confirme os comandos antes de executar e registre saída e limitações. Se houver comparação entre GPU e software, identifique qual renderizador produziu cada resultado.
- **Completude.** O smoke verde comprova carregamento. O aceite do redesign também exige inspeção humana ou visual documentada das telas, comparação antes/depois e verificação das ações principais. Mantenha abertas as lacunas que não puderem ser observadas.

### Formato de entrega

Entregue o redesign aplicado e um relatório curto com:

1. **Inventário observado**, com a lista de telas e superfícies percorridas.
2. **Diagnóstico e correções**, com uma linha por problema relevante, a intervenção e sua evidência.
3. **Capturas antes/depois**, organizadas por tela, tema e condição. Use dados sintéticos ou anonimizados.
4. **Verificações executadas**, separando observação interativa, comparação visual, testes automatizados e lacunas de ambiente.
5. **Arquivos e decisões**, destacando mudanças compartilhadas, alterações localizadas e decisões de identidade que precisam ser mantidas.

## Skills recomendadas

Use `ux-product-designer` para observar jornadas e navegação, `premium-ui-designer` para composição e hierarquia, e `design-system-architect` para tokens e componentes compartilhados. A implementação QML usa `senior-software-engineer`. Use `process-verifier` na etapa de aceite para relacionar cada afirmação a uma captura, interação ou teste observado. Ative as skills conforme a etapa.
