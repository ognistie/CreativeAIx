// Direcao de arte por cena: cada cena escolhe a tecnica que combina com ela (nao um filtro igual para todas).
// Sem controles tecnicos na interface: e o "preset" artistico da cena; da para ajustar aqui ou por opcao.

import type { ZoneHues } from "../generative";
import type { SceneId } from "../scenes";
import type { DitherMethod } from "./engine";

export type MotionKind = "stars" | "bubbles" | "dust" | "petals" | "fireflies" | "glints" | null;

export interface SceneArt {
  /** algoritmo do dithering */
  dither: DitherMethod;
  /** tamanho do pixel do dithering (px na largura de 1440) */
  ditherPx: number;
  /** espaco entre pontos do halftone (px na largura de 1440) */
  halftoneCell: number;
  /** particulas ligadas ao conteudo (estrelas, bolhas, poeira); null = cena parada */
  motion: MotionKind;
  /** color grading da cena: giro de cor do chao e das luzes a partir do destaque */
  hues: ZoneHues;
  /** escala das marcas pelo perfil de qualidade (eco: marcas maiores = menos amostras; alto: mais detalhe) */
  scale: number;
}

export const DEFAULT_ART: SceneArt = { dither: "bayer", ditherPx: 4, halftoneCell: 9, motion: null,
  hues: { ground: -140, glow: 40 }, scale: 1 };

const ART: Partial<Record<SceneId, Partial<SceneArt>>> = {
  // neon retro: trama Bayer classica, estrelas cintilando
  retro: { dither: "bayer", ditherPx: 4, motion: "stars" },
  // agua: ruido azul (sem trama em cruz nos degrades do fundo), pontos finos, bolhas subindo
  aquario: { dither: "blue", ditherPx: 3, halftoneCell: 8, motion: "bubbles", hues: { ground: -150, glow: 22, groundAbs: 40 } },
  // deserto: difusao de erro (textura de areia e rocha), poeira no ar
  // chao cor de areia (vizinha quente do destaque), luz do sol amarelada
  texas: { dither: "atkinson", ditherPx: 3, halftoneCell: 8, motion: "dust", hues: { ground: -14, glow: 28, groundAbs: 30 } },
  // telhado ao luar: Bayer (noite retro), estrelas
  gatinhos: { dither: "bayer", motion: "stars" },
  // natureza-morta impressa: pontos finos, difusao de erro nas texturas, poeira na luz da janela
  frutas: { dither: "atkinson", halftoneCell: 8, motion: "dust", hues: { ground: -25, glow: 30 } },
  // baia ao entardecer: ruido azul nos degrades do ceu e da agua, brilho na agua
  rio: { dither: "blue", motion: "glints", hues: { ground: -160, glow: 30 } },
  // céu em correntes e estrelas
  noite: { dither: "bayer", motion: "stars", hues: { ground: -150, glow: 50 } },
  // jardim: pontos e petalas soltas ao vento
  jardim: { dither: "atkinson", halftoneCell: 8, motion: "petals", hues: { ground: 120, glow: 45 } },
  // floresta: difusao de erro (textura de folhagem), vaga-lumes
  bosque: { dither: "atkinson", ditherPx: 3, motion: "fireflies", hues: { ground: -30, glow: 60 } },
  // lago: ruido azul (reflexo liso), brilho da lua na agua
  lago: { dither: "blue", ditherPx: 3, motion: "glints", hues: { ground: -20, glow: 35 } },
  // praia: areia dourada fixa, brilho do sol no mar
  praia: { dither: "atkinson", ditherPx: 3, halftoneCell: 8, motion: "glints", hues: { ground: -150, glow: 30, groundAbs: 42 } },
};

export const artFor = (scene: SceneId, override?: Partial<SceneArt>): SceneArt => ({ ...DEFAULT_ART, ...ART[scene], ...override });

// ── Preferencias avancadas (Harness > Aparencia > Avancado; validadas em core/harness.py GEN_ART) ───────────
export type Quality = "eco" | "equilibrado" | "alto";
export type MotionLevel = "parado" | "sutil" | "animado";
export interface ArtPrefs {
  dither: "auto" | DitherMethod;
  quality: "auto" | Quality;
  motion: "auto" | MotionLevel;
}
export const DEFAULT_PREFS: ArtPrefs = { dither: "auto", quality: "auto", motion: "auto" };
export const PREF_OPTIONS = {
  dither: ["auto", "bayer", "blue", "atkinson"],
  quality: ["auto", "eco", "equilibrado", "alto"],
  motion: ["auto", "parado", "sutil", "animado"],
} as const;

/** Le as preferencias do Harness; valor desconhecido vira "auto". */
export function readPrefs(raw: unknown): ArtPrefs {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const pick = <K extends keyof ArtPrefs>(k: K) =>
    ((PREF_OPTIONS[k] as readonly string[]).includes(String(r[k])) ? r[k] : "auto") as ArtPrefs[K];
  return { dither: pick("dither"), quality: pick("quality"), motion: pick("motion") };
}

/** Perfil automatico pelo aparelho: poucos nucleos ou pouca memoria = eco; muitos nucleos = alto. */
export function autoQuality(env: { cores?: number; memory?: number; saving?: boolean } = {}): Quality {
  const cores = env.cores ?? (typeof navigator !== "undefined" ? navigator.hardwareConcurrency : 8) ?? 8;
  const memory = env.memory ?? (typeof navigator !== "undefined" ? (navigator as Navigator & { deviceMemory?: number }).deviceMemory : undefined);
  if (env.saving || cores <= 4 || (memory !== undefined && memory <= 4)) return "eco";
  return cores >= 12 ? "alto" : "equilibrado";
}

const QUALITY_SCALE: Record<Quality, number> = { eco: 1.35, equilibrado: 1, alto: 0.85 };

/** Ajuste da direcao de arte da cena pelas preferencias (o que for "auto" fica com a cena e o aparelho). */
export function prefsOverride(prefs: ArtPrefs, env?: Parameters<typeof autoQuality>[0]): Partial<SceneArt> {
  const out: Partial<SceneArt> = { scale: QUALITY_SCALE[prefs.quality === "auto" ? autoQuality(env) : prefs.quality] };
  if (prefs.dither !== "auto") out.dither = prefs.dither;
  return out;
}

/** Quadros por segundo da camada de movimento (0 = parado). Eco e "sutil" andam a 15; "animado" a 30. */
export function motionFps(prefs: ArtPrefs, env?: Parameters<typeof autoQuality>[0]): number {
  const level = prefs.motion === "auto" ? (autoQuality(env) === "eco" ? "sutil" : "animado") : prefs.motion;
  return level === "parado" ? 0 : level === "sutil" ? 15 : 30;
}
