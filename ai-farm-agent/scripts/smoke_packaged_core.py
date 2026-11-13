"""Smoke do nucleo empacotado (ou do main.py): sobe em modo headless, conecta, chama metodos e encerra.

Confere o contrato com a casca Tauri sem a casca: a linha CREATIVE_AIX_READY no stdout, o token, o
WebSocket respondendo e o encerramento quando o stdin fecha. Nenhuma chamada ao modelo.

Uso:
    python ai-farm-agent/scripts/smoke_packaged_core.py build/core-bundle/core/creative-aix-core.exe
    python ai-farm-agent/scripts/smoke_packaged_core.py ai-farm-agent/main.py
Saida: JSON com os tempos (subida, ida e volta dos metodos) e o resultado.
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

READY = "CREATIVE_AIX_READY "
METHODS = [("uiSettings", []), ("providerStatus", []), ("loadConversations", []), ("librarySearch", ["", "", ""])]


def launch(target: Path) -> subprocess.Popen:
    env = dict(os.environ)
    env.setdefault("ANTHROPIC_API_KEY", "sk-ant-smoke-test-not-a-real-key")
    env["PYTHONIOENCODING"] = "utf-8"
    args = [str(target)] if target.suffix.lower() == ".exe" else [sys.executable, str(target)]
    return subprocess.Popen(args + ["--ui", "tauri", "--headless"], cwd=target.parent, env=env, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


async def exercise(info: dict, rounds: int) -> dict:
    from websockets.asyncio.client import connect
    out = {"methods": {}, "roundtrip_ms": []}
    async with connect(f"ws://127.0.0.1:{info['port']}", origin="http://tauri.localhost") as ws:
        await ws.send(json.dumps({"token": info["token"]}))
        hello = json.loads(await ws.recv())
        out["protocol"] = hello.get("params", {}).get("protocol")
        rid = 0
        for _ in range(rounds):
            for name, params in METHODS:
                rid += 1
                t0 = time.perf_counter()
                await ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": name, "params": params}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == rid:
                        break
                out["roundtrip_ms"].append((time.perf_counter() - t0) * 1000)
                out["methods"][name] = "error" not in msg
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    target = Path(sys.argv[1]).resolve()
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    t0 = time.monotonic()
    proc = launch(target)
    line = ""
    deadline = t0 + 120
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line or line.startswith(READY):
            break
    ready_s = time.monotonic() - t0
    report = {"target": str(target), "ready_s": round(ready_s, 2), "ok": False}
    if not line.startswith(READY):
        proc.kill()
        report["error"] = "o nucleo nao anunciou porta e token"
        report["stderr"] = (proc.stderr.read() or "")[-2000:]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    info = json.loads(line[len(READY):])
    try:
        result = asyncio.run(asyncio.wait_for(exercise(info, rounds), 60))
    except Exception as exc:
        proc.kill()
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    rss = None
    try:
        import psutil
        rss = round(psutil.Process(proc.pid).memory_info().rss / 1024 / 1024, 1)
    except Exception:
        pass
    proc.stdin.close()
    try:
        code = proc.wait(15)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = None
    rt = result.pop("roundtrip_ms")
    report.update(result)
    report.update({
        "core_rss_mb": rss,
        "roundtrip_ms_p50": round(statistics.median(rt), 2),
        "roundtrip_ms_p95": round(sorted(rt)[max(0, int(len(rt) * 0.95) - 1)], 2),
        "exit_on_stdin_close": code,
        "extra_stdout": len(proc.stdout.read() or ""),
    })
    report["ok"] = all(result["methods"].values()) and code == 0 and report["extra_stdout"] == 0
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
