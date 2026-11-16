"""Contraste AA medido nos tokens de app/design/theme.json, nos dois temas e em todas as paletas.

Compoe o vidro sobre a luz mais clara da paleta (pior caso para texto claro) e sobre a base (pior caso
para texto escuro), e exige WCAG AA: 4.5:1 para texto normal. Sem rede; roda no gate.
"""
import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
THEME = APP / 'design' / 'theme.json'
MIN_TEXT = 4.5          # textPrimary e textSecondary: texto normal
MIN_TERTIARY = 4.5      # rotulos pequenos tambem sao texto normal
MIN_UI = 3.0            # cor de destaque como componente de interface (icones, bordas)

_HEX = re.compile(r'^#([0-9A-Fa-f]{6})$')
_RGB = re.compile(r'^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*/\s*([\d.]+)\s*\)$')


def _color(expr):
    """'#rrggbb' ou 'rgb(r g b / a)' -> (r, g, b, a) de 0 a 1."""
    expr = str(expr).strip()
    m = _HEX.match(expr)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)
    m = _RGB.match(expr)
    if m:
        r, g, b, a = m.groups()
        return (int(r) / 255, int(g) / 255, int(b) / 255, float(a))
    raise ValueError(f'cor nao reconhecida: {expr}')


def parse(text):
    """theme.json -> (tokens {'dark','light'}, paletas {'palettes' (claro), 'darkPalettes'})."""
    data = json.loads(text)
    tokens = {theme: {k: _color(v) for k, v in data['colors'][theme].items()} for theme in ('dark', 'light')}
    palettes = {'palettes': {k: [_color(c) for c in v] for k, v in data['palettes']['light'].items()},
                'darkPalettes': {k: [_color(c) for c in v] for k, v in data['palettes']['dark'].items()}}
    return tokens, palettes


def over(fg, bg):
    """fg (com alfa) composto sobre bg opaco -> opaco."""
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def luminance(c):
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c[:3]]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def measure(tokens, palettes):
    """Lista de (tema, paleta, superficie, texto, contraste, minimo)."""
    rows = []
    for theme, pal_key in (('dark', 'darkPalettes'), ('light', 'palettes')):
        t = tokens[theme]
        for pal, tones in palettes[pal_key].items():
            # Fundo real atras do vidro: a luz mais clara (Theme.ambient pode chegar a 1.0) e a base
            backgrounds = [over(tone[:3] + (0.9,), tones[0]) for tone in tones[1:]] + [tones[0]]
            worst = {}
            for bg in backgrounds:
                for surface in ('bgGlass', 'bgGlassHi', 'bgSurface', 'bgSidebar'):
                    face = over(t[surface], bg)
                    for text, floor in (('textPrimary', MIN_TEXT), ('textSecondary', MIN_TEXT), ('textTertiary', MIN_TERTIARY)):
                        ratio = contrast(over(t[text], face), face)
                        key = (surface, text)
                        if key not in worst or ratio < worst[key][0]:
                            worst[key] = (ratio, floor)
                    ratio = contrast(over(t['accent'], face), face)
                    if ('accent',) not in worst or ratio < worst[('accent',)][0]:
                        worst[(surface, 'accent')] = (min(ratio, worst.get((surface, 'accent'), (99,))[0]), MIN_UI)
            # Texto invertido sobre a acao primaria
            worst[('primary', 'textInverse')] = (contrast(t['textInverse'], t['primary']), MIN_TEXT)
            for (surface, text), (ratio, floor) in sorted(worst.items()):
                rows.append((theme, pal, surface, text, round(ratio, 2), floor))
    return rows


def main(argv=None):
    tokens, palettes = parse(THEME.read_text(encoding='utf-8'))
    rows = measure(tokens, palettes)
    failed = [r for r in rows if r[4] < r[5]]
    if '--json' in (argv or sys.argv[1:]):
        print(json.dumps({'rows': rows, 'failed': failed}, ensure_ascii=False))
    else:
        worst_by = {}
        for theme, pal, surface, text, ratio, floor in rows:
            key = (theme, surface, text)
            if key not in worst_by or ratio < worst_by[key][0]:
                worst_by[key] = (ratio, floor, pal)
        for (theme, surface, text), (ratio, floor, pal) in sorted(worst_by.items()):
            mark = 'ok ' if ratio >= floor else 'FAIL'
            print(f'{mark} {theme:5} {surface:11} {text:13} {ratio:5.2f} (min {floor}, pior paleta {pal})')
        print(f'{len(rows)} medidas, {len(failed)} abaixo do minimo')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
