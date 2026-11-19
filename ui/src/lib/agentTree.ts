// Memoria dos agentes como UMA arvore vista de longe (mesmo traco em pixels da arvore do Cerebro).
//
// Leitura do desenho = fluxo de um pedido:
//   raiz (embaixo)  -> o pedido entra (voz ou texto)
//   tronco          -> sobe ate a copa, onde fica o Maestro (divide e delega)
//   galhos          -> um por agente; as folhas sao as notas da pasta dele no Cerebro
//   frutos (copa)   -> notas que mais de um agente usa (ligacoes [[...]] das notas dos agentes): memoria comum
//
// Deterministico (sementes pelo nome) e puro: testado em agentTree.test.ts.

import { at, Pixels, random, seedOf, stroke, tuft, type Curve, type Point } from "./branchLayout";

export const TREE_W = 1000;
export const TREE_H = 600;

export interface TreeAgentInput {
  id: string;
  /** notas da pasta do agente (rel) */
  own: string[];
  /** notas fora da pasta que as notas do agente citam (rel) */
  uses: string[];
}

export interface TreeLeaf { rel: string; x: number; y: number; agent: string }
export interface TreeFruit { rel: string; x: number; y: number; owners: string[] }
export interface TreeBranch {
  id: string;
  /** de onde sai do tronco e a ponta (onde fica o nome do agente) */
  base: Point;
  tip: Point;
  /** caminho da delegacao Maestro -> agente (para o pulso do fluxo) */
  flow: string;
  pixels: string[];
  leaves: TreeLeaf[];
  side: -1 | 1;
}
export interface AgentTree {
  trunk: { pixels: string[]; flow: string; root: Point; crown: Point };
  /** o agente que fica na copa (Maestro), se vier na entrada, e as notas dele (folhas em arco sobre a copa) */
  crown?: string;
  crownLeaves: TreeLeaf[];
  branches: TreeBranch[];
  fruits: TreeFruit[];
}

const ROOT: Point = [TREE_W / 2, TREE_H - 18];
const CROWN: Point = [TREE_W / 2, 112];
const MAX_LEAVES = 14;

const d = (c: Curve) => `M${c[0][0]} ${c[0][1]}C${c[1][0]} ${c[1][1]} ${c[2][0]} ${c[2][1]} ${c[3][0]} ${c[3][1]}`;

/** Monta a arvore. O primeiro agente com id "MAESTRO" vai para a copa; os outros viram galhos alternando os lados. */
export function layoutAgentTree(input: TreeAgentInput[]): AgentTree {
  const trunkPx = new Pixels();
  const rnd = random(seedOf("tronco"));
  const trunk: Curve = [ROOT, [ROOT[0] - 26, ROOT[1] - 150], [CROWN[0] + 30, CROWN[1] + 190], CROWN];
  stroke(trunk, 26, 10, rnd, trunkPx, 0.12);
  // raizes curtas espalhadas no chao
  for (const dx of [-120, -64, 58, 126]) {
    const root: Curve = [[ROOT[0] + dx * 0.15, ROOT[1] - 6], [ROOT[0] + dx * 0.5, ROOT[1] - 2], [ROOT[0] + dx * 0.8, ROOT[1] + 4], [ROOT[0] + dx, ROOT[1] + 6]];
    stroke(root, 8, 2, rnd, trunkPx, 0.05);
  }
  tuft(trunk, 0.82, 1, 260, 26, rnd, trunkPx);

  const crown = input.find((a) => a.id === "MAESTRO")?.id;
  const crownOwn = (input.find((a) => a.id === crown)?.own ?? []).slice(0, MAX_LEAVES);
  const crownLeaves: TreeLeaf[] = crownOwn.map((rel, k) => {
    const a = Math.PI * (1.12 + (0.76 * (k + 0.5)) / Math.max(crownOwn.length, 1));
    return { rel, x: Math.round(CROWN[0] + Math.cos(a) * 92), y: Math.round(CROWN[1] + 18 + Math.sin(a) * 62), agent: crown! };
  });
  const others = input.filter((a) => a.id !== crown);
  const n = others.length;
  const branches: TreeBranch[] = others.map((agent, i) => {
    const px = new Pixels();
    const r = random(seedOf(agent.id));
    const side: -1 | 1 = i % 2 === 0 ? -1 : 1;
    // altura no tronco: os primeiros mais baixos, subindo; dois por altura (um de cada lado)
    const level = Math.floor(i / 2), levels = Math.max(1, Math.ceil(n / 2));
    const t = 0.3 + (0.5 * (level + 0.5)) / levels;
    const base = at(trunk, t);
    const reach = 300 + r() * 50 - level * 14;
    const rise = 70 + level * 28 + r() * 24;
    const tip: Point = [clampX(base[0] + side * reach), Math.max(70, base[1] - rise)];
    const limb: Curve = [base, [base[0] + side * reach * 0.32, base[1] - rise * 0.05 - 10],
      [base[0] + side * reach * 0.7, tip[1] + 34 + r() * 16], tip];
    stroke(limb, 12, 4, r, px, 0.3);
    tuft(limb, 0.55, 1, 120, 14, r, px);
    // Folhas: uma por nota, em raminhos curtos ao longo do galho
    const own = agent.own.slice(0, MAX_LEAVES);
    const leaves: TreeLeaf[] = own.map((rel, k) => {
      const u = 0.28 + (0.68 * (k + 0.5)) / Math.max(own.length, 1);
      const p = at(limb, u);
      const up = k % 2 === 0 ? -1 : 1;
      const len = 16 + r() * 18;
      const leaf: Point = [p[0] + side * (6 + r() * 10), p[1] + up * len];
      const twig: Curve = [p, [p[0] + side * 3, p[1] + up * len * 0.4], [leaf[0], leaf[1] - up * 4], leaf];
      stroke(twig, 3, 2, r, px, 0.6);
      return { rel, x: leaf[0], y: leaf[1], agent: agent.id };
    });
    // Delegacao: do Maestro (copa) ate a ponta do galho, por fora da copa
    const flow: Curve = [CROWN, [CROWN[0] + side * 120, CROWN[1] - 40], [tip[0] - side * 40, tip[1] - 90], tip];
    return { id: agent.id, base, tip, flow: d(flow), pixels: px.layers, leaves, side };
  });

  // Frutos: notas que mais de um agente cita (inclui o Maestro). Ficam na copa, entre os galhos dos donos.
  const owners = new Map<string, Set<string>>();
  for (const a of input) for (const rel of new Set(a.uses)) {
    if (!rel) continue;
    (owners.get(rel) ?? owners.set(rel, new Set()).get(rel)!).add(a.id);
  }
  const tipOf = new Map(branches.map((b) => [b.id, b.tip]));
  const shared = [...owners.entries()].filter(([, s]) => s.size > 1)
    .sort((a, b) => b[1].size - a[1].size || a[0].localeCompare(b[0])).slice(0, 18);
  const fruits: TreeFruit[] = shared.map(([rel, set], k) => {
    const pts = [...set].map((id) => tipOf.get(id) ?? CROWN);
    const mx = pts.reduce((s, p) => s + p[0], 0) / pts.length, my = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    const r = random(seedOf(rel));
    // puxado para a copa (centro), com um pequeno espalhamento para nao empilhar
    const x = CROWN[0] + (mx - CROWN[0]) * 0.42 + (r() - 0.5) * 70;
    const y = CROWN[1] + 60 + (my - CROWN[1]) * 0.35 + (k % 3) * 14 + (r() - 0.5) * 20;
    return { rel, x: Math.round(x), y: Math.round(y), owners: [...set].sort() };
  });

  return { trunk: { pixels: trunkPx.layers, flow: d(trunk), root: ROOT, crown: CROWN }, crown, crownLeaves, branches, fruits };
}

function clampX(x: number) {
  return Math.max(90, Math.min(TREE_W - 90, x));
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
