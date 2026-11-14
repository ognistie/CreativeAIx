// Opcao selecionavel em pilula. Selecionada = tinta da cor de destaque.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string text: ""
    property string icon: ""
    property bool selected: false
    property color swatch: "transparent"     // bolinha de cor opcional
    signal clicked()

    implicitWidth: row.implicitWidth + 22
    implicitHeight: 30
    radius: Math.min(height / 2, Theme.rMd + 4)
    // Estilo "quieto": repouso em superficie leve sem borda; escolhido vira tinta cheia (como os filtros do estudo)
    color: selected ? Theme.primary : (mouse.containsMouse ? Theme.bgRowHover : Theme.bgChip)
    border.width: 0
    scale: mouse.pressed ? Theme.press : 1
    Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast) } }
    Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Rectangle {
            visible: root.swatch.a > 0
            width: 12; height: 12; radius: 6
            color: root.swatch
            border.width: 1
            border.color: Theme.hairlineHi
        }
        Icon {
            visible: root.icon !== ""
            // `icon` aceita o nome do desenho ("bolt") ou o glifo antigo de um caractere
            name: root.icon.length > 1 ? root.icon : ""
            glyph: root.icon.length === 1 ? root.icon : ""
            size: 12
            color: root.selected ? Theme.textInverse : Theme.textSecondary
        }
        Text {
            visible: root.text !== ""
            text: root.text
            color: root.selected ? Theme.textInverse : Theme.textSecondary
            font.family: Theme.fontSans
            font.pixelSize: Theme.sizeSm + 1
            font.weight: root.selected ? Font.Medium : Font.Normal
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
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
    Accessible.role: Accessible.RadioButton
    Accessible.name: root.text
    Accessible.checked: root.selected
}
