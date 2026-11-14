"""Gera ui/src/lib/contract.gen.ts a partir do contrato Python (sem Qt).

Fontes:
- metodos: desktop/server.py RPC_METHODS + assinaturas de desktop/bridge_core.py (nomes e tipos dos argumentos)
- eventos: tests/fixtures/bridge_contract.txt (Signals do Bridge) + eventos so da casca Tauri

Uso:
    python app/scripts/export_tauri_contract.py           # grava o arquivo
    python app/scripts/export_tauri_contract.py --check   # falha se o arquivo estiver desatualizado
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

OUT = ROOT / "ui" / "src" / "lib" / "contract.gen.ts"
FIXTURE = APP / "tests" / "fixtures" / "bridge_contract.txt"
TAURI_ONLY_EVENTS = ("windowRequest",)

_TS = {"str": "string", "bool": "boolean"}
# Nomes de argumento que o TypeScript nao aceita como rotulo de tupla em modo estrito
_RESERVED = {"private", "public", "protected", "package", "interface", "implements", "let", "static", "yield"}
# Slots que devolvem string JSON: pela rede chegam decodificados (objeto). bool e None ficam como sao.
_RET = {"str": "unknown", "bool": "boolean", "None": "null", "list": "unknown[]"}


def render() -> str:
    from desktop.bridge_core import BridgeCore
    from desktop.server import PROTOCOL_VERSION, READY_PREFIX, RPC_METHODS

    lines = [
        "// Gerado por app/scripts/export_tauri_contract.py. Nao edite a mao.",
        "// Fonte: desktop/server.py (RPC_METHODS), desktop/bridge_core.py e tests/fixtures/bridge_contract.txt.",
        "",
        f"export const PROTOCOL_VERSION = {PROTOCOL_VERSION};",
        f"export const READY_PREFIX = {READY_PREFIX!r};".replace("'", '"'),
        "",
        "/** Metodos do nucleo: nome -> [argumentos, retorno]. Mesmos nomes dos @Slots do Bridge (QML). */",
        "export interface Methods {",
    ]
    for name in sorted(RPC_METHODS):
        sig = inspect.signature(getattr(BridgeCore, name))
        params = list(sig.parameters.values())[1:]
        args = ", ".join(f"{p.name}{'_' if p.name in _RESERVED else ''}: {_TS.get(str(p.annotation), 'unknown')}" for p in params)
        ret = _RET.get(str(sig.return_annotation), "unknown")
        lines.append(f"  {name}: [args: [{args}], result: {ret}];")
    from desktop.server import HOST_SIGNATURES
    for name, (params, ret) in sorted(HOST_SIGNATURES.items()):
        args = ", ".join(f"{p}: {_TS[t]}" for p, t in params)
        lines.append(f"  /** So no host Qt (desktop/web_host.py). */")
        lines.append(f"  {name}: [args: [{args}], result: {_RET[ret]}];")
    lines += ["}", "", "export type MethodName = keyof Methods;", ""]

    events = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"signal (\w+)\((\w*)\)", line.strip())
        if m and not m.group(1).startswith("_"):
            events.append((m.group(1), {"QString": "unknown", "bool": "boolean", "": "null"}[m.group(2)]))
    events += [(e, "unknown") for e in TAURI_ONLY_EVENTS]
    lines.append("/** Eventos do nucleo: mesmos nomes dos Signals do Bridge. Payload JSON ja decodificado. */")
    lines.append("export interface Events {")
    lines += [f"  {name}: {kind};" for name, kind in sorted(events)]
    lines += ["}", "", "export type EventName = keyof Events;", ""]
    return "\n".join(lines)


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} desatualizado: rode scripts/export_tauri_contract.py")
            return 1
        print("contrato TS em dia")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"gravado {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
