"""Estudio de agentes (core/agent_studio.py): especificacao, codigo so leitura em lista fechada, memoria e
contexto ligado gravados na camada pessoal e entrando no prompt como referencia."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import agent_studio as S  # noqa: E402
from core.brain import Brain  # noqa: E402

VAULT = Path(__file__).resolve().parents[2] / "vault"


class Sections(unittest.TestCase):
    MD = "# Data Agent\n\n## Regras de execução\n- a\n- b\n\n## Como navegar e executar\n- c\n\n## Skills\n- s\n"

    def test_read_with_or_without_accents(self):
        self.assertEqual(S.section(self.MD, "Regras de execucao"), "- a\n- b")
        self.assertEqual(S.section(self.MD, "como navegar"), "- c")

    def test_replace_keeps_other_sections(self):
        out = S.set_section(self.MD, "Regras de execução", "- nova")
        self.assertEqual(S.section(out, "Regras de execução"), "- nova")
        self.assertEqual(S.section(out, "Skills"), "- s")
        self.assertEqual(S.section(out, "Como navegar e executar"), "- c")

    def test_append_and_remove(self):
        out = S.set_section(self.MD, "Contexto extra", "texto")
        self.assertTrue(out.rstrip().endswith("## Contexto extra\ntexto"))
        self.assertNotIn("Contexto extra", S.set_section(out, "Contexto extra", ""))
        self.assertEqual(S.set_section(self.MD, "Nao existe", ""), self.MD)

    def test_links(self):
        self.assertEqual(S.parse_links("- [[A]]\n- [[B|apelido]] [[a]] [[C#sec]]"), ["A", "B", "C"])


class Source(unittest.TestCase):
    def test_closed_list(self):
        rels = [f["path"] for f in S.files("data")]
        self.assertIn("agents/data_agent.py", rels)
        self.assertIn("core/action_policy.py", rels)            # compartilhado
        self.assertIn("def ", S.source("DATA", "agents/data_agent.py")["text"])
        for bad in ("../config.yaml", "core/config.py", "agents/web_agent.py", "C:/Windows/win.ini"):
            with self.assertRaises(ValueError, msg=bad):
                S.source("DATA", bad)
        with self.assertRaises(ValueError):
            S.files("ROOT")


class Memory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.brain = Brain(str(VAULT), personal_path=str(self.tmp / "pessoal"))

    def tearDown(self):
        self.brain.store.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_spec_has_what_the_screen_needs(self):
        spec = S.spec("DATA", self.brain)
        self.assertTrue(spec["role"])
        self.assertIn("create_workbook", [t["name"] for t in spec["tools"]])
        self.assertIn("model", spec["config"])
        self.assertTrue(any(p["id"].startswith("POL-") for p in spec["policies"]))

    def test_save_goes_to_personal_layer_and_into_the_prompt(self):
        factory = (VAULT / "10 Agentes/Data/Data Agent.md").read_text(encoding="utf-8")
        mem = S.save("DATA", {"extra": "Prefiro planilhas com cabecalho azul.", "links": ["Maestro", "Nao existe"]}, self.brain)
        self.assertEqual(mem["layer"], "editada")
        self.assertEqual([l["title"] for l in mem["links"]], ["Maestro", "Nao existe"])
        self.assertTrue(mem["links"][0]["rel"])
        self.assertEqual(mem["links"][1]["rel"], "")
        self.assertEqual((VAULT / "10 Agentes/Data/Data Agent.md").read_text(encoding="utf-8"), factory)  # fabrica intacta
        text, used = S.linked_context("DATA", self.brain)
        self.assertIn("cabecalho azul", text)
        self.assertEqual(used, ["Maestro"])
        self.assertIn("cabecalho azul", self.brain.context_for("DATA", "crie uma planilha de gastos"))

    def test_rules_edit_reaches_agent_notes(self):
        S.save("DATA", {"rules": "- Sempre congelar a primeira linha."}, self.brain)
        self.assertIn("congelar a primeira linha", self.brain.agent_notes("DATA"))

    def test_limits(self):
        with self.assertRaises(ValueError):
            S.save("DATA", {"extra": "x" * (S.SECTION_MAX["extra"] + 1)}, self.brain)
        with self.assertRaises(ValueError):
            S.save("DATA", {"links": "Maestro"}, self.brain)
        mem = S.save("DATA", {"links": [f"N{i}" for i in range(30)]}, self.brain)
        self.assertEqual(len(mem["links"]), S.LINKS_MAX)


if __name__ == "__main__":
    unittest.main()
