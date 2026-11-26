"""Estado de dependências de um plano validado, sem dependência de Qt ou I/O."""
from dataclasses import dataclass
from enum import Enum


class Availability(Enum):
    READY = "ready"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SubtaskNode:
    id: int
    dependency: int | None


class TaskSchedule:
    """Usa os índices públicos do plano como IDs estáveis dentro da execução."""

    def __init__(self, subtasks: list[dict], skipped: set[int]):
        self.nodes = tuple(SubtaskNode(i, sub.get("depends_on")) for i, sub in enumerate(subtasks, 1))
        if any(node.dependency is not None and
               (type(node.dependency) is not int or not 1 <= node.dependency < node.id) for node in self.nodes):
            raise ValueError("Dependência inválida para execução.")
        self._skipped = set(skipped)
        self._completed: dict[int, bool] = {}

    def availability(self, node: SubtaskNode) -> Availability:
        if node.id in self._skipped or node.dependency in self._skipped:
            self._skipped.add(node.id)
            return Availability.SKIPPED
        if node.dependency is not None and self._completed.get(node.dependency) is not True:
            return Availability.BLOCKED
        return Availability.READY

    def finish(self, node: SubtaskNode, success: bool) -> None:
        self._completed[node.id] = success
