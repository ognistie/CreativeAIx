// AI Research Lab: uma tela, tres passos. (1) Versoes do agente: a publicada e as variantes, com "Nova versao".
// (2) Comparar: a publicada (A) contra uma variante (B), nos mesmos casos, em modo simulado ou real.
// (3) Resultado: caso a caso, conferido no disco; abrir um caso mostra o trace; "Promover" so com evidencia real.
// Dados de core/lab.py via Bridge.lab*. Codigo fica no Harness > Desenvolvedor; passos e evidencia no Historico.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components" as C

Item {
    id: root
    objectName: "labView"
    readonly property bool narrow: width < 900

    property string agent: "FILE"
    property var versions: []
    property var effective: ({})
    property var sets: []
    property var run: null
    property var caseOpen: null
    property string versionA: ""
    property string versionB: ""
    property string mode: "simulado"
    property bool busy: false
    property var progress: []
    property string message: ""
    property var promo: null
    property bool creating: false
    property bool loaded: false

    readonly property var agents: [["FILE", "Arquivos"], ["DATA", "Dados"], ["WEB", "Web"], ["CODE", "Código"],
                                   ["DESKTOP", "Desktop"], ["EXTCODE", "Claude / Codex"], ["MAESTRO", "Maestro"]]
    readonly property bool testable: agent === "FILE"      // so Arquivos tem casos conferiveis no disco hoje
    readonly property var statusNames: ({ passou: "Passou", falhou: "Falhou", falha_ferramenta: "Falha da ferramenta",
                                          falha_planejamento: "Falha no plano", indisponivel: "Indisponível",
                                          cancelado: "Cancelado" })
    readonly property var published: versions.find(v => v.published) || null

    function call(json) { const r = JSON.parse(json); if (r.ok === false) message = r.error || "Não deu certo."; return r }
    function loadVersions() {
        const r = call(Bridge.labVersions(agent))
        if (!r.ok) return
        versions = r.versions; effective = r.effective
        versionA = published ? published.id : (versions.length ? versions[0].id : "")
        if (!versions.find(v => v.id === versionB) || versionB === versionA) {
            const other = versions.filter(v => v.id !== versionA)
            versionB = other.length ? other[other.length - 1].id : ""
        }
        promo = null
    }
    function loadAll() {
        message = ""
        loadVersions()
        const s = call(Bridge.labEvalSets()); if (s.ok) sets = s.sets
        const r = call(Bridge.labRuns()); if (r.ok && r.runs.length && !run) { const d = call(Bridge.labRunDetail(r.runs[0].id)); if (d.ok) run = d.run }
        loaded = true
    }
    function start(confirmed) {
        const vs = [versionA, versionB].filter((v, i, a) => v && a.indexOf(v) === i)
        const r = call(Bridge.labRun(JSON.stringify({ set: sets.length ? sets[0].name : "", versions: vs, mode: mode,
                                                      confirmed: confirmed, budget: parseFloat(budgetField.text.replace(",", ".")) || 0 })))
        if (r.ok) { busy = true; progress = []; message = ""; caseOpen = null; promo = null }
    }
    function checkPromo() { if (versionB) { const r = call(Bridge.labPromotionCheck(versionB)); if (r.ok !== undefined) promo = r } }
    function label(id) { const v = versions.find(x => x.id === id); return v ? "v" + v.n : id }
    function money(v) { return "US$ " + (v || 0).toFixed(3).replace(".", ",") }

    onVisibleChanged: if (visible && !loaded) loadAll()
    onAgentChanged: if (loaded) { loadVersions(); creating = false }
    Connections {
        target: Bridge
        function onLabProgress(json) { root.progress = root.progress.concat([JSON.parse(json)]) }
        function onLabFinished(json) {
            const r = JSON.parse(json)
            root.busy = false
            if (!r.ok) { root.message = r.error; return }
            root.run = r.run
            root.checkPromo()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        anchors.topMargin: 16
        spacing: 14

        // Titulo e agente
        GridLayout {
            Layout.fillWidth: true
            columns: root.narrow ? 1 : 2
            columnSpacing: 16
            rowSpacing: 8
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: "AI Research Lab"; color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay
                       font.pixelSize: C.Theme.sizeXl + 6; font.weight: C.Theme.weightTitle
                       font.letterSpacing: C.Theme.tracking(C.Theme.sizeXl + 6) }
                Text { Layout.fillWidth: true; wrapMode: Text.Wrap
                       text: "Mude as instruções de um agente numa versão separada, compare com a atual nos mesmos casos e só publique se melhorar."
                       color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
            }
            // Agente em teste: botao com menu no estilo do app (nada de caixa nativa destoando)
            C.Button {
                objectName: "labAgent"
                Layout.alignment: Qt.AlignRight | Qt.AlignTop
                text: "Agente: " + root.agents.find(a => a[0] === root.agent)[1] + "  ▾"
                compact: true
                onClicked: agentMenu.popup()
                C.AppMenu {
                    id: agentMenu
                    Instantiator {
                        model: root.agents
                        delegate: C.AppMenuItem { text: modelData[1]; iconName: modelData[0] === root.agent ? "check" : ""
                                                  onTriggered: root.agent = modelData[0] }
                        onObjectAdded: (i, o) => agentMenu.insertItem(i, o)
                        onObjectRemoved: (i, o) => agentMenu.removeItem(o)
                    }
                }
            }
        }
        Text { visible: root.message !== ""; text: root.message; color: C.Theme.danger; wrapMode: Text.Wrap; Layout.fillWidth: true
               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: root.narrow ? 1 : 2
            columnSpacing: 16
            rowSpacing: 12

            // ── 1. Versoes ────────────────────────────────────────
            C.GlassPanel {
                Layout.preferredWidth: root.narrow ? -1 : 300
                Layout.fillWidth: root.narrow
                Layout.preferredHeight: root.narrow ? Math.min(300, root.height * 0.4) : -1
                Layout.fillHeight: !root.narrow
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "1  Versões"; Layout.fillWidth: true; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                               font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                        C.Button { text: root.creating ? "Fechar" : "Nova versão"; compact: true; icon: root.creating ? "" : "plus"
                                   onClicked: root.creating = !root.creating }
                    }
                    // Nova versao: instrucoes + esforco (o resto herda da publicada)
                    ColumnLayout {
                        visible: root.creating
                        Layout.fillWidth: true
                        spacing: 6
                        Rectangle {
                            Layout.fillWidth: true; implicitHeight: 96; radius: C.Theme.r2; color: C.Theme.bgSurface
                            border.width: 1; border.color: instr.activeFocus ? C.Theme.focusRing : C.Theme.hairlineHi
                            ScrollView { anchors.fill: parent; anchors.margins: 6
                                TextArea { id: instr; placeholderText: "Instruções desta versão (ex.: confira o destino antes de copiar)"
                                           wrapMode: TextArea.Wrap; background: null; color: C.Theme.textPrimary
                                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 } }
                        }
                        RowLayout {
                            spacing: 4
                            Text { text: "Esforço"; color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                            Repeater { model: [["", "Igual"], ["low", "Baixo"], ["medium", "Médio"], ["high", "Alto"]]
                                       C.Chip { text: modelData[1]; selected: effortPick.v === modelData[0]; onClicked: effortPick.v = modelData[0] } }
                            QtObject { id: effortPick; property string v: "" }
                        }
                        C.Button {
                            text: "Criar versão"; variant: "primary"; compact: true; enabled: instr.text.trim() !== ""
                            onClicked: {
                                const r = root.call(Bridge.labCreateVariant(JSON.stringify({ agent: root.agent, base: root.versionA,
                                                    instructions: instr.text, params: effortPick.v ? { effort: effortPick.v } : {}, note: instr.text.slice(0, 60) })))
                                if (r.ok) { instr.text = ""; effortPick.v = ""; root.creating = false; root.versionB = r.version.id; root.loadVersions() }
                            }
                        }
                    }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 2
                        model: root.versions
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: vCol.implicitHeight + 16
                            radius: C.Theme.r2
                            readonly property bool isB: modelData.id === root.versionB
                            color: isB ? C.Theme.bgRowHover : (vMouse.containsMouse ? C.Theme.bgHover : C.Theme.alpha(C.Theme.bgHover, 0))
                            ColumnLayout {
                                id: vCol
                                anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 10; anchors.rightMargin: 10
                                spacing: 2
                                RowLayout {
                                    spacing: 6
                                    Text { text: "v" + modelData.n; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                           font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                                    Text { visible: modelData.published; text: "publicada · A"; color: C.Theme.success
                                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                                    Text { visible: parent.parent.parent.isB; text: "comparando · B"; color: C.Theme.accent
                                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                                }
                                Text { Layout.fillWidth: true; elide: Text.ElideRight
                                       text: (modelData.instructions || "sem instruções próprias") + (modelData.params && modelData.params.effort ? " · esforço " + (({ low: "baixo", medium: "médio", high: "alto" })[modelData.params.effort] || modelData.params.effort) : "")
                                       color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                            }
                            MouseArea { id: vMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        enabled: !modelData.published; onClicked: { root.versionB = modelData.id; root.promo = null } }
                            Accessible.role: Accessible.ListItem
                            Accessible.name: "Versão " + modelData.n + (modelData.published ? ", publicada" : "")
                        }
                    }
                }
            }

            // ── 2 e 3. Comparar e resultado ───────────────────────
            C.GlassPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                fill: C.Theme.bgGlassHi
                C.ScrollPage {
                    anchors.fill: parent
                    maxWidth: 900
                    topPadding: 16
                    spacing: 12

                    Text { text: "2  Comparar"; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                           font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                    Text {
                        Layout.fillWidth: true; wrapMode: Text.Wrap
                        visible: !root.testable
                        text: "Para " + root.agents.find(a => a[0] === root.agent)[1] + " dá para criar e publicar versões, mas ainda não há casos que confiram o resultado no disco. Hoje a comparação roda só com o agente de Arquivos."
                        color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm
                    }
                    RowLayout {
                        visible: root.testable
                        Layout.fillWidth: true
                        spacing: 10
                        Text { text: root.versionA ? root.label(root.versionA) + " (publicada)" : "—"; color: C.Theme.textPrimary
                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                        Text { text: "×"; color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                        Text { text: root.versionB ? root.label(root.versionB) : "escolha uma versão à esquerda"
                               color: root.versionB ? C.Theme.accent : C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                        Item { Layout.fillWidth: true }
                        Text { text: root.sets.length ? root.sets[0].cases.length + " casos de arquivos" : ""; color: C.Theme.textTertiary
                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                    }
                    RowLayout {
                        visible: root.testable
                        spacing: 8
                        C.Chip { objectName: "labModeSim"; text: "Simulado"; selected: root.mode === "simulado"; onClicked: root.mode = "simulado" }
                        C.Chip { objectName: "labModeReal"; text: "Real (custa)"; selected: root.mode === "real"; onClicked: root.mode = "real" }
                        Text { visible: root.mode === "real"; text: "até US$"; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                        C.AppField { id: budgetField; visible: root.mode === "real"; Layout.preferredWidth: 70; text: "0,50" }
                        Item { width: 8 }
                        C.Button {
                            objectName: "labRunButton"
                            text: root.busy ? "Rodando " + root.progress.length + "…" : "Rodar"
                            variant: "primary"; compact: true
                            enabled: !root.busy && root.versionA !== ""
                            onClicked: root.mode === "real" ? confirmReal.open() : root.start(false)
                        }
                        C.Button { visible: root.busy; text: "Parar"; compact: true; onClicked: Bridge.labCancel() }
                    }
                    Text { visible: root.testable; Layout.fillWidth: true; wrapMode: Text.Wrap
                           text: root.mode === "simulado" ? "Simulado: repete o último plano real gravado de cada caso, sem custo. Caso sem gravação aparece como indisponível."
                                                         : "Real: chama o modelo para cada caso e para quando o orçamento acaba. Tudo roda numa pasta temporária."
                           color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }

                    // 3. Resultado
                    Rectangle { visible: !!root.run; Layout.fillWidth: true; Layout.topMargin: 6; implicitHeight: 1; color: C.Theme.hairline }
                    Text { visible: !!root.run; text: "3  Resultado"; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                           font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                    C.EmptyState {
                        visible: !root.run && root.testable
                        Layout.alignment: Qt.AlignHCenter
                        icon: "flask"
                        title: "Ainda sem comparação"
                        text: "Crie uma versão, escolha-a à esquerda e clique em Rodar."
                    }
                    // Resumo por versao: uma linha cada
                    Repeater {
                        model: root.run ? root.run.versions : []
                        RowLayout {
                            readonly property var s: root.run.summary[modelData]
                            Layout.fillWidth: true
                            spacing: 14
                            Text { text: root.label(modelData); Layout.preferredWidth: 40; color: C.Theme.textPrimary
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                            Text { text: s.passed + " de " + s.cases + " passaram"; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                   font.pixelSize: C.Theme.sizeSm; font.features: C.Theme.tabular }
                            Text { text: root.money(s.cost_usd) + " · " + (s.latency_ms_avg !== null ? (s.latency_ms_avg / 1000).toFixed(1).replace(".", ",") + " s por caso" : "—")
                                   color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm; font.features: C.Theme.tabular }
                            Item { Layout.fillWidth: true }
                            Text { text: s.origin === "real" ? "medido com o modelo" : "simulado"; color: C.Theme.textTertiary
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                        }
                    }
                    // Tabela caso a caso (clique abre o detalhe logo abaixo)
                    Repeater {
                        model: {
                            if (!root.run) return []
                            const cases = []
                            root.run.results.forEach(r => { if (cases.indexOf(r.case) < 0) cases.push(r.case) })
                            return cases
                        }
                        Rectangle {
                            readonly property var rowA: root.run.results.find(r => r.case === modelData && r.version === root.run.versions[0])
                            readonly property var rowB: root.run.versions.length > 1 ? root.run.results.find(r => r.case === modelData && r.version === root.run.versions[1]) : null
                            Layout.fillWidth: true
                            implicitHeight: 34
                            radius: C.Theme.r2
                            color: caseMouse.containsMouse ? C.Theme.bgHover : C.Theme.alpha(C.Theme.bgHover, 0)
                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 12
                                Text { text: modelData; Layout.fillWidth: true; color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                Repeater {
                                    model: [parent.parent.rowA, parent.parent.rowB].filter(x => x)
                                    Text { Layout.preferredWidth: 150; horizontalAlignment: Text.AlignRight
                                           text: root.label(modelData.version) + " · " + (root.statusNames[modelData.status] || modelData.status)
                                           color: modelData.status === "passou" ? C.Theme.success
                                                : (modelData.status === "cancelado" || modelData.status === "indisponivel") ? C.Theme.textTertiary : C.Theme.danger
                                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                }
                            }
                            MouseArea { id: caseMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: root.caseOpen = (parent.rowB || parent.rowA) }
                        }
                    }
                    // Detalhe do caso: o que o agente fez e o que foi conferido no disco
                    ColumnLayout {
                        visible: !!root.caseOpen
                        Layout.fillWidth: true
                        spacing: 4
                        Text { text: root.caseOpen ? "Detalhe · " + root.caseOpen.case + " · " + root.label(root.caseOpen.version) : ""
                               color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm; font.weight: Font.DemiBold }
                        Repeater {
                            model: root.caseOpen ? root.caseOpen.trace.filter(t => t.kind !== "planejado") : []
                            Text {
                                Layout.fillWidth: true; wrapMode: Text.Wrap
                                text: modelData.kind === "verificado"
                                      ? modelData.checks.map(c => (c.ok ? "✓ " : "✗ ") + c.check).join("    ")
                                      : (modelData.kind === "bloqueado" ? "bloqueado pelo executor: " : modelData.kind === "falha_ferramenta" ? "falhou: " : "")
                                        + (modelData.action || "") + " " + Object.keys(modelData.params || {}).map(k => k + "=" + modelData.params[k]).join(", ")
                                        + (modelData.reason ? " (" + modelData.reason + ")" : "")
                                color: modelData.kind === "bloqueado" || modelData.kind === "falha_ferramenta" ? C.Theme.warning : C.Theme.textSecondary
                                font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs
                            }
                        }
                    }
                    // Promover: so com evidencia real e sem piorar
                    RowLayout {
                        visible: !!root.run && !!root.versionB
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        spacing: 10
                        C.Button { objectName: "labPromote"; text: "Promover " + root.label(root.versionB); variant: "primary"; compact: true
                                   enabled: !!root.promo && root.promo.ok === true
                                   onClicked: publishDialog.open() }
                        Text { Layout.fillWidth: true; wrapMode: Text.Wrap
                               text: !root.promo ? "" : root.promo.ok ? "Pode promover: não piorou em nenhum caso no teste real."
                                                                     : "Para promover: " + (root.promo.reasons || []).join("; ") + "."
                               color: root.promo && root.promo.ok ? C.Theme.success : C.Theme.textTertiary
                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                    }
                }
            }
        }
    }

    C.AppDialog {
        id: confirmReal
        title: "Rodar com o modelo de verdade?"
        acceptText: "Rodar"
        anchors.centerIn: parent
        Text {
            width: 360; wrapMode: Text.Wrap; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
            text: {
                const n = (root.sets.length ? root.sets[0].cases.length : 0) * ([root.versionA, root.versionB].filter((v, i, a) => v && a.indexOf(v) === i).length)
                return n + " casos, até " + (2 * n) + " chamadas ao modelo. Para quando o orçamento de US$ " + budgetField.text
                     + " acabar. As ações rodam numa pasta temporária e passam pelas regras de sempre."
            }
        }
        onAccepted: root.start(true)
    }
    C.AppDialog {
        id: publishDialog
        title: "Promover esta versão?"
        acceptText: "Promover"
        anchors.centerIn: parent
        Text { width: 360; wrapMode: Text.Wrap; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
               text: "As instruções de " + root.label(root.versionB) + " passam a valer no Harness. A configuração anterior fica nas versões do Harness." }
        onAccepted: { const r = root.call(Bridge.labPromote(root.versionB)); if (r.ok) root.loadVersions() }
    }
}
