"""Segundo cerebro proprio: camadas base/pessoal, edicao, links, busca, Harness e Voce.
Tudo em pastas temporarias com notas ficticias (repositorio publico)."""
import json
import tempfile
import unittest
from pathlib import Path

from core.brain import Brain
from core.brain_store import BrainStore, clean_rel, links_in
from core.harness import DEFAULT, Harness, YOU_SECTIONS, validate, you_block, you_rel, you_template


def _vault(root: Path) -> Path:
    base = root / "base"
    (base / "10 Agentes" / "Desktop").mkdir(parents=True)
    (base / "60 Aprendizados").mkdir(parents=True)
    (base / ".obsidian").mkdir()
    (base / "10 Agentes" / "Desktop" / "Desktop Agent.md").write_text(
        "# Desktop\n\n## Regras de execucao\nUse atalhos do teclado. Veja [[Mapa]].\n", encoding="utf-8")
    (base / "Mapa.md").write_text("# Mapa\n\nLiga [[Desktop Agent]] e [[Inexistente]].\n", encoding="utf-8")
    (base / "60 Aprendizados" / "Licoes.md").write_text(
        "> [!lesson] Janela errada no bloco de notas\n> **Regra:** confirmar o titulo da janela\n", encoding="utf-8")
    (base / ".obsidian" / "x.md").write_text("oculto", encoding="utf-8")
    return base


class Layers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.base = _vault(root)
        self.personal = root / "pessoal"
        self.store = BrainStore(self.base, self.personal)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_without_personal_layer_listing_matches_vault(self):
        plain = BrainStore(self.base)
        self.assertEqual([r for r, _ in plain.files()],
                         [f.relative_to(self.base).as_posix() for f in self.base.rglob("*.md")
                          if ".obsidian" not in f.parts])
        with self.assertRaises(PermissionError):
            plain.write("Nova.md", "x")

    def test_editing_a_factory_note_never_touches_the_repo(self):
        original = (self.base / "Mapa.md").read_text(encoding="utf-8")
        self.store.write("Mapa.md", "# Mapa\n\nmeu texto\n")
        self.assertEqual((self.base / "Mapa.md").read_text(encoding="utf-8"), original)
        self.assertIn("meu texto", self.store.read("Mapa.md"))
        self.assertEqual(self.store.layer_of("Mapa.md"), "editada")
        self.store.restore("Mapa.md")
        self.assertEqual(self.store.read("Mapa.md"), original)

    def test_delete_hides_factory_note_and_restore_brings_it_back(self):
        self.store.delete("Mapa.md")
        self.assertEqual(self.store.read("Mapa.md"), "")
        self.assertNotIn("Mapa.md", [n["rel"] for n in self.store.notes()])
        self.assertTrue((self.base / "Mapa.md").exists())
        self.store.restore("Mapa.md")
        self.assertIn("Mapa.md", [n["rel"] for n in self.store.notes()])

    def test_personal_note_goes_to_trash(self):
        self.store.create("Ideias/Projeto.md", "# Projeto\n")
        self.assertEqual(self.store.layer_of("Ideias/Projeto.md"), "pessoal")
        self.store.delete("Ideias/Projeto.md")
        self.assertFalse((self.personal / "Ideias" / "Projeto.md").exists())
        self.assertTrue(list((self.personal / ".lixeira").rglob("Projeto.md")))

    def test_rename_updates_links_everywhere(self):
        out = self.store.rename("Mapa.md", "Mapa geral.md")
        self.assertEqual(out["links"], 1)
        self.assertIn("[[Mapa geral]]", self.store.read("10 Agentes/Desktop/Desktop Agent.md"))
        self.assertEqual(self.store.read("Mapa.md"), "")
        self.assertIn("[[Mapa]]", (self.base / "10 Agentes/Desktop/Desktop Agent.md").read_text(encoding="utf-8"))

    def test_links_backlinks_and_graph(self):
        links = {l["target"]: l["rel"] for l in self.store.links("Mapa.md")}
        self.assertEqual(links["Desktop Agent"], "10 Agentes/Desktop/Desktop Agent.md")
        self.assertIsNone(links["Inexistente"])
        self.assertEqual([b["rel"] for b in self.store.backlinks("Mapa.md")],
                         ["10 Agentes/Desktop/Desktop Agent.md"])
        g = self.store.graph()
        self.assertEqual(len(g["nodes"]), 3)
        self.assertEqual(len(g["edges"]), 2)

    def test_search_ignores_accents_and_sees_edits(self):
        self.assertEqual(self.store.search("atalhos teclado")[0]["rel"], "10 Agentes/Desktop/Desktop Agent.md")
        self.store.write("Mapa.md", "# Mapa\n\nRotina de revisão semanal\n")
        self.assertEqual(self.store.search("revisao")[0]["rel"], "Mapa.md")
        self.assertEqual(self.store.search("x"), [])

    def test_unsafe_paths_are_rejected(self):
        for bad in ("../fora.md", "..\\fora.md", ".cerebro/x.md", "a/<b>.md", ""):
            with self.assertRaises(ValueError):
                clean_rel(bad)
        self.assertEqual(clean_rel("Pasta\\Nota"), "Pasta/Nota.md")
        self.assertEqual(links_in("[[A|apelido]] [[B#titulo]] [[A]]"), ["A", "B"])


class HarnessAndYou(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.base = _vault(root)
        self.personal = root / "pessoal"

    def tearDown(self):
        self.tmp.cleanup()

    def test_invalid_harness_falls_back_to_defaults(self):
        data = validate({"agents": {"CODE": {"instructions": 5}, "HACKER": {"instructions": "x"}},
                         "appearance": {"accent": "red", "ambient": "muito", "motion": "sim"},
                         "response": {"tone": "grito"}, "extra": True})
        self.assertEqual(data, DEFAULT)
        self.assertEqual(validate({"appearance": {"ambient": 7}})["appearance"]["ambient"], 1.0)

    def test_versions_undo_changes(self):
        h = Harness(self.personal)
        h.save({"appearance": {"accent": "#FF6A3D"}}, label="laranja")
        h.save({"appearance": {"accent": "#7C5CFF"}}, label="lilas")
        self.assertEqual(h.load()["appearance"]["accent"], "#7C5CFF")
        first = h.versions()[0]["id"]
        h.restore(first)
        self.assertEqual(h.load()["appearance"]["accent"], "#FF6A3D")
        with self.assertRaises(ValueError):
            h.restore("../../x")

    def test_user_layer_enters_context_only_when_written(self):
        brain = Brain(str(self.base), personal_path=str(self.personal))
        plain = Brain(str(self.base))
        task = "usar atalhos no bloco de notas"
        self.assertEqual(brain.context_for("DESKTOP", task), plain.context_for("DESKTOP", task))
        # Modelo vazio da secao Voce nao entra no prompt
        for section, hint in YOU_SECTIONS:
            brain.store.write(you_rel(section), you_template(section, hint))
        self.assertEqual(you_block(brain.store), ("", []))
        brain.store.write(you_rel("Jeito de falar"), you_template("Jeito de falar", "dica") + "Digo 'bloquinho' para o Bloco de Notas.")
        brain.harness.save({"agents": {"DESKTOP": {"instructions": "Prefira atalhos de teclado."}}})
        ctx = brain.context_for("DESKTOP", task)
        self.assertIn("bloquinho", ctx)
        self.assertIn("Prefira atalhos de teclado.", ctx)
        self.assertNotIn("dica", ctx)
        self.assertIn("Harness", brain.last_sources["DESKTOP"])

    def test_personal_lesson_and_edit_reach_the_agents(self):
        brain = Brain(str(self.base), personal_path=str(self.personal))
        brain.store.write("10 Agentes/Desktop/Desktop Agent.md",
                          "# Desktop\n\n## Regras de execucao\nRegra pessoal nova.\n")
        self.assertIn("Regra pessoal nova.", brain.agent_guide("DESKTOP"))
        brain.store.write("60 Aprendizados/Minhas.md",
                          "> [!lesson] Planilha aberta duas vezes\n> **Regra:** reutilizar a janela da planilha\n")
        rules = [l["rule"] for l in brain.find_lessons("abrir a planilha de novo na janela")]
        self.assertIn("reutilizar a janela da planilha", rules)


if __name__ == "__main__":
    unittest.main()
