"""
Catalogo de papeis de parede (E4): imagens que vem com o app (com credito e licenca em CREDITS.md)
e imagens importadas pela pessoa (camada pessoal, fora do git). De cada imagem sai uma paleta
harmonica deterministica: base, 3 luzes, destaque, cor de texto e reforco do vidro com contraste
AA medido sobre a regiao mais clara da foto.
"""

from __future__ import annotations

import colorsys
import hashlib
import io
import json
import re
import time
from pathlib import Path
from typing import Optional

APP = Path(__file__).resolve().parents[1]
CATALOG = APP / "desktop" / "assets" / "wallpapers"
CREDITS = CATALOG / "CREDITS.md"
PERSONAL_DIR = "papeis"             # dentro de <camada pessoal>/.cerebro/
MAX_IMPORT_BYTES = 15 * 1024 * 1024
MAX_WIDTH = 2560
THUMB_WIDTH = 320
ALLOWED_FORMATS = ("PNG", "JPEG", "WEBP")
MIN_TEXT_CONTRAST = 4.5
MIN_UI_CONTRAST = 3.0
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
_FIELDS = ("title", "author", "year", "source", "license")


# ── Creditos: so entra no catalogo imagem com ficha completa ──────────────────

def read_credits(path: Path = CREDITS) -> dict:
    """{id: {title, author, year, source, license}} das secoes `## <id>` com `- campo: valor`."""
    out, current = {}, None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        m = re.match(r"^## +([a-z0-9-]+)\s*$", line)
        if m:
            current = m.group(1)
            out[current] = {}
            continue
        m = re.match(r"^- +(\w+): +(.+?)\s*$", line)
        if m and current:
            out[current][m.group(1).lower()] = m.group(2)
    return {k: v for k, v in out.items() if all(v.get(f) for f in _FIELDS)}


def catalog(folder: Path = CATALOG) -> list:
    """Imagens empacotadas com credito completo (as sem ficha ficam de fora, de proposito)."""
    credits = read_credits(folder / "CREDITS.md")
    items = []
    for wid, meta in sorted(credits.items()):
        image = folder / f"{wid}.webp"
        if image.is_file():
            items.append({"id": f"catalog:{wid}", "title": meta["title"], "author": meta["author"], "year": meta["year"],
                          "license": meta["license"], "source": meta["source"], "path": str(image),
                          "thumb": str(folder / f"{wid}-thumb.webp") if (folder / f"{wid}-thumb.webp").is_file() else str(image)})
    return items


def uncredited(folder: Path = CATALOG) -> list:
    """Imagens na pasta sem ficha em CREDITS.md (o gate reprova se houver)."""
    credits = read_credits(folder / "CREDITS.md")
    return sorted(p.name for p in folder.glob("*.webp") if not p.name.endswith("-thumb.webp") and p.stem not in credits)


# ── Camada pessoal: importar ──────────────────────────────────────────────────

def personal_dir(personal: Optional[Path]) -> Optional[Path]:
    return Path(personal) / ".cerebro" / PERSONAL_DIR if personal else None


def _prepare(image, width: int):
    from PIL import Image
    img = image.convert("RGB")
    if img.width > width:
        img = img.resize((width, max(1, round(img.height * width / img.width))), Image.LANCZOS)
    return img


DISPLAY_WIDTH = 1920            # largura minima da versao de tela (Full HD)
WEBP_QUALITY = 94


def display_version(image):
    """Versao para fundo de tela: ate 2560 px; imagem menor que Full HD e ampliada em etapas de 2x com
    Lanczos e ganha uma nitidez leve proporcional (o Qt ampliaria de forma bilinear e mais borrada).
    Nao inventa detalhe: quadro pequeno fica suave, como uma pintura vista de perto."""
    from PIL import Image, ImageFilter
    img = image.convert("RGB")
    if img.width > MAX_WIDTH:
        return _prepare(img, MAX_WIDTH)
    factor = DISPLAY_WIDTH / img.width
    if factor <= 1.02:
        return img
    while img.width * 2 <= DISPLAY_WIDTH:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    img = img.resize((DISPLAY_WIDTH, max(1, round(img.height * DISPLAY_WIDTH / img.width))), Image.LANCZOS)
    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=min(90, int(40 + 15 * factor)), threshold=2))


def save_display(image, folder: Path, wid: str, ai: Optional[bool] = None) -> None:
    """Grava <wid>.webp (tela: original reduzido, IA Real-ESRGAN ou ampliacao pictorica; core/painterly.finish)
    e <wid>-thumb.webp (miniatura)."""
    from core.painterly import finish
    folder.mkdir(parents=True, exist_ok=True)
    full, _method = finish(image, ai=ai)
    full.save(folder / f"{wid}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
    _prepare(full, THUMB_WIDTH).save(folder / f"{wid}-thumb.webp", "WEBP", quality=85, method=6)


def import_image(source: Path, personal: Optional[Path]) -> dict:
    """Valida (tipo, tamanho, decodificacao), reescreve em WebP na resolucao de tela + miniatura e
    grava a paleta. Nada e copiado antes de validar; nada vai para o repositorio."""
    from PIL import Image, UnidentifiedImageError
    target = personal_dir(personal)
    if target is None:
        raise PermissionError("camada pessoal indisponivel")
    source = Path(source)
    if not source.is_file():
        raise ValueError("arquivo nao encontrado")
    if source.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("imagem grande demais (maximo 15 MB)")
    try:
        with Image.open(source) as img:
            if img.format not in ALLOWED_FORMATS:
                raise ValueError(f"formato nao aceito ({img.format or 'desconhecido'}): use PNG, JPG ou WebP")
            img.load()
            if img.width < 320 or img.height < 200:
                raise ValueError("imagem pequena demais (minimo 320 x 200)")
            full = img.convert("RGB")
    except UnidentifiedImageError:
        raise ValueError("isto nao e uma imagem valida")
    wid = time.strftime("%Y%m%d-%H%M%S") + "-" + hashlib.sha1(source.read_bytes()).hexdigest()[:8]
    target.mkdir(parents=True, exist_ok=True)
    save_display(full, target, wid, ai=False)   # na tela: rapido (a IA leva minutos na CPU; use scripts/prepare_wallpapers.py)
    with Image.open(target / f"{wid}.webp") as saved:      # paleta do arquivo final (WebP), nao da fonte
        pal = palette_of(saved)
    (target / f"{wid}.json").write_text(json.dumps({"title": source.stem[:60], "palette": pal}, ensure_ascii=False), encoding="utf-8")
    return {"id": f"personal:{wid}", "title": source.stem[:60], "path": str(target / f"{wid}.webp"),
            "thumb": str(target / f"{wid}-thumb.webp"), "palette": pal}


def personal(personal_root: Optional[Path]) -> list:
    folder = personal_dir(personal_root)
    if not folder or not folder.is_dir():
        return []
    items = []
    for meta in sorted(folder.glob("*.json"), reverse=True):
        wid = meta.stem
        if not (folder / f"{wid}.webp").is_file():
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        items.append({"id": f"personal:{wid}", "title": data.get("title") or wid, "author": "", "year": "", "license": "sua",
                      "source": "", "path": str(folder / f"{wid}.webp"),
                      "thumb": str(folder / f"{wid}-thumb.webp") if (folder / f"{wid}-thumb.webp").is_file() else str(folder / f"{wid}.webp")})
    return items


def remove_personal(wid: str, personal_root: Optional[Path]) -> bool:
    folder = personal_dir(personal_root)
    if not folder or not _ID.match(wid or ""):
        return False
    gone = False
    for name in (f"{wid}.webp", f"{wid}-thumb.webp", f"{wid}.json"):
        p = folder / name
        if p.is_file():
            p.unlink()
            gone = True
    return gone


def resolve(wallpaper: str, personal_root: Optional[Path]) -> Optional[dict]:
    """'catalog:<id>' | 'personal:<id>' -> item com caminho e paleta, ou None."""
    if not wallpaper or ":" not in wallpaper:
        return None
    kind, wid = wallpaper.split(":", 1)
    if not _ID.match(wid):
        return None
    items = catalog() if kind == "catalog" else personal(personal_root) if kind == "personal" else []
    for item in items:
        if item["id"] == wallpaper:
            item = dict(item)
            item["palette"] = palette_for(item)
            return item
    return None


def palette_for(item: dict) -> dict:
    """Paleta gravada ao lado da imagem (calculada uma vez; deterministica)."""
    meta = Path(item["path"]).with_suffix(".json")
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        if isinstance(data.get("palette"), dict) and data["palette"].get("tones") and "min_dim" in data["palette"]:
            return data["palette"]
    except (OSError, ValueError):
        data = {}
    from PIL import Image
    with Image.open(item["path"]) as img:
        pal = palette_of(img)
    try:
        data["palette"] = pal
        meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return pal


# ── Paleta harmonica (k-means deterministico) ─────────────────────────────────

def _hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in rgb)


def _lum(rgb) -> float:
    lin = [(c / 255) / 12.92 if c / 255 <= 0.03928 else (((c / 255) + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _over(fg, alpha, bg):
    return tuple(fg[i] * alpha + bg[i] * (1 - alpha) for i in range(3))


def _kmeans(pixels, k=6, rounds=12):
    """Centroides iniciais fixos (pixels em posicoes espacadas): mesma imagem, mesma paleta."""
    centers = [pixels[i * len(pixels) // k] for i in range(k)]
    for _ in range(rounds):
        buckets = [[] for _ in range(k)]
        for p in pixels:
            best = min(range(k), key=lambda i: sum((p[j] - centers[i][j]) ** 2 for j in range(3)))
            buckets[best].append(p)
        for i, b in enumerate(buckets):
            if b:
                centers[i] = tuple(sum(p[j] for p in b) / len(b) for j in range(3))
    sizes = [len(b) for b in buckets]
    return [(centers[i], sizes[i]) for i in range(k) if sizes[i]]


def _adjust(rgb, *, sat=None, val=None):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    s = s if sat is None else sat(s)
    v = v if val is None else val(v)
    return tuple(c * 255 for c in colorsys.hsv_to_rgb(h, min(1, max(0, s)), min(1, max(0, v))))


def palette_of(image) -> dict:
    """{'mode','base','tones','accent','text','glass_boost','bright'}: tudo derivado da imagem."""
    from PIL import Image
    small = image.convert("RGB")
    small.thumbnail((64, 64), Image.BILINEAR)
    pixels = list(small.getdata())
    clusters = sorted(_kmeans(pixels), key=lambda c: -c[1])
    colors = [c[0] for c in clusters]
    # Base: a cor escura dominante, mais escura ainda (o fundo do app)
    base = _adjust(min(colors, key=_lum), sat=lambda s: min(s, 0.45), val=lambda v: min(v, 0.12))
    # Luzes: as 3 cores mais saturadas e distintas, trazidas para o tom medio do tema escuro
    by_sat = sorted(colors, key=lambda c: -colorsys.rgb_to_hsv(*(x / 255 for x in c))[1])
    lights = []
    for c in by_sat:
        if all(sum((c[j] - o[j]) ** 2 for j in range(3)) > 40 ** 2 for o in lights):
            lights.append(c)
        if len(lights) == 3:
            break
    while len(lights) < 3:
        lights.append(lights[-1] if lights else base)
    tones = [_adjust(c, sat=lambda s: max(0.35, min(s, 0.75)), val=lambda v: max(0.30, min(v, 0.52))) for c in lights]
    # Destaque: a cor mais saturada, clareada ate ter contraste 3:1 sobre o vidro escuro
    glass = (18, 18, 26)
    accent = _adjust(by_sat[0], sat=lambda s: max(0.55, s), val=lambda v: max(0.75, v))
    for _ in range(12):
        if contrast(accent, glass) >= MIN_UI_CONTRAST:
            break
        accent = _adjust(accent, val=lambda v: min(1, v + 0.05), sat=lambda s: max(0.3, s - 0.05))
    # Vidro: reforco de opacidade ate o texto claro ler sobre a regiao mais clara da foto
    bright_pixels = sorted(pixels, key=_lum)[-max(1, len(pixels) // 10):]
    bright = tuple(sum(p[j] for p in bright_pixels) / len(bright_pixels) for j in range(3))
    text = (244, 244, 247)
    boost = 0.0
    while boost < 0.3 and contrast(text, _over(glass, 0.66 + boost, bright)) < MIN_TEXT_CONTRAST:
        boost = round(boost + 0.02, 2)
    # Texto solto sobre a foto (titulos, sugestoes): o escurecimento minimo para o texto secundario do tema
    # escuro ter AA sobre o quarto mais claro da imagem; e, no tema claro, o veu branco minimo para o texto
    # escuro ler sobre o quarto mais escuro. O escurecimento escolhido pela pessoa so pode ser maior.
    ordered = sorted(pixels, key=_lum)
    q = max(1, len(ordered) // 4)
    light_q = tuple(sum(p[j] for p in ordered[-q:]) / q for j in range(3))
    dark_q = tuple(sum(p[j] for p in ordered[:q]) / q for j in range(3))
    min_dim = 0.0
    while min_dim < 0.85 and contrast((198, 198, 207), _over((0, 0, 0), min_dim, light_q)) < MIN_TEXT_CONTRAST:
        min_dim = round(min_dim + 0.02, 2)
    min_veil = 0.0
    while min_veil < 0.9 and contrast((29, 29, 31), _over((255, 255, 255), min_veil, dark_q)) < MIN_TEXT_CONTRAST:
        min_veil = round(min_veil + 0.02, 2)
    return {"mode": "escuro", "base": _hex(base), "tones": [_hex(t) for t in tones], "accent": _hex(accent),
            "text": _hex(text), "glass_boost": boost, "bright": _hex(bright),
            "min_dim": min_dim, "min_veil": min_veil}
