"""Confere os links da Biblioteca (core/library.py): status HTTP e titulo da pagina.

Usa a rede (nao roda no gate). Cliente generico, sem dados pessoais:
    ../.venv/Scripts/python.exe scripts/check_library_links.py
Sai com 1 se algum link nao responder 200 ou o titulo nao bater com o da ficha.
"""
import concurrent.futures as cf
import html
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.library import TOPICS


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(t).lower()).strip()


def check(ref: dict) -> tuple[dict, str]:
    req = urllib.request.Request(ref["url"], headers={"User-Agent": "Mozilla/5.0 (link-check)"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(400_000).decode("utf-8", "replace")
            if r.status != 200:
                return ref, f"HTTP {r.status}"
    except Exception as e:
        return ref, f"falhou: {getattr(e, 'code', '') or type(e).__name__}"
    m = re.search(r'<meta name="citation_title" content="([^"]+)"', body) or re.search(r"<title[^>]*>(.*?)</title>", body, re.S)
    page = _norm(m.group(1)) if m else ""
    want = _norm(re.sub(r"\s*\((?:blog|vLLM|DreamerV3)\)", "", ref["title"]).split(" — ")[0])
    key = " ".join(want.split()[:4])
    return ref, "" if key and key in page else f"titulo diferente: '{page[:80]}'"


def main() -> int:
    refs = {r["url"]: r for t in TOPICS for r in t["readings"]}.values()
    bad = 0
    with cf.ThreadPoolExecutor(8) as ex:
        for ref, err in ex.map(check, refs):
            print(("ok   " if not err else "FAIL ") + ref["url"] + ("" if not err else "  " + err))
            bad += bool(err)
    print(f"{len(list(refs)) - bad}/{len(list(refs))} conferidos")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
