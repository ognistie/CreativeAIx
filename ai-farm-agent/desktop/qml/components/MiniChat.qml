// Mini chat: quando o agente vai para outra janela (abre um app, o
// navegador...), a tarefa vira uma ORBE no canto inferior direito (TaskOrb: estado da
// tarefa e da voz, sem texto). Com o cursor em cima, abre o painel com o trajeto inteiro
// (pedido, o que ouviu, passos, resultado); o cursor saiu, volta a ser so a orbe.
//
// O "cursor em cima" vem da posicao global do mouse (Bridge.cursorPos), nao de eventos
// da janela: assim a janela continua transparente a cliques durante a tarefa.
//
// Enquanto a tarefa roda ele e "passivo": nao recebe foco nem cliques, para
// nao atrapalhar o que o agente digita e clica (parar: atalho global,
// Ctrl+Alt+X por padrao). Quando a tarefa termina ele volta a ser
// interativo e da para continuar a conversa.
//
// O estado vem da TaskView (`view`); o Python posiciona e alterna o modo.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "." as Own

Window {
    id: mini
    objectName: "miniChat"

    property var view: null
    property string stopHotkey: ""   // atalho global de parar (vazio se indisponivel)
    readonly property bool passive: !!view && view.running

    signal expandRequested()
    signal closeRequested()

    // ── Orbe recolhida / painel aberto (o canto inferior direito fica parado) ──
    readonly property int orbBox: 104
    readonly property int panelW: 380
    readonly property int panelH: 600
    property bool expanded: false
    property bool stuck: false          // aberto por clique na orbe ou pelo acesso rapido
    property bool hovered: false
    readonly property bool keepOpen: stuck || (!!view && view.reviewing)
                                     || ["focus", "typing", "error"].indexOf(miniComposer.phase) >= 0
    function setExpanded(on) {
        if (on === expanded) return
        const right = x + width, bottom = y + height
        expanded = on
        width = on ? panelW : orbBox
        height = on ? panelH : orbBox
        x = right - width
        y = bottom - height
        if (on) scrollSoon()
    }
    onKeepOpenChanged: if (keepOpen) setExpanded(true)
    onVisibleChanged: {
        if (visible) { scrollSoon(); return }
        stuck = false; hovered = false; expanded = false; width = orbBox; height = orbBox
    }

    // Cursor em cima: posicao global sondada (abre com 220 ms parado em cima, fecha 500 ms depois de sair)
    Timer {
        interval: 100; repeat: true; running: mini.visible
        onTriggered: {
            const c = Bridge.cursorPos()
            const inside = c[0] >= mini.x && c[0] < mini.x + mini.width && c[1] >= mini.y && c[1] < mini.y + mini.height
            if (inside !== mini.hovered) mini.hovered = inside
        }
    }
    onHoveredChanged: hovered ? (closeTimer.stop(), openTimer.restart()) : (openTimer.stop(), closeTimer.restart())
    Timer { id: openTimer; interval: 220; onTriggered: if (mini.hovered) mini.setExpanded(true) }
    Timer { id: closeTimer; interval: 500; onTriggered: if (!mini.hovered && !mini.keepOpen) mini.setExpanded(false) }

    // Estado da orbe: voz primeiro (e o que a pessoa sente), depois a tarefa
    readonly property string orbState: {
        const v = mini.view
        if (!v) return "idle"
        const vs = v.composer.voiceState
        if (vs === "recording" || (vs === "listening" && v.composer.liveOn)) return "listening"
        if (vs === "speaking") return "speaking"
        if (v.reviewing || v.status === "clarify") return "attention"
        if (v.running) return vs === "thinking" ? "thinking" : "running"
        if (vs === "thinking") return "thinking"
        if (v.status === "failed") return "failed"
        if (v.status === "done") return "done"
        return "idle"
    }

    width: orbBox
    height: orbBox
    visible: false
    // Janela independente: se fosse "filha" da principal, o Windows a
    // esconderia junto quando a principal minimiza
    transientParent: null
    color: "transparent"                // so a orbe (e o painel, quando aberto) aparecem
    title: "Creative AIx"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
           | (passive ? (Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus) : 0)

    function scrollSoon() { scrollTimer.restart() }
    Timer { id: scrollTimer; interval: 40; onTriggered: body.scrollToEnd() }

    Connections {
        target: mini.view
        ignoreUnknownSignals: true
        function onStatusChanged() { mini.scrollSoon() }
        function onAssistantTextChanged() { mini.scrollSoon() }
    }
    Connections {
        target: mini.view ? mini.view.steps : null
        ignoreUnknownSignals: true
        function onCountChanged() { mini.scrollSoon() }
    }
    // Acesso rapido (Alt+Espaco): o mini chat aparece ja com o cursor na caixa de pedido
    Connections {
        target: Bridge
        function onQuickEntry() { focusTimer.restart() }
    }
    Timer { id: focusTimer; interval: 60; onTriggered: { mini.stuck = true; mini.setExpanded(true); mini.requestActivate(); miniComposer.focusInput() } }

    // ── A orbe (sempre no canto) ─────────────────────────────────────
    Item {
        id: orbArea
        z: 2                              // a orbe fica por cima da borda do painel
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: mini.orbBox
        height: mini.orbBox
        TaskOrb {
            id: orb
            objectName: "taskOrb"
            anchors.centerIn: parent
            size: 60
            state_: mini.orbState
            level: mini.view ? mini.view.composer.voiceLevel : 0
        }
        // Fora da tarefa: clique fixa o painel aberto (de novo: solta); arrastar move
        TapHandler {
            enabled: !mini.passive
            onTapped: { mini.stuck = !mini.stuck; mini.setExpanded(mini.stuck || mini.hovered) }
        }
        DragHandler {
            enabled: !mini.passive
            target: null
            onActiveChanged: if (active) mini.startSystemMove()
        }
    }

    // ── Painel com o trajeto (so com o cursor em cima ou fixado) ─────
    Rectangle {
        id: card
        objectName: "miniPanel"
        visible: mini.expanded
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: orbArea.top
        anchors.bottomMargin: -20         // encosta na orbe sem cobrir a esfera (topo dela a 22 px)
        radius: 20
        color: Theme.bgBase
        border.width: 1
        border.color: Theme.hairline
        opacity: mini.expanded ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 1
            spacing: 0

            // ── Cabecalho (arrasta a janela) ─────────────────────────
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 44

                DragHandler {
                    target: null
                    onActiveChanged: if (active) mini.startSystemMove()
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 6
                    spacing: 8

                    BrandMark { sizePx: 14 }
                    Text {
                        text: "Creative AIx"
                        color: Theme.textPrimary
                        font.family: Theme.fontSans
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    Spinner { visible: mini.passive; size: 12 }
                    Text {
                        visible: mini.passive
                        text: "Executando"
                        color: Theme.textTertiary
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.sizeSm
                        Layout.rightMargin: 4
                    }
                    HeaderButton {
                        visible: !mini.passive
                        glyph: ""
                        tip: "Abrir a janela completa"
                        onClicked: mini.expandRequested()
                    }
                    HeaderButton {
                        visible: !mini.passive
                        glyph: ""
                        tip: "Fechar o mini chat"
                        onClicked: mini.closeRequested()
                    }
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width; height: 1
                    color: Theme.hairline
                }
            }

            // ── Conversa ────────────────────────────────────────────
            ScrollPage {
                id: body
                Layout.fillWidth: true
                Layout.fillHeight: true
                maxWidth: 10000
                sidePadding: 16
                topPadding: 14
                bottomPadding: 10
                spacing: 12

                // Pedidos anteriores: o que foi dito + resultado em uma linha
                Repeater {
                    model: mini.view ? mini.view.turns : null
                    delegate: ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        UserBubble { text: model.said }
                        ResultLine { status: model.status; text: model.summary }
                    }
                }

                // Pedido atual
                UserBubble {
                    visible: !!mini.view && !mini.view.idle
                    text: mini.view ? mini.view.task : ""
                }
                Caption {
                    visible: !!mini.view && mini.view.heardText !== ""
                    text: "Ouvi: “" + (mini.view ? mini.view.heardText : "") + "”"
                }
                Caption {
                    visible: !!mini.view && mini.view.resolvedText !== ""
                    text: "Entendi: " + (mini.view ? mini.view.resolvedText : "")
                }

                // Falas do assistente (voz)
                Repeater {
                    model: mini.view ? mini.view.replies : null
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Row {
                            spacing: 2
                            Layout.alignment: Qt.AlignTop
                            Layout.topMargin: 4
                            Repeater {
                                model: 4
                                Rectangle {
                                    width: 2.5; radius: 1.25
                                    height: [6, 10, 7, 11][index]
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: Theme.accent
                                }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: model.text
                            color: Theme.textPrimary
                            font.family: Theme.fontSans
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                    }
                }

                // Passos
                Repeater {
                    model: mini.view ? mini.view.steps : null
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Item {
                            Layout.preferredWidth: 16
                            Layout.preferredHeight: 16
                            Layout.alignment: Qt.AlignTop
                            Spinner { anchors.centerIn: parent; visible: model.state === "running"; size: 12 }
                            StatusDot { anchors.centerIn: parent; visible: model.state !== "running"; status: model.state }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: model.desc
                            color: model.kind === "note" ? Theme.textSecondary : Theme.textPrimary
                            font.family: Theme.fontSans
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }
                    }
                }

                // Plano esperando aprovacao
                ColumnLayout {
                    visible: !!mini.view && mini.view.reviewing
                    Layout.fillWidth: true
                    spacing: 6
                    Text {
                        text: "Aprovar o plano?"
                        color: Theme.textPrimary
                        font.family: Theme.fontSans
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Repeater {
                        model: mini.view ? mini.view.reviewSteps : []
                        delegate: Text {
                            Layout.fillWidth: true
                            text: (index + 1) + ". " + modelData
                            color: Theme.textSecondary
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.sizeSm
                            wrapMode: Text.Wrap
                        }
                    }
                    RowLayout {
                        spacing: 6
                        Own.Button { text: "Executar"; variant: "primary"; compact: true; onClicked: mini.view.decidePlan(true) }
                        Own.Button { text: "Cancelar"; variant: "ghost"; compact: true; onClicked: mini.view.decidePlan(false) }
                    }
                }

                // Andamento (antes do primeiro passo: "Entendendo o pedido"...)
                RowLayout {
                    visible: !!mini.view && mini.view.running && mini.view.steps.count === 0
                    Layout.fillWidth: true
                    spacing: 8
                    Spinner { size: 12 }
                    Text {
                        Layout.fillWidth: true
                        text: (mini.view ? mini.view.phaseMsg : "") + "..."
                        color: Theme.textSecondary
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.sizeSm
                        elide: Text.ElideRight
                    }
                }

                // Resultado
                Text {
                    visible: text !== "" && !!mini.view && !mini.view.running
                    Layout.fillWidth: true
                    text: !mini.view ? ""
                        : mini.view.assistantText || mini.view.reportSummary
                          || mini.view.question || (mini.view.status === "failed" ? mini.view.errorMsg : "")
                    color: Theme.textPrimary
                    font.family: Theme.fontSans
                    font.pixelSize: 13
                    lineHeight: 1.25
                    wrapMode: Text.Wrap
                    maximumLineCount: 8
                    elide: Text.ElideRight
                }
                Rectangle {
                    visible: !!mini.view && !mini.view.running && !mini.view.idle && !!mini.view.finalMetrics
                    implicitWidth: costText.implicitWidth + 16
                    implicitHeight: 22
                    radius: 6
                    color: Theme.bgSurfaceHi
                    Text {
                        id: costText
                        anchors.centerIn: parent
                        text: mini.view ? mini.view.usageLine() : ""
                        color: Theme.textSecondary
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.sizeXs
                    }
                }
            }

            // ── Entrada ─────────────────────────────────────────────
            Composer {
                id: miniComposer
                visible: !mini.passive
                Layout.fillWidth: true
                Layout.margins: 10
                Layout.topMargin: 4
                compact: true
                running: !!mini.view && mini.view.running
                placeholder: !running ? "Peça por texto ou voz..."
                           : mini.stopHotkey ? "Executando... " + mini.stopHotkey + " para parar"
                           : "Executando..."
                voiceState: mini.view ? mini.view.composer.voiceState : "idle"
                voiceLevel: mini.view ? mini.view.composer.voiceLevel : 0
                liveOn: mini.view ? mini.view.composer.liveOn : false
                queued: mini.view ? mini.view.composer.queued : 0
                recStartedAt: mini.view ? mini.view.composer.recStartedAt : 0
                voiceHotkey: mini.view ? mini.view.composer.voiceHotkey : "Ctrl+Alt+V"
                onSubmitted: (t) => { text = ""; mini.view.start(t) }
                onStopRequested: Bridge.forceStop()
                onMicClicked: Bridge.voiceRecordToggle()
                onRecordCancel: Bridge.voiceRecordCancel()
                onLiveSwitched: (on) => Bridge.setLiveConversation(on)
            }
        }
    }

    // ── Pecas locais ────────────────────────────────────────────────
    component UserBubble: Rectangle {
        property alias text: bubbleText.text
        Layout.alignment: Qt.AlignRight
        Layout.maximumWidth: body.width * 0.82
        implicitWidth: Math.min(bubbleText.implicitWidth + 26, body.width * 0.82)
        implicitHeight: bubbleText.implicitHeight + 16
        radius: 16
        color: Theme.bgSurfaceHi
        Text {
            id: bubbleText
            anchors.fill: parent
            anchors.leftMargin: 13; anchors.rightMargin: 13
            anchors.topMargin: 8; anchors.bottomMargin: 8
            color: Theme.textPrimary
            font.family: Theme.fontSans
            font.pixelSize: 13
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
        }
    }

    component Caption: Text {
        Layout.fillWidth: true
        color: Theme.textTertiary
        font.family: Theme.fontSans
        font.pixelSize: Theme.sizeSm
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
    }

    component ResultLine: Rectangle {
        id: rl
        property string status: "done"
        property alias text: resultText.text
        Layout.fillWidth: true
        implicitHeight: resultRow.implicitHeight + 16
        radius: 10
        color: Theme.bgBase
        border.width: 1
        border.color: Theme.hairline
        RowLayout {
            id: resultRow
            anchors.fill: parent
            anchors.margins: 8
            anchors.leftMargin: 10
            spacing: 8
            StatusDot { status: rl.status; Layout.alignment: Qt.AlignTop; Layout.topMargin: 1 }
            Text {
                id: resultText
                Layout.fillWidth: true
                color: Theme.textPrimary
                font.family: Theme.fontSans
                font.pixelSize: Theme.sizeSm + 1
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }
    }

    component HeaderButton: Rectangle {
        id: hb
        property string glyph: ""
        property string tip: ""
        signal clicked()
        width: 30; height: 30; radius: 8
        color: hbMouse.containsMouse ? Theme.bgHover : Theme.alpha(Theme.bgHover, 0)
        Icon { anchors.centerIn: parent; glyph: hb.glyph; size: 11; color: Theme.textSecondary }
        MouseArea {
            id: hbMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: hb.clicked()
        }
        ToolTipHint { text: hb.tip; shown: hbMouse.containsMouse }
        Accessible.role: Accessible.Button
        Accessible.name: hb.tip
    }
}
