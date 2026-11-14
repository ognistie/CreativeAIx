// Botao com tres variantes: primary (fundo claro), secondary (contorno)
// e ghost (so texto). `icon` opcional usa Segoe Fluent Icons.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string text: ""
    property string icon: ""
    property string variant: "secondary"   // primary | secondary | ghost
    property bool compact: false
    signal clicked()

    readonly property bool isPrimary: variant === "primary"
    readonly property color fg: isPrimary ? Theme.textInverse
                                          : (variant === "ghost" ? Theme.textSecondary : Theme.textPrimary)

    implicitWidth: row.implicitWidth + (compact ? 20 : 28)
    implicitHeight: compact ? 30 : 36
    radius: height / 2
    opacity: enabled ? 1 : 0.4
    color: {
        if (isPrimary) return mouse.pressed ? Qt.darker(Theme.primary, 1.15) : Theme.primary
        if (mouse.pressed) return Theme.bgPressed
        if (mouse.containsMouse) return Theme.bgHover
        return "transparent"
    }
    border.width: variant === "secondary" ? 1 : 0
    border.color: Theme.hairlineHi

    scale: mouse.pressed ? Theme.press : 1
    Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast); easing.type: Theme.easeOut } }
    Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Icon {
            visible: root.icon !== ""
            name: root.icon.length > 1 ? root.icon : ""      // nome do icone ("flask") ou glifo (1 caractere)
            glyph: root.icon.length === 1 ? root.icon : ""
            size: root.compact ? 12 : 14
            color: root.fg
        }
        Text {
            visible: root.text !== ""
            text: root.text
            color: root.fg
            font.family: Theme.fontSans
            font.pixelSize: root.compact ? Theme.sizeSm : 13
            font.weight: Font.Medium
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    // Teclado: Tab chega aqui, Enter/Espaco acionam, anel de foco visivel (nunca so cor de hover)
    activeFocusOnTab: enabled && visible
    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Space || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) { root.clicked(); e.accepted = true }
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
    Accessible.role: Accessible.Button
    Accessible.name: root.text
}
