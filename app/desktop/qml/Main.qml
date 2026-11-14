// Janela raiz: sidebar (navegacao + recentes) e area de conteudo, a
// abertura (Splash) por cima e o mini chat (janela propria no canto).
// As telas ficam num StackLayout para manter o estado ao trocar de aba —
// uma tarefa em execucao continua visivel ao voltar para ela.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "components" as C
import "views" as V

ApplicationWindow {
    id: win
    // A janela so aparece depois que o QML terminou de carregar.
    visible: false
    width: 1280
    height: 820
    minimumWidth: 900
    minimumHeight: 600
    title: "Creative AIx"
    color: C.Theme.bgBase
    // Fechar a janela principal encerra o app, mesmo com o mini chat ou outra janela aberta
    onClosing: Qt.quit()

    // 0 = tarefa, 1 = historico, 2 = sobre, 3 = configuracoes, 4 = cerebro, 5 = voce, 6 = harness
    property int page: 0
    // Barra lateral recolhida (so icones): Ctrl+\ ou o botao do cabecalho
    property bool sidebarCollapsed: false
    readonly property var pageTitles: ["Conversa", "Histórico", "Sobre", "Configurações", "Cérebro", "Você", "Harness", "Atividade",
                                       "Diário", "Biblioteca", "AI Research Lab"]
    // Telas da barra lateral escolhidas no Harness
    property var modules: ({ brain: true, you: true, history: true })
    property point glowPoint: Qt.point(width * 0.6, height * 0.35)
    // Sugestoes dos agentes esperando sua revisao (Cerebro > Sugestoes)
    property int suggestionCount: 0
    function refreshSuggestions() {
        const s = JSON.parse(Bridge.suggestionsList())
        suggestionCount = s.ok ? s.items.length : 0
    }
    onPageChanged: refreshSuggestions()
    // Conversas salvas (barra lateral): clicar reabre a conversa com o contexto
    property var conversations: []
    property string currentConversation: ""
    // Abertura em cena: nada da janela principal reage (hover, dicas, cliques)
    property bool splashActive: ui.splash !== false
    // Preferencias da interface (config.yaml > ui)
    readonly property var ui: JSON.parse(Bridge.uiSettings())

    // Ao voltar para a janela completa, o mini chat sai de cena
    onActiveChanged: if (active) Bridge.mainActivated()

    function reloadRecents() {
        const data = JSON.parse(Bridge.loadConversations())
        conversations = data.items || []
        currentConversation = data.current || ""
    }

    function openConversation(id) {
        if (taskView.running) return
        const data = JSON.parse(Bridge.openConversation(id))
        if (!data.id) return
        page = 0
        taskView.showConversation(data)
        currentConversation = data.id
    }

    function openTask(text) {
        page = 0
        taskView.prefill(text)
    }

    Component.onCompleted: {
        C.Theme.backdrop = ambient          // os paineis de vidro desfocam este fundo
        reloadRecents()
        // Aparencia e telas salvas no Harness (cor, paleta, ambiente, movimento, cantos)
        const h = JSON.parse(Bridge.harnessGet())
        if (h.ok) {
            C.Theme.applyAppearance(h.harness.appearance)
            modules = h.harness.modules
            taskView.dev = h.harness.dev || taskView.dev
        }
        refreshSuggestions()
        Bridge.setTitleBarColor(C.Theme.splashBase.toString())
    }
    // A barra de titulo nativa acompanha a paleta (desktop/titlebar.py)
    Connections {
        target: C.Theme
        function onSplashBaseChanged() { Bridge.setTitleBarColor(C.Theme.splashBase.toString()) }
    }

    Connections {
        target: Bridge
        function onHistoryChanged(json) { win.reloadRecents(); win.refreshSuggestions() }
        function onConversationsChanged(json) { win.reloadRecents() }
        function onSessionReset(json) { win.currentConversation = JSON.parse(json).session || "" }
        function onPlanReview(json) {
            if (!JSON.parse(json).effect) return
            win.page = 0
            if (win.visibility === Window.Minimized) Bridge.restoreMain()
        }
        // Fala transcrita entra na conversa como se tivesse sido digitada
        function onVoiceCommand(json) {
            const v = JSON.parse(json)
            const t = v.text || ""
            if (!t || taskView.running) return
            win.page = 0
            taskView.start(t, v.heard || "")
        }
    }

    Shortcut { sequence: "Ctrl+N"; onActivated: { win.page = 0; taskView.newTask() } }
    Shortcut { sequence: "Ctrl+H"; onActivated: win.page = 1 }
    Shortcut { sequence: "Ctrl+B"; onActivated: win.page = 4 }
    Shortcut { sequence: "Ctrl+,"; onActivated: win.page = 3 }
    Shortcut { sequence: "Esc"; enabled: taskView.running; onActivated: Bridge.forceStop() }
    Shortcut { sequence: "Ctrl+\\"; onActivated: win.sidebarCollapsed = !win.sidebarCollapsed }
    Shortcut { sequence: "Ctrl+K"; enabled: !win.splashActive; onActivated: palette.opened ? palette.close() : palette.open() }

    // ═══ Paleta de comandos (Ctrl+K): so navega ou preenche; nada roda sem a pessoa enviar ═══
    function paletteItems(q) {
        const fold = (t) => (t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        const want = fold(q)
        const hit = (t) => !want || fold(t).indexOf(want) >= 0
        const pages = [
            { kind: "page", id: 0, title: "Nova conversa", area: "Ação", icon: "plus", hint: "Ctrl N" },
            { kind: "page", id: 7, title: "Atividade", area: "Ir para", icon: "chart" },
            { kind: "page", id: 1, title: "Histórico", area: "Ir para", icon: "history", hint: "Ctrl H" },
            { kind: "page", id: 4, title: "Cérebro", area: "Ir para", icon: "brain", hint: "Ctrl B" },
            { kind: "page", id: 5, title: "Você", area: "Ir para", icon: "user" },
            { kind: "page", id: 8, title: "Diário", area: "Ir para", icon: "notebook" },
            { kind: "page", id: 9, title: "Biblioteca", area: "Ir para", icon: "book" },
            { kind: "page", id: 10, title: "AI Research Lab", area: "Ir para", icon: "flask" },
            { kind: "page", id: 6, title: "Harness", area: "Ir para", icon: "sliders" },
            { kind: "page", id: 3, title: "Configurações", area: "Ir para", icon: "settings", hint: "Ctrl ," },
            { kind: "page", id: 2, title: "Sobre", area: "Ir para", icon: "info" },
            { kind: "diary-new", id: "", title: "Nova entrada no Diário", area: "Ação", icon: "edit" },
        ].filter(i => hit(i.title))
        let out = pages
        if (want.length >= 2) {
            try {
                const lib = JSON.parse(Bridge.librarySearch(q, "", "")).items
                out = out.concat(lib.slice(0, 5).map(t => ({ kind: "topic", id: t.id, title: t.title, area: "Biblioteca", icon: "book" })))
                const d = JSON.parse(Bridge.journalList(q, "", ""))
                if (d.ok) out = out.concat(d.items.slice(0, 5).map(e => ({ kind: "diary", id: e.id, folder: e.folder, title: e.title || "Sem título",
                                                                            area: "Diário · " + e.date, icon: "notebook" })))
            } catch (e) {}
            out = out.concat(win.conversations.filter(c => hit(c.title)).slice(0, 5)
                                .map(c => ({ kind: "conversation", id: c.id, title: c.title, area: "Conversa", icon: "message" })))
            out.push({ kind: "ask", id: "", title: "Pedir na Conversa: " + q, area: "Preenche a caixa", icon: "arrow-up", text: q })
        }
        return out
    }
    C.CommandPalette {
        id: palette
        parent: Overlay.overlay
        provider: win.paletteItems
        onChosen: (item) => {
            if (item.kind === "page") { if (item.id === 0) { win.page = 0; taskView.newTask() } else win.page = item.id }
            else if (item.kind === "diary-new") { win.page = 8; journalPage.openFolder("notas", true) }
            else if (item.kind === "diary") { win.page = 8; journalPage.openFolder(item.folder || "notas", false); journalPage.open(item.id) }
            else if (item.kind === "topic") { win.page = 9; libraryPage.openTopic(item.id) }
            else if (item.kind === "conversation") win.openConversation(item.id)
            else if (item.kind === "ask") win.openTask(item.text)
        }
    }

    // Identidade da abertura no app inteiro: as mesmas luzes, mais suaves, e um
    // brilho da cor de destaque que acompanha o cursor devagar
    C.Ambient {
        id: ambient
        anchors.fill: parent
        intensity: C.Theme.ambient
        follow: C.Theme.motion
        animate: C.Theme.motion && !win.splashActive && win.visibility !== Window.Minimized
        pointer: win.glowPoint
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        // Atras da abertura nada reage (hover, dicas, cliques)
        enabled: !win.splashActive
        HoverHandler { id: pointerTrack }
        // O brilho segue o cursor por amostragem (nao a cada pixel): nada de animacao reiniciando
        // sem parar sobre a barra lateral, que fazia os itens piscarem
        Timer {
            interval: 120
            repeat: true
            running: pointerTrack.hovered && C.Theme.motion && !win.splashActive
            onTriggered: {
                const p = pointerTrack.point.position
                if (Math.abs(p.x - win.glowPoint.x) + Math.abs(p.y - win.glowPoint.y) > 24) win.glowPoint = Qt.point(p.x, p.y)
            }
        }

        // ═══ Sidebar ════════════════════════════════════════════════
        Rectangle {
            id: sidebar
            readonly property bool compact: win.sidebarCollapsed
            Layout.fillHeight: true
            Layout.preferredWidth: compact ? 64 : 248
            Behavior on Layout.preferredWidth { NumberAnimation { duration: C.Theme.motion ? 220 : 0; easing.type: Easing.OutCubic } }
            color: C.Theme.bgSidebar
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: sidebar.compact ? 8 : 12
                anchors.topMargin: 16
                spacing: 2

                // Marca
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: sidebar.compact ? 0 : 8
                    Layout.alignment: sidebar.compact ? Qt.AlignHCenter : Qt.AlignLeft
                    Layout.bottomMargin: 14
                    spacing: 10
                    C.BrandMark { sizePx: 18; Layout.alignment: Qt.AlignHCenter }
                    Text {
                        visible: !sidebar.compact
                        text: "Creative AIx"
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeMd + 1
                        font.weight: Font.DemiBold
                    }
                }

                // Navegacao em grupos (Trabalho, Conhecimento, Sistema): o rotulo mono separa sem linhas
                C.NavItem {
                    objectName: "navPalette"
                    Layout.fillWidth: true
                    Layout.bottomMargin: 8
                    compact: sidebar.compact
                    label: "Buscar"
                    icon: "search"
                    badge: "Ctrl K"
                    muted: true
                    onClicked: palette.open()
                }
                C.Eyebrow { visible: !sidebar.compact; text: "Trabalho"; Layout.leftMargin: 12; Layout.bottomMargin: 2 }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "Nova conversa"
                    icon: ""
                    active: win.page === 0 && taskView.idle && !taskView.hasConversation
                    onClicked: { win.page = 0; taskView.newTask() }
                }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    visible: !taskView.idle
                    label: taskView.running ? "Em execução" : "Tarefa atual"
                    icon: taskView.running ? "" : ""
                    active: win.page === 0 && !taskView.idle
                    onClicked: win.page = 0
                }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    visible: win.modules.history !== false
                    label: "Histórico"
                    icon: ""
                    active: win.page === 1
                    onClicked: win.page = 1
                }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "Atividade"
                    icon: "chart"
                    active: win.page === 7
                    onClicked: win.page = 7
                }
                C.Eyebrow { visible: !sidebar.compact; text: "Conhecimento"; Layout.leftMargin: 12; Layout.topMargin: 14; Layout.bottomMargin: 2 }
                Item { visible: sidebar.compact; Layout.preferredHeight: 12 }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    visible: win.modules.brain !== false
                    badge: win.suggestionCount > 0 ? win.suggestionCount + (win.suggestionCount === 1 ? " sugestão" : " sugestões") : ""
                    label: "Cérebro"
                    icon: ""
                    active: win.page === 4
                    onClicked: win.page = 4
                }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    visible: win.modules.you !== false
                    label: "Você"
                    icon: ""
                    active: win.page === 5
                    onClicked: win.page = 5
                }
                C.NavItem {
                    objectName: "navDiary"
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "Diário"
                    icon: "notebook"
                    active: win.page === 8
                    onClicked: win.page = 8
                }
                C.NavItem {
                    objectName: "navLibrary"
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "Biblioteca"
                    icon: "book"
                    active: win.page === 9
                    onClicked: win.page = 9
                }
                C.Eyebrow { visible: !sidebar.compact; text: "Sistema"; Layout.leftMargin: 12; Layout.topMargin: 14; Layout.bottomMargin: 2 }
                Item { visible: sidebar.compact; Layout.preferredHeight: 12 }
                C.NavItem {
                    objectName: "navLab"
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "AI Research Lab"
                    icon: "flask"
                    active: win.page === 10
                    onClicked: win.page = 10
                }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "Harness"
                    icon: ""
                    active: win.page === 6
                    onClicked: win.page = 6
                }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "Configurações"
                    icon: ""
                    active: win.page === 3
                    onClicked: win.page = 3
                }
                C.NavItem {
                    Layout.fillWidth: true
                    compact: sidebar.compact
                    label: "Sobre"
                    icon: ""
                    active: win.page === 2
                    onClicked: win.page = 2
                }

                // Busca nas conversas
                Rectangle {
                    visible: win.conversations.length > 4 && !sidebar.compact
                    Layout.fillWidth: true
                    Layout.topMargin: 14
                    implicitHeight: 32
                    radius: C.Theme.rSm
                    color: C.Theme.bgSurface
                    border.width: 1
                    border.color: convSearch.activeFocus ? C.Theme.alpha(C.Theme.accent, 0.45) : C.Theme.hairline
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 8
                        spacing: 8
                        C.Icon { glyph: ""; size: 12; color: C.Theme.textTertiary }
                        TextField {
                            id: convSearch
                            Layout.fillWidth: true
                            placeholderText: "Buscar conversas"
                            placeholderTextColor: C.Theme.textTertiary
                            color: C.Theme.textPrimary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeSm + 1
                            background: null
                            padding: 0
                            Keys.onEscapePressed: text = ""
                        }
                    }
                }

                // Recentes
                Text {
                    visible: win.conversations.length > 0 && !sidebar.compact
                    Layout.topMargin: 22
                    Layout.leftMargin: 10
                    Layout.bottomMargin: 4
                    text: "Conversas"
                    color: C.Theme.textTertiary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeSm
                    font.weight: Font.Medium
                }
                // Lista de conversas com as bordas esmaecendo ao rolar (a lista "continua" em vez de cortar seco)
                Item {
                    visible: !sidebar.compact
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ListView {
                        id: convList
                        anchors.fill: parent
                        clip: true
                        model: win.conversations.filter(c => !convSearch.text.trim()
                            || c.title.toLowerCase().indexOf(convSearch.text.trim().toLowerCase()) >= 0)
                        spacing: 1
                        boundsBehavior: Flickable.StopAtBounds
                        delegate: C.NavItem {
                            width: ListView.view.width
                            label: modelData.title
                            // Botao direito: renomear / excluir
                            TapHandler {
                                acceptedButtons: Qt.RightButton
                                onTapped: convMenu.popup()
                            }
                            C.AppMenu {
                                id: convMenu
                                C.AppMenuItem {
                                    text: "Renomear"
                                    iconName: "edit"
                                    onTriggered: {
                                        renameDialog.sid = modelData.id
                                        renameField.text = modelData.title
                                        renameDialog.open()
                                        renameField.forceActiveFocus()
                                        renameField.selectAll()
                                    }
                                }
                                C.AppMenuItem {
                                    text: "Excluir"
                                    iconName: "x"
                                    danger: true
                                    onTriggered: {
                                        deleteDialog.sid = modelData.id
                                        deleteDialog.convTitle = modelData.title
                                        deleteDialog.open()
                                    }
                                }
                            }
                            muted: modelData.id !== win.currentConversation
                            active: modelData.id === win.currentConversation && win.page === 0
                            onClicked: win.openConversation(modelData.id)
                            C.ToolTipHint {
                                text: modelData.title + "  ·  " + modelData.turns + (modelData.turns === 1 ? " pedido" : " pedidos")
                                shown: hovered
                            }
                            property bool hovered: false
                            HoverHandler { onHoveredChanged: parent.hovered = hovered }
                        }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 6 }
                    }
                    Rectangle {
                        visible: !convList.atYBeginning
                        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                        height: 22
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: C.Theme.bgSidebar }
                            GradientStop { position: 1.0; color: C.Theme.alpha(C.Theme.bgSidebar, 0) }
                        }
                    }
                    Rectangle {
                        visible: !convList.atYEnd
                        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                        height: 26
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: C.Theme.alpha(C.Theme.bgSidebar, 0) }
                            GradientStop { position: 1.0; color: C.Theme.bgSidebar }
                        }
                    }
                }
                Item { visible: win.conversations.length === 0 || sidebar.compact; Layout.fillHeight: true }

                // Rodape: modelo em uso
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: C.Theme.hairline
                    Layout.bottomMargin: 8
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 10
                    Layout.bottomMargin: 4
                    spacing: 8
                    Rectangle {
                        Layout.preferredWidth: 6
                        Layout.preferredHeight: 6
                        radius: 3
                        color: taskView.running ? C.Theme.warning : C.Theme.success
                    }
                    Text {
                        visible: !sidebar.compact
                        Layout.fillWidth: true
                        text: taskView.running ? "Executando..." : "Pronto  ·  Claude Sonnet 5"
                        color: C.Theme.textTertiary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeSm
                        elide: Text.ElideRight
                    }
                }
            }

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: C.Theme.hairline
            }
        }

        // ═══ Conteudo ═══════════════════════════════════════════════
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Cabecalho: recolher a barra, tela atual, agente preferido e acoes. Uma barra so, mesmo desenho em
            // todos os temas: botoes de icone sem moldura, titulo em texto, o agente num controle segmentado.
            // No claro com foto, um vidro unico atras da barra inteira (em vez de um vidro por peca).
            Item {
                objectName: "topBar"
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                Rectangle {
                    visible: C.Theme.photoLight
                    anchors.fill: parent
                    anchors.margins: 6
                    anchors.leftMargin: 8
                    anchors.rightMargin: 12
                    radius: height / 2
                    color: C.Theme.bgGlass
                    border.width: 1
                    border.color: C.Theme.glassEdge
                }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 18
                    spacing: 6
                    C.IconButton {
                        flat: true
                        name: "sidebar"
                        hint: win.sidebarCollapsed ? "Mostrar a barra lateral (Ctrl+\\)" : "Recolher a barra lateral (Ctrl+\\)"
                        onClicked: win.sidebarCollapsed = !win.sidebarCollapsed
                    }
                    Rectangle { width: 1; height: 18; color: C.Theme.hairline }
                    Text {
                        Layout.leftMargin: 6
                        text: win.pageTitles[win.page] || ""
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeMd + 1
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    // Quem atende o pedido: o Maestro escolhe, ou vai direto ao Claude Code / Codex
                    C.Segmented {
                        objectName: "agentPicker"
                        visible: win.page === 0
                        label: "Quem atende o pedido"
                        options: [["auto", "Automático", "route"], ["claude", "Claude Code", "bolt"], ["codex", "Codex", "terminal"]]
                        value: taskView.agentPreference
                        onPicked: (v) => taskView.agentPreference = v
                    }
                    Item { width: 4; visible: win.page === 0 }
                    C.IconButton {
                        flat: true
                        visible: taskView.running
                        name: "stop"
                        tone: C.Theme.danger
                        hint: "Parar (Esc)"
                        onClicked: Bridge.forceStop()
                    }
                    C.IconButton {
                        flat: true
                        name: "plus"
                        hint: "Nova conversa (Ctrl+N)"
                        enabled: !taskView.running
                        onClicked: { win.page = 0; taskView.newTask() }
                    }
                }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: win.page

                V.TaskView { id: taskView; objectName: "taskView"
                             onOpenPage: (p) => win.page = p }
                V.HistoryView { onReuseRequested: (t) => win.openTask(t) }
                V.AboutView {}
                V.SettingsView {}
                V.BrainView { id: brainPage; objectName: "brainView"; onOpenYou: win.page = 5 }
                V.YouView { objectName: "youView"; onOpenBrain: win.page = 4 }
                V.HarnessView { objectName: "harnessView"; onHarnessSaved: (h) => { win.modules = h.modules; taskView.dev = h.dev || taskView.dev }
                                onOpenYou: win.page = 5
                                onOpenNote: (rel) => { win.page = 4; brainPage.open(rel) } }
                V.ActivityView { objectName: "activityView"; onOpenPage: (p) => win.page = p
                                 onOpenTask: (t) => win.openTask(t) }
                V.JournalView { id: journalPage }
                V.LibraryView { id: libraryPage }
                V.LabView { id: labPage }
            }
        }
    }

    // ═══ Abertura ═══════════════════════════════════════════════════
    // Janela propria em tela cheia por cima do app, que ja esta maximizado e
    // pronto embaixo. Ao entrar, so a abertura some (fade da janela): nada
    // muda de tamanho, entao nao ha quebra de imagem. O Python a mostra.
    C.SplashWindow {
        id: splashWindow
        active: win.splashActive
        onFinished: {
            win.splashActive = false
            win.raise()
            win.requestActivate()
            taskView.composer.focusInput()
        }
    }

    // ═══ Conversas: renomear e excluir ══════════════════════════════
    C.AppDialog {
        id: renameDialog
        property string sid: ""
        title: "Renomear conversa"
        acceptText: "Renomear"
        anchors.centerIn: parent
        canAccept: renameField.text.trim().length > 0
        C.AppField {
            id: renameField
            width: renameDialog.availableWidth
            onAccepted: if (text.trim()) renameDialog.accept()
        }
        onAccepted: if (renameField.text.trim()) Bridge.renameConversation(sid, renameField.text.trim())
    }
    C.AppDialog {
        id: deleteDialog
        property string sid: ""
        property string convTitle: ""
        title: "Excluir conversa"
        acceptText: "Excluir"
        danger: true
        anchors.centerIn: parent
        Text {
            width: deleteDialog.availableWidth
            wrapMode: Text.Wrap
            text: "“" + deleteDialog.convTitle + "” sai da lista. O arquivo vai para memory/sessions/_excluidas (dá para recuperar)."
            color: C.Theme.textPrimary
            font.family: C.Theme.fontSans
            font.pixelSize: C.Theme.sizeMd
        }
        onAccepted: Bridge.deleteConversation(sid)
    }

    // ═══ Mini chat (canto inferior direito, fora da janela) ═════════
    C.MiniChat {
        id: miniChat
        view: taskView
        stopHotkey: win.ui.stop_hotkey_label || ""
        onExpandRequested: Bridge.restoreMain()
        onCloseRequested: Bridge.closeMini()
    }
}
