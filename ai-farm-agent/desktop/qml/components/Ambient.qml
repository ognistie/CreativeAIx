// Ambiente: a camada de fundo atras de toda a interface (wallpaper, depois veu de leitura, depois o app).
// Com GPU: malha organica em shader (ShaderWallpaper) com as cores da paleta. Sem GPU ou com a malha
// desligada: as luzes classicas (manchas de gradiente radial em deriva lenta). A foto de parede, quando
// escolhida, fica por cima disso. O vidro canelado (opcional) refrata o fundo inteiro, nunca a interface.
// Theme.motion = false (ou fluxo "parado") deixa tudo parado. Nada aqui recebe clique.
import QtQuick

Rectangle {
    id: root
    color: Theme.splashBase
    property real intensity: 1.0
    property bool animate: Theme.motion
    // Ponto de luz que segue o cursor (sutil): o app parece responder ao movimento
    property bool follow: false
    property point pointer: Qt.point(width * 0.5, height * 0.4)
    readonly property bool gpu: GraphicsInfo.api !== GraphicsInfo.Software && GraphicsInfo.api !== GraphicsInfo.Unknown
    readonly property bool meshOn: gpu && Theme.mesh && Theme.wallpaperUrl === ""
    readonly property bool flutedOn: gpu && Theme.fluted

    component Blob: Canvas {
        id: blob
        property color tone: "white"
        property real strength: 0.9
        property real driftX: 40
        property real driftY: 30
        property int period: 9000
        property real baseX: 0
        property real baseY: 0
        x: baseX
        y: baseY
        renderStrategy: Canvas.Cooperative
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const r = width / 2
            const g = ctx.createRadialGradient(r, r, 0, r, r, r)
            const c = (a) => "rgba(" + Math.round(tone.r * 255) + "," + Math.round(tone.g * 255)
                            + "," + Math.round(tone.b * 255) + "," + a + ")"
            g.addColorStop(0.0, c(strength))
            g.addColorStop(0.45, c(strength * 0.55))
            g.addColorStop(1.0, c(0))
            ctx.fillStyle = g
            ctx.fillRect(0, 0, width, height)
        }
        transform: Translate { id: drift }
        SequentialAnimation {
            loops: Animation.Infinite
            running: blob.visible && root.visible && root.animate
            NumberAnimation { target: drift; property: "x"; to: blob.driftX; duration: blob.period; easing.type: Easing.InOutSine }
            NumberAnimation { target: drift; property: "x"; to: 0; duration: blob.period; easing.type: Easing.InOutSine }
        }
        SequentialAnimation {
            loops: Animation.Infinite
            running: blob.visible && root.visible && root.animate
            NumberAnimation { target: drift; property: "y"; to: blob.driftY; duration: blob.period * 1.3; easing.type: Easing.InOutSine }
            NumberAnimation { target: drift; property: "y"; to: 0; duration: blob.period * 1.3; easing.type: Easing.InOutSine }
        }
        onWidthChanged: requestPaint()
        onToneChanged: requestPaint()
        onStrengthChanged: requestPaint()
    }

    // Tudo o que o vidro canelado refrata
    Item {
        id: scene
        anchors.fill: parent

        Rectangle { anchors.fill: parent; color: Theme.splashBase }

        // Malha em GPU (tema ambiente): substitui as luzes quando nao ha foto
        Loader {
            id: meshLoader
            objectName: "meshLayer"
            anchors.fill: parent
            active: root.meshOn
            sourceComponent: ShaderWallpaper {
                strength: 0.9 * root.intensity
                running: root.animate
            }
        }

        // Papel de parede (E4): a foto preenche sem esticar (recorte proporcional), com escurecimento
        // ajustavel para leitura; as luzes continuam por cima, mais suaves
        Image {
            id: photo
            anchors.fill: parent
            visible: Theme.wallpaperUrl !== ""
            source: Theme.wallpaperUrl
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            smooth: true
            mipmap: true          // reduz a imagem grande (2880 px) para a tela sem serrilhar
        }
        Rectangle {
            anchors.fill: parent
            visible: photo.visible
            // So no escuro: no claro o veu branco deixava a pintura "nublada"; la a leitura vem do vidro atras do texto
            color: Qt.rgba(0, 0, 0, Theme.dark ? Theme.photoVeil : 0)
        }
        // Vinheta suave em cima e embaixo: o texto le melhor e a pintura continua inteira no centro
        Rectangle {
            anchors.fill: parent
            visible: photo.visible && Theme.dark
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.alpha(Theme.splashBase, 0.35) }
                GradientStop { position: 0.25; color: "transparent" }
                GradientStop { position: 0.7; color: "transparent" }
                GradientStop { position: 1.0; color: Theme.alpha(Theme.splashBase, 0.55) }
            }
        }

        Item {
            id: field
            anchors.fill: parent
            clip: true
            visible: !root.meshOn
            opacity: root.intensity * (photo.visible ? 0.18 : 1)   // sobre a foto as luzes so insinuam: a pintura fica com as cores dela
            Behavior on opacity { NumberAnimation { duration: Theme.dur(Theme.durSlow) } }
            readonly property real d: Math.max(width, height) * 0.75

            Blob { tone: Theme.splashPeach;  width: field.d; height: width
                   baseX: -field.d * 0.32; baseY: -field.d * 0.30; driftX: 70; driftY: 50; period: 9000 }
            Blob { tone: Theme.splashOrange; width: field.d * 0.85; height: width
                   baseX: field.width - field.d * 0.55; baseY: -field.d * 0.38; driftX: -60; driftY: 60; period: 11000 }
            Blob { tone: Theme.splashLilac;  width: field.d * 1.05; height: width
                   baseX: field.width * 0.38; baseY: field.height - field.d * 0.55; driftX: -80; driftY: -40; period: 10000 }
            Blob { tone: Theme.splashLilac;  width: field.d * 0.7; height: width; strength: 0.55
                   baseX: -field.d * 0.25; baseY: field.height - field.d * 0.35; driftX: 50; driftY: -30; period: 12000 }
        }
    }

    // Vidro canelado (reeded glass): refrata a cena inteira; a interface fica acima, sem distorcao
    Loader {
        objectName: "flutedLayer"
        anchors.fill: parent
        active: root.flutedOn
        sourceComponent: ShaderEffect {
            fragmentShader: "shaders/fluted.frag.qsb"
            property variant source: ShaderEffectSource { sourceItem: scene; hideSource: true; live: true }
            property real time: 0
            property real ribs: Math.max(24, Math.round(width / 26))
            property real amount: 1.0
            property real pointer: root.width > 0 ? root.pointer.x / root.width : 0.5
            Behavior on pointer { enabled: root.animate; NumberAnimation { duration: Theme.dur(900); easing.type: Easing.OutCubic } }
            NumberAnimation on time {
                from: 0; to: 6.2832; duration: 24000; loops: Animation.Infinite
                running: root.animate && Theme.flowSpeed > 0
            }
        }
    }

    // Luz do cursor: um brilho do destaque que acompanha o mouse devagar
    Blob {
        visible: root.follow
        tone: Theme.accent
        strength: 0.10; driftX: 0; driftY: 0
        width: 520; height: 520
        baseX: root.pointer.x - 260
        baseY: root.pointer.y - 260
        Behavior on baseX { enabled: root.animate; NumberAnimation { duration: Theme.dur(900); easing.type: Easing.OutCubic } }
        Behavior on baseY { enabled: root.animate; NumberAnimation { duration: Theme.dur(900); easing.type: Easing.OutCubic } }
    }
}
