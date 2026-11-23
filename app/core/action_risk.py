"""
Autorizacao por efeito: o que uma acao faz fora do computador, decidido pelo app e nao pelo modelo.

A autorizacao por agente (core/action_policy.py) diz qual ferramenta cada agente usa. Ela nao ve o
efeito: o piloto do navegador pode clicar em "Enviar" ou "Comprar" e so uma frase no prompt o
impedia. Aqui o efeito e classificado pelo que a acao toca (nome do botao, campo, tecla, tipo de
operacao) e cada caso sensivel passa por esta porta.

Modos (config.yaml > execution.authorization):
  shadow   so registra o que seria bloqueado; nada muda para a pessoa
  enforce  efeito sensível só com aprovação explícita (padrão)
  off      desligado
O registro em memory/authorization.jsonl guarda o rotulo do elemento (ex.: "Enviar"), nunca o
texto digitado nem o conteudo da pagina.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Optional

LOG = Path(__file__).resolve().parents[1] / "memory" / "authorization.jsonl"
MODES = ("off", "shadow", "enforce")
_lock = threading.Lock()

# Efeito fora do computador ou dificil de desfazer. O rotulo e normalizado sem acento.
KINDS = (
    ("pagar", r"\b(?:pag(?:ar|ue|a)|pagamento|finalizar (?:compra|pedido)|fechar pedido|checkout|pay|place order|"
              r"confirmar (?:compra|pedido|pagamento)|assinar plano|subscribe)\b"),
    ("comprar", r"\b(?:compr(?:ar|e|a)|buy now|buy|adicionar ao carrinho|add to cart)\b"),
    ("transferir", r"\b(?:transferir|transfere|transferencia|pix|enviar dinheiro|send money)\b"),
    ("excluir", r"\b(?:exclu(?:ir|a|i)|apag(?:ar|a|ue)|delet(?:ar|a|e)|delete|remov(?:er|a|e)|remove|descartar|"
                r"discard|esvaziar lixeira|desinstal(?:ar|a|e)|uninstall|formatar)\b"),
    # Seguir/curtir/compartilhar tambem aparecem para outras pessoas: contam como publicar
    ("publicar", r"\b(?:public(?:ar|a|que)|post(?:ar|a|e)|post|publish|tweetar|tweet|compartilhar publicamente|share|"
                 r"compartilh(?:ar|a|e)|repost(?:ar|a|e)?|retweet(?:ar)?|curt(?:ir|a|e)|like|reagir|follow)\b"),
    ("enviar", r"\b(?:envi(?:ar|a|e)|mand(?:ar|a|e)|send|responder a todos|reply all|encaminh(?:ar|a|e)|forward|"
               r"submit|submeter|dispar(?:ar|a|e)|manda bala|joga (?:no|na|pro|pra) (?:grupo|chat|conversa))\b"),
    # Chamada de voz/video para uma pessoa real
    # "ligar o bluetooth" nao conta: so ligar PARA alguem (o botao "Ligar" sozinho e tratado em label_risk)
    ("ligar", r"\b(?:(?:ligar|ligue|liga) (?:pro|pra|para)|ligacao|chamada(?: de (?:audio|video|voz))?|videochamada|"
              r"video ?chamada|iniciar chamada|call|audio call|video call|start call|discar|dial)\b"),
    ("conta", r"\b(?:sair da (?:sua )?conta|desconect(?:ar|e)|log ?out|sign out|encerrar (?:a )?sessao)\b"),
    # Inclui a tela de consentimento OAuth: "Permitir"/"Allow" entrega a conta a um app de terceiro
    ("aceitar", r"\b(?:aceito|aceitar|concordo|i agree|accept terms|aceitar os termos|assinar documento|sign|"
                r"permitir|allow|autorizar|authorize|conceder acesso|grant access)\b"),
    ("bloquear", r"\b(?:bloque(?:ar|ie|ia)|block|denunci(?:ar|e|a)|report)\b"),
)
# Campo onde Enter manda o texto para alguem
_MESSAGE_FIELD = r"\b(?:mensagem|message|digite uma mensagem|type a message|comentario|comment|chat|resposta|reply|tweet|post)\b"
_BROWSER_INPUT = re.compile(
    r"(?:barra de endereco|endereco|address bar|address|url|"
    r"(?:pesquisar|pesquisa|buscar|busca|search)(?: (?:no google|no bing|google|bing))?)")
# Confirmacao dita pela pessoa no proprio pedido
_CONFIRM = r"\b(?:confirmo|confirmado|pode (?:enviar|comprar|pagar|publicar|excluir|apagar|postar|mandar|transferir)|" \
           r"tenho certeza|sim,? (?:pode|envia|manda|compra|paga)|autorizo)\b"


def _norm(text: str) -> str:
    from core.lexicon import norm
    return norm(text or "")


# Botao de enviar uma BUSCA (o do Google se chama "Enviar consulta de pesquisa"). Estreito de proposito:
# uma palavra de busca qualquer no rotulo nao basta ("Enviar pesquisa de satisfacao" envia).
_SEARCH_SUBMIT = r"\b(?:enviar consulta|submit (?:search|query)|search submit)\b"


def label_risk(label: str) -> Optional[str]:
    """Efeito de clicar em um elemento com este rotulo. None = nada sensivel."""
    text = _norm(label)
    if not text:
        return None
    for kind, pattern in KINDS:
        if re.search(pattern, text):
            return None if kind == "enviar" and re.search(_SEARCH_SUBMIT, text) else kind
    # Botoes de uma palavra que, no pedido, seriam outra coisa ("ligar o bluetooth", "seguir as instrucoes")
    if re.fullmatch(r"ligar(?: (?:agora|para .{1,40}|pra .{1,40}))?", text):
        return "ligar"
    if re.fullmatch(r"(?:seguir|siga)(?: (?:@?\S+|de volta|tambem))?", text):
        return "publicar"
    return None


_DELETE_KEYS = ({"delete"}, {"del"}, {"shift", "delete"}, {"shift", "del"})


def ui_risk(act: str, label: str = "", submit: bool = False, key: str = "", web: bool = False,
            window: str = "", app: bool = False) -> Optional[str]:
    """Efeito de uma acao de piloto: clique, digitar com Enter, ou tecla.

    No navegador (web=True), digitar com Enter envia o formulario: conta como "enviar" em
    qualquer campo que nao seja busca ou endereco. O rotulo do campo nao e confiavel (o chat de
    um webmail se chamava "Historico ativado" e o Enter mandou a mensagem sem passar por aqui).
    Num app (app=True), Enter envia numa janela de mensagem (pelo titulo, lido do sistema) e num campo
    sem nome: apps Electron/WebView2 (Slack, Teams, Discord) nao dao nome ao campo de mensagem."""
    act = (act or "").lower()
    if act in ("click", "double_click", "vision_click"):
        return label_risk(label)
    pressed = set(norm_keys(key)) if key else set()
    if act == "press" and pressed in _DELETE_KEYS:
        return "excluir"
    field = _norm(label)
    messaging = bool(window) and bool(re.search(_MESSAGING_WINDOW, _norm(window)))
    sends = (bool(re.search(_MESSAGE_FIELD, field)) or messaging or (app and not field.strip())
             or (web and not _BROWSER_INPUT.fullmatch(field)))
    if act == "type" and submit and sends:
        return "enviar"
    enter = pressed in ({"enter"}, {"ctrl", "enter"})
    if act == "press" and enter and sends:
        return "enviar"
    return None


# Janela de app de mensagem/e-mail: Enter (ou Ctrl+Enter, Alt+S) ali manda o texto para alguem.
# Vem do titulo da janela em primeiro plano, lido do sistema, nunca do plano do modelo.
_MESSAGING_WINDOW = (r"\b(?:whatsapp|microsoft teams|teams|outlook|telegram|slack|discord|signal|messenger|"
                     r"thunderbird|gmail|(?:mensagem|message) (?:html|texto|plain text|rich text|formato rich text))")
_KEY_ALIASES = {"return": "enter", "control": "ctrl", "windows": "win", "winleft": "win", "winright": "win",
                "lwin": "win", "rwin": "win", "super": "win", "escape": "esc"}


def norm_keys(keys) -> list:
    """['Ctrl', 'Return'] / 'ctrl+enter' -> ['ctrl', 'enter']."""
    if isinstance(keys, str):
        keys = keys.split("+")
    try:
        items = [str(k).strip().lower() for k in (keys or [])]
    except TypeError:
        return []
    return [_KEY_ALIASES.get(k, k) for k in items if k]


def hotkey_risk(keys, window_title: str = "", effect: str = "") -> Optional[str]:
    """Tecla que envia: Enter, Ctrl+Enter ou Alt+S num app de mensagem, ou um passo que a rotina
    marcou como envio (effect='enviar'). A marca so ACRESCENTA a porta; nunca a dispensa."""
    pressed = set(norm_keys(keys))
    # Delete manda para a lixeira e Shift+Delete apaga de vez no Explorer: o titulo da janela nao diz se e o
    # Explorer (no Win11 e so o nome da pasta), entao vale em qualquer janela
    if pressed in _DELETE_KEYS:
        return "excluir"
    if pressed not in ({"enter"}, {"ctrl", "enter"}, {"alt", "s"}):
        return None
    if effect == "enviar" or re.search(_MESSAGING_WINDOW, _norm(window_title)):
        return "enviar"
    return None


def step_risk(action: str, params: dict, window_title: str = "") -> Optional[str]:
    """Efeito de um passo do executor (fora dos pilotos). window_title: janela em primeiro plano."""
    if action == "delete_file":
        return "excluir"
    if action == "hotkey":
        p = params or {}
        return hotkey_risk(p.get("keys"), window_title, str(p.get("effect") or ""))
    if action in ("click", "vision_click", "uia_click"):
        return label_risk(str((params or {}).get("description") or (params or {}).get("element") or ""))
    return None


# "pode enviar" / "sim, paga": a confirmacao diz QUAL efeito libera
_CONFIRM_VERB = {"enviar": "enviar", "mandar": "enviar", "envia": "enviar", "manda": "enviar",
                 "comprar": "comprar", "compra": "comprar", "pagar": "pagar", "paga": "pagar",
                 "publicar": "publicar", "postar": "publicar", "excluir": "excluir", "apagar": "excluir",
                 "transferir": "transferir", "ligar": "ligar", "liga": "ligar"}
_CONFIRM_SPECIFIC = r"\b(?:pode |sim,? (?:pode )?)(enviar|mandar|envia|manda|comprar|compra|pagar|paga|publicar|postar|" \
                    r"excluir|apagar|transferir|ligar|liga)\b"
# "confirmo", "autorizo": genericas, so valem para o efeito que o proprio pedido cita
_CONFIRM_GENERIC = r"\b(?:confirmo|confirmado|tenho certeza|sim,? pode|autorizo)\b"


def confirmed(task: str, kind: Optional[str] = None) -> bool:
    """A pessoa confirmou no proprio pedido? Com `kind`, so a confirmacao DESSE efeito conta:
    "pode enviar o relatorio" nao libera "pagar"; "autorizo" libera so o que o pedido cita."""
    text = _norm(task)
    if kind is None:
        return bool(re.search(_CONFIRM, text))
    if any(_CONFIRM_VERB.get(verb) == kind for verb in re.findall(_CONFIRM_SPECIFIC, text)):
        return True
    return bool(re.search(_CONFIRM_GENERIC, text)) and requested(kind, task)


def requested(kind: str, task: str) -> bool:
    """O pedido da pessoa fala desse efeito? Serve para medir, nunca substitui a confirmacao."""
    pattern = dict(KINDS).get(kind)
    return bool(pattern and re.search(pattern, _norm(task)))


def mode() -> str:
    try:
        from core.config import get_config
        value = str(get_config().get("execution.authorization", "enforce")).lower()
    except Exception:
        value = "enforce"
    return value if value in MODES else "enforce"     # na duvida, protege


def _record(row: dict, path: Optional[Path] = None) -> None:
    target = path or LOG
    try:
        with _lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def authorize(kind: Optional[str], *, task: str, agent: str, action: str, label: str = "",
              current: Optional[str] = None, log_path: Optional[Path] = None, accept_inline: bool = True) -> str:
    """-> '' para seguir, ou a pergunta de confirmacao (so no modo enforce)."""
    if not kind:
        return ""
    current = current or mode()
    if current == "off":
        return ""
    ok = accept_inline and confirmed(task, kind)
    blocked = current == "enforce" and not ok
    _record({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": current, "agent": agent, "action": action,
             "kind": kind, "label": str(label)[:60], "requested": requested(kind, task), "confirmed": ok,
             "decision": "blocked" if blocked else ("allowed" if ok or current == "enforce" else "would_block")},
            log_path)
    if not blocked:
        return ""
    return _ask(kind, label)


CONFIRM_MARK = "preciso da sua confirmação"
_VERBS = {"pagar": "pagar", "comprar": "comprar", "transferir": "transferir", "excluir": "excluir",
          "publicar": "publicar", "enviar": "enviar", "aceitar": "aceitar",
          "ligar": "fazer a chamada", "conta": "sair da conta", "bloquear": "bloquear ou denunciar",
          "navegar": "abrir o site"}


def _ask(kind: str, label: str = "", again: bool = False) -> str:
    where = f" ('{str(label)[:40]}')" if label else ""
    if again:
        return (f"Já houve uma tentativa de {_VERBS.get(kind, kind)}{where} uma vez nesta tarefa. "
                f"Para repetir, {CONFIRM_MARK}.")
    return f"Antes de {_VERBS.get(kind, kind)}{where} {CONFIRM_MARK}."


def authorize_once(kind: Optional[str], done: list, *, task: str, agent: str, action: str, label: str = "",
                   current: Optional[str] = None, log_path: Optional[Path] = None,
                   accept_inline: bool = True) -> str:
    """Como authorize, e mais: o mesmo efeito no maximo UMA vez por tarefa (`done` e a lista da
    tarefa). Repetir pede confirmacao em qualquer modo menos off: o piloto via o campo vazio
    (porque ja tinha enviado) e reenviava; a mensagem chegou varias vezes a uma pessoa real."""
    if not kind:
        return ""
    current = current or mode()
    if current == "off":
        return ""
    if kind in done:
        _record({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": current, "agent": agent, "action": action,
                 "kind": kind, "label": str(label)[:60], "requested": requested(kind, task),
                 "confirmed": accept_inline and confirmed(task, kind), "decision": "blocked_repeat"}, log_path)
        return _ask(kind, label, again=True)
    message = authorize(kind, task=task, agent=agent, action=action, label=label, current=current,
                        log_path=log_path, accept_inline=accept_inline)
    if not message:
        done.append(kind)
    return message


def effect_reply(text: str) -> Optional[bool]:
    reply = _norm(text).rstrip(".")
    if reply in ("sim", "confirmo", "sim confirmo"):
        return True
    if reply in ("nao", "cancelar", "cancela", "nao confirmo"):
        return False
    return None


_DIGIT_WORDS = {"zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2", "tres": "3", "quatro": "4",
                "cinco": "5", "seis": "6", "meia": "6", "sete": "7", "oito": "8", "nove": "9"}


def spoken_effect_code(text: str) -> str:
    """"confirmo 1001", "confirmo 1 0 0 1" ou "confirmo um zero zero um" -> "1001"."""
    words = re.sub(r"[,;]", " ", _norm(text).rstrip(".")).split()
    norm_text = " ".join(_DIGIT_WORDS.get(w, w) for w in words)
    match = re.fullmatch(r"confirmo ([0-9](?:[ .]?[0-9]){3,9})", norm_text)
    return re.sub(r"[ .]", "", match[1]) if match else ""


class NeedsConfirmation(Exception):
    """Levantada pelo piloto quando a porta bloqueia: ele para antes de agir e pergunta."""


def report(path: Optional[Path] = None) -> dict:
    """Resumo do modo shadow: o que seria bloqueado e quantas vezes o pedido nem falava disso."""
    target = path or LOG
    rows = []
    try:
        rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError):
        pass
    by_kind: dict = {}
    for row in rows:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    return {"total": len(rows), "would_block": sum(r["decision"] == "would_block" for r in rows),
            "blocked": sum(r["decision"] == "blocked" for r in rows),
            "not_requested": sum(not r["requested"] for r in rows), "by_kind": by_kind}


if __name__ == "__main__":
    print(json.dumps(report(), ensure_ascii=False, indent=1))
