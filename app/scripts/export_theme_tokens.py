"""Gera os tokens visuais da interface Tauri a partir do QML (fonte unica).

    desktop/qml/components/Theme.qml  ->  ui/src/styles/tokens.css
    desktop/qml/components/Icon.qml   ->  ui/src/lib/icons.gen.ts

Theme.qml continua sendo a fonte: scripts/check_contrast.py mede o AA nele, e o CSS sai dele, entao as
duas interfaces nunca divergem. Mesmo parser do check_contrast (cada token com tema numa linha
`nome: dark ? <escuro> : <claro>`).

Seletores no CSS (a tela aplica o que o usuario salvou no Harness, via Bridge.appearance):
    <html data-theme="escuro|claro" data-palette="abismo|..." data-radius="suave|reto|redondo"
          data-motion="on|off">   e   style="--accent: #RRGGBB" para a cor de destaque

Uso:
    python app/scripts/export_theme_tokens.py           # grava
    python app/scripts/export_theme_tokens.py --check   # falha se estiver desatualizado
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP / "scripts"))

from check_contrast import THEME, parse  # noqa: E402

ICON_QML = APP / "desktop" / "qml" / "components" / "Icon.qml"
OUT_CSS = ROOT / "ui" / "src" / "styles" / "tokens.css"
OUT_ICONS = ROOT / "ui" / "src" / "lib" / "icons.gen.ts"
HEADER = "Gerado por app/scripts/export_theme_tokens.py a partir de {src}. Nao edite a mao."


def kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def css_color(c: tuple) -> str:
    r, g, b, a = (round(c[0] * 255), round(c[1] * 255), round(c[2] * 255), c[3])
    if a >= 0.999:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgb({r} {g} {b} / {round(a, 3)})"


def _ints(text: str, names: list) -> dict:
    out = {}
    for n in names:
        m = re.search(rf"property int {n}:\s*(\d+)", text)
        if not m:
            raise ValueError(f"Theme.qml sem {n}")
        out[n] = int(m.group(1))
    return out


def _radii(text: str) -> dict:
    out = {}
    for n in ("r1", "r2", "r3", "r4", "rComposer"):
        m = re.search(rf"property int {n}:\s*Math\.round\((\d+) \* rScale\)", text)
        if not m:
            raise ValueError(f"Theme.qml sem {n}")
        out[n] = int(m.group(1))
    scales = re.search(r'radiusStyle === "reto" \? ([\d.]+) : \(radiusStyle === "redondo" \? ([\d.]+) : ([\d.]+)\)', text)
    return out | {"_reto": float(scales.group(1)), "_redondo": float(scales.group(2))}


def _string(text: str, name: str) -> str:
    m = re.search(rf'property string {name}:\s*"([^"]+)"', text)
    if not m:
        raise ValueError(f"Theme.qml sem {name}")
    return m.group(1)


def render_css() -> str:
    text = THEME.read_text(encoding="utf-8")
    tokens, palettes = parse(text)
    dark, light = tokens["dark"], tokens["light"]
    default_palette = _string(text, "palette")
    sp = _ints(text, ["sp1", "sp2", "sp3", "sp4", "sp5", "sp6"])
    sizes = _ints(text, ["sizeXs", "sizeSm", "sizeMd", "sizeLg", "sizeXl", "sizeHero"])
    durs = _ints(text, ["durFast", "durNormal", "durPanel", "durSlow", "stagger", "contentMax"])
    radii = _radii(text)
    press = re.search(r"property real press:\s*([\d.]+)", text).group(1)
    fonts = {k: _string(text, k) for k in ("fontSans", "fontDisplay", "fontMono")}

    def block(selector: str, values: dict) -> list:
        body = [f"  --{kebab(k)}: {css_color(v)};" for k, v in values.items()]
        return [f"{selector} {{", *body, "}", ""]

    out = [f"/* {HEADER.format(src='Theme.qml')} */", ""]
    shared = {k: v for k, v in dark.items() if light.get(k) == v}
    out += [":root {", "  color-scheme: dark;"]
    out += [f"  --{kebab(k)}: {css_color(v)};" for k, v in shared.items()]
    out += [f"  --sp{i}: {sp[f'sp{i}']}px;" for i in range(1, 7)]
    out += [f"  --r-scale: 1;"]
    out += [f"  --{kebab(k)}: calc({v}px * var(--r-scale));" for k, v in radii.items() if not k.startswith("_")]
    out += [f"  --{kebab(k)}: {v}px;" for k, v in sizes.items()]
    out += [f"  --font-sans-family: \"{fonts['fontSans']}\", \"Segoe UI\", system-ui, sans-serif;",
            f"  --font-display-family: \"{fonts['fontDisplay']}\", \"Segoe UI\", system-ui, sans-serif;",
            f"  --font-mono-family: \"{fonts['fontMono']}\", Consolas, monospace;"]
    out += [f"  --{kebab(k)}: {v}ms;" for k, v in durs.items() if k.startswith("dur") or k == "stagger"]
    out += [f"  --content-max: {durs['contentMax']}px;",
            f"  --press: {press};",
            "  --ease-standard: cubic-bezier(0.65, 0, 0.35, 1);",
            "  --ease-out: cubic-bezier(0.33, 1, 0.68, 1);",
            "  --ease-in: cubic-bezier(0.32, 0, 0.67, 0);",
            "}", ""]

    themed_dark = {k: v for k, v in dark.items() if k not in shared}
    themed_light = {k: v for k, v in light.items() if k not in shared}
    out += block(':root,\n[data-theme="escuro"]', themed_dark)
    out += ['[data-theme="claro"] {', "  color-scheme: light;"]
    out += [f"  --{kebab(k)}: {css_color(v)};" for k, v in themed_light.items()]
    out += ["}", ""]

    # Paletas (base + 3 luzes). --bg-base e a base da paleta, como Theme.bgBase = splashBase.
    for theme, key in (("escuro", "darkPalettes"), ("claro", "palettes")):
        for name, tones in palettes[key].items():
            sel = f'[data-theme="{theme}"][data-palette="{name}"]'
            if theme == "escuro" and name == default_palette:
                sel = f':root,\n[data-palette="{name}"],\n{sel}'
            elif name == default_palette:
                sel = f'[data-theme="claro"],\n{sel}'
            out += [f"{sel} {{"]
            out += [f"  --tone-{i}: {css_color(t)};" for i, t in enumerate(tones)]
            out += ["  --bg-base: var(--tone-0);", "}", ""]

    out += [f'[data-radius="reto"] {{ --r-scale: {radii["_reto"]}; }}',
            f'[data-radius="redondo"] {{ --r-scale: {radii["_redondo"]}; }}', ""]
    out += ['[data-motion="off"] {', "  --dur-fast: 0ms;", "  --dur-normal: 0ms;", "  --dur-panel: 0ms;",
            "  --dur-slow: 0ms;", "  --stagger: 0ms;", "}", ""]
    out += ["@media (prefers-reduced-motion: reduce) {", "  :root {", "    --dur-fast: 0ms;", "    --dur-normal: 0ms;",
            "    --dur-panel: 0ms;", "    --dur-slow: 0ms;", "    --stagger: 0ms;", "  }", "}", ""]
    return "\n".join(out)


def render_icons() -> str:
    text = ICON_QML.read_text(encoding="utf-8")
    body = re.search(r"readonly property var paths: \(\{(.*?)\}\)", text, re.S).group(1)
    paths = dict(re.findall(r'"([\w-]+)":\s*"([^"]+)"', body))
    lines = [f"// {HEADER.format(src='Icon.qml')}", "// Desenhos de linha 24x24 (traco, pontas arredondadas): os mesmos do app QML.", "",
             "export const ICONS = {"]
    lines += [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in sorted(paths.items())]
    lines += ["} as const;", "", "export type IconName = keyof typeof ICONS;", ""]
    return "\n".join(lines)


def main() -> int:
    outputs = {OUT_CSS: render_css(), OUT_ICONS: render_icons()}
    if "--check" in sys.argv:
        stale = [p for p, t in outputs.items() if (p.read_text(encoding="utf-8") if p.is_file() else "") != t]
        for p in stale:
            print(f"{p.relative_to(ROOT)} desatualizado: rode scripts/export_theme_tokens.py")
        if not stale:
            print("tokens e icones em dia")
        return 1 if stale else 0
    for p, t in outputs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(t, encoding="utf-8", newline="\n")
        print(f"gravado {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
