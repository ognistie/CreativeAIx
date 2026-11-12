// Entrada escalonada de um item de lista: aparece com atraso proporcional a posicao (Theme.stagger).
// Uso: dentro do delegate, `opacity: C.Theme.motion ? 0 : 1` e `C.Enter { target: parent; order: index }`.
// Com "luzes paradas" as duracoes sao 0 (Theme.dur) e o item ja nasce visivel.
import QtQuick

SequentialAnimation {
    id: root
    property Item target: null
    property int order: 0
    running: false
    Component.onCompleted: if (target) start()
    PauseAnimation { duration: Theme.dur(Math.min(root.order, 8) * Theme.stagger) }
    NumberAnimation { target: root.target; property: "opacity"; from: 0; to: 1
                      duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut }
}
