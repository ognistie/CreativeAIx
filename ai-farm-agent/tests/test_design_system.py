"""Estudo de design (docs/design/estudo-inspora.md), fases F1..F6: tokens, movimento, Atividade e plano por passo."""
import re
import sys
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
QML = APP / "desktop" / "qml"
SKIP_MOTION = {"Ambient.qml", "Splash.qml", "SplashWindow.qml", "Spinner.qml", "Theme.qml",
               "PhaseStepper.qml", "Skeleton.qml", "VoiceGlow.qml", "TaskOrb.qml"}   # pulsos continuos: param pelo `running: Theme.motion`


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.theme = (QML / "components" / "Theme.qml").read_text(encoding="utf-8")

    def test_f1_tokens_exist(self):
        for token in ("r1:", "r2:", "r3:", "r4:", "function nested(", "function dur(", "easeOut:", "press:",
                      "stagger:", "tabular:", "shadowSoft:", "edgeWidth:"):
            self.assertIn(token, self.theme)

    def test_motion_goes_through_theme_dur(self):
        """Duracao escrita a mao nao respeita "luzes paradas": tudo passa por Theme.dur (ou por motion ? x : 0)."""
        loose = []
        for path in QML.rglob("*.qml"):
            if path.name in SKIP_MOTION:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                m = re.search(r"duration:\s*([^;}\n]+)", line)
                if m and "dur(" not in m.group(1) and "motion" not in m.group(1):
                    loose.append(f"{path.name}:{n}: {m.group(1).strip()}")
        self.assertEqual(loose, [])

    def test_continuous_pulses_stop_with_still_lights(self):
        for name in ("PhaseStepper.qml", "Skeleton.qml", "VoiceGlow.qml", "TaskOrb.qml"):
            src = (QML / "components" / name).read_text(encoding="utf-8")
            self.assertIn("Theme.motion", src, name)

    def test_nav_items_accept_icon_names(self):
        src = (QML / "components" / "NavItem.qml").read_text(encoding="utf-8")
        self.assertIn("root.icon.length > 1", src)


class QuietIntelligenceTests(unittest.TestCase):
    """Especificacao de referencias (Auros, composer, voz, wallpaper em shader): o que nao pode regredir."""

    def test_shaders_are_compiled_next_to_their_sources(self):
        shaders = QML / "components" / "shaders"
        for name in ("mesh.frag", "fluted.frag"):
            src, qsb = shaders / name, shaders / (name + ".qsb")
            self.assertTrue(src.is_file() and qsb.is_file() and qsb.stat().st_size > 500, name)
            self.assertIn("qt_Opacity", src.read_text(encoding="utf-8"))

    def test_background_falls_back_without_gpu_and_pauses(self):
        amb = (QML / "components" / "Ambient.qml").read_text(encoding="utf-8")
        self.assertIn("GraphicsInfo.api !== GraphicsInfo.Software", amb)
        self.assertIn("visible: !root.meshOn", amb)                       # luzes quando a malha nao roda
        sw = (QML / "components" / "ShaderWallpaper.qml").read_text(encoding="utf-8")
        self.assertIn("interval: 33", sw)                                  # ~30 fps
        self.assertIn("root.running && root.speed > 0", sw)                # parado / minimizado nao anima
        self.assertIn("quality: 0.5", sw)
        main = (QML / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("win.visibility !== Window.Minimized", main)

    def test_voice_glow_reuses_the_existing_signal(self):
        glow = (QML / "components" / "VoiceGlow.qml").read_text(encoding="utf-8")
        self.assertNotIn("Bridge", glow)                                   # nada de abrir microfone pela UI
        for word in ("threshold", "attack", "release", "processing", "speaking"):
            self.assertIn(word, glow)
        comp = (QML / "components" / "Composer.qml").read_text(encoding="utf-8")
        self.assertIn("level: root.voiceLevel", comp)
        for phase in ('"error"', '"processing"', '"sending"', '"typing"', '"focus"', '"idle"'):
            self.assertIn(phase, comp)

    def test_new_palettes_and_background_settings_are_validated(self):
        from core.harness import validate, upgrade_style, DEFAULT, STYLE
        theme = (QML / "components" / "Theme.qml").read_text(encoding="utf-8")
        for name in ("abismo", "ameixa", "nevoa", "matcha", "seda"):
            self.assertEqual(theme.count(f'"{name}":'), 2, name)           # versao clara e escura
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


class TaskOrbTests(unittest.TestCase):
    """Mini chat como orbe: o trajeto abre com o cursor em cima, sem a janela receber cliques na tarefa."""

    def test_orb_states_and_hover_without_input(self):
        mini = (QML / "components" / "MiniChat.qml").read_text(encoding="utf-8")
        self.assertIn("passive ? (Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)", mini)
        self.assertIn("Bridge.cursorPos()", mini)                 # cursor em cima por posicao global
        self.assertIn('color: "transparent"', mini)
        self.assertIn("visible: !mini.passive", mini)              # durante a tarefa o painel so mostra
        orb = (QML / "components" / "TaskOrb.qml").read_text(encoding="utf-8")
        for state in ("running", "listening", "thinking", "speaking", "attention", "done", "failed"):
            self.assertIn(f'"{state}"', orb)
        self.assertNotIn("Bridge", orb)                            # a orbe so desenha; nao abre microfone

    def test_bridge_gives_the_cursor_position(self):
        src = (APP / "desktop" / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("def cursorPos(self)", src)


class KeyboardTests(unittest.TestCase):
    def test_base_controls_take_tab_enter_space_and_show_focus(self):
        for name in ("Button.qml", "Chip.qml", "NavItem.qml", "TogglePill.qml", "IconButton.qml"):
            src = (QML / "components" / name).read_text(encoding="utf-8")
            self.assertIn("activeFocusOnTab", src, name)
            self.assertIn("Qt.Key_Space", src, name)
            self.assertIn("Qt.Key_Return", src, name)
        for name in ("Button.qml", "Chip.qml", "NavItem.qml", "TogglePill.qml"):
            src = (QML / "components" / name).read_text(encoding="utf-8")
            self.assertIn("border.color: Theme.focusRing", src, name)
            self.assertIn("visible: root.activeFocus", src, name)


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
        src = (APP / "desktop" / "controller.py").read_text(encoding="utf-8")
        self.assertIn("if si + 1 in skipped or (dependency is not None and int(dependency) in skipped):", src)
        self.assertIn("len(skipped_steps) >= len(plan.get(\"subtasks\", []))", src)   # pular tudo = nao executar


if __name__ == "__main__":
    unittest.main()
