// Esqueleto de carregamento: a silhueta do conteudo que vem, pulsando de leve (parada com "luzes paradas").
// Use no lugar de um spinner solto quando o formato do conteudo e conhecido.
import QtQuick

Rectangle {
    id: root
    radius: Theme.r1
    color: Theme.bgChip
    SequentialAnimation on opacity {
        running: Theme.motion && root.visible
        loops: Animation.Infinite
        NumberAnimation { to: 0.45; duration: 800; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1.0; duration: 800; easing.type: Easing.InOutSine }
    }
}
