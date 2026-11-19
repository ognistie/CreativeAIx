// Cenas dos papeis de parede gerativos. Cada cena e um campo de luz f(u, v) -> 0..1 (0 = base da paleta,
// 1 = luz/destaque) desenhado com formas simples: discos, elipses, triangulos, curvas e ruido. Os estilos
// (dithering e halftone em generative.ts) transformam a mesma cena em pixels ou pontos.
// Coordenadas: u de 0 a A (A = largura/altura da janela), v de 0 (topo) a 1 (base). Composicao pensada para
// telas largas, com o assunto principal fora do centro (onde fica o conteudo do app).

export type SceneId =
  | "retro" | "aquario" | "gatinhos" | "frutas" | "rio" | "texas"
  | "noite" | "jardim" | "bosque" | "lago" | "praia";

export const SCENES: ReadonlyArray<{ id: SceneId; label: string }> = [
  { id: "retro", label: "Synthwave" },
  { id: "aquario", label: "Aquário" },
  { id: "gatinhos", label: "Gatinhos" },
  { id: "frutas", label: "Frutas" },
  { id: "rio", label: "Rio de Janeiro" },
  { id: "texas", label: "Velho Oeste" },
  { id: "noite", label: "Noite estrelada" },
  { id: "jardim", label: "Jardim" },
  { id: "bosque", label: "Bosque" },
  { id: "lago", label: "Lago" },
  { id: "praia", label: "Praia" },
];
export const SCENE_IDS = SCENES.map((s) => s.id);

// ── Ferramentas ─────────────────────────────────────────────────────────────────────────────────
export const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const smooth = (a: number, b: number, v: number) => { const t = clamp01((v - a) / (b - a)); return t * t * (3 - 2 * t); };
export const hash = (x: number, y: number) => { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); };
function noise1(x: number) { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return hash(i, 0) * (1 - u) + hash(i + 1, 0) * u; }
export const fbm = (x: number) => noise1(x) * 0.55 + noise1(x * 2.1 + 7) * 0.3 + noise1(x * 4.3 + 13) * 0.15;
function noise2(x: number, y: number) {
  const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j;
  const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
  const a = hash(i, j), b = hash(i + 1, j), c = hash(i, j + 1), d = hash(i + 1, j + 1);
  return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
}
/** dentro de um disco (com borda suave de ~2 px) */
const disc = (u: number, v: number, cx: number, cy: number, r: number) => 1 - smooth(r - 0.003, r + 0.003, Math.hypot(u - cx, v - cy));
const ellipse = (u: number, v: number, cx: number, cy: number, rx: number, ry: number) => Math.hypot((u - cx) / rx, (v - cy) / ry) < 1;
function tri(u: number, v: number, ax: number, ay: number, bx: number, by: number, cx: number, cy: number) {
  const s1 = (bx - ax) * (v - ay) - (by - ay) * (u - ax), s2 = (cx - bx) * (v - by) - (cy - by) * (u - bx), s3 = (ax - cx) * (v - cy) - (ay - cy) * (u - cx);
  return (s1 >= 0 && s2 >= 0 && s3 >= 0) || (s1 <= 0 && s2 <= 0 && s3 <= 0);
}
function seg(u: number, v: number, ax: number, ay: number, bx: number, by: number) {
  const vx = bx - ax, vy = by - ay, t = clamp01(((u - ax) * vx + (v - ay) * vy) / (vx * vx + vy * vy || 1));
  return Math.hypot(u - ax - vx * t, v - ay - vy * t);
}

// ── Regioes de cor ──────────────────────────────────────────────────────────────────────────────
/** Cada parte da cena tem a sua rampa de cor (generative.ts): 0 fundo/ceu, 1 chao/agua, 2 assunto, 3 luzes. */
export type Zone = 0 | 1 | 2 | 3;
let zone: Zone = 0;
/** marca a regiao do ponto e devolve a luz (as cenas sao sincronas: a marca vale so para esta amostra) */
const z = (region: Zone, value: number) => { zone = region; return value; };

// ── Cenas ───────────────────────────────────────────────────────────────────────────────────────
type Scene = (u: number, v: number, A: number) => number;

// ── Cenas-piloto (motor 2): camadas fundo / meio / frente / atmosfera / brilho, com perspectiva e neblina ──
// Composicao: o assunto fica na direita e nas bordas; a coluna do meio (titulo e caixa de pedido) e area de
// descanso. Cada objeto tem caixa de teste antes do calculo fino (a cena e lida ~1 vez por celula).

/** ruido "cumeeira": picos agudos e vales suaves, para silhuetas de serra */
const ridged = (x: number) => 1 - Math.abs(2 * noise1(x) - 1);
const serra = (x: number) => 0.55 * ridged(x) + 0.3 * ridged(x * 2.13 + 5.1) + 0.15 * noise1(x * 4.7 + 9.3);

const retro: Scene = (u, v, A) => {
  const H = 0.6;                                         // horizonte
  const sunX = 0.86 * A, sunY = 0.37, sunR = 0.155;
  // Chao: grade em perspectiva (linhas finas de largura constante na tela), neblina pela distancia e o reflexo
  // do sol escorrendo na grade
  if (v > H) {
    const c = 0.07, zd = c / (v - H);                     // profundidade (grande perto do horizonte)
    const fog = Math.exp(-zd * 1.5);
    const fz = zd * 14, rowGap = Math.abs(fz - Math.round(fz)), rowW = 0.0038 * 14 * zd * zd / c;
    const X = (u - A / 2) * zd * 40, colGap = Math.abs(X - Math.round(X)), colW = 0.003 * zd * 40;
    // linhas que ja se juntam (longe) valem pela cobertura media, nao como faixa acesa
    const row = (rowGap < rowW ? 1 - rowGap / rowW : 0) * Math.min(1, 0.3 / rowW);
    const col = (colGap < colW ? 1 - colGap / colW : 0) * Math.min(1, 0.3 / colW);
    const line = Math.max(row, col);
    // reflexo: faixa estreita e partida sob o sol, sumindo para perto (nao invade a caixa de pedido)
    const spread = 0.012 + 0.06 * (v - H);
    const refl = Math.exp(-(((u - sunX) / spread) ** 2)) * (Math.sin((v - H) * 300) > 0.3 ? 1 : 0) * 0.42 * (1 - (v - H) / (1 - H)) ** 2.2;
    if (refl > 0.16 && line < 0.5) return z(3, 0.28 + refl);
    return z(1, 0.05 + 0.06 * fog + line * (0.25 + 0.55 * fog));
  }
  // Serras: perto (escura, contorno aceso) na frente da de longe (mais clara, nevoa); contorno mais forte do
  // lado do sol
  const nearTop = H - 0.01 - 0.11 * serra(u * 6.5 + 11) ** 1.4 * (0.25 + 0.75 * Math.min(1, Math.abs(u - A * 0.55) / (0.45 * A)));
  if (v > nearTop) {
    const rim = Math.exp(-(v - nearTop) / 0.005) * (0.3 + 0.5 * Math.exp(-Math.abs(u - sunX) / (0.5 * A)));
    return z(2, 0.13 + rim + 0.06 * (((v - nearTop) * 70) % 1 < 0.12 ? 1 : 0));
  }
  const farTop = H - 0.035 - 0.2 * serra(u * 4.2 + 3) ** 1.6;
  if (v > farTop) {
    const rim = Math.exp(-(v - farTop) / 0.007) * 0.42;
    const haze = (v - farTop) / (H - farTop + 1e-6);
    return z(2, 0.26 + rim + 0.12 * haze + 0.06 * (((v - farTop) * 55) % 1 < 0.1 ? 1 : 0));
  }
  // Sol: degrade de cima (quase branco) para baixo, fatias horizontais que engrossam para baixo
  const dx = u - sunX, dy = v - sunY, d = Math.hypot(dx, dy);
  if (d < sunR) {
    const t = (dy / sunR + 1) / 2;                        // 0 topo .. 1 base
    if (t > 0.48) {
      const k = (t - 0.48) / 0.52, band = ((k * 5.5) % 1);
      if (band < 0.12 + k * 0.45) return Math.min(0.3, 0.06 + 0.36 * (v / H) ** 1.7);   // fresta: ceu por tras
    }
    return z(3, 0.98 - 0.22 * t);
  }
  // Ceu: degrade para o horizonte, neblina quente na linha do horizonte, halo do sol e estrelas so no alto
  let s = 0.04 + 0.3 * (v / H) ** 1.8 + 0.14 * Math.exp(-(((v - H + 0.015) / 0.035) ** 2));
  s += 0.42 * Math.exp(-(d - sunR) / 0.045) + 0.12 * Math.exp(-(d - sunR) / 0.18);
  if (v < 0.42 && d > sunR + 0.05) {
    const gx = Math.floor(u * 170), gy = Math.floor(v * 170), h = hash(gx, gy);
    if (h > 0.9935) return z(3, Math.max(s, 0.6 + 0.4 * hash(gx + 7, gy + 3)));
  }
  return s;
};

/** Peixe de perfil: corpo afilado, cauda bifurcada, nadadeira dorsal, olho, guelra e listras; luz de cima. */
function fish(u: number, v: number, cx: number, cy: number, s: number, dir: number, tilt: number): number {
  if (Math.abs(u - cx) > s * 1.6 || Math.abs(v - cy) > s * 0.75) return -1;
  const ca = Math.cos(tilt), sa = Math.sin(tilt);
  const lx = (u - cx) * dir, ly = v - cy;
  const x = (lx * ca + ly * sa) / s, y = (-lx * sa + ly * ca) / s;      // coordenadas do peixe (cabeca em +1)
  if (x > -1 && x < 1) {
    const half = 0.34 * Math.sqrt(1 - x * x) * (1 + 0.28 * x) * (x < -0.6 ? 0.75 + 0.6 * (x + 1) : 1);
    if (Math.abs(y) < half) {
      if (Math.hypot(x - 0.66, y + 0.07) < 0.075) return Math.hypot(x - 0.68, y + 0.09) < 0.025 ? 0.95 : 0.03;   // olho com brilho
      if (Math.abs(x - 0.42) < 0.02 && Math.abs(y) < half * 0.75) return 0.3;                                   // guelra
      const top = 1 - (y + half) / (2 * half);            // 1 no dorso (luz), 0 na barriga
      const stripe = x < 0.38 && x > -0.7 && Math.sin(x * 15 + 0.6) > 0.55 ? 0.2 : 0;
      return 0.5 + 0.38 * top - stripe;
    }
    // nadadeira dorsal (em cima) e ventral (pequena)
    if (x > -0.4 && x < 0.5 && y < 0 && y > -half - 0.2 * (1 - Math.abs(x - 0.05) / 0.45) && Math.sin(x * 60) > -0.6) return 0.62;
    if (x > -0.2 && x < 0.15 && y > half && y < half + 0.1 * (1 - Math.abs(x + 0.02) / 0.17)) return 0.5;
  }
  // cauda bifurcada
  if (x < -0.85 && x > -1.5) {
    const k = -x - 0.85, w = k * 0.8;
    if (Math.abs(y) < w && Math.abs(y) > (k - 0.38) * 1.1 && Math.sin(Math.atan2(y, x) * 40) > -0.5) return 0.58 + 0.15 * (1 - k);
  }
  return -1;
}

const aquario: Scene = (u, v, A) => {
  const floor = 0.86 + 0.035 * Math.sin(u * 2.3 + 1) + 0.012 * Math.sin(u * 9);
  // Fundo: areia com causticas (rede de luz), pedras com topo iluminado
  if (v > floor) {
    for (const [rx, ry, rw, rh] of [[0.07, 0.9, 0.09, 0.05], [0.95, 0.88, 0.12, 0.07], [0.6, 0.93, 0.05, 0.025]] as const) {
      const ex = (u - rx * A) / rw, ey = (v - ry) / rh;
      if (ex * ex + ey * ey < 1) return z(1, 0.18 + 0.32 * Math.max(0, -ey) + 0.06 * noise2(u * 80, v * 80));
    }
    const ca = Math.abs(Math.sin(u * 34 + Math.sin(v * 28) * 1.6) * Math.sin(v * 52 + Math.sin(u * 19) * 1.4));
    return z(1, 0.26 + 0.3 * ca ** 3 + 0.08 * noise2(u * 120, v * 120) - 0.12 * (v - floor) * 4);
  }
  // Algas nas laterais (nunca no centro), ondulando mais na ponta
  for (let k = 0; k < 7; k++) {
    const side = k < 4 ? 0.03 + k * 0.055 : 0.84 + (k - 4) * 0.055;
    const bx = side * A, base = 0.88, top = 0.36 + 0.2 * hash(k, 9);
    if (v < top || u < bx - 0.08 || u > bx + 0.08) continue;
    const t = (base - v) / (base - top);
    const cxk = bx + 0.035 * Math.sin(v * 8 + k * 1.7) * t;
    const w = 0.009 * (1 - t * 0.7) + 0.004;
    if (Math.abs(u - cxk) < w) return z(1, 0.36 + 0.14 * Math.sin(v * 70 + k) + 0.12 * (u < cxk ? 1 : 0));
    // folhas alternadas
    const lt = (v * 26 + k) % 1;
    if (lt < 0.5 && Math.abs(u - cxk - (k % 2 ? 1 : -1) * lt * 0.05) < 0.004 && t > 0.15) return z(1, 0.42);
  }
  // Peixes: o principal a direita, dois menores e um cardume ao fundo (mais apagado pela agua)
  for (const [fx, fy, s, dir, tilt] of [[0.83, 0.25, 0.125, -1, -0.06], [0.66, 0.66, 0.058, 1, 0.05], [0.25, 0.58, 0.05, -1, 0.1], [0.5, 0.8, 0.034, 1, -0.04]] as const) {
    const f = fish(u, v, fx * A, fy, s, dir, tilt);
    if (f >= 0) return f < 0.06 ? z(0, f) : f > 0.9 ? z(3, f) : z(2, f);
  }
  if (u > 0.55 * A && u < 0.8 * A && v < 0.24 && v > 0.04) {
    for (let k = 0; k < 13; k++) {
      const a = k * 0.47, fx = 0.66 * A + Math.cos(a) * (0.07 + 0.012 * k), fy = 0.13 + Math.sin(a * 1.3) * 0.05;
      const f = fish(u, v, fx, fy, 0.017, -1, 0.1 * Math.sin(k));
      if (f >= 0) return z(0, 0.18 + f * 0.25);
    }
  }
  // Bolhas subindo em tres colunas (crescem na subida): anel com brilho
  for (const [bx0, phase] of [[0.12, 0], [0.88, 0.3], [0.7, 0.6]] as const) {
    if (Math.abs(u - bx0 * A) > 0.05) continue;
    for (let k = 0; k < 10; k++) {
      const by = 0.86 - ((k * 0.085 + phase * 0.085) % 0.85);
      const r = 0.003 + 0.0055 * (1 - by);
      const bx = bx0 * A + 0.01 * Math.sin(by * 24 + bx0 * 9);
      const d = Math.hypot(u - bx, v - by);
      if (d < r + 0.002) {
        if (Math.hypot(u - bx + r * 0.35, v - by + r * 0.35) < r * 0.3) return z(3, 0.98);
        if (d > r - 0.0018) return z(3, 0.82);
        return 0.3;
      }
    }
  }
  // Agua: luz de cima caindo com a profundidade, superficie ondulada, raios inclinados e poeira em suspensao
  const surface = 0.028 + 0.007 * Math.sin(u * 13) + 0.004 * Math.sin(u * 31 + 2);
  if (v < surface) return 0.55 + 0.38 * Math.abs(Math.sin(u * 46 + Math.sin(u * 7) * 2)) ** 3;
  let w = 0.08 + 0.34 * (1 - v) ** 1.6;
  for (const [x0, slope, wid] of [[0.45, 0.22, 0.06], [0.95, 0.3, 0.09], [1.42, 0.16, 0.05], [1.7, 0.26, 0.04]] as const) {
    const dist = Math.abs(u - (x0 * A / 1.78 + v * slope));
    if (dist < wid * 3) w += 0.3 * Math.exp(-((dist / wid) ** 2)) * (1 - v) ** 1.2 * (0.55 + 0.45 * noise1(v * 9 + x0 * 5));
  }
  if (hash(Math.floor(u * 260), Math.floor(v * 260)) > 0.996) w += 0.18;
  return w;
};

/** Saguaro: tronco e bracos em capsula, gomos verticais e borda acesa do lado do sol (sunSide = +1 direita). */
function saguaro(u: number, v: number, x: number, base: number, h: number, sunSide: number, seed: number): number {
  const w = 0.016 * (h / 0.3) + 0.004;
  if (u < x - 0.09 * h / 0.3 - w || u > x + 0.09 * h / 0.3 + w || v < base - h - w || v > base + 0.01) return -1;
  const top = base - h;
  const armY1 = top + h * (0.38 + 0.08 * hash(seed, 1)), armY2 = top + h * (0.5 + 0.08 * hash(seed, 2));
  const reach = 0.06 * h / 0.3;
  const parts: Array<[number, number, number, number, number]> = [
    [x, base, x, top + w, w],                                  // tronco
    [x, armY1, x + reach, armY1 + 0.01, w * 0.8], [x + reach, armY1 + 0.01, x + reach, armY1 - h * 0.28, w * 0.8],
    [x, armY2, x - reach * 0.8, armY2 + 0.01, w * 0.75], [x - reach * 0.8, armY2 + 0.01, x - reach * 0.8, armY2 - h * 0.18, w * 0.75],
  ];
  for (const [ax, ay, bx, by, r] of parts) {
    const d = seg(u, v, ax, ay, bx, by);
    if (d < r) {
      const vertical = Math.abs(bx - ax) < 1e-6;
      const across = vertical ? (u - ax) / r : (v - ay) / r;  // -1..1 atravessando o gomo
      const ribs = 0.05 * Math.cos(across * Math.PI * 2.5);
      const lit = vertical ? across * sunSide : -across;
      return 0.58 + ribs * 1.6 + (lit > 0.4 ? 0.34 * (lit - 0.4) / 0.6 : -0.08 * Math.max(0, -lit));
    }
  }
  return -1;
}

const texas: Scene = (u, v, A) => {
  const H = 0.64;                                          // linha do deserto
  const sunX = 0.78 * A, sunY = 0.5, sunR = 0.12;
  // Frente: saguaros (um grande na direita, um medio a esquerda do centro e um pequeno ao longe)
  for (const [cx, h, seed] of [[0.9, 0.42, 1], [0.37, 0.27, 2], [0.6, 0.1, 3]] as const) {
    const base = cx === 0.6 ? H + 0.04 : 0.95 - (0.42 - h) * 0.3;
    const c = saguaro(u, v, cx * A, base, h, 1, seed);
    if (c >= 0) return z(2, c);
  }
  if (v > H) {
    // Trilha que some no horizonte, sombras compridas dos cactos para a esquerda, pedras e moitas
    const p = (v - H) / (1 - H);
    const roadX = 0.48 * A - 0.55 * p * A * 0.3, half = 0.004 + p * 0.09;
    const fog = 1 - p;
    for (const [cx, base, len] of [[0.9, 0.95, 0.38], [0.37, 0.98, 0.25]] as const) {
      if (Math.abs(v - base + 0.004) < 0.01 * (1 - (cx * A - u) / len * 0.6) && u < cx * A && u > cx * A - len) return z(1, 0.5);
    }
    const shrub = hash(Math.floor(u * 40), Math.floor(v * 40)) > 0.94 && noise2(u * 140, v * 140) > 0.45;
    if (shrub) return z(1, 0.42 + 0.15 * noise2(u * 300, v * 300));
    if (Math.abs(u - roadX) < half) {
      const rut = Math.abs(Math.abs(u - roadX) / half - 0.55) < 0.1;
      return z(1, 0.3 + (rut ? 0.14 : 0) + 0.05 * noise2(u * 200, v * 200));
    }
    const dunes = Math.sin(u * 9 + v * 30 + Math.sin(u * 3) * 2) > 0.85 ? 0.06 : 0;
    return z(1, 0.13 + 0.07 * fog + dunes + 0.08 * noise2(u * 90, v * 90));
  }
  // Meio: mesas de topo reto com penhasco, estratos e talude; lado do sol aceso, outro na sombra
  for (const [cx, topY, halfTop] of [[0.14, H - 0.2, 0.085], [0.5, H - 0.075, 0.045], [0.97, H - 0.25, 0.1]] as const) {
    const x = cx * A;
    if (v < topY || Math.abs(u - x) > halfTop + 0.2) continue;
    const k = (v - topY) / (H - topY);                       // 0 topo .. 1 base
    const halfW = halfTop + 0.02 * k + (k > 0.62 ? (k - 0.62) ** 1.6 * 0.42 : 0);   // penhasco e talude
    if (Math.abs(u - x) < halfW) {
      const lit = u > x ? 1 : 0;
      const strata = ((v - topY) * 46 + noise1(u * 30) * 0.6) % 1 < 0.16 ? -0.08 : 0;
      const cap = v - topY < 0.012 ? 0.1 : 0;
      return z(2, 0.42 + 0.26 * lit + strata + cap + 0.05 * noise2(u * 70, v * 70) - (k > 0.62 ? 0.08 : 0));
    }
  }
  // Fundo: serra distante (cor do ceu, nevoa) e o sol baixo, meio escondido atras dela
  const ridge = H - 0.035 - 0.045 * serra(u * 3.1 + 2);
  if (v > ridge) return z(0, 0.27 + 0.05 * (v - ridge) / (H - ridge));
  const d = Math.hypot(u - sunX, v - sunY);
  if (d < sunR) return z(3, Math.abs(Math.sin(v * 160)) < 0.22 && v > sunY + 0.04 ? 0.62 : 0.96);
  // Ceu quente: degrade, halo do sol e nuvens finas em faixas
  let s = 0.06 + 0.22 * (v / H) ** 2 + 0.38 * Math.exp(-(d - sunR) / 0.06) + 0.1 * Math.exp(-(d - sunR) / 0.25);
  const cloud = Math.abs(v - (0.2 + 0.025 * Math.sin(u * 2.2) + 0.08 * (u / A))) < 0.011 * noise1(u * 4) && u > 0.42 * A;
  if (cloud) s += 0.18;
  return s;
};




/** Esfera iluminada de cima-esquerda: -1 fora; senao luz difusa (0..1) e brilho especular em spec. */
let spec = 0;
function sphere(u: number, v: number, cx: number, cy: number, r: number): number {
  const dx = (u - cx) / r, dy = (v - cy) / r, d2 = dx * dx + dy * dy;
  if (d2 > 1) return -1;
  const nz = Math.sqrt(1 - d2);
  const lam = Math.max(0, -0.48 * dx - 0.56 * dy + 0.67 * nz);
  spec = lam ** 24;
  return lam;
}

/** Gato sentado de perfil 3/4: quadril, peito, cabeca, orelhas, rabo enrolado na frente. -> 0 corpo, 1 borda de luz,
 *  2 olho, -1 fora. rimSide: lado de onde vem a luz (-1 esquerda, 1 direita). */
function cat(u: number, v: number, cx: number, base: number, h: number, dir: number, rimSide: number): number {
  if (Math.abs(u - cx) > h * 0.8 || v < base - h * 1.25 || v > base + 0.01) return -1;
  const x = (u - cx) * dir, y = base - v;                     // y para cima a partir do chao
  const inside = (px: number, py: number) => {
    const hip = ((px + 0.02 * h) / (0.3 * h)) ** 2 + ((py - 0.24 * h) / (0.25 * h)) ** 2 < 1;
    const chest = ((px - 0.07 * h) / (0.19 * h)) ** 2 + ((py - 0.55 * h) / (0.26 * h)) ** 2 < 1;
    const neck = Math.abs(px - 0.1 * h) < 0.1 * h && py > 0.6 * h && py < 0.85 * h;
    const hx = 0.13 * h, hy = 0.92 * h;
    const head = ((px - hx) / (0.17 * h)) ** 2 + ((py - hy) / (0.145 * h)) ** 2 < 1;
    const ear = (ex: number) => tri(px, py, hx + ex - 0.075 * h, hy + 0.08 * h, hx + ex + 0.065 * h, hy + 0.06 * h, hx + ex - 0.01 * h, hy + 0.27 * h);
    const tail = py < 0.08 * h && py > 0 && Math.abs(Math.hypot((px - 0.05 * h) / 1.6, py - 0.04 * h * 0) - 0.21 * h) < 0.05 * h && px > -0.25 * h;
    const paws = py < 0.06 * h && Math.abs(px - 0.12 * h) < 0.1 * h;
    return hip || chest || neck || head || ear(-0.08 * h) || ear(0.08 * h) || tail || paws;
  };
  if (!inside(x, y)) return -1;
  const hx = 0.13 * h, hy = 0.92 * h;
  for (const ex of [0.065, -0.005]) if (((x - hx - ex * h) / (0.03 * h)) ** 2 + ((y - hy - 0.01 * h) / (0.018 * h)) ** 2 < 1) return 2;
  // borda de luz: o ponto um pouco na direcao da luz ja esta fora do gato
  const off = 0.035 * h;
  return !inside(x + rimSide * dir * off, y) || !inside(x, y + off * 0.8) ? 1 : 0;
}

const gatinhos: Scene = (u, v, A) => {
  // Gatos no telhado contra a lua grande; cidade em camadas ao fundo, janelas acesas, telhas em perspectiva
  const moonX = 0.84 * A, moonY = 0.42, moonR = 0.2;
  const roof = 0.7 - 0.06 * clamp01((u - 0.55 * A) / (0.4 * A));     // cumeeira sobe para a direita
  // gatos: dois a direita (um recortado na lua), um menor a esquerda
  for (const [cx, h, dir] of [[0.79, 0.24, -1], [0.9, 0.17, 1], [0.27, 0.12, 1]] as const) {
    const x = cx * A, base = 0.7 - 0.06 * clamp01((x - 0.55 * A) / (0.4 * A));
    const c = cat(u, v, x, base, h, dir, x < moonX ? 1 : -1);
    if (c === 2) return z(3, 0.98);
    if (c === 1) return z(2, 0.85);
    // corpo: escuro contra a lua, mas com pelo visivel (assunto) no ceu escuro
    if (c === 0) return z(0, 0.015);                                       // silhueta escura; o contorno aceso desenha o gato
  }
  if (v > roof) {
    // telhas: fileiras que se apertam para o fundo; cumeeira clara (lua)
    const d = (v - roof) / (1 - roof);
    if (d < 0.025) return z(1, 0.55);
    const rowsY = Math.log(1 + d * 9) * 6, row = rowsY % 1;
    const col = ((u * (14 + 26 * d) + Math.floor(rowsY) * 0.5) % 1);
    const edge = row < 0.12 || col < 0.06;
    return z(1, (edge ? 0.08 : 0.2 + 0.14 * (1 - row)) * (1 - 0.3 * d) + 0.04 * noise2(u * 90, v * 90));
  }
  // cidade ao fundo: duas fileiras de predios, chamines, janelas acesas raras
  for (const [layer, top0, lum] of [[0, 0.5, 0.09], [1, 0.58, 0.04]] as const) {
    const w = 0.045 + 0.02 * layer, i = Math.floor(u / w + layer * 0.5);
    const hgt = top0 - 0.12 * hash(i, 7 + layer) - (hash(i, 9) > 0.8 ? 0.06 : 0);
    if (v > hgt) {
      const lx = (u / w + layer * 0.5) % 1;
      if (hash(i, 3) > 0.6 && lx > 0.6 && lx < 0.75 && v < hgt + 0.03) return z(0, lum + 0.03);       // chamine
      const wx = Math.floor(lx * 4), wy = Math.floor((v - hgt) * 60);
      if (lx > 0.15 && lx < 0.85 && (v - hgt) * 60 % 1 > 0.35 && (lx * 4) % 1 > 0.3 && hash(i * 7 + wx, wy) > 0.965) return z(3, 0.8);
      return z(0, lum + 0.04 * layer);
    }
  }
  const md = Math.hypot(u - moonX, v - moonY);
  if (md < moonR) {
    const crater = noise2(u * 14 + 3, v * 14) > 0.64 ? 0.13 : noise2(u * 40, v * 40) > 0.7 ? 0.06 : 0;
    return z(3, 0.97 - crater - 0.1 * ((u - moonX) / moonR + 1) / 2);
  }
  if (v < 0.45 && hash(Math.floor(u * 160), Math.floor(v * 160)) > 0.994 && md > moonR + 0.06) return z(3, 0.75);
  return 0.05 + 0.2 * (v / roof) ** 2 + 0.4 * Math.exp(-(md - moonR) / 0.04) + 0.1 * Math.exp(-(md - moonR) / 0.2);
};

const frutas: Scene = (u, v, A) => {
  // Natureza-morta: parede com luz de janela, mesa com toalha, fruteira a direita, melancia e cerejas a esquerda
  const table = 0.74;
  // fruteira (tigela) e frutas dentro, com sombra na mesa
  const bx = 0.83 * A, by = table - 0.02;
  const fruitsIn: Array<[number, number, number, number]> = [[0.75, -0.14, 0.095, 0], [0.86, -0.18, 0.11, 1], [0.95, -0.12, 0.08, 2], [0.8, -0.27, 0.08, 3]];
  for (const [fx, fy, r, kind] of fruitsIn) {
    const s = sphere(u, v, fx * A, by + fy, r);
    if (s >= 0) {
      if (spec > 0.55) return z(3, 0.95);
      if (kind === 3 && v < by + fy - r * 0.85 && Math.abs(u - fx * A) < 0.006) return z(1, 0.3);   // cabinho
      const dimple = kind === 0 ? 0.04 * noise2(u * 400, v * 400) : 0;
      return z(2, 0.32 + 0.55 * s + dimple);
    }
  }
  // uvas penduradas da tigela
  for (let k = 0; k < 9; k++) {
    const gx = bx - 0.12 + (k % 3) * 0.022 + (Math.floor(k / 3) % 2) * 0.011, gy = by - 0.02 + Math.floor(k / 3) * 0.02;
    const s = sphere(u, v, gx, gy, 0.013);
    if (s >= 0) return spec > 0.5 ? z(3, 0.9) : z(2, 0.25 + 0.5 * s);
  }
  if (v > by - 0.07 && v < by + 0.035 && Math.abs(u - bx) < 0.19 - (v - by + 0.07) * 0.5) {
    const rim = v < by - 0.06;
    return z(1, rim ? 0.8 : 0.45 + 0.3 * (1 - Math.abs(u - bx) / 0.19) - 0.15 * ((v - by + 0.07) / 0.105));
  }
  // fatia de melancia e cerejas a esquerda (em cima da mesa)
  const mx = 0.3 * A, my = table + 0.005, md = Math.hypot((u - mx) / 1.25, v - my) * 0.8;
  if (v < my && md < 0.1) {
    if (md > 0.09) return z(1, 0.48);
    if (md > 0.082) return z(3, 0.9);
    const seed = [[-0.04, -0.045], [0.0, -0.06], [0.04, -0.045], [-0.02, -0.03], [0.025, -0.03]].some(([sx, sy]) => ellipse(u, v, mx + sx! * 1.25, my + sy!, 0.006, 0.01));
    return seed ? z(0, 0.04) : z(2, 0.6 + 0.25 * (1 - md / 0.082));
  }
  for (const [cx, cy] of [[0.4, table - 0.025], [0.43, table - 0.02]] as const) {
    const s = sphere(u, v, cx * A, cy, 0.022);
    if (s >= 0) return spec > 0.5 ? z(3, 0.95) : z(2, 0.3 + 0.55 * s);
  }
  if (seg(u, v, 0.4 * A, table - 0.045, 0.415 * A, table - 0.1) < 0.002 || seg(u, v, 0.43 * A, table - 0.04, 0.415 * A, table - 0.1) < 0.002) return z(1, 0.35);
  if (v > table) {
    // toalha: barra de listras e dobras; sombras das frutas
    const shadow = Math.hypot((u - bx - 0.06) / 0.2, (v - table - 0.02) / 0.025) < 1 || Math.hypot((u - mx - 0.05) / 0.12, (v - table - 0.012) / 0.015) < 1;
    const stripe = ((u * 6 + Math.sin(v * 9) * 0.2) % 1) < 0.08 ? 0.12 : 0;
    const fold = Math.sin(u * 5 + 1) * 0.06;
    return z(1, (shadow ? 0.08 : 0.2) + stripe + fold + (v < table + 0.006 ? 0.3 : 0));
  }
  // parede: luz da janela entrando pela direita em losango suave, papel de parede discreto
  const light = Math.exp(-(((u - 0.62 * A + (v - 0.4) * 0.5) / 0.3) ** 2)) * 0.18;
  const paper = ((u * 22 + v * 22) % 1 < 0.04 || (u * 22 - v * 22 + 100) % 1 < 0.04) ? 0.04 : 0;
  return 0.06 + 0.1 * (1 - v) + light + paper;
};

const rio: Scene = (u, v, A) => {
  // Por do sol na baia: Corcovado com o Cristo a direita, Pao de Acucar a esquerda com o bondinho, cidade acesa,
  // agua com reflexos e o calcadao de Copacabana em ondas na frente
  const sea = 0.64;
  if (v > 0.88) {
    // calcadao: ondas largas (o desenho da calcada) em duas cores
    const wave = Math.sin(u * 22 + Math.sin(u * 3) * 0.5 - (v - 0.88) * 40) ;
    return z(1, wave > 0.15 ? 0.82 : 0.1);
  }
  if (v > 0.85) return z(1, 0.62 + 0.1 * noise2(u * 80, v * 80));                   // areia
  // Corcovado: pico ingreme a direita, Cristo de bracos abertos aceso
  const cx = 0.86 * A;
  const corc = sea - 0.04 - 0.38 * Math.max(0, 1 - Math.abs(u - cx) / 0.17) ** 1.9 - 0.012 * fbm(u * 14);
  const top = sea - 0.42;
  if ((Math.abs(u - cx) < 0.005 && v > top - 0.06 && v < top + 0.012) || (Math.abs(v - (top - 0.043)) < 0.004 && Math.abs(u - cx) < 0.03)) return z(3, 0.98);
  // Pao de Acucar (cupula alta) e Urca (baixa) a esquerda, com o cabo do bondinho
  const dome = (x0: number, w: number, h: number) => { const t = 1 - ((u - x0 * A) / w) ** 2; return t > 0 ? sea - h * t ** 0.35 : sea; };
  const sugar = Math.min(dome(0.29, 0.07, 0.3), dome(0.2, 0.065, 0.15));
  const cableA = [0.2 * A, sea - 0.15] as const, cableB = [0.29 * A, sea - 0.3] as const;
  if (seg(u, v, cableA[0], cableA[1], cableB[0], cableB[1]) < 0.0012) return z(3, 0.8);
  if (Math.abs(u - (0.245 * A)) < 0.007 && Math.abs(v - (sea - 0.225 + 0.003)) < 0.006) return z(3, 0.92);
  const hills = sea - 0.035 - 0.05 * fbm(u * 3 + 2);
  const land = Math.min(corc, sugar, hills);
  if (v < sea && v > land) {
    const facing = u < cx ? 0.06 : 0;                                       // lado que pega o por do sol
    if (v > sea - 0.03 && hash(Math.floor(u * 160), Math.floor(v * 160)) > 0.8) return z(3, 0.85);   // cidade acesa
    return z(2, 0.12 + facing + 0.06 * noise2(u * 30, v * 30) + (v - land < 0.006 ? 0.25 : 0));
  }
  if (v >= sea) {
    // baia: reflexo do sol e das luzes, ondinhas que se apertam ao longe
    const d = v - sea;
    const glint = Math.exp(-(((u - 0.58 * A) / (0.03 + d * 0.4)) ** 2)) * (Math.sin(d * 400 + u * 30) > 0.4 ? 1 : 0);
    if (glint > 0.4) return z(3, 0.5 + glint * 0.4);
    const boat = [0.48, 0.66].some((bx2, i) => ellipse(u, v, bx2 * A, sea + 0.05 + i * 0.06, 0.018, 0.004));
    if (boat) return z(2, 0.45);
    return z(1, 0.14 + 0.1 * (Math.sin(d * 160 + Math.sin(u * 10)) > 0.75 ? 1 : 0) * (1 - d * 3));
  }
  // ceu ao entardecer: sol baixo entre os morros, faixas de nuvem
  const sd = Math.hypot(u - 0.58 * A, v - (sea - 0.02));
  if (sd < 0.06) return z(3, 0.95);
  const cloud = Math.abs(v - (0.22 + 0.03 * Math.sin(u * 2.5))) < 0.012 * noise1(u * 3 + 1) ? 0.15 : 0;
  return 0.05 + 0.4 * (v / sea) ** 2.2 + 0.4 * Math.exp(-(sd - 0.06) / 0.05) + cloud;
};

const noite: Scene = (u, v, A) => {
  // Ceu em correntes (linhas de fluxo de dois redemoinhos), lua crescente com halos, estrelas com aneis, vila com
  // janelas acesas nas colinas e um cipreste alto em chamas na esquerda
  const hill = 0.73 + 0.045 * Math.sin(u * 2.6 + 1) + 0.02 * fbm(u * 5);
  const cyX = 0.21 * A;
  // cipreste: chama alta com bordas recortadas e pinceladas verticais
  if (v > 0.2 && v < 1) {
    const t = (v - 0.2) / 0.8;
    const half = 0.008 + 0.075 * Math.sin(Math.min(1, t * 1.15) * Math.PI * 0.5) ** 1.4 * (0.82 + 0.18 * noise1(v * 40));
    const sway = 0.025 * Math.sin(v * 9) * (1 - t);
    if (Math.abs(u - cyX - sway) < half) {
      const stroke = Math.sin((u - cyX) * 140 + v * 30 + noise2(u * 30, v * 30) * 3) > 0.35 ? 0.12 : 0;
      return z(1, 0.22 + stroke * 1.6 + (u < cyX + sway - half * 0.6 ? 0.12 : 0));
    }
  }
  if (v > hill) {
    for (let k = 0; k < 9; k++) {                                                          // casas e igreja
      const hx = (0.44 + k * 0.058) * A, w = 0.02 + 0.006 * (k % 2), floor = hill + 0.06 + (k % 3) * 0.012;
      if (k === 4) {                                                                       // torre da igreja
        if (Math.abs(u - hx) < 0.012 && v > hill - 0.07 && v < floor) return z(1, 0.2);
        if (tri(u, v, hx - 0.014, hill - 0.07, hx + 0.014, hill - 0.07, hx, hill - 0.14)) return z(1, 0.16);
      }
      if (Math.abs(u - hx) < w && v > hill + 0.012 && v < floor) {
        const lit = Math.abs(u - hx) < 0.006 && Math.abs(v - (hill + 0.03)) < 0.007 && hash(k, 4) > 0.25;
        return lit ? z(3, 0.95) : z(1, 0.22);
      }
      if (tri(u, v, hx - w - 0.006, hill + 0.014, hx + w + 0.006, hill + 0.014, hx, hill - 0.016)) return z(1, 0.15);
    }
    return z(1, 0.06 + 0.07 * (Math.sin(u * 46 + v * 22 + noise2(u * 9, v * 9) * 2) > 0.65 ? 1 : 0));
  }
  // lua crescente com aneis de halo
  const mx = 0.87 * A, my = 0.16, mdist = Math.hypot(u - mx, v - my);
  const moon = disc(u, v, mx, my, 0.06) * (1 - disc(u, v, mx - 0.028, my - 0.016, 0.056));
  if (moon > 0.5) return z(3, 0.97);
  if (mdist < 0.16 && Math.abs(((mdist - 0.06) * 36) % 1 - 0.5) < 0.12) return z(3, 0.6 - mdist * 2);
  for (let k = 0; k < 9; k++) {
    const sx = (0.32 + 0.6 * hash(k, 9)) * A, sy = 0.06 + 0.4 * hash(k, 4);
    if (Math.abs(sx - 0.55 * A) < 0.25 && sy > 0.24 && sy < 0.46) continue;                // nao em cima do titulo
    const d = Math.hypot(u - sx, v - sy);
    if (d < 0.007) return z(3, 0.98);
    if (Math.abs(d - 0.02) < 0.003) return z(3, 0.62);
  }
  // correntes do ceu: funcao de fluxo de dois redemoinhos + vento; as faixas seguem as linhas de fluxo
  const r1 = Math.hypot(u - 0.56 * A, v - 0.26) + 0.02, r2 = Math.hypot(u - 0.36 * A, v - 0.14) + 0.02;
  const psi = 0.9 * Math.log(r1) - 0.6 * Math.log(r2) + v * 3.2 + 0.3 * noise2(u * 3, v * 3);
  const band = Math.sin(psi * 11);
  return 0.09 + 0.14 * (1 - v) + (band > 0.82 ? 0.46 : band > 0.55 ? 0.24 : band > 0.25 ? 0.1 : 0) * (0.6 + 0.4 * (1 - v));
};

const jardim: Scene = (u, v, A) => {
  // Jardim de dia: cerca-viva ao fundo, canteiros, flores grandes nas bordas (tulipas e margaridas com petalas),
  // borboletas e sol suave; o meio fica com grama baixa
  const ground = 0.86;
  const sunD = Math.hypot(u - 0.88 * A, v - 0.13);
  // flores grandes de primeiro plano (bordas)
  for (const [fx, top, kind, s] of [[0.06, 0.48, 0, 1.3], [0.13, 0.56, 1, 1.1], [0.83, 0.5, 1, 1.4], [0.92, 0.44, 0, 1.25], [0.97, 0.6, 1, 1], [0.75, 0.62, 0, 0.9]] as const) {
    const x = fx * A, sway = 0.012 * Math.sin(v * 8 + fx * 20);
    if (Math.abs(u - x - sway) < 0.004 * s && v > top && v < 1) return z(1, 0.5);                              // caule
    const leafY = top + (ground - top) * 0.55;
    if (ellipse(u, v, x + 0.035 * s, leafY, 0.035 * s, 0.009 * s)) return z(1, Math.abs(v - leafY) < 0.0015 ? 0.75 : 0.58);   // folha com nervura
    if (kind === 0) {
      // tulipa: tres petalas em calice, luz de um lado
      const cx = x, cy = top - 0.03 * s, w = 0.03 * s, h = 0.045 * s;
      if (ellipse(u, v, cx, cy, w, h) && !(v < cy - h * 0.55 && Math.abs(Math.abs(u - cx) - w * 0.35) < w * 0.12)) {
        const side = (u - cx) / w;
        return z(2, 0.55 + 0.3 * (side < -0.2 ? 1 : 0) + 0.15 * (1 - Math.abs(side)));
      }
    } else {
      // margarida: 14 petalas em volta do miolo texturizado
      const cx = x, cy = top - 0.02 * s, d = Math.hypot(u - cx, v - cy), a = Math.atan2(v - cy, u - cx);
      if (d < 0.013 * s) return z(3, 0.55 + 0.35 * hash(Math.floor(u * 500), Math.floor(v * 500)));
      const petal = 0.036 * s * (0.75 + 0.25 * Math.abs(Math.cos(a * 7)));
      if (d < petal && Math.abs(Math.sin(a * 7)) > 0.12) return z(2, 0.9 - 0.25 * (d / petal) ** 2);
    }
  }
  // borboletas (asas com desenho e corpo)
  for (const [bx, by, sz] of [[0.3, 0.2, 1], [0.7, 0.18, 0.8], [0.62, 0.62, 0.7]] as const) {
    const x = bx * A, dx = Math.abs(u - x), dy = v - by;
    if (dx > 0.05 * sz || Math.abs(dy) > 0.04 * sz) continue;
    if (dx < 0.0025 * sz && Math.abs(dy) < 0.022 * sz) return z(1, 0.15);
    const upper = ellipse(dx, dy, 0.022 * sz, -0.011 * sz, 0.021 * sz, 0.016 * sz), lower = ellipse(dx, dy, 0.016 * sz, 0.013 * sz, 0.014 * sz, 0.011 * sz);
    if (upper || lower) return Math.hypot(dx - 0.026 * sz, dy + 0.013 * sz) < 0.006 * sz ? z(3, 0.95) : z(2, upper ? 0.8 : 0.65);
  }
  if (v > ground) return z(1, 0.32 + 0.16 * (Math.abs(Math.sin(u * 120 + Math.sin(u * 7) * 3)) < 0.3 ? 1 : 0) + 0.08 * noise2(u * 60, v * 60));
  // canteiro do meio: grama baixa e algumas flores pequenas (longe, menores)
  if (v > 0.74) {
    const tuft = Math.abs(Math.sin(u * 150 + noise1(u * 20) * 4)) < 0.3 && v > 0.74 + 0.04 * hash(Math.floor(u * 60), 2);
    if (hash(Math.floor(u * 70), Math.floor(v * 70)) > 0.97) return z(2, 0.75);
    return z(1, tuft ? 0.4 : 0.22);
  }
  // cerca-viva ao fundo (arredondada) e arvores distantes
  const hedge = 0.62 + 0.025 * Math.sin(u * 14) + 0.015 * noise1(u * 30);
  if (v > hedge) return z(1, 0.14 + 0.08 * noise2(u * 40, v * 40) + (v - hedge < 0.008 ? 0.12 : 0));
  const trees = 0.5 + 0.06 * fbm(u * 5 + 3);
  if (v > trees) return z(0, 0.16 + 0.05 * noise2(u * 20, v * 20));
  if (sunD < 0.06) return z(3, 0.9);
  return 0.06 + 0.16 * (v / 0.6) + 0.35 * Math.exp(-(sunD - 0.06) / 0.05);
};

const bosque: Scene = (u, v, A) => {
  // Floresta de pinheiros em camadas que somem na nevoa; troncos grandes emoldurando as bordas; raios de luz de
  // cima a direita; samambaias no chao
  const rays = Math.max(0, Math.sin((u - v * 0.45) * 8 + 1)) ** 10 * 0.28 * (1 - v) * (u > 0.4 * A ? 1 : 0.4);
  // troncos de primeiro plano nas bordas (casca com sulcos, borda iluminada do lado da luz)
  for (const [tx, w] of [[0.05, 0.05], [0.95, 0.06], [0.84, 0.03]] as const) {
    const x = tx * A + 0.01 * Math.sin(v * 3);
    if (Math.abs(u - x) < w) {
      const across = (u - x) / w;
      const groove = Math.sin(across * 9 + noise2(u * 20, v * 6) * 3) > 0.6 ? -0.05 : 0;
      return z(2, 0.08 + groove + (across > 0.6 ? 0.22 : 0));
    }
  }
  // samambaias no chao (frente)
  if (v > 0.86) {
    const frond = Math.abs(Math.sin(u * 60 + Math.sin(u * 7) * 2) * Math.cos(v * 90)) > 0.6;
    return z(1, frond ? 0.32 : 0.08 + 0.06 * noise2(u * 70, v * 70));
  }
  // camadas de pinheiros: de tras (claro, nevoa) para a frente (escuro, nitido)
  for (let layer = 3; layer >= 0; layer--) {
    const spacing = 0.07 + layer * 0.025, base = 0.6 + layer * 0.085;
    const i = Math.floor(u / spacing + layer * 0.37), cx = (i + 0.5 - layer * 0.37) * spacing + 0.02 * (hash(i, layer) - 0.5);
    if (layer <= 1 && Math.abs(cx - 0.55 * A) < 0.28 && hash(i, 33) > 0.35) continue;       // clareira no meio
    const h = (0.26 + 0.24 * hash(i, layer + 7)) * (0.8 + layer * 0.15);
    const top = base - h, rel = (v - top) / h;
    if (rel > 0 && rel < 1.05) {
      const tier = (rel * 5) % 1;                                                           // galhos em niveis
      const jag = 0.85 + 0.15 * noise1(v * 120 + i);
      const half = spacing * 0.48 * (0.2 + 0.8 * tier ** 0.7) * (0.25 + 0.75 * rel) * jag;
      const fog = [0.5, 0.36, 0.22, 0.09][layer]!;
      if (Math.abs(u - cx) < half) return z(layer >= 2 ? 0 : 1, fog + (u < cx ? 0.05 : 0) + (tier > 0.85 ? 0.04 : 0));
      if (Math.abs(u - cx) < 0.004 + layer * 0.001 && rel > 0.9) return z(1, fog * 0.8);
    }
  }
  return 0.25 + 0.35 * (1 - v) + rays;
};

const lago: Scene = (u, v, A) => {
  // Lago de montanha a noite: duas serras (neve no alto, lado da lua aceso), linha de pinheiros na margem,
  // reflexo ondulado com trilha de brilho da lua, juncos nas bordas
  const water = 0.62;
  const moonX = 0.82 * A, moonY = 0.16;
  // juncos e taboas nas bordas da frente
  for (const [rx, h, k] of [[0.04, 0.3, 0], [0.07, 0.36, 1], [0.1, 0.24, 2], [0.93, 0.3, 3], [0.96, 0.22, 4], [0.98, 0.34, 5]] as const) {
    const x = rx * A, foot = 1.0, topY = foot - h;
    const bend = 0.025 * ((v - foot) / h) ** 2 * (k % 2 ? 1 : -1);
    if (Math.abs(u - x - bend) < 0.003 && v > topY && v < foot) return z(2, 0.04);
    if (k % 2 === 0 && ellipse(u, v, x + 0.025 * (k % 2 ? 1 : -1) * 0, topY + 0.02, 0.006, 0.028)) return z(2, 0.12);
  }
  const look = (vv: number, mirror: boolean) => {
    // serra de tras (neve) e da frente (escura), pelo ruido cumeeira
    const back = water - 0.07 - 0.3 * serra(u * 2.4 + 4) ** 1.5;
    const front = water - 0.02 - 0.12 * serra(u * 4.6 + 9) ** 1.3;
    if (vv > water - 0.02 - 0.03 * noise1(u * 60) && !mirror) return z(1, 0.04);               // pinheiros da margem
    if (vv > front) return z(2, 0.12 + 0.05 * noise2(u * 40, vv * 40));
    if (vv > back) {
      const depth = vv - back;
      const lit = (u - moonX) < 0 ? 0 : 0.1;
      const snow = depth < 0.075 + 0.03 * noise1(u * 30) ? 0.72 + lit : 0;
      return z(2, (snow || 0.2 + lit * 0.6) + 0.06 * (Math.abs((u * 12 - vv * 5) % 1) < 0.1 ? 1 : 0));
    }
    const md = Math.hypot(u - moonX, vv - moonY);
    if (md < 0.06) return z(3, 0.96 - (noise2(u * 50, vv * 50) > 0.7 ? 0.1 : 0));
    return z(0, 0.06 + 0.26 * (vv / water) ** 2 + 0.4 * Math.exp(-(md - 0.06) / 0.04));
  };
  if (v < water) return look(v, false);
  // agua: reflexo espelhado ondulado e mais escuro; trilha de brilho da lua
  const d = v - water;
  const trail = Math.exp(-(((u - moonX) / (0.02 + d * 0.25)) ** 2)) * (Math.sin(d * 300 + u * 40) > 0.3 ? 1 : 0);
  if (trail > 0.45) return z(3, 0.55 + trail * 0.4);
  const mirror = water - d * 1.05 + 0.006 * Math.sin(v * 180 + u * 7);
  const reflected = look(mirror, true);
  const ripple = Math.abs(Math.sin(v * 240 + Math.sin(u * 6))) < 0.1 ? 0.06 : 0;
  return z(1, clamp01(reflected * 0.6 + ripple));
};

const praia: Scene = (u, v, A) => {
  // Praia de dia: sol a direita, mar com ondas em perspectiva e espuma, areia molhada que reflete, coqueiro grande
  // na direita, guarda-sol e cadeira na esquerda, gaivotas
  const sea = 0.52;
  const shore = 0.72 + 0.025 * Math.sin(u * 4.5) + 0.01 * Math.sin(u * 13);
  // coqueiro: tronco curvo com aneis, copa de folhas arqueadas com foliolos
  const px = 0.9 * A;
  const trunkX = (y: number) => px - 0.12 * ((1 - y) / 0.75) ** 1.6;
  if (v > 0.25 && v < 0.98) {
    const w = 0.009 + (v - 0.25) * 0.012;
    if (Math.abs(u - trunkX(v)) < w) return z(2, 0.42 + (Math.sin(v * 140) > 0.55 ? -0.12 : 0) + ((u - trunkX(v)) / w > 0.4 ? 0.2 : 0));
  }
  const crX = trunkX(0.25), crY = 0.25;
  for (let k = 0; k < 9; k++) {
    const a = -Math.PI * 0.95 + (k / 8) * Math.PI * 1.25;
    const len = 0.16 + 0.03 * hash(k, 2);
    for (let t = 0.05; t <= 1; t += 0.04) {
      const fx = crX + Math.cos(a) * len * t, fy = crY + Math.sin(a) * len * t * 0.5 + t * t * 0.09;
      const dd = Math.hypot(u - fx, v - fy);
      if (dd < 0.004) return z(2, 0.3);                                                    // nervura
      const leaflet = 0.022 * (1 - t * 0.7);
      if (dd < leaflet && Math.sin((u - fx) * 900 + (v - fy) * 900) > -0.2) return z(2, 0.55 + 0.25 * t);
    }
  }
  if (sphere(u, v, crX, crY + 0.012, 0.012) >= 0) return z(1, 0.3);                       // cocos
  // guarda-sol listrado e cadeira (esquerda, depois da barra lateral)
  const um = 0.28 * A, top = 0.56;
  if (Math.abs(u - um - (v - top) * 0.08) < 0.0035 && v > top && v < shore + 0.12) return z(2, 0.3);
  if (v < top + 0.035 && v > top - 0.05 && Math.hypot((u - um) / 1.4, (v - top - 0.035) * 1.8) < 0.08) {
    return Math.floor((Math.atan2(v - top - 0.035, u - um) + Math.PI) * 5) % 2 ? z(3, 0.9) : z(2, 0.62);
  }
  if (seg(u, v, um + 0.04, shore + 0.1, um + 0.09, shore + 0.06) < 0.004 || seg(u, v, um + 0.06, shore + 0.1, um + 0.04, shore + 0.05) < 0.003) return z(2, 0.5);
  // gaivotas (dois arcos)
  for (const [gx, gy] of [[0.58, 0.16], [0.63, 0.12], [0.7, 0.19]] as const) {
    const dx = u - gx * A, dy = v - gy;
    if (Math.abs(dx) < 0.02 && Math.abs(dy - 0.25 * Math.abs(dx) * (1 - Math.abs(dx) / 0.02) * 2 + 0.004) < 0.0025) return z(2, 0.2);
  }
  if (v > shore) {
    const wet = v < shore + 0.05;
    const shell = [0.46, 0.6, 0.7].some((sx, i) => ellipse(u, v, sx * A, 0.9 + i * 0.025, 0.012, 0.007));
    if (shell) return z(3, 0.85);
    return z(1, (wet ? 0.3 + 0.2 * Math.exp(-(((u - 0.82 * A) / 0.08) ** 2)) : 0.46) + 0.1 * noise2(u * 70, v * 70));
  }
  if (v > sea) {
    // mar: faixas de onda que se apertam para o horizonte, espuma na arrebentacao e na beira
    const d = (v - sea) / (shore - sea);
    const wave = Math.sin(1 / (d + 0.08) * 6 + Math.sin(u * 6) * 0.8);
    const foam = v > shore - 0.012 || (wave > 0.9 && d > 0.4);
    if (foam) return z(3, 0.85);
    const glint = Math.exp(-(((u - 0.82 * A) / (0.02 + d * 0.15)) ** 2)) * (Math.sin(v * 380 + u * 50) > 0.5 ? 1 : 0);
    if (glint > 0.5) return z(3, 0.7);
    return z(0, 0.38 + 0.2 * d + (wave > 0.6 ? 0.12 : 0));
  }
  const sunD = Math.hypot(u - 0.82 * A, v - 0.27);
  if (sunD < 0.07) return z(3, 0.95);
  const cloud = Math.abs(v - (0.14 + 0.02 * Math.sin(u * 3))) < 0.014 * noise1(u * 4 + 7) && u < 0.7 * A ? 0.12 : 0;
  return 0.05 + 0.2 * (v / sea) ** 2 + 0.35 * Math.exp(-(sunD - 0.07) / 0.05) + cloud;
};

export const SCENE_FIELDS: Record<SceneId, Scene> = { retro, aquario, gatinhos, frutas, rio, texas, noite, jardim, bosque, lago, praia };

/** Luz e regiao da cena em (x, y) normalizados 0..1, para uma janela de proporcao `aspect`. */
export function sceneSample(id: SceneId, x: number, y: number, aspect = 16 / 9): { v: number; zone: Zone } {
  zone = 0;
  const v = clamp01(SCENE_FIELDS[id](x * aspect, y, aspect));
  return { v, zone: zone === 0 && v >= 0.9 ? 3 : zone };       // brilho forte no ceu (estrela, lua) e luz
}

/** So a luz da cena (sem regiao). */
export function sceneValue(id: SceneId, x: number, y: number, aspect = 16 / 9): number {
  return sceneSample(id, x, y, aspect).v;
}
