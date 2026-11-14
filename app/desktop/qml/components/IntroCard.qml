// Introducao de uma tela: o que da para fazer ali e como, em passos curtos.
// "Entendi" recolhe para uma pilula "Como usar" (lembrado entre aberturas do app).
import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property string key: ""            // brain | you | harness
    property string title: ""
    property string place: ""          // "o Cérebro": recolhido vira "Como usar o Cérebro"
    property string lead: ""
    property var steps: []             // [[icone, titulo, texto], ...]
    property bool open: true
    // Pouca altura (janela reduzida): mostra a pilula sem mudar a escolha salva; um clique abre mesmo assim
    property bool squeeze: false
    property bool peek: false
    readonly property bool shown: open && (!squeeze || peek)

    implicitHeight: shown ? card.implicitHeight : pill.implicitHeight
    Behavior on implicitHeight { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Easing.OutCubic } }
    clip: true

    Component.onCompleted: {
        try { open = !(JSON.parse(Bridge.introSeen())[key] === true) } catch (e) { open = true }
    }
    function setOpen(v) {
        open = v
        Bridge.setIntroSeen(key, !v)
    }

    GlassPanel {
        id: card
        visible: root.shown
        width: parent.width
        implicitHeight: col.implicitHeight + 36
        fill: Theme.bgGlassHi
        ColumnLayout {
            id: col
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 18
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Eyebrow { text: "Como usar"; dot: true }
                    Text { text: root.title; color: Theme.textPrimary; font.family: Theme.fontDisplay
                           font.pixelSize: Theme.sizeLg + 1; font.weight: Theme.weightTitle }
                    Text { Layout.fillWidth: true; text: root.lead; wrapMode: Text.Wrap; color: Theme.textSecondary
                           font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm + 1 }
                }
                Button { text: "Entendi"; compact: true; onClicked: { root.peek = false; root.setOpen(false) } }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: width > 720 ? root.steps.length : 1
                columnSpacing: 12
                rowSpacing: 10
                Repeater {
                    model: root.steps
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        spacing: 10
                        Text {
                            Layout.alignment: Qt.AlignTop
                            Layout.topMargin: 2
                            text: (index < 9 ? "0" : "") + (index + 1)
                            color: Theme.accent
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.sizeSm
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            RowLayout {
                                spacing: 6
                                Icon { name: modelData[0]; size: 13; color: Theme.textPrimary }
                                Text { text: modelData[1]; color: Theme.textPrimary; font.family: Theme.fontSans
                                       font.pixelSize: Theme.sizeMd; font.weight: Font.Medium }
                            }
                            Text { Layout.fillWidth: true; text: modelData[2]; wrapMode: Text.Wrap; color: Theme.textSecondary
                                   font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm + 1; lineHeight: 1.15 }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: pill
        visible: !root.shown
        implicitWidth: pillRow.implicitWidth + 24
        implicitHeight: 30
        radius: 15
        color: pillMouse.containsMouse ? Theme.bgGlassHi : Theme.bgChip
        border.width: 1
        border.color: Theme.hairline
        RowLayout {
            id: pillRow
            anchors.centerIn: parent
            spacing: 6
            Icon { name: "help"; size: 13; color: Theme.textSecondary }
            Text { text: "Como usar " + root.place; color: Theme.textSecondary
                   font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm + 1 }
        }
        MouseArea { id: pillMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: { root.peek = true; root.setOpen(true) } }
        Accessible.role: Accessible.Button
        Accessible.name: "Mostrar a introdução"
    }
}
