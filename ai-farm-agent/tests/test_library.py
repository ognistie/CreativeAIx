"""Biblioteca (core/library.py): aceite do briefing — dez temas completos, fontes rastreaveis, busca e filtros.
A conferencia dos links usa a rede e fica em scripts/check_library_links.py (fora do gate)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import library


class Catalog(unittest.TestCase):
    def test_ten_topics_with_everything_the_brief_asks(self):
        self.assertEqual(len(library.TOPICS), 10)
        ids = {t["id"] for t in library.TOPICS}
        self.assertEqual(len(ids), 10)
        for t in library.TOPICS:
            for field in ("title", "intro", "why", "practice"):
                self.assertTrue(t[field].strip(), (t["id"], field))
            self.assertIn(t["level"], library.LEVELS)
            self.assertGreaterEqual(len(t["terms"]), 3, t["id"])
            self.assertGreaterEqual(len(t["readings"]), 2, t["id"])
            self.assertTrue(set(t["prereqs"]) <= ids - {t["id"]}, t["id"])
            for r in t["readings"]:
                self.assertIn(r["kind"], library.KINDS, r["title"])
                self.assertTrue(r["url"].startswith("https://"), r["url"])
                self.assertTrue(r["title"] and r["authors"] and 2015 <= r["year"] <= 2026, r["title"])
                if r["kind"] == "pesquisa":
                    self.assertTrue(r["venue"], f"pesquisa publicada sem veiculo: {r['title']}")
        # tema experimental avisa o limite da evidencia
        self.assertTrue(library.topic("rlm")["limits"])

    def test_track_order_and_first_reading_for_beginners(self):
        track = library.track()
        self.assertEqual([t["order"] for t in track], list(range(1, 11)))
        self.assertEqual(track[0]["level"], "iniciante")
        self.assertIn("building-effective-agents", track[0]["readings"][0]["url"])

    def test_search_and_filters(self):
        self.assertEqual([t["id"] for t in library.search("circuit")], ["interpretability"])
        self.assertEqual([t["id"] for t in library.search("prefill")], ["serving"])
        self.assertIn("evals", [t["id"] for t in library.search("Lightman")])          # por autor
        self.assertTrue(all(t["level"] == "avancado" for t in library.search(level="avancado")))
        docs = library.search(kind="documentacao")
        self.assertTrue(docs and all(any(r["kind"] == "documentacao" for r in t["readings"]) for t in docs))
        self.assertEqual(library.search("memoria contexto")[0]["id"], "context")         # sem acento acha


if __name__ == "__main__":
    unittest.main()
