// Papeis de parede gerativos (estetica retro digital): uma cena (lib/scenes.ts) desenhada em dithering ou halftone, sempre com as cores da paleta atual (base, luzes e destaque). O motor (lib/wallpaper/
// engine.ts) separa conteudo de estilo: primeiro o buffer da cena, depois a tecnica. O desenho e estatico (so
// refaz quando a janela ou a aparencia muda); o movimento, quando a cena tem, e uma camada leve por cima
// (lib/wallpaper/motion.ts).
// A cena e um campo de luz f(x, y) -> 0..1 (0 = base da paleta, 1 = luz/destaque). Logica pura testada em
// generative.test.ts; o desenho usa um contexto 2D de canvas.

import { SCENE_IDS, type SceneId } from "./scenes";
import { artFor, type SceneArt } from "./wallpaper/art";
import { applySafe, ditherLevels, dotRadius, FieldSampler, safeWeight,
  type Field, type SafeRect } from "./wallpaper/engine";

export type { SafeRect } from "./wallpaper/engine";

export type GenerativeStyle = "dither" | "halftone";
export const GENERATIVE_STYLES: readonly GenerativeStyle[] = ["dither", "halftone"];
export const GENERATIVE_LABEL: Record<GenerativeStyle, string> = { dither: "Dithering", halftone: "Halftone" };
export const GENERATIVE_NOTE: Record<GenerativeStyle, string> = {
  dither: "Pixels em quatro tons, como os primeiros games",
  halftone: "Pontos de tamanho variável, como impressão",
};

export interface Generative { style: GenerativeStyle; scene: SceneId }

/** "gen:<estilo>[:<cena>]" -> estilo e cena (sem cena = synthwave, o formato antigo); outro id -> null */
export function generativeOf(wallpaper: string): Generative | null {
  const [prefix, savedStyle, scene = "retro", ...rest] = wallpaper.split(":");
  // Preferências antigas mantêm a paisagem ao migrar de ASCII para dithering.
  const style = savedStyle === "ascii" ? "dither" : savedStyle;
  if (prefix !== "gen" || rest.length || (style !== "dither" && style !== "halftone")) return null;
  if (!(SCENE_IDS as readonly string[]).includes(scene)) return null;
  return { style, scene: scene as SceneId };
}

export const wallpaperOf = (g: Generative) => `gen:${g.style}:${g.scene}`;

export interface Colors {
  base: string;
  tones: [string, string, string];
  accent: string;
}

type RGB = [number, number, number];

export function hexToRgb(color: string): RGB {
  const m = color.trim().match(/^#?([0-9a-f]{6})$/i);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1]!.slice(i, i + 2), 16)) as RGB;
  const rgb = color.match(/rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)/i);
  return rgb ? [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])] : [0, 0, 0];
}
const mix = (a: RGB, b: RGB, t: number): RGB => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const css = (c: RGB) => `rgb(${Math.round(c[0])} ${Math.round(c[1])} ${Math.round(c[2])})`;

/** Rampa de cor da cena: base -> luzes da paleta -> destaque (as partes mais claras puxam para o destaque). */
export function ramp(colors: Colors, steps = 8): string[] {
  // Os tons do meio puxam o destaque: com paletas claras (tons pastel) a cena ainda tem contraste
  const accent = hexToRgb(colors.accent);
  const stops = [hexToRgb(colors.base), hexToRgb(colors.tones[0]), mix(hexToRgb(colors.tones[2]), accent, 0.35),
    mix(hexToRgb(colors.tones[1]), accent, 0.65), accent];
  const out: string[] = [];
  for (let i = 0; i < steps; i++) {
    const t = (i / (steps - 1)) * (stops.length - 1);
    const k = Math.min(stops.length - 2, Math.floor(t));
    out.push(css(mix(stops[k]!, stops[k + 1]!, t - k)));
  }
  return out;
}

// ── Cores por regiao ────────────────────────────────────────────────────────────────────────────
function toHsl([r, g, b]: RGB): [number, number, number] {
  const R = r / 255, G = g / 255, B = b / 255, max = Math.max(R, G, B), min = Math.min(R, G, B), l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min, s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === R ? (G - B) / d + (G < B ? 6 : 0) : max === G ? (B - R) / d + 2 : (R - G) / d + 4;
  return [h * 60, s, l];
}
function fromHsl([h, s, l]: [number, number, number]): RGB {
  const k = (n: number) => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
  return [f(0) * 255, f(8) * 255, f(4) * 255];
}
/** Cor vizinha do destaque no circulo de cores (graus), com a mesma forca: da variedade sem fugir da paleta */
function turn(color: RGB, degrees: number, sat = 1, light = 0): RGB {
  const [h, s, l] = toHsl(color);
  return fromHsl([(h + degrees + 360) % 360, Math.min(1, s * sat), Math.max(0.05, Math.min(0.95, l + light))]);
}
function steps(stops: RGB[], count = 8): string[] {
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const t = (i / (count - 1)) * (stops.length - 1);
    const k = Math.min(stops.length - 2, Math.floor(t));
    out.push(css(mix(stops[k]!, stops[k + 1]!, t - k)));
  }
  return out;
}

/** Giro de cor (graus no circulo) de cada regiao a partir do destaque: e o color grading da cena. */
export interface ZoneHues {
  ground: number;
  glow: number;
  /** cor fixa do chao (graus): materiais que nao mudam com o destaque (areia dourada, rocha). A forca e a luz
   *  continuam vindo do destaque, entao a paleta ainda manda no clima. */
  groundAbs?: number;
}
export const DEFAULT_HUES: ZoneHues = { ground: -140, glow: 40 };

/** Quatro rampas, uma por regiao da cena: fundo (luzes da paleta), chao/agua (vizinha do destaque, pelo giro da
 *  cena), assunto (o destaque) e luzes (vizinha quente). Assim um mesmo cenario tem varias cores, e cada cena
 *  escolhe as suas (deserto: chao areia; mar: algas quentes contra agua fria). */
export function zoneRamps(colors: Colors, hues: ZoneHues = DEFAULT_HUES): string[][] {
  const base = hexToRgb(colors.base);
  const [t1, t2, t3] = colors.tones.map(hexToRgb) as [RGB, RGB, RGB];
  const light = toHsl(base)[2] > 0.5;                      // paleta clara: tons mais fortes para aparecer
  // Toda cor de regiao separa do fundo pelo menos `min` de contraste (destaque claro em paleta clara sumia)
  const firm = (c: RGB, min: number) => separate(c, base, min);
  const accent = firm(hexToRgb(colors.accent), light ? 2.2 : 1.8);
  const ground = firm(hues.groundAbs === undefined ? turn(accent, hues.ground, 0.85, light ? -0.08 : 0.02)
    : turn(accent, hues.groundAbs - toHsl(accent)[0], 0.7, light ? -0.1 : 0.04), 1.6);
  const glow = firm(turn(accent, hues.glow, light ? 1.1 : 0.9, light ? 0.02 : 0.18), light ? 1.8 : 2.2);
  // a luz mais forte: no escuro quase branca; no claro a cor viva da luz (antes era quase preta: o sol virava buraco)
  const white: RGB = light ? firm(turn(accent, hues.glow * 0.6, 1.15, 0.04), 2.4) : [250, 246, 236];
  return [
    steps([base, t1, mix(t3, accent, 0.3), mix(t2, accent, 0.55), mix(accent, [255, 255, 255], light ? 0 : 0.35)]),
    steps([base, mix(base, ground, 0.35), ground, mix(ground, [255, 255, 255], light ? 0 : 0.4)]),
    steps([base, mix(base, accent, 0.4), accent, mix(accent, white, 0.45)]),
    steps([base, mix(glow, base, 0.4), glow, white]),
  ];
}

/** Contraste de luminancia relativa (WCAG) entre duas cores. */
export function contrastRatio(a: RGB, b: RGB): number {
  const lum = (c: RGB) => {
    const ch = c.map((v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * ch[0]! + 0.7152 * ch[1]! + 0.0722 * ch[2]!;
  };
  const x = lum(a), y = lum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

/** Escurece (fundo claro) ou clareia (fundo escuro) a cor ate separar do fundo; mantem matiz e saturacao. */
function separate(color: RGB, base: RGB, min: number): RGB {
  if (contrastRatio(color, base) >= min) return color;
  const [h, s, l] = toHsl(color);
  const down = toHsl(base)[2] > 0.5;
  let c = color;
  for (let k = 1; k <= 30; k++) {
    c = fromHsl([h, Math.min(1, s * 1.02), Math.max(0, Math.min(1, l + (down ? -0.03 : 0.03) * k))]);
    if (contrastRatio(c, base) >= min) break;
  }
  return c;
}

// ── Desenho ─────────────────────────────────────────────────────────────────────────────────────
export interface Ctx {
  fillStyle: string | CanvasGradient | CanvasPattern;
  imageSmoothingEnabled: boolean;
  fillRect(x: number, y: number, w: number, h: number): void;
  beginPath(): void;
  moveTo(x: number, y: number): void;
  arc(x: number, y: number, r: number, a0: number, a1: number): void;
  fill(): void;
  /** caminho rapido (canvas de verdade): o dithering vira uma imagem pequena ampliada sem suavizar */
  drawImage?(image: CanvasImageSource, ...coords: number[]): void;
}

export interface DrawOptions {
  /** zonas da interface (fracoes da tela): luz e contraste mais baixos atras delas */
  safe?: readonly SafeRect[];
  /** ajuste da direcao de arte da cena (lib/wallpaper/art.ts) */
  art?: Partial<SceneArt>;
  /** desligar o caminho rapido por imagem (testes contam as marcas) */
  vector?: boolean;
}

type AnyCanvas = HTMLCanvasElement | OffscreenCanvas;
function makeCanvas(w: number, h: number): AnyCanvas | null {
  if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(w, h);
  if (typeof document !== "undefined") { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; }
  return null;
}

/** Desenha a cena num contexto de `width` x `height` pixels. Devolve quantas marcas (pixels ou pontos)
 *  foram desenhadas. Etapa 1: buffer da cena (supersampling + mascara da interface); etapa 2: o estilo. */
export function drawGenerative(ctx: Ctx, style: GenerativeStyle, width: number, height: number, colors: Colors,
  sceneId: SceneId = "retro", options: DrawOptions = {}): number {
  const art = artFor(sceneId, options.art);
  const safe = options.safe ?? [];
  const ramps = zoneRamps(colors, art.hues);
  const aspect = width / Math.max(1, height);
  ctx.fillStyle = colors.base;
  ctx.fillRect(0, 0, width, height);
  // Escala das marcas pela largura (scaleOf): no fundo da janela ~1, numa miniatura bem menor
  if (style === "dither") return drawDither(ctx, width, height, sceneId, art, safe, ramps, options.vector);
  return drawHalftone(ctx, width, height, sceneId, art, safe, ramps, aspect);
}

// Luz minima por regiao: o assunto escuro (gato contra a lua) nunca some
const FLOOR = [0, 0, 0.34, 0] as const;

// ── Geometria de cada estilo e cache do buffer da cena ──────────────────────────────────────────
const scaleOf = (width: number) => Math.min(1.4, Math.max(0.3, width / 1440));
type Spec = { cols: number; rows: number; aspect: number; ss: number };
function ditherGeom(width: number, height: number, art: SceneArt) {
  const px = Math.max(2, Math.round(art.ditherPx * art.scale * scaleOf(width)));
  const cols = Math.ceil(width / px), rows = Math.ceil(height / px);
  return { px, cols, rows, spec: { cols, rows, aspect: cols / rows, ss: 2 } };
}
function halftoneGeom(width: number, height: number, art: SceneArt) {
  const cell = Math.max(4, art.halftoneCell * art.scale * scaleOf(width));
  const dy = cell * 0.866, R = cell / 2;
  const cols = Math.ceil((width + cell) / R) + 1, rows = Math.ceil((height + cell) / dy) + 1;
  return { cell, dy, R, cols, rows, spec: { cols, rows, aspect: (cols * R) / (rows * dy), ss: 3 } };
}
function specOf(style: GenerativeStyle, width: number, height: number, art: SceneArt): Spec {
  return (style === "dither" ? ditherGeom : halftoneGeom)(width, height, art).spec;
}

// Buffer da cena por (cena, grade): trocar paleta, destaque ou a mascara da interface so repinta.
const FIELDS = new Map<string, Field>();
const FIELD_CACHE = 8;
const keyOf = (scene: SceneId, s: Spec) => `${scene}|${s.cols}x${s.rows}|${s.aspect.toFixed(4)}|${s.ss}`;
function remember(key: string, field: Field) {
  FIELDS.delete(key);
  FIELDS.set(key, field);
  while (FIELDS.size > FIELD_CACHE) FIELDS.delete(FIELDS.keys().next().value!);
  return field;
}
/** Esvazia o cache dos buffers (bancada e testes). */
export function clearGenerativeCache() { FIELDS.clear(); }

function fieldFor(scene: SceneId, s: Spec): Field {
  const key = keyOf(scene, s);
  const hit = FIELDS.get(key);
  if (hit) return remember(key, hit);
  const sampler = new FieldSampler(scene, s.cols, s.rows, s.aspect, s.ss);
  sampler.step(Infinity);
  return remember(key, sampler.field);
}

function sampleInWorker(scene: SceneId, spec: Spec, signal?: AbortSignal): Promise<Field | null> {
  return new Promise((resolve) => {
    let worker: Worker;
    try {
      worker = new Worker(new URL("./wallpaper/scene.worker.ts", import.meta.url), { type: "module" });
    } catch {
      resolve(null);
      return;
    }
    const finish = (field: Field | null) => {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
      worker.terminate();
      resolve(field);
    };
    const abort = () => finish(null);
    const timeout = setTimeout(abort, 3000);
    signal?.addEventListener("abort", abort, { once: true });
    worker.onmessage = (event: MessageEvent<Field>) => finish(event.data);
    worker.onerror = (event) => { event.preventDefault(); finish(null); };
    worker.onmessageerror = abort;
    try {
      worker.postMessage({ scene, ...spec });
    } catch {
      abort();
    }
  });
}

/** Prepara o buffer para a pintura. Na ausência de worker, calcula em fatias canceláveis. */
export async function prepareGenerative(style: GenerativeStyle, width: number, height: number, sceneId: SceneId,
  options: { art?: Partial<SceneArt>; signal?: AbortSignal; worker?: boolean; budgetMs?: number; onSlice?: (ms: number) => void } = {}): Promise<boolean> {
  const spec = specOf(style, width, height, artFor(sceneId, options.art));
  const key = keyOf(sceneId, spec);
  if (options.signal?.aborted) return false;
  if (FIELDS.has(key)) return true;
  if (options.worker) {
    const field = await sampleInWorker(sceneId, spec, options.signal);
    if (options.signal?.aborted) return false;
    if (field) {
      remember(key, field);
      return true;
    }
  }
  const sampler = new FieldSampler(sceneId, spec.cols, spec.rows, spec.aspect, spec.ss);
  const budget = options.budgetMs ?? 8;
  let rowsPerSlice = 4;
  while (!sampler.done) {
    if (options.signal?.aborted) return false;
    const t0 = performance.now();
    sampler.step(rowsPerSlice);
    const spent = performance.now() - t0;
    options.onSlice?.(spent);
    // ajusta a fatia para caber no orcamento (a cena custa diferente em cada altura)
    rowsPerSlice = Math.max(1, Math.round(rowsPerSlice * Math.min(2, budget / Math.max(0.5, spent))));
    await new Promise<void>((r) => setTimeout(r, 0));
  }
  if (options.signal?.aborted) return false;
  remember(key, sampler.field);
  return true;
}

function drawDither(ctx: Ctx, width: number, height: number, scene: SceneId, art: SceneArt, safe: readonly SafeRect[],
  ramps: string[][], vector?: boolean): number {
  const { px, cols, rows, spec } = ditherGeom(width, height, art);
  const field = applySafe(fieldFor(scene, spec), safe, width / height);
  const levels = ditherLevels(field, 4, art.dither, FLOOR);
  const tones = ramps.map((r) => [r[0]!, r[2]!, r[4]!, r[7]!]);
  let marks = 0;
  for (let k = 0; k < levels.length; k++) if (levels[k]) marks++;
  const small = !vector && ctx.drawImage ? makeCanvas(cols, rows) : null;
  const g = small?.getContext("2d") as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null | undefined;
  if (small && g) {
    // uma imagem de cols x rows (1 pixel por celula) ampliada sem suavizar: rapido e nitido
    const img = g.createImageData(cols, rows);
    const rgb = tones.map((t) => t.map(hexToRgb));
    for (let at = 0; at < levels.length; at++) {
      const k = levels[at]!;
      if (!k) continue;
      const c = rgb[field.zone[at]!]![k]!;
      img.data[at * 4] = c[0]; img.data[at * 4 + 1] = c[1]; img.data[at * 4 + 2] = c[2]; img.data[at * 4 + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage!(small, 0, 0, cols * px, rows * px);
    return marks;
  }
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const at = j * cols + i, k = levels[at]!;
      if (!k) continue;
      ctx.fillStyle = tones[field.zone[at]!]![k]!;
      ctx.fillRect(i * px, j * px, px, px);
    }
  }
  return marks;
}

function drawHalftone(ctx: Ctx, width: number, height: number, scene: SceneId, art: SceneArt, safe: readonly SafeRect[],
  ramps: string[][], aspect: number): number {
  const { cell, dy, R, cols, rows, spec } = halftoneGeom(width, height, art);
  const buckets = new Map<string, number[]>();
  // Buffer da cena numa grade de meio ponto (R x dy): cada ponto le as duas celulas que cobre
  const field = fieldFor(scene, spec);
  for (let y = 0, row = 0; y < height + cell && row < rows; y += dy, row++) {
    for (let x = (row % 2) * R; x < width + cell; x += cell) {
      const ix = Math.min(cols - 1, Math.round(x / R)), left = row * cols + Math.max(0, ix - 1), right = row * cols + ix;
      const za = field.zone[left]!, zb = field.zone[right]!;
      const z = Math.max(za, zb) >= 2 ? Math.max(za, zb) : za;
      const m = safe.length ? safeWeight(x / width, y / height, safe, aspect) : 0;
      let v = Math.max((field.lum[left]! + field.lum[right]!) / 2, FLOOR[z]!);
      if (m > 0) v = v * (1 - 0.62 * m) + 0.04 * m;
      const r = dotRadius(v, R * 1.02);
      if (!r) continue;
      const ramp = ramps[z]!;
      const color = ramp[Math.min(ramp.length - 1, Math.floor(Math.max(0.3, v) * ramp.length))]!;
      const list = buckets.get(color) ?? buckets.set(color, []).get(color)!;
      list.push(x, y, r);
    }
  }
  let marks = 0;
  for (const [color, list] of buckets) {
    // um caminho por cor (moveTo evita a linha entre um circulo e o proximo)
    ctx.fillStyle = color;
    ctx.beginPath();
    for (let k = 0; k < list.length; k += 3) {
      ctx.moveTo(list[k]! + list[k + 2]!, list[k + 1]!);
      ctx.arc(list[k]!, list[k + 1]!, list[k + 2]!, 0, Math.PI * 2);
    }
    ctx.fill();
    marks += list.length / 3;
  }
  return marks;
}

/** Cores atuais da aparencia, lidas das variaveis CSS do documento. */
export function currentColors(root: HTMLElement = document.documentElement): Colors {
  const style = getComputedStyle(root);
  const read = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return {
    base: read("--tone-0", "#08090a"),
    tones: [read("--tone-1", "#0e2523"), read("--tone-2", "#131617"), read("--tone-3", "#1a1626")],
    accent: read("--accent", "#16897e"),
  };
}
