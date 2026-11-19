// Motor dos papeis de parede gerativos, em duas etapas separadas (conteudo antes do estilo):
//   1. sampleField: a cena (lib/scenes.ts) vira um buffer de luz + regiao por celula, com supersampling (bordas
//      sem serrilhado e linhas finas que nao somem). A mascara da interface (safe zones) abaixa luz e contraste
//      atras da barra lateral, do conteudo e da caixa de pedido.
//   2. Os estilos leem o buffer: dithering (Bayer 8x8, ruído azul ou Atkinson) ou halftone com raio pela área de luz.
// Tudo aqui e puro (sem DOM): testado em engine.test.ts. O desenho no canvas fica em lib/generative.ts.

import { sceneSample, type SceneId } from "../scenes";

export interface Field { cols: number; rows: number; lum: Float32Array; zone: Uint8Array }

/** Retangulo de interface em fracoes da tela (0..1). strength: quanto apagar (0..1). */
export interface SafeRect { x: number; y: number; w: number; h: number; strength?: number; feather?: number }

/** Amostra a cena numa grade cols x rows com supersampling ADAPTATIVO: a cena e lida nos cantos das celulas
 *  (compartilhados: ~1 amostra por celula) e a celula e a media dos 4 cantos; so as celulas de borda (cantos muito
 *  diferentes ou de regioes diferentes) ganham mais 5 amostras (quartos e centro). Regiao pela maioria, mas assunto e
 *  luz pequenos ganham a celula se cobrirem 1/4 dela, para detalhe fino nao sumir.
 *  ss = 1: uma amostra no centro. ss = 3: cantos + centro sempre (células grandes
 *  do halftone: uma estrela menor que a celula nao some entre os cantos). */
export function sampleField(scene: SceneId, cols: number, rows: number, aspect: number, ss = 2): Field {
  const sampler = new FieldSampler(scene, cols, rows, aspect, ss);
  sampler.step(Infinity);
  return sampler.field;
}

/** O mesmo amostrador em fatias de linhas: step(n) le ate n linhas e devolve se terminou. Assim o buffer de uma
 *  cena grande e montado aos poucos (sem travar a janela) e o resultado e identico ao do sampleField. */
export class FieldSampler {
  readonly field: Field;
  private row = 0;
  private prevV: Float32Array; private prevZ: Uint8Array;
  private nextV: Float32Array; private nextZ: Uint8Array;
  private readonly counts = [0, 0, 0, 0];

  constructor(private readonly scene: SceneId, readonly cols: number, readonly rows: number,
    private readonly aspect: number, private readonly ss = 2) {
    this.field = { cols, rows, lum: new Float32Array(cols * rows), zone: new Uint8Array(cols * rows) };
    const W = cols + 1;
    this.prevV = new Float32Array(W); this.prevZ = new Uint8Array(W);
    this.nextV = new Float32Array(W); this.nextZ = new Uint8Array(W);
    if (ss > 1) for (let i = 0; i <= cols; i++) { const s = this.at(i, 0); this.prevV[i] = s.v; this.prevZ[i] = s.zone; }
  }

  get done() { return this.row >= this.rows; }

  private at(x: number, y: number) { return sceneSample(this.scene, x / this.cols, y / this.rows, this.aspect); }

  step(maxRows: number): boolean {
    const { cols, field: { lum, zone }, counts } = this;
    const end = Math.min(this.rows, this.row + maxRows);
    for (let j = this.row; j < end; j++) {
      if (this.ss <= 1) {
        for (let i = 0; i < cols; i++) { const s = this.at(i + 0.5, j + 0.5); lum[j * cols + i] = s.v; zone[j * cols + i] = s.zone; }
        continue;
      }
      const { prevV, prevZ, nextV, nextZ } = this;
      for (let i = 0; i <= cols; i++) { const s = this.at(i, j + 1); nextV[i] = s.v; nextZ[i] = s.zone; }
      for (let i = 0; i < cols; i++) {
        counts[0] = counts[1] = counts[2] = counts[3] = 0;
        counts[prevZ[i]!]!++; counts[prevZ[i + 1]!]!++; counts[nextZ[i]!]!++; counts[nextZ[i + 1]!]!++;
        const a = prevV[i]!, b = prevV[i + 1]!, c = nextV[i]!, d = nextV[i + 1]!;
        let acc = a + b + c + d, n = 4;
        let peak = 0;                                     // luz pontual (estrela, brilho): a media nao apaga
        const lo = Math.min(a, b, c, d), hi = Math.max(a, b, c, d);
        const mixed = prevZ[i] !== nextZ[i + 1] || prevZ[i + 1] !== nextZ[i] || prevZ[i] !== prevZ[i + 1];
        if (this.ss >= 3) {                                // estilos de celula grande: o centro sempre entra
          const s = this.at(i + 0.5, j + 0.5);
          acc += s.v; counts[s.zone]!++; n++;
          if (s.zone === 3 && s.v > peak) peak = s.v;
        }
        if (hi - lo > 0.16 || mixed) {
          for (const [ox, oy] of EDGE_TAPS) {
            const s = this.at(i + ox, j + oy);
            acc += s.v; counts[s.zone]!++; n++;
            if (s.zone === 3 && s.v > peak) peak = s.v;
          }
        }
        if (prevZ[i] === 3 || prevZ[i + 1] === 3 || nextZ[i] === 3 || nextZ[i + 1] === 3) peak = Math.max(peak, hi);
        let best = 0;
        for (let k = 1; k < 4; k++) if (counts[k]! > counts[best]!) best = k;
        if (counts[3]! * 4 >= n && best !== 3) best = 3;
        else if (counts[2]! * 4 >= n && best < 2) best = 2;
        lum[j * cols + i] = Math.max(acc / n, best === 3 ? peak * 0.9 : 0);
        zone[j * cols + i] = best;
      }
      this.prevV = nextV; this.nextV = prevV;
      this.prevZ = nextZ; this.nextZ = prevZ;
    }
    this.row = end;
    return this.done;
  }
}
const EDGE_TAPS = [[0.25, 0.25], [0.75, 0.25], [0.5, 0.5], [0.25, 0.75], [0.75, 0.75]] as const;

/** Distancia (em fracoes) ate um retangulo de cantos arredondados; <= 0 dentro. */
function rectDistance(x: number, y: number, r: SafeRect, aspect: number) {
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
  const dx = Math.max(Math.abs(x - cx) - r.w / 2, 0) * aspect, dy = Math.max(Math.abs(y - cy) - r.h / 2, 0);
  return Math.hypot(dx, dy);
}

/** Peso da mascara da interface em (x, y): 1 dentro de um retangulo, caindo suave ate 0 na borda do feather. */
export function safeWeight(x: number, y: number, safe: readonly SafeRect[], aspect = 16 / 9): number {
  let m = 0;
  for (const r of safe) {
    const d = rectDistance(x, y, r, aspect);
    const f = r.feather ?? 0.06;
    const t = d <= 0 ? 1 : d >= f ? 0 : 1 - (d / f) * (d / f) * (3 - 2 * (d / f));
    m = Math.max(m, t * (r.strength ?? 0.6));
  }
  return m;
}

/** Atras da interface: menos luz e menos contraste (o tema continua, mas nao briga com o texto). Devolve uma copia:
 *  o buffer da cena fica intacto no cache (mudar a interface nao exige amostrar a cena de novo). */
export function applySafe(field: Field, safe: readonly SafeRect[], aspect: number): Field {
  if (!safe.length) return field;
  const { cols, rows } = field;
  const lum = new Float32Array(field.lum);
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const m = safeWeight((i + 0.5) / cols, (j + 0.5) / rows, safe, aspect);
      if (m <= 0) continue;
      const at = j * cols + i;
      // puxa para um tom baixo e achata: luz forte cai mais que luz fraca
      lum[at] = lum[at]! * (1 - 0.62 * m) + 0.04 * m;
    }
  }
  return { ...field, lum };
}

// ── Dithering ───────────────────────────────────────────────────────────────────────────────────
export type DitherMethod = "bayer" | "blue" | "atkinson";

export const BAYER8: number[][] = (() => {
  const m = [[0, 2], [3, 1]];
  let b = m;
  for (let n = 2; n < 8; n *= 2) {
    b = Array.from({ length: n * 2 }, (_, i) => Array.from({ length: n * 2 }, (_, j) => 4 * b[i % n]![j % n]! + m[Math.floor(i / n)]![Math.floor(j / n)]!));
  }
  return b.map((r) => r.map((v) => (v + 0.5) / 64));
})();

/** Ruido de gradiente intercalado (Jimenez): limiar de espectro azul, sem a trama em cruz do Bayer. */
export const blueNoise = (i: number, j: number) => {
  const f = 0.06711056 * i + 0.00583715 * j;
  const g = 52.9829189 * (f - Math.floor(f));
  return g - Math.floor(g);
};

/** Nivel (0..levels-1) de cada celula. `floor` = luz minima por regiao (assunto escuro continua visivel). */
export function ditherLevels(field: Field, levels: number, method: DitherMethod, floor: readonly number[] = [0, 0, 0, 0]): Uint8Array {
  const { cols, rows, lum, zone } = field;
  const out = new Uint8Array(cols * rows);
  const top = levels - 1;
  if (method === "atkinson") {
    // difusao de erro: 1/8 para seis vizinhos (2/8 se perdem: contraste mais vivo, sem lama nos escuros)
    const work = new Float32Array(cols * rows);
    for (let k = 0; k < work.length; k++) work[k] = Math.max(lum[k]!, floor[zone[k]!]!) * top;
    const push = (i: number, j: number, e: number) => { if (i >= 0 && i < cols && j < rows) work[j * cols + i]! += e; };
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        const at = j * cols + i, v = work[at]!;
        const k = Math.max(0, Math.min(top, Math.round(v)));
        out[at] = k;
        const e = (v - k) / 8;
        push(i + 1, j, e); push(i + 2, j, e); push(i - 1, j + 1, e); push(i, j + 1, e); push(i + 1, j + 1, e); push(i, j + 2, e);
      }
    }
    return out;
  }
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const at = j * cols + i;
      const v = Math.max(lum[at]!, floor[zone[at]!]!) * top;
      const t = method === "bayer" ? BAYER8[j & 7]![i & 7]! : blueNoise(i, j);
      out[at] = Math.min(top, Math.floor(v) + (v - Math.floor(v) > t ? 1 : 0));
    }
  }
  return out;
}

// ── Halftone ────────────────────────────────────────────────────────────────────────────────────
/** Raio do ponto pela area de luz (area ~ luz): r = R * sqrt(luz). Abaixo de minR o ponto nao aparece. */
export const dotRadius = (light: number, cellR: number, minR = 0.55) => {
  const r = cellR * Math.sqrt(Math.max(0, Math.min(1, light)));
  return r < minR ? 0 : r;
};
