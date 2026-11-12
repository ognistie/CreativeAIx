# Relatório de implementação — Quiet Intelligence

> Especificação: `ESPECIFICACAO_DESIGN_DESKTOP_IA_REFERENCIAS.md`. Auditoria: `DESIGN_AUDIT.md`. Data: 2026-11-11.

## a. Telas alteradas

Todas herdam os tokens novos (superfícies, texto, raios, tipografia). Mudanças diretas: Conversa (composer e brilho de
voz), Harness (paletas novas e controles de fundo), fundo de todas as telas (`Ambient`).

## b. O que veio de cada referência

| Ref. | Aplicado como |
|---|---|
| R1 AI Prompt Bar | composer como componente âncora: superfície fosca única, raio 18, padding 14–18, botões de 36 px; estados `idle → focus → typing → sending → processing`, mais `error` com ícone, texto e "Fechar". O campo de texto nunca é recriado (cursor e rascunho ficam) |
| R2 Voice Effect | `VoiceGlow`: três lóbulos que nascem da borda de baixo da caixa; com o nível real do microfone já aberto (limiar 0.04, ataque 0.35, liberação 0.08); "entendendo" vira um feixe que percorre a borda; "falando" é uma respiração baixa (sem sinal de saída, não inventa nível). Nenhum microfone novo |
| R3 Chat Component | sem mudança de estrutura nesta rodada; o ritmo de mensagens já usa a entrada escalonada (F6) |
| R4 Wafer | o fio de andamento do agente na borda do composer é diferente do brilho de voz (dois canais de estado); o cartão do agente e a Atividade (F3/F4) continuam |
| R5 Date Range Picker | não aplicado: o produto não tem seletor de datas (regra da especificação) |
| R6 Auros | escuro "Abismo": base `#011D1C`, superfícies verde-petróleo, texto `#EDFFFE`/`#BBC7C6`, anel de foco `#9FE6DF`, acento raro `#FDE9FF`; claro "Pearl": `#F4F7F4`, texto `#102825`/`#4C625E`, foco `#156B64`; destaque padrão `#16897E` |
| R7 Fluted Image | `shaders/fluted.frag`: nervuras verticais que refratam o fundo inteiro (distorção forte em x, mínima em y), faixas de luz estreitas, resposta mínima ao cursor. Nunca atrás da interface: refrata só a cena do fundo |
| R8–R11 Plum, Mint, Matcha, Silk | paletas `ameixa`, `nevoa`, `matcha`, `seda` (versões claro e escuro) desenhadas pela malha `shaders/mesh.frag` (domínio deformado, três regiões de cor sobre a base e grão fino) |

## c. Capturas

`scripts/capture_ui.py` gera as capturas (fora do git, em `memory/ui-captures`):

- `UI_GPU=1` renderiza com a placa de vídeo, numa janela fora da área visível, sem foco e sem entrada;
- `UI_PALETTE=seda` tira a foto e mostra a malha.

Conferidas nesta rodada: Conversa, Atividade e Harness nos dois temas, com Abismo, Ameixa e Seda, mais a foto do
catálogo.

## d. Componentes e tokens criados

| Novo | Função |
|---|---|
| `ShaderWallpaper.qml` | malha em GPU, meia resolução (`layer.textureSize`), cerca de 30 quadros por segundo, crossfade de cores em 450 ms, para quando parado ou minimizado |
| `VoiceGlow.qml` | brilho de voz ligado a `voice_state` e `voice_level` |
| `shaders/mesh.frag`, `shaders/fluted.frag` (+ `.qsb`) | compilados por `scripts/build_shaders.py` (GLSL, HLSL e MSL) |
| `Theme`: `phosphor`, `focusRing`, `rComposer`, `durPanel`, `weightTitle`, `tracking()`, `trackingLabel`, `mesh`, `flow`, `fluted`, `flowSpeed` | tokens novos |
| `Theme`: paletas `abismo`, `ameixa`, `nevoa`, `matcha`, `seda` | paleta padrão: `abismo` |
| `core/harness.py`: `mesh`, `flow` (`parado` / `sutil` / `normal`), `fluted`, `style` e `upgrade_style()` | validação das chaves de aparência e migração única de paleta e destaque |

Valores alterados: cartão 14 → 16; `durFast` 150 → 140; pressão 0.97 → 0.985; títulos em Segoe UI Variable Display,
peso 500, com tracking negativo nos grandes.

## e. Desempenho

O que foi feito por construção: a malha renderiza em meia resolução, avança a cerca de 30 quadros por segundo e para
quando a janela é minimizada, durante a abertura, com "luzes paradas" e com o fluxo "Parado". Um único renderizador
fica no fundo, sem um canvas por cartão. Sem GPU, as luzes antigas assumem.

**Não medido:** CPU, GPU e memória em dois perfis de notebook, e o uso de memória ao trocar temas várias vezes. Fica
pendente.

## f. Testes

- Gate `check_release.py`: `CODE_READY True` (395 testes, smoke, QML, cofre).
- Contraste: 442 medidas AA, nenhuma abaixo do mínimo; as cinco paletas novas entram na medição.
- Fluxos de UI: 8 de 8. Os dois novos:
  - `composer_states`: erro, digitar limpa o erro, processando, ouvindo e entendendo;
  - `background_settings`: o fluxo e o canelado ficam gravados, e sem GPU a malha cai para as luzes.
- `tests/test_design_system.py`: shaders compilados, queda e pausa do fundo, brilho de voz sem abrir microfone, as
  seis fases do composer, validação e migração das chaves novas.
- GPU (Direct3D 11): os dois shaders compilaram e renderizaram numa janela real fora da tela.

## g. Pendências

- Medir desempenho (seção e).
- R3: ações contextuais por mensagem e detalhes de ferramenta recolhíveis.
- Escalas de 125%/150% e janela compacta de 900×650: não capturadas nesta rodada.
- Revisão na tela real pelo usuário: as capturas em GPU foram feitas fora da área visível.
