"""
Planos aprendidos: quando um tipo de pedido já deu certo várias vezes com o MESMO plano, o app passa a executá-lo
sem chamar o modelo do Maestro. É a camada de auto-aperfeiçoamento: cada execução bem-sucedida ensina, cada falha
desensina.

    "pesquisa receita de bolo no google"     ─┐
    "pesquisa preço do dólar no google"      ─┼─ molde "pesquisa ⟨consulta⟩ no google" + plano com ⟨consulta⟩
    "pesquisa horário do jogo no google"     ─┘   3 sucessos com o mesmo plano → promovido
    "pesquisa previsão do tempo no google"   ──── plano montado do molde, sem chamar o modelo

Regras (código, não prompt):
- Aprende só o ROTEAMENTO do Maestro (quais agentes, com quais parâmetros). Os agentes, o validador de plano, a
  política por agente e a porta de efeitos continuam valendo em toda execução: nada aprendido pula confirmação.
- Só vira molde o plano cujo conteúdo (texto, mensagem, busca, URL, destinatário...) vem inteiro do pedido. Se o
  modelo inventou ou compôs conteúdo, o plano não é aprendido: aquilo exige o modelo de novo.
- Pedido que depende da conversa ("isso", "de novo", "o segundo") nunca usa nem ensina molde.
- Promoção: PROMOTE_AFTER sucessos seguidos com o mesmo plano. Uma falha zera a sequência; uma falha de um plano
  já promovido o rebaixa; FAIL_LIMIT falhas o bloqueiam para sempre (até a pessoa esquecer o molde).
- Mudou o prompt do Maestro ou as políticas: os moldes antigos ficam velhos e são reaprendidos.
- Estado local em app/memory/learned_plans.json (fora do git), com dados pessoais redigidos.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

# Variavel de ambiente: leva a loja para outro lugar (medicoes e testes nao tocam no estado da pessoa)
STORE = Path(os.environ.get("CREATIVE_AIX_LEARNED_PLANS") or
             Path(__file__).resolve().parents[1] / "memory" / "learned_plans.json")
PROMOTE_AFTER = 3
MIN_TEMPLATE_WORDS = 3     # "fazer", "abre isso": curto demais para ser um tipo de pedido
FAIL_LIMIT = 2
MAX_ENTRIES = 300
_lock = threading.Lock()

# Campos de parâmetro que carregam CONTEÚDO da pessoa: precisam vir do pedido
CONTENT_KEYS = ("text", "message", "query", "url", "start_url", "person", "to", "subject", "content", "filename",
                "name", "path", "goal", "folder", "prompt")
# Slots extraídos do pedido (do mais específico ao mais geral)
_QUOTED = re.compile(r"[\"“”‘’']([^\"“”‘’']{1,300})[\"“”‘’']")
_URL = re.compile(r"\bhttps?://[^\s\"'<>]+", re.I)
_DOMAIN = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com\.br|gov\.br|org\.br|com|net|org|io|br|dev|app)\b", re.I)
_PATH = re.compile(r"\b[a-z]:\\[^\s\"'<>]+", re.I)
_NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w])")
# "pesquisa <consulta> no google/youtube": a consulta é o slot
_SEARCH = re.compile(r"^(?P<verb>(?:pesquis|procur|busc)\w*)(?:\s+(?:por|sobre))?\s+(?P<q>.+?)"
                     r"(?P<site>\s+(?:no|na|em)\s+(?:google|youtube|bing|mercado livre|wikipedia))?$", re.I)
_FILLER = re.compile(r"^(?:(?:por favor|agora|ai|entao|ei|oi|tipo)[\s,]+)+")


def _norm(text: str) -> str:
    from core.lexicon import norm
    return " ".join(norm(text or "").replace(",", " ").split()).strip(" .!?")


def depends_on_context(task: str) -> bool:
    """Pedido que aponta para a conversa ("isso", "de novo", "o segundo"): não usa nem ensina molde."""
    from core.followup import _FOLLOW
    return bool(_FOLLOW.search(_norm(task)))


def extract(task: str) -> tuple[str, dict]:
    """-> (molde normalizado com ⟨slots⟩, {slot: valor como foi dito})."""
    raw = (task or "").strip()
    slots: dict = {}
    n = [0]

    def take(kind: str, value: str, text: str) -> str:
        n[0] += 1
        name = f"{kind}{n[0]}"
        slots[name] = value
        return text.replace(value, f" ⟨{name}⟩ ", 1)

    text = raw
    for match in list(_QUOTED.finditer(raw)):
        text = take("texto", match.group(1), text)
    for pattern, kind in ((_URL, "url"), (_PATH, "caminho")):
        for match in list(pattern.finditer(text)):
            text = take(kind, match.group(0), text)
    for match in list(_DOMAIN.finditer(text)):
        if "⟨" not in match.group(0):
            text = take("site", match.group(0), text)
    # A normalizacao tira simbolos: os slots atravessam como "qqnomeqq" e voltam a ser ⟨nome⟩
    plain = _FILLER.sub("", _norm(re.sub(r"⟨(\w+)⟩", r"qq\1qq", text)))
    plain = re.sub(r"qq([a-z]+\d+)qq", r"⟨\1⟩", plain)
    search = _SEARCH.match(plain)
    if search and "⟨" not in search.group("q"):
        query_norm = search.group("q")
        original = _find_original(raw, query_norm)
        if original:
            slots[f"consulta{n[0] + 1}"] = original
            n[0] += 1
            plain = plain[:search.start("q")] + f"⟨consulta{n[0]}⟩" + plain[search.end("q"):]
    for match in reversed(list(_NUMBER.finditer(plain))):
        n[0] += 1
        slots[f"numero{n[0]}"] = match.group(0)
        plain = plain[:match.start()] + f"⟨numero{n[0]}⟩" + plain[match.end():]
    return " ".join(plain.split()), slots


def _find_original(raw: str, normalized: str) -> str:
    """O trecho do pedido original (com acentos e maiúsculas) que corresponde ao trecho normalizado."""
    words = normalized.split()
    tokens = re.findall(r"\S+", raw)
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens) + 1):
            if _norm(" ".join(tokens[i:j])) == normalized:
                return " ".join(tokens[i:j]).strip(" .!?,")
            if len(_norm(" ".join(tokens[i:j])).split()) > len(words):
                break
    return ""


def _key(template: str) -> str:
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:16]


def planner_version() -> str:
    """Muda quando o prompt do Maestro ou as políticas de plano mudam: moldes antigos ficam velhos."""
    try:
        from agents.maestro import PROMPT
        from core import plan_validator
        source = PROMPT + Path(plan_validator.__file__).read_text(encoding="utf-8")
    except Exception:
        source = ""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


# ── molde do plano ─────────────────────────────────────────────────────────────────────────

def _bounded(value: str) -> str:
    """Padrao do valor como trecho inteiro: sem letra ou numero colado antes ou depois."""
    return r"(?<![\w])" + re.escape(value) + r"(?![\w])"


def _fold(text: str) -> str:
    """Minusculas sem acento, letra a letra (mesmo comprimento do texto em NFC)."""
    import unicodedata
    out = []
    for ch in text:
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        out.append((base[:1] or ch).lower())
    return "".join(out)


def _replace_folded(text: str, value: str, placeholder: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFC", text)
    folded, needle = _fold(text), _fold(unicodedata.normalize("NFC", value))
    if not needle.strip() or len(folded) != len(text):
        return text
    for match in reversed(list(re.finditer(_bounded(needle), folded))):
        text = text[:match.start()] + placeholder + text[match.end():]
    return text


def _replace_slots(value, slots: dict):
    if isinstance(value, str):
        from urllib.parse import quote, quote_plus
        out = value
        for name, val in sorted(slots.items(), key=lambda kv: -len(kv[1])):
            # Dentro de URL o valor aparece codificado ("receita+de+bolo"): vira ⟨nome|url⟩ e volta codificado
            if not val:
                continue
            for encoded in {quote_plus(val), quote(val)} - {val}:
                out = re.sub(_bounded(encoded), f"⟨{name}|url⟩", out)
            # Palavra inteira: o valor "a" nao pode virar slot dentro de "pesquisar"
            out = re.sub(_bounded(val), f"⟨{name}⟩", out, flags=re.I)
            # O modelo as vezes tira acentos ("tenis" para "tênis"): procura no texto sem acento, que tem o mesmo
            # tamanho letra a letra, e troca o trecho correspondente do original
            out = _replace_folded(out, val, f"⟨{name}⟩")
        return out
    if isinstance(value, list):
        return [_replace_slots(v, slots) for v in value]
    if isinstance(value, dict):
        return {k: _replace_slots(v, slots) for k, v in value.items()}
    return value


def _fill(value, slots: dict):
    if isinstance(value, str):
        from urllib.parse import quote_plus

        def put(m):
            val = slots.get(m.group(1))
            if val is None:
                return m.group(0)
            return quote_plus(val) if m.group(2) == "|url" else val
        return re.sub(r"⟨(\w+)(\|url)?⟩", put, value)
    if isinstance(value, list):
        return [_fill(v, slots) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, slots) for k, v in value.items()}
    return value




def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", _norm(re.sub(r"⟨[\w|]+⟩", " ", text))))


def _content_from_request(key: str, value: str, allowed: set) -> bool:
    """O valor de um campo de conteúdo vem inteiro do pedido (slots ou palavras ditas)?"""
    if key in ("url", "start_url") and re.match(r"https?://", value, re.I):
        from urllib.parse import parse_qsl, urlsplit
        parts = urlsplit(value)
        # Valores da busca na URL: so slots. O caminho e estrutura do site ("/jm/search"): se o modelo inventasse
        # algo ali, mudaria a cada pedido e o molde nunca juntaria os sucessos iguais exigidos para promover.
        return not any(_words(v) for _, v in parse_qsl(parts.query, keep_blank_values=True))
    return not (_words(value) - allowed)


def plan_template(task: str, plan: dict) -> Optional[dict]:
    """Molde do plano do Maestro, ou None se o plano não pode ser aprendido (conteúdo que não vem do pedido)."""
    subtasks = plan.get("subtasks") or []
    if not subtasks or plan.get("fast_path") or plan.get("needs_clarification") or plan.get("error"):
        return None
    template, slots = extract(task)
    if len(template.split()) < MIN_TEMPLATE_WORDS:
        return None
    allowed = _words(template)
    clean = []
    for sub in subtasks:
        if not isinstance(sub, dict) or not isinstance(sub.get("params", {}), dict):
            return None
        item = {"agent": str(sub.get("agent", "")).upper(), "task": _replace_slots(str(sub.get("task", "")), slots),
                "params": _replace_slots(copy.deepcopy(sub.get("params") or {}), slots)}
        if sub.get("depends_on") is not None:
            item["depends_on"] = sub["depends_on"]
        for key in CONTENT_KEYS:
            value = item["params"].get(key)
            if value in (None, "", [], {}):
                continue
            if not isinstance(value, str):
                return None
            if not _content_from_request(key, value, allowed):
                return None          # conteúdo que o modelo criou ou completou: não dá para repetir sem ele
        clean.append(item)
    return {"subtasks": clean, "skills": list(plan.get("skills") or [])}


def _signature(template_plan: dict) -> str:
    """O que define o plano: agentes, parametros e dependencias. A redacao da task ("Mercado Livre" x "mercado
    livre") e as skills citadas variam entre chamadas do modelo sem mudar o que e feito (medido com o Maestro real:
    planos iguais nunca juntavam 3 sucessos por causa disso)."""
    def canon(value):
        if isinstance(value, str):
            return _fold(" ".join(value.split()))
        if isinstance(value, dict):
            return {k: canon(v) for k, v in value.items()}
        if isinstance(value, list):
            return [canon(v) for v in value]
        return value
    core = [{"agent": s.get("agent"), "task": canon(s.get("task", "")), "params": canon(s.get("params") or {}),
             "depends_on": s.get("depends_on")} for s in template_plan.get("subtasks", [])]
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


# ── armazenamento ──────────────────────────────────────────────────────────────────────────

def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("entries"), dict) else {"entries": {}}
    except (OSError, ValueError):
        return {"entries": {}}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = data["entries"]
    if len(entries) > MAX_ENTRIES:
        keep = sorted(entries.items(), key=lambda kv: kv[1].get("last", 0), reverse=True)[:MAX_ENTRIES]
        data["entries"] = dict(keep)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".learned_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _enabled() -> bool:
    try:
        from core.config import get_config
        return bool(get_config().get("learning.autopilot", True))
    except Exception:
        return True


def _promote_after() -> int:
    try:
        from core.config import get_config
        return max(2, int(get_config().get("learning.promote_after", PROMOTE_AFTER)))
    except Exception:
        return PROMOTE_AFTER


class LearnedPlans:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or STORE)

    # Leitura: plano pronto para um pedido novo, se o molde já foi promovido
    def plan_for(self, task: str) -> Optional[dict]:
        if not _enabled() or depends_on_context(task):
            return None
        template, slots = extract(task)
        with _lock:
            entry = _load(self.path)["entries"].get(_key(template))
        if not entry or entry.get("status") != "promoted" or entry.get("planner") != planner_version():
            return None
        if set(re.findall(r"⟨(\w+)(?:\|url)?⟩", json.dumps(entry["plan"], ensure_ascii=False))) - set(slots):
            return None              # o molde pede um slot que este pedido não tem
        plan = _fill(copy.deepcopy(entry["plan"]), slots)
        for sub in plan["subtasks"]:
            sub["original_task"] = task
        from core.plan_validator import validate_plan
        check = validate_plan(task, plan)
        if not check.approved:
            return None
        plan.update(analysis=f"Plano aprendido (sem IA): já deu certo {entry['successes']} vezes neste tipo de pedido",
                    fast_path="aprendido", learned_key=_key(template),
                    validation={"approved": True, "violations": []})
        return plan

    # Escrita: resultado de uma execução
    def observe(self, task: str, plan: dict, success: bool) -> Optional[str]:
        """Aprende com uma execução terminada. -> status do molde, ou None se nada mudou."""
        if not _enabled() or depends_on_context(task):
            return None
        learned = plan.get("learned_key")
        with _lock:
            data = _load(self.path)
            entries = data["entries"]
            if learned:
                entry = entries.get(learned)
                if not entry:
                    return None
                entry["last"] = time.time()
                if success:
                    entry["successes"] = entry.get("successes", 0) + 1
                    entry["replays"] = entry.get("replays", 0) + 1
                else:
                    entry["failures"] = entry.get("failures", 0) + 1
                    entry["streak"] = 0
                    entry["status"] = "blocked" if entry["failures"] >= FAIL_LIMIT else "candidate"
                _save(self.path, data)
                return entry["status"]
            shaped = plan_template(task, plan)
            if shaped is None:
                return None
            template, _ = extract(task)
            from agents.memory_agent import _redact_pii
            key, sig = _key(template), _signature(shaped)
            entry = entries.get(key) or {"template": _redact_pii(template)[0], "successes": 0, "failures": 0,
                                         "streak": 0, "status": "candidate"}
            if entry.get("status") == "blocked":
                return "blocked"
            if entry.get("planner") != planner_version() or entry.get("signature") != sig:
                entry.update(streak=0, signature=sig, plan=shaped, planner=planner_version(), status="candidate")
            entry["last"] = time.time()
            if success:
                entry["streak"] = entry.get("streak", 0) + 1
                entry["successes"] = entry.get("successes", 0) + 1
                if entry["streak"] >= _promote_after():
                    entry["status"] = "promoted"
            else:
                entry["failures"] = entry.get("failures", 0) + 1
                entry["streak"] = 0
                entry["status"] = "blocked" if entry["failures"] >= FAIL_LIMIT * 2 else "candidate"
            entries[key] = entry
            _save(self.path, data)
            return entry["status"]

    def entries(self) -> list:
        with _lock:
            data = _load(self.path)["entries"]
        return [{"key": k, **{f: v.get(f) for f in ("template", "status", "successes", "failures", "streak", "replays")}}
                for k, v in sorted(data.items(), key=lambda kv: -kv[1].get("last", 0))]

    def forget(self, key: str) -> bool:
        with _lock:
            data = _load(self.path)
            if data["entries"].pop(key, None) is None:
                return False
            _save(self.path, data)
            return True


_shared: Optional[LearnedPlans] = None


def get_learned() -> LearnedPlans:
    global _shared
    if _shared is None:
        _shared = LearnedPlans()
    return _shared
