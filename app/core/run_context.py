"""Estado compartilhado da tarefa, do planejamento ao último resultado."""
from dataclasses import dataclass, field
from copy import deepcopy
from time import monotonic
from typing import Callable
import re
import stat
from urllib.parse import urlsplit

from core.lab_budget import Budget
from core.lab_budget import RequestLimit, budget_scope
from core.step_runtime import StepRuntime
from core.task_schedule import TaskSchedule
from core.verification import apply_independent_check, classify, file_identity


@dataclass(frozen=True)
class PlanPatch:
    """Substitui parâmetros de um único passo ainda não concluído."""
    strategy: str
    observation: str
    changes: tuple[tuple[str, str | int], ...]


def _requested_url(goal: str) -> str:
    URLs = {value.rstrip(".,;!?)]") for value in re.findall(r'https?://[^\s<>"\']+', goal, re.I)}
    if len(URLs) != 1:
        return ""
    raw = URLs.pop()
    try:
        url = urlsplit(raw)
        return raw if url.hostname and url.username is None and url.password is None else ""
    except ValueError:
        return ""


@dataclass
class RunContext:
    goal: str
    cancelled: Callable[[], bool]
    deadline: float | None = None
    budget: Budget | None = None
    max_actions: int = 100
    dry_run: bool = False
    file_roots: tuple[str, ...] = ()
    evidence: list[dict] = field(default_factory=list)
    schedule: TaskSchedule | None = None
    ledger: object = None
    task_id: str = ""
    read_replanner: Callable | None = None
    runtime: StepRuntime = field(init=False)
    _original_goal: str = field(init=False, repr=False)

    def __post_init__(self):
        self._original_goal = self.goal
        if self.deadline is None and self.budget is not None:
            self.deadline = self.budget.deadline
        self.runtime = StepRuntime(self.max_actions, self.deadline, self.cancelled)

    def interrupted(self) -> bool:
        return self.cancelled() or (self.deadline is not None and monotonic() >= self.deadline)

    def make_schedule(self, subtasks, skipped):
        self.schedule = TaskSchedule(subtasks, skipped)
        return self.schedule

    def execute_step(self, agent, action, params, dispatch, *, authorize_patch, allow_directory,
                     adaptive=True, phase_iv=False, retry=False, before_retry=lambda: None,
                     on_patch=lambda _patch: None, review=lambda _params, result: result) -> dict:
        """Admite, observa e adapta um passo com a mesma política em qualquer ponto de entrada."""
        from core.file_recovery import alternative_copy, alternative_read

        def budget_stop():
            if self.budget is not None and self.budget.stop:
                return {"success": False, "verified": False, "status": "budget_limit",
                        "result": "Orçamento da tarefa esgotado."}
            return None

        def guarded_dispatch(arguments):
            stopped = budget_stop()
            if stopped:
                return stopped
            effective = deepcopy(arguments)
            result = apply_independent_check(action, effective, dispatch(arguments))
            return review(effective, result)

        original = dict(params)
        if action == "browser_read" and agent == "WEB":
            original.pop("_read_view", None)
            original.pop("_expected_url", None)
            original.pop("_read_window", None)
            original.pop("_expected_text", None)
            expected = _requested_url(self._original_goal)
            if expected and not phase_iv:
                original["_expected_url"] = expected
                if re.search(r"\b(confira|verifique|encontre|contenha|contém|trecho literal)\b",
                             self._original_goal, re.I):
                    anchors = re.findall(r'["“]([^"”\r\n]{1,120})["”]', self._original_goal)
                    if len(anchors) == 1 and not anchors[0].startswith(("http://", "https://")):
                        original["_expected_text"] = anchors[0]
        else:
            expected = ""
        file_strategy = {"copy_file": ("source", alternative_copy, "unique_file_in_source_tree"),
                         "read_file": ("path", alternative_read, "unique_read_in_source_tree")}.get(action)

        def replan(result):
            from core.panorama import activity
            activity("recovery", agent=agent, status="started", action=action)
            reason = result.get("failure_reason", "")
            identity = None
            selected = None
            if agent == "FILE" and file_strategy:
                key, choose, name = file_strategy
                proposal = choose(self._original_goal, original, result, self.interrupted, allow_directory)
                if proposal is None:
                    return None
                selected = proposal[key]
                identity = file_identity(selected)
                if identity is None or not stat.S_ISREG(identity[3]):
                    return None
                patch = PlanPatch(name, reason, ((key, selected),))
            elif (expected and reason in ("web_empty", "web_marker_missing") and result.get("observed_url") == expected
                  and type(result.get("observed_window")) is int and result["observed_window"] > 0):
                window = ("_read_window", result["observed_window"])
                if reason == "web_empty":
                    patch = PlanPatch("visible_page_text", reason, (("_read_view", "visible"), window))
                elif self.read_replanner is not None and self.budget is not None and not self.runtime.stop_reason():
                    # Só a decisão folheia o modelo. A evidência, o alvo e os parâmetros ficam locais.
                    try:
                        with budget_scope(self.budget):
                            answer = self.read_replanner(reason, ("visible", "expanded"))
                    except (RequestLimit, ValueError, RuntimeError):
                        return None
                    if not isinstance(answer, dict) or set(answer) != {"strategy"}:
                        return None
                    if answer["strategy"] == "visible":
                        patch = PlanPatch("model_visible_page_text", reason, (("_read_view", "visible"), window))
                    elif answer["strategy"] == "expanded":
                        patch = PlanPatch("model_expanded_page_text", reason, (("max_chars", 12000), window))
                    else:
                        return None
                else:
                    return None
            else:
                return None
            updated = original | dict(patch.changes)
            if not authorize_patch(updated):
                return None

            def apply():
                on_patch(patch)
                if not authorize_patch(updated):
                    return {"success": False, "status": "rejected", "result": "Alternativa recusada pela política atual."}
                if selected and file_identity(selected) != identity:
                    return {"success": False, "status": "rejected", "result": "Origem mudou durante o replanejamento."}
                if self.interrupted():
                    return {"success": False, "status": "cancelled", "result": "Replanejamento interrompido."}
                return guarded_dispatch(updated)
            return apply

        eligible = (not self.dry_run and (adaptive or (phase_iv and action == "copy_file"))
                    and ((agent == "FILE" and file_strategy is not None) or bool(expected)))
        result = self.runtime.run(lambda: guarded_dispatch(original), retry=retry and not self.dry_run,
                                  before_retry=before_retry, replan=replan if eligible else None)
        if classify(result) == "pre_effect_failure":
            result = budget_stop() or result
        return {**result, "outcome": classify(result)}
