"""Fluxos reais da interface, fora da tela, com um Cerebro temporario (nada toca a sua pasta pessoal).

1. Papel de parede escolhido no Harness continua depois de ir para a Conversa, e fica gravado.
2. "Ver o mapa" no Cerebro abre o mapa com o grafo ja na primeira vez.
3. Confirmação de efeito encaminha somente o token da ação em espera.
4. Composer: erro com texto, digitar limpa, executando = processing; brilho de voz ouve e entende.
5. Fundo: fluxo e vidro canelado gravam; sem GPU a malha cai para as luzes.
6. Diario: salva sozinho, entra no contexto com a origem, privada sai, excluida some.
7. Biblioteca: busca por termo e ficha do tema. Paleta (Ctrl+K): vai para a tela; "Pedir" so preenche.
8. Lab: duas versoes nos mesmos casos pela tela (simulado); real sem confirmacao e recusado.
9. Historico: filtro por estado e detalhes abertos pelo teclado.
10. Teclado: Enter abre um tema da Biblioteca e Esc volta; a pilula "Conversa" so pede a troca ao app.
Imprime FLOW <nome> ok|FAIL <motivo> e sai com 1 se algum falhar. Roda no gate (tests/test_ui_flows.py).
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import PySide6
DLL_DIRECTORY = os.add_dll_directory(str(Path(PySide6.__file__).parent)) if os.name == 'nt' else None
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QObject, QUrl, QEventLoop, QTimer, QMetaObject, Q_ARG
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuickControls2 import QQuickStyle


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main():
    personal = Path(tempfile.mkdtemp(prefix='ui-flows-'))
    from core import brain as brain_mod
    brain_mod._instance = brain_mod.Brain(personal_path=str(personal))
    from desktop.bridge import Bridge
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication([])
    bridge = Bridge.__new__(Bridge)
    QObject.__init__(bridge)
    bridge._controller = SimpleNamespace(state={'running': False}, list_conversations=lambda: [],
                                         session=SimpleNamespace(id='qa-fixture'))
    bridge._running = False
    bridge._voice = bridge._window_mode = bridge._stop_hotkey = None
    from desktop import history_store
    history_store.HISTORY_FILE = ROOT / 'memory' / 'test_tmp' / 'ui-empty-history.jsonl'
    history_store.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Historico de brinquedo com tarefas de varios agentes: a Atividade desenha barras e mapa de calor de verdade
    # (com historico vazio um laco de layout das barras passou despercebido)
    from datetime import datetime, timedelta
    now = datetime.now()
    fake = []
    for i, (agents, cost, ok) in enumerate(((['CODE'], 0.40, True), (['WEB', 'DATA'], 0.25, False),
                                             (['DESKTOP'], 0.05, True), (['FILE'], 0.01, True), (['EXTCODE'], 0.0, True))):
        fake.append(json.dumps({'id': f'qa_{i}_flow', 'task': f'tarefa de teste {i}', 'started_at': (now - timedelta(hours=i * 7)).isoformat(timespec='seconds'),
                                'success': ok, 'dry_run': False, 'duration_ms': 1500,
                                'metrics': {'api_calls': 2, 'tokens_est': 400, 'cost_usd': cost},
                                'subtasks': [{'agent': a} for a in agents]}))
    history_store.HISTORY_FILE.write_text(''.join(line + '\n' for line in fake), encoding='utf-8')
    engine = QQmlApplicationEngine()
    errors = []
    engine.warnings.connect(lambda items: errors.extend(e.toString() for e in items))
    engine.rootContext().setContextProperty('Bridge', bridge)
    engine.addImportPath(str(ROOT / 'desktop' / 'qml'))
    engine.load(QUrl.fromLocalFile(str(ROOT / 'desktop' / 'qml' / 'Main.qml')))
    wait(300)
    root = engine.rootObjects()[0]
    root.setProperty('splashActive', False)
    root.show()
    wait(500)
    results = []

    # 1. Papel de parede ------------------------------------------------------
    harness = root.findChild(QObject, 'harnessView')
    root.setProperty('page', 6)
    wait(400)
    wid = 'catalog:bierstadt-storm-rocky-mountains'
    QMetaObject.invokeMethod(harness, 'patch', Q_ARG('QVariant', ['appearance', 'wallpaper']), Q_ARG('QVariant', wid))
    wait(50)
    root.setProperty('page', 0)          # sai do Harness logo depois de clicar (antes de qualquer Salvar)
    wait(700)
    saved = json.loads((personal / '.cerebro' / 'harness.json').read_text(encoding='utf-8')) \
        if (personal / '.cerebro' / 'harness.json').exists() else {}
    on_disk = saved.get('appearance', {}).get('wallpaper')
    wp_now = probe_value(engine, 'C.Theme.wallpaper')
    results.append(('wallpaper_persists', on_disk == wid and wp_now == wid,
                    f'arquivo={on_disk!r} tema={wp_now!r}'))
    # volta ao Harness e ve que continua marcado (draft recarregado do arquivo)
    root.setProperty('page', 6)
    wait(300)
    root.setProperty('page', 0)
    wait(300)
    results.append(('wallpaper_survives_revisit', probe_value(engine, 'C.Theme.wallpaper') == wid,
                    probe_value(engine, 'C.Theme.wallpaper')))

    # 2. Mapa do Cerebro ------------------------------------------------------
    brain_view = root.findChild(QObject, 'brainView')
    root.setProperty('page', 4)
    wait(400)
    first = brain_mod._instance.store.notes()[0]['rel']
    QMetaObject.invokeMethod(brain_view, 'open', Q_ARG('QVariant', first))
    brain_view.setProperty('graph', None)
    brain_view.setProperty('mode', 'mapa')     # o que o botao "Ver o mapa" faz
    wait(200)
    graph = brain_view.property('graph')
    nodes = (graph.toVariant() if hasattr(graph, 'toVariant') else graph) or {}
    results.append(('map_opens_first_click', bool(nodes) and bool((nodes or {}).get('nodes')),
                    f'graph={"vazio" if not nodes else len(nodes.get("nodes", []))}'))

    approvals = []
    bridge._controller.approve_plan = lambda decision, token: approvals.append((decision, token))
    task_view = root.findChild(QObject, 'taskView')
    bridge.planReview.emit(json.dumps({'effect': True, 'token': 'qa-effect',
                                       'plan': {'steps': ['Confirme o envio simulado.']}}))
    wait(50)
    visible = root.property('page') == 0 and task_view.property('reviewing') and task_view.property('reviewEffect')
    QMetaObject.invokeMethod(task_view, 'decidePlan', Q_ARG('QVariant', True))
    results.append(('effect_confirmation', visible and approvals == [(True, 'qa-effect')]
                    and not task_view.property('reviewing'), f'visible={visible}, approvals={len(approvals)}'))

    # Plano com decisao por passo: aprovar 1 e 3, pular 2 -> Bridge recebe so o 2 como pulado
    plan_calls = []
    bridge._controller.approve_plan = lambda decision, token, skip=None: plan_calls.append((decision, token, list(skip or [])))
    bridge.planReview.emit(json.dumps({'token': 'qa-plan', 'plan': {'summary': 'x', 'steps': [
        '[WEB] pesquisar precos', '[DATA] montar planilha', '[DESKTOP] abrir no Excel']}}))
    wait(80)
    card = root.findChild(QObject, 'planCard')
    # condicao do proprio cartao (a transcricao inteira fica oculta com a conversa ociosa da montagem de teste)
    shown = bool(card) and task_view.property('reviewing') and not task_view.property('reviewEffect')
    for i, d in ((0, 'ok'), (1, 'skip'), (2, 'ok')):
        QMetaObject.invokeMethod(card, 'decide', Q_ARG('QVariant', i), Q_ARG('QVariant', d))
    ready = card.property('decided') == 3 and card.property('approved') == 2
    QMetaObject.invokeMethod(card, 'runNow')
    wait(50)
    results.append(('plan_skip_one_step', shown and ready and plan_calls == [(True, 'qa-plan', [2])]
                    and not task_view.property('reviewing'), f'shown={shown}, ready={ready}, calls={plan_calls}'))

    # Atividade: a tela abre e mostra o resumo (historico vazio = estado vazio, sem erro)
    root.setProperty('page', 7)
    wait(400)
    activity = root.findChild(QObject, 'activityView')
    summary = activity.property('summary') if activity else None
    summary = summary.toVariant() if hasattr(summary, 'toVariant') else summary
    results.append(('activity_loads', bool(activity) and not activity.property('loading') and isinstance(summary, dict)
                    and 'usage' in summary and summary['usage']['runs'] >= 1 and len(activity.findChildren(QObject)) > 20,
                    f'loading={activity.property("loading") if activity else "?"}, filhos={len(activity.findChildren(QObject)) if activity else 0}'))

    # Composer: estados reais (erro com texto, digitar limpa o erro, executando = processing) e brilho de voz
    root.setProperty('page', 0)
    wait(200)
    composer = root.findChild(QObject, 'composer')
    glow = root.findChild(QObject, 'voiceGlow')
    composer.setProperty('errorText', 'Microfone indisponivel')
    wait(30)
    err_phase = composer.property('phase')
    composer.setProperty('text', 'nova tarefa')
    wait(30)
    cleared = composer.property('errorText') == ''
    composer.setProperty('running', True)
    wait(30)
    run_phase = composer.property('phase')
    composer.setProperty('running', False)
    composer.setProperty('voiceState', 'listening')
    composer.setProperty('voiceLevel', 0.8)
    wait(30)
    hearing = glow.property('hearing') and glow.property('lit')
    composer.setProperty('voiceState', 'thinking')
    wait(30)
    processing = glow.property('processing') and not glow.property('hearing')
    composer.setProperty('voiceState', 'idle')
    composer.setProperty('text', '')
    wait(30)
    results.append(('composer_states', err_phase == 'error' and cleared and run_phase == 'processing' and hearing
                    and processing and not glow.property('lit'),
                    f'erro={err_phase}, limpou={cleared}, exec={run_phase}, ouvindo={hearing}, entendendo={processing}'))

    # Fundo: fluxo e vidro canelado gravam; sem GPU (smoke por software) a malha cai para as luzes
    root.setProperty('page', 6)
    wait(300)
    QMetaObject.invokeMethod(harness, 'patch', Q_ARG('QVariant', ['appearance', 'wallpaper']), Q_ARG('QVariant', ''))
    QMetaObject.invokeMethod(harness, 'patch', Q_ARG('QVariant', ['appearance', 'flow']), Q_ARG('QVariant', 'normal'))
    QMetaObject.invokeMethod(harness, 'patch', Q_ARG('QVariant', ['appearance', 'fluted']), Q_ARG('QVariant', True))
    wait(50)
    root.setProperty('page', 0)
    wait(700)
    saved = json.loads((personal / '.cerebro' / 'harness.json').read_text(encoding='utf-8'))
    app_saved = saved.get('appearance', {})
    mesh_layer = root.findChild(QObject, 'meshLayer')
    fluted_layer = root.findChild(QObject, 'flutedLayer')
    fallback = mesh_layer is not None and not mesh_layer.property('active') and not fluted_layer.property('active')
    results.append(('background_settings', app_saved.get('flow') == 'normal' and app_saved.get('fluted') is True
                    and probe_value(engine, 'C.Theme.flowSpeed') == 1.0 and fallback,
                    f'arquivo={app_saved.get("flow")}/{app_saved.get("fluted")}, sem_gpu_cai_para_luzes={fallback}'))

    # Diario: escrever -> salva sozinho -> com a integracao ligada entra no contexto com a origem ->
    # privada sai do contexto -> excluida sai do disco. Tudo pela tela e pela Bridge, com o Cerebro temporario.
    root.setProperty('page', 8)
    wait(300)
    journal = root.findChild(QObject, 'journalView')
    QMetaObject.invokeMethod(journal, 'openFolder', Q_ARG('QVariant', 'notas'), Q_ARG('QVariant', True))
    root.findChild(QObject, 'journalTitle').setProperty('text', 'Plano da estufa')
    root.findChild(QObject, 'journalBody').setProperty('text', '! Medir a umidade da estufa 7 toda manha')
    wait(1200)                                             # salvamento automatico (800 ms parado)
    saved_state = root.findChild(QObject, 'journalSaveState').property('text')
    entry = journal.property('entry')
    entry = entry.toVariant() if hasattr(entry, 'toVariant') else entry
    bridge.journalUseInBrain(True)
    brain = brain_mod._instance
    ctx = brain.context_for('DATA', 'umidade da estufa 7')
    cited = 'Medir a umidade da estufa 7' in ctx and any(x.startswith('Diário/') for x in brain.last_sources.get('DATA', []))
    bridge.journalSetPrivate(entry['id'], True)
    hidden = 'estufa 7' not in brain.context_for('DATA', 'umidade da estufa 7')
    bridge.journalDelete(entry['id'])
    gone = brain.journal.get(entry['id']) is None and not brain.journal.list()
    results.append(('diary_cycle', saved_state.startswith('Salvo') and cited and hidden and gone,
                    f'estado={saved_state!r}, citado={cited}, privado_fora={hidden}, excluido={gone}'))

    # Biblioteca: buscar um termo tecnico acha o tema; abrir pelo id mostra a ficha com leituras
    root.setProperty('page', 9)
    wait(300)
    library = root.findChild(QObject, 'libraryView')
    root.findChild(QObject, 'librarySearch').setProperty('text', 'circuit')
    wait(100)
    found = [t['id'] for t in (library.property('items').toVariant() if hasattr(library.property('items'), 'toVariant') else library.property('items'))]
    QMetaObject.invokeMethod(library, 'openTopic', Q_ARG('QVariant', 'harness'))
    cur = library.property('current')
    cur = cur.toVariant() if hasattr(cur, 'toVariant') else cur
    results.append(('library_search', found == ['interpretability'] and cur['id'] == 'harness' and len(cur['readings']) >= 2,
                    f'busca={found}, aberto={cur.get("id")}'))

    # Paleta (Ctrl+K): buscar "biblio" e Enter leva para a Biblioteca; "Pedir" so preenche a caixa
    root.setProperty('page', 0)
    wait(100)
    palette = root.findChild(QObject, 'commandPalette')
    QMetaObject.invokeMethod(palette, 'open')
    wait(150)
    root.findChild(QObject, 'paletteField').setProperty('text', 'biblio')
    wait(50)
    QMetaObject.invokeMethod(palette, 'run', Q_ARG('QVariant', 0))
    wait(150)
    went = root.property('page') == 9
    QMetaObject.invokeMethod(palette, 'open')
    wait(150)
    root.findChild(QObject, 'paletteField').setProperty('text', 'planilha de testes')
    wait(50)
    items = palette.property('results')
    items = items.toVariant() if hasattr(items, 'toVariant') else items
    ask = len(items) - 1
    QMetaObject.invokeMethod(palette, 'run', Q_ARG('QVariant', ask))
    wait(150)
    composer = root.findChild(QObject, 'composer')
    prefilled = root.property('page') == 0 and composer.property('text') == 'planilha de testes' \
        and not task_view.property('running')
    composer.setProperty('text', '')
    results.append(('command_palette', went and prefilled and items[ask]['kind'] == 'ask',
                    f'biblioteca={went}, preencheu_sem_executar={prefilled}'))

    # AI Research Lab: duas versoes nos mesmos casos pela tela (modo simulado = replay do plano gravado);
    # o modo real sem confirmacao e recusado pela Bridge (nao so pela tela)
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_lab import good_planner
    from core.lab import get_lab
    lab = get_lab(brain_mod._instance.store.personal)
    v1 = lab.versions('FILE', brain_mod._instance.harness)[0]
    v2 = lab.create_variant('FILE', v1['id'], 'Confira o destino antes de copiar.', {'effort': 'low'}, note='teste')
    lab.run('arquivos-basico', [v1['id'], v2['id']], good_planner, origin='real')     # gravacao para o replay
    root.setProperty('page', 10)
    wait(400)
    lab_view = root.findChild(QObject, 'labView')
    lab_view.setProperty('versionA', v1['id'])
    lab_view.setProperty('versionB', v2['id'])
    QMetaObject.invokeMethod(lab_view, 'start', Q_ARG('QVariant', False))
    for _ in range(50):
        wait(100)
        if not lab_view.property('busy'):
            break
    run = lab_view.property('run')
    run = run.toVariant() if hasattr(run, 'toVariant') else run
    summary = (run or {}).get('summary', {})
    sim_ok = bool(run) and run.get('origin') == 'simulado' and all(summary.get(v, {}).get('passed') == 4 for v in (v1['id'], v2['id']))
    refused = json.loads(bridge.labRun(json.dumps({'set': 'arquivos-basico', 'versions': [v1['id']], 'mode': 'real',
                                                   'confirmed': False, 'budget': 0.5})))
    results.append(('lab_experiment', sim_ok and refused['ok'] is False and 'confirma' in refused['error'],
                    f'simulado={sim_ok}, real_sem_confirmacao_recusado={refused.get("ok") is False}'))

    # Historico: filtro por estado e detalhes abertos pelo teclado (Enter na lista)
    root.setProperty('page', 1)
    wait(300)
    hist = root.findChild(QObject, 'historyView')
    QMetaObject.invokeMethod(hist, 'reload')
    hist.setProperty('stateFilter', 'falhou')
    wait(100)
    only_failed = hist.property('filtered')
    only_failed = only_failed.toVariant() if hasattr(only_failed, 'toVariant') else only_failed
    hlist = root.findChild(QObject, 'historyList')
    hlist.forceActiveFocus()
    hlist.setProperty('currentIndex', 0)
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent, Qt as _Qt
    app.sendEvent(hlist, QKeyEvent(QEvent.KeyPress, _Qt.Key_Return, _Qt.NoModifier))
    wait(100)
    cur = hist.property('current')
    cur = cur.toVariant() if hasattr(cur, 'toVariant') else cur
    det = hist.property('detail')
    det = det.toVariant() if hasattr(det, 'toVariant') else det
    results.append(('history_filter_detail', len(only_failed) == 1 and bool(cur) and cur.get('success') is False
                    and isinstance(det, dict) and det.get('ok') is True,
                    f'falharam={len(only_failed)}, aberto_pelo_teclado={bool(cur)}, detalhe={det.get("ok") if isinstance(det, dict) else det}'))

    # Teclado: chip com foco + Espaco aciona; a pilula "Conversa" pelo teclado so PEDE a troca (estado vem do app)
    root.setProperty('page', 9)
    wait(200)
    lib = root.findChild(QObject, 'libraryView')
    root.findChild(QObject, 'librarySearch').setProperty('text', '')   # o fluxo anterior deixou uma busca
    lib.setProperty('level', '')
    lib.setProperty('current', None)
    QMetaObject.invokeMethod(lib, 'reload')
    wait(100)
    grid = root.findChild(QObject, 'libraryGrid')
    grid.forceActiveFocus()
    grid.setProperty('currentIndex', 0)
    wait(50)
    from PySide6.QtGui import QKeyEvent as _KE
    from PySide6.QtCore import QEvent as _EV, Qt as _Q
    app.sendEvent(grid, _KE(_EV.KeyPress, _Q.Key_Return, _Q.NoModifier))
    wait(100)
    opened = lib.property('current')
    opened = opened.toVariant() if hasattr(opened, 'toVariant') else opened
    app.sendEvent(lib, _KE(_EV.KeyPress, _Q.Key_Escape, _Q.NoModifier))
    wait(100)
    by_key = bool(opened) and opened.get('id') == 'harness' and lib.property('current') is None
    # A pilula vai ate a Bridge (TaskView -> Bridge.setLiveConversation). Aqui o slot so registra: o de verdade
    # liga a conversa ao vivo (microfone e threads de audio), e isso derrubava o processo ao encerrar.
    from desktop.bridge import Bridge as _Bridge
    live_calls = []
    real_live = _Bridge.setLiveConversation
    _Bridge.setLiveConversation = lambda self, on: live_calls.append(on)
    try:
        root.setProperty('page', 0)
        wait(150)
        composer = root.findChild(QObject, 'composer')
        pill = next((o for o in composer.findChildren(QObject) if o.property('text') == 'Conversa' and o.property('manual') is True), None)
        if pill is not None:
            pill.forceActiveFocus()
            wait(50)
            app.sendEvent(pill, _KE(_EV.KeyPress, _Q.Key_Return, _Q.NoModifier))
            wait(50)
        pill_ok = pill is not None and live_calls == [True] and pill.property('checked') is False
    finally:
        _Bridge.setLiveConversation = real_live
    results.append(('keyboard_controls', bool(by_key) and pill_ok,
                    f'biblioteca_enter_esc={bool(by_key)}, pilula_pede_troca={live_calls}, estado_nao_virou_sozinho={pill is not None and pill.property("checked") is False}'))

    failed = False
    for name, ok, why in results:
        print(f'FLOW {name} {"ok" if ok else "FAIL"} {why}')
        failed |= not ok
    if errors:
        print('\n'.join(errors))
    # Encerramento em ordem: janelas, depois o motor QML, depois o app. Deixar o Python destruir tudo sozinho
    # na saida (ordem arbitraria) derrubava o processo de vez em quando com 0xC0000005, depois dos fluxos.
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    for window in app.topLevelWindows():
        window.close()
    for obj in engine.rootObjects():
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    del engine, root
    gc.collect()
    return 1 if failed or errors else 0


def probe_value(engine, expr):
    comp = QQmlComponent(engine)
    comp.setData(('import QtQuick\nimport "components" as C\nQtObject { property var v: ' + expr + ' }').encode(),
                 QUrl.fromLocalFile(str(ROOT / 'desktop' / 'qml' / 'probe.qml')))
    obj = comp.create()
    return obj.property('v') if obj is not None else comp.errorString()


if __name__ == '__main__':
    raise SystemExit(main())
