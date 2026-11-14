// Tela principal. Sem tarefa: saudacao + caixa de entrada + sugestoes.
// Com tarefa: o pedido, o plano do Maestro, os passos em tempo real e o
// resultado (com links para o que foi criado e o custo real).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import "../components" as C

Item {
    id: root

    // idle | running | done | failed | cancelled | clarify
    property string status: "idle"
    property string task: ""
    property string phaseMsg: ""
    property string errorMsg: ""
    property string question: ""
    property string resolvedText: ""   // como o pedido foi entendido no contexto da conversa
    property string heardText: ""      // o que o microfone ouviu (se diferente do pedido)
    property string assistantText: ""  // resposta do assistente a este pedido (como numa conversa)
    readonly property bool hasConversation: turnsModel.count > 0
    property string reportSummary: ""
    property bool wasDryRun: false
    property real progress: 0
    property int elapsedMs: 0
    property double startedAt: 0

    // Uso de API: o Bridge manda o acumulado da sessao; guardamos a base
    // no inicio da tarefa para mostrar so o desta execucao.
    property var usageNow: ({ calls: 0, tokens_est: 0, cost_usd: 0 })
    property var usageBase: ({ calls: 0, tokens_est: 0, cost_usd: 0 })
    property var finalMetrics: null
    property var artifacts: ({ folder: "", files: [], url: "" })

    readonly property bool idle: status === "idle"
    // Plano esperando aprovacao (Configuracoes > revisar o plano antes de executar)
    property var reviewSteps: []
    property string reviewSummary: ""
    property string reviewToken: ""
    property bool reviewEffect: false
    readonly property bool reviewing: reviewSteps.length > 0
    function decidePlan(ok) {
        reviewSteps = []
        Bridge.approvePlan(ok, reviewToken)
        reviewToken = ""
    }
    function decidePlanSteps(skipped) {
        reviewSteps = []
        Bridge.approvePlanSteps(reviewToken, JSON.stringify(skipped || []))
        reviewToken = ""
    }
    // Etapa para o indicador: 0 entender, 1 planejar (revisao), 2 executar, 3 concluir, 4 concluido
    readonly property int phaseIndex: status === "done" ? 4
        : (reviewing && !reviewEffect) ? 1
        : (running && progress >= 100) ? 3
        : (stepModel.count > 0 || planModel.count > 0) ? 2 : 0
    property bool executionBusy: false
    readonly property bool running: executionBusy

    ListModel { id: turnsModel }  // pedidos anteriores da conversa { said, resolved, status, summary }
    ListModel { id: planModel }
    ListModel { id: replyModel }  // falas do agente (modo voz) neste pedido
    ListModel { id: stepModel }   // { n, agent, desc, state, result, kind }

    // O mini chat (canto da tela) mostra a mesma conversa
    property alias turns: turnsModel
    property alias replies: replyModel
    property alias steps: stepModel
    property alias composer: composer

    // ── API usada pelo Main ──────────────────────────────────────────
    // Nova conversa: esquece o contexto (o que foi feito e o que ficou aberto)
    function newTask() {
        if (running) return
        turnsModel.clear()
        Bridge.newSession()
        status = "idle"
        composer.text = ""
        composer.focusInput()
    }

    // Conversa salva reaberta pela barra lateral: pedidos e respostas voltam para a tela
    function showConversation(data) {
        if (running) return
        turnsModel.clear()
        for (const t of (data.turns || [])) {
            turnsModel.append({
                said: t.said || "", resolved: t.resolved || "",
                status: t.kind === "chat" ? "done" : (t.success === false ? "failed" : "done"),
                summary: (t.reply || t.summary || "").substring(0, 400)
            })
        }
        clearCurrent()
        composer.focusInput()
        scrollSoon()
    }

    // Pedido atual vira historico e a tela fica pronta para o proximo
    function clearCurrent() {
        status = "idle"; task = ""; resolvedText = ""; heardText = ""; assistantText = ""
        errorMsg = ""; question = ""; reportSummary = ""
        planModel.clear(); stepModel.clear(); replyModel.clear()
    }

    // Papo por voz ("valeu", "oi"): mensagem propria, sem grudar no pedido anterior
    function addChat(heard, reply) {
        if (running) { replyModel.append({ text: reply }); return }
        archiveTurn()
        clearCurrent()
        turnsModel.append({ said: heard, resolved: "", status: "done", summary: reply })
        scrollSoon()
    }

    function prefill(text) {
        if (running) return
        composer.text = text
        composer.focusInput()
    }

    // O pedido que terminou vai para o topo da conversa, em forma compacta
    function archiveTurn() {
        if (idle || !task) return
        const lastReply = replyModel.count ? replyModel.get(replyModel.count - 1).text : ""
        turnsModel.append({
            said: task, resolved: resolvedText, status: status,
            summary: (assistantText || reportSummary || errorMsg || question || lastReply || "").substring(0, 400)
        })
    }

    // Agente preferido no cabecalho: "auto" deixa o Maestro escolher; "claude"/"codex" mandam o
    // pedido ao Claude Code ou ao Codex (o atalho EXTCODE le a mencao no texto)
    property string agentPreference: "auto"
    signal openPage(int page)
    // Modo Desenvolvedor (Harness > dev): saudacao, dica, atalhos e cartoes da tela inicial
    property var dev: ({ enabled: false, greeting: "", hint: "", shortcuts: [], cards: [] })
    readonly property var devShortcuts: dev && dev.enabled ? (dev.shortcuts || []) : []
    readonly property var devCards: dev && dev.enabled ? (dev.cards || []) : []
    function withAgent(text) {
        const t = text.trim()
        if (agentPreference === "auto" || /\b(claude|codex)\b/i.test(t)) return t
        return t + (agentPreference === "claude" ? " com o Claude Code" : " com o Codex")
    }

    // heard: o que o microfone ouviu, quando o pedido veio por voz
    function start(text, heard) {
        text = withAgent(text)
        archiveTurn()
        resolvedText = ""
        heardText = (heard && heard.trim().toLowerCase().replace(/[.!?,]/g, "")
                     !== text.trim().toLowerCase().replace(/[.!?,]/g, "")) ? heard : ""
        replyModel.clear()
        assistantText = ""
        task = text
        phaseMsg = "Entendendo o pedido"
        errorMsg = ""; question = ""; reportSummary = ""
        progress = 0
        elapsedMs = 0
        startedAt = Date.now()
        wasDryRun = composer.dryRun
        usageBase = usageNow
        finalMetrics = null
        artifacts = { folder: "", files: [], url: "" }
        planModel.clear()
        stepModel.clear()
        reviewSteps = []
        status = "running"
        executionBusy = true
        composer.text = ""
        Bridge.executeTask(text, composer.dryRun, composer.genReport)
    }

    // ── Formatacao ───────────────────────────────────────────────────
    function fmtDuration(ms) {
        const s = Math.round(ms / 1000)
        return s < 60 ? s + "s" : Math.floor(s / 60) + "min " + (s % 60) + "s"
    }
    function fmtTokens(n) {
        return n >= 1000 ? (n / 1000).toFixed(1).replace(".", ",") + "k" : "" + n
    }
    function fmtCost(v) { return "US$ " + (v || 0).toFixed(4).replace(".", ",") }

    function usageLine() {
        const m = finalMetrics
        const calls = m ? m.api_calls : usageNow.calls - usageBase.calls
        const tokens = m ? m.tokens_est : usageNow.tokens_est - usageBase.tokens_est
        const cost = m ? m.cost_usd : usageNow.cost_usd - usageBase.cost_usd
        const parts = [fmtDuration(elapsedMs)]
        if (calls > 0) parts.push(calls + (calls === 1 ? " chamada" : " chamadas"),
                                  fmtTokens(tokens) + " tokens", fmtCost(cost))
        return parts.join("  ·  ")
    }

    function parseAgent(desc) {
        const m = (desc || "").match(/^\[(\w+)\]\s*/)
        return m ? { agent: m[1], text: desc.substring(m[0].length) } : { agent: "", text: desc || "" }
    }

    function findStep(n) {
        for (let i = 0; i < stepModel.count; i++)
            if (stepModel.get(i).kind === "step" && stepModel.get(i).n === n) return i
        return -1
    }

    function scrollSoon() { scrollTimer.restart() }

    Timer { id: scrollTimer; interval: 30; onTriggered: transcript.scrollToEnd() }

    Timer {
        interval: 250; repeat: true; running: root.running
        onTriggered: root.elapsedMs = Date.now() - root.startedAt
    }

    // ── Eventos do backend ──────────────────────────────────────────
    Connections {
        target: Bridge

        function onPhaseChanged(json) {
            root.executionBusy = true
            const p = JSON.parse(json)
            if (p.msg) root.phaseMsg = p.msg
        }
        function onPlanReady(json) {
            const plan = JSON.parse(json).plan || {}
            planModel.clear()
            for (const s of (plan.steps || [])) {
                const a = root.parseAgent(s.description)
                planModel.append({ agent: a.agent || s.action || "", text: a.text })
            }
            root.phaseMsg = "Executando"
            root.scrollSoon()
        }
        function onStepStart(json) {
            const s = JSON.parse(json)
            const a = root.parseAgent(s.desc)
            stepModel.append({ kind: "step", n: s.step, agent: a.agent, desc: a.text,
                               state: "running", result: "" })
            root.progress = s.progress || root.progress
            root.phaseMsg = "Passo " + s.step + (s.total ? " de " + s.total : "")
            root.scrollSoon()
        }
        function onStepDone(json) {
            const s = JSON.parse(json)
            const i = root.findStep(s.step)
            const result = (s.result || "").toString().trim().substring(0, 600)
            if (i >= 0) {
                stepModel.setProperty(i, "state", s.ok ? "ok" : "fail")
                stepModel.setProperty(i, "result", result)
            } else {
                const a = root.parseAgent(s.desc)
                stepModel.append({ kind: "step", n: s.step, agent: a.agent, desc: a.text,
                                   state: s.ok ? "ok" : "fail", result: result })
            }
            root.progress = s.progress || root.progress
        }
        function onLogEntry(json) {
            // So o que o usuario precisa saber: avisos e erros que nao
            // viraram passo (ex.: "Plano falhou" de um agente).
            const e = JSON.parse(json)
            const level = (e.level || "").toUpperCase()
            const msg = e.msg || ""
            if (!root.running) return
            if (level !== "ERROR" && level !== "WARN") return
            if (msg.indexOf("Step falhou") === 0) return
            stepModel.append({ kind: "note", n: -1, agent: e.agent || "",
                               desc: msg, state: level === "ERROR" ? "fail" : "warn", result: "" })
            root.scrollSoon()
        }
        function onApiUsage(json) { root.usageNow = JSON.parse(json) }
        function onContextExtracted(json) {
            const c = JSON.parse(json)
            root.artifacts = {
                folder: c.folder || root.artifacts.folder,
                files: (c.files && c.files.length) ? c.files : root.artifacts.files,
                url: c.url || root.artifacts.url
            }
        }
        function onTaskDone(json) {
            root.progress = 100
            root.phaseMsg = "Finalizando"
        }
        function onExecutionFinished(json) {
            root.executionBusy = false
            root.reviewSteps = []
            root.reviewToken = ""
        }
        function onReportReady(json) {
            const r = JSON.parse(json).report || {}
            root.reportSummary = r.summary || ""
        }
        function onPlanReview(json) {
            const event = JSON.parse(json)
            const p = event.plan || {}
            const effectClosed = root.reviewEffect && !event.token
            root.reviewToken = event.token || ""
            root.reviewEffect = !!event.effect
            root.reviewSummary = p.summary || ""
            root.reviewSteps = p.steps || []
            if (event.effect && event.spoken_code)
                root.reviewSteps = root.reviewSteps.concat(["Por voz, diga: confirmo " + event.spoken_code])
            if (root.reviewToken) root.phaseMsg = "Aguardando sua aprovação"
            else if (effectClosed && root.running) root.phaseMsg = "Executando"
            root.scrollSoon()
        }
        function onCancelled(json) {
            root.reviewSteps = []
            root.reviewToken = ""
            if (root.status === "running") root.status = "cancelled"
        }
        function onErrorRaised(json) {
            const e = JSON.parse(json)
            composer.sending = false
            if (e.kind === "clarification") {
                root.question = e.msg || "Pode dar mais detalhes?"
                root.status = "clarify"
                composer.text = ""
                composer.focusInput()
            } else if (e.kind === "limitation") {
                // O Maestro decidiu nao cumprir como pedido (ex.: obra protegida)
                root.question = e.msg || "Nao posso fazer isso como pedido."
                root.status = "limited"
                composer.focusInput()
            } else {
                root.errorMsg = e.msg || "Erro desconhecido"
                root.status = "failed"
            }
            root.scrollSoon()
        }
        function onResolved(json) {
            const r = JSON.parse(json)
            if (r.said === root.task && r.task !== r.said) root.resolvedText = r.task
        }
        function onVoiceState(json) {
            const v = JSON.parse(json)
            if (v.state === "recording" && composer.voiceState !== "recording")
                composer.recStartedAt = Date.now()
            composer.voiceState = v.state || "idle"
            // Falha real do microfone: o composer mostra o erro com a solucao (nao so a cor)
            if (v.error) composer.errorText = "Microfone indisponível. Confira o microfone padrão do Windows (Configurações > Privacidade > Microfone) e tente de novo."
            composer.liveOn = !!v.live
            composer.queued = v.queued || 0
            if (v.hotkey) composer.voiceHotkey = v.hotkey.split("+").map(k =>
                k === "space" ? "Espaço" : k.charAt(0).toUpperCase() + k.slice(1)).join("+")
        }
        function onVoiceLevel(json) { composer.voiceLevel = JSON.parse(json).level || 0 }
        function onVoiceReply(json) {
            // O que o agente falou em voz alta aparece na conversa
            const t = JSON.parse(json).text || ""
            if (t && !root.idle) { replyModel.append({ text: t }); root.scrollSoon() }
        }
        function onAssistantMessage(json) {
            const m = JSON.parse(json)
            if (m.said === root.task) { root.assistantText = m.text || ""; root.scrollSoon() }
        }
        function onVoiceChat(json) {
            const c = JSON.parse(json)
            root.addChat(c.heard || "", c.reply || "")
        }
        function onAnswerReady(json) {
            // Pergunta sobre algo ja feito: respondida pela conversa, sem acao
            root.reportSummary = JSON.parse(json).msg || ""
        }
        function onHistoryChanged(json) {
            // Registro final: sucesso real, metricas desta execucao, artefatos.
            const entry = JSON.parse(json).entry || {}
            if (entry.task !== root.task) return
            root.finalMetrics = entry.metrics || null
            root.elapsedMs = entry.duration_ms || root.elapsedMs
            const art = entry.artifacts || {}
            root.artifacts = {
                folder: art.folder || root.artifacts.folder,
                files: (art.files && art.files.length) ? art.files : root.artifacts.files,
                url: art.url || root.artifacts.url
            }
            if (root.status === "running")
                root.status = entry.success ? "done" : "failed"
            if (root.status === "failed" && !root.errorMsg)
                root.errorMsg = entry.error || "Um ou mais passos não funcionaram."
            root.scrollSoon()
        }
    }

    // ══ Estado inicial: saudacao ════════════════════════════════════
    // Claro com foto: luz difusa atras da saudacao, sem caixa: gradiente radial liso (sem aneis) e translucido,
    // a pintura continua aparecendo. O texto da saudacao usa a tinta mais forte para ler sobre a parte escura.
    Item {
        id: heroHalo
        objectName: "heroHalo"
        visible: hero.visible && C.Theme.photoLight
        readonly property real core: 0.42
        width: hero.width + 520
        height: hero.height + 220
        x: hero.x - 260
        y: hero.y - 110
        // circulo num quadrado, esticado na horizontal: elipse com borda que some
        Shape {
            width: heroHalo.height
            height: heroHalo.height
            transform: Scale { xScale: heroHalo.width / Math.max(1, heroHalo.height) }
            ShapePath {
                strokeWidth: -1
                strokeColor: "transparent"
                fillGradient: RadialGradient {
                    centerX: heroHalo.height / 2; centerY: heroHalo.height / 2; centerRadius: heroHalo.height / 2
                    focalX: heroHalo.height / 2; focalY: heroHalo.height / 2
                    GradientStop { position: 0.0; color: Qt.rgba(0.98, 0.984, 0.98, heroHalo.core) }
                    GradientStop { position: 0.4; color: Qt.rgba(0.98, 0.984, 0.98, heroHalo.core * 0.85) }
                    GradientStop { position: 1.0; color: Qt.rgba(0.98, 0.984, 0.98, 0) }
                }
                startX: 0; startY: 0
                PathLine { x: heroHalo.height; y: 0 }
                PathLine { x: heroHalo.height; y: heroHalo.height }
                PathLine { x: 0; y: heroHalo.height }
                PathLine { x: 0; y: 0 }
            }
        }
    }
    ColumnLayout {
        id: hero
        visible: root.idle && !root.hasConversation
        width: composer.width
        x: composer.x
        y: Math.max(C.Theme.sp6, composer.y - implicitHeight - 32)
        spacing: 8

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: (root.dev && root.dev.enabled && root.dev.greeting) || "Como posso ajudar?"
            color: C.Theme.textPrimary
            font.family: C.Theme.fontDisplay
            font.pixelSize: C.Theme.sizeHero
            font.weight: C.Theme.weightTitle
            font.letterSpacing: C.Theme.tracking(C.Theme.sizeHero)
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: (root.dev && root.dev.enabled && root.dev.hint) || "Digite ou fale um pedido. O Maestro escolhe o agente certo e executa no seu computador."
            color: C.Theme.photoLight ? C.Theme.textPrimary : C.Theme.textSecondary
            font.family: C.Theme.fontSans
            font.pixelSize: C.Theme.sizeMd
            wrapMode: Text.Wrap
        }
    }

    // Sugestoes centralizadas: as pilulas sao distribuidas em linhas (medidas pelo texto) e cada linha centra
    FontMetrics { id: sugMetrics; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
    // Atalhos do modo Desenvolvedor (nivel 2) entram antes dos exemplos fixos
    readonly property var suggestionItems: root.devShortcuts.map(s => ({ i: s.icon || "sparkle", t: s.request, l: s.label })).concat([
                { i: "", t: "Crie uma planilha de gastos do mês com gráfico" },
                { i: "", t: "Pesquise no Google sobre inteligência artificial" },
                { i: "", t: "Crie um site sobre uma cafeteria artesanal" },
                { i: "", t: "Organize os arquivos da pasta Downloads por tipo" },
            ])
    function sugWidth(item) { return Math.ceil(sugMetrics.advanceWidth(item.l || item.t)) + 13 + 8 + 28 }
    readonly property var suggestionRows: {
        const rows = [], max = composer.width
        let row = [], used = 0
        for (const item of suggestionItems) {
            const w = sugWidth(item)
            if (row.length && used + 8 + w > max) { rows.push(row); row = []; used = 0 }
            used += (row.length ? 8 : 0) + w
            row.push(item)
        }
        if (row.length) rows.push(row)
        return rows
    }
    Column {
        id: suggestions
        visible: root.idle && !root.hasConversation
        x: composer.x
        width: composer.width
        y: composer.y + composer.height + 18
        spacing: 8

        Repeater {
          model: root.suggestionRows
          Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8
            Repeater {
            model: modelData
            delegate: Rectangle {
                width: root.sugWidth(modelData)
                height: 34
                radius: 17
                // Claro com foto: pilula de vidro fosco, sem contorno; nos outros casos, a pilula quieta de sempre
                color: C.Theme.photoLight ? (sugMouse.containsMouse ? C.Theme.bgGlassHi : C.Theme.alpha(C.Theme.bgGlassHi, 0.80))
                     : (sugMouse.containsMouse ? C.Theme.bgHover : C.Theme.alpha(C.Theme.bgHover, 0))
                border.width: C.Theme.photoLight ? 0 : 1
                border.color: C.Theme.hairline
                Behavior on color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                RowLayout {
                    id: sugRow
                    anchors.centerIn: parent
                    spacing: 8
                    C.Icon { name: modelData.i.length > 1 ? modelData.i : ""; glyph: modelData.i.length === 1 ? modelData.i : ""; size: 13 }
                    Text {
                        text: modelData.l || modelData.t
                        color: C.Theme.textSecondary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm + 1
                    }
                }
                MouseArea {
                    id: sugMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.prefill(modelData.t)
                }
            }
            }
          }
        }
    }

    // ══ Estado inicial: cartoes de recurso (Cerebro, Voce, Harness, Desenvolvedor) ══
    Flow {
        id: features
        visible: root.idle && !root.hasConversation
        x: composer.x
        width: composer.width
        y: suggestions.y + suggestions.height + 26
        spacing: 12
        readonly property int cardW: Math.floor((width - spacing * 3) / 4)
        Repeater {
            // Cartoes do modo Desenvolvedor (nivel 2) viram pedidos normais (page -1)
            model: [
                { n: "brain", t: "Cérebro", d: "Notas, regras e lições que guiam os agentes", page: 4 },
                { n: "user", t: "Você", d: "Quem você é e como prefere as respostas", page: 5 },
                { n: "sliders", t: "Harness", d: "Instruções por agente, aparência e versões", page: 6 },
                { n: "terminal", t: "Desenvolvedor", d: "Mude a plataforma por dentro, com segurança", page: 6 },
            ].concat(root.devCards.map(c => ({ n: c.icon || "sparkle", t: c.title, d: c.text, page: -1, request: c.request })))
            delegate: C.GlassPanel {
                id: card
                width: features.cardW
                height: 108
                raised: cardMouse.containsMouse
                // Claro com foto: cartao de vidro mais branco (como o composer), com a sombra macia do GlassPanel
                fill: C.Theme.photoLight ? (cardMouse.containsMouse ? C.Theme.bgGlassHi : C.Theme.bgGlass)
                    : (cardMouse.containsMouse ? C.Theme.bgGlassHi : C.Theme.bgGlass)
                // Entrada discreta (respeita "luzes paradas"): sobe e aparece em sequencia
                opacity: 0
                transform: Translate { id: lift; y: C.Theme.motion ? 10 : 0 }
                Component.onCompleted: enter.start()
                SequentialAnimation {
                    id: enter
                    PauseAnimation { duration: C.Theme.motion ? 80 * index : 0 }
                    ParallelAnimation {
                        NumberAnimation { target: card; property: "opacity"; to: 1; duration: C.Theme.motion ? 260 : 0 }
                        NumberAnimation { target: lift; property: "y"; to: 0; duration: C.Theme.motion ? 320 : 0; easing.type: Easing.OutCubic }
                    }
                }
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 6
                    C.Icon { name: modelData.n; size: 18; color: C.Theme.accent }
                    Text {
                        text: modelData.t
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontDisplay
                        font.pixelSize: C.Theme.sizeMd + 1
                        font.weight: C.Theme.weightTitle
                    }
                    Text {
                        Layout.fillWidth: true
                        text: modelData.d
                        color: C.Theme.textSecondary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    Item { Layout.fillHeight: true }
                }
                MouseArea {
                    id: cardMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modelData.page < 0 ? root.prefill(modelData.request) : root.openPage(modelData.page)
                }
                Accessible.role: Accessible.Button
                Accessible.name: modelData.t
            }
        }
    }

    // ══ Execucao: transcricao ═══════════════════════════════════════
    C.ScrollPage {
        id: transcript
        visible: !root.idle || root.hasConversation
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: composer.top
        anchors.bottomMargin: 8
        topPadding: 40
        bottomPadding: 16
        spacing: 20

        // Pedidos anteriores da conversa (compactos)
        Repeater {
            model: turnsModel
            delegate: PastTurn {
                Layout.fillWidth: true
                said: model.said
                status: model.status
                summary: model.summary
            }
        }

        // Pedido do usuario
        Rectangle {
            visible: !root.idle
            Layout.alignment: Qt.AlignRight
            Layout.maximumWidth: parent.width * 0.8
            implicitWidth: Math.min(taskText.implicitWidth + 32, parent.width * 0.8)
            implicitHeight: taskText.implicitHeight + 20
            radius: 18
            color: C.Theme.bgSurfaceHi
            Text {
                id: taskText
                anchors.fill: parent
                anchors.leftMargin: 16; anchors.rightMargin: 16
                anchors.topMargin: 10; anchors.bottomMargin: 10
                text: root.task
                color: C.Theme.textPrimary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd + 1
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }
        }

        // O que o microfone ouviu (pedido por voz)
        Text {
            visible: root.heardText !== ""
            Layout.alignment: Qt.AlignRight
            Layout.maximumWidth: parent.width * 0.8
            Layout.topMargin: -12
            text: "Ouvi: “" + root.heardText + "”"
            color: C.Theme.textTertiary
            font.family: C.Theme.fontSans
            font.pixelSize: C.Theme.sizeSm
            font.italic: true
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignRight
        }

        // Falas do agente (modo voz)
        Repeater {
            model: replyModel
            delegate: RowLayout {
                Layout.fillWidth: true
                spacing: 8
                C.Icon { glyph: ""; size: 12; color: C.Theme.textTertiary; Layout.alignment: Qt.AlignTop; Layout.topMargin: 2 }
                Text {
                    Layout.fillWidth: true
                    text: model.text
                    color: C.Theme.textSecondary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeMd
                    wrapMode: Text.Wrap
                }
            }
        }

        // Como o pedido foi entendido (continuacao da conversa)
        Text {
            visible: root.resolvedText !== ""
            Layout.alignment: Qt.AlignRight
            Layout.maximumWidth: parent.width * 0.8
            Layout.topMargin: -12
            text: "Entendi: " + root.resolvedText
            color: C.Theme.textTertiary
            font.family: C.Theme.fontSans
            font.pixelSize: C.Theme.sizeSm
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignRight
        }

        // Plano para aprovar: decisao por passo (Configuracoes > revisar o plano antes de executar)
        C.PlanCard {
            objectName: "planCard"
            visible: root.reviewing && !root.reviewEffect
            Layout.fillWidth: true
            steps: root.reviewEffect ? [] : root.reviewSteps
            onRun: (skipped) => root.decidePlanSteps(skipped)
            onCancelled: root.decidePlan(false)
        }
        // Efeito sensivel no meio da execucao (enviar, publicar...): confirmar ou cancelar
        C.GlassPanel {
            visible: root.reviewing && root.reviewEffect
            Layout.fillWidth: true
            implicitHeight: effCol.implicitHeight + 32
            fill: C.Theme.bgGlassHi
            ColumnLayout {
                id: effCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 16
                spacing: 8
                C.Eyebrow { text: "Confirmar ação"; dot: true; dotColor: C.Theme.warning }
                Repeater {
                    model: root.reviewEffect ? root.reviewSteps : []
                    delegate: Text {
                        Layout.fillWidth: true
                        text: modelData
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeMd
                        wrapMode: Text.Wrap
                    }
                }
                RowLayout {
                    spacing: 8
                    Layout.topMargin: 4
                    C.Button { text: "Confirmar"; variant: "primary"; compact: true; onClicked: root.decidePlan(true) }
                    C.Button { text: "Cancelar"; variant: "ghost"; compact: true; onClicked: root.decidePlan(false) }
                }
            }
        }

        // Pergunta do Maestro (ambiguidade)
        Rectangle {
            visible: root.status === "clarify" || root.status === "limited"
            Layout.fillWidth: true
            implicitHeight: qText.implicitHeight + 28
            radius: C.Theme.rMd
            color: C.Theme.alpha(C.Theme.info, 0.08)
            border.width: 1
            border.color: C.Theme.alpha(C.Theme.info, 0.25)
            Text {
                id: qText
                anchors.fill: parent
                anchors.margins: 14
                text: root.question + (root.status === "clarify"
                      ? "\n\nResponda abaixo — eu continuo o mesmo pedido."
                      : "\n\nVocê pode reformular o pedido abaixo.")
                color: C.Theme.textPrimary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd
                wrapMode: Text.Wrap
            }
        }

        // Cartao do agente: etapa, progresso, plano, passos e o que custou ate aqui
        C.GlassPanel {
            id: runCard
            visible: !root.idle && root.status !== "clarify" && root.status !== "limited"
            Layout.fillWidth: true
            implicitHeight: runCol.implicitHeight + 32
            ColumnLayout {
                id: runCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 16
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Item {
                        Layout.preferredWidth: 16; Layout.preferredHeight: 16
                        C.Spinner { anchors.centerIn: parent; visible: root.running; size: 14 }
                        C.StatusDot { anchors.centerIn: parent; visible: !root.running; size: 16; status: root.status }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: {
                            switch (root.status) {
                                case "running":   return root.phaseMsg + "..."
                                case "done":      return root.wasDryRun ? "Simulação concluída — nada foi executado" : "Tarefa concluída"
                                case "failed":    return "Não foi possível concluir"
                                case "cancelled": return "Execução interrompida"
                            }
                            return ""
                        }
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeMd
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    C.PhaseStepper {
                        visible: runCard.width > 620
                        current: root.phaseIndex
                        failed: root.status === "failed" || root.status === "cancelled"
                    }
                }

                // Barra de progresso fina
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 3
                    visible: root.running
                    radius: 2
                    color: C.Theme.bgChip
                    Rectangle {
                        width: parent.width * Math.max(0.03, Math.min(1, root.progress / 100))
                        height: parent.height
                        radius: 2
                        color: C.Theme.accent
                        Behavior on width { NumberAnimation { duration: C.Theme.dur(C.Theme.durNormal); easing.type: C.Theme.easeOut } }
                    }
                }

                // Plano
                ColumnLayout {
                    visible: planModel.count > 0
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "Plano"
                        color: C.Theme.textTertiary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm
                        font.weight: Font.Medium
                    }
                    Repeater {
                        model: planModel
                        delegate: RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Text {
                                text: (index + 1) + "."
                                color: C.Theme.textTertiary
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeMd
                                Layout.preferredWidth: 18
                                Layout.alignment: Qt.AlignTop
                            }
                            Text {
                                Layout.fillWidth: true
                                text: model.text
                                color: C.Theme.textSecondary
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeMd
                                wrapMode: Text.Wrap
                            }
                            AgentTag { agent: model.agent; Layout.alignment: Qt.AlignTop }
                        }
                    }
                }

                // Passos
                ColumnLayout {
                    visible: stepModel.count > 0
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Passos"
                        color: C.Theme.textTertiary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm
                        font.weight: Font.Medium
                        Layout.bottomMargin: 4
                    }
                    Repeater {
                        model: stepModel
                        delegate: StepRow {
                            Layout.fillWidth: true
                            desc: model.desc
                            agent: model.agent
                            status: model.state
                            result: model.result
                            kind: model.kind
                        }
                    }
                }

                // Rodape: tempo, chamadas, tokens e custo (numeros tabulares) e o botao de parar
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: C.Theme.hairline; visible: stepModel.count > 0 || planModel.count > 0 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Text {
                        Layout.fillWidth: true
                        text: root.usageLine()
                        color: C.Theme.textTertiary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm
                        font.features: C.Theme.tabular
                        elide: Text.ElideRight
                    }
                    C.Button { visible: root.running; text: "Parar"; icon: ""; compact: true; onClicked: Bridge.forceStop() }
                }
            }
        }

        // Resultado
        ColumnLayout {
            visible: !root.idle && !root.running && root.status !== "clarify"
            Layout.fillWidth: true
            spacing: 12

            Text {
                visible: root.status === "failed" && root.errorMsg !== ""
                Layout.fillWidth: true
                text: root.errorMsg
                color: C.Theme.textSecondary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd
                wrapMode: Text.Wrap
                maximumLineCount: 6
                elide: Text.ElideRight
            }

            Text {
                visible: root.assistantText !== ""
                Layout.fillWidth: true
                text: root.assistantText
                color: C.Theme.textPrimary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd + 1
                lineHeight: 1.3
                wrapMode: Text.Wrap
            }

            Text {
                visible: root.reportSummary !== ""
                Layout.fillWidth: true
                text: root.reportSummary
                color: C.Theme.textPrimary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd
                lineHeight: 1.3
                wrapMode: Text.Wrap
            }

            Flow {
                Layout.fillWidth: true
                spacing: 8
                C.Button {
                    visible: !!root.artifacts.folder
                    text: "Abrir pasta"
                    icon: ""
                    compact: true
                    onClicked: Qt.openUrlExternally("file:///" + root.artifacts.folder)
                }
                C.Button {
                    visible: !!root.artifacts.url
                    text: "Abrir link"
                    icon: ""
                    compact: true
                    onClicked: Qt.openUrlExternally(root.artifacts.url)
                }
                C.Button {
                    visible: root.status === "failed" || root.status === "cancelled"
                    text: "Tentar de novo"
                    icon: ""
                    compact: true
                    onClicked: root.start(root.task)
                }
                C.Button {
                    text: "Nova conversa"
                    icon: ""
                    variant: "ghost"
                    compact: true
                    onClicked: root.newTask()
                }
            }
        }
    }

    // ══ Caixa de entrada (centro no inicio, rodape durante a execucao) ══
    C.Composer {
        id: composer
        objectName: "composer"
        width: Math.min(C.Theme.contentMax, root.width - 48)
        x: (root.width - width) / 2
        y: (root.idle && !root.hasConversation) ? Math.round(root.height * 0.42) : root.height - height - 20
        running: root.running
        placeholder: (root.idle && !root.hasConversation) ? "Ex.: crie uma planilha de vendas do trimestre e abra no Excel"
                   : root.running ? "Executando... pressione Esc para parar"
                   : "Continue a conversa (ex.: agora abra o segundo vídeo)..."
        onSubmitted: (t) => root.start(t)
        onStopRequested: Bridge.forceStop()
        onMicClicked: Bridge.voiceRecordToggle()
        onRecordCancel: Bridge.voiceRecordCancel()
        onLiveSwitched: (on) => Bridge.setLiveConversation(on)
        Behavior on y { NumberAnimation { duration: C.Theme.dur(260); easing.type: Easing.OutCubic } }
        Component.onCompleted: focusInput()
    }

    // ── Subcomponentes locais ────────────────────────────────────────
    component AgentTag: Text {
        property string agent: ""
        visible: agent !== ""
        text: C.Theme.agentLabel(agent)
        color: C.Theme.textTertiary
        font.family: C.Theme.fontSans
        font.pixelSize: C.Theme.sizeSm
    }

    // Pedido anterior da conversa: o que foi dito + resultado em uma linha
    component PastTurn: ColumnLayout {
        id: past
        property string said: ""
        property string status: ""
        property string summary: ""
        spacing: 6
        opacity: 0.8

        Rectangle {
            Layout.alignment: Qt.AlignRight
            Layout.maximumWidth: past.width * 0.8
            implicitWidth: Math.min(pastSaid.implicitWidth + 28, past.width * 0.8)
            implicitHeight: pastSaid.implicitHeight + 16
            radius: 16
            color: C.Theme.bgSurfaceHi
            Text {
                id: pastSaid
                anchors.fill: parent
                anchors.leftMargin: 14; anchors.rightMargin: 14
                anchors.topMargin: 8; anchors.bottomMargin: 8
                text: past.said
                color: C.Theme.textPrimary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            C.StatusDot {
                Layout.alignment: Qt.AlignTop
                Layout.topMargin: 2
                size: 15
                status: past.status
            }
            Text {
                Layout.fillWidth: true
                text: past.summary !== "" ? past.summary
                      : past.status === "done" ? "Concluído"
                      : past.status === "cancelled" ? "Interrompido" : "Não concluído"
                color: C.Theme.textSecondary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeSm + 1
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
            }
        }
        Rectangle { Layout.fillWidth: true; Layout.topMargin: 6; implicitHeight: 1; color: C.Theme.hairline }
    }

    component StepRow: ColumnLayout {
        id: row
        property string desc: ""
        property string agent: ""
        property string status: "running"   // running | ok | fail | warn
        property string result: ""
        property string kind: "step"
        property bool expanded: false
        spacing: 2

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: 30
            spacing: 10

            Item {
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
                C.Spinner { anchors.centerIn: parent; visible: row.status === "running"; size: 13 }
                C.StatusDot {
                    anchors.centerIn: parent
                    visible: row.status !== "running"
                    size: 15
                    status: row.status
                }
            }
            Text {
                Layout.fillWidth: true
                text: row.desc
                color: row.kind === "note" ? C.Theme.textSecondary : C.Theme.textPrimary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd
                elide: row.expanded ? Text.ElideNone : Text.ElideRight
                wrapMode: row.expanded ? Text.Wrap : Text.NoWrap
            }
            AgentTag { agent: row.agent }
            C.Icon {
                visible: row.result !== ""
                glyph: row.expanded ? "" : ""
                size: 10
                color: C.Theme.textTertiary
            }
        }

        Text {
            visible: row.expanded && row.result !== ""
            Layout.fillWidth: true
            Layout.leftMargin: 26
            Layout.bottomMargin: 6
            text: row.result
            color: C.Theme.textSecondary
            font.family: C.Theme.fontMono
            font.pixelSize: C.Theme.sizeXs + 1
            wrapMode: Text.WrapAnywhere
            textFormat: Text.PlainText
        }

        TapHandler {
            enabled: row.result !== ""
            onTapped: row.expanded = !row.expanded
        }
        HoverHandler { cursorShape: row.result !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor }
    }
}
