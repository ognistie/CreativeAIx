"""Declarative FILE plans. No shell, Python or executable-open tool in this domain."""
import contextvars
import os
from pathlib import Path

FIELDS = {'open_path': ('path',), 'list_files': ('path',), 'find_files': ('path', 'pattern'), 'read_file': ('path',),
          'create_folder': ('path',), 'copy_file': ('source', 'destination'),
          'move_file': ('source', 'destination'), 'delete_file': ('path',)}

# Pastas que a conversa ja liberou (o Controller define por execucao, na thread dela). "abra o relatorio para
# mim" nao cita caminho: sem isto o agente de Arquivos recusava ("nao vou inferir um escopo") o arquivo que o
# proprio app tinha acabado de criar ou que estava na pasta que a pessoa citou duas falas antes.
CONVERSATION_ROOTS: contextvars.ContextVar = contextvars.ContextVar("file_conversation_roots", default=())


def conversation_roots(session) -> list:
    """Escopo da conversa = pastas que a PESSOA citou nas falas + pastas que o app criou ou abriu nela
    (projeto, pasta aberta, arquivos criados). Nunca o que um modelo descobriu lendo arquivos."""
    from core.paths import existing_prefix, extract_path, is_network_path
    found = []
    turns = getattr(session, 'turns', None)
    for turn in turns if isinstance(turns, (list, tuple)) else []:
        cited = extract_path(getattr(turn, 'said', '') or '')
        path = existing_prefix(cited) if cited else None
        if path:
            found.append(path if os.path.isdir(path) else os.path.dirname(path))
    code = getattr(session, 'code', None) or {}
    if isinstance(code, dict) and code.get('folder'):
        found.append(code['folder'])
    if isinstance(getattr(session, 'folder', None), str):
        found.append(session.folder)
    files = getattr(session, 'files', None)
    found.extend(os.path.dirname(f) for f in (files if isinstance(files, (list, tuple)) else []) if isinstance(f, str) and f)
    return sorted({os.path.realpath(p) for p in found if p and not is_network_path(p) and os.path.isdir(p)})


def request_roots(task):
    from agents.subagents import PathResolver
    from core.paths import extract_path
    roots = PathResolver().run(task).data['folders']
    explicit = extract_path(task)
    if explicit:
        roots.append(explicit)
    roots.extend(CONVERSATION_ROOTS.get())
    return sorted({os.path.realpath(p) for p in roots if p})


def validate(steps, roots, allow_delete=False):
    roots = [os.path.normcase(os.path.realpath(r)) for r in roots]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 40:
        return 'Plano FILE deve conter de 1 a 40 operacoes.'
    if not roots:
        return 'Informe a pasta ou caminho a operar; nao vou inferir um escopo.'
    for step in steps:
        if not isinstance(step, dict):
            return 'Operacao invalida.'
        action, params = step.get('action'), step.get('params')
        if action not in FIELDS or not isinstance(params, dict):
            return 'FILE aceita apenas ferramentas de arquivo declarativas.'
        if action == 'delete_file' and not allow_delete:
            return 'Exclusao requer confirmacao explicita no pedido original.'
        for key in FIELDS[action]:
            value = params.get(key)
            if not isinstance(value, str) or not value.strip():
                return f'Parametro obrigatorio: {key}.'
            if key == 'pattern':
                if '/' in value or '\\' in value or '..' in value:
                    return 'Pattern deve ser apenas um nome, sem caminho.'
                continue
            if not os.path.isabs(os.path.expanduser(os.path.expandvars(value))):
                return 'Caminhos devem ser absolutos.'
            path = os.path.normcase(os.path.realpath(os.path.expanduser(os.path.expandvars(value))))
            inside = False
            for root in roots:
                try:
                    inside = inside or os.path.commonpath([root, path]) == root
                except ValueError:
                    continue
            if not inside:
                return f'Caminho fora do escopo do pedido: {value}'
            if action in ('delete_file', 'move_file') and path in roots:
                return 'Operar a raiz inteira exige um procedimento separado; escolha arquivos internos.'
    return ''
