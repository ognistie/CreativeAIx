"""Voz em conversa longa: resposta presa a pergunta, memoria da conversa inteira e nada de acao sem pedido.

Casos tirados da sessao real de 2026-11-15 13:12-13:22: "voltar para a pagina anterior e clicar em 'imagens'"
virou pergunta; a resposta "imagens" foi reescrita como "abrir a pasta Imagens" e o app abriu a pasta do Windows.
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.followup import resolve
from core.session import Session
from core.voice.understand import understand


def no_llm(system, user):
    raise AssertionError("o modelo nao deveria ser chamado")


def fixed_llm(payload: str):
    return lambda system, user: payload


class PendingAnswerTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.s.add_turn("ir para o Google e pesquisar sobre Galáxia de Andrômeda", "pesquisar Galáxia de Andrômeda no Google",
                        "new", ["WEB"], True, "Pesquisa aberta")
        self.s.set_pending("Em qual aba devo clicar?", "voltar para a página anterior do navegador e clicar em 'imagens'")

    def test_short_answer_is_bound_to_the_question_without_the_model(self):
        u = understand("imagens", 1.0, self.s.context_block(), [], llm=no_llm, session=self.s, mode="live")
        self.assertEqual((u["kind"], u["command"], u["via"]), ("command", "imagens", "pendente"))
        res = resolve(u["command"], self.s)
        self.assertEqual(res["via"], "pending")
        self.assertIn("voltar para a página anterior", res["task"])
        self.assertIn("imagens", res["task"])
        self.assertNotIn("pasta", res["task"].lower())

    def test_clear_new_request_escapes_the_question(self):
        llm = fixed_llm('{"kind": "command", "command": "abrir o Excel", "reply": "Abrindo.", "confidence": 0.95}')
        u = understand("na verdade abre o Excel", 1.0, self.s.context_block(), [], llm=llm, session=self.s, mode="live")
        self.assertNotEqual(u["via"], "pendente")

    def test_expired_question_does_not_capture_new_speech(self):
        self.s.pending["at"] = time.time() - 10_000
        llm = fixed_llm('{"kind": "chat", "command": "", "reply": "Oi!", "confidence": 0.9}')
        u = understand("bom dia", 1.0, "", [], llm=llm, session=self.s, mode="live")
        self.assertNotEqual(u["via"], "pendente")


class GroundingTests(unittest.TestCase):
    def test_loose_word_never_becomes_an_action(self):
        llm = fixed_llm('{"kind": "command", "command": "abrir a pasta Imagens", "reply": "Abrindo.", "confidence": 0.9}')
        u = understand("imagens", 1.0, "", [], llm=llm, session=Session(), mode="live")
        self.assertEqual(u["kind"], "unclear")
        self.assertIn("abrir a pasta Imagens", u["guess"])
        self.assertTrue(u["reply"].endswith("?"))

    def test_short_answer_to_an_offer_still_acts(self):
        s = Session()
        s.add_turn("pesquisa lofi no youtube", "pesquisar lofi no YouTube", "new", ["WEB"], True, "Resultados abertos")
        s.set_last_reply("Quer que eu toque o primeiro?")
        llm = fixed_llm('{"kind": "command", "command": "tocar o primeiro vídeo", "reply": "Tocando.", "confidence": 0.95}')
        u = understand("o primeiro", 1.0, s.context_block(), [], llm=llm, session=s, mode="live")
        self.assertEqual(u["kind"], "command")

    def test_full_request_is_not_blocked(self):
        llm = fixed_llm('{"kind": "command", "command": "abrir o Bloco de Notas e escrever sobre Andrômeda", '
                        '"reply": "Abrindo.", "confidence": 0.95}')
        u = understand("abre o bloco de notas e escreve sobre andromeda", 1.0, "", [], llm=llm, session=Session(), mode="live")
        self.assertEqual(u["kind"], "command")


class LongConversationMemoryTests(unittest.TestCase):
    def test_everything_done_stays_in_the_context(self):
        s = Session()
        s.add_turn("abrir o Bloco de Notas", "abrir o Bloco de Notas", "new", ["DESKTOP"], True, "Bloco de Notas aberto")
        for i in range(30):
            s.add_turn(f"pedido {i}", f"pesquisar assunto {i} no Google", "new", ["WEB"], i % 4 != 0, f"busca {i}")
        ctx = s.context_block(4800)
        self.assertIn("FEITO NESTA CONVERSA", ctx)
        self.assertIn("pesquisar assunto 29", ctx)                 # recente, detalhado
        self.assertIn("[falhou]", ctx)                             # o que deu errado tambem fica
        self.assertLessEqual(len(ctx), 4800)

    def test_chat_is_not_listed_as_done(self):
        s = Session()
        for i in range(8):
            s.add_turn("valeu", "valeu", "chat", [], True, "")
        self.assertEqual(s.done_log(), "")


class BrowserPilotTests(unittest.TestCase):
    def test_pilot_can_close_the_current_tab(self):
        from core import browser_pilot
        self.assertIn("close_tab()", browser_pilot.SYSTEM)
        self.assertIn('if act == "close_tab"', Path(browser_pilot.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
