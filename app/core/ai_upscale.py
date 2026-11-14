"""
Ampliacao 4x por IA (Real-ESRGAN x4plus, exportacao ONNX oficial da Qualcomm AI Hub, licenca BSD-3)
para os papeis de parede. Roda no computador (onnxruntime, CPU); nada sai da maquina.

O modelo fica FORA do repositorio, em %LOCALAPPDATA%/AI Farm Agent/models/real-esrgan/ (67 MB). Sem ele,
available() = False e core/wallpapers.py usa a ampliacao pictorica (core/painterly.py).

A rede recebe blocos fixos de 128x128 (0..1, NCHW) e devolve 512x512. A imagem e cortada em blocos
sobrepostos; cada bloco ampliado entra com peso que cai suavemente nas bordas (sem costura visivel).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

import numpy as np

TILE = 128
SCALE = 4
OVERLAP = 8            # sobreposicao por lado (px de entrada): menos blocos, costura ainda invisivel


def model_path() -> Optional[Path]:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AI Farm Agent" / "models" / "real-esrgan" / "model"
    found = sorted(base.rglob("real_esrgan_x4plus.onnx")) if base.is_dir() else []
    return found[0] if found else None


def available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return model_path() is not None


_session = None


def _get_session():
    global _session
    if _session is None:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, (os.cpu_count() or 4) - 1)
        _session = ort.InferenceSession(str(model_path()), opts, providers=["CPUExecutionProvider"])
    return _session


def _weights(size: int, fade: int) -> np.ndarray:
    ramp = np.ones(size, dtype=np.float32)
    if fade > 0:
        edge = (np.arange(fade, dtype=np.float32) + 0.5) / fade
        ramp[:fade] = edge
        ramp[-fade:] = edge[::-1]
    return np.outer(ramp, ramp)


def upscale4(image, progress: Optional[Callable[[int, int], None]] = None):
    """PIL RGB -> PIL RGB com 4x a largura e a altura."""
    from PIL import Image
    sess = _get_session()
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    H, W, _ = rgb.shape
    # Borda espelhada: todo bloco cabe inteiro e as bordas da foto recebem o mesmo contexto do miolo
    pad_h, pad_w = max(0, TILE - H), max(0, TILE - W)
    src = np.pad(rgb, ((OVERLAP, OVERLAP + pad_h), (OVERLAP, OVERLAP + pad_w), (0, 0)), mode="reflect")
    h, w = src.shape[:2]
    step = TILE - 2 * OVERLAP
    ys = list(range(0, max(1, h - TILE + 1), step))
    xs = list(range(0, max(1, w - TILE + 1), step))
    if ys[-1] != h - TILE:
        ys.append(h - TILE)
    if xs[-1] != w - TILE:
        xs.append(w - TILE)
    out = np.zeros((h * SCALE, w * SCALE, 3), dtype=np.float32)
    acc = np.zeros((h * SCALE, w * SCALE, 1), dtype=np.float32)
    wt = _weights(TILE * SCALE, OVERLAP * SCALE)[..., None]
    name_in = sess.get_inputs()[0].name
    total, done = len(ys) * len(xs), 0
    for y in ys:
        for x in xs:
            tile = src[y:y + TILE, x:x + TILE].transpose(2, 0, 1)[None]
            res = sess.run(None, {name_in: np.ascontiguousarray(tile)})[0][0].transpose(1, 2, 0)
            Y, X = y * SCALE, x * SCALE
            out[Y:Y + TILE * SCALE, X:X + TILE * SCALE] += res * wt
            acc[Y:Y + TILE * SCALE, X:X + TILE * SCALE] += wt
            done += 1
            if progress:
                progress(done, total)
    out /= np.maximum(acc, 1e-6)
    o = OVERLAP * SCALE
    out = out[o:o + H * SCALE, o:o + W * SCALE]
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))
