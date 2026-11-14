// Cerebro: o segundo cerebro dentro do app. Pastas e notas a esquerda (com busca),
// a nota no centro (editar, ler ou ver no mapa de ligacoes) e as ligacoes a direita.
// Tudo que voce muda vai para a sua pasta pessoal; as notas de fabrica (do repositorio)
// nunca sao alteradas: editar cria uma copia sua, e "Restaurar original" desfaz.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components" as C

Item {
    id: root

    property var notes: []
    property var folders: []
    property var removed: []
    property bool writable: true
    property string personal: ""
    property string loadError: ""

    property string current: ""
    property var note: ({})
    property bool dirty: false
    property string mode: "editar"          // editar | ler | mapa
    // O mapa carrega o grafo ao entrar no modo, venha de onde vier (antes so a aba carregava, e o botao
    // "Ver o mapa" abria vazio na primeira vez)
    onModeChanged: if (mode === "mapa" && !graph) graph = JSON.parse(Bridge.brainGraph())
    property string filter: "tudo"          // tudo | meus | ocultas
    property var expanded: ({ "Você": true })
    property var results: []
    property var graph: null
    // Sugestoes dos agentes (licoes e procedimentos): so valem depois que voce aprova
    property var suggestions: []
    property var suggestion: null
    readonly property bool reviewing: filter === "sugestoes" && suggestion !== null
    property string toast: ""
    property bool toastError: false

    signal openYou()

    readonly property bool searching: search.text.trim().length >= 2

    // ── dados ────────────────────────────────────────────────────────
    function call(json) {
        const r = JSON.parse(json)
        if (!r.ok) say(r.error || "Não deu certo.", true)
        return r
    }
    function say(text, isError) { toast = text; toastError = !!isError; toastTimer.restart() }

    function reload() {
        const r = JSON.parse(Bridge.brainOverview())
        if (!r.ok) { loadError = r.error || "Cérebro indisponível"; return }
        loadError = ""
        notes = r.notes; folders = r.folders; removed = r.removed
        writable = r.writable; personal = r.personal
        graph = mode === "mapa" ? JSON.parse(Bridge.brainGraph()) : null
        const sg = JSON.parse(Bridge.suggestionsList())
        suggestions = sg.ok ? sg.items : []
        if (suggestion && !suggestions.some(x => x.id === suggestion.id)) suggestion = null
        if (filter === "sugestoes" && suggestions.length === 0) filter = "tudo"
    }

    function pickSuggestion(sid) {
        if (dirty) save(true)
        const item = suggestions.find(x => x.id === sid)
        if (!item) return
        suggestion = item
        sgTitle.text = item.title
        sgTitle.cursorPosition = 0          // mostra o comeco do titulo, nao o fim
        sgBody.text = item.body || ""
    }
    function decideSuggestion(approve) {
        if (!suggestion) return
        const r = approve ? call(Bridge.suggestionApprove(suggestion.id, sgTitle.text, sgBody.text))
                          : call(Bridge.suggestionDismiss(suggestion.id))
        if (!r.ok) return
        suggestion = null
        reload()
        if (approve) say(r.rel ? "Aprovada · os agentes já usam" : "Aprovada")
        else say("Sugestão recusada · não volta a aparecer")
    }

    function open(rel) {
        if (!rel) return
        if (dirty) save(true)
        const r = call(Bridge.brainRead(rel))
        if (!r.ok) return
        note = r
        current = rel
        editor.text = r.text
        titleField.text = rel.split("/").pop().replace(/\.md$/, "")
        titleField.cursorPosition = 0
        dirty = false
        // Abre a pasta da nota na arvore
        const parts = rel.split("/"); const ex = Object.assign({}, expanded)
        for (let i = 1; i < parts.length; i++) ex[parts.slice(0, i).join("/")] = true
        expanded = ex
    }

    function save(quiet) {
        if (!current || !dirty) return
        const r = call(Bridge.brainSave(current, editor.text))
        if (!r.ok) return
        dirty = false
        reload()
        const keep = editor.cursorPosition
        const again = JSON.parse(Bridge.brainRead(current))
        if (again.ok) note = again
        editor.cursorPosition = Math.min(keep, editor.length)
        if (!quiet) say("Salvo na sua pasta")
    }

    function rename(newTitle) {
        newTitle = newTitle.trim()
        const oldTitle = current.split("/").pop().replace(/\.md$/, "")
        if (!current || !newTitle || newTitle === oldTitle) { titleField.text = oldTitle; return }
        if (dirty) save(true)
        const folder = current.indexOf("/") >= 0 ? current.slice(0, current.lastIndexOf("/") + 1) : ""
        const r = call(Bridge.brainRename(current, folder + newTitle + ".md"))
        if (!r.ok) { titleField.text = oldTitle; return }
        reload(); open(r.rel)
        say(r.links ? "Renomeada · " + r.links + (r.links === 1 ? " ligação atualizada" : " ligações atualizadas") : "Renomeada")
    }

    function createNote(folder, title) {
        title = (title || "").trim()
        if (!title) return
        const rel = (folder ? folder + "/" : "") + title + ".md"
        const r = call(Bridge.brainCreate(rel, ""))
        if (!r.ok) return
        reload(); open(r.rel); mode = "editar"
        editor.forceActiveFocus(); editor.cursorPosition = editor.length
    }

    function fold(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim() }
    function findByTitle(t) {
        const want = fold(t)
        for (const n of notes) if (fold(n.title) === want || fold(n.rel.replace(/\.md$/, "")) === want) return n.rel
        return ""
    }
    function follow(target) {
        const rel = findByTitle(target)
        if (rel) { open(rel); return }
        if (!writable) return
        newDialog.folder = current.indexOf("/") >= 0 ? current.slice(0, current.lastIndexOf("/")) : ""
        newDialog.noteTitle = target
        newDialog.open()
    }

    function preview(md) {
        md = (md || "").replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, "")
        // O titulo ja aparece no cabecalho: um "# Titulo" igual no topo nao se repete
        const t = current.split("/").pop().replace(/\.md$/, "")
        md = md.replace(/^\s*#\s+(.+)\n/, (m, h) => fold(h) === fold(t) ? "" : m)
        md = md.replace(/\[\[([^\[\]|#]+)(#[^\[\]|]*)?(\|([^\[\]]*))?\]\]/g,
                        (m, t, h, a, alias) => "[" + (alias || t) + "](nota:" + encodeURIComponent(t.trim()) + ")")
        return md.replace(/^>\s*\[!(\w+)\]\s*/gm, "> **$1** · ")
    }

    function layerLabel(l) {
        return l === "editada" ? "Editada por você" : (l === "pessoal" ? "Sua nota" : "De fábrica")
    }

    // Arvore: pastas (abre/fecha) e notas, conforme o filtro
    function parentOf(p) { return p.indexOf("/") >= 0 ? p.slice(0, p.lastIndexOf("/")) : "" }
    function buildRows() {
        const out = []
        if (filter === "sugestoes") {
            for (const x of suggestions) out.push({ kind: "suggestion", sid: x.id, rel: "", depth: 0,
                                                   title: (x.kind === "licao" ? "Lição · " : "Procedimento · ") + x.title })
            return out
        }
        if (filter === "ocultas") {
            for (const r of removed) out.push({ kind: "hidden", rel: r, title: r.split("/").pop().replace(/\.md$/, ""), depth: 0 })
            return out
        }
        const list = notes.filter(n => filter === "tudo" || n.layer !== "base")
        const byFolder = {}
        for (const n of list) (byFolder[n.folder] = byFolder[n.folder] || []).push(n)
        const all = new Set(filter === "tudo" ? folders : [])
        for (const f of Object.keys(byFolder)) { let p = f; while (p) { all.add(p); p = parentOf(p) } }
        const count = {}
        for (const n of list) { let p = n.folder; while (p) { count[p] = (count[p] || 0) + 1; p = parentOf(p) } }
        const walk = (parent, depth) => {
            const kids = Array.from(all).filter(f => f && parentOf(f) === parent)
                              .sort((a, b) => a.localeCompare(b))
            for (const f of kids) {
                const isOpen = filter === "meus" || expanded[f] === true
                out.push({ kind: "folder", path: f, title: f.split("/").pop(), depth: depth, open: isOpen, count: count[f] || 0 })
                if (isOpen) walk(f, depth + 1)
            }
            for (const n of (byFolder[parent] || [])) out.push({ kind: "note", rel: n.rel, title: n.title, layer: n.layer, depth: depth })
        }
        walk("", 0)
        return out
    }
    readonly property var rows: buildRows()

    Timer { id: searchTimer; interval: 220; onTriggered: {
        const r = JSON.parse(Bridge.brainSearch(search.text))
        root.results = r.ok ? r.items : []
    } }
    Timer { id: toastTimer; interval: 2600; onTriggered: root.toast = "" }

    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload(); else if (dirty) save(true)

    Shortcut { sequence: "Ctrl+S"; enabled: root.visible && root.dirty; onActivated: root.save(false) }
    Shortcut { sequence: "Ctrl+K"; enabled: root.visible; onActivated: { search.forceActiveFocus(); search.selectAll() } }

    C.IntroCard {
        id: brainIntro
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 16
        key: "brain"
        place: "o Cérebro"
        title: "Seu segundo cérebro"
        lead: "Tudo o que os agentes sabem para fazer as suas tarefas, em notas que você lê e muda aqui. "
            + "O que você muda fica na sua pasta pessoal; o original de fábrica continua guardado."
        steps: [["search", "Encontre", "Navegue pelas pastas ou busque com Ctrl+K. A busca ignora acentos."],
                ["edit", "Edite e ligue", "Abra uma nota e escreva. Use [[Nome da nota]] para ligar ideias; o modo Mapa mostra as ligações."],
                ["plus", "Crie e organize", "Nova nota, nova pasta, renomear (as ligações acompanham) e remover, com restauração."],
                ["sparkle", "Revise sugestões", "Quando uma tarefa falha ou dá certo, os agentes sugerem uma lição ou um caminho. Só vale depois que você aprova."]]
    }

    RowLayout {
        anchors.top: brainIntro.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 16
        anchors.topMargin: 12
        spacing: 14

        // ═══ Navegador de notas ═════════════════════════════════════
        C.GlassPanel {
            Layout.preferredWidth: 280
            Layout.fillHeight: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    C.BrandMark { sizePx: 16 }
                    Text {
                        Layout.fillWidth: true
                        text: "Cérebro"
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontDisplay
                        font.pixelSize: C.Theme.sizeXl
                        font.weight: C.Theme.weightTitle
                    }
                    Text {
                        text: root.notes.length + " notas"
                        color: C.Theme.textTertiary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeXs
                    }
                }

                // Busca (Ctrl+K): texto completo, sem acento
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 34
                    radius: C.Theme.rMd
                    color: C.Theme.bgGlassHi
                    border.width: 1
                    border.color: search.activeFocus ? C.Theme.alpha(C.Theme.accent, 0.55) : C.Theme.hairline
                    Behavior on border.color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 8
                        C.Icon { glyph: ""; size: 12; color: search.activeFocus ? C.Theme.accent : C.Theme.textTertiary }
                        TextField {
                            id: search
                            Layout.fillWidth: true
                            placeholderText: "Buscar no cérebro  ·  Ctrl+K"
                            placeholderTextColor: C.Theme.textTertiary
                            color: C.Theme.textPrimary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeSm + 1
                            background: null
                            padding: 0
                            onTextChanged: searchTimer.restart()
                            Keys.onEscapePressed: text = ""
                            Keys.onReturnPressed: if (root.results.length) root.open(root.results[0].rel)
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.searching
                    spacing: 6
                    C.Chip { text: "Tudo"; selected: root.filter === "tudo"; onClicked: root.filter = "tudo" }
                    C.Chip { text: "Minhas"; selected: root.filter === "meus"; onClicked: root.filter = "meus" }
                    C.Chip { text: "Ocultas"; visible: root.removed.length > 0; selected: root.filter === "ocultas"
                             onClicked: root.filter = "ocultas" }
                    C.Chip { text: "Sugestões · " + root.suggestions.length; visible: root.suggestions.length > 0
                             selected: root.filter === "sugestoes"; swatch: C.Theme.accent
                             onClicked: { root.filter = "sugestoes"; if (root.suggestions.length) root.pickSuggestion(root.suggestions[0].id) } }
                }

                // Resultados da busca
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: root.searching
                    clip: true
                    spacing: 2
                    model: root.results
                    boundsBehavior: Flickable.StopAtBounds
                    delegate: Rectangle {
                        width: ListView.view.width
                        implicitHeight: resCol.implicitHeight + 14
                        radius: C.Theme.rSm
                        color: modelData.rel === root.current ? C.Theme.bgGlassHi : (resMouse.containsMouse ? C.Theme.bgRowHover : C.Theme.alpha(C.Theme.bgRowHover, 0))
                        ColumnLayout {
                            id: resCol
                            anchors.fill: parent
                            anchors.margins: 7
                            anchors.leftMargin: 10
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: modelData.title
                                elide: Text.ElideRight
                                color: C.Theme.textPrimary
                                font.family: C.Theme.fontSans
                                font.pixelSize: 13
                                font.weight: Font.Medium
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.snippet.replace(/«/g, "").replace(/»/g, "")
                                maximumLineCount: 2
                                wrapMode: Text.Wrap
                                elide: Text.ElideRight
                                color: C.Theme.textSecondary
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeSm
                            }
                        }
                        MouseArea { id: resMouse; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor; onClicked: root.open(modelData.rel) }
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: root.searching && root.results.length === 0
                        text: "Nada encontrado"
                        color: C.Theme.textTertiary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm + 1
                    }
                }

                // Arvore
                ListView {
                    id: tree
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !root.searching
                    clip: true
                    spacing: 1
                    model: root.rows
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 6 }
                    delegate: Rectangle {
                        id: row
                        width: ListView.view.width
                        implicitHeight: 30
                        radius: C.Theme.rSm
                        readonly property bool isNote: modelData.kind !== "folder"
                        readonly property bool isCurrent: modelData.kind === "suggestion"
                            ? (root.suggestion !== null && root.suggestion.id === modelData.sid)
                            : (isNote && modelData.rel === root.current)
                        color: isCurrent ? C.Theme.bgGlassHi : (rowMouse.containsMouse ? C.Theme.bgRowHover : C.Theme.alpha(C.Theme.bgRowHover, 0))
                        border.width: isCurrent ? 1 : 0
                        border.color: C.Theme.hairline
                        Behavior on color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8 + modelData.depth * 14
                            anchors.rightMargin: 8
                            spacing: 7
                            C.Icon {
                                glyph: modelData.kind === "folder" ? (modelData.open ? "" : "")
                                     : (modelData.kind === "hidden" ? "" : "")
                                size: modelData.kind === "folder" ? 9 : 12
                                Layout.preferredWidth: 14
                                color: row.isCurrent ? C.Theme.accent : C.Theme.textTertiary
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.title
                                elide: Text.ElideRight
                                color: modelData.kind === "hidden" ? C.Theme.textSecondary : C.Theme.textPrimary
                                font.family: C.Theme.fontSans
                                font.pixelSize: 13
                                font.weight: modelData.kind === "folder" || row.isCurrent ? Font.Medium : Font.Normal
                            }
                            Rectangle {     // marca: nota sua ou editada por voce
                                visible: modelData.kind === "note" && modelData.layer !== "base"
                                width: 6; height: 6; radius: 3
                                color: C.Theme.accent
                            }
                            Text {
                                visible: modelData.kind === "folder"
                                text: modelData.count || ""
                                color: C.Theme.textTertiary
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeXs
                            }
                            Text {
                                visible: modelData.kind === "hidden"
                                text: "Restaurar"
                                color: C.Theme.accent
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeSm
                            }
                        }
                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: (e) => {
                                if (modelData.kind === "folder") {
                                    if (e.button === Qt.RightButton) { newDialog.folder = modelData.path; newDialog.noteTitle = ""; newDialog.open(); return }
                                    const ex = Object.assign({}, root.expanded)
                                    ex[modelData.path] = !modelData.open
                                    root.expanded = ex
                                } else if (modelData.kind === "suggestion") {
                                    root.pickSuggestion(modelData.sid)
                                } else if (modelData.kind === "hidden") {
                                    if (root.call(Bridge.brainRestore(modelData.rel)).ok) { root.reload(); root.say("Nota restaurada") }
                                } else {
                                    root.open(modelData.rel)
                                }
                            }
                        }
                        C.ToolTipHint { text: modelData.kind === "folder" ? "Botão direito: nova nota aqui" : ""
                                        shown: rowMouse.containsMouse && modelData.kind === "folder" }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    enabled: root.writable
                    C.Button {
                        Layout.fillWidth: true
                        text: "Nova nota"
                        icon: ""
                        variant: "primary"
                        compact: true
                        onClicked: {
                            newDialog.folder = root.current.indexOf("/") >= 0 ? root.current.slice(0, root.current.lastIndexOf("/")) : ""
                            newDialog.noteTitle = ""
                            newDialog.open()
                        }
                    }
                    C.Button { text: "Pasta"; icon: ""; compact: true; onClicked: folderDialog.open() }
                    C.Button { icon: ""; compact: true; Accessible.name: "Abrir a pasta do cérebro"
                               onClicked: Bridge.openBrainFolder() }
                }
            }
        }

        // ═══ Nota ═══════════════════════════════════════════════════
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Estado vazio: boas-vindas
            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - 64, 460)
                visible: !root.current && !root.reviewing
                spacing: 14
                C.BrandMark { Layout.alignment: Qt.AlignHCenter; sizePx: 34 }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: root.loadError || "Seu segundo cérebro"
                    color: C.Theme.textPrimary
                    font.family: C.Theme.fontDisplay
                    font.pixelSize: 28
                    font.weight: C.Theme.weightTitle
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: "Os agentes consultam estas notas para planejar cada tarefa. Edite, ligue com [[colchetes duplos]] "
                        + "e crie notas novas. O que você muda fica na sua pasta pessoal; o original de fábrica continua lá."
                    color: C.Theme.textSecondary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeMd
                    lineHeight: 1.25
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 6
                    spacing: 8
                    C.Button { text: "Contar sobre você"; icon: ""; variant: "primary"; onClicked: root.openYou() }
                    C.Button { text: "Ver o mapa"; icon: ""
                               onClicked: { const first = root.findByTitle("Início") || (root.notes[0] || {}).rel; root.open(first); root.mode = "mapa" } }
                }
                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    horizontalAlignment: Text.AlignHCenter
                    visible: root.personal !== ""
                    text: "Sua pasta: " + root.personal
                    elide: Text.ElideMiddle
                    color: C.Theme.textTertiary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeXs
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                visible: root.current !== "" && !root.reviewing
                spacing: 10

                // Cabecalho: caminho, titulo (renomeia), selo da camada, modos e acoes
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.maximumWidth: 260
                        text: root.current.indexOf("/") >= 0 ? root.current.slice(0, root.current.lastIndexOf("/")).replace(/\//g, "  ›  ") : "Raiz"
                        elide: Text.ElideLeft
                        color: C.Theme.textTertiary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: layerText.implicitWidth + 16
                        implicitHeight: 22
                        radius: 11
                        color: (root.note.layer || "base") === "base" ? C.Theme.alpha(C.Theme.textPrimary, 0.06) : C.Theme.alpha(C.Theme.accent, 0.12)
                        Text {
                            id: layerText
                            anchors.centerIn: parent
                            text: root.layerLabel(root.note.layer || "base")
                            color: (root.note.layer || "base") === "base" ? C.Theme.textSecondary : C.Theme.accent
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeXs
                            font.weight: Font.Medium
                        }
                    }
                    // Modos
                    Rectangle {
                        implicitWidth: modes.implicitWidth + 6
                        implicitHeight: 30
                        radius: 15
                        color: C.Theme.alpha(C.Theme.textPrimary, 0.05)
                        Row {
                            id: modes
                            anchors.centerIn: parent
                            spacing: 2
                            Repeater {
                                model: [["editar", "Editar", ""], ["ler", "Ler", ""], ["mapa", "Mapa", ""]]
                                Rectangle {
                                    width: modeRow.implicitWidth + 18
                                    height: 24
                                    radius: 12
                                    color: root.mode === modelData[0] ? C.Theme.bgSurface : "transparent"
                                    border.width: root.mode === modelData[0] ? 1 : 0
                                    border.color: C.Theme.hairline
                                    Behavior on color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                                    Row {
                                        id: modeRow
                                        anchors.centerIn: parent
                                        spacing: 5
                                        C.Icon { glyph: modelData[2]; size: 11; anchors.verticalCenter: parent.verticalCenter
                                                 color: root.mode === modelData[0] ? C.Theme.accent : C.Theme.textSecondary }
                                        Text { text: modelData[1]; anchors.verticalCenter: parent.verticalCenter
                                               color: root.mode === modelData[0] ? C.Theme.textPrimary : C.Theme.textSecondary
                                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                    }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                onClicked: { root.mode = modelData[0]; if (root.mode === "mapa" && !root.graph) root.graph = JSON.parse(Bridge.brainGraph()) } }
                                }
                            }
                        }
                    }
                    C.Button {
                        text: root.dirty ? "Salvar" : "Salvo"
                        icon: root.dirty ? "" : ""
                        variant: root.dirty ? "primary" : "ghost"
                        compact: true
                        enabled: root.dirty && root.writable
                        onClicked: root.save(false)
                    }
                    C.Button {
                        icon: ""
                        compact: true
                        variant: "ghost"
                        onClicked: noteMenu.popup()
                        C.AppMenu {
                            id: noteMenu
                            C.AppMenuItem { text: "Restaurar original de fábrica"; iconName: "refresh"; enabled: root.note.layer === "editada"
                                       onTriggered: if (root.call(Bridge.brainRestore(root.current)).ok) { root.dirty = false; const c = root.current; root.reload(); root.open(c); root.say("Original restaurado") } }
                            C.AppMenuItem { text: "Inserir ligação  [[ ]]"; iconName: "link"; onTriggered: { root.mode = "editar"; editor.insert(editor.cursorPosition, "[[]]"); editor.cursorPosition -= 2; editor.forceActiveFocus() } }
                            C.AppMenuItem { text: "Remover nota…"; iconName: "x"; danger: true; onTriggered: deleteDialog.open() }
                        }
                    }
                }

                // Titulo (Enter renomeia e atualiza as ligacoes)
                TextField {
                    id: titleField
                    Layout.fillWidth: true
                    readOnly: !root.writable
                    color: C.Theme.textPrimary
                    font.family: C.Theme.fontDisplay
                    font.pixelSize: C.Theme.sizeHero - 4
                    font.weight: C.Theme.weightTitle
                    background: Rectangle {
                        color: "transparent"
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1
                                    color: titleField.activeFocus ? C.Theme.alpha(C.Theme.accent, 0.6) : "transparent" }
                    }
                    leftPadding: 0
                    onAccepted: { root.rename(text); editor.forceActiveFocus() }
                    onActiveFocusChanged: if (!activeFocus) root.rename(text)
                    Keys.onEscapePressed: { text = root.current.split("/").pop().replace(/\.md$/, ""); editor.forceActiveFocus() }
                }

                // Corpo
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: root.mode === "editar" ? 0 : (root.mode === "ler" ? 1 : 2)

                    ScrollView {
                        clip: true
                        TextArea {
                            id: editor
                            wrapMode: TextArea.Wrap
                            readOnly: !root.writable
                            selectByMouse: true
                            color: C.Theme.textPrimary
                            selectionColor: C.Theme.alpha(C.Theme.accent, 0.25)
                            selectedTextColor: C.Theme.textPrimary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeMd + 1
                            placeholderText: "Escreva aqui. Use [[Nome da nota]] para ligar ideias."
                            placeholderTextColor: C.Theme.textTertiary
                            background: null
                            leftPadding: 2
                            onTextChanged: if (activeFocus) root.dirty = text !== (root.note.text || "")
                            Keys.onPressed: (e) => {
                                // [[ abre a ligacao ja fechada
                                if (e.text === "[" && cursorPosition > 0 && getText(cursorPosition - 1, cursorPosition) === "[") {
                                    insert(cursorPosition, "[]]"); cursorPosition -= 2; e.accepted = true
                                }
                            }
                        }
                    }

                    ScrollView {
                        id: readerScroll
                        clip: true
                        Text {
                            width: readerScroll.availableWidth
                            textFormat: Text.MarkdownText
                            text: root.preview(editor.text)
                            wrapMode: Text.Wrap
                            color: C.Theme.textPrimary
                            linkColor: C.Theme.accent
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeMd + 1
                            lineHeight: 1.2
                            onLinkActivated: (link) => {
                                if (link.indexOf("nota:") === 0) root.follow(decodeURIComponent(link.slice(5)))
                                else if (/^https?:/.test(link)) Qt.openUrlExternally(link)
                            }
                            HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.IBeamCursor }
                        }
                    }

                    C.NoteMap {
                        graph: root.graph
                        center: root.current
                        onPicked: (rel) => root.open(rel)
                    }
                }
            }

            // Revisao de uma sugestao dos agentes
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                visible: root.reviewing
                spacing: 12
                RowLayout {
                    spacing: 8
                    Rectangle {
                        implicitWidth: kindText.implicitWidth + 18; implicitHeight: 24; radius: 12
                        color: C.Theme.alpha(C.Theme.accent, 0.12)
                        Text { id: kindText; anchors.centerIn: parent
                               text: root.suggestion && root.suggestion.kind === "licao" ? "Lição sugerida" : "Procedimento sugerido"
                               color: C.Theme.accent; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm; font.weight: Font.Medium }
                    }
                    Text { text: root.suggestion ? root.suggestion.created + (root.suggestion.agents && root.suggestion.agents.length
                                 ? "  ·  " + root.suggestion.agents.map(a => C.Theme.agentLabel(a)).join(", ") : "") : ""
                           color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                }
                TextField {
                    id: sgTitle
                    Layout.fillWidth: true
                    color: C.Theme.textPrimary
                    font.family: C.Theme.fontDisplay
                    font.pixelSize: C.Theme.sizeXl + 4
                    font.weight: C.Theme.weightTitle
                    leftPadding: 0
                    maximumLength: 90
                    background: Rectangle { color: "transparent"
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1
                                    color: sgTitle.activeFocus ? C.Theme.alpha(C.Theme.accent, 0.6) : C.Theme.hairline } }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: root.suggestion ? root.suggestion.evidence : ""
                    color: C.Theme.textSecondary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeMd
                }
                Text {
                    Layout.topMargin: 6
                    text: root.suggestion && root.suggestion.kind === "licao" ? "Regra" : "Caminho"
                    color: C.Theme.textPrimary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeMd
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 150
                    radius: C.Theme.rMd
                    color: C.Theme.bgSurface
                    border.width: 1
                    border.color: sgBody.activeFocus ? C.Theme.alpha(C.Theme.accent, 0.55) : C.Theme.hairline
                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 10
                        TextArea {
                            id: sgBody
                            objectName: "sgBody"
                            wrapMode: TextArea.Wrap
                            placeholderText: root.suggestion ? root.suggestion.hint : ""
                            placeholderTextColor: C.Theme.textTertiary
                            color: C.Theme.textPrimary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeMd
                            background: null
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: root.suggestion && root.suggestion.kind === "licao"
                          ? "Ao aprovar, a lição vai para 60 Aprendizados e os agentes passam a evitar essa falha."
                          : "Ao aprovar, vira um procedimento verificado por você em 30 Tarefas de referencia e os agentes passam a seguir este caminho."
                    color: C.Theme.textTertiary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeSm
                }
                RowLayout {
                    spacing: 8
                    C.Button { text: "Aprovar"; icon: "\uE73E"; variant: "primary"
                               enabled: sgBody.text.trim().length > 0 && sgTitle.text.trim().length > 0
                               onClicked: root.decideSuggestion(true) }
                    C.Button { text: "Recusar"; onClicked: root.decideSuggestion(false) }
                }
                Item { Layout.fillHeight: true }
            }

            // Aviso curto (salvo, erro)
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                visible: opacity > 0
                opacity: root.toast ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: C.Theme.dur(C.Theme.durNormal) } }
                implicitWidth: toastText.implicitWidth + 28
                implicitHeight: 34
                radius: 17
                color: root.toastError ? C.Theme.danger : C.Theme.primary
                Text { id: toastText; anchors.centerIn: parent; text: root.toast; color: C.Theme.textInverse
                       font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
            }
        }

        // ═══ Ligacoes ═══════════════════════════════════════════════
        C.GlassPanel {
            Layout.preferredWidth: 250
            Layout.fillHeight: true
            visible: root.current !== "" && !root.reviewing && root.width > 1080

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 6

                Text { text: "Liga para"; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                       font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                Text { visible: (root.note.links || []).length === 0; text: "Nenhuma ligação. Use [[ ]] no texto."
                       wrapMode: Text.Wrap; Layout.fillWidth: true
                       color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                Repeater {
                    model: (root.note.links || []).slice(0, 14)
                    LinkRow { Layout.fillWidth: true; label: modelData.target; missing: !modelData.rel
                              onClicked: modelData.rel ? root.open(modelData.rel) : root.follow(modelData.target) }
                }

                Text { Layout.topMargin: 14; text: "Mencionada em"; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                       font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                Text { visible: (root.note.backlinks || []).length === 0; text: "Nenhuma nota cita esta ainda."
                       wrapMode: Text.Wrap; Layout.fillWidth: true
                       color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                Repeater {
                    model: (root.note.backlinks || []).slice(0, 14)
                    LinkRow { Layout.fillWidth: true; label: modelData.title; onClicked: root.open(modelData.rel) }
                }
                Item { Layout.fillHeight: true }
            }
        }
    }

    component LinkRow: Rectangle {
        id: lr
        property string label: ""
        property bool missing: false
        signal clicked()
        implicitHeight: 28
        radius: C.Theme.rSm
        color: lrMouse.containsMouse ? C.Theme.bgRowHover : C.Theme.alpha(C.Theme.bgRowHover, 0)
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 7
            C.Icon { glyph: lr.missing ? "" : ""; size: 11; color: lr.missing ? C.Theme.textTertiary : C.Theme.accent }
            Text { Layout.fillWidth: true; text: lr.label + (lr.missing ? "  · criar" : ""); elide: Text.ElideRight
                   color: lr.missing ? C.Theme.textSecondary : C.Theme.textPrimary
                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
        }
        MouseArea { id: lrMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: lr.clicked() }
    }

    // ═══ Dialogos ═══════════════════════════════════════════════════
    C.AppDialog {
        id: newDialog
        objectName: "newNoteDialog"
        property string folder: ""
        property alias noteTitle: newTitle.text
        title: "Nova nota"
        acceptText: "Criar nota"
        anchors.centerIn: parent
        canAccept: newTitle.text.trim().length > 0
        onOpened: { folderField.text = folder; newTitle.forceActiveFocus(); newTitle.selectAll() }
        ColumnLayout {
            width: newDialog.availableWidth
            spacing: 8
            Text { text: "Pasta"; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
            C.AppField { id: folderField; Layout.fillWidth: true; placeholderText: "Raiz do cérebro (ou digite uma pasta nova)" }
            Flow {
                Layout.fillWidth: true
                spacing: 6
                Repeater {
                    model: root.folders.filter(f => f !== folderField.text
                               && (!folderField.text.trim() || root.fold(f).indexOf(root.fold(folderField.text)) >= 0)).slice(0, 6)
                    C.Chip { text: modelData; icon: "\uE8B7"; onClicked: folderField.text = modelData }
                }
            }
            Text { Layout.topMargin: 6; text: "Nome"; color: C.Theme.textSecondary; font.family: C.Theme.fontSans
                   font.pixelSize: C.Theme.sizeSm + 1 }
            C.AppField { id: newTitle; Layout.fillWidth: true; placeholderText: "Nome da nota"
                         onAccepted: if (text.trim()) newDialog.accept() }
        }
        onAccepted: root.createNote(folderField.text.trim(), newTitle.text)
    }
    C.AppDialog {
        id: folderDialog
        title: "Nova pasta"
        acceptText: "Criar pasta"
        anchors.centerIn: parent
        canAccept: folderName.text.trim().length > 0
        onOpened: { folderName.text = ""; folderName.forceActiveFocus() }
        C.AppField { id: folderName; width: folderDialog.availableWidth; placeholderText: "Ex.: Projetos/Ideias"
                     onAccepted: if (text.trim()) folderDialog.accept() }
        onAccepted: {
            const r = root.call(Bridge.brainCreateFolder(folderName.text))
            if (r.ok) { root.reload(); const ex = Object.assign({}, root.expanded); ex[r.rel] = true; root.expanded = ex; root.say("Pasta criada") }
        }
    }
    C.AppDialog {
        id: deleteDialog
        title: "Remover nota"
        acceptText: "Remover"
        danger: true
        anchors.centerIn: parent
        Text {
            width: deleteDialog.availableWidth
            wrapMode: Text.Wrap
            text: "“" + root.current.split("/").pop().replace(/\.md$/, "") + "” sai do cérebro e os agentes deixam de usá-la. "
                + ((root.note.layer || "base") === "pessoal" ? "O arquivo vai para a lixeira da sua pasta (.lixeira)."
                                                             : "A nota de fábrica fica oculta: dá para restaurar em Ocultas.")
            color: C.Theme.textPrimary
            font.family: C.Theme.fontSans
            font.pixelSize: C.Theme.sizeMd
        }
        onAccepted: {
            if (root.call(Bridge.brainDelete(root.current)).ok) {
                root.dirty = false; root.current = ""; root.note = ({}); root.reload(); root.say("Nota removida")
            }
        }
    }
}
