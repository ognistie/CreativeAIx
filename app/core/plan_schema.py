"""Contrato tipado do plano (versão 1): Plan, Subtask e Step.

O schema cuida só da FORMA (tipos, campos, tamanho). As regras de negócio (POL-001 em diante) continuam em
core/plan_validator.py, sobre um plano que já passou por aqui. Campos extras são aceitos: o Maestro e os
atalhos anotam o plano (analysis, skills, fast_path, profile...) e os agentes leem params livres.
`plan_json_schema()` é a documentação viva do contrato.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

SCHEMA_VERSION = 1
MAX_SUBTASKS = 5


class Subtask(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    agent: StrictStr = ""
    task: StrictStr = ""
    params: dict = Field(default_factory=dict)
    depends_on: Optional[StrictInt] = None       # posição (1..n) de uma subtarefa anterior


class Plan(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    subtasks: list[Subtask] = Field(min_length=1, max_length=MAX_SUBTASKS)


class Step(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    action: StrictStr = ""
    params: dict = Field(default_factory=dict)


def plan_json_schema() -> dict:
    schema = Plan.model_json_schema()
    schema["$comment"] = f"Creative AIx plano v{SCHEMA_VERSION}"
    return schema


def plan_shape(plan: object) -> tuple[Optional[str], dict[int, list[tuple[str, str]]]]:
    """-> (erro do plano inteiro, {posição: [(política, mensagem)]}). Mensagens iguais às de antes do schema,
    para o replanejamento receber o mesmo motivo literal."""
    if not isinstance(plan, dict):
        return "plano deve ser um objeto", {}
    subs = plan.get("subtasks")
    if not subs:
        return "plano sem subtasks", {}
    if not isinstance(subs, list) or len(subs) > MAX_SUBTASKS or any(not isinstance(s, dict) for s in subs):
        return f"subtasks deve ser uma lista de ate {'cinco' if MAX_SUBTASKS == 5 else MAX_SUBTASKS} objetos", {}
    bad: dict[int, list[tuple[str, str]]] = {}
    for i, sub in enumerate(subs, start=1):
        try:
            Subtask.model_validate(sub)
        except ValidationError as exc:
            fields = {str(e["loc"][0]) for e in exc.errors() if e.get("loc")}
            out = []
            if "depends_on" in fields:
                out.append(("POL-004", "depends_on deve apontar para uma subtarefa anterior"))
            if "params" in fields:
                out.append(("POL-000", "params deve ser um objeto"))
            elif fields & {"agent", "task"}:
                out.append(("POL-000", "agent e task devem ser texto"))
            bad[i] = out or [("POL-000", "subtarefa fora do formato")]
    return None, bad


def steps_shape(steps: object) -> Optional[str]:
    if not steps:
        return "agente nao propos nenhum passo"
    if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps):
        return "steps deve conter objetos com params validos"
    for step in steps:
        try:
            Step.model_validate({k: v for k, v in step.items() if k != "action"} | {"action": str(step.get("action") or "")})
        except ValidationError:
            return "steps deve conter objetos com params validos"
    return None
