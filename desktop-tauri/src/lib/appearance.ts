// Aparencia salva no Harness (Bridge.appearance) aplicada como atributos no <html>, que o tokens.css le.
// Mesmo conjunto que Theme.applyAppearance() aceita no QML.

export interface Appearance {
  mode?: string;
  palette?: string;
  accent?: string;
  radius?: string;
  motion?: boolean;
}

const MODES = new Set(["escuro", "claro"]);
const RADII = new Set(["suave", "reto", "redondo"]);
const HEX = /^#[0-9A-Fa-f]{6}$/;

export function applyAppearance(a: Appearance | null | undefined, root: HTMLElement = document.documentElement): void {
  if (!a) return;
  if (a.mode && MODES.has(a.mode)) root.dataset.theme = a.mode;
  if (a.palette && /^[\w-]+$/.test(a.palette)) root.dataset.palette = a.palette;
  if (a.radius && RADII.has(a.radius)) root.dataset.radius = a.radius;
  if (typeof a.motion === "boolean") root.dataset.motion = a.motion ? "on" : "off";
  if (a.accent && HEX.test(a.accent)) root.style.setProperty("--accent", a.accent);
}
