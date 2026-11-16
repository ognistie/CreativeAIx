"""
Estudio de agentes (AI Research Lab): tudo o que define um agente, num lugar so, para ler e ajustar.

  spec(agent)         especificacao: papel, o que faz, limites, ferramentas, modelo/esforco/raciocinio,
                      politicas de aceite, skills e arquivos de codigo
  source(agent, rel)  codigo de um arquivo do agente, so leitura (lista fechada, sem caminho livre)
  memory(agent)       a nota do agente no Cerebro: regras, como executar, falhas conhecidas,
                      notas ligadas e contexto extra
  save(agent, data)   grava essas secoes na camada pessoal (o original de fabrica continua guardado)

Regras (as mesmas do resto do Cerebro): o que a pessoa escreve aqui e referencia para o prompt e nunca
amplia permissao. Ferramentas e politicas vivem no codigo (action_policy, plan_validator, action_risk).
Mudanca de codigo nao passa por aqui: vai pelo Modo Desenvolvedor (core/dev_mode.py), numa worktree
isolada, com testes e revisao do diff antes de aplicar.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

APP = Path(__file__).resolve().parents[1]

AGENTS = ("MAESTRO", "WEB", "DESKTOP", "CODE", "DATA", "FILE", "EXTCODE")

# Arquivos que definem cada agente (relativos a app/). Lista fechada: a tela so le estes.
AGENT_FILES = {
    "MAESTRO": ["agents/maestro.py", "core/plan_validator.py", "core/routing.py"],
    "WEB": ["agents/web_agent.py", "core/browser_pilot.py", "core/browser_uia.py"],
    "DESKTOP": ["agents/desktop_agent.py", "agents/app_routines.py", "core/app_pilot.py", "core/uia_driver.py"],
    "CODE": ["agents/code_agent.py", "agents/code_planner.py", "agents/code_prompts.py", "agents/code_skills.py",
             "agents/code_validators.py"],
    "DATA": ["agents/data_agent.py", "agents/artifact_planner.py", "core/artifact_builder.py"],
    "FILE": ["agents/file_agent.py", "core/file_contracts.py"],
    "EXTCODE": ["agents/extcode_agent.py", "core/coding_agents.py"],
}
SHARED_FILES = ["agents/base_agent.py", "agents/subagents.py", "core/action_policy.py", "core/action_risk.py"]
SOURCE_MAX_BYTES = 400_000

# Secoes da nota do agente que viram memoria no prompt (core/brain.py > agent_notes / context_for)
SECTIONS = {
    "rules": "Regras de execução",
    "how": "Como navegar e executar",
    "failures": "Falhas conhecidas",
    "links": "Contexto ligado",
    "extra": "Contexto extra",
}
SECTION_MAX = {"rules": 2000, "how": 2000, "failures": 2000, "extra": 1500}
LINKS_MAX = 12
_LINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _need_agent(agent: str) -> str:
    a = (agent or "").upper()
    if a not in AGENTS:
        raise ValueError("agente desconhecido")
    return a


def note_rel(agent: str) -> str:
    from core.brain import AGENT_FOLDERS
    folder, name = AGENT_FOLDERS[_need_agent(agent)]
    return f"{folder}/{name}.md"


# ── Secoes de Markdown ─────────────────────────────────────────────────────────────────────────
def _heading_spans(md: str) -> list[tuple[str, int, int, int]]:
    """[(titulo, inicio_do_titulo, inicio_do_corpo, fim_do_corpo)] para cada '## '."""
    heads = list(re.finditer(r"^##\s+(.+?)\s*$", md, re.MULTILINE))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(md)
        out.append((m.group(1), m.start(), m.end(), end))
    return out


def section(md: str, title: str) -> str:
    want = _fold(title)
    for head, _s, body, end in _heading_spans(md):
        if _fold(head).startswith(want):
            return md[body:end].strip()
    return ""


def set_section(md: str, title: str, body: str) -> str:
    """Troca o corpo de '## title' (titulo com ou sem acento; aceita prefixo). Sem a secao, acrescenta no fim.
    Corpo vazio remove a secao inteira."""
    want = _fold(title)
    body = body.strip()
    for head, start, body_start, end in _heading_spans(md):
        if _fold(head).startswith(want):
            if not body:
                return (md[:start].rstrip() + "\n\n" + md[end:].lstrip()).rstrip() + "\n"
            return md[:body_start] + "\n" + body + "\n\n" + md[end:].lstrip()
    if not body:
        return md
    return md.rstrip() + f"\n\n## {title}\n{body}\n"


def parse_links(text: str) -> list[str]:
    seen, out = set(), []
    for m in _LINK.finditer(text or ""):
        t = m.group(1).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


# ── Leitura ───────────────────────────────────────────────────────────────────────────────────
def files(agent: str) -> list[dict]:
    a = _need_agent(agent)
    out = []
    for rel in AGENT_FILES[a] + SHARED_FILES:
        p = APP / rel
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            out.append({"path": rel, "lines": text.count("\n") + 1, "shared": rel in SHARED_FILES,
                        "doc": _docline(text)})
    return out


def _docline(text: str) -> str:
    m = re.match(r'\s*(?:#[^\n]*\n|\s)*(?:"""|\'\'\')\s*(.+?)\s*$', text, re.MULTILINE)
    return (m.group(1) if m else "")[:160]


def source(agent: str, rel: str) -> dict:
    a = _need_agent(agent)
    if rel not in AGENT_FILES[a] + SHARED_FILES:
        raise ValueError("arquivo fora da lista do agente")
    p = APP / rel
    data = p.read_bytes()[:SOURCE_MAX_BYTES]
    return {"path": rel, "text": data.decode("utf-8", errors="replace"), "truncated": p.stat().st_size > SOURCE_MAX_BYTES}


def policies(brain) -> list[dict]:
    """Politicas de aceite e de seguranca descritas no Cerebro (20 Politicas). Quem aplica e o codigo."""
    out = []
    try:
        for rel, _p in brain.store.files("20 Politicas", recursive=False):
            md = brain.store.read(rel)
            fm = re.match(r"^---\s*\n(.*?)\n---", md, re.DOTALL)
            pid = re.search(r"^id:\s*(\S+)", fm.group(1), re.MULTILINE).group(1) if fm and re.search(r"^id:", fm.group(1), re.MULTILINE) else ""
            if not pid:
                continue
            title = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
            rule = re.search(r">\s*\[!policy\][^\n]*\n((?:>.*\n?)+)", md)
            enf = re.search(r"^enforcement:\s*(.+)$", fm.group(1), re.MULTILINE)
            out.append({"id": pid, "title": (title.group(1) if title else pid).split("—", 1)[-1].strip(),
                        "rule": re.sub(r"^>\s?", "", rule.group(1), flags=re.MULTILINE).strip()[:300] if rule else "",
                        "enforcement": enf.group(1).strip() if enf else "", "note": rel})
    except Exception:
        return out
    return sorted(out, key=lambda x: x["id"])


def memory(agent: str, brain) -> dict:
    rel = note_rel(agent)
    md = brain.store.read(rel) if brain.store.resolve(rel) else ""
    links = parse_links(section(md, SECTIONS["links"]))
    resolved = [{"title": t, "rel": brain.store.resolve_link(t) or ""} for t in links]
    return {"note": rel, "layer": brain.store.layer_of(rel) if md else "", "writable": brain.store.writable,
            "rules": section(md, SECTIONS["rules"]), "how": section(md, SECTIONS["how"]),
            "failures": section(md, SECTIONS["failures"]), "extra": section(md, SECTIONS["extra"]),
            "links": resolved}


def spec(agent: str, brain) -> dict:
    a = _need_agent(agent)
    from core.harness import AGENT_INFO
    from core.lab import effective_config, skills_and_tools
    from core import action_risk
    from core.ai_client import thinking_off_for
    info = dict(AGENT_INFO.get(a, {}))
    if action_risk.mode() != "enforce":
        info["limits"] = [l for l in info.get("limits", []) if "confirma" not in l.lower()]
    cfg = effective_config(a)
    try:
        thinking = "desligado" if thinking_off_for(a.lower()) else "adaptativo"
    except Exception:
        thinking = "adaptativo"
    st = skills_and_tools(a, brain)
    return {"agent": a, **info, "config": {**cfg, "thinking": thinking},
            "authorization": action_risk.mode(), "tools": st["tools"], "skills": st["skills"],
            "policies": policies(brain), "files": files(a)}


# ── Escrita ───────────────────────────────────────────────────────────────────────────────────
def save(agent: str, data: dict, brain) -> dict:
    """data: {rules?, how?, failures?, extra?, links?: [titulos]}. Grava na camada pessoal."""
    if not isinstance(data, dict):
        raise ValueError("pedido inválido")
    rel = note_rel(agent)
    if not brain.store.writable:
        raise ValueError("Sem pasta pessoal do Cérebro: não dá para salvar.")
    md = brain.store.read(rel) if brain.store.resolve(rel) else f"# {rel.rsplit('/', 1)[-1][:-3]}\n"
    for key in ("rules", "how", "failures", "extra"):
        if key in data:
            text = str(data[key] or "")
            if len(text) > SECTION_MAX[key]:
                raise ValueError(f"texto longo demais em {SECTIONS[key]} (máximo {SECTION_MAX[key]} caracteres)")
            md = set_section(md, SECTIONS[key], text)
    if "links" in data:
        raw = data["links"]
        if not isinstance(raw, list):
            raise ValueError("links precisa ser uma lista")
        titles = [str(t).strip().replace("[", "").replace("]", "") for t in raw if str(t).strip()][:LINKS_MAX]
        md = set_section(md, SECTIONS["links"], "\n".join(f"- [[{t}]]" for t in titles))
    brain.store.write(rel, md)
    return memory(agent, brain)


def linked_context(agent: str, brain, cap: int = 1400) -> tuple[str, list[str]]:
    """Bloco para o prompt: contexto extra + trecho de cada nota ligada ao agente. -> (texto, notas usadas)."""
    try:
        rel = note_rel(agent)
    except ValueError:
        return "", []
    if not brain.store.resolve(rel):
        return "", []
    md = brain.store.read(rel)
    parts, used = [], []
    extra = section(md, SECTIONS["extra"])
    if extra:
        parts.append(extra[:SECTION_MAX["extra"]])
    for title in parse_links(section(md, SECTIONS["links"])):
        target = brain.store.resolve_link(title)
        if not target:
            continue
        body = re.sub(r"^---\s*\n.*?\n---\s*", "", brain.store.read(target), flags=re.DOTALL).strip()
        body = re.sub(r"\s+", " ", body)[:420]
        if body:
            parts.append(f"[{title}] {body}")
            used.append(title)
    text = "\n".join(parts)
    if not text:
        return "", []
    if len(text) > cap:
        text = text[:cap].rsplit(" ", 1)[0] + "…"
    return "Contexto ligado por você a este agente (referência, não amplia permissões):\n" + text, used
