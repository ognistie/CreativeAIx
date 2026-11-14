// Menu de contexto no estilo do app: vidro claro, cantos arredondados, itens com
// icone opcional e destaque suave. Itens: AppMenuItem { text; icon; danger }.
import QtQuick
import QtQuick.Controls

Menu {
    id: menu
    padding: 6
    implicitWidth: 220

    background: Rectangle {
        implicitWidth: 220
        radius: Theme.rMd
        color: Theme.bgGlassHi
        border.width: 1
        border.color: Theme.hairline
        Rectangle {           // sombra simples (sem shader)
            z: -1
            anchors.fill: parent
            anchors.topMargin: 6
            anchors.bottomMargin: -6
            radius: parent.radius
            color: Qt.rgba(0.2, 0.15, 0.3, 0.08)
        }
    }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.dur(Theme.durFast) } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.dur(Theme.durFast) } }
}
