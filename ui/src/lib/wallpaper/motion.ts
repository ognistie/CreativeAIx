// Movimento dos papeis de parede: so o que existe na cena e se moveria nela (estrelas cintilando, bolhas subindo,
// poeira no ar). A cena em si fica parada (desenhada uma vez); as particulas sao uma camada leve por cima, com
// posicao funcao pura do tempo (sem acumular erro, sem tremor) e sementes fixas. Sem particulas atras da interface.

import { hash } from "../scenes";
import type { MotionKind } from "./art";
import { safeWeight, type SafeRect } from "./engine";

/** Particula em fracoes da tela; size em multiplos da marca do estilo; alpha 0..1 */
export interface Particle { x: number; y: number; size: number; alpha: number }

const STARS = 46, BUBBLES = 22, DUST = 34, PETALS = 16, FIREFLIES = 26, GLINTS = 40;

/** Particulas no instante t (segundos). aspect = largura/altura (as cenas usam u de 0 a aspect). */
export function particlesAt(kind: MotionKind, t: number, aspect: number, safe: readonly SafeRect[] = []): Particle[] {
  const out: Particle[] = [];
  const keep = (p: Particle) => {
    const m = safe.length ? safeWeight(p.x, p.y, safe, aspect) : 0;
    if (m < 0.45) out.push({ ...p, alpha: p.alpha * (1 - m) });
  };
  if (kind === "stars") {
    for (let k = 0; k < STARS; k++) {
      const x = hash(k, 11), y = 0.03 + 0.38 * hash(k, 12) ** 1.3;
      // cintilar lento e raro: a maior parte do tempo quase apagada, as vezes um brilho
      const phase = hash(k, 13) * 6.283, speed = 0.35 + 0.5 * hash(k, 14);
      const tw = Math.max(0, Math.sin(t * speed + phase)) ** 6;
      keep({ x, y, size: 0.8 + 0.6 * hash(k, 15), alpha: 0.15 + 0.85 * tw });
    }
  } else if (kind === "bubbles") {
    // nas mesmas tres colunas de bolhas da cena (lib/scenes.ts, aquario), subindo e oscilando
    const cols = [0.12, 0.88, 0.7];
    for (let k = 0; k < BUBBLES; k++) {
      const col = cols[k % 3]!, speed = 0.028 + 0.02 * hash(k, 21), phase = hash(k, 22);
      const rise = (t * speed + phase) % 0.82;
      const y = 0.86 - rise;
      const x = (col * aspect + 0.012 * Math.sin(y * 24 + k) + (hash(k, 23) - 0.5) * 0.02) / aspect;
      keep({ x, y, size: 0.6 + 1.1 * (rise / 0.82), alpha: 0.75 * Math.min(1, rise * 8) * Math.min(1, (0.82 - rise) * 10) });
    }
  } else if (kind === "dust") {
    // poeira na luz baixa do deserto: deriva lenta para a direita, ondulando; acende quando pega luz
    for (let k = 0; k < DUST; k++) {
      const x = (hash(k, 31) + t * (0.004 + 0.006 * hash(k, 32))) % 1;
      const y = 0.42 + 0.46 * hash(k, 33) + 0.012 * Math.sin(t * 0.6 + k);
      const glint = Math.max(0, Math.sin(t * (0.5 + hash(k, 34)) + k)) ** 4;
      keep({ x, y, size: 0.6 + 0.5 * hash(k, 35), alpha: 0.25 + 0.55 * glint });
    }
  } else if (kind === "petals") {
    // petalas caindo devagar e girando (a "piscada" e a petala virando de lado)
    for (let k = 0; k < PETALS; k++) {
      const fall = (t * (0.012 + 0.01 * hash(k, 41)) + hash(k, 42)) % 1;
      const x = (hash(k, 43) + 0.06 * Math.sin(t * 0.7 + k) + t * 0.006) % 1;
      keep({ x, y: fall, size: 0.9 + 0.6 * hash(k, 44), alpha: 0.35 + 0.5 * Math.abs(Math.sin(t * 1.3 + k)) });
    }
  } else if (kind === "fireflies") {
    // vaga-lumes na parte baixa da floresta: vagam devagar e acendem em pulsos
    for (let k = 0; k < FIREFLIES; k++) {
      const x = hash(k, 51) + 0.03 * Math.sin(t * 0.23 + k * 1.7);
      const y = 0.55 + 0.35 * hash(k, 52) + 0.02 * Math.cos(t * 0.31 + k);
      const pulse = Math.max(0, Math.sin(t * (0.6 + 0.5 * hash(k, 53)) + k * 2.1)) ** 3;
      keep({ x: ((x % 1) + 1) % 1, y, size: 0.8, alpha: 0.1 + 0.9 * pulse });
    }
  } else if (kind === "glints") {
    // brilhos na agua (abaixo do horizonte): acendem e apagam no lugar, sem deslizar
    for (let k = 0; k < GLINTS; k++) {
      const x = hash(k, 61), y = 0.58 + 0.3 * hash(k, 62) ** 1.4;
      const on = Math.max(0, Math.sin(t * (0.9 + hash(k, 63)) + k * 3.3)) ** 8;
      keep({ x, y, size: 0.7 + 0.5 * hash(k, 64), alpha: on * 0.9 });
    }
  }
  return out;
}

/** Quadros por segundo da camada (30 animado, 15 sutil/eco); cai pela metade se o quadro passar de 6 ms (medido). */
export class FrameBudget {
  private slow = 0;
  constructor(public fps = 30) {}
  record(ms: number) {
    this.slow = ms > 6 ? this.slow + 1 : Math.max(0, this.slow - 1);
    if (this.slow > 10 && this.fps > 10) { this.fps = Math.max(10, Math.round(this.fps / 2)); this.slow = 0; }
  }
}
