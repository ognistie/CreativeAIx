"""RSI supervisionado do AI Research Lab (Phase VII): melhoria iterativa e versionada do harness, com o modelo congelado.

Não é um segundo laboratório. Usa as versões, as rodadas pareadas, o `promotion_check` (holdout obrigatório), a
promoção humana e o rollback de core/lab.py, e acrescenta o que faltava para uma rodada governada:

  ExperimentSpec      objetivo do operador, categoria, componente mutável, limites (propostas, custo) e aprovação
  ImprovementProposal hipótese declarativa admitida por regra fixa (nunca código, política, avaliador ou holdout)
  EvaluationRecord    resultado de cada candidata na rodada (origem real/simulado, taxas, motivos)
  PromotionDecision   decisão humana registrada (promover / rejeitar), com a versão anterior para rollback
  ScientificMemory    histórico de hipóteses, inclusive negativas: não repete o que já foi refutado

O que a camada NÃO pode fazer (garantido aqui e em lab.py): publicar sozinha, mudar limites, critérios, avaliadores,
casos reservados, políticas de segurança, ferramentas ou permissões, nem rodar em segundo plano sem o operador.
Isolamento do holdout por identidade do sistema operacional não existe nesta máquina: a promoção científica
continua exigindo os casos reservados do Lab, e essa limitação aparece em todo relatório (`limitations`).
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import datetime
from typing import Callable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = 1
MAX_PROPOSALS = 3
LIMITATIONS = ("Casos reservados separados por pasta do Lab, não por identidade do sistema operacional.",
               "Rodadas simuladas nunca valem como evidência de promoção.")
# Categorias com mecanismo de publicação implementado. As outras ficam declaradas e recusadas, sem simular.
SUPPORTED = {"prompt"}
Category = Literal["prompt", "skill", "context", "runtime_strategy"]

# O que uma proposta nunca pode conter: código, mexer em segurança, avaliação ou acesso.
_FORBIDDEN = [
    (re.compile(r"```|<script|\bimport\s+\w+|\bdef\s+\w+\(|\bexec\(|\beval\(|subprocess|powershell|cmd\.exe", re.I),
     "contém código; propostas são instruções declarativas"),
    (re.compile(r"\b(?:run_python|run_command|pip_install|delete_file)\b", re.I), "cita ferramenta privilegiada"),
    (re.compile(r"\b(?:sem|nao|não)\s+(?:pedir|perguntar|precisar\s+de)\s+(?:confirma|aprova|autoriza)", re.I),
     "tenta dispensar confirmação de efeito"),
    (re.compile(r"\b(?:ignor\w*|desativ\w*|deslig\w*|contorn\w*|burl\w*)\b.{0,40}"
                r"\b(?:pol[ií]tica|regra|seguran|confirma|guardrail|permiss|limite|or[cç]amento|valida)", re.I),
     "tenta desligar política, limite ou validação"),
    (re.compile(r"\bPOL-\d{3}\b|plan_validator|action_policy|action_risk", re.I), "cita política em código"),
    (re.compile(r"\b(?:holdout|casos?\s+reservados?|avaliador|grader|gabarito|rubrica)\b", re.I),
     "cita o avaliador ou os casos reservados"),
    (re.compile(r"\b(?:api[_ ]?key|senha|password|token|credencia)", re.I), "cita credenciais"),
]


class ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: int = SCHEMA_VERSION
    objective: str = Field(min_length=4, max_length=400)
    agent: str = Field(pattern=r"^(?:DATA|WEB|CODE|DESKTOP|FILE|EXTCODE|MAESTRO)$")
    category: Category = "prompt"
    dataset: str = Field(min_length=1, max_length=80)
    max_proposals: int = Field(default=1, ge=1, le=MAX_PROPOSALS)
    budget_usd: float = Field(default=0.0, ge=0.0, le=5.0)
    origin: Literal["real", "simulado"] = "simulado"
    operator_approved: bool = False            # o operador iniciou ESTA rodada; nunca vem da proposta

    @field_validator("objective")
    @classmethod
    def _clean(cls, v: str) -> str:
        return " ".join(v.split())


class ImprovementProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis: str
    component: str
    delta: str                                 # instruções novas (texto declarativo)
    evidence: list[dict] = Field(default_factory=list)
    risk: str = "A nova instrução pode alterar casos que já funcionavam."
    regression_required: bool = True


class InstructionMutation(BaseModel):
    """Única operação que uma proposta admitida pode executar no Lab."""
    model_config = ConfigDict(extra="forbid", strict=True)
    operation: Literal["replace_instructions"] = "replace_instructions"
    agent: Literal["DATA", "WEB", "CODE", "DESKTOP", "FILE", "EXTCODE", "MAESTRO"]
    baseline: str = Field(pattern=r"^[a-z]+-v[0-9]+$")
    instructions: str = Field(min_length=1, max_length=1500)

    def apply(self, lab, objective):
        base = lab.version(self.baseline)
        if base is None or base["agent"] != self.agent or base.get("archived"):
            raise ValueError("Baseline da proposta inválida.")
        return lab.create_variant(self.agent, self.baseline, self.instructions,
                                  note=("rsi: " + objective)[:120])


class EvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: str
    baseline: str
    run: str
    origin: Literal["real", "simulado"]
    rates: dict
    verdict_ok: bool
    reasons: list[str]


class PromotionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: str
    decision: Literal["promover", "rejeitar"]
    operator: str
    previous: str = ""
    run: str = ""
    when: str


def fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join((text or "").casefold().split()).encode("utf-8")).hexdigest()[:16]


def admit(spec: ExperimentSpec, delta: str, baseline_instructions: str) -> list[str]:
    """Motivos de recusa ([] = admitida). Regra fixa em código: a variante não escreve as próprias regras."""
    reasons = []
    if spec.category not in SUPPORTED:
        reasons.append(f"categoria '{spec.category}' ainda não tem publicação segura; só 'prompt' nesta fase")
    text = (delta or "").strip()
    if not text:
        reasons.append("proposta vazia")
    if len(text) > 1500:
        reasons.append("proposta longa demais (máx. 1500 caracteres)")
    if fingerprint(text) == fingerprint(baseline_instructions):
        reasons.append("proposta igual às instruções atuais")
    reasons += [why for pattern, why in _FORBIDDEN if pattern.search(text)]
    return reasons


class ScientificMemory:
    """Hipóteses e resultados (positivos e negativos) em science.jsonl na pasta pessoal do Lab.

    Memória de pesquisa: separada da memória do usuário e da operacional. Sem conteúdo dos casos reservados."""

    def __init__(self, lab):
        self._lab = lab
        self._lock = threading.Lock()

    @property
    def path(self):
        return self._lab._need() / "science.jsonl"

    def entries(self) -> list[dict]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out

    def add(self, row: dict) -> dict:
        row = {"id": uuid.uuid4().hex[:12], "schema_version": SCHEMA_VERSION,
               "when": datetime.now().isoformat(timespec="seconds"), **row}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def refuted(self, agent: str, dataset_hash: str, hypothesis_fp: str) -> Optional[dict]:
        """A mesma hipótese, no mesmo agente e conjunto, já perdeu ou foi rejeitada: não gastar de novo."""
        for row in reversed(self.entries()):
            same = row.get("agent") == agent and row.get("hypothesis_fp") == hypothesis_fp
            if same and (row.get("result") == "rejeitada"            # o operador rejeitou: vale para qualquer conjunto
                         or row.get("result") == "refutada" and row.get("dataset_hash") == dataset_hash):
                return row
        return None

    def search(self, query: str = "", agent: str = "", limit: int = 50) -> list[dict]:
        words = [w for w in re.findall(r"\w{3,}", (query or "").casefold())]
        rows = [r for r in self.entries() if not agent or r.get("agent") == agent]
        if words:
            rows = [r for r in rows if all(w in json.dumps(r, ensure_ascii=False).casefold() for w in words)]
        return rows[-limit:][::-1]


def run_round(lab, spec: ExperimentSpec, propose: Callable[[str, str, list], str], planner: Callable,
              cancel: Optional[threading.Event] = None, on_event: Optional[Callable] = None) -> dict:
    from core.lab_budget import Budget, budget_scope, current
    # Uma rodada possui a própria reserva. Aninhamento sem suborçamento explícito é recusado.
    if current.get() is not None:
        raise ValueError("Inicie a rodada fora de outro orçamento de experimento.")
    cancel = cancel or threading.Event()
    limits = Budget(spec.budget_usd if spec.origin == "real" else 0.0, 600, 200, 1000000, cancel)
    with budget_scope(limits):
        result = _run_round(lab, spec, propose, planner, cancel, on_event, limits)
    result["spent_usd"] = round(max(result["spent_usd"], limits.spent), 6)
    result["usage"] = {"calls_started": limits.calls, "tokens_accounted": limits.tokens}
    return result


def _run_round(lab, spec, propose, planner, cancel, on_event, limits):
    """Uma rodada finita: até `max_proposals` hipóteses -> admissão -> variante isolada -> rodada pareada nos casos
    de desenvolvimento -> veredito do `promotion_check` -> memória científica. Nunca publica nada."""
    if not spec.operator_approved:
        raise PermissionError("a rodada precisa ser iniciada pelo operador")
    from core.lab import _fingerprint
    memory = ScientificMemory(lab)
    rows = lab.versions(spec.agent)
    base = next((v for v in rows if v.get("published")), rows[0])
    dataset = lab.eval_set(spec.dataset)
    dataset_hash = _fingerprint(dataset)
    published_before = base["hash"]
    development = {c["id"] for c in dataset["cases"] if c.get("split", "development") == "development"}
    if not development:
        raise ValueError("o conjunto precisa de casos de desenvolvimento")
    failures = [r for r in lab.development_results(dataset_hash, base["id"])
                if r["case"] in development and r["status"] != "passou"]
    report = {"spec": spec.model_dump(), "baseline": base["id"], "dataset_hash": dataset_hash, "proposals": [],
              "evaluations": [], "limitations": list(LIMITATIONS), "stopped": ""}
    spent = 0.0
    for attempt in range(spec.max_proposals):
        if cancel is not None and cancel.is_set():
            report["stopped"] = "cancelada pelo operador"
            break
        if limits.stop or (spec.origin == "real" and max(spent, limits.spent) >= spec.budget_usd):
            report["stopped"] = limits.stop or "orçamento da rodada esgotado"
            break
        from core.lab_budget import RequestLimit
        try:
            limits.time_left()
            delta = str(propose(spec.objective, base.get("instructions", ""), failures) or "").strip()
            limits.time_left()
        except RequestLimit as error:
            report["stopped"] = str(error)
            break
        if spec.origin == "real" and limits.spent >= spec.budget_usd:
            report["stopped"] = "orçamento da rodada esgotado"
            break
        proposal = ImprovementProposal(hypothesis=f"Instruções novas para {spec.agent} atingem: {spec.objective}",
                                       component=f"{spec.agent}.instructions", delta=delta[:1500],
                                       evidence=[{"case": f["case"], "status": f["status"]} for f in failures][:20])
        reasons = admit(spec, delta, base.get("instructions", ""))
        hyp = fingerprint(delta)
        seen = memory.refuted(spec.agent, dataset_hash, hyp) if not reasons else None
        if seen:
            reasons.append(f"hipótese já refutada em {seen.get('when', '')[:10]} ({seen.get('candidate', '')})")
        entry = {"proposal": proposal.model_dump(), "admitted": not reasons, "reasons": reasons}
        report["proposals"].append(entry)
        if on_event:
            on_event({"type": "rsi_proposal", "attempt": attempt + 1, "admitted": not reasons})
        if reasons:
            memory.add({"agent": spec.agent, "dataset_hash": dataset_hash, "hypothesis_fp": hyp,
                        "objective": spec.objective, "category": spec.category, "candidate": "",
                        "baseline": base["id"], "result": "recusada", "reasons": reasons})
            continue
        try:
            variant = InstructionMutation(agent=spec.agent, baseline=base["id"], instructions=delta).apply(lab, spec.objective)
        except ValueError:                     # mesma hipótese já virou variante: reaproveita
            variant = next(v for v in lab.versions(spec.agent) if v["instructions"] == delta[:1500]
                           and v["params"] == base["params"])
        remaining = None if spec.origin != "real" else max(0.0, spec.budget_usd - max(spent, limits.spent))
        if spec.origin == "real" and not remaining:
            report["stopped"] = "orçamento da rodada esgotado"
            break
        run = lab.run(spec.dataset, [base["id"], variant["id"]], planner, origin=spec.origin, cancel=cancel,
                      on_event=on_event, budget_usd=remaining, revision=dataset_hash, split="development")
        spent += sum(float((run.get("summary") or {}).get(v, {}).get("cost_usd") or 0) for v in (base["id"], variant["id"]))
        summary = run.get("summary") or {}
        rates = {v: (summary.get(v) or {}).get("success_rate") for v in (base["id"], variant["id"])}
        verdict = lab.promotion_check(variant["id"], require_improvement=True) if spec.origin == "real" else \
            {"ok": False, "reasons": ["rodada simulada não vale como evidência para promover"]}
        record = EvaluationRecord(candidate=variant["id"], baseline=base["id"], run=run["id"], origin=spec.origin,
                                  rates=rates, verdict_ok=bool(verdict.get("ok")), reasons=list(verdict.get("reasons", [])))
        report["evaluations"].append(record.model_dump())
        better = (rates.get(variant["id"]) or 0) > (rates.get(base["id"]) or 0)
        worse = (rates.get(variant["id"]) or 0) < (rates.get(base["id"]) or 0)
        memory.add({"agent": spec.agent, "dataset_hash": dataset_hash, "hypothesis_fp": hyp, "objective": spec.objective,
                    "category": spec.category, "candidate": variant["id"], "baseline": base["id"], "run": run["id"],
                    "origin": spec.origin, "rates": rates,
                    "result": ("aguardando decisão" if verdict.get("ok")
                               else "refutada" if worse or (spec.origin == "real" and not better)
                               else "inconclusiva"),
                    "reasons": record.reasons, "limitations": list(LIMITATIONS)})
        if verdict.get("ok"):
            break                              # uma candidata pronta: a decisão agora é do operador
    after = next((v for v in lab.versions(spec.agent) if v.get("published")), base)
    if after["hash"] != published_before:      # invariante: a rodada nunca muda a versão ativa
        raise RuntimeError("a versão ativa mudou durante a rodada de pesquisa")
    report["spent_usd"] = round(spent, 6)
    return report


def decide(lab, harness, candidate: str, decision: str, operator: str) -> dict:
    """Decisão humana explícita. Promover passa pelo promotion_check do Lab (sem atalho); rejeitar arquiva a variante.
    Ambas entram na memória científica."""
    operator = " ".join(str(operator or "").split())[:60]
    if not operator:
        raise PermissionError("a decisão precisa de um operador identificado")
    version = lab.version(candidate)
    if version is None:
        raise FileNotFoundError("candidata não encontrada")
    published = next((v for v in lab.versions(version["agent"], harness) if v.get("published")), None)
    memory = ScientificMemory(lab)
    if decision == "promover":
        check = lab.promotion_check(candidate, require_improvement=True)
        lab.promote(candidate, harness, require_improvement=True)
        record = PromotionDecision(candidate=candidate, decision="promover", operator=operator,
                                   previous=(published or {}).get("id", ""), run=check.get("run", ""),
                                   when=datetime.now().isoformat(timespec="seconds"))
        result = "promovida"
    elif decision == "rejeitar":
        lab.archive(candidate, True, harness)
        record = PromotionDecision(candidate=candidate, decision="rejeitar", operator=operator,
                                   when=datetime.now().isoformat(timespec="seconds"))
        result = "rejeitada"
    else:
        raise ValueError("decisão inválida")
    memory.add({"agent": version["agent"], "candidate": candidate, "hypothesis_fp": fingerprint(version["instructions"]),
                "dataset_hash": "", "result": result, "decision": record.model_dump()})
    return record.model_dump()
