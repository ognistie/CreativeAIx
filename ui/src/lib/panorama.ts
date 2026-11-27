// Panorama 3D do harness: layout da cena, camera em perspectiva e o que acende ao vivo. Puro e deterministico
// (testado em panorama.test.ts); o desenho em canvas fica em views/lab/HarnessPanorama.tsx.
//
// Regioes funcionais no alto, distribuicao pela medula e agentes nas ramificacoes.
// Feixes e dendritos correspondem a conexoes do codigo; apenas traceLit acende eventos observados.
// Notas e memoria comum preservam os caminhos do Cerebro; planos e hipoteses vem dos registros existentes.

export type Vec3 = readonly [number, number, number];
export type NodeKind = "core" | "agent" | "note" | "shared" | "stage" | "plan" | "hypothesis" | "tool" | "model";
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
export interface PanoramaInput { agents: PanoramaAgent[]; routing?: RoutingData | null; evolution?: EvolutionData | null; events?: import("./cognitive").CognitiveEvent[] }

const CORE = "MAESTRO";
const AGENT_Y = 120;
const NOTE_SHELL = 60;
const MAX_NOTES = 28;
const MAX_SHARED = 22;
const ROUTE_Y = -130;
const EVO_Y = 350;
export const FLOOR_Y = -460;

/** Estagios do roteamento: id, rotulo e posicao (frente da cena = z positivo, onde a camera comeca). */
export const STAGES: Array<{ id: string; label: string; pos: Vec3; hint: string }> = [
  { id: "pedido", label: "Estímulo", pos: [0, -420, 80], hint: "Texto ou voz; desktop/controller.py" },
  { id: "entendimento", label: "Entendimento", pos: [-120, 220, 50], hint: "Resolve a conversa: continuação, pergunta, pedido novo · core/followup.py" },
  { id: "resposta", label: "Resposta direta", pos: [-230, 205, 55], hint: "Respondido sem plano (papo, tela, andamento)" },
  { id: "atalho", label: "Atalho sem IA", pos: [-85, 15, 85], hint: "Abrir app, pasta ou pesquisa citada: zero modelo" },
  { id: "aprendido", label: "Plano aprendido", pos: [-80, 55, -90], hint: "Molde que já deu certo: executa sem chamar o Maestro" },
  { id: "continuar", label: "Continuar", pos: [55, -15, -70], hint: "Age no que já está aberto" },
  { id: "conversa", label: "Conversa", pos: [215, 140, -10], hint: "Responde com leitura de arquivos e busca; ação vai ao Maestro" },
  { id: "politicas", label: "Decisão · políticas", pos: [100, 140, 75], hint: "Validação e confirmação de efeitos · core/plan_validator.py · desktop/controller_gates.py" },
];
export const REGIONS: Array<{ id: string; label: string; pos: Vec3; color: string; detail: string }> = [
  { id: "perception", label: "Percepção · Vision", pos: [-315, 220, -90], color: "#86adb8", detail: "Leitura da tela e localização visual · core/vision.py · core/screen_question.py. Vision observa; o executor realiza o clique." },
  { id: "memory", label: "Hipocampo · memória", pos: [-140, 110, -85], color: "#d48da7", detail: "Recuperação e associação · core/brain.py · core/context_engine.py. Analogia funcional, sem equivalência biológica." },
  { id: "context", label: "Contexto", pos: [130, 270, -60], color: "#79a9ba", detail: "Seleção de referências e contexto da sessão. O contador indica caracteres selecionados, não tokens." },
  { id: "spine", label: "Medula · distribuição", pos: [0, -70, 0], color: "#8e9cb4", detail: "Comunicação e despacho · TaskSchedule / StepRuntime / Controller" },
  { id: "verify", label: "Validação", pos: [120, -320, 20], color: "#80b4a1", detail: "Conferência independente · core/verification.py. Operação concluída não significa resultado verificado." },
  { id: "learning", label: "Plasticidade · RSI", pos: [-70, 355, -45], color: "#d9b776", detail: "Planos aprendidos e memória científica · core/learned_plans.py · core/rsi.py. Promoção humana continua obrigatória no Lab." },
  { id: "model", label: "Interface de modelos", pos: [300, 230, -110], color: "#a095b8", detail: "Chamadas por core/ai_client.py. A cena só indica uma chamada quando ela é observada." },
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
  const corePos: Vec3 = [0, AGENT_Y + 100, 0];
  nodes.push({ id: CORE, kind: "core", pos: corePos, r: 30, color: core?.color ?? "#8b5cf6", label: core?.name ?? "Maestro",
    agent: CORE, detail: "Planeja e delega. Recebe o que nenhum atalho resolveu.", weight: 1 });

  // Agentes distribuidos ao longo da medula, em ramificacoes bilaterais.
  const agentPos = new Map<string, Vec3>([[CORE, corePos]]);
  ring.forEach((a, i) => {
    const side = i % 2 === 0 ? -1 : 1;
    const pos: Vec3 = [side * (235 + (i % 3) * 25), 25 - Math.floor(i / 2) * 125, Math.sin(i * 1.7) * 95];
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
      edges.push({ id: `e:${id}`, a: id, b: a.id, kind: "own", weight: 0.3, lift: 12 });
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
  R(CORE, "stage:politicas", routeWeight("maestro"), 40);
  for (const region of REGIONS) nodes.push({ ...region, id: `region:${region.id}`, kind: "stage", r: 14 });
  for (const [a, b] of [["stage:entendimento", "region:memory"], ["region:memory", "region:context"],
    ["region:context", CORE], ["stage:politicas", "region:spine"], ["region:spine", "region:verify"],
    ["region:verify", "region:learning"], ["region:learning", "region:memory"], [CORE, "region:model"]]) R(a!, b!, 0, 30);
  // Politicas -> agentes: trafego por agente
  for (const a of ring) {
    const t = traffic.get(a.id);
    edges.push({ id: `traffic:${a.id}`, a: "region:spine", b: a.id, kind: "traffic", weight: (t?.runs ?? 0) / maxAgentRuns, lift: 55 });
    edges.push({ id: `verify:${a.id}`, a: a.id, b: "region:verify", kind: "evolve", weight: 0, lift: -30 });
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

  // Periferia criada somente a partir de chamadas observadas, nunca de capacidades presumidas.
  const calls = new Map<string, import("./cognitive").CognitiveEvent>();
  for (const e of input.events ?? []) if (e.action && (e.stage === "model" || e.stage === "execution")) {
    calls.set(`${e.stage}:${e.agent}:${e.action}`, e);
  }
  [...calls.entries()].slice(-24).forEach(([key, e], i) => {
    const parent = agentPos.has(e.agent) ? e.agent : e.agent === "CHAT" ? "stage:conversa"
      : ["VISION", "ASSIST", "READER"].includes(e.agent) ? "region:perception" : "region:model";
    const pos = nodes.find((n) => n.id === parent)!.pos;
    const id = `call:${key}`;
    nodes.push({ id, kind: e.stage === "model" ? "model" : "tool", agent: e.agent, label: e.action,
      pos: [pos[0] + (pos[0] < 0 ? -1 : 1) * 170, pos[1] + (i % 3 - 1) * 35, pos[2] - 70 - (i % 2) * 40],
      r: 8, color: e.stage === "model" ? "#a095b8" : "#83b6a5", detail: `Chamada observada · ${e.status} · ${e.ms} ms. Sem conteúdo ou credenciais.` });
    edges.push({ id: `e:${id}`, a: parent, b: id, kind: "own", lift: 30, weight: 0 });
  });

  return { nodes, edges, byId: new Map(nodes.map((n) => [n.id, n])), floorY: FLOOR_Y };
}

// ── camera ──────────────────────────────────────────────────────────────────
export interface Camera { yaw: number; pitch: number; dist: number; target: Vec3; fov: number }
export interface Projected { x: number; y: number; depth: number; k: number; visible: boolean }
export const NEAR = 40;

export const VIEWS: Record<"geral" | "rotas" | "contexto" | "memoria" | "evolucao", Camera> = {
  geral: { yaw: 0.22, pitch: 0.12, dist: 900, target: [0, -15, 0], fov: 0.95 },
  rotas: { yaw: 0.05, pitch: 0.6, dist: 700, target: [0, ROUTE_Y + 30, 170], fov: 0.95 },
  contexto: { yaw: -0.3, pitch: 0.12, dist: 540, target: [0, 205, -10], fov: 0.95 },
  memoria: { yaw: 0.6, pitch: 0.24, dist: 700, target: [0, AGENT_Y + 30, 0], fov: 0.95 },
  evolucao: { yaw: 0.2, pitch: -0.1, dist: 600, target: [0, EVO_Y - 20, 0], fov: 0.95 },
};

export function clampCamera(c: Camera): Camera {
  return { ...c, pitch: Math.max(-1.5, Math.min(1.5, c.pitch)), dist: Math.max(85, Math.min(2400, c.dist)) };
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
export function markerRadius(node: SceneNode, scale: number): number {
  return Math.max(node.kind === "note" || node.kind === "shared" ? 5 : 3, node.r * scale);
}

export function pick(nodes: SceneNode[], c: Camera, w: number, h: number, px: number, py: number, slack = 6): SceneNode | null {
  let best: SceneNode | null = null;
  let bestDepth = Infinity;
  let bestDistance = Infinity;
  for (const n of nodes) {
    const p = project(n.pos, c, w, h);
    if (!p.visible) continue;
    const rr = markerRadius(n, p.k) + slack;
    const distance = (p.x - px) ** 2 + (p.y - py) ** 2;
    if (distance <= rr * rr && (distance < bestDistance || (distance === bestDistance && p.depth < bestDepth))) {
      best = n;
      bestDepth = p.depth;
      bestDistance = distance;
    }
  }
  return best;
}

// ── ao vivo ─────────────────────────────────────────────────────────────────
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

/** Apenas os sinais explicitamente observados acendem o observatorio. Sem dados, a cena fica quieta. */
export function traceLit(events: import("./cognitive").CognitiveEvent[], scene: Scene): LiveLit {
  const event = events.at(-1);
  const nodes = new Set<string>(), working = new Set<string>(), path: string[] = [];
  if (!event) return { nodes, working, path, outcome: "" };
  const stages: Record<string, string> = { stimulus: "stage:pedido", understanding: "stage:entendimento",
    memory: "region:memory", context: "region:context", planning: CORE, decision: "stage:politicas",
    transmission: "region:spine", execution: event.agent, verification: "region:verify",
    learning: "region:learning", recovery: CORE, model: "region:model" };
  const id = stages[event.stage] || CORE;
  nodes.add(id);
  if (event.agent && scene.byId.has(event.agent)) nodes.add(event.agent);
  if (event.status === "started") working.add(id);
  const callId = `call:${event.stage}:${event.agent}:${event.action}`;
  if (scene.byId.has(callId)) {
    nodes.add(callId); path.push(`e:${callId}`);
    const connection = scene.edges.find((e) => e.id === `e:${callId}`);
    if (connection) nodes.add(connection.a);
  }
  const pairs: Record<string, [string, string]> = { memory: ["region:memory", "region:context"],
    context: ["region:context", CORE], execution: ["region:spine", event.agent],
    verification: [event.agent, "region:verify"], learning: ["region:verify", "region:learning"],
    model: [event.agent || CORE, "region:model"], transmission: ["stage:politicas", "region:spine"] };
  const pair = pairs[event.stage];
  if (pair && !(event.stage === "memory" && event.count === 0)) {
    for (const edge of scene.edges) if (edge.a === pair[0] && edge.b === pair[1]) path.push(edge.id);
  }
  if (event.stage === "memory" && event.count > 0) {
    for (const ref of event.refs) {
      const matches = scene.nodes.filter((n) => n.rel && (n.rel === ref || noteName(n.rel) === ref) && (!event.agent || n.agent === event.agent));
      // Titulos ambiguos nao sao prova de qual nota foi recuperada.
      if (matches.length === 1) {
        const note = matches[0]!;
        nodes.add(note.id);
        for (const edge of scene.edges) if (edge.a === note.id && edge.b === event.agent) path.push(edge.id);
      }
    }
  }
  const outcome = event.status === "verified" ? "ok" : ["failed", "blocked", "uncertain"].includes(event.status) ? "fail" : "";
  return { nodes, working, path, outcome };
}
