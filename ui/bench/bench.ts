// Bancada dos papeis de parede (so desenvolvimento, `npm run dev` -> /bench/):
//   single   -> um quadro grande:        ?view=single&combo=synthwave&style=dither&ui=0
//   grid     -> todas as cenas:          ?view=grid&combo=synthwave&style=dither
//   palettes -> uma cena em cada paleta: ?view=palettes&scene=aquario&style=halftone&mode=escuro
//   perf     -> tempo por resolucao e estilo (frio, so pintar, preparo em fatias e maior fatia)
// Cores: as mesmas variaveis CSS do app (tokens.css), lidas do proprio quadro (data-theme / data-palette / --accent).
// A comparacao com o motor anterior esta registrada em app/captures/wallpapers-2026-11-18 e docs/architecture/wallpapers.md.
import "../src/styles/tokens.css";
import { GENERATIVE_STYLES, clearGenerativeCache, currentColors, drawGenerative, generativeOf, prepareGenerative, type GenerativeStyle } from "../src/lib/generative";
import { SCENES, type SceneId } from "../src/lib/scenes";
import { COMBOS as APP_COMBOS, PALETTES } from "../src/views/AppearancePanel";

type Look = { mode: string; palette: string; accent: string };
type Combo = Look & { id: string; style: GenerativeStyle; scene: SceneId };
const COMBOS: Combo[] = APP_COMBOS.flatMap((c) => {
  const g = generativeOf(c.wallpaper);
  return g ? [{ id: c.id, mode: c.mode, palette: c.palette, accent: c.accent, style: g.style, scene: g.scene }] : [];
});
const STYLES = GENERATIVE_STYLES;
const q = new URLSearchParams(location.search);
const view = q.get("view") ?? "single";
const W = Number(q.get("w") ?? 960), H = Number(q.get("h") ?? 540);
const out = document.getElementById("out")!;
const info = document.getElementById("info")!;

/** Zonas da interface na maquete (fracoes da tela): barra lateral, titulo e caixa de pedido */
export const MOCK_SAFE = [
  { x: 0.005, y: 0.01, w: 0.165, h: 0.98, kind: "sidebar" },
  { x: 0.36, y: 0.26, w: 0.4, h: 0.1, kind: "content" },
  { x: 0.3, y: 0.78, w: 0.56, h: 0.16, kind: "composer" },
] as const;

function frame(look: Look, label: string, draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => number, ui = true) {
  const fig = document.createElement("figure");
  const box = document.createElement("div");
  box.className = "frame";
  box.dataset.theme = look.mode;
  box.dataset.palette = look.palette;
  box.style.setProperty("--accent", look.accent);
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  box.append(canvas);
  if (ui) {
    const mock = document.createElement("div");
    mock.className = "ui";
    mock.innerHTML = MOCK_SAFE.map((r) => r.kind === "content" ? `<b>Bom dia. O que vamos fazer?</b>`
      : `<i style="left:${r.x * 100}%;top:${r.y * 100}%;width:${r.w * 100}%;height:${r.h * 100}%"></i>`).join("");
    box.append(mock);
  }
  const cap = document.createElement("figcaption");
  fig.append(box, cap);
  requestAnimationFrame(() => {
    const ctx = canvas.getContext("2d")!;
    const t0 = performance.now();
    const cells = draw(ctx, W, H);
    cap.textContent = `${label} · ${(performance.now() - t0).toFixed(0)} ms · ${cells} marcas`;
  });
  return fig;
}

function row(cols: number, items: HTMLElement[]) {
  const r = document.createElement("div");
  r.className = "row";
  r.style.setProperty("--cols", String(cols));
  r.append(...items);
  out.append(r);
}

const colorsOf = (look: Look) => {
  const probe = document.createElement("div");
  probe.dataset.theme = look.mode;
  probe.dataset.palette = look.palette;
  probe.style.setProperty("--accent", look.accent);
  document.body.append(probe);
  const c = currentColors(probe);
  probe.remove();
  return c;
};
const comboOf = (id: string | null) => COMBOS.find((c) => c.id === (id ?? "synthwave")) ?? COMBOS[0]!;

if (view === "single") {
  const combo = comboOf(q.get("combo"));
  const style = (q.get("style") ?? combo.style) as GenerativeStyle;
  const scene = (q.get("scene") ?? combo.scene) as SceneId;
  const colors = colorsOf(combo);
  info.textContent = `${combo.id} · ${scene} · ${style}`;
  row(1, [frame(combo, style, (ctx, w, h) => drawGenerative(ctx, style, w, h, colors, scene, { safe: q.get("ui") === "0" ? [] : MOCK_SAFE }), q.get("ui") !== "0")]);
} else if (view === "grid") {
  const combo = comboOf(q.get("combo"));
  const style = (q.get("style") ?? combo.style) as GenerativeStyle;
  const colors = colorsOf(combo);
  info.textContent = `Todas as cenas · ${style} · paleta ${combo.palette}`;
  row(4, SCENES.map((s) => frame(combo, s.label, (ctx, w, h) => drawGenerative(ctx, style, w, h, colors, s.id), false)));
} else if (view === "palettes") {
  const scene = (q.get("scene") ?? "aquario") as SceneId;
  const style = (q.get("style") ?? "dither") as GenerativeStyle;
  const mode = q.get("mode") ?? "escuro";
  const accent = q.get("accent") ?? "#16897E";
  info.textContent = `${scene} · ${style} · ${mode}, em todas as paletas (destaque ${accent})`;
  row(5, PALETTES.map(([id, label]) => {
    const look = { mode, palette: id, accent };
    const colors = colorsOf(look);
    return frame(look, label, (ctx, w, h) => drawGenerative(ctx, style, w, h, colors, scene), false);
  }));
} else {
  const runs = Number(q.get("runs") ?? 3);
  const sizes: Array<[number, number]> = [[1920, 1080], [2560, 1440], [3840, 2160]];
  const combo = comboOf(q.get("combo") ?? "aquario");
  const colors = colorsOf(combo);
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;
  const median = (xs: number[]) => xs.sort((a, b) => a - b)[Math.floor(xs.length / 2)]!;
  const time = (fn: () => void) => { const t0 = performance.now(); fn(); return performance.now() - t0; };
  const results: Record<string, Record<string, number>> = {};
  info.textContent = `Medindo cena ${combo.scene}…`;
  void (async () => {
    const rows: string[] = [];
    for (const [w, h] of sizes) {
      canvas.width = w; canvas.height = h;
      for (const style of STYLES) {
        const cold = median(Array.from({ length: runs }, () => { clearGenerativeCache(); return time(() => drawGenerative(ctx, style, w, h, colors, combo.scene, { safe: MOCK_SAFE })); }));
        const paint = median(Array.from({ length: runs }, () => time(() => drawGenerative(ctx, style, w, h, colors, combo.scene, { safe: MOCK_SAFE }))));
        clearGenerativeCache();
        let worst = 0;
        const t0 = performance.now();
        await prepareGenerative(style, w, h, combo.scene, { onSlice: (ms) => { worst = Math.max(worst, ms); } });
        const total = performance.now() - t0;
        results[`${w}x${h}/${style}`] = { cold, paint, total, worst };
        rows.push(`<tr><td>${w}x${h}</td><td>${style}</td><td>${cold.toFixed(0)}</td><td>${paint.toFixed(0)}</td><td>${total.toFixed(0)}</td><td>${worst.toFixed(1)}</td></tr>`);
        await new Promise((r) => setTimeout(r, 0));
      }
    }
    info.textContent = `Cena ${combo.scene}, ${runs} rodadas, mediana em ms. ${navigator.userAgent.match(/Chrome\/[\d.]+/)?.[0] ?? ""}, ${navigator.hardwareConcurrency} núcleos.`;
    out.innerHTML = `<table><tr><th>resolução</th><th>estilo</th><th>frio</th><th>só pintar</th><th>preparo total</th><th>maior fatia</th></tr>${rows.join("")}</table>`;
    (window as unknown as { __bench: unknown }).__bench = results;
  })();
}
