"""Prepara uma imagem para o catalogo empacotado: WebP na resolucao de tela + miniatura + paleta.

    python scripts/prepare_wallpapers.py <imagem> <id>

Antes de rodar, escreva a ficha (titulo, autor, ano, fonte, licenca) em desktop/assets/wallpapers/CREDITS.md:
sem ficha completa a imagem nao aparece no app, e o gate acusa (tests/test_wallpapers.py).
"""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from core.wallpapers import CATALOG, MAX_WIDTH, THUMB_WIDTH, _prepare, palette_of, read_credits


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    source, wid = Path(argv[0]), argv[1]
    if wid not in read_credits():
        print(f"sem ficha completa para '{wid}' em {CATALOG / 'CREDITS.md'}")
        return 1
    from PIL import Image
    from core.wallpapers import save_display
    with Image.open(source) as img:
        save_display(img, CATALOG, wid)
    with Image.open(CATALOG / f"{wid}.webp") as img:
        full_size = img.size
    with Image.open(CATALOG / f"{wid}.webp") as saved:      # paleta do arquivo final (WebP)
        pal = palette_of(saved)
    (CATALOG / f"{wid}.json").write_text(json.dumps({"palette": pal}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(wid, full_size, (CATALOG / f"{wid}.webp").stat().st_size // 1024, "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
