"""Compila os shaders do fundo (desktop/qml/components/shaders/*.frag) para .qsb com o qsb do PySide6.

Os .qsb vao no git (o app nao depende do compilador em tempo de execucao). Rode depois de mudar um .frag:
    ../.venv/Scripts/python.exe scripts/build_shaders.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SHADERS = APP / "desktop" / "qml" / "components" / "shaders"


def qsb():
    exe = Path(sys.executable).parent / ("pyside6-qsb.exe" if sys.platform == "win32" else "pyside6-qsb")
    return str(exe) if exe.exists() else shutil.which("pyside6-qsb") or shutil.which("qsb")


def main():
    tool = qsb()
    if not tool:
        print("qsb nao encontrado (pip install pyside6)")
        return 1
    for src in sorted(SHADERS.glob("*.frag")):
        out = src.with_suffix(".frag.qsb")
        subprocess.run([tool, "--glsl", "100es,120,150", "--hlsl", "50", "--msl", "12", "-o", str(out), str(src)],
                       check=True)
        print("ok", out.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
