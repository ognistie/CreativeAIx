// Diario: caderno pessoal com salvamento automatico, prioridades, tarefas, tags, busca e navegacao por data.
// Lista a esquerda (por data), editor a direita. O que o Segundo Cerebro pode usar aparece embaixo do texto;
// a integracao com a Conversa e opcional (desligada por padrao) e o processamento e local.
// Dados: core/journal.py via Bridge.journal*. Nada aqui executa acao: o Diario e referencia, nunca permissao.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components" as C

Item {
    id: root
    objectName: "journalView"
    readonly property bool narrow: width < 860      // janela estreita: uma coluna, controles abaixo do titulo

    property var items: []
    property var tags: []
    property bool available: true
    property bool useInBrain: false
    property string query: ""
    property string tagFilter: ""
    property string dayFilter: ""       // AAAA-MM-DD escolhido no calendario
    property var dates: []              // dias com entrada
    property date month: new Date()     // mes mostrado no calendario
    property bool summarizing: false
    property string summaryError: ""
    property var entry: null            // entrada aberta (null = nova, ainda nao salva)
    property string saveState: "idle"   // idle | dirty | saving | saved | error
    property string saveError: ""
    property bool loading: false        // preenchendo o editor: nao conta como edicao
    // Pastas (inicio do Diario): "" = grade de pastas; senao a pasta aberta
    property string folder: ""
    property var folders: []
    readonly property var folderPalettes: C.Theme.artFolders
    readonly property var folderHints: ({ agentes: "sempre disponível aos agentes", rotinas: "", notas: "", assuntos: "" })
    readonly property string folderName: { const f = folders.find(x => x.key === folder); return f ? f.name : "" }
    function openFolder(key, create) {
        flush()
        folder = key
        query = ""; tagFilter = ""; dayFilter = ""
        fill(null)
        reload()
        if (create) newEntry()
    }
    function home() { flush(); folder = ""; fill(null); reload() }

    function reload() {
        if (folder === "") {
            const f = JSON.parse(Bridge.journalFolders())
            if (!f.ok) { available = false; return }
            available = f.available
            folders = f.folders
            useInBrain = f.use_in_brain
            return
        }
        const r = JSON.parse(Bridge.journalListIn(folder, query, tagFilter, dayFilter))
        if (!r.ok) { available = false; return }
        available = r.available
        items = r.items
        tags = r.tags
        useInBrain = r.use_in_brain
        const d = JSON.parse(Bridge.journalDates())
        if (d.ok) dates = d.dates
    }
    function iso(y, m, d) { return y + "-" + ("0" + (m + 1)).slice(-2) + "-" + ("0" + d).slice(-2) }
    function shiftMonth(n) { month = new Date(month.getFullYear(), month.getMonth() + n, 1) }
    function open(id) {
        flush()
        const r = JSON.parse(Bridge.journalGet(id))
        if (!r.ok) return
        fill(r.entry)
    }
    function fill(e) {
        loading = true
        entry = e
        titleField.text = e ? e.title : ""
        bodyArea.text = e ? e.body : ""
        loading = false
        saveState = e ? "saved" : "idle"
    }
    function newEntry() {
        flush()
        fill(null)
        titleField.forceActiveFocus()
    }
    function edited() {
        if (loading) return
        saveState = "dirty"
        saveTimer.restart()
    }
    function flush() { if (saveTimer.running) { saveTimer.stop(); save() } }
    function save() {
        if (!entry && titleField.text.trim() === "" && bodyArea.text.trim() === "") { saveState = "idle"; return }
        saveState = "saving"
        const r = JSON.parse(Bridge.journalSave(JSON.stringify({
            id: entry ? entry.id : "", title: titleField.text, body: bodyArea.text,
            tags: entry ? entry.tags : [], folder: entry ? "" : root.folder })))
        if (!r.ok) { saveState = "error"; saveError = r.error || "Não salvou."; return }
        entry = r.entry
        saveState = "saved"
        reload()
    }
    function setPrivate(on) {
        if (!entry) return
        flush()
        const r = JSON.parse(Bridge.journalSetPrivate(entry.id, on))
        if (r.ok) { entry = r.entry; reload() }
    }

    onVisibleChanged: visible ? reload() : flush()
    Component.onCompleted: reload()
    Timer { id: saveTimer; interval: 800; onTriggered: root.save() }
    Connections {
        target: Bridge
        function onJournalSummary(json) {
            const r = JSON.parse(json)
            root.summarizing = false
            if (!r.ok) { root.summaryError = r.error; return }
            root.summaryError = ""
            if (root.entry && r.entry.id === root.entry.id) root.entry = r.entry
        }
    }
    Shortcut { sequence: "Ctrl+S"; enabled: root.visible; onActivated: { saveTimer.stop(); root.save() } }

    function fmtDay(d) {
        if (!d) return ""
        const p = d.split("-"), months = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
        return parseInt(p[2]) + " " + months[parseInt(p[1]) - 1] + " " + p[0]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        anchors.topMargin: 16
        spacing: 14

        // Cabecalho compacto: titulo, integracao com o Cerebro, nova entrada
        GridLayout {
            Layout.fillWidth: true
            columns: root.narrow ? 1 : 3
            columnSpacing: 12
            rowSpacing: 8
            ColumnLayout {
                spacing: 2
                C.Button { visible: root.folder !== ""; objectName: "journalBack"; text: "← Diário"; variant: "ghost"; compact: true
                           onClicked: root.home() }
                Text { text: root.folder === "" ? "Diário" : root.folderName; color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay
                       font.pixelSize: C.Theme.sizeXl + 6; font.weight: C.Theme.weightTitle
                       font.letterSpacing: C.Theme.tracking(C.Theme.sizeXl + 6) }
                Text { text: root.folder === "agentes" ? "O que os agentes devem saber. Entra no contexto deles (nunca se for privada)."
                           : "Rotinas, notas e assuntos. Fica só no seu computador."
                       color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
            }
            Item { Layout.fillWidth: true; visible: !root.narrow }
            RowLayout {
                Layout.alignment: root.narrow ? Qt.AlignLeft : (Qt.AlignRight | Qt.AlignVCenter)
                spacing: 8
                C.TogglePill {
                    objectName: "useInBrain"
                    text: root.useInBrain ? "Usado na Conversa" : "Fora da Conversa"
                    icon: ""
                    checked: root.useInBrain
                    tooltip: "Ligado: trechos relevantes (nunca os privados) entram como referência quando você pede algo na Conversa. "
                           + "A leitura é feita no seu computador; o trecho escolhido vai junto com o pedido para o modelo."
                    manual: true     // o estado vem do Diario; clique ou teclado so pedem a troca
                    onToggled: { const r = JSON.parse(Bridge.journalUseInBrain(!root.useInBrain)); if (r.ok) root.useInBrain = r.use_in_brain }
                }
                C.Button { visible: root.folder !== ""; text: "Nova entrada"; icon: "plus"; variant: "primary"; compact: true
                           onClicked: root.newEntry() }
            }
        }

        C.IntroCard {
            visible: root.folder === ""
            squeeze: root.height < 760
            Layout.fillWidth: true
            key: "diary"
            place: "o Diário"
            title: "Um caderno que o agente pode consultar, se você quiser"
            lead: "Escreva livremente. Algumas marcas viram contexto útil, extraído no seu computador."
            steps: [["", "Prioridades", "Comece a linha com ! ou “Prioridade:”."],
                    ["", "Tarefas", "Use “- [ ] tarefa”; marque feita com “- [x]”."],
                    ["", "Tags", "Escreva #tag no texto para filtrar depois."],
                    ["", "Privacidade", "Entrada privada nunca vai para a Conversa. Excluir apaga de vez."]]
        }

        // Indisponivel: sem a pasta pessoal do Cerebro nao ha onde guardar
        C.EmptyState {
            visible: !root.available
            Layout.fillWidth: true
            icon: "lock"
            title: "Diário indisponível"
            text: "O Diário fica na pasta pessoal do Segundo Cérebro, que não está configurada."
        }

        // ── Inicio: as quatro pastas ───────────────────────────
        Item {
            visible: root.available && root.folder === ""
            Layout.fillWidth: true
            Layout.fillHeight: true
            GridLayout {
                objectName: "journalFolders"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 24
                columns: parent.width < 680 ? 1 : 2
                columnSpacing: 40
                rowSpacing: 36
                Repeater {
                    model: root.folders
                    C.FolderCard {
                        objectName: "folder_" + modelData.key
                        name: modelData.name
                        count: modelData.count
                        recent: modelData.recent
                        hint: root.folderHints[modelData.key] || ""
                        palette: root.folderPalettes[modelData.key]
                        onOpened: root.openFolder(modelData.key, false)
                        onAddRequested: root.openFolder(modelData.key, true)
                    }
                }
            }
        }

        GridLayout {
            visible: root.available && root.folder !== ""
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: root.narrow ? 1 : 2; columnSpacing: 16; rowSpacing: 12

            // ── Lista por data, busca e tags ──────────────────────
            C.GlassPanel {
                Layout.preferredWidth: root.narrow ? -1 : 300
                Layout.fillWidth: root.narrow
                Layout.preferredHeight: root.narrow ? Math.min(280, root.height * 0.35) : -1
                Layout.fillHeight: !root.narrow
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10
                    // Navegacao por data: dias com entrada marcados; clique filtra o dia (de novo: tira o filtro)
                    ColumnLayout {
                        objectName: "journalCalendar"
                        Layout.fillWidth: true
                        spacing: 4
                        readonly property int calY: root.month.getFullYear()
                        readonly property int calM: root.month.getMonth()
                        readonly property int calFirst: new Date(calY, calM, 1).getDay()
                        readonly property int calCount: new Date(calY, calM + 1, 0).getDate()
                        RowLayout {
                            Layout.fillWidth: true
                            C.IconButton { name: "chevron-right"; rotation: 180; hint: "Mês anterior"; onClicked: root.shiftMonth(-1) }
                            Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
                                   text: ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
                                          "outubro", "novembro", "dezembro"][parent.parent.calM] + " " + parent.parent.calY
                                   color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm; font.weight: Font.DemiBold }
                            C.IconButton { name: "chevron-right"; hint: "Próximo mês"; onClicked: root.shiftMonth(1) }
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 7
                            rowSpacing: 2
                            columnSpacing: 2
                            Repeater {
                                model: ["D", "S", "T", "Q", "Q", "S", "S"]
                                Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: modelData
                                       color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                            }
                            Repeater {
                                model: parent.parent.calFirst + parent.parent.calCount
                                Rectangle {
                                    readonly property int day: index - parent.parent.calFirst + 1
                                    readonly property string key: day > 0 ? root.iso(parent.parent.calY, parent.parent.calM, day) : ""
                                    readonly property bool has: key !== "" && root.dates.indexOf(key) >= 0
                                    readonly property bool on: key !== "" && root.dayFilter === key
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 26
                                    radius: C.Theme.r1
                                    color: on ? C.Theme.primary : (dayMouse.containsMouse && day > 0 ? C.Theme.bgHover : C.Theme.alpha(C.Theme.bgHover, 0))
                                    Text { anchors.centerIn: parent; visible: parent.day > 0; text: parent.day
                                           color: parent.on ? C.Theme.textInverse : (parent.has ? C.Theme.textPrimary : C.Theme.textTertiary)
                                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs
                                           font.weight: parent.has ? Font.DemiBold : Font.Normal; font.features: C.Theme.tabular }
                                    Rectangle { visible: parent.has && !parent.on; width: 4; height: 4; radius: 2; color: C.Theme.accent
                                                anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 2 }
                                    MouseArea { id: dayMouse; anchors.fill: parent; hoverEnabled: true; enabled: parent.day > 0
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: { root.dayFilter = root.dayFilter === parent.key ? "" : parent.key; root.reload() } }
                                    Accessible.role: Accessible.Button
                                    Accessible.name: day > 0 ? day + (has ? ", tem entrada" : "") : ""
                                }
                            }
                        }
                    }
                    C.AppField {
                        id: searchField
                        objectName: "journalSearch"
                        Layout.fillWidth: true
                        placeholderText: "Buscar no Diário"
                        onTextChanged: { root.query = text; searchTimer.restart() }
                        Timer { id: searchTimer; interval: 200; onTriggered: root.reload() }
                    }
                    Flow {
                        Layout.fillWidth: true
                        visible: root.tags.length > 0
                        spacing: 6
                        Repeater {
                            model: root.tags
                            C.Chip { text: "#" + modelData; selected: root.tagFilter === modelData
                                     onClicked: { root.tagFilter = root.tagFilter === modelData ? "" : modelData; root.reload() } }
                        }
                    }
                    ListView {
                        id: list
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 2
                        model: root.items
                        section.property: "date"
                        section.delegate: Text {
                            width: list.width
                            topPadding: 8; bottomPadding: 4
                            text: root.fmtDay(section).toUpperCase()
                            color: C.Theme.textTertiary
                            font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs
                            font.letterSpacing: C.Theme.trackingLabel
                        }
                        delegate: Rectangle {
                            width: list.width
                            height: rowCol.implicitHeight + 16
                            radius: C.Theme.r2
                            readonly property bool current: !!root.entry && root.entry.id === modelData.id
                            color: current ? C.Theme.bgRowHover : (rowMouse.containsMouse ? C.Theme.bgHover : C.Theme.alpha(C.Theme.bgHover, 0))
                            Behavior on color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                            ColumnLayout {
                                id: rowCol
                                anchors.left: parent.left; anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 10; anchors.rightMargin: 10
                                spacing: 2
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Text { Layout.fillWidth: true; text: modelData.title || "Sem título"; elide: Text.ElideRight
                                           color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
                                           font.weight: current ? Font.DemiBold : Font.Normal }
                                    C.Icon { visible: modelData.private; name: "lock"; size: 12; color: C.Theme.textTertiary }
                                }
                                Text { Layout.fillWidth: true; visible: text !== ""; elide: Text.ElideRight
                                       text: modelData.priorities ? modelData.priorities + (modelData.priorities === 1 ? " prioridade" : " prioridades")
                                             + (modelData.open_tasks ? " · " + modelData.open_tasks + " a fazer" : "")
                                             : (modelData.open_tasks ? modelData.open_tasks + " a fazer" : "")
                                       color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                            }
                            MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: root.open(modelData.id) }
                            Accessible.role: Accessible.ListItem
                            Accessible.name: (modelData.title || "Sem título") + ", " + root.fmtDay(modelData.date)
                        }
                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 20
                            visible: list.count === 0
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: root.query || root.tagFilter ? "Nada encontrado." : "Nenhuma entrada ainda."
                            color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm
                        }
                    }
                }
            }

            // ── Editor ────────────────────────────────────────────
            C.GlassPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                fill: C.Theme.bgGlassHi
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Text { text: root.entry ? root.fmtDay(root.entry.date) : "Nova entrada"
                               color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs
                               font.letterSpacing: C.Theme.trackingLabel; font.capitalization: Font.AllUppercase }
                        Item { Layout.fillWidth: true }
                        // Estado do salvamento: sempre em texto (nunca so cor)
                        Text {
                            objectName: "journalSaveState"
                            text: root.summaryError !== "" ? root.summaryError
                                : root.saveState === "saving" ? "Salvando…"
                                : root.saveState === "dirty" ? "Alterações não salvas"
                                : root.saveState === "error" ? root.saveError
                                : root.saveState === "saved" && root.entry ? "Salvo · versão " + root.entry.version : ""
                            color: root.saveState === "error" ? C.Theme.danger : C.Theme.textTertiary
                            font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs
                        }
                        C.Button { visible: root.saveState === "error"; text: "Tentar de novo"; compact: true; onClicked: root.save() }
                        C.TogglePill { visible: !!root.entry; text: root.entry && root.entry.private ? "Privada" : "Pode ser usada"
                                       icon: ""; checked: !!root.entry && root.entry.private
                                       tooltip: "Privada: nunca entra na Conversa, mesmo com o Diário ligado."
                                       manual: true
                                       onToggled: root.setPrivate(!root.entry.private) }
                        C.Button { objectName: "journalSummarize"; visible: !!root.entry && !root.entry.private
                                   text: root.summarizing ? "Resumindo…" : "Resumir com IA"; compact: true; enabled: !root.summarizing
                                   onClicked: { root.flush(); summaryDialog.open() } }
                        C.IconButton { visible: !!root.entry; name: "x"; hint: "Excluir esta entrada"; onClicked: deleteDialog.open() }
                    }
                    TextField {
                        id: titleField
                        objectName: "journalTitle"
                        Layout.fillWidth: true
                        placeholderText: "Título"
                        background: null
                        leftPadding: 0
                        color: C.Theme.textPrimary
                        placeholderTextColor: C.Theme.textTertiary
                        font.family: C.Theme.fontDisplay; font.pixelSize: C.Theme.sizeXl + 2; font.weight: C.Theme.weightTitle
                        onTextChanged: root.edited()
                    }
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        TextArea {
                            id: bodyArea
                            objectName: "journalBody"
                            placeholderText: "Escreva aqui… ! prioridade   - [ ] tarefa   #tag"
                            wrapMode: TextArea.Wrap
                            background: null
                            leftPadding: 0
                            color: C.Theme.textPrimary
                            placeholderTextColor: C.Theme.textTertiary
                            selectionColor: C.Theme.alpha(C.Theme.accent, 0.25)
                            font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd + 1
                            onTextChanged: root.edited()
                        }
                    }
                    // O que o Segundo Cerebro pode usar desta entrada (derivados locais, ligados a esta versao)
                    Rectangle {
                        Layout.fillWidth: true
                        visible: !!root.entry && !!root.entry.derived
                                 && (root.entry.derived.priorities.length + root.entry.derived.tasks.length + root.entry.derived.tags.length) > 0
                        implicitHeight: dCol.implicitHeight + 20
                        radius: C.Theme.r2
                        color: C.Theme.bgChip
                        ColumnLayout {
                            id: dCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                            anchors.margins: 10
                            spacing: 4
                            Text { text: root.entry && root.entry.private ? "Extraído (privada: fica fora da Conversa)"
                                         : root.useInBrain ? "Extraído no seu computador · pode entrar na Conversa"
                                         : "Extraído no seu computador · Diário fora da Conversa"
                                   color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                            Repeater {
                                model: root.entry && root.entry.derived ? root.entry.derived.priorities : []
                                Text { text: "! " + modelData; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                       font.pixelSize: C.Theme.sizeSm; elide: Text.ElideRight; Layout.fillWidth: true }
                            }
                            Repeater {
                                model: root.entry && root.entry.derived ? root.entry.derived.tasks : []
                                Text { text: (modelData.done ? "☑ " : "☐ ") + modelData.text; color: C.Theme.textSecondary
                                       font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm; elide: Text.ElideRight; Layout.fillWidth: true }
                            }
                            Text { visible: !!root.entry && !!root.entry.derived && !!root.entry.derived.ai_summary
                                   Layout.fillWidth: true; wrapMode: Text.Wrap
                                   text: root.entry && root.entry.derived && root.entry.derived.ai_summary
                                         ? "Resumo por IA" + (root.entry.derived.ai_summary.version !== root.entry.version ? " (desatualizado: a entrada mudou)" : "")
                                           + ": " + root.entry.derived.ai_summary.text : ""
                                   color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                            Text { visible: root.entry && root.entry.derived && root.entry.derived.tags.length > 0
                                   text: root.entry && root.entry.derived ? root.entry.derived.tags.map(t => "#" + t).join("  ") : ""
                                   color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                        }
                    }
                }
            }
        }
    }

    // Resumo por IA: avisa ANTES o que vai para o provedor externo
    C.AppDialog {
        id: summaryDialog
        title: "Resumir esta entrada com IA?"
        acceptText: "Enviar e resumir"
        anchors.centerIn: parent
        Text { width: 340; wrapMode: Text.Wrap; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
               text: "O título e o texto desta entrada (" + (root.entry ? (root.entry.title.length + root.entry.body.length) : 0)
                     + " caracteres) vão para o modelo da Anthropic gerar um resumo de até 3 frases. Nenhuma outra entrada é enviada. "
                     + "O resumo fica só no seu computador, junto da entrada." }
        onAccepted: { if (!root.entry) return; root.summarizing = true; root.summaryError = ""; Bridge.journalSummarize(root.entry.id) }
    }
    C.AppDialog {
        id: deleteDialog
        title: "Excluir esta entrada?"
        acceptText: "Excluir"
        danger: true
        anchors.centerIn: parent
        Text { width: 320; wrapMode: Text.Wrap; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
               text: "A entrada e o que foi extraído dela saem do disco e da Conversa. Não dá para desfazer." }
        onAccepted: {
            if (!root.entry) return
            saveTimer.stop()
            const r = JSON.parse(Bridge.journalDelete(root.entry.id))
            if (r.ok) { root.fill(null); root.reload() }
        }
    }
}
