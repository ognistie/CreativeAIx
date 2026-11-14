// Abertura: marca sobre um degrade suave (pessego, laranja e lilas) que se
// move devagar. Depois da entrada, convida a pressionar qualquer tecla ou
// clicar. Ao sair, some com um leve zoom e revela o app.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    color: Theme.splashBase

    // O que some no fim: a propria abertura ou a janela dela (tela cheia)
    property var fadeTarget: root
    signal finished()
    property bool leaving: false
    property bool canLeave: false

    function dismiss() {
        if (leaving || !canLeave) return
        leaving = true
        exitAnim.start()
    }

    // A animacao de entrada comeca quando a janela da abertura aparece
    property bool started: false
    readonly property bool windowShown: Window.window ? Window.window.visible : false
    function begin() {
        if (started || !visible || !windowShown) return
        started = true
        forceActiveFocus()
        introAnim.start()
    }
    onWindowShownChanged: begin()
    Component.onCompleted: begin()

    Keys.onPressed: (event) => { event.accepted = true; root.dismiss() }

    // ── Fundo: as luzes da marca (o mesmo ambiente do app, em intensidade cheia) ──
    Ambient { anchors.fill: parent; intensity: 1.0 }

    // ── Marca ────────────────────────────────────────────────────────
    ColumnLayout {
        id: brand
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -24
        spacing: 0
        opacity: 0
        transformOrigin: Item.Center

        BrandMark {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: 18
            sizePx: 40
        }
        Text {
            id: title
            Layout.alignment: Qt.AlignHCenter
            text: "Creative AIx"
            color: Theme.textPrimary
            font.family: Theme.fontDisplay
            font.pixelSize: 56
            font.weight: Theme.weightTitle
            font.letterSpacing: -1.2
        }
        Text {
            id: tagline
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 10
            opacity: 0
            text: "Linguagem natural entra. Ações reais saem."
            color: Theme.textSecondary
            font.family: Theme.fontSans
            font.pixelSize: 18
        }
    }

    // ── Convite para entrar ─────────────────────────────────────────
    Rectangle {
        id: hint
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Math.max(48, parent.height * 0.12)
        width: hintRow.implicitWidth + 32
        height: 38
        radius: 19
        opacity: 0
        color: Theme.bgChip
        border.width: 1
        border.color: Theme.hairline

        RowLayout {
            id: hintRow
            anchors.centerIn: parent
            spacing: 10
            Rectangle {
                width: 6; height: 6; radius: 3
                color: Theme.accent
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: hint.opacity > 0 && !root.leaving
                    NumberAnimation { to: 0.3; duration: 900; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                }
            }
            Text {
                text: "Pressione qualquer tecla ou clique para entrar"
                color: Theme.textSecondary
                font.family: Theme.fontSans
                font.pixelSize: 14
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: root.canLeave ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.dismiss()
    }

    // ── Animacoes ────────────────────────────────────────────────────
    SequentialAnimation {
        id: introAnim
        PauseAnimation { duration: 250 }
        ParallelAnimation {
            NumberAnimation { target: brand; property: "opacity"; from: 0; to: 1; duration: 700; easing.type: Easing.OutCubic }
            NumberAnimation { target: brand; property: "scale"; from: 0.96; to: 1; duration: 900; easing.type: Easing.OutCubic }
        }
        NumberAnimation { target: tagline; property: "opacity"; to: 1; duration: 500; easing.type: Easing.OutCubic }
        ScriptAction { script: root.canLeave = true }
        PauseAnimation { duration: 350 }
        NumberAnimation { target: hint; property: "opacity"; to: 1; duration: 500; easing.type: Easing.OutCubic }
    }

    SequentialAnimation {
        id: exitAnim
        ScriptAction { script: introAnim.stop() }
        ParallelAnimation {
            NumberAnimation { target: brand; property: "scale"; to: 1.04; duration: 450; easing.type: Easing.InCubic }
            NumberAnimation { target: hint; property: "opacity"; to: 0; duration: 200 }
            NumberAnimation { target: root.fadeTarget; property: "opacity"; to: 0; duration: 550; easing.type: Easing.InOutCubic }
        }
        ScriptAction { script: { root.visible = false; root.finished() } }
    }

    Accessible.role: Accessible.Pane
    Accessible.name: "Creative AIx. Pressione qualquer tecla para entrar."
}
