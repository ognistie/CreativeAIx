"""Execution-time domain authorization. Model-generated steps cannot choose their owner."""
from core.file_contracts import FIELDS, request_roots, validate

TOOLS = {
    'CODE': {'create_project', 'edit_project', 'revert_project', 'wait'},
    'DATA': {'create_workbook', 'wait'},
    'FILE': set(FIELDS) | {'wait'},
    'WEB': {'open_url', 'browser_task', 'browser_click', 'browser_read', 'web_goto', 'web_new_tab',
            'web_click', 'web_type', 'web_key', 'web_read', 'wait', 'wait_for_window', 'focus_window'},
    'DESKTOP': {'app_search', 'open_app', 'app_type', 'blank_document', 'app_task', 'open_path', 'open_in_editor',
                'close_app', 'focus_window', 'type_text', 'hotkey', 'click', 'vision_click',
                'vision_type', 'vision_analyze', 'vision_verify', 'uia_click',
                'uia_type', 'wait', 'wait_for_window', 'wait_for_element', 'screenshot'},
    # Claude Code / Codex numa pasta escolhida pela pessoa (core/coding_agents.py)
    'EXTCODE': {'ext_code_task', 'wait'},
}


# Atalhos que abrem uma superficie onde texto digitado + Enter EXECUTA (Executar, Iniciar/busca,
# menu Win+X com terminal, Gerenciador de Tarefas > Executar nova tarefa). Nenhuma rotina precisa deles.
BLOCKED_HOTKEYS = ({"win"}, {"win", "r"}, {"win", "x"}, {"win", "s"}, {"win", "q"},
                   {"ctrl", "esc"}, {"ctrl", "shift", "esc"})


def blocked_hotkey(keys) -> bool:
    from core.action_risk import norm_keys
    return set(norm_keys(keys)) in BLOCKED_HOTKEYS


def authorize(agent, task, action, params, *, file_scope=None):
    if action not in TOOLS.get(agent, set()):
        return f'Ferramenta {action} nao autorizada para {agent or "contexto ausente"}.'
    if action == 'hotkey' and blocked_hotkey((params or {}).get('keys')):
        return 'Atalho bloqueado: abre Executar/Iniciar/terminal, onde digitar executa comandos.'
    if agent == 'FILE' and action != 'wait':
        from agents.file_agent import _has_explicit_confirmation
        roots = request_roots(task) if file_scope is None else file_scope
        allow_delete = file_scope is None and _has_explicit_confirmation(task)
        return validate([{'action': action, 'params': params}], roots, allow_delete)
    if action == 'ext_code_task':
        from core.coding_agents import folder_error
        return folder_error((params or {}).get('folder'))
    return ''
