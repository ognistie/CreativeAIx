# Redesign — relatório curto (Creative AIx)

Rodada de 12/11/2026. Mesmas condições antes e depois: `scripts/capture_ui.py` com `UI_GPU=1 UI_SYNTHETIC=1
QT_SCALE_FACTOR=1.5 UI_SIZE=1280x720` (2400 × 1350 px), temas escuro e claro, dados sintéticos (nada da pasta
pessoal). As capturas ficam em `app/memory/ui-captures/` (fora do Git).

## 1. Inventário

| Tela | Estado antes | O que mudou |
|---|---|---|
| Barra superior (todas) | três estilos lado a lado: círculo de vidro, pílula de vidro no título, chips soltos | barra única: ícones sem moldura, título em texto, agente num controle segmentado; um vidro só no claro com foto |
| Conversa | ok | recebe a barra nova |
| Histórico, Configurações, Cérebro, Você, Harness, Atividade, Sobre | ok (rodada anterior) | só a barra e o nome novo |
| Diário | lista + editor direto | início com 4 pastas; lista e editor dentro da pasta |
| Biblioteca | cartões com texto curto (100–270 palavras) | capas por tema; artigo de 5 seções (250–500 palavras); referências no fim |
| AI Research Lab | 6 abas, 2 linhas de chips, formulário e vários diálogos | uma tela em 3 passos: versões → comparar → resultado |

## 2. Diagnóstico e correções

- **Barra fora do padrão.** Cada peça tinha seu próprio vidro e forma; o seletor de agente eram três chips
  independentes, sem relação visual de escolha exclusiva. Correção: `components/Segmented.qml` (trilho + marca que
  desliza, setas trocam) e `IconButton.flat` para botões dentro de uma barra que já tem vidro.
- **Lab difícil de ler.** O caminho principal (criar versão, comparar, decidir) estava espalhado por abas com
  funções avançadas no mesmo nível. Correção: os três passos numerados numa tela; o seletor de agente vira um botão
  com menu do app (a caixa nativa destoava); "Promover" só habilita com a checagem de promoção aprovada. Código fica
  no Harness › Desenvolvedor, evidência dos passos no Histórico.
- **Biblioteca rasa.** Os artigos marcavam "1 min" em todos os temas. Correção: textos expandidos com exemplo e
  funcionamento; links só no fim.
- **Pastas do Diário com luzes escuras.** As cores vinham como texto e `Theme.alpha` lia `r/g/b` indefinidos (preto).
  Correção: `Qt.color(...)` antes do alfa. A dica longa de "Notas para os agentes" passava por baixo do "+"; agora
  ganha linha própria com reticências.
- **Cores soltas nas telas novas** (capas, pastas, botão "+") quebravam o teste de tokens. Agora são tokens do Theme
  (`artCovers`, `artFolders`, `artInk`, `artBadgeText`).

## 3. Verificações

| Verificação | Resultado |
|---|---|
| `scripts/check_release.py` (dependências, compilação, 447 testes, smoke, QML, cofre, espaços) | `CODE_READY True` |
| `scripts/check_contrast.py` | 442 medidas, 0 abaixo do mínimo |
| `scripts/ui_flows.py` (inclui `lab_experiment`, `diary_cycle`, `library_search`, `keyboard_controls`) | 14/14 ok |
| Capturas antes/depois, mesmas condições | conferidas a olho: barra, Lab, Biblioteca, Diário |

Limite conhecido: as capturas "claro" das telas depois do Harness saem no tema salvo, porque o Harness reaplica a
aparência ao abrir (comportamento da captura, não do app).

## 4. Arquivos e decisões

- Novos: `components/Segmented.qml`, `components/FolderCard.qml`, `core/library_articles.py`.
- Reescritos: `views/LabView.qml`, `views/LibraryView.qml`; cabeçalho em `Main.qml`; pastas em `views/JournalView.qml`.
- Nome: textos visíveis, prompts e docs viram "Creative AIx". Pastas do código, pasta de dados
  (`Documentos/AI Farm Agent`) e a identidade do app no Windows ficam iguais para não perder dados nem atalhos.
- Segurança: abertura de arquivos sem passar por `cmd` (`os.startfile`); revisão de caminhos nos slots da Bridge
  (Cérebro, Lab, papéis de parede) sem achados.
