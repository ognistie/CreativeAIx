// Arvore do Cerebro: UMA arvore que cresce com o caminho aberto. O primeiro galho (a raiz do Cerebro) entra pela
// esquerda; cada pasta aberta faz brotar um galho novo a partir do proprio icone dela, e os galhos de antes
// continuam no lugar. A vista (camera) enquadra o galho da pasta aberta.
//
// Tudo e desenhado em pixels (quadrados de 3 unidades alinhados a grade), agrupados por tom num caminho SVG
// cada um. Deterministico: a mesma pasta desenha sempre o mesmo galho (a semente e o caminho dela).
// Logica pura, testada em branchLayout.test.ts.

export const VIEW_W = 1000;
export const VIEW_H = 560;
export const PER_PAGE = 7;
/** Tons dos pixels: casca escura, casca clara, verde, verde claro, amarelo, rosa */
export const TONES = 6;
const PX = 3;

export type Point = readonly [number, number];
export type Curve = readonly [Point, Point, Point, Point];

export interface LevelSpec {
  /** caminho da pasta deste nivel ("" = raiz do Cerebro) e a pagina mostrada */
  key: string;
  /** quantos filhos aparecem neste nivel (0..PER_PAGE) */
  count: number;
  /** indice (entre os visiveis) do filho aberto, de onde brota o proximo galho */
  open?: number;
}

export interface Node {
  /** ponta do raminho, onde fica o icone */
  tip: Point;
  /** -1 em cima do galho, 1 embaixo: o galho que brotar dali segue para o mesmo lado */
  side: -1 | 1;
}

export interface Level {
  key: string;
  /** de onde o galho nasce (para a raiz, a borda esquerda) */
  anchor: Point;
  nodes: Node[];
  /** pixels por tom (TONES caminhos) */
  pixels: string[];
  /** caixa do galho e dos nomes, para a camera enquadrar */
  box: { x0: number; y0: number; x1: number; y1: number };
  /** pontos do galho (para o proximo galho escolher uma direcao livre) */
  trace: Point[];
}

export interface World {
  levels: Level[];
  /** deslocamento da cena para enquadrar o ultimo nivel, em unidades do desenho */
  camera: Point;
}

/** Semente estavel a partir do texto (FNV-1a). */
export function seedOf(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** Gerador pseudo-aleatorio pequeno e deterministico (mulberry32). */
export function random(seed: number): () => number {
  let a = seed || 1;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function at(curve: Curve, t: number): Point {
  const u = 1 - t;
  const w = [u * u * u, 3 * t * u * u, 3 * t * t * u, t * t * t];
  return [curve.reduce((s, p, i) => s + p[0] * w[i]!, 0), curve.reduce((s, p, i) => s + p[1] * w[i]!, 0)];
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Caixa aproximada de um nome (icone + ~22 letras), a direita da ponta, em unidades do desenho. */
export const LABEL_W = 150;
export const LABEL_H = 32;
export function labelBox(tip: Point) {
  return { x: tip[0] - 12, y: tip[1] - LABEL_H / 2 };
}
function overlaps(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.abs(a.x - b.x) < LABEL_W && Math.abs(a.y - b.y) < LABEL_H;
}

/** Leva um ponto do galho (desenhado na horizontal, a partir de 0,0) para o mundo: gira e desloca. */
function placer(anchor: Point, angle: number) {
  const c = Math.cos(angle), s = Math.sin(angle);
  return ([x, y]: Point): Point => [anchor[0] + x * c - y * s, anchor[1] + x * s + y * c];
}

export class Pixels {
  private seen = new Set<string>();
  readonly layers = Array.from({ length: TONES }, () => "");
  add(x: number, y: number, tone: number) {
    const gx = Math.round(x / PX) * PX, gy = Math.round(y / PX) * PX;
    const key = `${gx},${gy}`;
    if (this.seen.has(key)) return;
    this.seen.add(key);
    this.layers[tone] += `M${gx} ${gy}h${PX}v${PX}h-${PX}z`;
  }
}

function lengthOf(curve: Curve) {
  let len = 0, prev = at(curve, 0);
  for (let i = 1; i <= 24; i++) {
    const p = at(curve, i / 24);
    len += Math.hypot(p[0] - prev[0], p[1] - prev[1]);
    prev = p;
  }
  return len;
}

/** Traco pixelado que afina: miolo de casca, bordas com verde/amarelo, um rosa raro; a ponta fica pontilhada. */
export function stroke(curve: Curve, w0: number, w1: number, rnd: () => number, px: Pixels, leafy = 0.3) {
  const steps = Math.max(4, Math.round(lengthOf(curve) / (PX * 0.9)));
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const [x, y] = at(curve, t);
    const [x2, y2] = at(curve, Math.min(1, t + 0.01));
    const dx = x2 - x || 1e-6, dy = y2 - y;
    const d = Math.hypot(dx, dy);
    const nx = -dy / d, ny = dx / d;
    const width = w0 + (w1 - w0) * t;
    const k = Math.max(1, Math.round(width / PX));
    if (k === 1 && t > 0.75 && rnd() < 0.35) continue;          // ponta pontilhada
    for (let j = 0; j < k; j++) {
      const off = (j - (k - 1) / 2) * PX;
      const edge = k > 1 && (j === 0 || j === k - 1);
      const r = rnd();
      const tone = edge || k === 1
        ? (r < leafy * 0.5 ? 2 : r < leafy ? 3 : r < leafy + 0.08 ? 4 : r < leafy + 0.1 ? 5 : 1)
        : (r < 0.7 ? 0 : 1);
      px.add(x + nx * off, y + ny * off, tone);
    }
  }
}

/** Tufos de folhas: pixels verdes e amarelos por cima de um trecho do galho. */
export function tuft(curve: Curve, from: number, to: number, count: number, spread: number, rnd: () => number, px: Pixels) {
  for (let i = 0; i < count; i++) {
    const t = from + (to - from) * rnd();
    const [x, y] = at(curve, t);
    const lift = rnd() * spread * (1 - (t - from) / (to - from + 1e-6) * 0.5);
    const r = rnd();
    px.add(x + (rnd() - 0.5) * 8, y - lift + (rnd() < 0.2 ? spread * 0.4 : 0), r < 0.35 ? 2 : r < 0.75 ? 3 : r < 0.95 ? 4 : 5);
  }
}

/** Broto decorativo: pixels espacados saindo do galho. */
export function sprout(from: Point, dir: Point, length: number, rnd: () => number, px: Pixels) {
  const n = Math.round(length / (PX * 1.8));
  for (let i = 1; i <= n; i++) {
    const bend = (i / n) ** 2 * 6;
    px.add(from[0] + dir[0] * i * PX * 1.8 - dir[1] * bend, from[1] + dir[1] * i * PX * 1.8 + dir[0] * bend, rnd() < 0.6 ? 1 : 4);
  }
}

const ROOT_ANCHOR: Point = [-40, VIEW_H / 2 + 30];

/** Desenha um nivel (um galho com os filhos visiveis) e posiciona os nomes sem encostar nos que ja existem. */
function layoutLevel(spec: LevelSpec, anchor: Point, angle: number, root: boolean, placed: Array<{ x: number; y: number }>): Level {
  const rnd = random(seedOf(spec.key || "/"));
  const n = clamp(Math.floor(spec.count), 0, PER_PAGE);
  const toWorld = placer(anchor, angle);
  const px = new Pixels();

  // Galho deste nivel, desenhado na horizontal a partir do ponto de origem
  const length = root ? 1010 : 590 + rnd() * 70;
  const wave = rnd() < 0.5 ? -1 : 1;
  const local: Curve = root
    ? [[0, 0], [120, -70 - rnd() * 40], [230, 40 + rnd() * 30], [length * 0.36, -10]]
    : [[0, 0], [length * 0.28, wave * (34 + rnd() * 30)], [length * 0.62, -wave * (30 + rnd() * 26)], [length, wave * rnd() * 30]];
  const limbs: Curve[] = [local];
  if (root) limbs.push([[length * 0.36, -10], [length * 0.55, -40 - rnd() * 30], [length * 0.78, 30 + rnd() * 26], [length, -20 + rnd() * 20]]);
  const world = limbs.map((c) => c.map(toWorld) as unknown as Curve);
  world.forEach((c, i) => stroke(c, root && i === 0 ? 12 : root ? 9 : 8, i === world.length - 1 ? 2 : 6, rnd, px, 0.28));
  // Tufo grande na base (como na referencia) e um menor mais adiante
  tuft(world[0]!, 0, root ? 0.75 : 0.35, root ? 420 : 160, root ? 18 : 12, rnd, px);
  const last = world[world.length - 1]!;
  const patch = 0.25 + rnd() * 0.4;
  tuft(last, patch, patch + 0.14, 90, 9, rnd, px);

  // Cada filho fica na ponta de um raminho que sai do galho, alternando os lados
  const along = (t: number): Point => (root ? at(limbs[1]!, t) : at(local, t));
  const nodes: Node[] = [];
  let side: -1 | 1 = rnd() < 0.5 ? -1 : 1;
  for (let i = 0; i < n; i++) {
    const t = 0.06 + (0.86 * (i + 0.42 + rnd() * 0.16)) / Math.max(n, 1);
    const base = along(t);
    const long = Math.floor(i / 2) % 2 === 1;
    const reach0 = long ? 112 + rnd() * 30 : 58 + rnd() * 24;
    const forward0 = 34 + rnd() * 30;
    // Primeiro lugar livre: o nome nao encosta em nenhum nome ja posto (deste nivel ou de antes)
    let tipLocal: Point = [base[0] + forward0, base[1] + side * reach0];
    search: for (const push of [0, 36, 72, -30, 108, 144, 180]) {
      for (const delta of [0, 22, 44, 66, 88, -20, 110, 132]) {
        const candidate: Point = [base[0] + forward0 + push, base[1] + side * Math.max(44, reach0 + delta)];
        if (!placed.some((b) => overlaps(labelBox(toWorld(candidate)), b))) {
          tipLocal = candidate;
          break search;
        }
      }
    }
    const tip = toWorld(tipLocal);
    placed.push(labelBox(tip));
    const twigLocal: Point[] = [base, [base[0] + (tipLocal[0] - base[0]) * 0.2, base[1] + (tipLocal[1] - base[1]) * 0.45],
      [base[0] + (tipLocal[0] - base[0]) * 0.55, tipLocal[1] - (tipLocal[1] - base[1]) * 0.1], tipLocal];
    const twig = twigLocal.map(toWorld) as unknown as Curve;
    stroke(twig, 5, 2, rnd, px, 0.45);
    if (i % 2 === 0) tuft(twig, 0.05, 0.5, 40, 7, rnd, px);
    if (rnd() < 0.55) {
      const mid = at(twig, 0.5);
      const a = angle + side * (0.5 + rnd() * 0.4);
      sprout(mid, [Math.cos(a), Math.sin(a)], 26 + rnd() * 22, rnd, px);
    }
    nodes.push({ tip, side });
    side = side === 1 ? -1 : 1;
  }

  // Caixa para a camera: o galho inteiro e os nomes
  const points: Point[] = [];
  world.forEach((c) => { for (let i = 0; i <= 12; i++) points.push(at(c, i / 12)); });
  nodes.forEach((node) => points.push(node.tip, [node.tip[0] + LABEL_W, node.tip[1]]));
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
  const trace: Point[] = [];
  world.forEach((c) => { for (let i = 0; i <= 30; i++) trace.push(at(c, i / 30)); });
  return { key: spec.key, anchor, nodes, pixels: px.layers, trace,
    box: { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) } };
}

/** A arvore do caminho aberto: um nivel por pasta, cada um brotando do filho aberto do nivel anterior. */
export function layoutWorld(specs: LevelSpec[]): World {
  const placed: Array<{ x: number; y: number }> = [];
  const levels: Level[] = [];
  specs.forEach((spec, i) => {
    const parent = levels[i - 1];
    const opened = parent && specs[i - 1]!.open !== undefined ? parent.nodes[specs[i - 1]!.open!] : undefined;
    if (i > 0 && !opened) return;
    if (!opened) {
      levels.push(layoutLevel(spec, ROOT_ANCHOR, 0, true, placed));
      return;
    }
    // Direcao do galho novo: para o lado em que a pasta estava; se esse caminho passar por cima dos galhos e
    // nomes que ja existem, tenta outras inclinacoes e fica com a que menos esbarra (deterministico)
    const drawn = levels.flatMap((level) => level.trace);
    const names = [...placed];
    let best: { level: Level; score: number; placed: typeof placed } | undefined;
    for (const degrees of [22, 30, 14, 38, -12]) {
      const trial = [...placed];
      const level = layoutLevel(spec, opened.tip, (opened.side * degrees * Math.PI) / 180, false, trial);
      const near = (p: Point, q: Point, r: number) => Math.abs(p[0] - q[0]) < r && Math.abs(p[1] - q[1]) < r;
      // inclinar demais tambem custa: o galho fica de pe e foge da leitura da esquerda para a direita
      const score = Math.abs(degrees - 22) * 0.4 + level.trace.filter((p) => drawn.some((q) => near(p, q, 34))).length
        + 3 * level.trace.filter((p) => names.some((b) => p[0] > b.x && p[0] < b.x + LABEL_W && p[1] > b.y && p[1] < b.y + LABEL_H)).length;
      if (!best || score < best.score) best = { level, score, placed: trial };
      if (score <= 0) break;
    }
    placed.splice(0, placed.length, ...best!.placed);
    levels.push(best!.level);
  });
  // Camera: o galho da pasta aberta no meio da vista, com a origem dele sempre a vista na esquerda
  const box = levels[levels.length - 1]!.box;
  const cx = (box.x0 + box.x1) / 2, cy = (box.y0 + box.y1) / 2;
  const x = levels.length === 1 ? 0 : Math.max(VIEW_W / 2 - cx, 70 - levels[levels.length - 1]!.anchor[0]);
  const y = VIEW_H / 2 - cy;
  return { levels, camera: [x, y] };
}
