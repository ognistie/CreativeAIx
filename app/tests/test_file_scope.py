"""Escopo do agente de Arquivos (core/file_contracts.request_roots + PathResolver).

Achado do AI Research Lab: nomes de pastas conhecidas DENTRO de um caminho citado ("...\\Documents\\proj",
"...\\Downloads\\fotos\\viagem") ampliavam o escopo autorizado para Documentos, Downloads e Imagens inteiros.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.file_contracts import request_roots, validate


class ScopeComesFromWhatWasSaid(unittest.TestCase):
    def test_folder_words_inside_a_cited_path_do_not_widen_the_scope(self):
        roots = request_roots(r"mova a.txt para b dentro de C:\Users\Fulano\Downloads\fotos\viagem")
        self.assertEqual([os.path.normcase(r) for r in roots],
                         [os.path.normcase(os.path.realpath(r"C:\Users\Fulano\Downloads\fotos\viagem"))])
        roots = request_roots(r"organize os arquivos de C:\Users\Fulano\Documents\GitHub\proj\caso")
        self.assertEqual(len(roots), 1)

    def test_a_sibling_of_the_cited_folder_stays_out(self):
        task = r"organize por tipo os arquivos de C:\Users\Fulano\Documents\proj\caso"
        step = [{"action": "move_file", "params": {"source": r"C:\Users\Fulano\Documents\proj\caso\foto.jpg",
                                                   "destination": r"C:\Users\Fulano\Documents\proj\fora\foto.jpg"}}]
        self.assertIn("fora do escopo", validate(step, request_roots(task)).lower())

    def test_known_folders_named_in_the_text_still_count(self):
        from core.paths import known_folder
        roots = [os.path.normcase(r) for r in request_roots(r"copie os pdfs da pasta documentos para C:\backup")]
        self.assertIn(os.path.normcase(os.path.realpath(known_folder("Documents"))), roots)
        self.assertIn(os.path.normcase(os.path.realpath(r"C:\backup")), roots)


if __name__ == "__main__":
    unittest.main()
