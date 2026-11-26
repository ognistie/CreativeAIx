"""Aparencia (paletas e fundo validados no Harness), Atividade e plano por passo."""
import re
import sys
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))


class AppearanceTests(unittest.TestCase):
    def test_new_palettes_and_background_settings_are_validated(self):
        from core.harness import validate, upgrade_style, DEFAULT, STYLE
        import json
        theme = json.loads((APP / "design" / "theme.json").read_text(encoding="utf-8"))
        for name in ("abismo", "ameixa", "nevoa", "matcha", "seda"):
            self.assertIn(name, theme["palettes"]["dark"])                 # versao clara e escura
            self.assertIn(name, theme["palettes"]["light"])
        out = validate({"appearance": {"mesh": False, "flow": "normal", "fluted": True}})["appearance"]
        self.assertEqual((out["mesh"], out["flow"], out["fluted"]), (False, "normal", True))
        bad = validate({"appearance": {"mesh": "sim", "flow": "rapido", "fluted": 1}})["appearance"]
        self.assertEqual((bad["mesh"], bad["flow"], bad["fluted"]), (True, "sutil", False))
        old = {"appearance": {"accent": "#0A7CFF", "palette": "coral", "mode": "claro", "wallpaper": "catalog:x-y"}}
        up = validate(upgrade_style(old))["appearance"]
        self.assertEqual((up["palette"], up["accent"], up["mode"], up["style"]),
                         (DEFAULT["appearance"]["palette"], DEFAULT["appearance"]["accent"], "claro", STYLE))
        mine = {"appearance": {"accent": "#E0457B", "palette": "seda", "style": STYLE}}
        self.assertEqual(validate(upgrade_style(mine))["appearance"]["palette"], "seda")   # escolha nova fica


    def test_bridge_gives_the_cursor_position(self):
        src = (APP / "desktop" / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("def cursorPos(self)", src)


class ActivityTests(unittest.TestCase):
    def test_summary_from_history(self):
        from core.activity import summarize
        now = datetime(2026, 11, 11, 15, 0)
        def e(hours_ago, ok, cost, agents, dry=False):
            t = now - timedelta(hours=hours_ago)
            return {"task": f"pedido {hours_ago}", "started_at": t.isoformat(timespec="seconds"), "success": ok,
                    "dry_run": dry, "duration_ms": 1200, "metrics": {"api_calls": 2, "tokens_est": 500, "cost_usd": cost},
                    "subtasks": [{"agent": a} for a in agents]}
        items = [e(1, True, 0.02, ["WEB"]), e(2, False, 0.01, ["WEB", "DATA"]), e(30, True, 0.04, ["CODE"]),
                 e(3, True, 9.0, ["WEB"], dry=True), e(24 * 40, True, 1.0, ["FILE"])]
        out = summarize(items, now=now, pending={"question": "Envio a mensagem?", "kind": "confirm", "task": "x"},
                        running="pedido atual")
        self.assertEqual([t["time"] for t in out["today"]], ["14:00", "13:00"])      # simulacao fica de fora
        self.assertEqual(out["usage"]["runs"], 3)                                     # mes atual, sem simulacao
        self.assertAlmostEqual(out["usage"]["cost"], 0.07, places=4)
        shares = {s["agent"]: s["share"] for s in out["usage"]["segments"]}
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=6)
        self.assertGreater(shares["CODE"], shares["DATA"])
        self.assertEqual(len(out["usage"]["daily"]), 14)
        self.assertEqual(sum(map(sum, out["heatmap"]["rows"])), 3)                   # 40 dias atras fica fora
        self.assertEqual(out["attention"][0]["kind"], "confirm")
        self.assertEqual(out["running"], "pedido atual")
        empty = summarize([], now=now)
        self.assertEqual((empty["today"], empty["usage"]["segments"], empty["attention"]), ([], [], []))


class PlanSkipTests(unittest.TestCase):
    def controller(self):
        from desktop.controller import Controller
        c = Controller.__new__(Controller)
        c._lock = threading.Lock()
        c._plan_token = "tok"
        c._plan_gate = threading.Event()
        c._plan_ok = False
        c._plan_skip = set()
        c._cancel_event = threading.Event()
        c._effect_deadline = 0
        return c

    def test_approve_records_only_valid_step_numbers(self):
        c = self.controller()
        self.assertTrue(c.approve_plan(True, "tok", skip=[2, 0, -1, True, "3", 4]))
        self.assertEqual(c._plan_skip, {2, 4})
        self.assertTrue(c._plan_ok and c._plan_gate.is_set())
        c2 = self.controller()
        self.assertFalse(c2.approve_plan(True, "outro", skip=[1]))     # token errado nao decide nada
        self.assertEqual(c2._plan_skip, set())

    def test_skipped_steps_and_dependents_do_not_run(self):
        """O laco do controlador pula o passo escolhido e quem depende dele (sem contar como falha)."""
        from core.task_schedule import Availability, TaskSchedule

        schedule = TaskSchedule([{}, {"depends_on": 1}, {}], {1})
        self.assertEqual([schedule.availability(node) for node in schedule.nodes],
                         [Availability.SKIPPED, Availability.SKIPPED, Availability.READY])
        src = (APP / "desktop" / "controller.py").read_text(encoding="utf-8")
        self.assertIn("len(skipped_steps) >= len(plan.get(\"subtasks\", []))", src)   # pular tudo = nao executar


if __name__ == "__main__":
    unittest.main()
