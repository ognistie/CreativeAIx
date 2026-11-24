// Memoria dos agentes como uma medula espinhal, no MESMO traco em pixels da arvore do Cerebro (lib/branchLayout.ts).
//
// Leitura do desenho = fluxo de um pedido:
//   cauda (embaixo)   -> o pedido entra (voz ou texto); as raizes viram a cauda equina
//   medula            -> o tronco vira a coluna: vertebras de osso em pixel, com luz em cima e sombra embaixo
//   cerebro (topo)    -> a copa vira o cerebro do Maestro (sulcos e volume em pixel); as notas dele ficam em volta
//   nervos            -> os galhos viram pares de nervos, um agente por nervo; as folhas sao as notas da pasta dele
//   frutos            -> notas que mais de um agente usa (memoria comum), perto da medula
//
// Deterministico (sementes pelo nome) e puro: testado em agentSpine.test.ts.

import { at, Pixels, random, seedOf, stroke, tuft, type Curve, type Point } from "./branchLayout";

export const SPINE_W = 1000;
export const SPINE_H = 640;
const PX = 3;
const CX = SPINE_W / 2;
const BRAIN: Point = [CX, 98];
const BRAIN_RX = 150;
const BRAIN_RY = 70;
const STEM: Point = [CX, BRAIN[1] + BRAIN_RY - 8];
const ROOT: Point = [CX, SPINE_H - 30];
const MAX_LEAVES = 12;

export interface SpineAgentInput {
  id: string;
  /** notas da pasta do agente (rel) */
  own: string[];
  /** notas fora da pasta que o agente usa (rel) */
  uses: string[];
}

export interface SpineNote { rel: string; x: number; y: number; agent: string }
export interface SpineShared { rel: string; x: number; y: number; owners: string[] }
export interface SpineNerve {
  id: string;
  side: -1 | 1;
  /** altura da vertebra de onde o nervo sai */
  level: number;
  base: Point;
  tip: Point;
  /** caminho do cerebro, descendo a medula, ate a ponta do nervo (pulso da delegacao) */
  flow: string;
  /** pixels do nervo por tom (mesmos tons da arvore) */
  pixels: string[];
  notes: SpineNote[];
  /** notas que nao couberam no desenho (o painel lista todas) */
  hidden: number;
}
export interface AgentSpine {
  /** medula e cauda equina: pixels nos tons da arvore */
  cord: { pixels: string[]; flow: string; root: Point; stem: Point };
  /** vertebras: 0 sombra, 1 osso, 2 luz, 3 brilho */
  bones: string[];
  /** cerebro: 0 sulco/contorno, 1 base, 2 luz, 3 brilho */
  brain: { pixels: string[]; center: Point; agent?: string; notes: SpineNote[] };
  nerves: SpineNerve[];
  shared: SpineShared[];
}

const r1 = (v: number) => Math.round(v * 10) / 10;
const d = (c: Curve) => `M${r1(c[0][0])} ${r1(c[0][1])}C${r1(c[1][0])} ${r1(c[1][1])} ${r1(c[2][0])} ${r1(c[2][1])} ${r1(c[3][0])} ${r1(c[3][1])}`;

/** Cerebro em pixels: dois hemisferios, a fissura no meio, sulcos ondulados e luz vindo de cima a esquerda. */
function brainPixels(): Pixels {
  const px = new Pixels();
  const rnd = random(seedOf("cerebro"));
  const [cx, cy] = BRAIN;
  const hx = BRAIN_RX * 0.4, rx = BRAIN_RX * 0.62, ry = BRAIN_RY;
  for (let y = cy - ry; y <= cy + ry; y += PX) {
    for (let x = cx - BRAIN_RX - 6; x <= cx + BRAIN_RX + 6; x += PX) {
      const side = x < cx ? -1 : 1;
      // hemisferio: elipse um pouco achatada embaixo (lobo temporal mais estreito)
      const ex = (x - (cx + side * hx)) / rx;
      const ey = (y - cy) / (y > cy ? ry * 0.82 : ry);
      const inside = ex * ex + ey * ey;
      if (inside > 1) continue;
      if (Math.abs(x - cx) < 3 && y < cy + ry * 0.45) continue;            // fissura longitudinal
      const edge = inside > 0.8;
      // giros e sulcos: ondas cruzadas, mais densas, que lembram o cortex visto de cima
      const groove = Math.sin(x * 0.16 + Math.sin(y * 0.11 + side * 1.3) * 2.6) * Math.cos(y * 0.15 + Math.sin(x * 0.07) * 2.2);
      const light = -ex * 0.35 - ey * 0.75;                               // luz de cima e da esquerda
      let tone = 1;
      if (edge || groove > 0.5) tone = 0;
      else if (light > 0.35 + rnd() * 0.25) tone = rnd() < 0.18 ? 3 : 2;
      else if (light < -0.45 && rnd() < 0.6) tone = 0;
      px.add(x, y, tone);
    }
  }
  // tronco cerebral descendo ate a medula
  for (let y = cy + ry * 0.55; y <= STEM[1] + 10; y += PX) {
    for (let x = cx - 9; x <= cx + 9; x += PX) px.add(x, y, Math.abs(x - cx) > 6 ? 0 : x < cx ? 2 : 1);
  }
  return px;
}

/** Uma vertebra em pixels: corpo arredondado (luz em cima, sombra embaixo) e os processos transversos dos lados. */
function vertebra(px: Pixels, y: number, w: number, h: number, rnd: () => number) {
  const blob = (cx0: number, cy0: number, bw: number, bh: number) => {
    for (let yy = cy0 - bh / 2; yy <= cy0 + bh / 2; yy += PX) {
      for (let xx = cx0 - bw / 2; xx <= cx0 + bw / 2; xx += PX) {
        const ex = (xx - cx0) / (bw / 2), ey = (yy - cy0) / (bh / 2);
        const q = ex * ex * 0.55 + ey * ey;                               // retangulo de cantos redondos
        if (q > 1) continue;
        const v = (yy - cy0) / (bh / 2);                                  // -1 em cima, 1 embaixo
        let tone = 1;
        if (q > 0.78 || v > 0.55) tone = 0;
        else if (v < -0.35) tone = rnd() < 0.2 ? 3 : 2;
        else if (ex < -0.55 && rnd() < 0.5) tone = 2;
        px.add(xx, yy, tone);
      }
    }
  };
  blob(CX, y, w, h);
  for (const side of [-1, 1]) blob(CX + side * (w / 2 + 7), y + 3, 16, 8);
}

/** Monta a medula. "MAESTRO" vai para o cerebro; os outros saem em pares de nervos, subindo a coluna de baixo para cima. */
export function layoutAgentSpine(input: SpineAgentInput[]): AgentSpine {
  const head = input.find((a) => a.id === "MAESTRO");
  const body = input.filter((a) => a.id !== "MAESTRO");

  // Medula: leve curva em S, como a coluna vista de lado e endireitada
  const cordPx = new Pixels();
  const rc = random(seedOf("medula"));
  const cord: Curve = [ROOT, [ROOT[0] - 14, ROOT[1] - 160], [STEM[0] + 14, STEM[1] + 160], STEM];
  stroke(cord, 16, 12, rc, cordPx, 0.06);
  // Cauda equina: as raizes da arvore viram os feixes que saem da base da coluna
  for (const dx of [-110, -70, -34, 30, 66, 108]) {
    const strand: Curve = [[ROOT[0] + dx * 0.08, ROOT[1] - 8], [ROOT[0] + dx * 0.4, ROOT[1] + 2], [ROOT[0] + dx * 0.75, ROOT[1] + 10], [ROOT[0] + dx, ROOT[1] + 16]];
    stroke(strand, 5, 2, rc, cordPx, 0.05);
  }

  // Vertebras ao longo da medula; os nervos saem de algumas delas, em pares (esquerda e direita)
  const pairs = Math.max(1, Math.ceil(body.length / 2));
  const count = Math.max(9, pairs * 2 + 3);
  const tOf = (k: number) => 0.1 + (0.78 * k) / (count - 1);           // t na curva (0 = base, 1 = cerebro)
  const bonesPx = new Pixels();
  const rb = random(seedOf("vertebras"));
  for (let k = 0; k < count; k++) {
    const [, y] = at(cord, tOf(k));
    const big = 0.7 + 0.3 * (1 - k / count);                              // mais largas embaixo (lombar), estreitas em cima
    vertebra(bonesPx, y, 56 * big + 14, 24, rb);
  }
  // pares espalhados pela coluna: o primeiro perto do cerebro, o ultimo perto da base
  const nerveLevels = Array.from({ length: pairs }, (_, p) => Math.round(2 + ((count - 5) * (pairs - 1 - p)) / Math.max(pairs - 1, 1)));

  const nerves: SpineNerve[] = body.map((agent, i) => {
    const px = new Pixels();
    const r = random(seedOf(agent.id));
    const side: -1 | 1 = i % 2 === 0 ? -1 : 1;
    const pair = Math.floor(i / 2);
    const k = nerveLevels[pair] ?? 1;
    const [bx, by] = at(cord, tOf(k));
    const base: Point = [bx + side * 40, by + 3];
    const reach = 300 + r() * 40 - pair * 10;
    const rise = 24 + r() * 26;
    const tip: Point = [Math.max(80, Math.min(SPINE_W - 80, base[0] + side * reach)), Math.max(70, by - rise)];
    const nerve: Curve = [base, [base[0] + side * reach * 0.3, base[1] + 18], [base[0] + side * reach * 0.68, tip[1] + 30 + r() * 12], tip];
    stroke(nerve, 9, 3, r, px, 0.22);
    tuft(nerve, 0.72, 1, 70, 11, r, px);                                  // terminacoes do nervo (mesmo tufo da arvore)
    const own = agent.own.slice(0, MAX_LEAVES);
    const notes: SpineNote[] = own.map((rel, j) => {
      const u = 0.25 + (0.7 * (j + 0.5)) / Math.max(own.length, 1);
      const p = at(nerve, u);
      const up = j % 2 === 0 ? -1 : 1;
      const len = 15 + r() * 16;
      const leaf: Point = [p[0] + side * (5 + r() * 9), p[1] + up * len];
      const twig: Curve = [p, [p[0] + side * 3, p[1] + up * len * 0.4], [leaf[0], leaf[1] - up * 4], leaf];
      stroke(twig, 3, 2, r, px, 0.55);
      return { rel, agent: agent.id, x: Math.round(leaf[0]), y: Math.round(leaf[1]) };
    });
    const flow = `M${STEM[0]} ${STEM[1]}L${r1(bx)} ${r1(by)}L${r1(base[0])} ${r1(base[1])}` + d(nerve).replace(/^M[^C]+/, "");
    return { id: agent.id, side, level: Math.round(by), base, tip, flow, pixels: px.layers, notes, hidden: agent.own.length - own.length };
  });

  // Cerebro do Maestro e as notas dele num arco por cima
  const headOwn = (head?.own ?? []).slice(0, 16);
  const brainNotes: SpineNote[] = headOwn.map((rel, k) => {
    const a = Math.PI * (1.08 + (0.84 * (k + 0.5)) / Math.max(headOwn.length, 1));
    return { rel, agent: head!.id, x: Math.round(BRAIN[0] + Math.cos(a) * (BRAIN_RX + 20)), y: Math.round(BRAIN[1] + 8 + Math.sin(a) * (BRAIN_RY + 16)) };
  });

  // Frutos: notas que mais de um agente usa (ou guarda), entre a medula e os nervos dos donos
  const owners = new Map<string, Set<string>>();
  for (const a of input) for (const rel of new Set([...a.own, ...a.uses])) {
    if (!rel) continue;
    (owners.get(rel) ?? owners.set(rel, new Set()).get(rel)!).add(a.id);
  }
  const tipOf = new Map(nerves.map((n) => [n.id, n.tip]));
  const common = [...owners.entries()].filter(([, s]) => s.size > 1)
    .sort((a, b) => b[1].size - a[1].size || a[0].localeCompare(b[0])).slice(0, 18);
  const shared: SpineShared[] = common.map(([rel, set], k) => {
    const pts = [...set].map((id) => tipOf.get(id) ?? [BRAIN[0], BRAIN[1] + BRAIN_RY] as Point);
    const mx = pts.reduce((s, p) => s + p[0], 0) / pts.length, my = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    const rr = random(seedOf(rel));
    const x = CX + (mx - CX) * 0.34 + (rr() - 0.5) * 60;
    const y = Math.min(SPINE_H - 60, Math.max(STEM[1] + 20, my + 20 + (k % 3) * 12 + (rr() - 0.5) * 18));
    return { rel, x: Math.round(x), y: Math.round(y), owners: [...set].sort() };
  });

  return {
    cord: { pixels: cordPx.layers, flow: d(cord), root: ROOT, stem: STEM },
    bones: bonesPx.layers,
    brain: { pixels: brainPixels().layers, center: BRAIN, agent: head?.id, notes: brainNotes },
    nerves, shared,
  };
}

/** Notas fora da pasta de cada agente que as notas dele citam (pelas arestas do grafo do Cerebro). */
export function usesFromGraph(folders: Record<string, string>, edges: Array<{ from: string; to: string }>, own: Record<string, string[]>) {
  const inside = (rel: string, folder: string) => rel === folder || rel.startsWith(folder + "/");
  const out: Record<string, string[]> = {};
  for (const [id, folder] of Object.entries(folders)) {
    const mine = new Set(own[id] ?? []);
    out[id] = [...new Set(edges.filter((e) => mine.has(e.from) && !inside(e.to, folder)).map((e) => e.to))].sort();
  }
  return out;
}
