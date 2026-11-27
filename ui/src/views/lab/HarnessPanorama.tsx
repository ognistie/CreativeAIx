import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon, Segmented, Skeleton } from "../../components/ui";
import { cn } from "../../lib/cn";
import { core, demoMode } from "../../lib/host";
import { useTask } from "../../lib/stores";
import { fmtDuration } from "../../lib/taskStore";
import {
  clampCamera, curvePoints, layoutPanorama, traceLit, pick, project, STAGES, VIEWS,
  type Camera, type EvolutionData, type LiveLit, type RoutingData, type Scene, type SceneNode, type Vec3,
} from "../../lib/panorama";
import { COGNITIVE_STAGES, STATUS_LABEL, animationTime, signalProgress, detailLevel, eventsAt, eventSource, type CognitiveRun } from "../../lib/cognitive";
import { useAgentKnowledge, type Knowledge } from "./knowledge";
import { AGENTS, AGENT_LOOK, call } from "./types";

// Panorama do harness em 3D (lib/panorama.ts): roteamento embaixo, memoria dos agentes no meio, evolucao (planos
// aprendidos e hipoteses do Lab) em cima. Arrastar gira, a roda aproxima, clique duplo volta a visao. Ao vivo, a rota do
// pedido atual acende e pulsos correm por ela ate o agente que esta trabalhando.

type View = keyof typeof VIEWS;
const VIEW_OPTIONS: Array<{ value: View; label: string }> = [
  { value: "geral", label: "Geral" }, { value: "rotas", label: "Atividade" }, { value: "contexto", label: "Contexto" },
  { value: "memoria", label: "Memória" }, { value: "evolucao", label: "Evolução" },
];
const ROUTE_LABEL: Record<string, string> = {
  resposta: "Resposta direta", atalho: "Atalho sem IA", aprendido: "Plano aprendido", continuar: "Continuar no aberto",
  conversa: "Conversa", maestro: "Maestro",
};
const KIND_LABEL: Record<SceneNode["kind"], string> = {
  core: "Cérebro do harness", agent: "Agente", note: "Nota", shared: "Memória comum", stage: "Etapa do roteamento",
  plan: "Plano aprendido", hypothesis: "Hipótese do Lab",
  tool: "Ferramenta observada", model: "Modelo observado",
};
export const routeLabel = (route: string) => route.split("→").map((r) => ROUTE_LABEL[r] ?? r).join(" → ");

interface Harness { routing: RoutingData; evolution: EvolutionData; runs: CognitiveRun[] }

/** Roteamento e evolucao do nucleo; recarrega quando um pedido termina (o historico e os planos mudaram). */
function useHarness(busy: boolean): { data: Harness | null; error: string } {
  const [error, setError] = useState("");
  const [data, setData] = useState<Harness | null>(null);
  const [version, setVersion] = useState(0);
  const was = useRef(busy);
  useEffect(() => {
    if (was.current && !busy) {
      const t = setTimeout(() => setVersion((v) => v + 1), 900);   // o historico e gravado logo depois do fim
      was.current = busy;
      return () => clearTimeout(t);
    }
    was.current = busy;
  }, [busy]);
  useEffect(() => {
    let active = true;
    void call(core().call("harnessPanorama")).then((r) => {
      if (!active) return;
      if (!r.ok) { setError(r.error || "Telemetria indisponível."); return; }
      setError(Array.isArray(r.warnings) ? r.warnings.join(" ") : "");
      setData({ routing: r.routing as RoutingData, evolution: r.evolution as EvolutionData, runs: (r.runs as CognitiveRun[]) ?? [] });
    });
    return () => { active = false; };
  }, [version]);
  useEffect(() => {
    const refresh = () => setVersion((v) => v + 1);
    const offHistory = core().on("historyChanged", refresh), offLab = core().on("labFinished", refresh);
    return () => { offHistory(); offLab(); };
  }, []);
  return { data, error };
}

// ── cores ───────────────────────────────────────────────────────────────────
function rgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6), 16);
  return Number.isFinite(n) ? [(n >> 16) & 255, (n >> 8) & 255, n & 255] : [140, 140, 160];
}
const rgba = (hex: string, a: number) => { const [r, g, b] = rgb(hex); return `rgba(${r},${g},${b},${Math.max(0, Math.min(1, a)).toFixed(3)})`; };
function shade(hex: string, t: number) {               // t > 0 clareia, t < 0 escurece
  const [r, g, b] = rgb(hex);
  const f = (c: number) => Math.round(t > 0 ? c + (255 - c) * t : c * (1 + t));
  return `rgb(${f(r)},${f(g)},${f(b)})`;
}
interface Theme { text: string; muted: string; surface: string; edge: string; accent: string; dark: boolean; font: string; calm: boolean }
function readTheme(): Theme {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string, fb: string) => css.getPropertyValue(name).trim() || fb;
  const surface = v("--bg-surface", "#ffffff");
  // A superficie pode vir em hex ou rgb()/rgba() (vidro); o texto claro tambem denuncia o tema escuro
  const channels = (col: string): [number, number, number] | null => {
    if (col.startsWith("#")) return rgb(col);
    const m = col.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
    return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
  };
  const lum = (c: [number, number, number] | null) => (c ? (c[0] + c[1] + c[2]) / 3 : null);
  const text = v("--text-primary", "#1c1c1e");
  const bgLum = lum(channels(surface)), textLum = lum(channels(text));
  const dark = document.documentElement.dataset.theme === "escuro" || (textLum !== null ? textLum > 150 : (bgLum ?? 255) < 110);
  return { text, muted: v("--text-secondary", "#6b6b70"), surface, edge: v("--edge", "#d4d4d8"),
    accent: v("--accent", "#16897e"), dark,
    font: getComputedStyle(document.body).fontFamily || "sans-serif", calm: reducedMotion() };
}
const reducedMotion = () =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || document.documentElement.dataset.motion === "off";

// ── componente ──────────────────────────────────────────────────────────────
export interface PanoramaProps {
  knowledge: Knowledge | null;
  compact?: boolean;
  selected?: string;
  note?: string;
  onSelect?: (agent: string) => void;
  onNote?: (agent: string, rel: string) => void;
}

export function HarnessPanorama({ knowledge, compact = false, selected = "", note = "", onSelect, onNote }: PanoramaProps) {
  const task = useTask();
  const { data: harness, error: harnessError } = useHarness(task.busy);
  const [runKey, setRunKey] = useState("live");
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [inspected, setInspected] = useState("");
  const [connection, setConnection] = useState("");
  const replay = harness?.runs.find((r) => r.id === runKey);
  const recorded = replay?.events ?? [];
  const duration = recorded.at(-1)?.ms ?? 0;
  const observed = useMemo(() => runKey === "live" ? task.cognitive : eventsAt(recorded, playhead), [runKey, task.cognitive, recorded, playhead]);
  const current = observed.at(-1);
  const signalAt = useRef(0);
  useEffect(() => { signalAt.current = performance.now(); }, [current, runKey]);
  useEffect(() => {
    if (!playing || runKey === "live") return;
    const start = performance.now(), from = playhead;
    const timer = setInterval(() => {
      const next = Math.min(duration, from + performance.now() - start);
      setPlayhead(next);
      if (next >= duration) setPlaying(false);
    }, 50);
    return () => clearInterval(timer);
    // O cursor avanca pelo relogio, sem reiniciar o intervalo a cada quadro.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, runKey, duration]);
  const scene = useMemo<Scene | null>(() => knowledge && layoutPanorama({
    agents: AGENTS.map((id) => ({ id, name: AGENT_LOOK[id]!.name, color: AGENT_LOOK[id]!.color, ...knowledge.agents[id]! })),
    routing: harness?.routing, evolution: harness?.evolution, events: observed,
  }), [knowledge, harness, observed]);
  const live = useMemo<LiveLit | null>(() => scene && traceLit(observed, scene), [scene, observed]);

  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const cam = useRef<Camera>({ ...VIEWS.geral });
  const goal = useRef<Camera>({ ...VIEWS.geral });
  const viewCam = useRef<Camera>({ ...VIEWS.geral });   // a camera de fato desenhada (enquadrada); o clique usa a mesma
  const hoverId = useRef("");
  const state = useRef({ scene, live, selected, note, compact, current, connection });
  state.current = { scene, live, selected, note, compact, current, connection };
  const outcomeAt = useRef(0);
  const dragging = useRef(false);
  const down = useRef<{ x: number; y: number; yaw: number; pitch: number; moved: boolean } | null>(null);
  const [view, setView] = useState<View>("geral");
  const [spin, setSpin] = useState(true);
  const spinRef = useRef(spin);
  spinRef.current = spin;
  const [tip, setTip] = useState<{ node: SceneNode; x: number; y: number } | null>(null);

  useEffect(() => { if (live?.outcome) outcomeAt.current = performance.now(); }, [live?.outcome]);
  const goTo = useCallback((v: View) => { setView(v); goal.current = { ...VIEWS[v], yaw: cam.current.yaw + angleTo(cam.current.yaw, VIEWS[v].yaw) }; }, []);

  // Curvas 3D das ligacoes: calculadas uma vez por cena
  const curves = useMemo(() => {
    const out = new Map<string, Vec3[]>();
    if (!scene) return out;
    for (const e of scene.edges) {
      const a = scene.byId.get(e.a)!, b = scene.byId.get(e.b)!;
      const nerve: Vec3 = [12 * Math.sin(b.pos[1] / 100), b.pos[1], 0];
      out.set(e.id, e.kind === "traffic" ? [...curvePoints(a.pos, nerve, 0, 10), ...curvePoints(nerve, b.pos, e.lift, 12).slice(1)]
        : curvePoints(a.pos, b.pos, e.lift, e.kind === "own" ? 8 : 16));
    }
    return out;
  }, [scene]);
  const ready = !!scene;
  const curvesRef = useRef(curves);
  curvesRef.current = curves;

  // Laco de desenho: so roda com o painel visivel na tela
  useEffect(() => {
    const el = canvas.current, box = wrap.current;
    if (!el || !box) return;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    let theme = readTheme();
    let w = 0, h = 0, dpr = 1, raf = 0, visible = true, last = performance.now(), dirty = true;
    let lastState: unknown = null, lastSignaling = false;
    const resize = () => {
      const r = box.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = Math.max(1, r.width);
      h = Math.max(1, r.height);
      dirty = true;
      el.width = Math.round(w * dpr);
      el.height = Math.round(h * dpr);
      el.style.width = `${w}px`;
      el.style.height = `${h}px`;
    };
    const ro = new ResizeObserver(resize);
    ro.observe(box);
    resize();
    const io = new IntersectionObserver(([e]) => { visible = !!e?.isIntersecting; if (visible) loop(); });
    io.observe(box);
    const mo = new MutationObserver(() => { theme = readTheme(); dirty = true; });
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => { theme = readTheme(); dirty = true; };
    media.addEventListener("change", changed);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "style", "class", "data-photo", "data-motion", "data-palette"] });

    const frame = (now: number) => {
      const dt = Math.min(64, now - last);
      last = now;
      const c = cam.current, g = goal.current;
      const ease = 1 - Math.pow(0.0025, dt / 1000);                 // aproxima ~uniforme, independe do fps
      const moving = Math.abs(c.yaw - g.yaw) + Math.abs(c.pitch - g.pitch) + Math.abs(c.dist - g.dist)
        + Math.hypot(...c.target.map((v, i) => v - g.target[i]!)) > 0.001;
      const signaling = !!state.current.current && now - signalAt.current < 1200 && spinRef.current && !theme.calm;
      if (!dirty && lastState === state.current && !moving && !signaling && !lastSignaling) return;
      dirty = false; lastState = state.current; lastSignaling = signaling;
      cam.current = clampCamera({
        ...c, yaw: c.yaw + (g.yaw - c.yaw) * ease, pitch: c.pitch + (g.pitch - c.pitch) * ease, dist: c.dist + (g.dist - c.dist) * ease,
        target: [c.target[0] + (g.target[0] - c.target[0]) * ease, c.target[1] + (g.target[1] - c.target[1]) * ease,
          c.target[2] + (g.target[2] - c.target[2]) * ease], fov: g.fov,
      });
      // Enquadra pelo formato do painel: alto e estreito (ao lado da conversa) afasta a camera para caber tudo
      viewCam.current = { ...cam.current, dist: cam.current.dist * Math.min(1.7, Math.max(1, Math.pow((1.25 * h) / w, 0.7))) };
      draw(ctx, w, h, dpr, now, theme);
    };
    const loop = () => {
      cancelAnimationFrame(raf);
      const tick = (now: number) => {
        if (!visible) return;
        if (now - last >= 32) frame(now);
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    loop();
    return () => { cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); mo.disconnect(); media.removeEventListener("change", changed); };
    // O canvas so existe com a cena pronta (antes disso aparece o esqueleto): o laco liga quando ela fica pronta
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  function draw(ctx: CanvasRenderingContext2D, w: number, h: number, dpr: number, now: number, th: Theme) {
    const { scene: sc, live: lv, selected: sel, note: nt, compact: small, current: event, connection: selectedEdge } = state.current;
    const clock = animationTime(now, th.calm || !spinRef.current || now - signalAt.current >= 1200 || !event);
    const lod = detailLevel(w, small);
    const c = viewCam.current;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    // Fundo: luz no centro, borda mais escura (profundidade de palco)
    const bg = ctx.createRadialGradient(w * 0.5, h * 0.42, 10, w * 0.5, h * 0.5, Math.max(w, h) * 0.75);
    bg.addColorStop(0, th.dark ? "rgba(70,72,95,0.55)" : "rgba(255,255,255,0.75)");
    bg.addColorStop(1, th.dark ? "rgba(8,9,14,0.65)" : "rgba(214,218,230,0.55)");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);
    if (!sc) return;
    const P = (p: Vec3) => project(p, c, w, h);
    const far = c.dist + 900;
    const fog = (depth: number) => Math.max(0.18, Math.min(1, 1.15 - (depth - c.dist * 0.45) / (far - c.dist * 0.45)));

    // Foco: agente sob o mouse ou escolhido
    const hov = hoverId.current ? sc.byId.get(hoverId.current) : undefined;
    const focus = hov?.kind === "agent" || hov?.kind === "core" ? hov.id : hov?.agent && hov.kind === "note" ? hov.agent : sel;
    const working = lv?.working ?? new Set<string>();
    const lit = lv?.nodes ?? new Set<string>();
    const litPath = new Set(lv?.path ?? []);

    // Sombras no chao (vendem a altura de cada no)
    for (const n of sc.nodes) {
      if (n.kind === "note" && small) continue;
      const p = P([n.pos[0], sc.floorY, n.pos[2]]);
      if (!p.visible) continue;
      const height = n.pos[1] - sc.floorY;
      const rr = Math.max(1.5, n.r * p.k * (1 + height / 900));
      ctx.fillStyle = `rgba(0,0,0,${(th.dark ? 0.32 : 0.16) * Math.max(0.15, 1 - height / 520) * (n.kind === "note" ? 0.5 : 1)})`;
      ctx.beginPath(); ctx.ellipse(p.x, p.y, rr * 1.15, rr * 0.38, 0, 0, Math.PI * 2); ctx.fill();
    }

    // Ligacoes e trilhas

    for (const e of sc.edges) {
      const pts = curvesRef.current.get(e.id);
      if (!pts) continue;
      const a = sc.byId.get(e.a)!, b = sc.byId.get(e.b)!;
      const isLit = litPath.has(e.id);
      const inspectedEdge = selectedEdge === e.id;
      let color = th.muted, alpha = 0.18, width = 1;
      if (e.kind === "route") { color = isLit ? th.accent : "#7d8aa5"; alpha = isLit ? 0.95 : 0.16 + 0.6 * e.weight; width = (isLit ? 3 : 1) + 5 * e.weight; }
      else if (e.kind === "traffic") { color = isLit ? th.accent : b.color; alpha = isLit ? 0.9 : 0.1 + 0.5 * e.weight; width = (isLit ? 2.5 : 0.8) + 4 * e.weight; }
      else if (e.kind === "shared") { color = "#e88aa6"; alpha = focus ? (e.b === focus ? 0.75 : 0.06) : 0.22; width = 1; }
      else if (e.kind === "own") { color = b.color; alpha = focus && focus !== a.id && focus !== b.id ? 0.04 : 0.16; width = 0.8; }
      if (isLit && e.kind === "own") { color = th.accent; alpha = 0.95; width = 2; }
      else if (e.kind === "evolve") { color = a.color; alpha = focus ? (e.b === focus ? 0.7 : 0.05) : 0.24; width = 1; }
      if (inspectedEdge) { color = th.accent; alpha = 1; width = 2.5; }
      if (alpha < 0.03 || (lod === 1 && e.kind === "own" && !focus && !isLit)) continue;
      ctx.beginPath();
      let started = false, depthSum = 0, k = 0;
      for (const q of pts) {
        const p = P(q);
        if (!p.visible) { started = false; continue; }
        if (!started) { ctx.moveTo(p.x, p.y); started = true; } else ctx.lineTo(p.x, p.y);
        depthSum += p.depth; k += p.k;
      }
      const f = fog(depthSum / pts.length);
      ctx.strokeStyle = rgba(color.startsWith("#") ? color : "#7d8aa5", alpha * f);
      ctx.lineWidth = Math.max(0.6, width * Math.min(1.6, (k / pts.length) * 1.1));
      if (e.kind === "evolve") ctx.setLineDash([3, 5]); else ctx.setLineDash([]);
      ctx.stroke();
      ctx.setLineDash([]);
      // Fibras paralelas formam feixes organicos da mesma conexao, sem inventar componentes.
      if (lod > 1 && (e.kind === "traffic" || e.kind === "route" || e.kind === "evolve")) {
        for (let strand = -2; strand <= 2; strand++) {
          if (!strand) continue;
          ctx.beginPath();
          pts.forEach((q, i) => {
            const wave = Math.sin((i / (pts.length - 1)) * Math.PI);
            const p = P([q[0] + strand * wave * 3, q[1], q[2] + strand * wave * 5]);
            if (!p.visible) return;
            if (!i) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
          });
          ctx.lineWidth = 0.6; ctx.globalAlpha = 0.3; ctx.stroke(); ctx.globalAlpha = 1;
        }
      }
      const flow = isLit && clock > 0;
      if (flow) {
        for (let j = 0; j < (isLit ? 3 : 1); j++) {
          const u = signalProgress(now, signalAt.current, j * 0.07);
          const idx = u * (pts.length - 1);
          const i0 = Math.floor(idx), fr = idx - i0;
          const q0 = pts[i0]!, q1 = pts[Math.min(pts.length - 1, i0 + 1)]!;
          const p = P([q0[0] + (q1[0] - q0[0]) * fr, q0[1] + (q1[1] - q0[1]) * fr, q0[2] + (q1[2] - q0[2]) * fr]);
          if (!p.visible) continue;
          const pr = Math.max(2, (isLit ? 5 : 3) * p.k);
          const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, pr * 3);
          const col = isLit ? th.accent : (e.kind === "traffic" ? b.color : "#9fb0d6");
          glow.addColorStop(0, rgba(col.startsWith("#") ? col : "#16897e", isLit ? 0.95 : 0.55));
          glow.addColorStop(1, rgba(col.startsWith("#") ? col : "#16897e", 0));
          ctx.fillStyle = glow;
          ctx.beginPath(); ctx.arc(p.x, p.y, pr * 3, 0, Math.PI * 2); ctx.fill();
        }
      }
    }

    // Nos: do fundo para a frente
    const order = sc.nodes.map((n) => ({ n, p: P(n.pos) })).filter((x) => x.p.visible).sort((x, y) => y.p.depth - x.p.depth);
    const sinceOutcome = (now - outcomeAt.current) / 1000;
    for (const { n, p } of order) {
      const R = Math.max(n.kind === "note" ? 1.6 : 3, n.r * p.k);
      let alpha = fog(p.depth);
      if (focus && n.kind === "note" && n.agent !== focus) alpha *= 0.22;
      if (focus && n.kind === "agent" && n.id !== focus) alpha *= 0.65;
      if (n.kind === "stage" && !lit.has(n.id) && (n.weight ?? 0) === 0) alpha *= 0.55;
      ctx.globalAlpha = alpha;
      const isHover = hoverId.current === n.id, isSel = (n.kind === "agent" || n.kind === "core") && n.id === sel || n.rel === nt && !!nt;
      const glowOn = lit.has(n.id) || working.has(n.id) || isHover || isSel;
      if (glowOn) {
        const pulse = working.has(n.id) && clock ? 1 + 0.12 * Math.sin(clock / 180) : 1;
        const gr = ctx.createRadialGradient(p.x, p.y, R * 0.6, p.x, p.y, R * 2.6 * pulse);
        const col = lit.has(n.id) && n.kind === "stage" ? th.accent : n.color;
        gr.addColorStop(0, rgba(col.startsWith("#") ? col : "#16897e", 0.5));
        gr.addColorStop(1, rgba(col.startsWith("#") ? col : "#16897e", 0));
        ctx.fillStyle = gr;
        ctx.beginPath(); ctx.arc(p.x, p.y, R * 2.6 * pulse, 0, Math.PI * 2); ctx.fill();
      }
      if (n.kind === "stage") drawNeuron(ctx, p.x, p.y, R, n.color);
      else if (n.kind === "plan") drawCrystal(ctx, p.x, p.y, R, n.color, 0, n.status === "promoted");
      else if (n.kind === "core" || n.kind === "agent") drawNeuron(ctx, p.x, p.y, R, n.color);
      else drawSphere(ctx, p.x, p.y, R, n.color);
      if (n.kind === "core") drawOrbit(ctx, n, c, w, h, 0, th);
      // Resultado do ultimo pedido: anel verde (ok) ou vermelho (falhou) que se desfaz
      if (clock && lv?.outcome && sinceOutcome < 1.2 && (n.kind === "agent" && lit.has(n.id) || n.id === "MAESTRO")) {
        ctx.strokeStyle = rgba(lv.outcome === "ok" ? "#22c55e" : "#ef4444", 1 - sinceOutcome / 2.6);
        ctx.lineWidth = 2.5;
        ctx.beginPath(); ctx.arc(p.x, p.y, R * (1.3 + sinceOutcome * 0.9), 0, Math.PI * 2); ctx.stroke();
      }
      if (isSel) {
        ctx.strokeStyle = th.text;
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(p.x, p.y, R + 4, 0, Math.PI * 2); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;

    // Rotulos: agentes, Maestro e etapas (no modo compacto, so as etapas acesas)
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const occupied: Array<{ left: number; right: number; top: number; bottom: number }> = [];
    const priority = (n: SceneNode) => n.kind === "core" || n.kind === "agent" ? 0 : lit.has(n.id) ? 1 : 2;
    for (const { n, p } of [...order].sort((a, b) => priority(a.n) - priority(b.n))) {
      const isStage = n.kind === "stage";
      if (!(n.kind === "agent" || n.kind === "core" || (isStage && (!small || lit.has(n.id))))) continue;
      const R = Math.max(3, n.r * p.k);
      const size = Math.round(Math.max(10, Math.min(13.5, 9 + p.k * 4)));
      ctx.font = `${n.kind === "stage" ? 500 : 650} ${size}px ${th.font}`;
      const label = n.label ?? n.id;
      const tw = ctx.measureText(label).width;
      const dot = isStage ? 0 : 10;                     // ponto na cor do agente, antes do nome
      const preferredY = p.y + (isStage && !n.labelAbove ? R * 0.9 + 12 : -(R + 13));
      const bounds = (y: number) => ({ left: p.x - (tw + dot) / 2 - 9, right: p.x + (tw + dot) / 2 + 9,
        top: y - size / 2 - 6, bottom: y + size / 2 + 6 });
      const y = [0, -22, 22, -44, 44].map((offset) => preferredY + offset).find((candidate) => {
        const b = bounds(candidate);
        return b.top > 4 && b.bottom < h - 4 && !occupied.some((a) => b.left < a.right && b.right > a.left && b.top < a.bottom && b.bottom > a.top);
      });
      if (y === undefined) continue; // o inspetor mantem acesso aos nomes ocultos pelo nivel de detalhe
      occupied.push(bounds(y));
      ctx.globalAlpha = fog(p.depth) * (isStage && !lit.has(n.id) ? 0.75 : 1);
      ctx.fillStyle = th.dark ? "rgba(20,22,30,0.72)" : "rgba(255,255,255,0.82)";
      roundRect(ctx, p.x - (tw + dot) / 2 - 7, y - size / 2 - 4, tw + dot + 14, size + 8, (size + 8) / 2);
      ctx.fill();
      if (dot) {
        ctx.fillStyle = n.color;
        ctx.beginPath(); ctx.arc(p.x - (tw + dot) / 2 + 3, y, 3.5, 0, Math.PI * 2); ctx.fill();
      }
      ctx.fillStyle = lit.has(n.id) && isStage ? th.accent : th.text;
      ctx.fillText(label, p.x + dot / 2, y + 0.5);
    }
    ctx.globalAlpha = 1;
  }

  // ── interacao: arrastar gira, roda aproxima, clique escolhe ──────────────
  const local = (e: { clientX: number; clientY: number }) => {
    const r = canvas.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top, w: r.width, h: r.height };
  };
  const onPointerDown = (e: React.PointerEvent) => {
    canvas.current?.setPointerCapture(e.pointerId);
    down.current = { x: e.clientX, y: e.clientY, yaw: goal.current.yaw, pitch: goal.current.pitch, moved: false };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = down.current;
    if (d) {
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) { d.moved = true; dragging.current = true; }
      if (d.moved) {
        goal.current = clampCamera({ ...goal.current, yaw: d.yaw - dx * 0.006, pitch: d.pitch + dy * 0.005 });
        setTip(null);
        return;
      }
    }
    if (!scene) return;
    const m = local(e);
    const n = pick(scene.nodes, viewCam.current, m.w, m.h, m.x, m.y);
    if ((n?.id ?? "") !== hoverId.current) {
      hoverId.current = n?.id ?? "";
      setTip(n ? { node: n, x: m.x, y: m.y } : null);
    } else if (n) setTip((cur) => (cur ? { ...cur, x: m.x, y: m.y } : cur));
    if (canvas.current) canvas.current.style.cursor = n ? "pointer" : "grab";
  };
  const onPointerUp = (e: React.PointerEvent) => {
    const d = down.current;
    down.current = null;
    dragging.current = false;
    if (!d || d.moved || !scene) return;
    const m = local(e);
    const n = pick(scene.nodes, viewCam.current, m.w, m.h, m.x, m.y);
    if (!n) return;
    setInspected(n.id); setConnection("");
    if ((n.kind === "agent" || n.kind === "core") && onSelect) onSelect(n.id);
    else if ((n.kind === "note" || n.kind === "shared") && n.rel && onNote) onNote(n.agent ?? "MAESTRO", n.rel);
    else {
      // Etapa, plano ou hipotese: a camera vai ate ele e o cartao fica
      goal.current = clampCamera({ ...goal.current, target: n.pos, dist: Math.min(goal.current.dist, 640) });
      setTip({ node: n, x: m.x, y: m.y });
    }
  };
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      goal.current = clampCamera({ ...goal.current, dist: goal.current.dist * (1 + Math.sign(e.deltaY) * Math.min(0.25, Math.abs(e.deltaY) / 600)) });
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, [ready]);
  const onKey = (e: React.KeyboardEvent) => {
    const g = goal.current;
    const step: Record<string, Partial<Camera>> = {
      ArrowLeft: { yaw: g.yaw + 0.15 }, ArrowRight: { yaw: g.yaw - 0.15 }, ArrowUp: { pitch: g.pitch + 0.1 }, ArrowDown: { pitch: g.pitch - 0.1 },
      "+": { dist: g.dist * 0.88 }, "=": { dist: g.dist * 0.88 }, "-": { dist: g.dist * 1.12 },
    };
    const pan: Record<string, Vec3> = { w: [0, 25, 0], s: [0, -25, 0], a: [-25, 0, 0], d: [25, 0, 0], q: [0, 0, -25], e: [0, 0, 25] };
    if (pan[e.key]) { e.preventDefault(); goal.current = { ...g, target: g.target.map((v, i) => v + pan[e.key]![i]!) as unknown as Vec3 }; return; }
    if (e.key === "0") return goTo(view);
    const s = step[e.key];
    if (!s) return;
    e.preventDefault();
    goal.current = clampCamera({ ...g, ...s });
  };

  if (!knowledge || !scene) return <Skeleton className={cn("w-full rounded-r4", compact ? "h-full" : "aspect-[16/9]")} />;

  const ev = harness?.evolution.summary;
  const inspectedNode = scene.byId.get(inspected);
  const inspectedConnection = scene.edges.find((e) => e.id === connection);
  const notes = Object.values(knowledge.agents).reduce((s, a) => s + a.own.length, 0);

  return (
    <section className={cn("harness-panorama", compact && "is-compact")} aria-label="Panorama do harness">
      {harnessError && <p className="hp-error" role="status">{harnessError} As regiões continuam navegáveis; dados de atividade não disponíveis.</p>}
      <div ref={wrap} className="hp-stage" tabIndex={0} onKeyDown={onKey}
        aria-label="Cena 3D do harness. Arraste para girar em 360 graus; roda aproxima, setas giram, W A S D deslocam o foco, zero volta a visão.">
        <canvas ref={canvas} className="hp-canvas" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
          onPointerLeave={() => { hoverId.current = ""; setTip(null); }} onDoubleClick={() => goTo(view)} />

        <div className={cn("hp-live", task.busy && "is-on")} aria-live="polite">
          <span className="hp-live-dot" aria-hidden />
          <div className="min-w-0">
            <p className="hp-live-title">{demoMode ? "Demonstração · dados fictícios" : runKey !== "live" ? "Replay registrado" : task.dryRun ? "Simulação" : task.busy ? "Ao vivo" : "Observatório"}</p>
            <p className="hp-live-step">{current ? `${COGNITIVE_STAGES[current.stage].label} · ${STATUS_LABEL[current.status]}` : "Sem evento observado neste instante"}</p>
            {current?.count ? <p className="hp-live-step">{current.count} {current.action === "selected_characters" ? "caracteres selecionados" : current.stage === "model" ? "tokens reportados" : "referências"}</p> : null}
          </div>
        </div>

        <div className="hp-tools">
          {!compact && <Segmented label="Visão" value={view} onValueChange={goTo} options={VIEW_OPTIONS} />}
          {compact && (
            <select className="hp-select" aria-label="Visão" value={view} onChange={(e) => goTo(e.target.value as View)}>
              {VIEW_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          )}
          <button type="button" className="hp-icon" aria-pressed={spin} title={spin ? "Pausar impulsos" : "Mostrar impulsos observados"} onClick={() => setSpin((v) => !v)}>
            <Icon name={spin ? "stop" : "play"} size={13} />
          </button>
          <button type="button" className="hp-icon" title="Voltar a visão" onClick={() => goTo(view)}><Icon name="refresh" size={13} /></button>
        </div>

        {tip && (
          <div className="hp-tip" style={{ left: tip.x, top: tip.y }} role="tooltip">
            <small>{KIND_LABEL[tip.node.kind]}{tip.node.kind !== "agent" && tip.node.agent && tip.node.kind !== "core" ? ` · ${AGENT_LOOK[tip.node.agent]?.name ?? tip.node.agent}` : ""}</small>
            <strong>{tip.node.label ?? tip.node.id}</strong>
            {tip.node.detail && <span>{tip.node.detail}</span>}
            {(tip.node.kind === "note" || tip.node.kind === "shared") && onNote && <em>Clique para abrir a nota</em>}
            {tip.node.kind === "agent" && onSelect && <em>Clique para ver o conhecimento</em>}
          </div>
        )}
      </div>

      <div className="hp-timeline">
        <label>Operação
          <select aria-label="Operação para explorar" value={runKey} onChange={(e) => { setRunKey(e.target.value); setPlaying(false); setPlayhead(0); }}>
            <option value="live">Execução atual</option>
            {(harness?.runs ?? []).filter((r) => r.id).map((r) => <option key={r.id} value={r.id}>{r.when.replace("T", " ")} · {routeLabel(r.route)}{!r.events.length ? " · sem registro cognitivo" : ""}</option>)}
          </select>
        </label>
        {runKey !== "live" && <>
          <button type="button" disabled={!recorded.length} onClick={() => { if (playhead >= duration) setPlayhead(0); setPlaying((v) => !v); }}>{playing ? "Pausar replay" : "Reproduzir"}</button>
          <input type="range" aria-label="Instante da operação" min={0} max={Math.max(1, duration)} value={playhead} onChange={(e) => { setPlaying(false); setPlayhead(Number(e.target.value)); }} />
          <span>{fmtDuration(playhead)} / {fmtDuration(duration)}</span>
          {!recorded.length && <p>Esta operação não possui eventos cognitivos registrados. Nenhuma atividade será inventada.</p>}
          {!!replay?.dropped && <p>Registro parcial: {replay.dropped} eventos excederam o limite.</p>}
        </>}
      </div>
      {!compact && <div className="hp-inspector">
        <div>
          <label>Região ou unidade
            <select aria-label="Inspecionar região ou unidade" value={inspected} onChange={(e) => setInspected(e.target.value)}>
              <option value="">Escolha uma região, agente ou memória</option>
              {scene.nodes.map((n) => <option key={n.id} value={n.id}>{KIND_LABEL[n.kind]} · {n.label || n.id}</option>)}
            </select>
          </label>
          <strong>{inspectedNode?.label || "Explore uma região"}</strong>
          <p>{inspectedNode?.detail || "Selecione uma região, agente, memória ou sinapse. A organização nervosa é uma analogia funcional da arquitetura."}</p>
          {inspectedNode && <button type="button" onClick={() => { goal.current = { ...goal.current, target: inspectedNode.pos, dist: 240 }; }}>Entrar na região</button>}
          {inspectedNode?.agent && onSelect && <button type="button" onClick={() => onSelect(inspectedNode.agent!)}>Ver agente</button>}
          {inspectedNode?.rel && onNote && <button type="button" onClick={() => onNote(inspectedNode.agent || "MAESTRO", inspectedNode.rel!)}>Abrir nota</button>}
        </div>
        <div>
          <label>Sinapse
            <select aria-label="Inspecionar conexão" value={connection} onChange={(e) => setConnection(e.target.value)}>
              <option value="">Selecione uma conexão</option>
              {scene.edges.filter((e) => !inspected || e.a === inspected || e.b === inspected).map((e) => <option key={e.id} value={e.id}>{scene.byId.get(e.a)?.label} → {scene.byId.get(e.b)?.label}</option>)}
            </select>
          </label>
          {inspectedConnection && <p>{inspectedConnection.kind} · peso observado {inspectedConnection.weight.toFixed(2)}. A ligação indica um caminho do código; não prova uso nesta operação.</p>}
        </div>
        <div>
          <strong>{current ? COGNITIVE_STAGES[current.stage].label : "Proveniência"}</strong>
          <p>{current ? `${eventSource(current)} · ${current.agent || "runtime"} · ${current.action || STATUS_LABEL[current.status]}` : "Sinais aparecem apenas quando há um evento registrado."}</p>
          {!!current?.refs.length && <ul>{current.refs.map((ref, i) => <li key={`${ref}:${i}`}>{ref}</li>)}</ul>}
        </div>
      </div>}
      <div className="hp-legend">
        <span><i className="hp-k hp-k-route" /> rota de um pedido · espessura = tráfego real ({harness?.routing.total ?? 0} pedidos)</span>
        <span><i className="hp-k hp-k-note" /> {notes} notas dos agentes</span>
        <span><i className="hp-k hp-k-shared" /> {knowledge.shared.size} na memória comum</span>
        <span><i className="hp-k hp-k-plan" /> planos aprendidos: {ev ? `${ev.promoted} promovidos · ${ev.candidate} candidatos · ${ev.blocked} bloqueados` : "…"}</span>
        {!compact && <span><i className="hp-k hp-k-hyp" /> {ev?.hypotheses ?? 0} hipóteses do Lab</span>}
      </div>

      {!compact && (
        <ul className="sr-only" aria-label="Agentes e etapas">
          {AGENTS.map((id) => (
            <li key={id}><button type="button" onClick={() => onSelect?.(id)}>{AGENT_LOOK[id]!.name}: {knowledge.agents[id]!.own.length} notas</button></li>
          ))}
          {STAGES.map((s) => <li key={s.id}>{s.label}: {s.hint}</li>)}
        </ul>
      )}
    </section>
  );
}

/** Painel ao vivo para a tela de conversa: carrega a propria memoria. */
export function LivePanorama() {
  const { knowledge, error } = useAgentKnowledge();
  if (error) return <p className="hp-error" role="status">Memória indisponível: {error}</p>;
  return <HarnessPanorama knowledge={knowledge} compact />;
}

// ── formas ──────────────────────────────────────────────────────────────────
function drawSphere(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string) {
  const g = ctx.createRadialGradient(x - r * 0.38, y - r * 0.42, r * 0.08, x, y, r);
  g.addColorStop(0, shade(color, 0.62));
  g.addColorStop(0.5, color);
  g.addColorStop(1, shade(color, -0.5));
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  if (r > 6) {                                          // brilho especular
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.beginPath(); ctx.ellipse(x - r * 0.35, y - r * 0.42, r * 0.22, r * 0.14, -0.6, 0, Math.PI * 2); ctx.fill();
  }
}

function drawNeuron(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string) {
  ctx.save(); ctx.translate(x, y);
  const fill = ctx.createRadialGradient(-r * 0.3, -r * 0.25, r * 0.05, 0, 0, r * 1.25);
  fill.addColorStop(0, shade(color, 0.25)); fill.addColorStop(1, shade(color, -0.6));
  ctx.fillStyle = fill;
  ctx.strokeStyle = rgba(color, 0.7); ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i <= 40; i++) {
    const a = i / 40 * Math.PI * 2, radius = r * (0.95 + 0.23 * Math.sin(a * 3) + 0.13 * Math.cos(a * 5));
    const px = Math.cos(a) * radius, py = Math.sin(a) * radius;
    if (!i) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.closePath(); ctx.fill(); ctx.stroke();
  drawSphere(ctx, -r * 0.12, r * 0.1, r * 0.28, color);
  ctx.restore();
}

function drawCrystal(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, now: number, bright: boolean) {
  const spin = (now / 2400) % (Math.PI * 2);
  const wx = r * (0.55 + 0.25 * Math.abs(Math.cos(spin)));
  const top: [number, number] = [x, y - r * 1.25], bottom: [number, number] = [x, y + r * 1.25];
  const left: [number, number] = [x - wx, y], right: [number, number] = [x + wx, y];
  const face = (pts: Array<[number, number]>, fill: string) => {
    ctx.fillStyle = fill;
    ctx.beginPath(); ctx.moveTo(...pts[0]!); for (const p of pts.slice(1)) ctx.lineTo(...p); ctx.closePath(); ctx.fill();
  };
  face([top, left, [x, y]], shade(color, 0.5));
  face([top, right, [x, y]], color);
  face([bottom, left, [x, y]], shade(color, -0.25));
  face([bottom, right, [x, y]], shade(color, -0.5));
  if (bright) {
    ctx.strokeStyle = shade(color, 0.7);
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(...top); ctx.lineTo(...right); ctx.lineTo(...bottom); ctx.lineTo(...left); ctx.closePath(); ctx.stroke();
  }
}

function drawOrbit(ctx: CanvasRenderingContext2D, n: SceneNode, c: Camera, w: number, h: number, now: number, th: Theme) {
  // Anel em volta do Maestro, girando no proprio plano (inclinado): da a leitura de volume do centro
  const pts: Array<{ x: number; y: number }> = [];
  const spin = now / 4000;
  for (let i = 0; i <= 48; i++) {
    const a = (i / 48) * Math.PI * 2 + spin;
    const q: Vec3 = [n.pos[0] + Math.cos(a) * n.r * 1.9, n.pos[1] + Math.sin(a) * n.r * 0.5, n.pos[2] + Math.sin(a) * n.r * 1.9];
    const p = project(q, c, w, h);
    if (p.visible) pts.push(p);
  }
  ctx.strokeStyle = rgba(n.color, 0.55);
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  ctx.stroke();
  const head = pts[Math.floor(((now / 60) % 48))];
  if (head) {
    ctx.fillStyle = th.accent.startsWith("#") ? th.accent : n.color;
    ctx.beginPath(); ctx.arc(head.x, head.y, 2.5, 0, Math.PI * 2); ctx.fill();
  }
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** Menor giro ate o angulo pedido (a camera nao da uma volta inteira para mudar de visao). */
function angleTo(from: number, to: number) {
  let d = (to - from) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return d;
}
