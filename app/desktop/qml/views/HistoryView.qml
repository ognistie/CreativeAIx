// Historico de execucoes (desktop/data/history.jsonl): busca, filtros por estado e lista a esquerda; detalhes a
// direita com plano, passos com evidencia (registro de tarefas, via Bridge.historyDetail), resultado e metricas.
// Teclado: Tab chega na lista, setas navegam, Enter abre os detalhes. "Usar de novo" so preenche a caixa de pedido.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components" as C

Item {
    id: root
    objectName: "historyView"
    readonly property bool narrow: width < 860      // janela estreita: uma coluna, controles abaixo do titulo

    signal reuseRequested(string task)

    property var items: []
    property var stats: ({ total: 0, success_rate: 0, total_cost_usd: 0 })
    property string query: ""
    property string stateFilter: ""          // "" | ok | falhou | detalhes | simulacao
    property var current: null
    property var detail: null
    readonly property var cur: current || ({})
    readonly property string curState: current ? stateOf(current) : ""

    function stateOf(it) {
        if (it.dry_run) return "simulacao"
        if (it.error === "clarification_required" || (it.error || "").indexOf("limitation") === 0) return "detalhes"
        return it.success ? "ok" : "falhou"
    }
    readonly property var stateNames: ({ ok: "Concluída", falhou: "Falhou", detalhes: "Pediu detalhes", simulacao: "Simulação" })
    readonly property var filtered: {
        const q = query.trim().toLowerCase()
        return items.filter(it => (!q || (it.task || "").toLowerCase().indexOf(q) >= 0)
                                  && (!stateFilter || stateOf(it) === stateFilter))
    }

    function reload() {
        const data = JSON.parse(Bridge.loadHistory())
        items = data.items || []
        stats = data.stats || stats
    }
    function open(it) {
        current = it
        detail = it && it.id ? JSON.parse(Bridge.historyDetail(it.id)) : null
    }

    function fmtWhen(iso) {
        if (!iso) return ""
        const d = new Date(iso)
        const sameDay = d.toDateString() === new Date().toDateString()
        const time = d.toLocaleTimeString(Qt.locale("pt_BR"), "HH:mm")
        return sameDay ? "Hoje, " + time : d.toLocaleDateString(Qt.locale("pt_BR"), "dd/MM") + ", " + time
    }
    function fmtDuration(ms) {
        const s = Math.round((ms || 0) / 1000)
        return s < 60 ? s + " s" : Math.floor(s / 60) + " min " + (s % 60) + " s"
    }
    function fmtCost(v) { return "US$ " + (v || 0).toFixed(4).replace(".", ",") }
    function agentsOf(it) {
        const seen = []
        for (const s of (it.subtasks || [])) {
            const l = C.Theme.agentLabel(s.agent)
            if (l && seen.indexOf(l) < 0) seen.push(l)
        }
        return seen.join(", ")
    }
    function iconFor(st) { return ({ ok: "check", falhou: "alert-circle", detalhes: "help", simulacao: "eye" })[st] || "info" }
    function colorFor(st) { return ({ ok: C.Theme.success, falhou: C.Theme.danger, detalhes: C.Theme.info, simulacao: C.Theme.textTertiary })[st] || C.Theme.textTertiary }

    Component.onCompleted: reload()
    Connections {
        target: Bridge
        function onHistoryChanged(json) { root.reload() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        anchors.topMargin: 16
        spacing: 12

        // Titulo, numeros do periodo e busca alinhados
        GridLayout {
            Layout.fillWidth: true
            columns: root.narrow ? 1 : 3
            columnSpacing: 12
            rowSpacing: 8
            ColumnLayout {
                spacing: 2
                Text { text: "Histórico"; color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay
                       font.pixelSize: C.Theme.sizeXl + 6; font.weight: C.Theme.weightTitle
                       font.letterSpacing: C.Theme.tracking(C.Theme.sizeXl + 6) }
                Text { text: root.stats.total > 0
                             ? root.stats.total + " execuções · " + root.stats.success_rate.toFixed(0) + "% concluídas · " + root.fmtCost(root.stats.total_cost_usd) + " no total"
                             : "Cada pedido com o plano, os passos, o resultado e o custo real."
                       color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1
                       font.features: C.Theme.tabular }
            }
            Item { Layout.fillWidth: true; visible: !root.narrow }
            RowLayout {
                Layout.alignment: root.narrow ? Qt.AlignLeft : (Qt.AlignRight | Qt.AlignVCenter)
                spacing: 8
                C.AppField {
                    objectName: "historySearch"
                    Layout.preferredWidth: 280
                    placeholderText: "Buscar no histórico"
                    onTextChanged: root.query = text
                    Keys.onDownPressed: list.forceActiveFocus()
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: [["", "Todas"], ["ok", "Concluídas"], ["falhou", "Falharam"], ["detalhes", "Pediram detalhes"], ["simulacao", "Simulações"]]
                C.Chip { text: modelData[1]; selected: root.stateFilter === modelData[0]; onClicked: root.stateFilter = modelData[0] }
            }
            Item { Layout.fillWidth: true }
            Text { text: root.filtered.length + (root.filtered.length === 1 ? " execução" : " execuções")
                   color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm; font.features: C.Theme.tabular }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: root.narrow ? 1 : 2; columnSpacing: 16; rowSpacing: 12

            // ── Lista ─────────────────────────────────────────────
            C.GlassPanel {
                Layout.preferredWidth: root.narrow ? -1 : Math.min(460, root.width * 0.45)
                Layout.fillWidth: root.narrow
                Layout.preferredHeight: root.narrow ? Math.min(280, root.height * 0.35) : -1
                Layout.fillHeight: !root.narrow
                ListView {
                    id: list
                    objectName: "historyList"
                    anchors.fill: parent
                    anchors.margins: 8
                    clip: true
                    spacing: 1
                    model: root.filtered
                    keyNavigationEnabled: true
                    activeFocusOnTab: true
                    highlightFollowsCurrentItem: false
                    Keys.onReturnPressed: if (currentIndex >= 0) root.open(root.filtered[currentIndex])
                    Keys.onEnterPressed: if (currentIndex >= 0) root.open(root.filtered[currentIndex])
                    delegate: Rectangle {
                        id: row
                        width: ListView.view.width
                        height: rowCol.implicitHeight + 18
                        radius: C.Theme.r2
                        readonly property var it: modelData
                        readonly property string st: root.stateOf(modelData)
                        readonly property bool on: root.current === modelData
                        readonly property bool focusHere: list.activeFocus && list.currentIndex === index
                        color: on ? C.Theme.bgRowHover : (rowMouse.containsMouse ? C.Theme.bgHover : C.Theme.alpha(C.Theme.bgHover, 0))
                        border.width: focusHere ? 2 : 0
                        border.color: C.Theme.focusRing
                        Behavior on color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                        RowLayout {
                            anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 10; anchors.rightMargin: 10
                            spacing: 10
                            C.Icon { name: root.iconFor(row.st); size: 13; color: root.colorFor(row.st); Layout.alignment: Qt.AlignTop; Layout.topMargin: 3 }
                            ColumnLayout {
                                id: rowCol
                                Layout.fillWidth: true
                                spacing: 2
                                Text { Layout.fillWidth: true; text: row.it.task || ""; elide: Text.ElideRight; textFormat: Text.PlainText
                                       color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
                                       font.weight: row.on ? Font.DemiBold : Font.Normal }
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: [root.stateNames[row.st], root.fmtWhen(row.it.started_at), root.fmtDuration(row.it.duration_ms),
                                           root.agentsOf(row.it)].concat(((row.it.metrics || {}).cost_usd || 0) > 0 ? [root.fmtCost(row.it.metrics.cost_usd)] : [])
                                          .filter(x => x).join("  ·  ")
                                    color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs
                                    font.features: C.Theme.tabular
                                }
                            }
                        }
                        MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: { list.currentIndex = index; root.open(row.it) } }
                        Accessible.role: Accessible.ListItem
                        Accessible.name: (row.it.task || "") + ", " + root.stateNames[row.st]
                    }
                    C.EmptyState {
                        anchors.centerIn: parent
                        width: parent.width - 32
                        visible: list.count === 0
                        icon: "history"
                        title: root.items.length === 0 ? "Nenhuma execução ainda" : "Nada com esse filtro"
                        text: root.items.length === 0 ? "Cada pedido feito na Conversa aparece aqui com o resultado e o custo." : ""
                    }
                }
            }

            // ── Detalhes ──────────────────────────────────────────
            C.GlassPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                fill: C.Theme.bgGlassHi
                C.EmptyState {
                    anchors.centerIn: parent
                    visible: !root.current
                    icon: "list"
                    title: "Escolha uma execução"
                    text: "O plano, os passos com evidência e o resultado aparecem aqui."
                }
                C.ScrollPage {
                    anchors.fill: parent
                    visible: !!root.current
                    maxWidth: 820
                    topPadding: 20
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        C.Icon { name: root.iconFor(root.curState); size: 14; color: root.colorFor(root.curState) }
                        Text { text: root.stateNames[root.curState] || ""; color: root.colorFor(root.curState)
                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm; font.weight: Font.DemiBold }
                        Text { visible: root.current && root.current.verified === true; text: "· resultado verificado"
                               color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                        Item { Layout.fillWidth: true }
                        C.Button { objectName: "historyReuse"; text: "Usar de novo"; compact: true
                                   onClicked: root.reuseRequested(root.current.task || "") }
                    }
                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: root.cur.task || ""
                           color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay; font.pixelSize: C.Theme.sizeXl; font.weight: C.Theme.weightTitle }
                    Text { visible: !!root.cur.resolved && root.cur.resolved !== root.cur.task; Layout.fillWidth: true; wrapMode: Text.Wrap
                           text: "Entendido como: " + (root.cur.resolved || ""); textFormat: Text.PlainText
                           color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }

                    C.Eyebrow { text: "Métricas"; Layout.topMargin: 4 }
                    C.KeyValue { Layout.fillWidth: true; label: "Quando"; value: root.fmtWhen(root.cur.started_at) }
                    C.KeyValue { Layout.fillWidth: true; label: "Duração"; value: root.fmtDuration(root.cur.duration_ms); numeric: true }
                    C.KeyValue { Layout.fillWidth: true; label: "Chamadas ao modelo"; value: "" + ((root.cur.metrics || {}).api_calls || 0); numeric: true }
                    C.KeyValue { Layout.fillWidth: true; label: "Tokens (estimados)"; value: "" + ((root.cur.metrics || {}).tokens_est || 0); numeric: true }
                    C.KeyValue { Layout.fillWidth: true; label: "Custo"; value: root.fmtCost((root.cur.metrics || {}).cost_usd); numeric: true; last: true }

                    C.Eyebrow { text: "Plano"; Layout.topMargin: 6 }
                    Repeater {
                        model: root.cur.subtasks || []
                        Text { Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
                               text: (index + 1) + ". " + C.Theme.agentLabel(modelData.agent) + " — " + (modelData.task || "")
                               color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                    }
                    Text { visible: (root.cur.subtasks || []).length === 0; text: "Sem plano registrado (resposta direta ou pergunta)."
                           color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }

                    C.Eyebrow { text: "Passos e evidência"; Layout.topMargin: 6 }
                    Text { visible: !root.detail || !root.detail.ok || !root.detail.found
                           text: root.detail && !root.detail.ok ? root.detail.error : "Esta execução não tem passos no registro de tarefas."
                           color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                    Repeater {
                        model: root.detail && root.detail.ok ? root.detail.steps : []
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            C.Icon { name: modelData.ok === true ? "check" : modelData.ok === false ? "alert-circle" : "help"; size: 12
                                     color: modelData.ok === true ? C.Theme.success : modelData.ok === false ? C.Theme.danger : C.Theme.warning
                                     Layout.alignment: Qt.AlignTop; Layout.topMargin: 2 }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text { Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
                                       text: (modelData.description || modelData.action) + (modelData.ok === null ? " (sem confirmação de término)" : "")
                                       color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                Repeater {
                                    model: root.detail.evidence.filter(e => e.step === modelData.step && e.result)
                                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
                                           text: (modelData.verified ? "verificado: " : "relatado: ") + modelData.result
                                           color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                                }
                            }
                        }
                    }

                    C.Eyebrow { text: "Resultado"; Layout.topMargin: 6 }
                    Text {
                        Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
                        text: {
                            const a = root.cur.artifacts || {}
                            const parts = []
                            if (a.url) parts.push("Endereço: " + a.url)
                            if (a.folder) parts.push("Pasta: " + a.folder)
                            if ((a.files || []).length) parts.push("Arquivos: " + a.files.slice(0, 6).join(", "))
                            if (root.cur.error && root.cur.error !== "clarification_required") parts.push("Erro: " + root.cur.error)
                            return parts.join("\n") || "Sem artefato registrado."
                        }
                        color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm
                    }
                }
            }
        }
    }
}
