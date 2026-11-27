"""
Maestro v18 — Roteamento inteligente + ambiguity gate + memoria de rotas.

MUDANÇAS v18 (vs v17):
- Sem cache de planos em memoria: a chave era task[:80], entao tarefas
  diferentes com o mesmo comeco recebiam o MESMO plano, e repetir um
  pedido devolvia sempre a mesma resposta.
- Memoria deixou de ser ATALHO (antes: devolvia so o 1o agente, sem
  params, sem chamar o LLM — perdia subtasks). Agora as rotas que ja
  funcionaram entram no prompt como REFERENCIA; o plano e o conteudo sao
  sempre gerados para a tarefa atual.

MUDANÇAS v17 (vs v16):
- AMBIGUITY GATE (cenários A e J do briefing): prompts vagos ("deixa o
  projeto rodando", "atualiza o relatorio do mes passado") NAO disparam
  3 hipoteses em paralelo. Maestro retorna needs_clarification=True com
  uma unica pergunta objetiva.
- Heuristica deterministica detecta padroes obvios antes de chamar LLM.
- Prompt ensina o LLM a usar needs_clarification quando ambiguo.

MUDANÇAS v16:
- "abra VS Code e crie arquivo/projeto" → CODE (não DESKTOP)
- "abra VS Code" (sem criar) → DESKTOP
"""

import re
from typing import Optional

from anthropic import APIConnectionError

from core.ai_client import get_client
from core.config import get_config
from core.json_validator import safe_parse

PROMPT = (
    "Voce e o MAESTRO do Creative AIx.\n"
    "Entenda a INTENCAO REAL e gere plano preciso. JSON PURO.\n\n"

    "═══ PRINCIPIO ═══\n"
    "PROCEDIMENTO ≠ CONTEUDO. Se usuario NAO pediu texto → text=''.\n"
    "NUNCA invente texto que o usuario nao pediu.\n\n"

    "═══ CONTEUDO PEDIDO ═══\n"
    "a) Texto ditado (entre aspas ou 'escreva X'): use X exatamente.\n"
    "b) Pedido para CRIAR conteudo (poema, email, resumo, lista, historia, texto sobre um tema):\n"
    "   ESCREVA o conteudo completo e coloque em text/message. Isso nao e inventar: foi pedido.\n"
    "c) Reproduzir obra protegida (letra de musica, capitulo de livro, texto pago): nao pode.\n"
    "   NUNCA escreva um substituto (titulo, trecho inventado). Retorne:\n"
    "   {\"cannot_do\": true, \"reason\": \"<por que>\", \"alternative\": \"<o que posso fazer>\"}\n"
    "   (ex.: resumo do tema da musica com palavras proprias, ou pesquisar a letra oficial).\n\n"
    "═══ PESQUISA WEB ═══\n"
    "Toda subtask WEB de pesquisa precisa de params.query com o termo exato.\n"
    "Cada pedido e novo: query, texto, nomes e tema saem SOMENTE da tarefa atual.\n"
    "Os exemplos abaixo ensinam o FORMATO — nao copie seus valores.\n\n"

    "═══ ROTEAMENTO (ORDEM DE PRIORIDADE) ═══\n"
    "1. Se pede CRIAR codigo/projeto/arquivo de programacao → CODE (mesmo se menciona VS Code)\n"
    "2. Se pede EDITAR/MODIFICAR/CORRIGIR arquivo de codigo existente → CODE\n"
    "3. Se pede ABRIR VS Code APONTANDO PRA UMA PASTA (sem criar nada) → CODE\n"
    "4. Se pede CRIAR planilha/Excel com dados → DATA\n"
    "5. Se pede navegar web/pesquisar/abrir site → WEB\n"
    "6. Se pede APENAS ABRIR um app vazio (sem criar conteudo nem apontar pasta) → DESKTOP\n"
    "7. Se pede interagir com app desktop (Teams, WhatsApp, Notepad, Paint) → DESKTOP\n"
    "8. Se pede organizar/mover/copiar arquivos → FILE\n"
    "9. SO se o pedido CITA o Claude Code ou o Codex pelo nome → EXTCODE\n"
    "   (params: tool='claude'|'codex', folder=<pasta citada>, prompt=<o que fazer>; sem pasta, pergunte)\n"
    "   Sem o nome no pedido, NUNCA use EXTCODE (politica POL-011).\n\n"

    "EXEMPLOS DE ROTEAMENTO:\n"
    "- 'abra o vs code e crie um arquivo python' → CODE (criar arquivo = CODE)\n"
    "- 'edite o app.py adicionando uma rota /login' → CODE (edit_existing)\n"
    "- 'abra o vs code na pasta meu-projeto' → CODE (open_vscode_folder)\n"
    "- 'abra o vs code' → DESKTOP (apenas abrir vazio = DESKTOP)\n"
    "- 'crie um site html' → CODE\n"
    "- 'crie um script python que renomeia imagens' → CODE (single_file)\n"
    "- 'abra o paint e desenhe' → DESKTOP com action_type=draw\n"
    "- 'pesquise no google' → WEB\n"
    "- 'crie uma planilha de vendas' → DATA\n\n"

    "═══ PARAMS ═══\n"
    "app, person, message, text, action_type, query, url\n\n"

    "═══ VARIAVEIS DE CONTEXTO ═══\n"
    "Quando depends_on: N, use SOMENTE:\n"
    "  {output_folder_N}   {output_path_N}   {output_files_N}\n"
    "  {output_all_files_N}   {output_url_N}\n"
    "  {output_text_N}     {output_summary_N}\n"
    "⚠️ NUNCA invente variaveis fora desta lista.\n"
    "⚠️ Para enviar resultado de pesquisa, use {output_summary_N} (mais curto e seguro).\n\n"

    "═══ REGRAS ═══\n"
    "1. UM APP = 1 subtask\n"
    "2. 2+ subtasks APENAS quando APPS DIFERENTES cooperam\n"
    "3. text='' se usuario nao pediu para escrever\n"
    "4. Formato ENXUTO: analysis curto (ate 6 palavras); em cada subtask so agent, task, params e\n"
    "   depends_on; skills no fim. Nada alem disso (cada token atrasa a resposta).\n"
    "5. ESCREVER numa conversa ou campo NAO e ENVIAR: 'escreve oi na conversa' → action_type='write_text'\n"
    "   (digita e para). Use action_type='send_message' e o verbo enviar na task SO quando o pedido\n"
    "   disser enviar/mandar/responder. Enviar e decisao da pessoa (politica POL-009).\n"
    "6. PROIBIDO acoplar CODE + DESKTOP notepad/word com o codigo gerado.\n"
    "   Se voce roteou para CODE, o CODE ja cria os arquivos e abre o\n"
    "   VS Code. NUNCA crie uma subtask DESKTOP escrevendo o HTML/python\n"
    "   no notepad/word como 'visualizacao'. Isso confunde o usuario.\n\n"

    "═══ EXEMPLOS ═══\n\n"

    "Tarefa: 'abra o bloco de notas'\n"
    '{"analysis":"apenas abrir","subtasks":[{"agent":"DESKTOP",'
    '"task":"abrir bloco de notas","params":{"app":"notepad","action_type":"open","text":""},'
    '"depends_on":null}],"skills":["notepad"]}\n\n'

    "Tarefa: 'abra o vs code e crie um arquivo python com sistema de login'\n"
    '{"analysis":"criar arquivo python no VS Code","subtasks":[{"agent":"CODE",'
    '"task":"criar arquivo python com sistema de login e abrir no VS Code",'
    '"params":{"action_type":"create_file"},'
    '"depends_on":null}],"skills":["python","vscode"]}\n\n'

    "Tarefa: 'abra o youtube e pesquise videos de skate'\n"
    '{"analysis":"youtube + pesquisa","subtasks":[{"agent":"WEB",'
    '"task":"abrir youtube e pesquisar videos de skate",'
    '"params":{"url":"https://www.youtube.com","query":"videos de skate","action_type":"search"},'
    '"depends_on":null}],"skills":["youtube"]}\n\n'

    "Tarefa: 'pesquise sobre Palmeiras e envie no Teams para Joao'\n"
    '{"analysis":"pesquisar + enviar via Teams","subtasks":['
    '{"agent":"WEB","task":"pesquisar sobre Palmeiras e ler resultado",'
    '"params":{"url":"https://www.google.com","query":"historia do Palmeiras","action_type":"search"},'
    '"depends_on":null},'
    '{"agent":"DESKTOP","task":"enviar resumo da pesquisa para Joao no Teams",'
    '"params":{"app":"teams","action_type":"send_message","person":"Joao","message":"{output_summary_1}"},'
    '"depends_on":1}'
    '],"skills":["web","teams"]}\n\n'

    "Tarefa: 'abra o paint e desenhe uma casa'\n"
    '{"analysis":"abrir paint e desenhar","subtasks":[{"agent":"DESKTOP",'
    '"task":"abrir paint e desenhar uma casa",'
    '"params":{"app":"paint","action_type":"draw","text":"casa"},'
    '"depends_on":null}],"skills":["paint"]}\n\n'

    "Tarefa: 'abra o notepad e escreva de 10 ate 20'\n"
    '{"analysis":"notepad + numeros","subtasks":[{"agent":"DESKTOP",'
    '"task":"abrir notepad e escrever numeros 10-20",'
    '"params":{"app":"notepad","action_type":"write_text","text":"10\\n11\\n12\\n13\\n14\\n15\\n16\\n17\\n18\\n19\\n20"},'
    '"depends_on":null}],"skills":["notepad"]}\n\n'

    "═══ CONVERSA EM ANDAMENTO ═══\n"
    "Se vier CONTEXTO DA CONVERSA, o usuario esta continuando uma conversa.\n"
    "Com CONTINUAR EM <alvo>, o pedido age sobre algo JA ABERTO:\n"
    "- 1 subtask para o agente do alvo (web->WEB, app:<x>->DESKTOP, code->CODE, folder->FILE).\n"
    "- NAO reabra o app/site e NAO recrie o projeto: o sistema entrega o alvo ao agente.\n"
    "- app: mantenha params.app do alvo (ex.: notepad) e o texto pedido em params.text.\n"
    "- code: params.action_type='edit_existing'; task diz O QUE mudar.\n"
    "Sem CONTINUAR EM, use a conversa so para entender referencias; o pedido e novo.\n\n"

    "═══ AMBIGUITY GATE (cenarios A e J do briefing) ═══\n"
    "Se a tarefa for AMBIGUA ou faltam dados essenciais para executar com\n"
    "seguranca (qual app? qual arquivo? qual periodo? qual destinatario?),\n"
    "NUNCA chute. NUNCA execute 3 hipoteses em paralelo. Retorne:\n"
    "  {\"needs_clarification\": true, \"question\": \"<UMA pergunta objetiva>\",\n"
    "   \"why\": \"<o que esta faltando>\"}\n"
    "Exemplos de pedidos ambiguos:\n"
    "- 'deixa o projeto rodando'        → qual projeto? rodar = dev/test/prod?\n"
    "- 'atualiza o relatorio do mes passado' → qual relatorio? que mes (abs)?\n"
    "- 'envia para ele'                 → ele quem? por qual canal?\n"
    "Regra: faca NO MAXIMO 1 pergunta por turno (briefing secao 10).\n\n"

    "Prefira 1 subtask. Windows PT-BR. JSON PURO."
)


# ───────────────────────────────────────────────────────────────────────
#  Heuristica determinstica de ambiguidade (cenarios A e J)
# ───────────────────────────────────────────────────────────────────────

# Frases curtas notoriamente vagas — fazem o usuario pagar uma chamada LLM
# por nada. Pre-bloqueamos com pergunta direta.
_VAGUE_PHRASES = {
    "deixa rodando", "deixa o projeto rodando", "deixa rodar",
    "faz funcionar", "arruma isso", "conserta", "resolve isso",
    "atualiza", "atualiza o relatorio", "envia pra ele", "manda pra ela",
    "termina isso", "continua de onde parou",
}

# Marcadores temporais relativos (cenario J).
_RELATIVE_TIME_MARKERS = (
    "mes passado", "semana passada", "ontem", "outro dia",
    "ultimo mes", "ultima semana", "anteontem", "esses dias",
    "no ano passado",
)

# Marcadores deicticos sem antecedente claro.
_DEICTIC_PRONOUNS = ("ele", "ela", "isso", "aquilo", "aquele", "aquela")


def _detect_ambiguity(task: str, *, lexicon=None) -> dict | None:
    """
    Retorna {"question": ..., "why": ...} se a tarefa for ambigua, senao None.

    NAO substitui o LLM — apenas elimina ambiguidades obvias antes do
    custo de uma chamada de API.
    """
    if not task:
        return {
            "question": "O que voce gostaria que eu fizesse?",
            "why": "tarefa vazia",
        }

    t = task.lower().strip()

    # Curto demais para uma intencao acionavel
    word_count = len(re.findall(r"\w+", t))
    # "abre youtube", "abre calculadora" sao curtos mas claros (comuns na voz)
    short_but_clear = False
    if word_count == 2:
        try:
            from core.lexicon import get_lexicon
            short_but_clear = bool((lexicon if lexicon is not None else get_lexicon()).apps_in(task))
        except Exception:
            short_but_clear = False
    if word_count <= 2 and not short_but_clear and t not in {"oi", "ola", "ajuda", "help"}:
        return {
            "question": f"'{task}' — pode detalhar o que voce quer fazer?",
            "why": "tarefa curta demais para roteamento confiavel",
        }

    # Frase vaga em catalogo
    for vague in _VAGUE_PHRASES:
        if t == vague or t.startswith(vague + " ") or t.endswith(" " + vague):
            return {
                "question": "Pode especificar qual projeto/arquivo/aplicacao e o resultado esperado?",
                "why": f"frase vaga detectada: '{vague}'",
            }

    # Marcador temporal relativo sem objeto especifico
    for marker in _RELATIVE_TIME_MARKERS:
        if marker in t:
            # Se nao tem nome proprio nem arquivo identificavel, e ambiguo
            has_filename = bool(re.search(r"\b[\w-]+\.[a-zA-Z]{1,5}\b", task))
            has_proper_noun = bool(re.search(r"\b[A-Z][a-z]+\b", task))
            if not has_filename and not has_proper_noun:
                return {
                    "question": f"Qual data exatamente ({marker})? E qual arquivo/relatorio especifico?",
                    "why": f"marcador temporal relativo sem referencia absoluta: '{marker}'",
                }

    return None


def _format_route_hint(routes: list) -> str:
    """Rotas da memoria -> bloco de referencia para o prompt (sem conteudo)."""
    if not routes:
        return ""
    from memory.workflow_store import format_route
    lines = [
        "REFERENCIA (memoria): rotas de agentes que ja funcionaram em tarefas "
        "parecidas. Use so como pista de roteamento. NAO reutilize textos, "
        "temas, nomes ou valores; se a tarefa atual pede outra coisa, ignore."
    ]
    for r in routes:
        lines.append(f"- {format_route(r['route'])}  [{r.get('success_count', 1)} sucesso(s)]")
    return "\n".join(lines)


# ── Atalho sem IA: "abrir <app ou site>" ──────────────────────────────
# O pedido mais comum ("abre o youtube", "abrir o paint") nao precisa de
# planejamento: o dicionario do Obsidian (70 Dicionario/Apps e sites) ja diz
# o que e e como abrir. Economiza a chamada do Maestro (~2-3 s).
_OPEN_REQUEST = re.compile(
    r"^(?:por favor,? )?(?:abr[aei]|abrir|abre ai|entr[ae] n[oa]|entrar n[oa]|acess[ae]r?|vai n[oa])"
    r"(?: (?:o|a|os|as|meu|minha|pra mim|para mim))* (?P<app>[\w .\-]{2,40}?)"
    r"(?: (?:pra mim|para mim|por favor|ai))?$")


def fast_open_plan(task: str, continue_in: str = "", *, lexicon=None) -> Optional[dict]:
    """Plano direto para "abrir X" quando X e exatamente um app/site do dicionario.
    None quando ha qualquer duvida (o Maestro planeja normalmente)."""
    if continue_in:
        return None                    # algo aberto na conversa: o resolvedor/Maestro decidem
    try:
        from core.lexicon import get_lexicon, norm
        lex = lexicon if lexicon is not None else get_lexicon()
        m = _OPEN_REQUEST.match(norm(task).strip(" .!?"))
        if not m:
            return None
        target = m.group("app").strip()
        apps = lex.apps_in(target)
        if len(apps) != 1 or not lex.is_app_name(target):
            return None
        entry = lex.app_entry(apps[0][0])
    except Exception:
        return None
    if entry is None or len(entry.extra) < 2:
        return None
    name = entry.meaning.split(" (")[0].split(" / ")[0]
    alvo = entry.extra[1].strip()
    how = entry.extra[2].strip() if len(entry.extra) > 2 else ""
    if alvo == "web" and re.fullmatch(r"https?://\S+", how):
        sub = {"agent": "WEB", "task": f"abrir {name}",
               "params": {"url": how, "action_type": "open"}}
    elif alvo.startswith("app:"):
        sub = {"agent": "DESKTOP", "task": f"abrir {name}",
               "params": {"app": alvo.split(":", 1)[1], "action_type": "open", "text": ""}}
    else:
        return None
    sub["original_task"] = task
    return {"analysis": f"Abrir {name} (atalho do dicionario, sem IA)",
            "subtasks": [sub], "skills": [], "fast_path": "abrir"}


# ── Atalhos sem IA: pasta, Configuracoes e pesquisa num site citado ─────
# O DesktopAgent ja abre pastas e paginas das Configuracoes sem modelo, e o WebAgent ja monta a pesquisa: so o
# roteamento passava pelo Maestro (uma chamada por pedido). Pedido composto ("... e ...") continua no Maestro.
_JUST_OPEN = re.compile(r"^(?:abr[aei]|abrir|abre ai|entr[ae] (?:na|nas|no)|vai (?:na|nas|no|pra|para)|acess[ae])\b")
_SEARCH_ON = re.compile(r"^(?:pesquis|procur|busc)\w*(?:\s+(?:por|sobre))?\s+(?P<q>.{2,120}?)\s+"
                        r"(?:no|na)\s+(?P<site>google|youtube)$")


def _compound(t: str) -> bool:
    return bool(re.search(r"\s(?:e|depois|entao|tambem)\s", t) or "," in t)


def fast_system_plan(task: str, continue_in: str = "") -> Optional[dict]:
    """'abre a pasta downloads' / 'abre as configuracoes de bluetooth' -> DESKTOP, sem modelo."""
    if continue_in:
        return None
    try:
        from core.lexicon import norm
        from core.paths import is_open_folder_request
        from agents.desktop_agent import _SETTINGS, _SETTINGS_ACT
        t = norm(task).strip(" .!?")
        if not _JUST_OPEN.match(t) or _compound(t) or _SETTINGS_ACT.search(t.split(" ", 1)[-1]):
            return None
        if _SETTINGS.search(t):
            what = "abrir as Configurações do Windows"
        elif is_open_folder_request(task):
            what = "abrir a pasta"
        else:
            return None
    except Exception:
        return None
    return {"analysis": f"{what.capitalize()} (atalho, sem IA)", "skills": [], "fast_path": "abrir",
            "subtasks": [{"agent": "DESKTOP", "task": task, "original_task": task,
                          "params": {"action_type": "open"}}]}


def fast_search_plan(task: str, continue_in: str = "") -> Optional[dict]:
    """'pesquisa receita de bolo no google' -> WEB com o termo, sem modelo. Sem site citado o Maestro decide
    (pode ser dentro do site aberto, numa loja, no Spotify...)."""
    if continue_in:
        return None
    try:
        from core.lexicon import norm
        m = _SEARCH_ON.match(norm(task).strip(" .!?"))
        if not m or _compound(m.group("q")):
            return None
        from core.learned_plans import _find_original
        query = _find_original(task, m.group("q")) or m.group("q")
    except Exception:
        return None
    site = "YouTube" if m.group("site") == "youtube" else "Google"
    return {"analysis": f"Pesquisar no {site} (atalho, sem IA)", "skills": [], "fast_path": "pesquisar",
            "subtasks": [{"agent": "WEB", "task": f"pesquisar {query} no {site}", "original_task": task,
                          "params": {"query": query}}]}


def shortcut_open_plan(task: str, continue_in: str = "") -> Optional[dict]:
    """Atalhos sem IA ("abrir <app/site>", "abre a pasta X", "abre as configuracoes de Y", "pesquisa X no Google")
    ja validados pelas politicas de aceite, como o Maestro faria. None = sem atalho, ou pedido ambiguo (o Maestro
    pergunta). O Controller chama antes da conversa: esses pedidos nao pagam modelo nenhum."""
    if _detect_ambiguity(task):
        return None
    fast = fast_open_plan(task, continue_in) or fast_system_plan(task, continue_in) \
        or fast_search_plan(task, continue_in)
    if not fast:
        return None
    from core.plan_validator import validate_plan
    if not validate_plan(task, fast).approved:
        return None
    fast["validation"] = {"approved": True, "violations": []}
    print(f"[Maestro] Atalho: {fast['analysis']}")
    return fast


# ── Atalho sem IA: continuar no que esta aberto ───────────────────────
# "clica em Area de Trabalho", "pausa o video", "volta para a tela anterior" com o app/aba
# aberto: o alvo da conversa ja diz qual agente age. Criar/escrever conteudo, resumir ou
# mexer em outro app continuam no Maestro (ele decide agente e conteudo).
_TARGET_AGENT = {"web": "WEB", "code": "CODE", "folder": "FILE"}
_INTERACT = re.compile(
    r"^(?:(?:agora|ai|e|entao|por favor)\s+)*(?:(?:no|na|nos|nas|em)\s+[^,]{1,70}?(?:,\s*|\s+))?"
    r"(?:clic|cliqu|apert|pression|selecion|marc|desmarc|abr|entr|ir\b|va\b|vai\b|volt|avanc|pul|paus|"
    r"toc|continu|rol|desc|sub|maximiz|minimiz|restaur|fech|ampli|diminu|aument|ativ|desativ|lig|deslig|"
    r"pesquis|busc|procur|filtr|orden|mostr|exib|copi|recarreg|atualiz|tir|assist|reproduz|silenci|"
    r"mud\w* para|troc\w* para|acess)\w*", re.I)
_NOT_SIMPLE = re.compile(r"\b(?:cri[ae]r?|ger[ae]r?|escrev\w*|redi[gj]\w*|compo\w*|elabor\w*|resum\w*|"
                         r"analis\w*|explic\w*|planilha nova|novo arquivo|e depois|depois disso)\b", re.I)


def profile_plan(task: str, store=None) -> Optional[dict]:
    """Rota aplicada no AI Research Lab (core/lab_drafts.py): o pedido que comeca com o prefixo vai para o
    agente-base do perfil, sem chamar o modelo para rotear. Passa pelas mesmas politicas de aceite; reprovado,
    o Maestro planeja normalmente. None: nenhum perfil aplicado abre este pedido."""
    try:
        from core.lab_drafts import profile_for
        if store is None:
            from core.brain import get_brain
            brain = get_brain()
            if not brain.enabled:
                return None
            store = brain.store
        found = profile_for(task, store)
    except Exception as exc:                     # perfil quebrado nunca bloqueia o pedido
        print(f"[Maestro] perfil do Lab indisponivel: {exc}")
        return None
    if not found:
        return None
    plan = {"analysis": f"Perfil do Lab \"{found['name']}\": pedidos que comecam com \"{found['prefix']}\" vao para "
                        f"{found['agent']}", "skills": [], "fast_path": "perfil",
            "profile": {"note": found["rel"], "agent": found["agent"], "prefix": found["prefix"]},
            "subtasks": [{"agent": found["agent"], "task": task, "original_task": task, "params": {}}]}
    from core.plan_validator import validate_plan
    check = validate_plan(task, plan)
    if not check.approved:
        print(f"[Maestro] Perfil do Lab recusado pelas politicas: {check.summary()}")
        return None
    plan["validation"] = {"approved": True, "violations": []}
    print(f"[Maestro] {plan['analysis']}")
    return plan


def vault_plan(task: str) -> Optional[dict]:
    """Abrir cofre do Obsidian: tem link direto e nao depende do que esta na tela, entao vem
    antes de continuar na janela aberta. None: o pedido nao e sobre cofre."""
    try:
        from core.obsidian_vaults import parse_request
        found = parse_request(task)
    except Exception:
        return None
    if not found:
        return None
    if found.get("ask"):
        return {"needs_clarification": True, "question": found["ask"]}
    name = found["open"]
    return {"analysis": f"Abrir o cofre {name} no Obsidian (link direto, sem IA)", "skills": [], "fast_path": "abrir",
            "subtasks": [{"agent": "DESKTOP", "task": f"abrir o cofre {name} no Obsidian", "original_task": task,
                          "params": {"vault": name, "action_type": "open"}}]}


def continue_plan(task: str, kind: str, target: Optional[str], session) -> Optional[dict]:
    """Plano direto para uma acao DENTRO do alvo aberto. None = o Maestro planeja."""
    if kind != "continue" or not target or session is None or not session.target(target):
        return None
    try:
        from core.lexicon import norm
        t = norm(task).strip(" .!?")
    except Exception:
        t = (task or "").lower().strip(" .!?")
    if not _INTERACT.match(t) or _NOT_SIMPLE.search(t) or len(t) > 220:
        return None
    if _detect_ambiguity(task):
        return None
    agent = "DESKTOP" if target.startswith("app:") else _TARGET_AGENT.get(target)
    if not agent:
        return None
    plan = {"analysis": f"Continuar em {target} (atalho da conversa, sem IA)",
            "subtasks": [{"agent": agent, "task": task, "params": {}, "original_task": task}],
            "skills": [], "fast_path": "continuar"}
    from core.plan_validator import validate_plan
    check = validate_plan(task, plan)
    if not check.approved:
        return None
    plan["validation"] = {"approved": True, "violations": []}
    print(f"[Maestro] Atalho: {plan['analysis']}")
    return plan


class Maestro:
    def __init__(self, memory=None):
        self._config = get_config()
        self._client = get_client()
        self.model = self._config.get_model("maestro")
        self.effort = self._config.get_effort("maestro")
        self._memory = memory

    def analyze(self, task, conversation: str = "", continue_in: str = ""):
        """conversation: resumo da sessao (Session.context_block); continue_in:
        alvo ja aberto onde o pedido continua (web, app:notepad, code...)."""
        print("\n[Maestro] Analisando...")

        # Ambiguity gate (cenarios A e J): bloqueia ANTES do cache,
        # antes da memoria e antes da API. Pergunta UMA coisa só.
        ambiguity = _detect_ambiguity(task)
        if ambiguity:
            print(f"[Maestro] Ambiguidade detectada: {ambiguity['why']}")
            return {
                "needs_clarification": True,
                "question": ambiguity["question"],
                "why": ambiguity["why"],
                "subtasks": [],
            }

        # "abrir <app/site>", "abre a pasta X", "abre as configuracoes de Y", "pesquisa X no Google": plano direto,
        # sem chamar o modelo. Passa pelas mesmas politicas de aceite que um plano do LLM.
        fast = shortcut_open_plan(task, continue_in)
        if fast:
            return fast
        # Rota aplicada pela pessoa no Lab (perfil sobre um agente-base): decide o agente sem o modelo
        if not continue_in:
            profiled = profile_plan(task)
            if profiled:
                return profiled

        # Memoria de rotas — falha do lookup nunca bloqueia a tarefa.
        # Vai na mensagem do usuario (nao no system) para nao invalidar
        # o prompt cache do PROMPT, que e o prefixo estavel.
        routes = []
        try:
            if self._memory is None:
                from agents.memory_agent import MemoryAgent
                self._memory = MemoryAgent()
            routes = self._memory.find_routes(task, k=2)
            from core.panorama import activity
            activity("memory", agent="MAESTRO", count=len(routes), action="workflow_routes")
            if routes:
                print(f"[Maestro] {len(routes)} rota(s) da memoria como referencia")
        except Exception as mem_err:
            print(f"[Maestro] memoria indisponivel: {mem_err}")
        hint = _format_route_hint(routes)

        # Segundo cerebro: tarefas de referencia parecidas (caminhos que ja
        # funcionaram, curados no Obsidian). Tambem so como referencia.
        try:
            from core.brain import get_brain
            refs = get_brain().find_references(task, k=2)
            from core.panorama import activity
            activity("memory", agent="MAESTRO", count=len(refs), refs=[r["title"] for r in refs], action="references")
            if refs:
                print(f"[Maestro] {len(refs)} referencia(s) do segundo cerebro")
                hint += ("\n" if hint else "") + "REFERENCIA (segundo cerebro, so pista — nao copie valores):\n"
                hint += "\n".join(f"- {r['title']} [{r['agent']}]: {r['path']}" for r in refs)
            # Licoes aprendidas que tocam no pedido (falhas reais que viraram regra)
            lessons = get_brain().find_lessons(task, k=2)
            if lessons:
                hint += ("\n" if hint else "") + "LICOES APRENDIDAS (segundo cerebro):\n"
                hint += "\n".join(f"- {l['title']}: {l['rule']}" for l in lessons)
            # Skills do catalogo que o Maestro aplica ao planejar (tech-lead, seguranca, ...)
            from core.skills import skills_for
            sk_text, sk_names = skills_for("MAESTRO", task, limit=2)
            get_brain().last_skills["MAESTRO"] = sk_names
            if sk_text:
                hint += ("\n" if hint else "") + "SKILLS PARA PLANEJAR (catalogo; referencia):\n" + sk_text
            # Camada do usuario: instrucoes do Harness para o Maestro e a secao Voce (so se escritas)
            from core.harness import you_block
            mine_h = get_brain().harness.agent_block("MAESTRO")
            if mine_h:
                hint += ("\n" if hint else "") + mine_h
            you, _ = you_block(get_brain().store, compact=True)
            if you:
                hint += ("\n" if hint else "") + you
            # Diario (so com a integracao ligada, nunca privado): dado da pessoa, nunca permissao
            diary, diary_used = get_brain().journal.context_block(task, compact=True)
            if diary:
                hint += ("\n" if hint else "") + diary
                get_brain().last_sources["MAESTRO"] = diary_used
        except Exception as brain_err:
            print(f"[Maestro] segundo cerebro indisponivel: {brain_err}")

        try:
            from core.user_settings import instructions_block
            mine = instructions_block()
            if mine:
                hint = (hint + "\n\n" if hint else "") + mine
        except Exception:
            pass
        if conversation:
            hint = (hint + "\n\n" if hint else "") + "CONTEXTO DA CONVERSA:\n" + conversation
        if continue_in:
            hint += f"\nCONTINUAR EM: {continue_in}"
        from core.panorama import activity
        activity("context", agent="MAESTRO", count=len(hint), status="completed", action="selected_characters")

        plan = self._ask(task, hint)
        if not plan.get("subtasks"):
            return plan   # clarificacao, limitacao ou erro

        # ── Politicas de aceite (codigo, nao LLM) ────────────────────
        # O Maestro propoe; as politicas validam. Uma reprovacao ganha UMA
        # chance de replanejar com o motivo literal.
        from core.plan_validator import validate_plan
        validation = validate_plan(task, plan)
        if not validation.approved:
            print(f"[Maestro] Plano reprovado: {validation.summary()}")
            retry = self._ask(task, hint, feedback=validation.feedback())
            if retry.get("limitation") or retry.get("needs_clarification"):
                return retry
            if retry.get("subtasks"):
                plan = retry
                validation = validate_plan(task, plan)

        plan["validation"] = {"approved": validation.approved,
                              "violations": validation.violations}
        if routes:
            plan["memory_routes"] = [r["route"] for r in routes]
        if not validation.approved:
            return {"error": True, "subtasks": [], "validation": plan["validation"],
                    "rejected_plan": plan,
                    "message": "O Maestro reprovou o plano: " + validation.summary()}
        return plan

    def _ask(self, task: str, hint: str = "", feedback: str = "") -> dict:
        """Uma chamada ao LLM + saneamento do plano (sem validacao de politica)."""
        try:
            user = f"TAREFA: {task}\n"
            if hint:
                user += f"\n{hint}\n"
            if feedback:
                user += ("\nSEU PLANO ANTERIOR FOI REPROVADO PELAS POLITICAS DE ACEITE:\n"
                         f"{feedback}\nCorrija e devolva o plano completo.\n")
            user += "JSON puro."
            raw = self._client.message(
                model=self.model, system=PROMPT,
                user_content=user,
                max_tokens=self._config.get("limits.max_tokens_strong", 16000),
                effort=self.effort, agent="MAESTRO",
            )
            plan = safe_parse(raw, self.model)

            # Se o LLM detectou ambiguidade que a heuristica nao pegou,
            # propaga o pedido de clarificacao em vez de "Sem subtasks".
            if plan.get("needs_clarification"):
                print(f"[Maestro] LLM pediu clarificacao: {plan.get('why','')}")
                return {
                    "needs_clarification": True,
                    "question": plan.get("question", "Pode dar mais detalhes?"),
                    "why": plan.get("why", "ambiguidade detectada pelo LLM"),
                    "subtasks": [],
                }

            # Pedido que o sistema nao deve cumprir (ex.: letra de musica
            # protegida). Melhor avisar do que escrever um substituto.
            if plan.get("cannot_do"):
                reason = plan.get("reason") or "Nao posso fazer isso como pedido."
                alt = plan.get("alternative") or ""
                print(f"[Maestro] Limitacao: {reason}")
                if alt and not alt.lower().startswith("posso"):
                    alt = "Posso " + alt[0].lower() + alt[1:]
                return {"limitation": True, "subtasks": [],
                        "message": reason + (f" {alt}" if alt else "")}

            if "subtasks" not in plan or not plan.get("subtasks"):
                return {"error": True, "message": "Sem subtasks"}

            # ── PRESERVA TASK ORIGINAL ──────────────────────────────────
            # O Maestro pode REFORMULAR a task ao gerar subtasks (ex.:
            # "sistema profissional" -> "criar sistema com arquitetura
            # modular"). Isso polui topic extraction e theme leak downstream.
            # Carregamos `original_task` ao lado para que os agentes possam
            # usar a versao do USUARIO quando precisarem (topic, theme leak).
            for sub in plan.get("subtasks", []):
                sub.setdefault("original_task", task)

            # Validação pós-LLM: bloqueia texto inventado
            # Texto generico que o usuario NAO pediu ("Ola", "Hello") nao vai para o app
            generics = {"ola!", "ola", "olá", "olá!", "hello", "hi", "oi", "bom dia"}
            low = task.lower()
            for sub in plan.get("subtasks", []):
                params = sub.get("params", {}) or {}
                for k in ("text", "message"):
                    v = str(params.get(k) or "").strip()
                    if v.lower() in generics and v.lower() not in low:
                        params[k] = ""

            # Filtro defensivo: se temos uma subtask CODE, removemos qualquer
            # subtask DESKTOP que pareça apenas "colar o codigo no notepad/word"
            # como visualizacao — comportamento ruim que confunde o usuario.
            subs = plan.get("subtasks", [])
            has_code = any((s.get("agent") or "").upper() == "CODE" for s in subs)
            if has_code:
                filtered = []
                removed = 0
                index_map: dict = {}     # numero antigo (1..n) -> novo, para remapear depends_on
                for old_n, s in enumerate(subs, start=1):
                    agent = (s.get("agent") or "").upper()
                    if agent == "DESKTOP":
                        p = s.get("params", {}) or {}
                        app = (p.get("app", "") or "").lower()
                        action = (p.get("action_type", "") or "").lower()
                        text = (p.get("text", "") or p.get("message", "") or "")
                        # Heuristica: notepad/word + texto que parece codigo
                        looks_like_code = any(
                            tok in text for tok in (
                                "<html", "<!DOCTYPE", "<script", "<style",
                                "def ", "class ", "import ", "from ", "function ",
                            )
                        )
                        if app in ("notepad", "bloco de notas", "word", "microsoft word") and (
                            action in ("write_text", "type", "paste") or looks_like_code
                        ):
                            removed += 1
                            continue
                    filtered.append(s)
                    index_map[old_n] = len(filtered)
                if removed:
                    print(f"[Maestro] Removido(s) {removed} subtask(s) DESKTOP redundante(s) acoplada(s) ao CODE")
                    for s in filtered:
                        dep = s.get("depends_on")
                        if isinstance(dep, int) and not isinstance(dep, bool):
                            # dependia de uma removida: fica sem dependencia (a removida so mostrava o codigo)
                            s["depends_on"] = index_map.get(dep)
                    plan["subtasks"] = filtered

            print(f"[Maestro] {len(plan['subtasks'])} subtask(s)")
            return plan

        except APIConnectionError:
            return {"error": True, "message": "Não consegui conectar ao serviço de IA. Verifique sua conexão e tente novamente."}
        except Exception as ex:
            print(f"[Maestro] Erro: {ex}")
            return {"error": True, "message": str(ex)}
