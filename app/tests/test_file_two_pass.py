"""FileAgent: pedido de ACAO nao termina so listando a pasta (achado do modo real do AI Research Lab).

O prompt manda "liste primeiro e pare" quando o modelo nao conhece a pasta. Em "mova notas.txt para a subpasta
arquivo" isso acabava a tarefa sem mover nada. Agora a leitura validada roda localmente e o modelo planeja de
novo com os nomes reais. Modelo falso: nenhuma chamada paga.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeClient:
    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def message(self, model, system, user_content, **kw):
        self.prompts.append(user_content)
        return json.dumps(self.replies.pop(0))


class ActAfterLooking(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="file-two-pass-")).resolve()
        (self.ws / "notas.txt").write_text("lista de compras", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def agent(self, replies):
        from agents.file_agent import FileAgent
        fake = FakeClient(replies)
        with patch("agents.base_agent.get_client", lambda: fake):
            a = FileAgent()
        a._client = fake
        return a, fake

    def test_move_request_plans_the_move_after_listing(self):
        ws = str(self.ws)
        a, fake = self.agent([
            {"steps": [{"action": "list_files", "params": {"path": ws}, "description": "ver a pasta"}]},
            {"steps": [{"action": "create_folder", "params": {"path": ws + "\\arquivo"}},
                       {"action": "move_file", "params": {"source": ws + "\\notas.txt", "destination": ws + "\\arquivo\\notas.txt"}}]},
        ])
        plan = a.plan(f"mova notas.txt para a subpasta arquivo, dentro de {ws}")
        self.assertEqual([s["action"] for s in plan["steps"]], ["create_folder", "move_file"])
        self.assertEqual(len(fake.prompts), 2)
        self.assertIn("notas.txt", fake.prompts[1])                       # o modelo viu a listagem real
        self.assertIn("O QUE HA NA PASTA", fake.prompts[1])
        # executa pelo mesmo caminho do app e confere no disco
        from core.lab import _FileExec
        ex = _FileExec()
        for st in plan["steps"]:
            self.assertTrue(ex.run(st["action"], st["params"])[0], st)
        self.assertTrue((self.ws / "arquivo" / "notas.txt").is_file())
        self.assertFalse((self.ws / "notas.txt").exists())

    def test_listing_request_stays_one_call(self):
        ws = str(self.ws)
        a, fake = self.agent([{"steps": [{"action": "list_files", "params": {"path": ws}}]}])
        plan = a.plan(f"liste os arquivos de {ws}")
        self.assertEqual([s["action"] for s in plan["steps"]], ["list_files"])
        self.assertEqual(len(fake.prompts), 1)

    def test_imperative_verbs_are_recognized(self):
        from agents.file_agent import _detect_operation
        self.assertEqual(_detect_operation("mova notas.txt para a pasta arquivo"), "move")
        self.assertEqual(_detect_operation("copie a.txt para b.txt"), "copy")


class ReplayWithLongAndShortPaths(unittest.TestCase):
    def test_recorded_plan_is_portable_whatever_path_form_the_model_used(self):
        from core.lab import Lab, replay_planner
        d = Path(tempfile.mkdtemp(prefix="lab-portable-"))
        try:
            lab = Lab(d)
            v = lab.versions("FILE")[0]
            lab.save_eval_set("um", [{"id": "criar", "task": "crie a pasta relatorios dentro de {ws}", "setup": {},
                                      "expect": {"exists": ["relatorios/"]}}])

            def long_form(version, task):          # o modelo escreve o caminho REAL (nome longo)
                import re
                ws = re.search(r"([A-Za-z]:\\[^\s]*?lab-caso-[^\\\s]+\\caso)", task).group(1)
                return {"steps": [{"action": "create_folder", "params": {"path": os.path.realpath(ws) + "\\relatorios"}}]}
            real = lab.run("um", [v["id"]], long_form, origin="real")
            self.assertEqual(real["results"][0]["plan"][0]["params"]["path"], "{ws}\\relatorios")
            sim = lab.run("um", [v["id"]], replay_planner(lab), origin="simulado")
            self.assertEqual(sim["summary"][v["id"]]["passed"], 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
