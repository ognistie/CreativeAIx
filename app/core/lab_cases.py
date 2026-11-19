"""Contratos de casos e verificadores isolados, um por agente avaliado."""
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import re


def relative_file(value):
    if not isinstance(value, str) or not value or ":" in value or "\x00" in value:
        raise ValueError("use caminhos relativos dentro da pasta do caso")
    path = PureWindowsPath(value)
    if path.anchor or not path.parts or any(p.endswith((" ", ".")) or PureWindowsPath(p).is_reserved() for p in path.parts):
        raise ValueError("use caminhos relativos dentro da pasta do caso")
    return Path(*path.parts)


def validate_file(case):
    setup, expect = case.get("setup", {}), case["expect"]
    if not isinstance(setup, dict) or len(setup) > 20 or any(not isinstance(v, str) for v in setup.values()):
        raise ValueError("preparo de Arquivos inválido")
    if "{ws}" not in case["task"]:
        raise ValueError("cada caso de Arquivos precisa de uma tarefa com {ws}")
    exists, absent, contains = expect.get("exists", []), expect.get("absent", []), expect.get("contains", {})
    if not isinstance(exists, list) or not isinstance(absent, list) or not isinstance(contains, dict):
        raise ValueError("verificação de Arquivos inválida")
    if not (exists or absent or contains or expect.get("blocked_or_inside") is True):
        raise ValueError("descreva ao menos uma verificação")
    if any(not isinstance(text, str) for text in contains.values()):
        raise ValueError("conteúdo esperado deve ser texto")
    if "blocked_or_inside" in expect and not isinstance(expect["blocked_or_inside"], bool):
        raise ValueError("verificação de escopo precisa ser booleana")
    for value in [*setup, *exists, *absent, *contains]:
        relative_file(value)


def validate_route(case):
    agents = case["expect"].get("agents")
    if not isinstance(agents, list) or len(agents) > 5 or any(
        agent not in ("FILE", "WEB", "DESKTOP", "CODE", "DATA", "EXTCODE") for agent in agents
    ):
        raise ValueError("informe os agentes esperados do Maestro")
    if not agents and case["expect"].get("clarify") is not True:
        raise ValueError("informe um roteiro ou marque que uma pergunta é esperada")


def validate_code(case):
    files = case["expect"].get("files")
    if not isinstance(files, dict) or not files or len(files) > 40:
        raise ValueError("informe os arquivos esperados de Código")
    functions = case["expect"].get("functions", {})
    if not isinstance(functions, dict) or any(path not in files or not isinstance(rules, dict) or
                                             any(not isinstance(expr, str) for expr in rules.values())
                                             for path, rules in functions.items()):
        raise ValueError("contrato estático de função inválido")
    import ast
    for rules in functions.values():
        for expression in rules.values():
            ast.parse(expression, mode="eval")
    for path, text in files.items():
        relative_file(path)
        if not isinstance(text, str):
            raise ValueError("conteúdo esperado deve ser texto")


def validate_data(case):
    sheets = case["expect"].get("sheets")
    if not isinstance(sheets, dict) or not sheets or len(sheets) > 6:
        raise ValueError("informe abas e células esperadas")
    for title, cells in sheets.items():
        if not title or not isinstance(cells, dict) or not cells or len(cells) > 100:
            raise ValueError("aba ou células inválidas")
        if any(not re.fullmatch(r"[A-Z]{1,2}[1-9][0-9]{0,3}", addr) for addr in cells):
            raise ValueError("use endereços de célula como A1 ou B3")
        if any(value is not None and not isinstance(value, (str, int, float, bool)) for value in cells.values()):
            raise ValueError("valor de célula inválido")


def check(name, ok):
    return {"check": name, "ok": bool(ok)}


def grade_route(case, plan, workspace):
    from core.plan_validator import validate_plan
    routing = plan.get("routing")
    if not isinstance(routing, dict):
        return [check("O planejador produziu um roteiro", False)], []
    exp = case["expect"]
    subs = routing.get("subtasks")
    subs = subs if isinstance(subs, list) else []
    names = [sub.get("agent", "") for sub in subs if isinstance(sub, dict)]
    clarification = routing.get("needs_clarification") is True and bool(routing.get("question"))
    route_ok = False
    if names and not clarification:
        try:
            route_ok = validate_plan(case["task"], routing).approved
        except (AttributeError, TypeError, ValueError):
            pass
    if exp.get("clarify"):
        checks = [check("Pediu esclarecimento sem delegar", clarification and routing.get("subtasks") == [])]
    else:
        checks = [check("Sequência de agentes esperada", names == exp["agents"]),
                  check("Roteiro conforme a política do Maestro", route_ok)]
    shown = [name for name in names if name in ("FILE", "WEB", "DESKTOP", "CODE", "DATA", "EXTCODE")]
    return checks, [{"kind": "roteamento", "action": "planejar", "params": {"agentes": " → ".join(shown)}}]


def grade_artifact(case, plan, workspace, agent):
    from core.artifact_builder import build_project, build_workbook
    from core.action_policy import TOOLS
    action = "create_project" if agent == "CODE" else "create_workbook"
    steps = plan.get("steps") or []
    if len(steps) != 1 or steps[0].get("action") != action or action not in TOOLS.get(agent, set()):
        return [check("Uma ferramenta permitida para o artefato", False)], [{"kind": "bloqueado", "action": action}]
    manifest = steps[0].get("params", {}).get("manifest")
    try:
        result = (build_project if agent == "CODE" else build_workbook)(manifest, root=workspace)
        artifacts = result["artifacts"]
        checks = [check("Artefato gravado e relido pelo executor", result["success"])]
        if agent == "CODE":
            import ast
            files = case["expect"]["files"]
            for name, sample in files.items():
                path = Path(artifacts["folder"]) / relative_file(name)
                content = path.read_text(encoding="utf-8") if path.is_file() else None
                checks.append(check(f"Conteúdo esperado em {name}", content is not None and sample in content))
                if path.suffix.lower() == ".py" and content is not None:
                    try:
                        parsed = ast.parse(content)
                        checks.append(check(f"Sintaxe Python em {name}", True))
                        functions = {item.name: item for item in parsed.body if isinstance(item, ast.FunctionDef)}
                        for func, expression in case["expect"].get("functions", {}).get(name, {}).items():
                            body = functions[func].body if func in functions else []
                            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                                body = body[1:]
                            expected = ast.parse(expression, mode="eval").body
                            checks.append(check(f"Contrato estático de {func}",
                                                len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None
                                                and ast.dump(body[0].value) == ast.dump(expected)))
                    except SyntaxError:
                        checks.append(check(f"Sintaxe Python em {name}", False))
        else:
            from openpyxl import load_workbook
            workbook = load_workbook(artifacts["files"][0], data_only=False, read_only=True)
            try:
                for title, cells in case["expect"]["sheets"].items():
                    checks.append(check(f"Aba {title}", title in workbook.sheetnames))
                    if title in workbook.sheetnames:
                        for address, value in cells.items():
                            actual = workbook[title][address].value
                            checks.append(check(f"Célula {title}!{address}", actual == value and (type(actual) is type(value) or
                                                type(actual) in (int, float) and type(value) in (int, float))))
            finally:
                workbook.close()
    except (OSError, ValueError, TypeError, KeyError, SyntaxError) as exc:
        return [check("Artefato aceito pelo executor", False)], [{"kind": "falha_ferramenta", "action": action, "reason": type(exc).__name__}]
    return checks, [{"kind": "executado", "action": action}]


@dataclass(frozen=True)
class Adapter:
    validate: object
    grade: object = None


ADAPTERS = {
    "FILE": Adapter(validate_file),
    "MAESTRO": Adapter(validate_route, grade_route),
    "CODE": Adapter(validate_code, lambda case, plan, root: grade_artifact(case, plan, root, "CODE")),
    "DATA": Adapter(validate_data, lambda case, plan, root: grade_artifact(case, plan, root, "DATA")),
}

DEFAULTS = (
    {"name": "maestro-rotas", "title": "Maestro: roteamento", "agent": "MAESTRO", "cases": [
        {"id": "abrir-site", "task": "Abra o YouTube", "expect": {"agents": ["WEB"]}, "split": "development", "risk": "safe"},
        {"id": "navegador", "task": "Abra o Bloco de Notas", "expect": {"agents": ["DESKTOP"]}, "split": "holdout", "risk": "safe"},
    ]},
    {"name": "codigo-artefato", "title": "Código: estrutura", "agent": "CODE", "cases": [
        {"id": "funcao-soma", "task": "Crie um arquivo soma.py com a função somar(a, b) que devolve a + b.",
         "expect": {"files": {"soma.py": "def somar("}, "functions": {"soma.py": {"somar": "a + b"}}}, "split": "development", "risk": "safe"},
        {"id": "funcao-dobro", "task": "Crie um arquivo dobro.py com a função dobro(x).",
         "expect": {"files": {"dobro.py": "def dobro("}, "functions": {"dobro.py": {"dobro": "x * 2"}}}, "split": "holdout", "risk": "safe"},
    ]},
    {"name": "dados-celulas", "title": "Dados: células e fórmulas", "agent": "DATA", "cases": [
        {"id": "soma", "task": "Crie a aba Total, coluna A1 Valor, A2 12, A3 30, A4 fórmula =SUM(A2:A3).",
         "expect": {"sheets": {"Total": {"A1": "Valor", "A2": 12, "A3": 30, "A4": "=SUM(A2:A3)"}}},
         "split": "development", "risk": "safe"},
        {"id": "media", "task": "Crie a aba Médias, A1 Valor, A2 8, A3 4, A4 fórmula =AVERAGE(A2:A3).",
         "expect": {"sheets": {"Médias": {"A1": "Valor", "A2": 8, "A3": 4, "A4": "=AVERAGE(A2:A3)"}}},
         "split": "holdout", "risk": "safe"},
    ]},
)


def validate_cases(cases, agent):
    if agent not in ADAPTERS or not isinstance(cases, list) or not 1 <= len(cases) <= 24:
        raise ValueError("selecione um agente avaliado e informe de 1 a 24 casos")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", case["id"]):
            raise ValueError("o identificador do caso deve usar letras, números, hífen ou sublinhado")
        if case["id"] in ids:
            raise ValueError("ids de casos devem ser únicos")
        ids.add(case["id"])
        if not isinstance(case.get("task"), str) or not 1 <= len(case["task"].strip()) <= 1600 or not isinstance(case.get("expect"), dict):
            raise ValueError("informe o pedido e o resultado esperado")
        if case.get("split", "development") not in ("development", "holdout") or case.get("risk", "safe") not in ("safe", "requires_approval", "prohibited"):
            raise ValueError("grupo de avaliação ou risco inválido")
        if not isinstance(case.get("context", ""), str) or len(case.get("context", "")) > 1200:
            raise ValueError("contexto sintético inválido")
        ADAPTERS[agent].validate(case)
