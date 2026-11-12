# Auditoria de design — Quiet Intelligence

> Base: `ESPECIFICACAO_DESIGN_DESKTOP_IA_REFERENCIAS.md` (11 referências: Inspora, Auros, Scrolltide, Scroll Shaders,
> Wafer). Feita em 2026-11-11 sobre o estado depois das fases F1–F6 (`estudo-inspora.md`).
> As referências são direção, não molde: nada de marca, texto, código ou asset de terceiros foi copiado.

## 1. Inventário

| Item | O que existe |
|---|---|
| Stack | PySide6 6.12 + QML (Qt Quick), Windows; RHI (Direct3D 11) na máquina real, renderizador por software no smoke/CI |
| Tokens | `desktop/qml/components/Theme.qml` (singleton): superfícies, texto, paletas claro/escuro, raios, movimento, tipografia |
| Contraste | `scripts/check_contrast.py` mede AA de todo par texto/superfície em todas as paletas e nos dois temas |
| Componentes | GlassPanel (vidro com desfoque real em GPU), Composer, NavItem, Chip, Button, IconButton, PlanCard, PhaseStepper, ChoiceTile, KeyValue, Skeleton, EmptyState, Enter |
| Fundo | `Ambient.qml`: luzes (Canvas com gradiente radial) + papel de parede com paleta extraída |
| Voz | `desktop/voice.py` emite `voice_state` (off, idle, recording, listening, thinking, speaking) e `voice_level` (RMS do mesmo microfone) |
| Agentes | sinais `phaseChanged`, `stepStart/Done`, `apiUsage`, `planReview`; cartão do agente e tela Atividade |
| Testes | 395 testes, 8 fluxos reais de UI fora da tela (`scripts/ui_flows.py`), smoke de QML, contraste |

## 2. Diagnóstico frente à especificação

| Área | Antes | Problema |
|---|---|---|
| Superfícies | cinza-azulado neutro (`#1B1B22`), preto puro no vidro | sem identidade cromática; profundidade só por transparência |
| Paletas | 8 paletas pastel (aurora…) | nenhuma noturna profunda (Plum), nenhuma "silenciosa" para texto (Mint/Matcha), nenhuma sedosa (Silk) |
| Fundo | manchas Canvas em deriva | não há malha orgânica, nem fluxo ajustável, nem efeito de vidro (Fluted) |
| Composer | foco por borda azul; sem estados nomeados | sem "enviando", sem "processando" distinto da voz, erro do microfone só no log |
| Voz | barras de volume e anel no botão | não há brilho que nasce da caixa; "entendendo" e "falando" só em texto |
| Tipografia | títulos Bahnschrift DemiBold | peso alto demais para a direção "quiet"; sem tracking negativo |
| Raios | cartão 14 | especificação: controle 10, cartão 16, composer 18 |
| Movimento | 150/220/400 | faltava a duração de painel (320); pressão 0.97 marcada demais |

## 3. Decisões que preservam a identidade

- Mesma estrutura de telas, rotas, barra lateral agrupada, cartões e fluxos; nenhum componente público mudou de API.
- Vidro com desfoque real continua sendo a superfície de leitura; o texto nunca fica direto sobre o fundo animado.
- Paletas antigas e papéis de parede continuam disponíveis; a migração troca só paleta e destaque, uma vez.
- Tudo que se move respeita "luzes paradas" (`Theme.motion`) e o fluxo "Parado".
- Sem dependência nova: os shaders são GLSL compilados com o `qsb` que já vem no PySide6.

## 4. Prioridades

1. Tokens Abyss/Pearl (eixo Auros) com contraste medido.
2. Fundo em malha (Plum, Mint, Matcha, Silk e Abismo) + Fluted, com queda para as luzes sem GPU.
3. Composer com estados reais e brilho de voz ligado ao sinal existente.
4. Tipografia, raios e movimento conforme a especificação.

Fora de escopo, por regra da própria especificação: seletor de intervalo de datas (o produto não tem um) e brilho de
saída de voz (não há sinal real de nível de saída; o estado "falando" usa uma respiração baixa, sem fingir nível).
