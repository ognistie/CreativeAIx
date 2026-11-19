"""Incidente 2026-11-17: o Codex criou o site em "Nova pasta (2)", mas "abra novamente" abriu o site de "Nova pasta".

Causa: o caminho citado era limpo com rstrip(".,;)"), que arrancava o ")" de "(2)"; "Nova pasta (2" nao existia, a
ultima palavra era cortada e sobrava "Nova pasta", uma pasta vizinha que existia (outro projeto). Correcao: um so
resolvedor (core.paths.existing_prefix) que so corta palavras de continuacao da frase; caminho citado que nao
existe vira pergunta, nunca outra pasta.
"""

import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

from core.paths import existing_prefix


class FolderSuffixIncident(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.old = os.path.join(self.root, "Nova pasta")          # projeto anterior (Hogwarts)
        self.new = os.path.join(self.root, "Nova pasta (2)")      # projeto pedido (F1)
        for folder in (self.old, self.new):
            os.makedirs(folder)
            with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
                f.write("<html></html>")
        self.new_slash = self.new.replace(os.sep, "/")

    def test_resolver_keeps_the_parenthesized_suffix(self):
        for tail in ("", " no navegador", ".", " e depois abre o site", ") ", " com o Codex"):
            self.assertEqual(existing_prefix(self.new_slash + tail), os.path.normpath(self.new), repr(tail))

    def test_missing_cited_folder_never_falls_back_to_a_sibling(self):
        missing = os.path.join(self.root, "Nova pasta (3)").replace(os.sep, "/")
        self.assertIsNone(existing_prefix(missing))
        self.assertIsNone(existing_prefix(missing + " no navegador"))
        self.assertIsNone(existing_prefix(os.path.join(self.root, "Nova pasta Final").replace(os.sep, "/")))

    def test_reopen_request_opens_the_cited_project(self):
        """O pedido real, como o resolvedor da conversa o reescreveu."""
        from core.existing_targets import existing_plan
        for task in (f"abrir novamente no navegador o arquivo index.html do projeto em {self.new_slash}",
                     f"abrir o index.html do projeto em {self.new_slash} no navegador"):
            plan = existing_plan(task, SimpleNamespace(code={"folder": self.old}, folder=None, turns=[]))
            path = plan["subtasks"][0]["params"]["existing"]["path"]
            self.assertEqual(os.path.dirname(os.path.normpath(path)), os.path.normpath(self.new), task)

    def test_plain_open_keeps_the_exact_folder_without_a_project(self):
        from core.existing_targets import existing_plan
        plan = existing_plan(f'Abra a pasta "{self.new_slash}"')
        target = plan["subtasks"][0]["params"]["existing"]["path"]
        self.assertEqual(os.path.normpath(target), os.path.normpath(self.new))
        missing = self.new_slash.replace("(2)", "(3)")
        self.assertTrue(existing_plan(f"Abra a pasta {missing}")["needs_clarification"])
        self.assertIsNone(existing_plan(f"Abra a pasta {self.new_slash} e depois mova um arquivo"))

    def test_reopen_with_missing_cited_folder_asks_instead_of_using_the_old_project(self):
        from core.existing_targets import existing_plan
        missing = os.path.join(self.root, "Nova pasta (3)").replace(os.sep, "/")
        plan = existing_plan(f"abra o site do projeto em {missing} no navegador",
                             SimpleNamespace(code={"folder": self.old}, folder=None, turns=[]))
        self.assertTrue(plan.get("needs_clarification"))
        self.assertIn("Nova pasta (3)", plan["question"])

    def test_codex_never_writes_in_a_sibling_folder(self):
        from unittest.mock import patch
        from agents.extcode_agent import extcode_plan
        session = SimpleNamespace(code={"folder": self.old}, folder=None, turns=[])
        # No gate a pasta temporaria fica dentro do app, que a politica (folder_error) recusa de proposito; aqui
        # o que se testa e a escolha da pasta, nao essa regra.
        self.enterContext(patch("agents.extcode_agent.folder_error", return_value=""))
        plan = extcode_plan(f"Faça um site sobre Fórmula 1 com o Codex na pasta {self.new_slash}", session)
        self.assertEqual(os.path.normpath(plan["subtasks"][0]["params"]["folder"]), os.path.normpath(self.new))
        missing = os.path.join(self.root, "Nova pasta (3)").replace(os.sep, "/")
        asked = extcode_plan(f"Faça um site sobre Fórmula 1 com o Codex na pasta {missing}", session)
        self.assertTrue(asked.get("needs_clarification"))
        self.assertFalse(asked.get("subtasks"))


if __name__ == "__main__":
    unittest.main()
