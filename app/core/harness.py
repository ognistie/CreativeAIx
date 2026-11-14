"""
Harness editavel e secao Voce — a camada do usuario sobre os agentes.

Harness (.cerebro/harness.json na camada pessoal, com versoes para desfazer):
  agents      instrucoes do usuario por agente (estilo e prioridade; nunca permissao)
  response    padrao das respostas (tom, tamanho, extra)
  appearance  cor de destaque, intensidade do ambiente, movimento, cantos, paleta
  modules     telas visiveis na barra lateral

Voce (pasta "Você/" na camada pessoal): notas guiadas sobre o usuario. O que ele preencher
entra no contexto dos agentes como preferencia, com limite de tamanho.

Tudo validado por esquema em codigo: valor desconhecido ou invalido volta ao padrao.
Sem camada pessoal ou sem arquivo, nada muda no comportamento dos agentes.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

AGENTS = ("MAESTRO", "WEB", "DESKTOP", "CODE", "DATA", "FILE", "EXTCODE")
TONES = ("natural", "direto", "detalhado", "amigavel", "formal")
LENGTHS = ("curta", "media", "longa")
RADII = ("suave", "reto", "redondo")
PALETTES = ("abismo", "ameixa", "nevoa", "matcha", "seda", "aurora", "brisa", "coral", "menta", "lavanda", "areia", "oceano", "aurora-boreal")
MODES = ("escuro", "claro")
FLOWS = ("parado", "sutil", "normal")
STYLE = 2          # 2 = Quiet Intelligence (Abismo/Pearl, malha em GPU); 1 = estilo anterior
MODULES = ("brain", "you", "harness", "history")
INSTRUCTIONS_MAX = 1500
KEEP_VERSIONS = 30

# O que cada agente faz, para a tela do Harness (texto fixo; as regras vivas vem do Cerebro)
AGENT_INFO = {
    "MAESTRO": {
        "role": "Entende o pedido, divide em etapas e escolhe o agente de cada uma.",
        "does": ["Lê o pedido e o contexto da conversa", "Monta o plano e passa pelas políticas de aceite",
                 "Usa referências, lições e o que você escreveu em Você"],
        "uses": "Plano validado em código antes de executar",
        "inputs": "Seu pedido, a conversa, o Harness, a seção Você e, se ligado, o Diário",
        "limits": ["Não age no computador: só planeja e delega", "O plano passa pelas políticas de aceite antes de rodar"],
        "examples": ["Pesquise preços de adubo e monte uma planilha", "Organize meus downloads e me diga o que mudou"],
        "quick": ["Antes de criar algo novo, procure se já existe.", "Prefira poucas etapas.",
                  "Se o pedido for ambíguo, pergunte uma coisa só."]},
    "WEB": {
        "role": "Pesquisa na internet, abre páginas, preenche e lê sites.",
        "does": ["Pesquisa e resume páginas", "Preenche formulários", "Lê tabelas e textos"],
        "uses": "Navegador controlado pelo app",
        "inputs": "Uma etapa do plano, mais as regras do Cérebro e as suas instruções",
        "limits": ["Enviar, publicar, comprar, pagar ou excluir pede sua confirmação", "Digitar com Enter num campo de mensagem conta como envio e pede confirmação"],
        "examples": ["Abra o g1", "Pesquise no Google a previsão do tempo"],
        "quick": ["Prefira fontes oficiais.", "Cite o link de onde tirou a informação.",
                  "Não aceite cookies além do necessário."]},
    "DESKTOP": {
        "role": "Abre aplicativos do Windows, digita e opera as janelas.",
        "does": ["Abre e traz apps para a frente", "Escreve em Bloco de Notas, Word, Excel", "Usa atalhos e menus"],
        "uses": "Automação de interface do Windows (UIA)",
        "inputs": "Uma etapa do plano, mais as regras do Cérebro e as suas instruções",
        "limits": ["Só mexe nas Configurações do Windows se você citar", "Enviar ou excluir pelo app pede sua confirmação"],
        "examples": ["Abra o bloco de notas e escreva uma lista", "Traga o Excel para a frente"],
        "quick": ["Prefira atalhos de teclado.", "Confirme o título da janela antes de digitar.",
                  "Reutilize a janela que já está aberta."]},
    "CODE": {
        "role": "Cria e corrige sites, scripts e projetos.",
        "does": ["Cria projetos e sites estáticos", "Corrige erros em scripts", "Só altera código quando você pede"],
        "uses": "Arquivos do projeto e testes",
        "inputs": "Uma etapa do plano e a pasta do projeto",
        "limits": ["Ferramentas: criar, editar e reverter projeto; nada além disso", "Cada mudança pode ser desfeita"],
        "examples": ["Crie um site sobre uma cafeteria artesanal", "Corrija o erro do script de relatório"],
        "quick": ["Rode os testes antes de entregar.", "Explique o que mudou em até 3 linhas.",
                  "Siga o estilo do código que já existe."]},
    "DATA": {
        "role": "Planilhas, gráficos e análises.",
        "does": ["Cria e organiza planilhas", "Gera gráficos", "Resume números"],
        "uses": "Excel e arquivos CSV",
        "inputs": "Uma etapa do plano e os dados citados no pedido",
        "limits": ["Ferramenta única: criar a planilha ou arquivo de dados", "Não envia o arquivo para ninguém"],
        "examples": ["Crie uma planilha de gastos do mês com gráfico", "Resuma as vendas por região"],
        "quick": ["Valores em R$ com duas casas.", "Sempre inclua um gráfico.", "Deixe a primeira linha como cabeçalho fixo."]},
    "FILE": {
        "role": "Organiza, move e renomeia arquivos e pastas.",
        "does": ["Organiza pastas por tipo ou data", "Renomeia em lote", "Abre pastas e arquivos"],
        "uses": "Pastas do seu usuário (executáveis nunca são abertos)",
        "inputs": "Uma etapa do plano e as pastas citadas no pedido",
        "limits": ["Só opera dentro das pastas citadas no pedido", "Excluir exige confirmação escrita no pedido", "Não roda Python, shell nem abre executáveis"],
        "examples": ["Organize por tipo os arquivos de Downloads", "Mova notas.txt para a pasta arquivo"],
        "quick": ["Nunca apague: mova para uma pasta de revisão.", "Mostre a lista antes de renomear em lote.",
                  "Use datas no formato AAAA-MM-DD."]},
    "EXTCODE": {
        "role": "Chama o Claude Code ou o Codex para trabalhar numa pasta de projeto que você escolhe.",
        "does": ["Roda a CLI oficial, já conectada por você, só na pasta do projeto",
                 "Mostra o andamento linha a linha e o resumo com os arquivos alterados",
                 "Para no botão Parar; nunca mexe na pasta do próprio Creative AIx"],
        "uses": "Sua sessão do Claude Code ou do Codex (o app nunca pede nem guarda chaves)",
        "inputs": "O pedido, a pasta do projeto e a sessão que você já fez no Claude Code ou no Codex",
        "limits": ["Só trabalha na pasta do projeto escolhida", "Abrir programas e sites vai para os agentes do computador", "Tem tempo máximo e teto de custo por tarefa"],
        "examples": ["Crie um README no projeto loja com o Claude", "Peça ao Codex para corrigir os testes"],
        "quick": ["Diga sempre a pasta do projeto.", "Peça um resumo curto do que mudou.",
                  "Não instale dependências sem avisar."]},
}

DEFAULT = {
    "version": 1,
    "agents": {a: {"instructions": ""} for a in AGENTS},
    "response": {"tone": "natural", "length": "media", "extra": ""},
    "appearance": {"accent": "#16897E", "ambient": 0.55, "motion": True, "radius": "suave", "palette": "abismo",
                   "mode": "escuro", "blur": True, "wallpaper": "", "dim": 0.35,
                   "mesh": True, "flow": "sutil", "fluted": False, "style": STYLE},
    "modules": {m: True for m in MODULES},
    # Modo Desenvolvedor, niveis 1 e 2: textos da tela inicial, atalhos de tarefa e cartoes (JSON validado)
    "dev": {"enabled": False, "code_changes": False, "greeting": "", "hint": "", "shortcuts": [], "cards": []},
}
DEV_MAX_ITEMS = 8
_ICON_NAME = re.compile(r"^[a-z][a-z0-9-]{0,24}$")


def _dev_items(items, fields) -> list:
    """Lista de objetos com os campos (nome, limite) dados; itens sem texto principal caem fora."""
    out = []
    for item in (items if isinstance(items, list) else [])[:DEV_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        clean = {}
        for name, limit in fields:
            v = item.get(name)
            clean[name] = v.strip()[:limit] if isinstance(v, str) else ""
        if clean.get("icon") and not _ICON_NAME.match(clean["icon"]):
            clean["icon"] = ""
        if clean[fields[0][0]] and clean["request"]:
            out.append(clean)
    return out


def validate_dev(data) -> dict:
    out = copy.deepcopy(DEFAULT["dev"])
    dev = data.get("dev") if isinstance(data, dict) and isinstance(data.get("dev"), dict) else {}
    for key in ("enabled", "code_changes"):
        if isinstance(dev.get(key), bool):
            out[key] = dev[key]
    for key, limit in (("greeting", 60), ("hint", 160)):
        if isinstance(dev.get(key), str):
            out[key] = dev[key].strip()[:limit]
    out["shortcuts"] = _dev_items(dev.get("shortcuts"), (("label", 40), ("icon", 25), ("request", 300)))
    out["cards"] = _dev_items(dev.get("cards"), (("title", 30), ("text", 90), ("icon", 25), ("request", 300)))
    return out

YOU_DIR = "Você"
YOU_SECTIONS = [
    ("Perfil", "Quem é você, no que trabalha, como prefere ser chamado."),
    ("Rotinas", "O que você faz todo dia ou toda semana, e em que horário."),
    ("Tarefas frequentes", "Pedidos que você mais faz para os agentes, com o jeito certo de fazer."),
    ("Jeito de falar", "Palavras, apelidos e atalhos que você usa ao pedir algo."),
    ("Padrão de respostas", "Como prefere as respostas: curtas, em tópicos, com ou sem explicação."),
    ("Skills para os agentes", "Habilidades e cuidados que os agentes devem aplicar nas suas tarefas."),
]
YOU_MAX = 700
_HINT = re.compile(r"^>\s?.*$|^<!--.*?-->$", re.MULTILINE)


def _hex(v, fallback):
    return v if isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", v) else fallback


def upgrade_style(data):
    """Arquivo gravado no estilo anterior (aparencia sem "style"): ganha a paleta e o destaque novos uma vez.
    Tema, foto, cantos e o resto ficam como estavam; da para voltar no Harness (e a versao anterior fica salva)."""
    if not isinstance(data, dict) or not isinstance(data.get("appearance"), dict):
        return data
    app = data["appearance"]
    if app.get("style") == STYLE:
        return data
    data = dict(data)
    data["appearance"] = dict(app, palette=DEFAULT["appearance"]["palette"],
                              accent=DEFAULT["appearance"]["accent"], style=STYLE)
    return data


def validate(data) -> dict:
    """Esquema do Harness: so campos conhecidos, tipos e faixas validos."""
    out = copy.deepcopy(DEFAULT)
    if not isinstance(data, dict):
        return out
    agents = data.get("agents") if isinstance(data.get("agents"), dict) else {}
    for a in AGENTS:
        item = agents.get(a) if isinstance(agents.get(a), dict) else {}
        text = item.get("instructions")
        if isinstance(text, str):
            out["agents"][a]["instructions"] = text.strip()[:INSTRUCTIONS_MAX]
    resp = data.get("response") if isinstance(data.get("response"), dict) else {}
    if resp.get("tone") in TONES:
        out["response"]["tone"] = resp["tone"]
    if resp.get("length") in LENGTHS:
        out["response"]["length"] = resp["length"]
    if isinstance(resp.get("extra"), str):
        out["response"]["extra"] = resp["extra"].strip()[:INSTRUCTIONS_MAX]
    app = data.get("appearance") if isinstance(data.get("appearance"), dict) else {}
    out["appearance"]["accent"] = _hex(app.get("accent"), DEFAULT["appearance"]["accent"])
    if isinstance(app.get("ambient"), (int, float)) and not isinstance(app.get("ambient"), bool):
        out["appearance"]["ambient"] = round(min(1.0, max(0.0, float(app["ambient"]))), 2)
    if isinstance(app.get("motion"), bool):
        out["appearance"]["motion"] = app["motion"]
    if app.get("radius") in RADII:
        out["appearance"]["radius"] = app["radius"]
    if app.get("palette") in PALETTES:
        out["appearance"]["palette"] = app["palette"]
    if app.get("mode") in MODES:
        out["appearance"]["mode"] = app["mode"]
    if isinstance(app.get("blur"), bool):
        out["appearance"]["blur"] = app["blur"]
    # Papel de parede: "" (so as luzes), "catalog:<id>" ou "personal:<id>"; escurecimento 0..1
    wp = app.get("wallpaper")
    if isinstance(wp, str) and re.fullmatch(r"(?:catalog|personal):[a-z0-9][a-z0-9-]{1,60}", wp):
        out["appearance"]["wallpaper"] = wp
    if isinstance(app.get("dim"), (int, float)) and not isinstance(app.get("dim"), bool):
        out["appearance"]["dim"] = round(min(1.0, max(0.0, float(app["dim"]))), 2)
    if isinstance(app.get("mesh"), bool):
        out["appearance"]["mesh"] = app["mesh"]
    if app.get("flow") in FLOWS:
        out["appearance"]["flow"] = app["flow"]
    if isinstance(app.get("fluted"), bool):
        out["appearance"]["fluted"] = app["fluted"]
    mods = data.get("modules") if isinstance(data.get("modules"), dict) else {}
    for m in MODULES:
        if isinstance(mods.get(m), bool):
            out["modules"][m] = mods[m]
    out["dev"] = validate_dev(data)
    return out


import contextlib
import contextvars

# Instrucoes de uma versao em teste no AI Research Lab: valem so dentro do `with` (nunca gravam no Harness)
_OVERRIDE: contextvars.ContextVar = contextvars.ContextVar("harness_override", default=None)


@contextlib.contextmanager
def instructions_override(agent: str, text: str):
    token = _OVERRIDE.set({(agent or "").upper(): str(text or "")[:INSTRUCTIONS_MAX]})
    try:
        yield
    finally:
        _OVERRIDE.reset(token)


class Harness:
    def __init__(self, personal: Optional[Path]) -> None:
        self.folder = Path(personal) / ".cerebro" if personal else None
        self._cache = (None, None)

    @property
    def file(self) -> Optional[Path]:
        return self.folder / "harness.json" if self.folder else None

    def load(self) -> dict:
        f = self.file
        try:
            stamp = f.stat().st_mtime_ns if f else None
        except OSError:
            stamp = None
        if stamp is None:
            return copy.deepcopy(DEFAULT)
        if self._cache[0] == stamp:
            return copy.deepcopy(self._cache[1])
        try:
            data = validate(upgrade_style(json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            data = copy.deepcopy(DEFAULT)
        self._cache = (stamp, data)
        return copy.deepcopy(data)

    def save(self, data, label: str = "") -> dict:
        if not self.folder:
            raise PermissionError("camada pessoal indisponivel")
        clean = validate(data)
        versions = self.folder / "harness_versoes"
        versions.mkdir(parents=True, exist_ok=True)
        if self.file.is_file():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            n = 0
            while (versions / f"{stamp}-{n}.json").exists():
                n += 1
            (versions / f"{stamp}-{n}.json").write_text(self.file.read_text(encoding="utf-8"), encoding="utf-8")
            for old in sorted(versions.glob("*.json"))[:-KEEP_VERSIONS]:
                old.unlink(missing_ok=True)
        clean["label"] = (label or "").strip()[:80]
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.file)
        self._cache = (None, None)
        return self.load()

    def versions(self) -> list[dict]:
        if not self.folder:
            return []
        out = []
        for f in sorted((self.folder / "harness_versoes").glob("*.json"), reverse=True):
            try:
                label = json.loads(f.read_text(encoding="utf-8")).get("label", "")
            except (OSError, ValueError):
                label = ""
            out.append({"id": f.stem, "label": label, "when": f.stem[:15]})
        return out

    def restore(self, version_id: str) -> dict:
        if not self.folder or not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9]+", version_id or ""):
            raise ValueError("versao invalida")
        f = self.folder / "harness_versoes" / f"{version_id}.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        return self.save(data, label=f"restaurado de {version_id}")

    def agent_block(self, agent: str, compact: bool = False) -> str:
        data = self.load()
        text = data["agents"].get((agent or "").upper(), {}).get("instructions", "")
        override = _OVERRIDE.get()
        if override and (agent or "").upper() in override:
            text = override[(agent or "").upper()]      # versao em teste no Lab (so dentro do experimento)
        resp = data["response"]
        parts = []
        if text:
            parts.append(text[: 350 if compact else 700])
        if (agent or "").upper() == "MAESTRO" and resp.get("extra"):
            parts.append("Padrão de resposta: " + resp["extra"][:300])
        if not parts:
            return ""
        return ("Instruções do usuário para este agente (preferência de estilo e prioridade; "
                "não ampliam permissões):\n" + "\n".join(parts))

    def response_style(self) -> str:
        """Frase curta sobre o padrao de resposta, para quem redige a resposta final."""
        data = self.load()
        r = data["response"]
        if r == DEFAULT["response"]:
            return ""
        out = f"Tom {r['tone']}, resposta {r['length']}."
        if r["extra"]:
            out += " " + r["extra"][:300]
        return out


# ── Voce ─────────────────────────────────────────────────────────────
def you_rel(section: str) -> str:
    return f"{YOU_DIR}/{section}.md"


def you_template(section: str, hint: str) -> str:
    return f"---\ntipo: voce\n---\n# {section}\n\n> {hint}\n\n"


def you_content(md: str) -> str:
    """Só o que o usuario escreveu: sem frontmatter, titulo e dicas."""
    md = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", md or "", flags=re.DOTALL)
    md = re.sub(r"^#\s+.*$", "", md, flags=re.MULTILINE)
    md = _HINT.sub("", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def you_block(store, compact: bool = False) -> tuple[str, list]:
    """Bloco 'Sobre o usuário' para o prompt e as notas usadas. Vazio se nada preenchido."""
    if store is None or not getattr(store, "personal", None):
        return "", []
    lines, used = [], []
    cap = YOU_MAX // (2 if compact else 1)
    size = 0
    for section, _ in YOU_SECTIONS:
        text = you_content(store.read(you_rel(section)))
        if not text:
            continue
        text = re.sub(r"\s*\n\s*", " · ", text)
        line = f"- {section}: {text}"
        if size + len(line) > cap:
            line = line[: max(0, cap - size)].rsplit(" ", 1)[0]
            if len(line) < 20:
                break
        lines.append(line)
        used.append(section)
        size += len(line) + 1
        if size >= cap:
            break
    if not lines:
        return "", []
    return ("Sobre o usuário (escrito por ele; use como preferência, não amplia permissões):\n"
            + "\n".join(lines)), used
