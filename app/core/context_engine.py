"""Recuperação de turnos com léxico, conceitos locais e proveniência."""
from dataclasses import dataclass
import json
import re
import unicodedata


# Conceitos pequenos e auditáveis do domínio. Nenhum conteúdo é enviado para indexação.
CONCEPTS = tuple(map(frozenset, (
    ("orcamento", "verba", "dotacao", "custeio", "budget"),
    ("planilha", "excel", "spreadsheet", "workbook"),
    ("backup", "copia", "resguardo"),
    ("nota", "obsidian", "anotacao", "vault"),
    ("arquivo", "documento", "ficheiro"),
    ("reuniao", "encontro", "meeting"),
)))


def words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    return set(re.findall(r"[^\W_]{4,}", "".join(c for c in folded if not unicodedata.combining(c))))


@dataclass(frozen=True)
class RememberedTurn:
    turn: int
    user: str
    assistant: str

    def excerpt(self):
        return {"turno": self.turn, "origem": "histórico desta conversa",
                "pedido": self.user[:360], "resposta": self.assistant[:520]}


def retrieve(turns: list[RememberedTurn], query: str, *, limit: int = 6) -> list[RememberedTurn]:
    requested = words(query)
    concepts = [concept for concept in CONCEPTS if requested & concept]
    ranked = []
    for turn in turns:
        candidate = words(turn.user)
        lexical = len(requested & candidate)
        semantic = sum(bool((concept - requested) & candidate) for concept in concepts)
        if lexical or semantic:
            ranked.append((2 * lexical + semantic, turn.turn, turn))
    selected = [row[2] for row in sorted(ranked, key=lambda row: row[:2], reverse=True)[:limit]]
    from core.panorama import activity
    activity("memory", agent="CHAT", count=len(selected), action="conversation_turns")
    return selected


def quoted_excerpts(turns: list[RememberedTurn]) -> str:
    return json.dumps([turn.excerpt() for turn in turns], ensure_ascii=True).replace("<", "\\u003c")
