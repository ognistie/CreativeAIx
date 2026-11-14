// Controle segmentado: um trilho e uma marca que desliza ate a opcao escolhida. Para escolhas exclusivas e
// curtas (2 a 4) num lugar so, como o agente do cabecalho. Setas trocam a opcao; Tab entra e sai do grupo.
import QtQuick

Rectangle {
    id: root
    property var options: []            // [[valor, rotulo, icone]]
    property string value: ""
    property string label: ""           // nome para o leitor de tela
    signal picked(string value)

    readonly property int current: Math.max(0, options.findIndex(o => o[0] === value))
    implicitWidth: row.implicitWidth + 6
    implicitHeight: 32
    radius: height / 2
    color: Theme.bgChip
    border.width: 1
    border.color: Theme.hairline

    // Marca da opcao escolhida
    Rectangle {
        readonly property Item target: rep.count > root.current ? rep.itemAt(root.current) : null
        visible: !!target
        x: target ? row.x + target.x : 0
        y: 3
        width: target ? target.width : 0
        height: root.height - 6
        radius: height / 2
        color: Theme.primary
        Behavior on x { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }
        Behavior on width { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }
    }
    Row {
        id: row
        x: 3
        anchors.verticalCenter: parent.verticalCenter
        Repeater {
            id: rep
            model: root.options
            Item {
                readonly property bool on: index === root.current
                width: seg.implicitWidth + 24
                height: root.height - 6
                Row {
                    id: seg
                    anchors.centerIn: parent
                    spacing: 6
                    Icon { visible: modelData[2] !== undefined && modelData[2] !== ""; anchors.verticalCenter: parent.verticalCenter
                           name: modelData[2] || ""; size: 12
                           color: on ? Theme.textInverse : (segMouse.containsMouse ? Theme.textPrimary : Theme.textSecondary) }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: modelData[1]
                           color: on ? Theme.textInverse : (segMouse.containsMouse ? Theme.textPrimary : Theme.textSecondary)
                           font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm + 1
                           font.weight: on ? Font.Medium : Font.Normal }
                }
                MouseArea { id: segMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: root.picked(modelData[0]) }
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData[1]
                Accessible.checked: on
            }
        }
    }
    activeFocusOnTab: true
    Keys.onPressed: (e) => {
        if (!options.length) return
        if (e.key === Qt.Key_Right || e.key === Qt.Key_Down) { root.picked(options[(current + 1) % options.length][0]); e.accepted = true }
        else if (e.key === Qt.Key_Left || e.key === Qt.Key_Up) { root.picked(options[(current - 1 + options.length) % options.length][0]); e.accepted = true }
    }
    Rectangle {
        anchors.fill: parent; anchors.margins: -3; radius: root.radius + 3
        color: "transparent"; border.width: 2; border.color: Theme.focusRing
        visible: root.activeFocus
    }
    Accessible.role: Accessible.Grouping
    Accessible.name: root.label
}
