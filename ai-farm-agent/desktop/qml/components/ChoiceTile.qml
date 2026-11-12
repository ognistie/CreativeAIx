// Escolha em bloco de vidro: icone, titulo, uma linha de ajuda e o selo ✓ quando escolhido.
// Para opcoes que se excluem (tema, modo de visualizacao, agente).
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string icon: ""
    property string title: ""
    property string hint: ""
    property bool selected: false
    signal clicked()

    implicitWidth: 150
    implicitHeight: 78
    radius: Theme.r3
    color: selected ? Theme.bgGlassHi : (mouse.containsMouse ? Theme.bgRowHover : Theme.bgChip)
    border.width: selected ? 2 : 0
    border.color: Theme.accent
    scale: mouse.pressed ? Theme.press : 1
    Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }
    Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast); easing.type: Theme.easeOut } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4
        Icon { name: root.icon; size: 18; color: root.selected ? Theme.accent : Theme.textSecondary }
        Item { Layout.fillHeight: true }
        Text { text: root.title; color: Theme.textPrimary; font.family: Theme.fontSans
               font.pixelSize: Theme.sizeMd; font.weight: root.selected ? Font.DemiBold : Font.Medium }
        Text { visible: root.hint !== ""; text: root.hint; color: Theme.textTertiary; font.family: Theme.fontSans
               font.pixelSize: Theme.sizeXs; elide: Text.ElideRight; Layout.fillWidth: true }
    }
    Rectangle {               // selo ✓
        visible: root.selected
        anchors.top: parent.top; anchors.right: parent.right; anchors.margins: 8
        width: 18; height: 18; radius: 9
        color: Theme.accent
        Icon { anchors.centerIn: parent; name: "check"; size: 11; color: Theme.textInverse; weight: 2.2 }
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked() }
    Accessible.role: Accessible.RadioButton
    Accessible.name: root.title
    Accessible.checked: root.selected
}
