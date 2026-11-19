"""Leitura local com o OCR que acompanha o Windows."""

import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)
_SCRIPT = Path(__file__).with_name("windows_ocr.ps1")


def read_image_text(image, language: str = "") -> list[dict]:
    """Devolve linhas e limites das palavras em coordenadas da imagem."""
    if sys.platform != "win32":
        return []
    shell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        with tempfile.TemporaryDirectory(prefix="aix-ocr-") as directory:
            path = Path(directory) / "image.png"
            image.save(path, format="PNG")
            command = [str(shell), "-NoProfile", "-NonInteractive", "-File", str(_SCRIPT), str(path)]
            if language:
                command.append(language)
            process = subprocess.run(command, capture_output=True, timeout=6, check=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        result = json.loads(process.stdout.decode("utf-8-sig"))
        return result if isinstance(result, list) else []
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.debug("OCR do Windows indisponível (%s)", type(exc).__name__)
        return []


def read_screen_text(region=None) -> list[dict]:
    """Lê o retângulo (esquerda, topo, direita, base), ou a tela principal."""
    from PIL import ImageGrab

    try:
        with ImageGrab.grab(bbox=region) as image:
            return read_image_text(image)
    except OSError:
        return []


def find_text_on_screen(target: str, region=None) -> dict:
    """Localiza uma sequência única de palavras e devolve coordenadas da tela."""
    needle = re.findall(r"\w+", target.casefold())
    matches = []
    if needle:
        for line in read_screen_text(region):
            tokens = [(token, word["bbox"]) for word in line["words"]
                      for token in re.findall(r"\w+", word["text"].casefold())]
            length = len(needle)
            for start in range(len(tokens) - length + 1):
                span = tokens[start:start + length]
                if [token for token, _ in span] == needle:
                    matches.append([box for _, box in span])
    if len(matches) != 1:
        return {"found": False}
    boxes = matches[0]
    x, y = region[:2] if region else (0, 0)
    left = int(min(b[0] for b in boxes)) + x
    top = int(min(b[1] for b in boxes)) + y
    right = round(max(b[2] for b in boxes)) + x
    bottom = round(max(b[3] for b in boxes)) + y
    return {"found": True, "text": target, "center": ((left + right) // 2, (top + bottom) // 2),
            "bbox": [left, top, right, bottom]}
