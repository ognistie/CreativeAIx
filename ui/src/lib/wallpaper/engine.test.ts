import { describe, expect, it } from "vitest";
import { prepareGenerative } from "../generative";
import { SCENE_IDS, sceneSample, type SceneId } from "../scenes";
import { artFor } from "./art";
import {
  applySafe, ditherLevels, dotRadius, FieldSampler, safeWeight, sampleField, type Field,
} from "./engine";
import { particlesAt } from "./motion";

const flat = (cols: number, rows: number, v: number, z = 0): Field =>
  ({ cols, rows, lum: new Float32Array(cols * rows).fill(v), zone: new Uint8Array(cols * rows).fill(z) });

describe("motor dos papeis de parede", () => {
  it("o buffer montado em fatias e identico ao montado de uma vez (deterministico)", () => {
    const whole = sampleField("aquario", 64, 36, 16 / 9);
    const sliced = new FieldSampler("aquario", 64, 36, 16 / 9);
    while (!sliced.step(5));
    expect(Array.from(sliced.field.lum)).toEqual(Array.from(whole.lum));
    expect(Array.from(sliced.field.zone)).toEqual(Array.from(whole.zone));
  });

  it("supersampling suaviza a borda: celulas de transicao ficam com luz intermediaria", () => {
    const field = sampleField("retro", 160, 90, 16 / 9);
    const mids = Array.from(field.lum).filter((v) => v > 0.35 && v < 0.65).length;
    expect(mids).toBeGreaterThan(20);
  });

  it("a mascara da interface apaga dentro e preserva fora, sem mexer no buffer original", () => {
    const field = flat(40, 20, 0.8);
    const safe = [{ x: 0.4, y: 0.4, w: 0.2, h: 0.2, strength: 0.6 }];
    const out = applySafe(field, safe, 2);
    expect(out.lum[10 * 40 + 20]).toBeLessThan(0.6);
    expect(out.lum[0]).toBeCloseTo(0.8);
    expect(field.lum[10 * 40 + 20]).toBeCloseTo(0.8);
    expect(safeWeight(0.5, 0.5, safe)).toBeCloseTo(0.6);
    expect(safeWeight(0.95, 0.05, safe)).toBe(0);
  });

  it("os tres dithers mantem a luz media (meio-tom de 0,5 vira ~1,5 de 0..3) e respeitam os niveis", () => {
    for (const method of ["bayer", "blue", "atkinson"] as const) {
      const levels = ditherLevels(flat(64, 64, 0.5), 4, method);
      const mean = levels.reduce((s, k) => s + k, 0) / levels.length;
      expect(mean, method).toBeGreaterThan(1.3);
      expect(mean, method).toBeLessThan(1.7);
      expect(Math.max(...levels), method).toBeLessThanOrEqual(3);
      // trama de verdade: o meio-tom mistura dois niveis vizinhos, nao vira um bloco liso
      expect(new Set(levels).size, method).toBeGreaterThanOrEqual(2);
    }
    // luz minima por regiao: assunto escuro continua aparecendo
    expect(Math.max(...ditherLevels(flat(8, 8, 0, 2), 4, "bayer", [0, 0, 0.34, 0]))).toBeGreaterThan(0);
  });

  it("halftone: area do ponto proporcional a luz; luz quase nula nao desenha", () => {
    const r1 = dotRadius(0.25, 10), r2 = dotRadius(1, 10);
    expect((r1 / r2) ** 2).toBeCloseTo(0.25);
    expect(dotRadius(0.001, 10)).toBe(0);
  });

  it("particulas: posicao pura do tempo, dentro da tela e fora da interface", () => {
    const safe = [{ x: 0.3, y: 0, w: 0.4, h: 1, strength: 1 }];
    for (const kind of ["stars", "bubbles", "dust"] as const) {
      const a = particlesAt(kind, 12.5, 16 / 9), b = particlesAt(kind, 12.5, 16 / 9);
      expect(a, kind).toEqual(b);
      expect(a.length, kind).toBeGreaterThan(10);
      for (const p of a) {
        expect(p.x).toBeGreaterThanOrEqual(0); expect(p.x).toBeLessThanOrEqual(1);
        expect(p.alpha).toBeGreaterThanOrEqual(0); expect(p.alpha).toBeLessThanOrEqual(1);
      }
      expect(particlesAt(kind, 12.5, 16 / 9, safe).every((p) => p.x < 0.3 || p.x > 0.7 || p.alpha < 0.6), kind).toBe(true);
    }
    expect(particlesAt(null, 1, 1)).toEqual([]);
  });

  it("preparo em fatias pode ser cancelado e depois reaproveita o cache", async () => {
    const stop = new AbortController();
    stop.abort();
    expect(await prepareGenerative("dither", 320, 180, "texas", { signal: stop.signal })).toBe(false);
    expect(await prepareGenerative("dither", 320, 180, "texas")).toBe(true);
    expect(await prepareGenerative("dither", 320, 180, "texas")).toBe(true);
  });
});

describe("cenas-piloto", () => {
  const at = (id: SceneId, x: number, y: number) => sceneSample(id, x, y, 16 / 9);
  /** luz media numa caixa (fracoes da tela) */
  const mean = (id: SceneId, x0: number, x1: number, y0: number, y1: number) => {
    let s = 0, n = 0;
    for (let y = y0; y < y1; y += 0.01) for (let x = x0; x < x1; x += 0.01) { s += at(id, x, y).v; n++; }
    return s / n;
  };

  it("cada piloto tem a sua direcao de arte (tecnica, movimento e cor)", () => {
    const methods = (["retro", "aquario", "texas"] as const).map((s) => artFor(s).dither);
    expect(new Set(methods).size).toBe(3);
    expect(artFor("retro").motion).toBe("stars");
    expect(artFor("aquario").motion).toBe("bubbles");
    expect(artFor("texas").motion).toBe("dust");
    expect(artFor("texas").hues.ground).not.toBe(artFor("retro").hues.ground);
  });

  it("Synthwave: sol (luz) a direita, serra (assunto) no horizonte, grade (chao) embaixo", () => {
    expect(at("retro", 0.86, 0.33).zone).toBe(3);
    expect(at("retro", 0.86, 0.33).v).toBeGreaterThan(0.75);
    expect(at("retro", 0.3, 0.8).zone).toBe(1);
    expect([0.2, 0.4, 0.6, 0.8].some((x) => at("retro", x, 0.57).zone === 2)).toBe(true);
  });

  it("Aquario: o peixe principal e reconhecivel (corpo claro, olho escuro) e fica fora da coluna do titulo", () => {
    const body = at("aquario", 0.83, 0.25);
    expect(body.zone).toBe(2);
    expect(body.v).toBeGreaterThan(0.45);
    expect(at("aquario", 0.5, 0.95).zone).toBe(1);
  });

  it("Velho Oeste: sol baixo (luz), saguaro e mesas (assunto), deserto (chao)", () => {
    expect(at("texas", 0.78, 0.47).zone).toBe(3);
    expect(at("texas", 0.9, 0.7).zone).toBe(2);
    expect(at("texas", 0.5, 0.85).zone).toBe(1);
  });

  it("composicao: a coluna do titulo e area de descanso, mais calma que o ponto focal", () => {
    for (const [id, fx0, fx1, fy0, fy1] of [["retro", 0.78, 0.95, 0.25, 0.45], ["aquario", 0.74, 0.92, 0.2, 0.3], ["texas", 0.72, 0.85, 0.42, 0.55]] as const) {
      expect(mean(id, 0.38, 0.62, 0.26, 0.36), id).toBeLessThan(mean(id, fx0, fx1, fy0, fy1));
    }
  });

  it("todas as cenas: a coluna do titulo e mais calma que a parte mais viva, e o assunto aparece fora dela", () => {
    const box = (id: SceneId, x0: number, y0: number) => mean(id, x0, x0 + 0.24, y0, y0 + 0.2);
    for (const id of SCENE_IDS) {
      const title = mean(id, 0.38, 0.62, 0.26, 0.36);
      const boxes = [0, 0.25, 0.5, 0.75].flatMap((x) => [0, 0.2, 0.4, 0.6, 0.8].map((y) => box(id, x, y)));
      expect(title, `${id}: titulo x parte mais viva`).toBeLessThan(Math.max(...boxes) * 0.92);
      let subject = 0;
      for (let y = 0.02; y < 1; y += 0.04) for (let x = 0.02; x < 1; x += 0.03) {
        const inTitle = x > 0.36 && x < 0.64 && y > 0.24 && y < 0.38;
        if (!inTitle && at(id, x, y).zone >= 2) subject++;
      }
      expect(subject, `${id}: assunto/luz fora da coluna do titulo`).toBeGreaterThan(8);
    }
  });
});
