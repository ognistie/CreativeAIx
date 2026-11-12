// Orbe da tarefa e da voz: uma esfera pequena com gradiente de ceu e uma faixa de nuvem. Ela representa o
// que esta acontecendo sem texto: executando (anel girando e nuvem em deriva), ouvindo (nevoa que segue o
// nivel REAL do microfone), falando (respiracao lenta), precisa de voce (pulso ambar), falhou (ponto
// vermelho), concluido (brilho verde que some). Nada pisca sem causa; "luzes paradas" deixa tudo parado.
import QtQuick
import QtQuick.Shapes

Item {
    id: root
    // idle | running | listening | thinking | speaking | attention | done | failed
    property string state_: "idle"
    property real level: 0                  // 0..1, nivel do microfone (o mesmo do composer)
    property real size: 64
    property color tint: Theme.accent
    implicitWidth: size
    implicitHeight: size

    readonly property bool busy: state_ === "running" || state_ === "thinking"
    readonly property bool hearing: state_ === "listening"
    readonly property color sky: tint
    readonly property color haze: Qt.tint(Qt.lighter(tint, 1.9), Qt.rgba(1, 1, 1, 0.55))

    // Nivel suavizado (ataque rapido, queda lenta), so enquanto ouve
    property real energy: 0
    Timer {
        interval: 33; repeat: true
        running: root.visible && root.hearing && Theme.motion
        onTriggered: {
            const target = root.level > 0.04 ? Math.min(1, root.level) : 0
            root.energy += (target - root.energy) * (target > root.energy ? 0.35 : 0.08)
        }
    }
    onHearingChanged: if (!hearing) energy = 0

    // ── Brilho externo: voz (nivel real) ou estado ────────────────────
    Shape {
        id: glow
        anchors.centerIn: parent
        width: root.size * 1.6
        height: width
        opacity: root.hearing ? 0.35 + 0.65 * root.energy
               : root.state_ === "speaking" ? breath.v
               : root.state_ === "attention" ? pulse.v
               : root.busy ? 0.35 : 0.18
        scale: root.hearing ? 0.85 + 0.3 * root.energy : 1
        Behavior on opacity { NumberAnimation { duration: Theme.dur(Theme.durNormal) } }
        Behavior on scale { NumberAnimation { duration: Theme.dur(90) } }
        readonly property color c: root.state_ === "attention" ? Theme.warning
                                 : root.state_ === "failed" ? Theme.danger : root.sky
        ShapePath {
            strokeWidth: -1
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: glow.width / 2; centerY: glow.height / 2; centerRadius: glow.width / 2
                focalX: glow.width / 2; focalY: glow.height / 2
                GradientStop { position: 0.55; color: Theme.alpha(glow.c, 0.55) }
                GradientStop { position: 1.0; color: Theme.alpha(glow.c, 0) }
            }
            startX: 0; startY: 0
            PathLine { x: glow.width; y: 0 }
            PathLine { x: glow.width; y: glow.height }
            PathLine { x: 0; y: glow.height }
            PathLine { x: 0; y: 0 }
        }
    }

    // Sombra macia (camadas, sem shader)
    Repeater {
        model: 4
        Rectangle {
            anchors.centerIn: sphere
            anchors.verticalCenterOffset: 3 + index
            width: root.size + index * 2
            height: width
            radius: width / 2
            color: Qt.rgba(0.05, 0.08, 0.2, 0.05)
        }
    }

    // ── A esfera: ceu em cima, claro embaixo ─────────────────────────
    Rectangle {
        id: sphere
        anchors.centerIn: parent
        width: root.size
        height: width
        radius: width / 2
        scale: root.state_ === "speaking" ? 1 + 0.04 * (breath.v - 0.2) : 1
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.sky }
            GradientStop { position: 0.55; color: Qt.lighter(root.sky, 1.45) }
            GradientStop { position: 1.0; color: root.haze }
        }

        // Faixa de nuvem: tres tufos elipticos com borda que some (ficam dentro da esfera, sem recorte)
        Item {
            id: clouds
            width: parent.width
            height: parent.height
            x: drift.dx
            y: drift.dy
            Puff { cx: 0.45; cy: 0.58; w: 0.78; h: 0.30; strength: 0.92 }
            Puff { cx: 0.63; cy: 0.51; w: 0.48; h: 0.22; strength: 0.75 }
            Puff { cx: 0.33; cy: 0.66; w: 0.50; h: 0.20; strength: 0.70 }
        }
    }

    // Tufo: gradiente radial num quadrado, achatado na vertical (elipse lisa, sem aneis)
    component Puff: Shape {
        id: puff
        property real cx: 0.5
        property real cy: 0.5
        property real w: 0.6
        property real h: 0.25
        property real strength: 0.9
        readonly property real d: sphere.width * w
        width: d
        height: d
        x: sphere.width * cx - d / 2
        y: sphere.height * cy - d / 2
        transform: Scale { origin.x: puff.d / 2; origin.y: puff.d / 2; yScale: puff.h / puff.w }
        ShapePath {
            strokeWidth: -1
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: puff.d / 2; centerY: puff.d / 2; centerRadius: puff.d / 2
                focalX: puff.d / 2; focalY: puff.d / 2
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, puff.strength) }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, puff.strength * 0.6) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0) }
            }
            startX: 0; startY: 0
            PathLine { x: puff.d; y: 0 }
            PathLine { x: puff.d; y: puff.d }
            PathLine { x: 0; y: puff.d }
            PathLine { x: 0; y: 0 }
        }
    }

    // Deriva da nuvem: lenta parada, mais viva executando
    QtObject { id: drift; property real dx: 0; property real dy: 0 }
    SequentialAnimation {
        running: root.visible && Theme.motion
        loops: Animation.Infinite
        NumberAnimation { target: drift; property: "dx"; to: root.size * 0.05; duration: root.busy ? 1400 : 4200; easing.type: Easing.InOutSine }
        NumberAnimation { target: drift; property: "dx"; to: -root.size * 0.05; duration: root.busy ? 1400 : 4200; easing.type: Easing.InOutSine }
    }
    SequentialAnimation {
        running: root.visible && Theme.motion && (root.busy || root.hearing)
        loops: Animation.Infinite
        NumberAnimation { target: drift; property: "dy"; to: -root.size * 0.05; duration: 900; easing.type: Easing.InOutSine }
        NumberAnimation { target: drift; property: "dy"; to: root.size * 0.03; duration: 900; easing.type: Easing.InOutSine }
    }

    // ── Anel de execucao: um arco que gira em volta ──────────────────
    Shape {
        id: ring
        anchors.centerIn: parent
        width: root.size + 10
        height: width
        visible: root.busy
        opacity: root.busy ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.dur(Theme.durNormal) } }
        ShapePath {
            strokeColor: Theme.alpha(root.sky, 0.85)
            strokeWidth: 2.5
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: ring.width / 2; centerY: ring.height / 2
                radiusX: ring.width / 2 - 2; radiusY: ring.height / 2 - 2
                startAngle: -90; sweepAngle: 90
            }
        }
        RotationAnimation on rotation {
            running: ring.visible && Theme.motion
            from: 0; to: 360; duration: root.state_ === "thinking" ? 900 : 1600; loops: Animation.Infinite
        }
    }

    // ── Selo: falhou (ponto vermelho) / concluido (check verde que some) ─
    Rectangle {
        visible: root.state_ === "attention"         // pergunta ou plano esperando: ponto ambar
        width: root.size * 0.24; height: width; radius: width / 2
        anchors.right: sphere.right; anchors.top: sphere.top
        color: Theme.warning
        border.width: 2; border.color: "white"
    }
    Rectangle {
        visible: root.state_ === "failed"
        width: root.size * 0.24; height: width; radius: width / 2
        anchors.right: sphere.right; anchors.top: sphere.top
        color: Theme.danger
        border.width: 2; border.color: "white"
    }
    Rectangle {
        id: doneBadge
        width: root.size * 0.28; height: width; radius: width / 2
        anchors.right: sphere.right; anchors.top: sphere.top
        color: Theme.success
        border.width: 2; border.color: "white"
        opacity: 0
        Icon { anchors.centerIn: parent; name: "check"; size: parent.width * 0.6; color: "white" }
    }
    onState_Changed: {
        if (state_ === "done") doneFlash.restart()
        else { doneFlash.stop(); doneBadge.opacity = 0 }
    }
    SequentialAnimation {
        id: doneFlash
        NumberAnimation { target: doneBadge; property: "opacity"; to: 1; duration: Theme.dur(Theme.durNormal) }
        PauseAnimation { duration: Theme.motion ? 2400 : 0 }
        NumberAnimation { target: doneBadge; property: "opacity"; to: 0; duration: Theme.dur(Theme.durSlow) }
    }

    // Respiracao (falando) e pulso (precisa de voce)
    QtObject { id: breath; property real v: 0.2 }
    SequentialAnimation {
        running: root.state_ === "speaking" && root.visible && Theme.motion
        loops: Animation.Infinite
        NumberAnimation { target: breath; property: "v"; from: 0.2; to: 0.6; duration: 1300; easing.type: Easing.InOutSine }
        NumberAnimation { target: breath; property: "v"; from: 0.6; to: 0.2; duration: 1300; easing.type: Easing.InOutSine }
    }
    QtObject { id: pulse; property real v: 0.6 }
    SequentialAnimation {
        running: root.state_ === "attention" && root.visible && Theme.motion
        loops: Animation.Infinite
        NumberAnimation { target: pulse; property: "v"; from: 0.25; to: 0.8; duration: 900; easing.type: Easing.InOutSine }
        NumberAnimation { target: pulse; property: "v"; from: 0.8; to: 0.25; duration: 900; easing.type: Easing.InOutSine }
    }

    Accessible.role: Accessible.Indicator
    Accessible.name: ({ idle: "Pronto", running: "Executando a tarefa", thinking: "Entendendo",
                        listening: "Ouvindo", speaking: "Falando", attention: "Precisa de você",
                        done: "Tarefa concluída", failed: "A tarefa falhou" })[root.state_] || ""
}
