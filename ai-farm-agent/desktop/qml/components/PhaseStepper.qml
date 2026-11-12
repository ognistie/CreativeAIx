// Etapas de um pedido: Entender → Planejar → Executar → Concluir. A atual pulsa de leve; as
// anteriores ficam marcadas. Compacto o bastante para morar no cabecalho do cartao do agente.
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root
    property int current: 0              // 0..3; 4 = tudo concluido
    property bool failed: false
    readonly property var labels: ["Entender", "Planejar", "Executar", "Concluir"]
    spacing: 6

    Repeater {
        model: root.labels
        RowLayout {
            id: stepItem
            spacing: 6
            readonly property bool done: index < root.current
            readonly property bool now: index === root.current
            Rectangle {
                Layout.preferredWidth: 18
                Layout.preferredHeight: 18
                radius: 9
                color: stepItem.done ? Theme.alpha(Theme.success, 0.18)
                     : stepItem.now ? Theme.alpha(root.failed ? Theme.danger : Theme.accent, 0.18) : Theme.bgChip
                Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durNormal) } }
                Icon {
                    anchors.centerIn: parent
                    visible: stepItem.done
                    name: "check"; size: 11; color: Theme.success
                }
                Rectangle {
                    anchors.centerIn: parent
                    visible: !stepItem.done
                    width: 6; height: 6; radius: 3
                    color: stepItem.now ? (root.failed ? Theme.danger : Theme.accent) : Theme.textTertiary
                    SequentialAnimation on opacity {
                        running: stepItem.now && !root.failed && Theme.motion
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.35; duration: 700; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1.0; duration: 700; easing.type: Easing.InOutSine }
                    }
                }
            }
            Text {
                text: modelData
                color: stepItem.now ? Theme.textPrimary : Theme.textTertiary
                font.family: Theme.fontSans
                font.pixelSize: Theme.sizeSm
                font.weight: stepItem.now ? Font.DemiBold : Font.Normal
            }
            Rectangle {
                visible: index < root.labels.length - 1
                Layout.preferredWidth: 14
                Layout.preferredHeight: 1
                color: Theme.hairlineHi
            }
        }
    }
    Accessible.role: Accessible.ProgressBar
    Accessible.name: "Etapa: " + (root.labels[Math.min(root.current, 3)] || "")
}
