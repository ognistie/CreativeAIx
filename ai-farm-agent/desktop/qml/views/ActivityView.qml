// Atividade: o que os agentes estao fazendo e fizeram (rodando agora, precisa de voce, hoje, uso do mes e
// quando costumam trabalhar). So le o historico e a pergunta pendente (Bridge.activitySummary).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components" as C

Item {
    id: root
    property var summary: null      // nao "data": em QML e a lista de filhos de todo Item
    property bool loading: true
    signal openTask(string text)
    signal openPage(int page)

    function reload() {
        const r = JSON.parse(Bridge.activitySummary())
        summary = r.ok ? r : null
        loading = false
    }
    onVisibleChanged: if (visible) reload()
    Component.onCompleted: reload()
    Timer { interval: 5000; repeat: true; running: root.visible; onTriggered: root.reload() }

    function fmtCost(v) { return "US$ " + (v || 0).toFixed(2).replace(".", ",") }
    function fmtDur(ms) { const s = Math.round((ms || 0) / 1000); return s < 60 ? s + " s" : Math.floor(s / 60) + " min " + (s % 60) + " s" }
    readonly property var agentColors: ({ MAESTRO: C.Theme.accent, WEB: C.Theme.splashPeach, DESKTOP: C.Theme.splashOrange,
                                          CODE: C.Theme.splashLilac, DATA: C.Theme.success, FILE: C.Theme.warning, EXTCODE: C.Theme.danger })

    C.ScrollPage {
        anchors.fill: parent
        maxWidth: 1040
        spacing: 18

        C.PageHeader {
            eyebrow: "Trabalho"
            title: "Atividade"
            subtitle: "O que seus agentes estão fazendo, o que espera por você e quanto custou este mês."
        }

        // Esqueleto enquanto carrega
        GridLayout {
            visible: root.loading
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 16; rowSpacing: 16
            Repeater { model: 4; C.Skeleton { Layout.fillWidth: true; Layout.preferredHeight: 140; radius: C.Theme.r4 } }
        }

        // Linha 1: rodando agora + precisa de voce
        RowLayout {
            visible: !root.loading && root.summary !== null
            Layout.fillWidth: true
            spacing: 16

            C.GlassPanel {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                implicitHeight: 128
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 18; spacing: 8
                    C.Eyebrow { text: "Rodando agora"; dot: !!(root.summary && root.summary.running); dotColor: C.Theme.success }
                    Text {
                        Layout.fillWidth: true
                        text: root.summary && root.summary.running ? root.summary.running : "Nenhuma tarefa em andamento"
                        color: root.summary && root.summary.running ? C.Theme.textPrimary : C.Theme.textSecondary
                        font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd + 1; font.weight: Font.Medium
                        wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                    }
                    Item { Layout.fillHeight: true }
                    C.Button { text: root.summary && root.summary.running ? "Ver a tarefa" : "Nova conversa"; compact: true
                               onClicked: root.openPage(0) }
                }
            }
            C.GlassPanel {
                id: attnPanel
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                implicitHeight: 128
                readonly property var items: root.summary ? root.summary.attention : []
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 18; spacing: 8
                    C.Eyebrow { text: "Precisa de você"; dot: attnPanel.items.length > 0; dotColor: C.Theme.warning }
                    Text {
                        Layout.fillWidth: true
                        text: attnPanel.items.length ? attnPanel.items[0].text : "Nada esperando por você"
                        color: attnPanel.items.length ? C.Theme.textPrimary : C.Theme.textSecondary
                        font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd + 1; font.weight: Font.Medium
                        wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                    }
                    Item { Layout.fillHeight: true }
                    C.Button { visible: attnPanel.items.length > 0; text: "Responder"; variant: "primary"; compact: true
                               onClicked: root.openPage(0) }
                }
            }
        }

        // Linha 2: uso do mes (medidor segmentado) + quando seus agentes trabalham (mapa de calor)
        RowLayout {
            visible: !root.loading && root.summary !== null
            Layout.fillWidth: true
            spacing: 16

            C.GlassPanel {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                id: usagePanel
                implicitHeight: usageCol.implicitHeight + 36
                readonly property var u: root.summary ? root.summary.usage : null
                ColumnLayout {
                    id: usageCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 18; spacing: 12
                    C.Eyebrow { text: "Uso do mês · desde 1º de " + ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                                     "agosto", "setembro", "outubro", "novembro", "dezembro"][new Date().getMonth()] }
                    RowLayout {
                        spacing: 10
                        Text { text: usagePanel.u ? root.fmtCost(usagePanel.u.cost) : "—"
                               color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay; font.pixelSize: 34
                               font.weight: C.Theme.weightTitle; font.features: C.Theme.tabular }
                        Text { Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 6
                               text: usagePanel.u ? usagePanel.u.runs + " tarefas · " + usagePanel.u.success_rate + "% ok" : ""
                               color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1
                               font.features: C.Theme.tabular }
                    }
                    // Barra segmentada por agente. As larguras dependem da largura da barra: o Row fica dentro de um
                    // Item sem largura implicita, senao o Row realimenta o layout (laco de polish que travava a tela)
                    Item {
                        id: segBar
                        Layout.fillWidth: true
                        implicitHeight: 8
                        clip: true
                        readonly property var segs: usagePanel.u ? usagePanel.u.segments : []
                        Rectangle { visible: segBar.segs.length === 0; anchors.fill: parent; radius: 4; color: C.Theme.bgChip }
                        Row {
                            anchors.fill: parent
                            spacing: 2
                            Repeater {
                                model: segBar.segs
                                Rectangle {
                                    width: Math.max(4, (segBar.width - 2 * (segBar.segs.length - 1)) * modelData.share)
                                    height: 8; radius: 4
                                    color: root.agentColors[modelData.agent] || C.Theme.textTertiary
                                }
                            }
                        }
                    }
                    Repeater {
                        model: usagePanel.u ? usagePanel.u.segments : []
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: root.agentColors[modelData.agent] || C.Theme.textTertiary }
                            Text { text: C.Theme.agentLabel(modelData.agent); color: C.Theme.textPrimary
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
                            Item { Layout.fillWidth: true }
                            Text { text: root.fmtCost(modelData.cost); color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                   font.pixelSize: C.Theme.sizeSm + 1; font.features: C.Theme.tabular }
                            Text { text: Math.round(modelData.share * 100) + "%"; Layout.preferredWidth: 38
                                   horizontalAlignment: Text.AlignRight; color: C.Theme.textTertiary
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1; font.features: C.Theme.tabular }
                        }
                    }
                    // Custo por dia (ultimos 14 dias): rotulo e datas das pontas
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        readonly property var days: usagePanel.u ? usagePanel.u.daily : []
                        Text { text: "Custo por dia · últimos 14 dias"; color: C.Theme.textTertiary
                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                        Item { Layout.fillWidth: true }
                        Text { text: parent.days.length ? parent.days[0].day + " → hoje" : ""
                               color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                    }
                    Item {
                        id: bars
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        implicitHeight: 44
                        readonly property var days: usagePanel.u ? usagePanel.u.daily : []
                        readonly property real peak: Math.max(0.0001, ...days.map(d => d.cost))
                        Row {
                        anchors.fill: parent
                        spacing: 3
                        Repeater {
                            model: bars.days
                            Item {
                                width: (bars.width - 3 * (bars.days.length - 1)) / Math.max(1, bars.days.length)
                                height: bars.height
                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    width: parent.width; radius: 2
                                    height: Math.max(3, parent.height * modelData.cost / bars.peak)
                                    color: modelData.cost > 0 ? C.Theme.accent : C.Theme.bgChip
                                    opacity: index === bars.days.length - 1 ? 1 : 0.6
                                }
                                C.ToolTipHint { text: modelData.day + " · " + root.fmtCost(modelData.cost); shown: barHover.hovered }
                                HoverHandler { id: barHover }
                            }
                        }
                        }
                    }
                    C.KeyValue { label: "Chamadas ao modelo"; value: usagePanel.u ? "" + usagePanel.u.calls : "—"; numeric: true }
                    C.KeyValue { label: "Tokens (estimados)"; value: usagePanel.u ? (usagePanel.u.tokens / 1000).toFixed(1).replace(".", ",") + "k" : "—"; numeric: true; last: true }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: "Tarefas: pedidos executados no mês (simulações não contam). % ok: concluídos sem erro. "
                            + "Custo: o que o provedor cobrou pelas chamadas, dividido igualmente entre os agentes do plano. "
                            + "Tokens: estimativa do app a partir das chamadas."
                        color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs
                    }
                }
            }

            C.GlassPanel {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                id: heatPanel
                implicitHeight: heatCol.implicitHeight + 36
                readonly property var h: root.summary ? root.summary.heatmap : null
                ColumnLayout {
                    id: heatCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 18; spacing: 10
                    C.Eyebrow { text: "Quando seus agentes trabalham · 30 dias" }
                    Repeater {
                        model: heatPanel.h ? heatPanel.h.rows : []
                        RowLayout {
                            id: hrow
                            readonly property var cells: modelData
                            readonly property int day: index
                            Layout.fillWidth: true
                            spacing: 3
                            Text { text: heatPanel.h.weekdays[hrow.day]; Layout.preferredWidth: 28
                                   color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                            Repeater {
                                model: hrow.cells
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 12
                                    radius: 3
                                    readonly property real level: heatPanel.h.peak ? modelData / heatPanel.h.peak : 0
                                    color: modelData > 0 ? C.Theme.alpha(C.Theme.accent, 0.2 + 0.8 * level) : C.Theme.bgChip
                                    C.ToolTipHint { text: heatPanel.h.weekdays[hrow.day] + " " + index + "h · " + modelData + (modelData === 1 ? " tarefa" : " tarefas")
                                                    shown: cellHover.hovered }
                                    HoverHandler { id: cellHover }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.leftMargin: 31
                        Text { text: "0h"; color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                        Item { Layout.fillWidth: true }
                        Text { text: "12h"; color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                        Item { Layout.fillWidth: true }
                        Text { text: "23h"; color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                    }
                    // Legenda: cor = quantidade de tarefas que comecaram naquela hora (pico = cor cheia)
                    RowLayout {
                        Layout.leftMargin: 31
                        spacing: 4
                        Text { text: "menos"; color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                        Repeater {
                            model: [0, 0.25, 0.5, 0.75, 1]
                            Rectangle { width: 12; height: 12; radius: 3
                                        color: modelData === 0 ? C.Theme.bgChip : C.Theme.alpha(C.Theme.accent, 0.2 + 0.8 * modelData) }
                        }
                        Text { text: "mais · tarefas iniciadas por hora" + (heatPanel.h && heatPanel.h.peak ? " (pico: " + heatPanel.h.peak + ")" : "")
                               color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                    }
                }
            }
        }

        // Hoje: linha do tempo
        C.GlassPanel {
            visible: !root.loading && root.summary !== null
            Layout.fillWidth: true
            id: todayPanel
            implicitHeight: todayCol.implicitHeight + 36
            readonly property var items: root.summary ? root.summary.today : []
            ColumnLayout {
                id: todayCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 18; spacing: 6
                C.Eyebrow { text: "Hoje" }
                C.EmptyState {
                    visible: todayPanel.items.length === 0
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 10
                    Layout.bottomMargin: 6
                    icon: "clock"
                    title: "Nenhuma tarefa hoje"
                    text: "Peça algo na Conversa: cada tarefa aparece aqui com hora, resultado e duração."
                    action: "Nova conversa"
                    onTriggered: root.openPage(0)
                }
                Repeater {
                    model: todayPanel.items
                    RowLayout {
                        id: todayRow
                        Layout.fillWidth: true
                        spacing: 12
                        C.Enter { target: todayRow; order: index }
                        Text { text: modelData.time; Layout.preferredWidth: 44; color: C.Theme.textTertiary
                               font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeSm }
                        Rectangle { width: 8; height: 8; radius: 4; color: modelData.ok ? C.Theme.success : C.Theme.danger }
                        Text { Layout.fillWidth: true; text: modelData.task; elide: Text.ElideRight; color: C.Theme.textPrimary
                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                        Text { text: modelData.agents.map(a => C.Theme.agentLabel(a)).join(", "); color: C.Theme.textTertiary
                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                        Text { text: root.fmtDur(modelData.duration_ms); Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight
                               color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm
                               font.features: C.Theme.tabular }
                        C.IconButton { name: "refresh"; hint: "Pedir de novo"; onClicked: root.openTask(modelData.task) }
                    }
                }
            }
        }
    }
}
