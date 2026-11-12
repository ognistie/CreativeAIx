// Painel de vidro sobre o ambiente. Com GPU, o fundo atras do painel e desfocado de verdade
// (ShaderEffectSource do Ambient + MultiEffect, recortado nos cantos); no renderizador por
// software (smoke de QML, maquinas sem GPU) o Loader fica inativo e sobra o vidro translucido
// de sempre: mesma leitura, sem shader e sem aviso. A sombra e um retangulo deslocado.
import QtQuick
import QtQuick.Effects

Item {
    id: root
    default property alias content: body.data
    property real radius: Theme.rLg
    property color fill: Theme.bgGlass
    property bool raised: true
    property real padding: 0
    property bool blur: Theme.blur
    // Posicao do painel dentro do fundo (para recortar a regiao que ele desfoca)
    property point origin: Qt.point(0, 0)
    function place() {
        if (Theme.backdrop) origin = root.mapToItem(Theme.backdrop, 0, 0)
    }
    onXChanged: place()
    onYChanged: place()
    onWidthChanged: place()
    onHeightChanged: place()
    Component.onCompleted: place()

    // Sombra macia so no claro: camadas que crescem e esmaecem (um desfoque sem shader). Profundidade
    // no lugar de borda; no escuro o deslocamento aparecia como uma "aba" embaixo.
    Repeater {
        model: root.raised && !Theme.dark ? 4 : 0
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: -index + 2
            anchors.leftMargin: -index
            anchors.rightMargin: -index
            anchors.bottomMargin: -index * 2 - 2
            radius: root.radius + index
            color: Theme.shadowSoft
        }
    }
    Loader {
        id: blurLayer
        anchors.fill: parent
        active: root.blur && Theme.backdrop !== null && root.visible
                && GraphicsInfo.api !== GraphicsInfo.Software && GraphicsInfo.api !== GraphicsInfo.Unknown
        sourceComponent: Component {
            Item {
                ShaderEffectSource {
                    id: behind
                    sourceItem: Theme.backdrop
                    sourceRect: Qt.rect(root.origin.x, root.origin.y, root.width, root.height)
                    live: true
                    visible: false
                    smooth: true
                }
                Rectangle {
                    id: mask
                    anchors.fill: parent
                    radius: root.radius
                    color: "black"
                    visible: false
                    layer.enabled: true
                }
                MultiEffect {
                    anchors.fill: parent
                    source: behind
                    autoPaddingEnabled: false
                    blurEnabled: true
                    blur: 1.0
                    blurMax: 40
                    maskEnabled: true
                    maskSource: mask
                    maskThresholdMin: 0.5
                    maskSpreadAtMin: 1.0
                }
                // Paineis dentro de listas roladas mudam de lugar sem mudar x/y: reposiciona de vez em quando
                Timer { interval: 200; repeat: true; running: true; onTriggered: root.place() }
            }
        }
    }
    Rectangle {
        anchors.fill: parent
        radius: root.radius
        // Com papel de parede, o vidro ganha o reforco medido para o texto ler sobre a parte clara da foto
        color: Theme.glassBoost > 0 ? Qt.rgba(root.fill.r, root.fill.g, root.fill.b, Math.min(0.96, root.fill.a + Theme.glassBoost)) : root.fill
        // escuro: borda de luz interna; claro: sem borda (a sombra separa); claro com foto: borda de luz branca (vidro fosco)
        border.width: Theme.photoLight ? 1 : Theme.edgeWidth
        border.color: Theme.photoLight ? Theme.glassEdge : Theme.edge
        Rectangle {               // reflexo suave no alto do vidro (escuro)
            visible: Theme.dark
            anchors.fill: parent
            radius: root.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.sheen }
                GradientStop { position: 0.35; color: "transparent" }
            }
        }
        Rectangle {               // brilho do topo
            anchors.top: parent.top
            anchors.topMargin: 1
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - root.radius * 2
            height: 1
            color: Theme.glassEdge
        }
    }
    Item {
        id: body
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
