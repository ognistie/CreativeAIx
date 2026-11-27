"""Panorama do harness (core/panorama.py): rotas, trafego por agente e evolucao (planos aprendidos + hipoteses)."""

import unittest

from core.panorama import build, evolution, route_of, routing


class RouteTests(unittest.TestCase):
    def test_route_of_a_plan(self):
        self.assertEqual(route_of({"learned_key": "k", "fast_path": "abrir"}), "aprendido")
        self.assertEqual(route_of({"fast_path": "abrir"}), "atalho")
        self.assertEqual(route_of({"fast_path": "pesquisar"}), "atalho")
        self.assertEqual(route_of({"fast_path": "continuar"}), "continuar")
        self.assertEqual(route_of({"subtasks": [{"agent": "WEB"}]}), "maestro")
        self.assertEqual(route_of({}, handed_by_chat=True), "conversa→maestro")
        self.assertEqual(route_of(None), "maestro")

    def test_traffic_by_route_and_agent_including_old_entries(self):
        history = [
            {"route": "conversa", "success": True, "subtasks": [{"agent": "CHAT"}], "duration_ms": 2000},
            {"route": "conversa→maestro", "success": True, "subtasks": [{"agent": "DATA"}], "duration_ms": 30000},
            {"route": "atalho", "success": False, "subtasks": [{"agent": "DESKTOP"}], "duration_ms": 1000},
            {"success": True, "subtasks": [{"agent": "CHAT"}]},                    # antigo, sem route: conversa
            {"success": True, "learned": True, "subtasks": [{"agent": "WEB"}]},    # antigo: plano aprendido
            {"success": True, "subtasks": [{"agent": "WEB"}], "dry_run": True},    # simulacao: fora
            {"success": False, "error": "clarification_required", "subtasks": []},  # antigo: Maestro sem plano
        ]
        out = routing(history)
        routes = {r["route"]: r for r in out["routes"]}
        self.assertEqual(out["total"], 6)
        self.assertEqual(routes["conversa"]["runs"], 2)
        self.assertEqual(routes["maestro"]["runs"], 2)
        self.assertEqual(routes["maestro"]["ok"], 1)
        self.assertEqual(routes["atalho"]["ok"], 0)
        self.assertEqual(routes["aprendido"]["runs"], 1)
        edges = {(e["from"], e["to"]): e["runs"] for e in out["edges"]}
        self.assertEqual(edges[("conversa", "maestro")], 1)               # a conversa entregou ao Maestro
        self.assertEqual(edges[("maestro", "DATA")], 1)
        self.assertEqual(out["recent"][0]["route"], "conversa")

    def test_evolution_summarizes_plans_and_hypotheses(self):
        plans = [{"key": "a", "template": "abrir <app>", "status": "promoted", "successes": 4, "streak": 3,
                  "agents": ["DESKTOP"]},
                 {"key": "b", "template": "pesquisar <termo>", "status": "candidate", "streak": 1},
                 {"key": "c", "template": "x", "status": "weird"}]
        science = [{"id": "h1", "agent": "file", "objective": "organizar melhor", "result": "refutada", "when": "2026-11-20T10:00:00"}]
        out = evolution(plans, science)
        self.assertEqual(out["summary"], {"promoted": 1, "candidate": 2, "blocked": 0, "hypotheses": 1})
        self.assertEqual(out["plans"][0]["agents"], ["DESKTOP"])
        self.assertEqual(out["hypotheses"][0]["agent"], "FILE")
        self.assertEqual(build([], plans, science)["routing"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
