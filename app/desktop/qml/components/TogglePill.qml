// Opcao liga/desliga compacta (ex.: "Simular" dentro do composer).
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string text: ""
    property string icon: ""
    property bool checked: false
    property string tooltip: ""
    // manual: o estado vem de fora (ex.: Conversa ao vivo); a pilula so avisa com toggled()
    property bool manual: false
    signal toggled()
    function toggle() { if (!manual) checked = !checked; toggled() }

    implicitWidth: row.implicitWidth + 20
    implicitHeight: 28
    radius: height / 2
    // Claro com foto (vidro fosco): pilula branca translucida, sem contorno
    color: checked ? Theme.alpha(Theme.primary, 0.12)
                   : Theme.photoLight ? Theme.alpha(Theme.bgSurface, mouse.containsMouse ? 0.85 : 0.55)
                   : (mouse.containsMouse ? Theme.bgHover : Theme.alpha(Theme.bgHover, 0))
    border.width: Theme.photoLight && !checked ? 0 : 1
    border.color: checked ? Theme.alpha(Theme.primary, 0.35) : Theme.hairline
    Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Icon {
            visible: root.icon !== ""
            glyph: root.icon
            size: 12
            color: root.checked ? Theme.textPrimary : Theme.textSecondary
        }
        Text {
            text: root.text
            color: root.checked ? Theme.textPrimary : Theme.textSecondary
            font.family: Theme.fontSans
            font.pixelSize: Theme.sizeSm
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.toggle()
    }

    ToolTipHint { text: root.tooltip; shown: mouse.containsMouse && root.tooltip !== "" }

    // Teclado: Tab chega aqui, Enter/Espaco acionam, anel de foco visivel (nunca so cor de hover)
    activeFocusOnTab: enabled && visible
    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Space || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) { root.toggle(); e.accepted = true }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: root.radius + 3
        color: "transparent"
        border.width: 2
        border.color: Theme.focusRing
        visible: root.activeFocus
        z: 10
    }
    Accessible.role: Accessible.CheckBox
    Accessible.name: root.text
    Accessible.checked: root.checked
}
