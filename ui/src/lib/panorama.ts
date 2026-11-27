// Panorama 3D do harness: layout da cena, camera em perspectiva e o que acende ao vivo. Puro e deterministico
// (testado em panorama.test.ts); o desenho em canvas fica em views/lab/HarnessPanorama.tsx.
//
// A cena, de baixo para cima (y para cima, unidades do mundo):
//   chao        grade em perspectiva e as sombras dos nos (profundidade real)
//   roteamento  o caminho de um pedido: Pedido -> Entendimento -> resposta direta | atalho sem IA | plano aprendido |
//               continuar | Conversa | Maestro -> Politicas -> agentes. A espessura de cada trilha e o trafego real
//               (historico); ao vivo, a trilha do pedido atual acende e pulsos correm por ela
//   memoria     o Maestro no centro, os agentes em orbita, as notas de cada agente numa nuvem em volta dele e a
//               memoria comum (notas usadas por mais de um agente) entre o centro e os donos
//   evolucao    o auto-aperfeicoamento por cima: planos aprendidos (candidato, promovido, bloqueado) e as hipoteses do
//               Lab, ligados aos agentes que mudam

export type Vec3 = readonly [number, number, number];
export type NodeKind = "core" | "agent" | "note" | "shared" | "stage" | "plan" | "hypothesis";
export type EdgeKind = "own" | "shared" | "route" | "traffic" | "evolve";

export interface SceneNode {
  id: string;
  kind: NodeKind;
  pos: Vec3;
  r: number;
  color: string;
  label?: string;
  /** agente dono (notas, agentes) ou ligado (planos, hipoteses) */
  agent?: string;
  /** texto do cartao ao passar o mouse */
  detail?: string;
  /** nota do Cerebro (abre no painel ao lado) */
  rel?: string;
  /** 0..1: quanto o no "pesa" (trafego, sucessos) */
  weight?: number;
  /** estado (planos: candidate | promoted | blocked; hipoteses: resultado) */
  status?: string;
  /** rotulo acima do no (etapas vizinhas alternam, para os nomes nao se sobreporem) */
  labelAbove?: boolean;
}
export interface SceneEdge { id: string; a: string; b: string; kind: EdgeKind; weight: number; lift: number }
export interface Scene { nodes: SceneNode[]; edges: SceneEdge[]; byId: Map<string, SceneNode>; floorY: number }

export interface PanoramaAgent { id: string; name: string; color: string; own: string[]; uses: string[] }
export interface RoutingData {
  total: number;
  routes: Array<{ route: string; runs: number; ok: number; avg_ms: number }>;
  agents: Array<{ agent: string; runs: number; ok: number }>;
  edges: Array<{ from: string; to: string; runs: number }>;
  recent?: Array<{ route: string; ok: boolean; agents: string[]; when: string; ms: number }>;
}
export interface EvolutionData {
  plans: Array<{ key: string; template: string; status: string; successes: number; failures: number; streak: number; replays: number; agents: string[] }>;
  hypotheses: Array<{ id: string; agent: string; objective: string; result: string; origin?: string; when?: string }>;
  summary: { promoted: number; candidate: number; blocked: number; hypotheses: number };
}
export interface PanoramaInput { agents: PanoramaAgent[]; routing?: RoutingData | null; evolution?: EvolutionData | null }

const CORE = "MAESTRO";
const AGENT_RING = 270;
const AGENT_Y = 40;
const NOTE_SHELL = 60;
const MAX_NOTES = 28;
const MAX_SHARED = 22;
const ROUTE_Y = -130;
const EVO_Y = 245;
export const FLOOR_Y = -215;

/** Estagios do roteamento: id, rotulo e posicao (frente da cena = z positivo, onde a camera comeca). */
export const STAGES: Array<{ id: string; label: string; pos: Vec3; hint: string }> = [
  { id: "pedido", label: "Pedido", pos: [0, ROUTE_Y - 20, 400], hint: "Texto ou voz entra aqui" },
  { id: "entendimento", label: "Entendimento", pos: [0, ROUTE_Y - 10, 300], hint: "Resolve a conversa: continuação, pergunta, pedido novo" },
  { id: "resposta", label: "Resposta direta", pos: [-370, ROUTE_Y, 235], hint: "Respondido sem plano (papo, tela, andamento)" },
  { id: "atalho", label: "Atalho sem IA", pos: [-230, ROUTE_Y, 205], hint: "Abrir app, pasta ou pesquisa citada: zero modelo" },
  { id: "aprendido", label: "Plano aprendido", pos: [-95, ROUTE_Y, 190], hint: "Molde que já deu certo: executa sem chamar o Maestro" },
  { id: "continuar", label: "Continuar", pos: [40, ROUTE_Y, 190], hint: "Age no que já está aberto" },
  { id: "conversa", label: "Conversa", pos: [185, ROUTE_Y, 210], hint: "Responde com leitura de arquivos e busca; ação vai ao Maestro" },
  { id: "politicas", label: "Políticas", pos: [0, ROUTE_Y + 30, 40], hint: "Validação do plano e dos passos em código, confirmação de efeitos" },
];
const ROUTE_STAGE: Record<string, string> = {
  resposta: "resposta", atalho: "atalho", aprendido: "aprendido", continuar: "continuar", conversa: "conversa", maestro: CORE,
};

// ── aleatorio deterministico ────────────────────────────────────────────────
function seedOf(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}
function rand(seed: number) {
  let s = seed || 1;
  return () => ((s = Math.imul(s ^ (s >>> 15), 1 | s) + 0x6d2b79f5) >>> 0) / 4294967296;
}
const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const scale = (a: Vec3, k: number): Vec3 => [a[0] * k, a[1] * k, a[2] * k];

/** Pontos bem espalhados numa esfera (espiral de Fibonacci). */
export function fibonacciSphere(n: number, radius: number): Vec3[] {
  const out: Vec3[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = n === 1 ? 0 : 1 - (i / (n - 1)) * 2;
    const rr = Math.sqrt(1 - y * y);
    const t = golden * i;
    out.push([Math.cos(t) * rr * radius, y * radius, Math.sin(t) * rr * radius]);
  }
  return out;
}

export const noteName = (rel: string) => rel.split("/").pop()!.replace(/\.md$/i, "");
const PLAN_COLOR: Record<string, string> = { promoted: "#f5b43c", candidate: "#5aa7ff", blocked: "#e05a5a" };
function hypothesisColor(result: string): string {
  const r = result.toLowerCase();
  if (r.includes("promov")) return "#f5b43c";
  if (r.includes("aguard")) return "#5aa7ff";
  if (r.includes("refut") || r.includes("rejeit") || r.includes("recus")) return "#e05a5a";
  return "#9aa3b2";
}

/** Monta a cena inteira a partir da memoria dos agentes, do trafego de rotas e da evolucao. */
export function layoutPanorama(input: PanoramaInput): Scene {
  const nodes: SceneNode[] = [];
  const edges: SceneEdge[] = [];
  const agents = input.agents;
  const core = agents.find((a) => a.id === CORE);
  const ring = agents.filter((a) => a.id !== CORE);
  const traffic = new Map((input.routing?.agents ?? []).map((a) => [a.agent, a]));
  const maxAgentRuns = Math.max(1, ...[...traffic.values()].map((a) => a.runs));

  // Maestro no centro
  const corePos: Vec3 = [0, AGENT_Y + 20, 0];
  nodes.push({ id: CORE, kind: "core", pos: corePos, r: 30, color: core?.color ?? "#8b5cf6", label: core?.name ?? "Maestro",
    agent: CORE, detail: "Planeja e delega. Recebe o que nenhum atalho resolveu.", weight: 1 });

  // Agentes em orbita (leve ondulacao para nao parecer um prato)
  const agentPos = new Map<string, Vec3>([[CORE, corePos]]);
  ring.forEach((a, i) => {
    const ang = -Math.PI / 2 + (i / Math.max(ring.length, 1)) * Math.PI * 2 + 0.35;
    const pos: Vec3 = [Math.cos(ang) * AGENT_RING, AGENT_Y + Math.sin(i * 1.7) * 26, Math.sin(ang) * AGENT_RING];
    agentPos.set(a.id, pos);
    const t = traffic.get(a.id);
    nodes.push({ id: a.id, kind: "agent", pos, r: 19 + 7 * ((t?.runs ?? 0) / maxAgentRuns), color: a.color, label: a.name,
      agent: a.id, weight: (t?.runs ?? 0) / maxAgentRuns,
      detail: `${a.own.length} ${a.own.length === 1 ? "nota" : "notas"} · usa ${a.uses.length}` +
        (t ? ` · ${t.runs} ${t.runs === 1 ? "execução" : "execuções"}, ${Math.round((t.ok / t.runs) * 100)}% ok` : "") });
  });

  // Notas de cada agente: nuvem em volta dele (o Maestro tem a dele em volta do centro)
  for (const a of agents) {
    const center = agentPos.get(a.id)!;
    const own = a.own.slice(0, MAX_NOTES);
    const shell = fibonacciSphere(own.length, (a.id === CORE ? NOTE_SHELL + 22 : NOTE_SHELL));
    const r = rand(seedOf(a.id));
    own.forEach((rel, k) => {
      const wob = 1 + (r() - 0.5) * 0.28;
      const id = `note:${a.id}:${rel}`;
      nodes.push({ id, kind: "note", pos: add(center, scale(shell[k]!, wob)), r: 5.6, color: a.color, agent: a.id, rel,
        label: noteName(rel), detail: `Nota de ${a.name}` });
      if (k % 2 === 0) edges.push({ id: `e:${id}`, a: a.id, b: id, kind: "own", weight: 0.3, lift: 0 });
    });
  }

  // Memoria comum: notas que mais de um agente usa, entre o centro e os donos, um pouco acima do plano
  const owners = new Map<string, Set<string>>();
  for (const a of agents) for (const rel of new Set([...a.own, ...a.uses])) {
    if (rel) (owners.get(rel) ?? owners.set(rel, new Set()).get(rel)!).add(a.id);
  }
  const common = [...owners.entries()].filter(([, s]) => s.size > 1)
    .sort((x, y) => y[1].size - x[1].size || x[0].localeCompare(y[0])).slice(0, MAX_SHARED);
  for (const [rel, set] of common) {
    const pts = [...set].map((id) => agentPos.get(id) ?? corePos);
    const mid = scale(pts.reduce((s, p) => add(s, p), [0, 0, 0] as Vec3), 1 / pts.length);
    const r = rand(seedOf(rel));
    const pos: Vec3 = [mid[0] * 0.48 + (r() - 0.5) * 40, AGENT_Y + 70 + r() * 40, mid[2] * 0.48 + (r() - 0.5) * 40];
    const id = `shared:${rel}`;
    const list = [...set].sort();
    nodes.push({ id, kind: "shared", pos, r: 6.5 + set.size, color: "#e88aa6", rel, agent: list[0], label: noteName(rel),
      detail: `Memória comum · usada por ${list.map((o) => agents.find((a) => a.id === o)?.name ?? o).join(", ")}`,
      weight: set.size / agents.length });
    for (const o of list) edges.push({ id: `e:${id}:${o}`, a: id, b: o, kind: "shared", weight: 0.35, lift: 18 });
  }

  // Roteamento: estagios, trilhas e trafego real
  const routes = new Map((input.routing?.routes ?? []).map((r) => [r.route, r]));
  const total = Math.max(1, input.routing?.total ?? 0);
  for (const s of STAGES) {
    const routeKey = Object.keys(ROUTE_STAGE).find((k) => ROUTE_STAGE[k] === s.id);
    const stat = routeKey ? routes.get(routeKey) : undefined;
    nodes.push({ id: `stage:${s.id}`, kind: "stage", pos: s.pos, r: s.id === "pedido" ? 12 : 10, color: "#7d8aa5", label: s.label,
      labelAbove: s.id === "atalho" || s.id === "continuar",
      weight: stat ? stat.runs / total : s.id === "pedido" || s.id === "entendimento" || s.id === "politicas" ? 1 : 0,
      detail: s.hint + (stat ? ` · ${stat.runs} ${stat.runs === 1 ? "pedido" : "pedidos"} (${Math.round((stat.runs / total) * 100)}%), ` +
        `${Math.round((stat.ok / stat.runs) * 100)}% ok${stat.avg_ms ? `, ${(stat.avg_ms / 1000).toFixed(1)} s em média` : ""}` : "") });
  }
  const routeWeight = (key: string) => (routes.get(key)?.runs ?? 0) / total;
  const R = (a: string, b: string, weight: number, lift = 30) =>
    edges.push({ id: `route:${a}>${b}`, a, b, kind: "route", weight, lift });
  R("stage:pedido", "stage:entendimento", 1, 8);
  for (const key of Object.keys(ROUTE_STAGE)) {
    const target = ROUTE_STAGE[key] === CORE ? CORE : `stage:${ROUTE_STAGE[key]}`;
    R("stage:entendimento", target, routeWeight(key), key === "maestro" ? 120 : 26);
  }
  const handed = (input.routing?.edges ?? []).find((e) => e.from === "conversa" && e.to === "maestro")?.runs ?? 0;
  R("stage:conversa", CORE, handed / total, 90);
  for (const s of ["atalho", "aprendido", "continuar"]) R(`stage:${s}`, "stage:politicas", routeWeight(s), 20);
  R(CORE, "stage:politicas", routeWeight("maestro") + handed / total, 40);
  // Politicas -> agentes: trafego por agente
  for (const a of ring) {
    const t = traffic.get(a.id);
    edges.push({ id: `traffic:${a.id}`, a: "stage:politicas", b: a.id, kind: "traffic", weight: (t?.runs ?? 0) / maxAgentRuns, lift: 70 });
  }

  // Evolucao: planos aprendidos num halo acima do Maestro, hipoteses do Lab num anel maior
  const plans = input.evolution?.plans ?? [];
  const maxSucc = Math.max(1, ...plans.map((p) => p.successes));
  plans.forEach((p, i) => {
    const ang = (i / Math.max(plans.length, 1)) * Math.PI * 2;
    const rad = 105 + (i % 2) * 22;
    const id = `plan:${p.key || i}`;
    const status = PLAN_COLOR[p.status] ? p.status : "candidate";
    nodes.push({ id, kind: "plan", pos: [Math.cos(ang) * rad, EVO_Y + (i % 3) * 14, Math.sin(ang) * rad], r: 6 + 6 * (p.successes / maxSucc),
      color: PLAN_COLOR[status]!, status, label: p.template, weight: p.successes / maxSucc,
      detail: `Plano aprendido · ${status === "promoted" ? "promovido: roda sem o Maestro" : status === "blocked" ? "bloqueado por falhas" : `candidato (${p.streak} seguidos)`}` +
        ` · ${p.successes} ok, ${p.failures} falhas${p.replays ? `, ${p.replays} replays` : ""}` });
    for (const ag of p.agents) if (agentPos.has(ag)) edges.push({ id: `evo:${id}:${ag}`, a: id, b: ag, kind: "evolve", weight: 0.4, lift: -40 });
  });
  const hyps = input.evolution?.hypotheses ?? [];
  hyps.forEach((h, i) => {
    const ang = (i / Math.max(hyps.length, 1)) * Math.PI * 2 + 0.4;
    const id = `hyp:${h.id || i}`;
    nodes.push({ id, kind: "hypothesis", pos: [Math.cos(ang) * 190, EVO_Y + 40, Math.sin(ang) * 190], r: 5, color: hypothesisColor(h.result),
      status: h.result, agent: h.agent, label: h.objective,
      detail: `Hipótese do Lab · ${h.result || "sem resultado"}${h.origin ? ` · ${h.origin}` : ""}${h.when ? ` · ${h.when.replace("T", " ")}` : ""}` });
    if (agentPos.has(h.agent)) edges.push({ id: `evo:${id}`, a: id, b: h.agent, kind: "evolve", weight: 0.25, lift: -30 });
  });

  return { nodes, edges, byId: new Map(nodes.map((n) => [n.id, n])), floorY: FLOOR_Y };
}

// ── camera ──────────────────────────────────────────────────────────────────
export interface Camera { yaw: number; pitch: number; dist: number; target: Vec3; fov: number }
export interface Projected { x: number; y: number; depth: number; k: number; visible: boolean }
export const NEAR = 40;

export const VIEWS: Record<"geral" | "rotas" | "memoria" | "evolucao", Camera> = {
  geral: { yaw: 0.25, pitch: 0.36, dist: 780, target: [0, -5, 70], fov: 0.95 },
  rotas: { yaw: 0.05, pitch: 0.6, dist: 700, target: [0, ROUTE_Y + 30, 170], fov: 0.95 },
  memoria: { yaw: 0.6, pitch: 0.24, dist: 700, target: [0, AGENT_Y + 30, 0], fov: 0.95 },
  evolucao: { yaw: 0.2, pitch: -0.1, dist: 600, target: [0, EVO_Y - 20, 0], fov: 0.95 },
};

export function clampCamera(c: Camera): Camera {
  return { ...c, pitch: Math.max(-0.7, Math.min(1.25, c.pitch)), dist: Math.max(320, Math.min(2200, c.dist)) };
}

/** Projeta um ponto do mundo na tela (perspectiva). k = pixels por unidade do mundo naquela profundidade. */
export function project(p: Vec3, c: Camera, w: number, h: number): Projected {
  const x0 = p[0] - c.target[0], y0 = p[1] - c.target[1], z0 = p[2] - c.target[2];
  const cy = Math.cos(c.yaw), sy = Math.sin(c.yaw);
  const x1 = x0 * cy - z0 * sy;
  const z1 = x0 * sy + z0 * cy;
  const cp = Math.cos(c.pitch), sp = Math.sin(c.pitch);
  const y2 = y0 * cp - z1 * sp;
  const z2 = y0 * sp + z1 * cp;
  const depth = c.dist - z2;                        // camera na frente (z positivo) olhando para o alvo
  const f = h / 2 / Math.tan(c.fov / 2);
  if (depth < NEAR) return { x: 0, y: 0, depth, k: 0, visible: false };
  const k = f / depth;
  return { x: w / 2 + x1 * k, y: h / 2 - y2 * k, depth, k, visible: true };
}

/** Curva 3D (bezier quadratica com o meio levantado) em pontos, para trilhas e ligacoes. */
export function curvePoints(a: Vec3, b: Vec3, lift: number, steps = 14): Vec3[] {
  const mid: Vec3 = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + lift, (a[2] + b[2]) / 2];
  const out: Vec3[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps, u = 1 - t;
    out.push([u * u * a[0] + 2 * u * t * mid[0] + t * t * b[0], u * u * a[1] + 2 * u * t * mid[1] + t * t * b[1],
      u * u * a[2] + 2 * u * t * mid[2] + t * t * b[2]]);
  }
  return out;
}

/** No mais proximo do ponteiro (o da frente ganha empates), ou null. */
export function pick(nodes: SceneNode[], c: Camera, w: number, h: number, px: number, py: number, slack = 6): SceneNode | null {
  let best: SceneNode | null = null;
  let bestDepth = Infinity;
  for (const n of nodes) {
    const p = project(n.pos, c, w, h);
    if (!p.visible) continue;
    const rr = Math.max(n.r * p.k, 4) + slack;
    if ((p.x - px) ** 2 + (p.y - py) ** 2 <= rr * rr && p.depth < bestDepth) {
      best = n;
      bestDepth = p.depth;
    }
  }
  return best;
}

// ── ao vivo ─────────────────────────────────────────────────────────────────
export interface LiveInput {
  busy: boolean;
  status: string;
  route: string;
  planAgents: string[];
  steps: Array<{ agent: string; state: string }>;
  review: boolean;
}
export interface LiveLit {
  /** nos acesos (estagios, agentes, Maestro) */
  nodes: Set<string>;
  /** trilhas acesas (ids de aresta), na ordem do caminho */
  path: string[];
  /** agentes trabalhando agora (pulsando) */
  working: Set<string>;
  /** resultado final para o flash: ok | fail | "" */
  outcome: "ok" | "fail" | "";
}

/** O que acende na cena para o pedido atual. */
export function liveLit(s: LiveInput, sceneEdges: SceneEdge[]): LiveLit {
  const nodes = new Set<string>();
  const path: string[] = [];
  const working = new Set<string>();
  const outcome: LiveLit["outcome"] = s.busy ? "" : s.status === "done" ? "ok" : s.status === "failed" ? "fail" : "";
  if (!s.busy && !outcome) return { nodes, path, working, outcome };
  const has = (id: string) => sceneEdges.some((e) => e.id === id);
  const hop = (a: string, b: string) => {
    nodes.add(a);
    nodes.add(b);
    const id = `route:${a}>${b}`;
    if (has(id)) path.push(id);
  };
  hop("stage:pedido", "stage:entendimento");
  const chatSteps = s.steps.some((x) => x.agent === "CHAT");
  const [first, then] = (s.route || (chatSteps ? "conversa" : "")).split("→");
  const stageOf = (r: string) => (ROUTE_STAGE[r] === CORE ? CORE : ROUTE_STAGE[r] ? `stage:${ROUTE_STAGE[r]}` : "");
  const entry = stageOf(first ?? "");
  if (entry) hop("stage:entendimento", entry);
  if (then) hop(entry, stageOf(then));
  const last = then ? stageOf(then) : entry;
  const acting = s.planAgents.filter((a) => a !== "CHAT");
  if (acting.length && last && last !== "stage:resposta" && last !== "stage:conversa") {
    hop(last, "stage:politicas");
    for (const a of acting) {
      nodes.add(a);
      if (has(`traffic:${a}`)) path.push(`traffic:${a}`);
    }
  }
  if (s.review) nodes.add("stage:politicas");
  for (const st of s.steps) if (st.state === "running" && st.agent && st.agent !== "CHAT") working.add(st.agent);
  if (chatSteps && s.busy) working.add("stage:conversa");
  return { nodes, path, working, outcome };
}
