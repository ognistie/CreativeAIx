# Papéis de parede gerativos

Estado em 2026-11-18. Cenas desenhadas em dithering ou halftone com as cores da paleta atual. Preferências antigas de ASCII passam para dithering na mesma paisagem.

## Arquitetura

Conteúdo antes do estilo, em duas etapas:

| Peça | Arquivo | Faz |
| --- | --- | --- |
| Cena | `ui/src/lib/scenes.ts` | campo de luz `f(u, v) -> 0..1` + região (0 fundo, 1 chão/água, 2 assunto, 3 luzes) |
| Direção de arte | `ui/src/lib/wallpaper/art.ts` | algoritmo de dithering, tamanho das marcas, movimento e giro de cor das regiões por cena |
| Buffer da cena | `ui/src/lib/wallpaper/engine.ts` (`FieldSampler`) | amostra a cena numa grade com supersampling adaptativo (cantos compartilhados; bordas ganham mais amostras; luz pontual não some) |
| Máscara da interface | `engine.ts` (`applySafe`) | menos luz e contraste atrás da barra lateral e dos blocos `data-wallpaper-safe` (título, caixa de pedido) |
| Estilos | `ui/src/lib/generative.ts` | dithering (Bayer 8×8, ruído azul ou Atkinson) e halftone (raio pela área de luz) |
| Movimento | `ui/src/lib/wallpaper/motion.ts` | partículas da própria cena (estrelas, bolhas, poeira), posição função pura do tempo |
| Worker | `ui/src/lib/wallpaper/scene.worker.ts` | amostra a cena e transfere o buffer ao fundo principal |
| Componente | `ui/src/components/GenerativeCanvas.tsx` | agenda e cancela pinturas, mede as zonas da interface e mantém o quadro anterior até o próximo estar pronto |

O buffer fica em cache por cena e grade. Trocar paleta, destaque ou máscara reaproveita esse buffer. Quando falta
o buffer do fundo principal, um worker calcula a cena. Se o worker estiver indisponível ou falhar, o cálculo roda
em fatias canceláveis na interface. A abertura e o app usam o mesmo fundo. O canvas estático usa até 2560 pixels
no maior lado e a camada de partículas, até 1920. Isso limita o trabalho em janelas maiores.

O movimento roda a 30 qps, ou 15 qps se o quadro passar de 6 ms. Ele para quando:
- a janela está sem foco ou escondida;
- "Movimento" está desligado no Harness;
- o sistema pede redução de movimento.

Miniaturas usam o mesmo motor sem máscara e sem movimento e começam a renderizar perto da área visível.

## Controles em Aparência

O catálogo oferece Synthwave, Aquário, Velho Oeste, Gatinhos, Frutas, Rio de Janeiro, Noite estrelada, Jardim,
Bosque, Lago e Praia. Em **Avançado**, é possível escolher o algoritmo do dithering, a qualidade do fundo e o
nível de movimento das partículas. **Auto** usa a direção de arte da cena e adapta a qualidade ao computador.

## Criar ou ajustar um preset

1. **Cena:** escreva a função em `scenes.ts`, com `u` de 0 a `A` (proporção da tela) e `v` de 0 (topo) a 1.
   - Marque as regiões com `z(região, luz)`.
   - Ponha o assunto fora da coluna do meio, que é a área de descanso.
   - Teste uma caixa antes do cálculo fino, porque a cena é lida cerca de uma vez por célula.
2. **Direção de arte:** em `art.ts`, escolha `dither`, `halftoneCell`, `ditherPx`, `motion` e `hues` (giro de cor do chão e das luzes a partir do destaque).
3. **Conferir:**
   - `npm run dev` e abra `/bench/?view=single&combo=<id>&style=<estilo>`. Outras vistas: `view=compare` (antes × depois), `view=grid` (todas as cenas) e `view=perf` (tempo).
   - Os testes de composição ficam em `engine.test.ts`.

## Medições históricas antes do worker

O que trava a interface é o maior bloco de trabalho seguido na thread principal:

| Resolução | Estilo | Antes (desenho inteiro) | Depois: maior fatia + pintura |
| --- | --- | --- | --- |
| 1920×1080 | Dithering | 256 ms | 12 + 16 ms |
| 1920×1080 | Halftone | 29 ms | 8 + 12 ms |
| 3840×2160 | Dithering | 996 ms | 17 + 36 ms |
| 3840×2160 | Halftone | 146 ms | 13 + 31 ms |

- Medido com o painel do navegador em segundo plano: os números servem para comparar antes × depois, não como meta.
- Sem cache, o desenho completo do depois é parecido com o antes ou um pouco mais caro, porque o supersampling custa amostras. O ganho está em não bloquear a interface e em não repetir o trabalho.
- Não medido: quadros por segundo do movimento em hardware de entrada, memória e vários monitores com DPI diferente.

Imagens antes × depois: `app/captures/wallpapers-2026-11-18/`.

## Trade-offs e o que ficou de fora

- **Compatibilidade do worker:** o QtWebEngine no Windows enviou e recebeu mensagens de workers clássico e de
  módulo sob `app://`. O build empacotado também recebeu os buffers de seu worker de módulo. A pintura fica no
  Canvas 2D da interface.
- **Movimento só nas partículas:** a cena fica parada e não há parallax. Isso evita tremor de amostragem e repintura da tela inteira.
- **Catálogo:** Synthwave, Aquário e Velho Oeste têm desenho revisado. O catálogo inteiro usa supersampling,
  máscara e os algoritmos de dithering e halftone.
- **Sem perfil Eco/Alto automático para a cena:** só a camada de movimento se adapta. O tamanho das marcas acompanha a largura da janela.
