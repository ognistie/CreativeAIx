"""
Perguntas sobre a tela ("você está vendo o YouTube?", "o que tem na tela?", "qual botão está aberto?").

Camada de harness: o agente Vision SO OLHA. Ele descreve o que aparece e aponta onde estao os elementos; nunca
clica, digita, salva ou grava. Quem age e o executor (core/automation.py), com as politicas em codigo. Aqui a
pergunta e respondida lendo a tela uma vez, sem nenhuma acao no computador.

Ordem de custo (do gratis ao pago):
  1. Leitura local (VisionEngine.read_local): titulo da janela da frente, URL do navegador e textos da arvore de
     acessibilidade. "Voce esta vendo o YouTube?" e "qual site esta aberto?" se respondem aqui, sem modelo.
  2. Interpretacao (VisionEngine.look): so quando a pergunta pede entender a imagem ("o que tem na tela?", "o video
     esta tocando?"). Vai o recorte da janela da frente para o modelo auxiliar (Haiku), com o titulo e a URL como
     contexto; o modelo principal so entra se o auxiliar nao tiver certeza.

Uso: o resolvedor da conversa (core/followup.py) marca a fala como kind="look" e o controller chama answer().
A voz (core/voice/understand.py) nunca responde "de cabeca" a uma pergunta sobre a tela: delega para ca.
"""

from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import urlparse

from core.lexicon import norm

# "voce esta vendo", "ta vendo", "consegue ver", "o que tem/aparece na tela", "o que voce ve", "esta aberto na tela"
_SCREEN = re.compile(
    r"\b(?:(?:voce|vc|tu)\s+(?:esta|ta|tá|consegue|pode)\s+(?:vendo|ver|enxergar)|(?:ta|esta)\s+vendo|consegue\s+ver|"
    r"(?:o\s+)?que\s+(?:tem|aparece|esta|ta)\s+(?:na|em)\s+(?:minha\s+)?tela|o\s+que\s+(?:voce|vc)\s+(?:ve|esta\s+vendo)|"
    r"(?:olh[ae]|veja|confere|confira)\s+(?:a|na|minha)\s+tela|na\s+tela\s+agora|aparece\s+na\s+tela)\b")
# Comando escondido na pergunta ("olha a tela e clica em X"): nao e so olhar, segue o fluxo de execucao
_ACT = re.compile(r"\b(?:e\s+)?(?:clic\w*|cliqu\w*|digit\w*|escrev\w*|abr[ae]\w*|fech\w*|salv\w*|apert\w*|"
                  r"envi\w*|mand\w*|pesquis\w*|toc\w*)\b")

# "voce esta vendo O YOUTUBE", "ta vendo A PLANILHA", "consegue ver O GMAIL agora?"
_PRESENCE = re.compile(r"\b(?:vendo|ver|enxergar)\s+(?:(?:o|a|os|as|um|uma|esse|essa|este|esta|meu|minha)\s+)?(.+)$")
# "qual site/janela/app esta aberto", "em que pagina eu estou", "que programa esta na frente"
_WHICH = re.compile(r"\b(?:qual|que|em\s+que)\s+(?:e\s+o\s+|e\s+a\s+)?(?:site|pagina|janela|app|aplicativo|programa|aba)\b")
_TAIL = re.compile(r"\s*\b(?:na|da|minha|em)\s+tela\b.*$|\s*\b(?:agora|ai|aqui|ali|ja|direito)\b.*$")
_VAGUE = {"", "tela", "isso", "isto", "aquilo", "algo", "alguma coisa", "nada", "tudo", "o que", "que"}
# Coisas que so a imagem responde: o titulo e os textos nao bastam para dizer "nao estou vendo"
_VISUAL = re.compile(r"\b(?:botao|botoes|video|imagem|imagens|foto|fotos|icone|icones|cor|cores|grafico|erro|"
                     r"aviso|mensagem|popup|janela|menu|cursor|mouse|seta|logo|desenho|tocando|pausado|carregando)\b")
_WORD_STOP = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "e", "no", "na", "um", "uma", "site", "app", "pagina"}
_POINTING = re.compile(r"\bvendo\s+(?:(?:ai|ali|aqui)\b|(?:esse|essa|isso|este|esta)\b|(?:o\s+)?endereco\b)")
_DETAIL = re.compile(r"\b(?:endereco|telefone|email|contato|preco|valor|numero|horario)\b")
_READING = re.compile(r"^(?:e\s+)?(?:qual|quais|que|quanto|leia|le|me\s+(?:diga|diz|leia|mostra))\b")
_ON_SCREEN = re.compile(r"\b(?:na\s+tela|nesse\s+resultado|nessa\s+pagina|ali|ai|aqui|visivel|aparecendo)\b")

LOCAL = "local"


def is_screen_question(text: str, *, visual_context: bool = False) -> bool:
    """A fala pergunta sobre o que esta na tela (e nao manda fazer nada)."""
    n = norm(text or "")
    looking = bool(_SCREEN.search(n) or _POINTING.search(n))
    reading = bool(_READING.search(n) and _DETAIL.search(n) and (visual_context or _ON_SCREEN.search(n)))
    which = bool(_WHICH.search(n) and re.search(r"\b(?:abert[oa]|frente|tela|agora)\b", n))
    return (looking or reading or which) and not _ACT.search(n)


def presence_target(question: str) -> str:
    """O que a pessoa quer saber se esta na tela ("o YouTube"), sem artigo nem cauda; '' se a pergunta e aberta."""
    n = norm(question or "").rstrip("?!. ")
    m = _PRESENCE.search(n)
    if not m:
        return ""
    target = _TAIL.sub("", m.group(1)).strip(" ?!.")
    return "" if target in _VAGUE else target


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _front(state: dict) -> str:
    """Nome curto do que esta na frente: 'YouTube - Google Chrome (youtube.com)'."""
    title = str(state.get("title") or "").strip()
    host = _host(str(state.get("url") or ""))
    return f"{title} ({host})" if host and host not in norm(title) else title


def _words(target: str) -> list[str]:
    return [w for w in norm(target).split() if w not in _WORD_STOP and len(w) > 1]


def local_answer(question: str, state: Optional[dict]) -> Optional[dict]:
    """Resposta sem modelo quando o titulo, a URL e os textos da janela bastam. None = precisa olhar a imagem.

    -> {"ok", "answer", "seen", "confidence", "via": "local"}"""
    if not isinstance(state, dict) or not str(state.get("title") or "").strip():
        return None
    front = _front(state)
    n = norm(question or "")
    head = norm(" ".join([str(state.get("title") or ""), _host(str(state.get("url") or "")), str(state.get("url") or "")]))
    body = norm(str(state.get("text") or ""))
    target = presence_target(question)
    if target:
        words = _words(target)
        if not words:
            return None
        joined = "".join(words)
        if all(w in head for w in words) or joined in head.replace(" ", ""):
            return _local(f"Sim, estou vendo {target}: na frente está {front}.", front, 0.95)
        if body and all(w in body for w in words):
            return _local(f"Sim, {target} aparece na janela da frente ({front}).", front, 0.85)
        if _VISUAL.search(norm(target)) or _DETAIL.search(norm(target)):
            return None            # "ta vendo esse botao?": so a imagem diz
        return _local(f"Não estou vendo {target}. Na frente está {front}.", front, 0.8)
    if _WHICH.search(n):
        return _local(f"Na frente está {front}.", front, 0.95)
    return None


def _local(text: str, seen: str, confidence: float) -> dict:
    return {"ok": True, "answer": text, "seen": seen, "confidence": confidence, "via": LOCAL,
            "observed_at": time.time()}


def answer(question: str, vision=None) -> dict:
    """-> {"ok", "answer", "seen", "via"}. Le a tela (local primeiro, imagem so se precisar) e responde. Nunca age."""
    if vision is None:
        try:
            from core.vision import VisionEngine
            vision = VisionEngine()
        except Exception as exc:
            return {"ok": False, "answer": f"Não consegui olhar a tela agora ({type(exc).__name__}).", "seen": ""}
    try:
        state = None
        reader = getattr(vision, "read_local", None)
        if callable(reader):
            try:
                state = reader()
            except Exception:
                state = None
        state = state if isinstance(state, dict) else None
        local = local_answer(question, state)
        if local is not None:
            return local
        result = vision.look(question, context=state) if state else vision.look(question)
    except Exception:
        return {"ok": False, "answer": "Não consegui consultar a tela agora. Pode tentar de novo?", "seen": ""}
    finally:
        try:
            vision.restore_browser()
        except Exception:
            pass
    if not isinstance(result, dict) or result.get("error"):
        return {"ok": False, "answer": "Não consegui ler a tela agora. Pode tentar de novo?", "seen": ""}
    text = str(result.get("answer") or "").strip()
    seen = str(result.get("seen") or "").strip()
    if not text:
        return {"ok": False, "answer": "Olhei a tela, mas não consegui responder com segurança.", "seen": seen}
    try:
        confidence = float(result.get("confidence")) if result.get("confidence") is not None else None
    except (TypeError, ValueError):
        confidence = None
    out = {"ok": True, "answer": text, "seen": seen, "via": str(result.get("model") or "vision")}
    out.update(confidence=confidence, observed_at=time.time())
    out["answer"] = confident_answer(out, confidence)
    return out


def confident_answer(result: dict, confidence: Optional[float]) -> str:
    """Resposta com a incerteza dita em voz alta quando a visao nao tem certeza (nunca afirma o que nao viu)."""
    text = result.get("answer", "")
    if confidence is not None and confidence < 0.6 and result.get("ok"):
        return "Não tenho certeza, mas parece que " + text[:1].lower() + text[1:]
    return text
