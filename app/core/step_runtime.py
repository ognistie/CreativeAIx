"""Executa uma ação por tentativa e preserva a diferença entre execução e evidência."""
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic, sleep
from typing import Callable
from core.verification import classify


class UncertainEffect(RuntimeError):
    """O despacho ocorreu ou pode ter ocorrido, sem evidência do resultado."""


def verified_success(records: list[dict]) -> bool:
    outcomes = [row for row in records if row.get("action") != "wait"]
    return bool(outcomes) and all(
        row.get("success") is True and not row.get("dry_run")
        and row.get("status") != "simulated"
        and (row.get("action") == "wait" or row.get("verified") is True)
        for row in records
    )


@dataclass
class StepRuntime:
    max_actions: int
    deadline: float | None
    cancelled: Callable[[], bool]
    actions: int = 0
    retries: int = 0
    recovered: int = 0
    replans: int = 0
    max_replans: int = 4
    _admission: Lock = field(default_factory=Lock, init=False, repr=False, compare=False)

    def stop_reason(self) -> str:
        if self.cancelled():
            return "cancelled"
        if self.deadline is not None and monotonic() >= self.deadline:
            return "timeout"
        if self.actions >= self.max_actions:
            return "action_limit"
        return ""

    def run(self, call: Callable[[], dict], *, retry: bool = False,
            before_retry: Callable[[], None] = lambda: None,
            replan: Callable[[dict], Callable[[], dict] | None] | None = None,
            before_replan: Callable[[], None] = lambda: None) -> dict:
        if not self._admission.acquire(blocking=False):
            return {"success": False, "status": "rejected", "verified": False,
                    "result": "Outra operação desta tarefa já está em andamento."}
        try:
            return self._run(call, retry, before_retry, replan, before_replan)
        finally:
            self._admission.release()

    def _run(self, call, retry, before_retry, replan, before_replan):
        status = self.stop_reason()
        if status:
            return {"success": False, "verified": False, "status": status,
                    "result": f"Execução interrompida antes da ação ({status})."}
        self.actions += 1
        result = call()
        if (replan is not None and self.replans < self.max_replans
                and classify(result) == "pre_effect_failure" and not self.stop_reason()):
            self.actions += 1  # A observação da estratégia também consome orçamento.
            alternative = replan(result)
            if alternative is not None and not self.stop_reason():
                before_replan()
                if not self.stop_reason():
                    self.actions += 1
                    self.replans += 1
                    result = alternative()
                    self.recovered += int(classify(result) == "verified")
                    return result
        # Somente o adaptador conhece a fronteira anterior ao efeito. Mensagens de erro
        # e resultado incerto jamais autorizam uma tentativa adicional.
        if (retry and result.get("success") is False and result.get("status") == "failed"
                and result.get("effect_started") is False and not self.stop_reason()):
            before_retry()
            sleep(0.2)
            if not self.stop_reason():
                self.actions += 1
                self.retries += 1
                result = call()
                self.recovered += int(classify(result) == "verified")
        return result
