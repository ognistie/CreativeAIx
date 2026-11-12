"""
EXTCODE — Claude Code e Codex como agentes do app.

"faz um README no projeto X com o Claude" / "pede ao Codex para corrigir os testes em C:\\...":
a pessoa escolhe a ferramenta e a pasta; a CLI oficial (ja autenticada por ela) trabalha so nessa
pasta, com progresso linha a linha na tela e no registro de tarefas (core/coding_agents.py).

Sem modelo no caminho: o plano e um passo `ext_code_task`, montado em codigo. A pasta vem do
pedido (caminho citado) ou do projeto aberto na conversa; sem pasta, a resposta e uma pergunta.
"""

from __future__ import annotations

import re
from typing import Optional

from agents.base_agent import BaseAgent
from core.coding_agents import NAMES, TOOL_WORD, folder_error, tool_in

# "com o claude", "pelo codex", "usando o claude code": sai do prompt que vai para a CLI
_WITH_TOOL = re.compile(r"\s*\b(?:com|pelo|pela|usando|via|no|na|pede(?:\s+a[oa]?)?|pe[cç]a(?:\s+a[oa]?)?|manda(?:\s+o)?)\s+"
                        r"(?:o\s+|a\s+)?(?:claude(?:\s+code)?|codex)\b(?:\s+(?:para|pra|que))?", re.I)
_OPEN_ONLY = re.compile(r"^(?:por favor,?\s*)?(?:abr[aei]r?|abre|abrir|fech[ae]r?|feche|minimiz\w*|maximiz\w*)\s+"
                        r"(?:o\s+|a\s+)?(?:claude(?:\s+code)?|codex)\s*[.!]?$", re.I)
_FOLDER_QUESTION = "Em qual pasta de projeto o {name} deve trabalhar? Diga o caminho completo da pasta."
# Acao no computador (abrir programa ou site, pesquisar, tocar): nao e trabalho de codigo numa pasta.
# Com o Claude Code / Codex escolhido (no pedido ou no seletor do topo), vai para os agentes do computador.
_COMPUTER_ACTION = re.compile(r"^(?:por\s+favor,?\s*)?(?:me\s+)?(?:abr[aei]r?|abre|abrir|inici[ae]r?|execut[ae]r?|rod[ae]r?\s+o\s+programa|"
                              r"toc[ae]r?|pesquis[ae]r?|busc[ae]r?|procur[ae]r?|acess[ae]r?|entr[ae]r?\s+n[oa]|fech[ae]r?|minimiz\w*|maximiz\w*)\b", re.I)
_CODE_WORDS = re.compile(r"\b(?:c[oó]digo|projeto|reposit[oó]rio|repo|readme|testes?|fun[cç][aãõo]\w*|bug|script|refator\w*|commit|"
                         r"branch|programa[cç][aã]o|componente|endpoint|api|\w+\.(?:py|js|ts|tsx|qml|md|json|java|cs|go|rs))\b", re.I)


def is_computer_action(task: str) -> bool:
    """'abre o bloco de notas com o claude code', 'abra o google com o codex': acao no computador, nao codigo."""
    from core.paths import extract_path
    text = _prompt_from(task)
    return bool(_COMPUTER_ACTION.match(text)) and not _CODE_WORDS.search(text) and not extract_path(text)


def _prompt_from(task: str) -> str:
    text = _WITH_TOOL.sub(" ", task or "")
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.;")
    return text or (task or "").strip()


def _folder_from(task: str, session) -> Optional[str]:
    import os
    from core.paths import extract_path, resolve_path
    cited = extract_path(task)
    if cited:
        # O caminho citado vai ate o fim da frase ("C:\x\meu projeto com o claude"): fica o maior
        # prefixo que existe de verdade.
        parts = cited.split(" ")
        for i in range(len(parts), 0, -1):
            path = resolve_path(" ".join(parts[:i]))
            if os.path.isdir(path):
                return path
            if os.path.isfile(path):
                return os.path.dirname(path)
    if session is not None:
        code = getattr(session, "code", None) or {}
        if isinstance(code, dict) and code.get("folder"):
            return code["folder"]
        folder = getattr(session, "folder", None)
        if folder:
            return folder
    return None


def extcode_plan(task: str, session=None) -> Optional[dict]:
    """Plano direto (sem IA) quando o pedido cita o Claude Code ou o Codex. None: nao e com eles."""
    if not TOOL_WORD.search(task or "") or _OPEN_ONLY.match((task or "").strip()):
        return None
    tool = tool_in(task)
    if not tool:
        return None
    name = NAMES[tool]
    if is_computer_action(task):
        return {"reroute": _prompt_from(task),
                "note": f"O {name} trabalha com código numa pasta de projeto; abrir programas e sites é com os "
                        f"agentes do computador, então segui por eles."}
    folder = _folder_from(task, session)
    if not folder:
        return {"needs_clarification": True, "question": _FOLDER_QUESTION.format(name=name),
                "why": "pasta do projeto ausente", "subtasks": []}
    bad = folder_error(folder)
    if bad:
        return {"needs_clarification": True, "question": f"{bad} Qual pasta devo usar?",
                "why": "pasta do projeto invalida", "subtasks": []}
    prompt = _prompt_from(task)
    plan = {"analysis": f"{name} na pasta do projeto (atalho, sem IA)", "skills": [], "fast_path": "extcode",
            "subtasks": [{"agent": "EXTCODE", "task": f"{name}: {prompt[:120]}", "original_task": task,
                          "params": {"tool": tool, "folder": folder, "prompt": prompt}}]}
    from core.plan_validator import validate_plan
    check = validate_plan(task, plan)
    if not check.approved:
        return None
    plan["validation"] = {"approved": True, "violations": []}
    print(f"[Maestro] Atalho: {plan['analysis']}")
    return plan


class ExtCodeAgent(BaseAgent):
    """Um passo, montado em codigo: ext_code_task(tool, folder, prompt)."""

    def __init__(self):
        super().__init__(name="EXTCODE", system_prompt="")

    def plan(self, task, context=None):
        params = (task.get("params") or {}) if isinstance(task, dict) else {}
        text = self._extract_task_text(task)
        tool = (params.get("tool") or tool_in(text) or tool_in(self._extract_original_task(task)) or "").lower()
        if tool not in NAMES:
            return {"steps": [], "agent": self.name, "error": "Diga com qual agente: Claude Code ou Codex."}
        folder = params.get("folder") or ((params.get("continue") or {}).get("folder") if isinstance(params.get("continue"), dict) else None)
        bad = folder_error(folder)
        if bad:
            return {"steps": [], "agent": self.name, "error": bad}
        prompt = (params.get("prompt") or _prompt_from(self._extract_original_task(task) or text)).strip()
        if not prompt:
            return {"steps": [], "agent": self.name, "error": "Pedido vazio para o agente externo."}
        self._metrics["total_plans"] += 1
        self._metrics["successful_plans"] += 1
        return {"steps": [{"step": 1, "action": "ext_code_task", "agent": self.name,
                           "description": f"{NAMES[tool]} em {folder}: {prompt[:70]}",
                           "params": {"tool": tool, "folder": folder, "prompt": prompt}}],
                "agent": self.name}
