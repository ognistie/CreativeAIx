// Item da sidebar: icone + rotulo. Ativo = vidro claro com um filete da cor de
// destaque a esquerda (que cresce ao entrar); hover = leve brilho.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""
    property string icon: ""
    property bool active: false
    property bool muted: false      // itens secundarios (ex.: recentes)
    property string badge: ""       // contador opcional a direita
    property bool compact: false    // barra recolhida: so o icone, rotulo na dica
    signal clicked()

    implicitHeight: 34
    radius: Theme.rSm
    // Ativo = ponto da cor de destaque + peso do texto (sem pilula com borda); hover = fundo leve
    color: active || mouse.containsMouse ? Theme.bgRowHover : Theme.alpha(Theme.bgRowHover, 0)
    scale: mouse.pressed ? Theme.press : 1
    Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast); easing.type: Theme.easeOut } }
    Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }

    Rectangle {               // ponto do item ativo (cresce ao entrar)
        anchors.left: parent.left
        anchors.leftMargin: 3
        anchors.verticalCenter: parent.verticalCenter
        width: root.active ? 5 : 0
        height: width
        radius: width / 2
        color: Theme.accent
        Behavior on width { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: root.compact ? 0 : 12
        anchors.rightMargin: root.compact ? 0 : 10
        spacing: 10

        Icon {
            visible: root.icon !== ""
            name: root.icon.length > 1 ? root.icon : ""      // nome do desenho ("chart") ou glifo antigo
            glyph: root.icon.length === 1 ? root.icon : ""
            size: 15
            color: root.active ? Theme.accent : Theme.textSecondary
            Layout.preferredWidth: 18
            Layout.alignment: root.compact ? Qt.AlignHCenter : Qt.AlignLeft
            Layout.fillWidth: root.compact
            Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }
        }
        Text {
            visible: !root.compact
            Layout.fillWidth: true
            text: root.label
            elide: Text.ElideRight
            color: root.active ? Theme.textPrimary
                               : (root.muted ? Theme.textSecondary : Theme.textPrimary)
            font.family: Theme.fontSans
            font.pixelSize: 13
            font.weight: root.active ? Font.DemiBold : Font.Normal
        }
        Text {
            visible: root.badge !== "" && !root.compact
            text: root.badge
            color: Theme.textTertiary
            font.family: Theme.fontSans
            font.pixelSize: Theme.sizeXs
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
    ToolTipHint { text: root.label + (root.badge ? "  ·  " + root.badge : ""); shown: root.compact && mouse.containsMouse }

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
    Accessible.name: root.label
}
