// Ilustracoes dos agentes do AI Research Lab em meio-tom pixelado (dither), como uma imagem impressa em pontos.
// Cada agente e um campo de densidade f(x, y) -> 0..1 (0 = papel, 1 = tinta cheia), feito de formas com luz e
// sombra (esferas, planos, linhas). O campo vira uma grade de pontos com 3 tons e dither ordenado (Bayer 4x4).
// Logica pura (testada em halftone.test.ts); o desenho no canvas fica em AgentArtwork.tsx.
// Tudo e ilustrativo: nenhum grafico representa dado real.

import type { Agent } from "./types";

export const COLS = 104;
export const ROWS = 90;
export const CELL = 3;
const ASPECT = COLS / ROWS;

type Field = (x: number, y: number) => number;

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const smooth = (edge0: number, edge1: number, v: number) => {
  const t = clamp01((v - edge0) / (edge1 - edge0));
  return t * t * (3 - 2 * t);
};
/** Luz vindo do alto a esquerda, um pouco de frente */
const LIGHT = (() => { const l = [-0.55, -0.6, 0.58]; const n = Math.hypot(...l); return l.map((v) => v / n) as [number, number, number]; })();

/** Esfera sombreada: tinta no lado sem luz, brilho no lado com luz. -1 = fora. */
function sphere(px: number, py: number, cx: number, cy: number, r: number, base = 0.18, depth = 0.8): number {
  const nx = (px - cx) / r, ny = (py - cy) / r;
  const d2 = nx * nx + ny * ny;
  if (d2 > 1) return -1;
  const nz = Math.sqrt(1 - d2);
  const lambert = Math.max(0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]);
  const rim = smooth(0.8, 1, Math.sqrt(d2)) * 0.25;
  return clamp01(base + depth * (1 - lambert) * 0.85 + rim);
}

/** Distancia de um ponto a um segmento */
function segment(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const vx = bx - ax, vy = by - ay;
  const t = clamp01(((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy || 1));
  return Math.hypot(px - ax - vx * t, py - ay - vy * t);
}

/** Retangulo arredondado: distancia com sinal (negativo dentro) */
function box(px: number, py: number, cx: number, cy: number, hw: number, hh: number, r = 0.02): number {
  const qx = Math.abs(px - cx) - hw + r, qy = Math.abs(py - cy) - hh + r;
  return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
}

const glow = (d: number, spread: number, amount: number) => amount * Math.exp(-(d * d) / spread);

// Coordenadas: px de -ASPECT/2 a ASPECT/2, py de -0.5 a 0.5 (isotropicas, centro no meio)
const FIELDS: Record<Agent, Field> = {
  MAESTRO: (px, py) => {
    // Nucleo que coordena: esfera com halo, duas orbitas inclinadas e nos-satelite ligados ao centro
    const core = sphere(px, py, 0, 0, 0.15, 0.22, 0.85);
    if (core >= 0) return core;
    let v = glow(Math.hypot(px, py), 0.05, 0.22);
    for (const [tilt, rx, ry] of [[0.42, 0.42, 0.13], [-0.75, 0.38, 0.1]] as const) {
      const c = Math.cos(tilt), s = Math.sin(tilt);
      const ex = (px * c + py * s) / rx, ey = (-px * s + py * c) / ry;
      const ring = Math.abs(Math.hypot(ex, ey) - 1);
      v = Math.max(v, (1 - smooth(0, 0.07, ring)) * 0.55);
    }
    for (let k = 0; k < 7; k++) {
      const a = (k / 7) * Math.PI * 2 + 0.35;
      const nx = Math.cos(a) * 0.36, ny = Math.sin(a) * 0.3;
      const node = sphere(px, py, nx, ny, 0.035 + (k % 3) * 0.008, 0.3, 0.9);
      if (node >= 0) return node;
      v = Math.max(v, (1 - smooth(0.002, 0.007, segment(px, py, 0, 0, nx, ny))) * 0.4);
      const b = ((k + 2) % 7 / 7) * Math.PI * 2 + 0.35;
      v = Math.max(v, (1 - smooth(0.002, 0.006, segment(px, py, nx, ny, Math.cos(b) * 0.36, Math.sin(b) * 0.3))) * 0.28);
    }
    return v;
  },

  WEB: (px, py) => {
    // Globo com malha de latitudes e longitudes, inclinado, e uma atmosfera em volta
    const r = 0.36;
    const nx = px / r, ny = (py - 0.02) / r;
    const d2 = nx * nx + ny * ny;
    if (d2 > 1) {
      const d = Math.sqrt(d2) - 1;
      const orbit = Math.abs(Math.hypot(px / 0.5, (py + px * 0.25) / 0.14) - 1);
      return Math.max(glow(d, 0.02, 0.35), (1 - smooth(0, 0.05, orbit)) * 0.45 * (py + px * 0.25 > -0.02 ? 1 : 0.35));
    }
    const nz = Math.sqrt(1 - d2);
    const tilt = 0.4;
    const y2 = ny * Math.cos(tilt) - nz * Math.sin(tilt);
    const z2 = ny * Math.sin(tilt) + nz * Math.cos(tilt);
    const lat = Math.asin(Math.max(-1, Math.min(1, y2)));
    const lon = Math.atan2(nx, z2) + 0.6;
    const near = (v: number) => { const f = ((v % 1) + 1) % 1; return Math.min(f, 1 - f); };   // distancia a linha
    const grid = Math.min(near((lat / Math.PI) * 8), near((lon / Math.PI) * 6) / Math.max(0.35, Math.cos(lat)));
    const line = smooth(0.03, 0.08, grid);
    const lambert = Math.max(0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]);
    return clamp01(0.08 + (1 - lambert) * 0.55 + (1 - line) * 0.38);
  },

  DESKTOP: (px, py) => {
    // Tres janelas flutuando em camadas, cada uma com sombra, barra de titulo e conteudo; um cursor na frente
    const cursor = [[0.22, 0.2], [0.22, 0.34], [0.255, 0.305], [0.28, 0.36], [0.3, 0.35], [0.275, 0.3], [0.32, 0.3]];
    let inside = false;
    for (let i = 0, j = cursor.length - 1; i < cursor.length; j = i++) {
      const [xi, yi] = cursor[i]!, [xj, yj] = cursor[j]!;
      if ((yi! > py) !== (yj! > py) && px < ((xj! - xi!) * (py - yi!)) / (yj! - yi!) + xi!) inside = !inside;
    }
    if (inside) return 1;
    const windows = [[0.14, 0.13], [0.0, 0.0], [-0.14, -0.13]] as const;        // da frente para tras
    for (let w = 0; w < windows.length; w++) {
      const [cx, cy] = windows[w]!;
      const d = box(px, py, cx, cy, 0.25, 0.17, 0.025);
      if (d <= 0) {
        if (d > -0.008) return 0.9;                                           // borda
        if (py < cy - 0.115) return 0.62 - w * 0.08;                          // barra de titulo
        const row = (py - (cy - 0.08)) / 0.045;
        const ln = Math.floor(row), within = row - ln;
        const width = [0.36, 0.28, 0.4, 0.22, 0.32][((ln % 5) + 5) % 5]!;
        if (w === 0 && ln >= 0 && ln < 5 && within < 0.45 && px > cx - 0.2 && px < cx - 0.2 + width) return 0.55;
        return 0.1 + w * 0.05 + (cy + 0.17 - py) * 0.25;                     // corpo com luz de cima
      }
      if (w < windows.length - 1) {
        const shadow = box(px - 0.02, py - 0.03, cx, cy, 0.25, 0.17, 0.04);
        if (shadow < 0.05 && shadow > -0.5) return Math.max(0.05, 0.42 * (1 - smooth(-0.01, 0.05, shadow)));
      }
    }
    return glow(Math.hypot(px, py), 0.08, 0.12);
  },

  CODE: (px, py) => {
    // Estrutura de sintaxe: chaves grossas com volume e linhas de codigo em tokens, com recuo
    const brace = (side: number) => {
      const x = px * side;
      const bx = -0.36 + 0.05 * Math.cos(py * 9) * smooth(0.04, 0, Math.abs(py)) - 0.06 * smooth(0.05, 0, Math.abs(py));
      const along = Math.abs(py) < 0.32;
      const d = Math.abs(x - bx);
      const cap = Math.min(segment(x, py, bx, -0.32, bx + 0.08, -0.38), segment(x, py, bx, 0.32, bx + 0.08, 0.38));
      return Math.min(along ? d : 1, cap);
    };
    const bd = Math.min(brace(1), brace(-1));
    if (bd < 0.022) return clamp01(0.95 - bd * 18 + (py + 0.4) * 0.1);
    const row = (py + 0.3) / 0.075;
    const ln = Math.floor(row), within = row - ln;
    if (ln >= 0 && ln < 8 && within > 0.2 && within < 0.62) {
      const indent = [0, 1, 2, 2, 1, 2, 1, 0][ln]! * 0.06;
      const tokens = [[0.08, 0.14, 0.2], [0.1, 0.06, 0.22], [0.16, 0.12], [0.07, 0.2, 0.05], [0.12], [0.18, 0.08, 0.1], [0.09, 0.15], [0.05]][ln]!;
      let x = -0.26 + indent;
      for (let t = 0; t < tokens.length; t++) {
        if (px >= x && px < x + tokens[t]!) return [0.92, 0.5, 0.72][t % 3]!;
        x += tokens[t]! + 0.025;
      }
    }
    return glow(Math.hypot(px, py + 0.02), 0.09, 0.16);
  },

  DATA: (px, py) => {
    // Relevo de dados: cristas empilhadas (as da frente escondem as de tras), cada uma com picos proprios
    const rows = 13;
    for (let k = rows - 1; k >= 0; k--) {
      const base = -0.3 + (k / (rows - 1)) * 0.62;
      const center = Math.sin(k * 1.7) * 0.18;
      const h = 0.2 * Math.exp(-((px - center) ** 2) / 0.02) + 0.08 * Math.exp(-((px + 0.3 - k * 0.03) ** 2) / 0.006)
        + 0.015 * Math.sin(px * 40 + k);
      const curve = base - h * (0.4 + 0.6 * Math.sin((k / rows) * Math.PI));
      if (Math.abs(py - curve) < 0.007) return 0.95 - (rows - 1 - k) * 0.02;
      if (py > curve && py < base + 0.03) return 0.06 + 0.18 * smooth(0.12, 0, py - curve) * (k / rows);
    }
    return 0;
  },

  FILE: (px, py) => {
    // Folhas empilhadas em leque, girando em torno do canto de baixo, com dobra no canto e linhas de texto
    for (let s = 0; s < 4; s++) {                                           // da frente (0) para tras
      const a = -0.08 + s * 0.2;
      const c = Math.cos(a), sn = Math.sin(a);
      const ox = px + 0.18, oy = py - 0.32;
      const x = ox * c + oy * sn - 0.18 + s * 0.015, y = -ox * sn + oy * c + 0.32;
      const d = box(x, y, 0, 0, 0.21, 0.29, 0.012);
      if (d <= 0) {
        if (d > -0.007) return 0.88;
        const fold = x - 0.21 + 0.09 - (y + 0.29);
        if (fold > -0.0 && y < -0.2) return fold < 0.012 ? 0.9 : 0.6;
        if (s === 0) {
          const row = (y + 0.18) / 0.055;
          const ln = Math.floor(row);
          const width = [0.3, 0.26, 0.32, 0.18, 0.28, 0.22, 0.3, 0.12][((ln % 8) + 8) % 8]!;
          if (ln >= 0 && ln < 8 && row - ln < 0.42 && x > -0.15 && x < -0.15 + width) return ln === 0 ? 0.9 : 0.68;
        }
        return 0.2 + s * 0.12 + (y + 0.29) * 0.22;
      }
      const shadow = box(x - 0.015, y - 0.02, 0, 0, 0.21, 0.29, 0.03);
      if (shadow < 0.035 && s < 3) return 0.35 * (1 - smooth(-0.01, 0.035, shadow));
    }
    return glow(Math.hypot(px + 0.05, py - 0.05), 0.1, 0.1);
  },

  EXTCODE: (px, py) => {
    // Terminal: janela, prompt e cursor brilhando, linhas de saida e varredura de tela
    const d = box(px, py, 0, 0.02, 0.42, 0.3, 0.03);
    if (d > 0) return glow(d, 0.01, 0.35);
    if (d > -0.008) return 0.85;
    if (py < -0.22) {
      for (let k = 0; k < 3; k++) if (Math.hypot(px + 0.36 - k * 0.05, py + 0.25) < 0.014) return 0.95;
      return 0.32;
    }
    if (py > -0.22 && py < -0.214) return 0.6;
    const scan = Math.floor((py + 0.5) * ROWS) % 2 === 0 ? 0.06 : 0;
    const chevron = Math.min(segment(px, py, -0.32, -0.13, -0.24, -0.08), segment(px, py, -0.24, -0.08, -0.32, -0.03));
    if (chevron < 0.016) return 1;
    if (py > -0.11 && py < -0.06 && px > -0.2 && px < 0.12) return 0.82;                       // comando
    if (py > 0.13 && py < 0.2 && px > -0.32 && px < -0.25) return 1;                            // cursor
    for (const [y0, w] of [[0.0, 0.5], [0.05, 0.36], [0.1, 0.44]] as const) {
      if (py > y0 - 0.012 && py < y0 + 0.012 && px > -0.32 && px < -0.32 + w) return 0.48;
    }
    return 0.14 + scan + glow(Math.hypot(px + 0.2, py - 0.05), 0.06, 0.12);
  },
};

/** Grao do papel: pontos claros esparsos no fundo inteiro */
const PAPER = 0.07;

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);

/** Grade de tons (0 = papel, 1..3 = tinta clara, media, cheia) da ilustracao de um agente. */
export function halftone(agent: Agent): Uint8Array {
  const field = FIELDS[agent];
  const out = new Uint8Array(COLS * ROWS);
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const px = ((i + 0.5) / COLS - 0.5) * ASPECT, py = (j + 0.5) / ROWS - 0.5;
      const v = clamp01(Math.max(field(px, py), PAPER)) * 3;
      const level = Math.floor(v), frac = v - level;
      out[j * COLS + i] = Math.min(3, level + (frac > BAYER[(j % 4) * 4 + (i % 4)]! ? 1 : 0));
    }
  }
  return out;
}

/** Desenha a grade num canvas: cada tom com uma cor e um tamanho de ponto (pontos menores nos tons claros). */
export function paint(ctx: CanvasRenderingContext2D, grid: Uint8Array, ramp: readonly [string, string, string]) {
  ctx.clearRect(0, 0, COLS * CELL, ROWS * CELL);
  const sizes = [0, 1.6, 2.2, 2.7];
  for (let level = 1; level <= 3; level++) {
    ctx.fillStyle = ramp[level - 1]!;
    const s = sizes[level]!, off = (CELL - s) / 2;
    for (let k = 0; k < grid.length; k++) {
      if (grid[k] === level) ctx.fillRect((k % COLS) * CELL + off, Math.floor(k / COLS) * CELL + off, s, s);
    }
  }
}
