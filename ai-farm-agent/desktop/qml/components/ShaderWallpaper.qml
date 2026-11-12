// Fundo em malha (gradiente organico em GPU, shaders/mesh.frag) com as 4 cores da paleta do tema.
// Ambiente, nao protagonista: renderiza em meia resolucao, avanca a ~30 quadros por segundo e so quando
// deve se mover (fluxo diferente de parado, "luzes paradas" desligado, janela visivel). Trocar de paleta
// faz crossfade das cores sem recriar nada. Sem GPU quem usa este componente mostra as luzes (Ambient).
import QtQuick

Item {
    id: root
    property var tones: Theme.tones
    property real strength: 0.9          // ate 0.9: o contraste do vidro foi medido com as luzes a 90%
    property real speed: Theme.flowSpeed // 0 parado .. 1 normal
    property bool running: true          // o dono desliga quando a janela esta minimizada ou na abertura
    property real quality: 0.5           // escala da textura (0.5 = meia resolucao; fundo difuso nao perde nada)
    property real time: 0

    Timer {
        interval: 33                     // ~30 fps: fundo lento nao precisa de 60
        repeat: true
        running: root.visible && root.running && root.speed > 0
        onTriggered: root.time += 0.033 * 5 * root.speed
    }

    Item {
        anchors.fill: parent
        layer.enabled: true
        layer.smooth: true
        layer.textureSize: Qt.size(Math.max(2, Math.round(width * root.quality)),
                                   Math.max(2, Math.round(height * root.quality)))

        ShaderEffect {
            id: fx
            anchors.fill: parent
            fragmentShader: "shaders/mesh.frag.qsb"
            property real time: root.time
            property real aspect: height > 0 ? width / height : 1
            property real grain: 1.0
            property real strength: root.strength
            property color c0: root.tones[0]
            property color c1: root.tones[1]
            property color c2: root.tones[2]
            property color c3: root.tones[3]
            Behavior on c0 { ColorAnimation { duration: Theme.dur(450) } }
            Behavior on c1 { ColorAnimation { duration: Theme.dur(450) } }
            Behavior on c2 { ColorAnimation { duration: Theme.dur(450) } }
            Behavior on c3 { ColorAnimation { duration: Theme.dur(450) } }
            Behavior on strength { NumberAnimation { duration: Theme.dur(Theme.durSlow) } }
        }
    }
}
