// Botao redondo so com icone (cabecalho): hover em vidro, dica com atraso, teclado e leitor de tela.
import QtQuick

Rectangle {
    id: root
    property string name: ""
    property string hint: ""
    property color tone: Theme.textSecondary
    property bool flat: false               // dentro de uma barra que ja tem vidro: sem vidro proprio
    signal clicked()

    implicitWidth: 34
    implicitHeight: 34
    radius: 17
    opacity: enabled ? 1 : 0.4
    // Claro com foto: o botao ganha vidro para nao sumir sobre a pintura
    color: mouse.pressed ? Theme.bgPressed
         : Theme.photoLight && !flat ? (mouse.containsMouse || activeFocus ? Theme.bgGlassHi : Theme.bgGlass)
         : (mouse.containsMouse || activeFocus ? Theme.bgHover : Theme.alpha(Theme.bgHover, 0))
    scale: mouse.pressed ? Theme.press : 1
    Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast); easing.type: Theme.easeOut } }
    border.width: activeFocus ? 1 : 0
    border.color: Theme.alpha(Theme.accent, 0.6)
    Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }

    Icon { anchors.centerIn: parent; name: root.name; size: 16; color: root.tone }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
    ToolTipHint { text: root.hint; shown: mouse.containsMouse }
    activeFocusOnTab: true
    Keys.onPressed: (e) => { if (e.key === Qt.Key_Space || e.key === Qt.Key_Return) { root.clicked(); e.accepted = true } }
    Accessible.role: Accessible.Button
    Accessible.name: root.hint
}
