"""
Biblioteca de AI Engineering: trilha "Começar" e catalogo de topicos com busca e filtros.

Cada ficha: introducao em portugues, por que importa, nivel, pre-requisitos, leituras em ordem sugerida,
atividade pratica, termos-chave e limites de evidencia. Cada leitura tem titulo, autores ou instituicao,
ano, link original e tipo: documentacao | pesquisa | preprint | didatico.
  - pesquisa: publicada com revisao por pares (o veiculo esta em `venue`)
  - preprint: arXiv ou relatorio tecnico sem revisao por pares
  - didatico: guia tecnico de quem constroi o sistema (engenharia, blog tecnico)
  - documentacao: especificacao ou documentacao oficial

Links e titulos conferidos na fonte em 2026-11-12 (scripts/check_library_links.py refaz a conferencia).
Conteudo estatico, sem rede em tempo de execucao: a tela so abre o link quando a pessoa clica.
"""
from __future__ import annotations

import unicodedata
from typing import Optional

LEVELS = ("iniciante", "intermediario", "avancado")
KINDS = ("documentacao", "pesquisa", "preprint", "didatico")
VERIFIED_ON = "2026-11-12"


def _r(title, authors, year, url, kind, venue="", note=""):
    return {"title": title, "authors": authors, "year": year, "url": url, "kind": kind, "venue": venue, "note": note}


TOPICS = [
    {
        "id": "harness",
        "title": "Harness Engineering",
        "level": "iniciante",
        "order": 1,
        "intro": "O harness é tudo o que fica em volta do modelo: as ferramentas que ele pode usar, as regras, o "
                 "ambiente onde age, o que ele vê de volta (feedback) e as verificações que dizem se terminou. "
                 "Um bom harness transforma um modelo capaz em um agente confiável.",
        "why": "A maior parte da qualidade de um agente vem do ambiente, não do prompt: o que ele consegue observar, "
               "como recebe erros e como prova que terminou.",
        "prereqs": [],
        "readings": [
            _r("Building effective AI agents", "Anthropic", 2024,
               "https://www.anthropic.com/research/building-effective-agents", "didatico",
               note="Comece aqui: fluxos de trabalho x agentes, e quando não usar agentes."),
            _r("Effective harnesses for long-running agents", "Anthropic", 2025,
               "https://www.anthropic.com/research/effective-harnesses-for-long-running-agents", "didatico",
               note="Como manter progresso, verificação e estado em tarefas longas."),
            _r("SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering",
               "Yang, Jimenez, Wettig et al.", 2024, "https://arxiv.org/abs/2405.15793", "pesquisa",
               venue="NeurIPS 2024", note="Mostra com medição que a interface do ambiente muda o resultado."),
        ],
        "practice": "Escolha uma tarefa com resultado verificável (ex.: criar uma planilha com 3 colunas). No Creative AIx, "
                    "escreva no Harness uma regra para o agente de Dados e rode em modo Simular e depois de "
                    "verdade. Compare o plano e confira o arquivo final, não a mensagem de sucesso.",
        "terms": ["harness", "ferramenta", "feedback", "critério de término", "verificação independente"],
        "limits": "",
        "lab": "playground",
    },
    {
        "id": "context",
        "title": "Context Engineering & Agent Memory",
        "level": "iniciante",
        "order": 2,
        "intro": "Contexto é o que o modelo lê a cada passo. Engenharia de contexto decide o que entra, em que ordem e "
                 "dentro de qual orçamento; memória é o que persiste entre passos e sessões, com origem e atualização.",
        "why": "Contexto demais dilui a atenção e custa caro; de menos, o agente esquece regras. A memória precisa de "
               "proveniência para ser corrigida ou apagada.",
        "prereqs": ["harness"],
        "readings": [
            _r("Effective context engineering for AI agents", "Anthropic", 2025,
               "https://www.anthropic.com/research/effective-context-engineering-for-ai-agents", "didatico"),
            _r("Lost in the Middle: How Language Models Use Long Contexts", "Liu, Lin, Hewitt et al.", 2023,
               "https://arxiv.org/abs/2307.03172", "pesquisa", venue="TACL 2024",
               note="Informação no meio de contextos longos é usada pior do que no início ou no fim."),
            _r("MemGPT: Towards LLMs as Operating Systems", "Packer, Wooders, Lin et al.", 2023,
               "https://arxiv.org/abs/2310.08560", "preprint", note="Memória em camadas, inspirada em sistema operacional."),
        ],
        "practice": "Ligue o Diário na Conversa, escreva uma prioridade fictícia e faça um pedido que a mencione. "
                    "Veja na resposta de onde veio o trecho. Depois marque a entrada como privada e confirme que ela "
                    "deixa de aparecer.",
        "terms": ["janela de contexto", "orçamento", "memória de trabalho", "memória persistente", "proveniência", "recuperação"],
        "limits": "",
        "lab": "",
    },
    {
        "id": "aci",
        "title": "Agent-Computer Interface (ACI)",
        "level": "intermediario",
        "order": 3,
        "intro": "ACI é o contrato entre o agente e as ferramentas: nomes, parâmetros, o que cada ação devolve e como "
                 "os erros chegam. Ferramenta boa para humanos nem sempre é boa para modelos.",
        "why": "Muitas falhas de agentes são de interface: parâmetro ambíguo, saída longa demais, erro sem dica de "
               "como corrigir.",
        "prereqs": ["harness"],
        "readings": [
            _r("Writing effective tools for AI agents", "Anthropic", 2025,
               "https://www.anthropic.com/research/writing-tools-for-agents", "didatico"),
            _r("SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering",
               "Yang, Jimenez, Wettig et al.", 2024, "https://arxiv.org/abs/2405.15793", "pesquisa", venue="NeurIPS 2024"),
            _r("Model Context Protocol — Specification (2025-06-18)", "Model Context Protocol", 2025,
               "https://modelcontextprotocol.io/specification/2025-06-18", "documentacao",
               note="Padrão aberto para expor ferramentas e dados a agentes."),
        ],
        "practice": "Pegue uma ferramenta do servidor MCP do app (brain_search) e escreva três entradas inválidas "
                    "(vazia, longa demais, com caminho fora da pasta). Anote o erro devolvido e reescreva a mensagem "
                    "para que o agente saiba o que fazer em seguida.",
        "terms": ["contrato de ferramenta", "observação", "erro acionável", "MCP", "esquema de parâmetros"],
        "limits": "",
        "lab": "tools",
    },
    {
        "id": "orchestration",
        "title": "Multi-Agent Orchestration & Brain–Tool Decoupling",
        "level": "intermediario",
        "order": 4,
        "intro": "Orquestração divide um pedido entre agentes (roteamento, handoffs, contratos). Separar o cérebro "
                 "(o modelo que propõe) das mãos (o executor que age, com permissões) permite trocar um sem "
                 "perder o controle do outro.",
        "why": "O modelo pode propor qualquer coisa; quem autoriza a ação é código determinístico. É isso que impede "
               "um texto lido de virar uma ação não pedida.",
        "prereqs": ["harness", "aci"],
        "readings": [
            _r("ReAct: Synergizing Reasoning and Acting in Language Models", "Yao, Zhao, Yu et al.", 2022,
               "https://arxiv.org/abs/2210.03629", "pesquisa", venue="ICLR 2023"),
            _r("How we built our multi-agent research system", "Anthropic", 2025,
               "https://www.anthropic.com/research/multi-agent-research-system", "didatico"),
            _r("Scaling Managed Agents with stable interfaces", "Anthropic", 2026,
               "https://www.anthropic.com/research/managed-agents", "didatico",
               note="Separação entre o 'cérebro' e as 'mãos' do agente."),
            _r("Handoffs — OpenAI Agents SDK", "OpenAI", 2025,
               "https://openai.github.io/openai-agents-python/handoffs/", "documentacao"),
        ],
        "practice": "Faça um pedido com dois agentes (ex.: pesquisar preços e montar uma planilha) e acompanhe a "
                    "delegação no cartão do agente. Depois peça algo com efeito (enviar uma mensagem) e observe o "
                    "executor pedir confirmação mesmo com o plano aprovado.",
        "terms": ["roteamento", "handoff", "executor", "proposta x ação", "permissão no executor"],
        "limits": "",
        "lab": "playground",
    },
    {
        "id": "evals",
        "title": "Agentic Evals & Process Reward Models (PRMs)",
        "level": "intermediario",
        "order": 5,
        "intro": "Avaliar agentes é comparar o estado final com o esperado (resultado) e, às vezes, julgar cada passo "
                 "(trajetória). PRMs são modelos treinados para pontuar passos intermediários.",
        "why": "Agente que diz 'pronto' não terminou necessariamente. Sem verificador independente, você mede a "
               "confiança do agente, não o sucesso.",
        "prereqs": ["harness"],
        "readings": [
            _r("Demystifying evals for AI agents", "Anthropic", 2026,
               "https://www.anthropic.com/research/demystifying-evals-for-ai-agents", "didatico"),
            _r("τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains", "Yao, Shinn, Razavi et al.",
               2024, "https://arxiv.org/abs/2406.12045", "preprint", note="Mede o estado final do banco de dados, não a fala."),
            _r("Let's Verify Step by Step", "Lightman, Kosaraju, Burda et al.", 2023,
               "https://arxiv.org/abs/2305.20050", "pesquisa", venue="ICLR 2024",
               note="Supervisão por processo x por resultado, em matemática."),
        ],
        "practice": "Escolha três tarefas já feitas no Histórico. Para cada uma, escreva o que comprovaria o sucesso "
                    "(arquivo, URL, valor) e confira o estado final. Marque quais disseram 'pronto' sem comprovação.",
        "terms": ["avaliação por resultado", "trajetória", "verificador", "PRM", "sucesso declarado x comprovado"],
        "limits": "PRMs foram mais estudados em matemática; o uso em agentes com ferramentas ainda é pesquisa ativa.",
        "lab": "evals",
    },
    {
        "id": "test-time",
        "title": "Test-Time Scaling & Adaptive Reasoning",
        "level": "avancado",
        "order": 6,
        "intro": "Gastar mais computação na hora da resposta (mais raciocínio, mais tentativas, verificação) pode "
                 "melhorar o resultado. Raciocínio adaptativo decide quanto gastar conforme a dificuldade.",
        "why": "Esforço fixo desperdiça em tarefas fáceis e falta nas difíceis. Custo e latência entram na conta.",
        "prereqs": ["evals"],
        "readings": [
            _r("Self-Consistency Improves Chain of Thought Reasoning in Language Models", "Wang, Wei, Schuurmans et al.",
               2022, "https://arxiv.org/abs/2203.11171", "pesquisa", venue="ICLR 2023"),
            _r("Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters",
               "Snell, Lee, Xu et al.", 2024, "https://arxiv.org/abs/2408.03314", "preprint"),
            _r("s1: Simple test-time scaling", "Muennighoff, Yang, Shi et al.", 2025,
               "https://arxiv.org/abs/2501.19393", "preprint"),
        ],
        "practice": "Defina um orçamento (ex.: 3 chamadas). Compare 'uma tentativa com mais esforço' com 'três "
                    "tentativas e voto' em cinco pedidos com resposta conferível. Registre acertos, custo e tempo.",
        "terms": ["computação em teste", "esforço", "amostragem", "voto", "verificador", "orçamento"],
        "limits": "Os ganhos variam por tarefa e modelo; resultados medidos em matemática e código nem sempre "
                  "valem para tarefas com ferramentas.",
        "lab": "evals",
    },
    {
        "id": "rlm",
        "title": "Recursive Language Models (RLMs)",
        "level": "avancado",
        "order": 7,
        "intro": "Um RLM trata uma entrada enorme como ambiente: o modelo examina partes, chama a si mesmo (ou a "
                 "outro modelo) sobre pedaços e combina os resultados, em vez de ler tudo de uma vez.",
        "why": "Contextos muito longos degradam a qualidade. Decompor com chamadas recursivas é uma alternativa, com "
               "custo e condição de parada a controlar.",
        "prereqs": ["context", "test-time"],
        "readings": [
            _r("Recursive Language Models (blog)", "Zhang, Khattab", 2025,
               "https://alexzhang13.github.io/blog/2025/rlm/", "didatico"),
            _r("Recursive Language Models", "Zhang, Kraska, Khattab", 2025,
               "https://arxiv.org/abs/2512.24601", "preprint"),
        ],
        "practice": "Desenhe (no papel ou no Diário) um RLM para resumir 200 notas: o que cada chamada recebe, a "
                    "profundidade máxima, o limite de chamadas e como você conferiria o resumo contra as notas.",
        "terms": ["recursão", "decomposição", "condição de parada", "limite de recursos"],
        "limits": "Abordagem recente (preprint de 2025); evidência ainda restrita aos experimentos dos autores.",
        "lab": "",
    },
    {
        "id": "interpretability",
        "title": "Mechanistic Interpretability & Circuit Tracing",
        "level": "avancado",
        "order": 8,
        "intro": "Interpretabilidade mecanicista tenta entender o que acontece dentro do modelo: quais componentes e "
                 "caminhos internos produzem uma resposta. Circuit tracing monta grafos desses caminhos.",
        "why": "Olhar só a saída diz o que o modelo fez, não como. Entender mecanismos ajuda a achar falhas que "
               "testes de saída não mostram.",
        "prereqs": [],
        "readings": [
            _r("Toy Models of Superposition", "Elhage et al. (Anthropic)", 2022,
               "https://transformer-circuits.pub/2022/toy_model/index.html", "preprint",
               note="Relatório técnico, sem revisão por pares. Base conceitual."),
            _r("Circuit Tracing: Revealing Computational Graphs in Language Models", "Ameisen et al. (Anthropic)", 2025,
               "https://transformer-circuits.pub/2025/attribution-graphs/methods.html", "preprint",
               note="Relatório técnico. O método dos grafos de atribuição."),
            _r("On the Biology of a Large Language Model", "Lindsey et al. (Anthropic)", 2025,
               "https://transformer-circuits.pub/2025/attribution-graphs/biology.html", "preprint",
               note="Relatório técnico. Aplicações do método."),
        ],
        "practice": "Este tema exige acesso aos pesos de um modelo aberto; os modelos usados pelo app não expõem "
                    "ativações. Exercício guiado: leia a seção de método e escreva a diferença entre 'o modelo disse "
                    "X' e 'este caminho interno produziu X'.",
        "terms": ["ativação", "feature", "superposição", "circuito", "grafo de atribuição"],
        "limits": "Os métodos explicam parte do comportamento em casos estudados; não há garantia de cobertura "
                  "completa de um modelo.",
        "lab": "",
    },
    {
        "id": "world-models",
        "title": "World Models & Embodied AI",
        "level": "avancado",
        "order": 9,
        "intro": "Um world model aprende a dinâmica de um ambiente: dado o estado e uma ação, prevê o próximo estado. "
                 "Agentes incorporados agem em ambientes simulados ou físicos usando essas previsões.",
        "why": "Prever antes de agir permite planejar e treinar em simulação, com menos tentativa e erro no mundo real.",
        "prereqs": [],
        "readings": [
            _r("World Models", "Ha, Schmidhuber", 2018, "https://arxiv.org/abs/1803.10122", "pesquisa",
               venue="NeurIPS 2018 (como 'Recurrent World Models Facilitate Policy Evolution')"),
            _r("Mastering Diverse Domains through World Models (DreamerV3)", "Hafner, Pasukonis, Ba et al.", 2023,
               "https://arxiv.org/abs/2301.04104", "preprint"),
            _r("Genie: Generative Interactive Environments", "Bruce, Dennis, Edwards et al.", 2024,
               "https://arxiv.org/abs/2402.15391", "pesquisa", venue="ICML 2024"),
        ],
        "practice": "Em um ambiente controlado (uma pasta de teste), escreva sua previsão antes de cada ação do agente "
                    "de Arquivos (quais arquivos existirão depois) e compare com o estado real ao final.",
        "terms": ["estado", "dinâmica", "observação", "ação", "simulação", "planejamento"],
        "limits": "Resultados fortes em jogos e simulação; a transferência para o mundo físico segue em pesquisa.",
        "lab": "",
    },
    {
        "id": "serving",
        "title": "Disaggregated Serving & Dynamic Model Routing",
        "level": "avancado",
        "order": 10,
        "intro": "Servir modelos em escala separa estágios da inferência (prefill e decode) em máquinas diferentes e "
                 "gerencia a memória de atenção. Roteamento dinâmico manda cada pedido para o modelo que resolve "
                 "com o menor custo aceitável.",
        "why": "Qualidade, custo e latência competem. Política fixa (sempre o maior modelo) é cara; roteamento "
               "condicionado à tarefa pode manter a qualidade gastando menos.",
        "prereqs": ["evals"],
        "readings": [
            _r("Efficient Memory Management for Large Language Model Serving with PagedAttention (vLLM)",
               "Kwon, Li, Zhuang et al.", 2023, "https://arxiv.org/abs/2309.06180", "pesquisa", venue="SOSP 2023"),
            _r("DistServe: Disaggregating Prefill and Decoding for Goodput-optimized LLM Serving",
               "Zhong, Liu, Chen et al.", 2024, "https://arxiv.org/abs/2401.09670", "pesquisa", venue="OSDI 2024"),
            _r("Splitwise: Efficient generative LLM inference using phase splitting", "Patel, Choukse, Zhang et al.",
               2023, "https://arxiv.org/abs/2311.18677", "pesquisa", venue="ISCA 2024"),
            _r("RouteLLM: Learning to Route LLMs with Preference Data", "Ong, Almahairi, Wu et al.", 2024,
               "https://arxiv.org/abs/2406.18665", "preprint"),
        ],
        "practice": "Use a tela Atividade: compare o custo por tarefa entre agentes. Proponha uma regra (tarefas de "
                    "abrir site sem modelo; planilhas com o modelo menor) e estime a economia com os números reais.",
        "terms": ["prefill", "decode", "KV cache", "goodput", "roteamento", "política fixa x condicionada"],
        "limits": "",
        "lab": "evals",
    },
]

_BY_ID = {t["id"]: t for t in TOPICS}


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").lower()) if unicodedata.category(c) != "Mn")


def _with_article(t: dict) -> dict:
    from core.library_articles import ARTICLES, reading_minutes
    sections = ARTICLES.get(t["id"], [])
    return {**t, "article": sections, "minutes": reading_minutes(sections) if sections else 1}


def topic(topic_id: str) -> Optional[dict]:
    t = _BY_ID.get(topic_id)
    return _with_article(t) if t else None


def track() -> list[dict]:
    """Trilha 'Começar em AI Engineering': na ordem sugerida, com o artigo de cada tema."""
    return [_with_article(t) for t in sorted(TOPICS, key=lambda t: t["order"])]


def search(query: str = "", level: str = "", kind: str = "") -> list[dict]:
    """Busca por texto (titulo, introducao, termos, leituras) e filtros por nivel e tipo de material."""
    words = [w for w in _fold(query).split() if len(w) > 1]
    out = []
    for t in track():
        if level and t["level"] != level:
            continue
        if kind and not any(r["kind"] == kind for r in t["readings"]):
            continue
        hay = _fold(" ".join([t["title"], t["intro"], t["why"], " ".join(t["terms"])]
                             + [r["title"] + " " + r["authors"] for r in t["readings"]]
                             + [" ".join(sec["p"]) for sec in t.get("article", [])]))
        if all(w in hay for w in words):
            out.append(t)
    return out
