"""Mede as duas interfaces nesta maquina, sem abrir janela na tela e sem chamar o modelo.

- qt:   python main.py --ui qt com QT_QPA_PLATFORM=offscreen. Tempo ate a janela principal ser mostrada
        (showMaximized) e memoria do processo logo depois. E o processo inteiro: interface + nucleo.
- core: o nucleo headless da interface Tauri (scripts/smoke_packaged_core.py): tempo ate anunciar a
        porta, memoria e ida e volta dos metodos pelo WebSocket. A casca Tauri (WebView2) e medida a
        parte, com o app aberto: aqui ela nao roda.

Uso: python ai-farm-agent/scripts/measure_ui.py [--runs 3]
Saida: JSON (mediana das execucoes).
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]

QT_PROBE = r"""
import os, sys, time, threading
t0 = float(os.environ["MEASURE_T0"])
sys.argv = ["main.py", "--ui", "qt"]
sys.path.insert(0, os.environ["MEASURE_APP"])
os.chdir(os.environ["MEASURE_APP"])
from PySide6.QtGui import QWindow
_orig = QWindow.showMaximized
def _shown(self, *a):
    _orig(self, *a)
    shown = time.time() - t0
    def report():
        import psutil
        rss = psutil.Process().memory_info().rss / 1024 / 1024
        sys.__stdout__.write(f"MEASURE_QT {shown:.3f} {rss:.1f}\n")
        sys.__stdout__.flush()
        os._exit(0)
    threading.Timer(1.0, report).start()
QWindow.showMaximized = _shown
import runpy
runpy.run_path(os.path.join(os.environ["MEASURE_APP"], "main.py"), run_name="__main__")
"""


def measure_qt() -> dict:
    env = dict(os.environ)
    env.update({"QT_QPA_PLATFORM": "offscreen", "MEASURE_APP": str(APP), "MEASURE_T0": repr(time.time()),
                "PYTHONIOENCODING": "utf-8"})
    env.setdefault("ANTHROPIC_API_KEY", "sk-ant-measure-not-a-real-key")
    out = subprocess.run([sys.executable, "-c", QT_PROBE], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    for line in (out.stdout or "").splitlines():
        if line.startswith("MEASURE_QT "):
            _, shown, rss = line.split()
            return {"first_window_s": float(shown), "rss_mb": float(rss)}
    return {"error": (out.stdout + out.stderr)[-800:]}


def measure_core() -> dict:
    out = subprocess.run([sys.executable, str(APP / "scripts" / "smoke_packaged_core.py"), str(APP / "main.py"), "10"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        r = json.loads(out.stdout)
    except ValueError:
        return {"error": (out.stdout + out.stderr)[-800:]}
    return {"ready_s": r.get("ready_s"), "rss_mb": r.get("core_rss_mb"),
            "roundtrip_ms_p50": r.get("roundtrip_ms_p50"), "roundtrip_ms_p95": r.get("roundtrip_ms_p95"), "ok": r.get("ok")}


def median(rows: list, key: str):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return round(statistics.median(vals), 2) if vals else None


def main() -> int:
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 3
    qt = [measure_qt() for _ in range(runs)]
    core = [measure_core() for _ in range(runs)]
    report = {
        "runs": runs,
        "qt": {"first_window_s": median(qt, "first_window_s"), "rss_mb": median(qt, "rss_mb"),
               "errors": [r["error"] for r in qt if "error" in r][:1]},
        "tauri_core": {"ready_s": median(core, "ready_s"), "rss_mb": median(core, "rss_mb"),
                       "roundtrip_ms_p50": median(core, "roundtrip_ms_p50"),
                       "roundtrip_ms_p95": median(core, "roundtrip_ms_p95"),
                       "errors": [r["error"] for r in core if "error" in r][:1]},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
