// Aparencia salva no Harness (Bridge.appearance) aplicada como atributos no <html>, que o tokens.css le.
// Mesmo conjunto que Theme.applyAppearance() aceita no app anterior.

import { inQt } from "./host";

export interface Appearance {
  wallpaper?: string;
  art?: unknown;
  dim?: number;
  mode?: string;
  palette?: string;
  accent?: string;
  radius?: string;
  motion?: boolean;
  ambient?: number;
  blur?: boolean;
}

const MODES = new Set(["escuro", "claro"]);
const RADII = new Set(["suave", "reto", "redondo"]);
const HEX = /^#[0-9A-Fa-f]{6}$/;

export function applyAppearance(a: Appearance | null | undefined, root: HTMLElement = document.documentElement): void {
  if (!LIVE_BLUR) root.dataset.blur = "off";
  if (!a) return;
  if (a.mode && MODES.has(a.mode)) root.dataset.theme = a.mode;
  if (a.palette && /^[\w-]+$/.test(a.palette)) root.dataset.palette = a.palette;
  if (a.radius && RADII.has(a.radius)) root.dataset.radius = a.radius;
  if (typeof a.motion === "boolean") root.dataset.motion = a.motion ? "on" : "off";
  if (a.accent && HEX.test(a.accent)) root.style.setProperty("--accent", a.accent);
  if (typeof a.ambient === "number") root.style.setProperty("--ambient", String(Math.max(0, Math.min(1, a.ambient))));
  if (LIVE_BLUR && typeof a.blur === "boolean") root.dataset.blur = a.blur ? "on" : "off";
}

/** Vidro com desfoque de verdade (backdrop-filter) pode ser usado aqui? No app desktop (QtWebEngine) nao: medido em
 *  2026-11-24 no app real, com a tela gravada, a barra lateral sumia por 1-2 quadros em quase toda troca de secao
 *  (26 vezes em 24 trocas); sem backdrop-filter, 3; tirando so a camada da barra, 13. O defeito esta na composicao
 *  do QtWebEngine com o desfoque de fundo, nao no React. No app, os paineis viram superficies quase opacas. */
export const LIVE_BLUR = !inQt;

// Ultima aparencia vista, guardada so neste app (localStorage): a abertura e o primeiro quadro ja saem no tema,
// paleta e papel de parede escolhidos, sem esperar o nucleo carregar. A fonte continua sendo o Harness: assim que
// ele responde, o valor real substitui este.
export interface Look {
  appearance?: Appearance;
  wallpaper?: string;
}

const LOOK_KEY = "creative-aix.look";

export function rememberLook(look: Look): void {
  try {
    localStorage.setItem(LOOK_KEY, JSON.stringify(look));
  } catch {
    /* sem armazenamento: so perde o atalho visual */
  }
}

export function readLook(): Look {
  try {
    const v = JSON.parse(localStorage.getItem(LOOK_KEY) || "{}") as Look;
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}
