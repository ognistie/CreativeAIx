"""
Ampliacao "de pintura" para os papeis de parede (sem modelo de IA, so numpy + Pillow).

Imagens pequenas ou comprimidas em JPEG, ampliadas direto, mostram blocos e pixels. Para pinturas o
tratamento que fica natural e o pictorico:
1. ampliar em etapas de 2x com Lanczos ate a largura final;
2. filtro de Kuwahara (por regiao de menor variancia): desfaz blocos de JPEG e serrilhado e forma
   pinceladas planas com bordas nitidas, como tinta a oleo; misturado com a imagem ampliada para nao
   "posterizar";
3. nitidez (unsharp) para devolver o contorno das pinceladas;
4. textura leve de tela (trama), que da materialidade e disfarca o que restar de suavidade.
Deterministico: mesma imagem, mesmo resultado (a trama usa semente fixa).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PIL import Image, ImageFilter

TARGET_WIDTH = 2880          # 1920 x 1.5: nitido ate 150% de escala do Windows (e em 4K com pouca perda)


def _box_sums(S: np.ndarray, H: int, W: int, r: int):
    """Somas das 4 janelas (r+1)x(r+1) de cada pixel a partir da integral S (com borda de r e linha/coluna 0)."""
    k = r + 1
    out = []
    for oy in (0, r):
        for ox in (0, r):
            y0, x0 = oy, ox
            a = S[y0 + k:y0 + k + H, x0 + k:x0 + k + W]
            b = S[y0:y0 + H, x0 + k:x0 + k + W]
            c = S[y0 + k:y0 + k + H, x0:x0 + W]
            d = S[y0:y0 + H, x0:x0 + W]
            out.append(a - b - c + d)
    return out


def _integral(x: np.ndarray, r: int) -> np.ndarray:
    pad = np.pad(x, ((r, r), (r, r)) + ((0, 0),) * (x.ndim - 2), mode="reflect")
    S = pad.cumsum(0).cumsum(1)
    return np.pad(S, ((1, 0), (1, 0)) + ((0, 0),) * (x.ndim - 2))


def kuwahara(rgb: np.ndarray, r: int) -> np.ndarray:
    """Kuwahara classico guiado pela luminancia. rgb: float32 HxWx3 em 0..1."""
    H, W, _ = rgb.shape
    lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float64)
    n = float((r + 1) ** 2)
    s1 = _box_sums(_integral(lum, r), H, W, r)
    s2 = _box_sums(_integral(lum * lum, r), H, W, r)
    var = np.stack([b / n - (a / n) ** 2 for a, b in zip(s1, s2)])          # 4 x H x W
    best = var.argmin(0)
    sc = _box_sums(_integral(rgb.astype(np.float64), r), H, W, r)            # 4 x (H x W x 3)
    means = np.stack(sc) / n                                                 # 4 x H x W x 3
    idx = best[None, ..., None].repeat(3, axis=-1)
    return np.take_along_axis(means, idx, axis=0)[0].astype(np.float32)


def _canvas(H: int, W: int, strength: float = 0.028) -> np.ndarray:
    """Trama de tela: fios horizontais e verticais finos + grao, centrada em 1.0 (multiplicativa)."""
    rng = np.random.default_rng(1866)
    rows = rng.normal(0, 1, H).astype(np.float32)
    cols = rng.normal(0, 1, W).astype(np.float32)
    weave = (np.sin(np.arange(W, dtype=np.float32) * 1.9)[None, :] * np.sin(np.arange(H, dtype=np.float32) * 1.9)[:, None])
    grain = rng.normal(0, 1, (H, W)).astype(np.float32)
    tex = 0.35 * rows[:, None] + 0.35 * cols[None, :] + 0.5 * weave + 0.4 * grain
    tex /= max(1e-6, float(tex.std()))
    return 1.0 + strength * tex


def enhance(image: Image.Image, target_width: int = TARGET_WIDTH) -> Image.Image:
    """Versao de tela em qualidade de pintura. Nunca reduz abaixo da largura de origem."""
    img = image.convert("RGB")
    target = max(target_width, img.width)
    src_w = img.width
    while img.width * 2 <= target:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    if img.width != target:
        img = img.resize((target, max(1, round(img.height * target / img.width))), Image.LANCZOS)
    scale = target / src_w
    rgb = np.asarray(img, dtype=np.float32) / 255.0
    # Raio das pinceladas proporcional a ampliacao: quanto mais ampliado, mais blocos para desfazer
    r = int(min(4, max(2, round(scale * 0.9))))
    paint = kuwahara(rgb, r)
    # As janelas quadradas do Kuwahara deixam pinceladas "poligonais": um desfoque curto arredonda as bordas
    soft = Image.fromarray((np.clip(paint, 0, 1) * 255 + 0.5).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r * 0.35))
    paint = np.asarray(soft, dtype=np.float32) / 255.0
    mix = float(min(0.8, 0.45 + 0.08 * scale))
    out = mix * paint + (1 - mix) * rgb
    out = np.clip(out, 0, 1)
    pil = Image.fromarray((out * 255 + 0.5).astype(np.uint8))
    pil = pil.filter(ImageFilter.UnsharpMask(radius=max(1.0, r * 0.6), percent=70, threshold=2))
    arr = np.asarray(pil, dtype=np.float32) / 255.0
    arr = np.clip(arr * _canvas(*arr.shape[:2])[..., None], 0, 1)
    return Image.fromarray((arr * 255 + 0.5).astype(np.uint8))


def finish(image: Image.Image, target_width: int = TARGET_WIDTH, *, ai: Optional[bool] = None,
           progress=None) -> tuple:
    """Versao de tela pelo melhor caminho disponivel -> (imagem, metodo).
    - origem >= alvo: reducao Lanczos + nitidez fina (o detalhe e real; nada a inventar);
    - origem menor e modelo Real-ESRGAN instalado: IA 4x, ajuste Lanczos ao alvo e trama de tela leve;
    - sem modelo: ampliacao pictorica (enhance)."""
    from core import ai_upscale
    img = image.convert("RGB")
    if img.width >= target_width:
        out = img.resize((target_width, max(1, round(img.height * target_width / img.width))), Image.LANCZOS)
        return out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=35, threshold=2)), "original"
    if ai if ai is not None else ai_upscale.available():
        big = ai_upscale.upscale4(img, progress=progress)
        while big.width * 2 <= target_width:          # origem muito pequena: segunda passada da IA
            big = ai_upscale.upscale4(big, progress=progress)
        out = big.resize((target_width, max(1, round(big.height * target_width / big.width))), Image.LANCZOS)
        arr = np.asarray(out, dtype=np.float32) / 255.0
        arr = np.clip(arr * _canvas(*arr.shape[:2], strength=0.012)[..., None], 0, 1)
        return Image.fromarray((arr * 255 + 0.5).astype(np.uint8)), "ia"
    return enhance(img, target_width), "pictorico"
