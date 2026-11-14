// Brilho de voz: luz colorida que nasce da borda de baixo da caixa de pedido e reage a voz REAL.
// Usa o nivel que o app ja mede (evento voice_level do mesmo microfone); nunca abre outro microfone.
//   gravando / ouvindo -> lobulos sobem com a energia suavizada (limiar, ataque e liberacao)
//   entendendo         -> um feixe percorre a borda (movimento proprio: nao finge som recebido)
//   falando            -> respiracao baixa e lenta (nao ha sinal de saida: nao inventa nivel)
//   parado / erro      -> apagado (o estado tambem aparece em texto na caixa)
// Fica atras da caixa (z negativo no dono) e nao recebe clique.
import QtQuick

Item {
    id: root
    property string state_: "idle"       // idle | off | recording | listening | thinking | speaking
    property real level: 0               // 0..1, do backend
    property real threshold: 0.04
    property real attack: 0.35           // fracao do caminho por quadro ao subir
    property real release: 0.08          // ... ao descer (cai devagar, sem piscar)
    property real energy: 0
    readonly property bool hearing: state_ === "recording" || state_ === "listening"
    readonly property bool processing: state_ === "thinking"
    readonly property bool speaking: state_ === "speaking"
    readonly property bool lit: hearing || processing || speaking
    enabled: false

    opacity: lit ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.dur(280); easing.type: Theme.easeStandard } }

    // Suavizacao do nivel (so enquanto ouve; sem "luzes paradas" o brilho fica fixo e baixo)
    Timer {
        interval: 33
        repeat: true
        running: root.visible && root.hearing && Theme.motion
        onTriggered: {
            const target = root.level > root.threshold ? Math.min(1, root.level) : 0
            const k = target > root.energy ? root.attack : root.release
            root.energy += (target - root.energy) * k
        }
    }
    onHearingChanged: if (!hearing) energy = 0
    readonly property real e: !Theme.motion ? (hearing ? 0.25 : 0) : energy
    readonly property real base: hearing ? 0.22 : 0          // ouvindo em silencio: brilho baixo, nao zero

    component Lobe: Canvas {
        id: lobe
        property color tone: Theme.accent
        property real strength: 0.55
        renderStrategy: Canvas.Cooperative
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const r = width / 2
            const g = ctx.createRadialGradient(r, r, 0, r, r, r)
            const c = (a) => "rgba(" + Math.round(tone.r * 255) + "," + Math.round(tone.g * 255)
                            + "," + Math.round(tone.b * 255) + "," + a + ")"
            g.addColorStop(0.0, c(strength))
            g.addColorStop(0.5, c(strength * 0.4))
            g.addColorStop(1.0, c(0))
            ctx.fillStyle = g
            ctx.fillRect(0, 0, width, height)
        }
        onWidthChanged: requestPaint()
        onToneChanged: requestPaint()
    }

    readonly property real lobeW: Math.max(160, width * 0.42)
    // Tres lobulos com intensidades e alturas distintas (centro mais forte, bordas atrasadas)
    Repeater {
        model: [
            { x: 0.18, tone: "phosphor", gain: 0.75 },
            { x: 0.50, tone: "accent",   gain: 1.00 },
            { x: 0.82, tone: "focus",    gain: 0.85 }
        ]
        Lobe {
            readonly property real g: modelData.gain
            tone: modelData.tone === "accent" ? Theme.accent : (modelData.tone === "focus" ? Theme.focusRing : Theme.phosphor)
            strength: Theme.dark ? 0.55 : 0.38
            width: root.lobeW
            height: width
            x: root.width * modelData.x - width / 2
            y: root.height - height / 2
            visible: root.hearing || root.speaking
            transformOrigin: Item.Center
            // expansao nao linear: sussurro mal acende, voz forte abre
            scale: 0.55 + 0.75 * Math.pow(root.base + root.e * g, 0.8)
            opacity: Math.min(1, root.base + root.e * g + (root.speaking ? breath.v : 0))
            Behavior on scale { NumberAnimation { duration: Theme.dur(90) } }
        }
    }

    // Falando: respiracao lenta e baixa
    QtObject { id: breath; property real v: 0 }
    SequentialAnimation {
        running: root.speaking && root.visible && Theme.motion
        loops: Animation.Infinite
        NumberAnimation { target: breath; property: "v"; from: 0.15; to: 0.40; duration: 1400; easing.type: Easing.InOutSine }
        NumberAnimation { target: breath; property: "v"; from: 0.40; to: 0.15; duration: 1400; easing.type: Easing.InOutSine }
    }

    // Entendendo: feixe que percorre a borda de baixo
    Lobe {
        id: beam
        visible: root.processing
        tone: Theme.focusRing
        strength: Theme.dark ? 0.7 : 0.45
        width: Math.max(120, root.width * 0.34)
        height: width * 0.5
        y: root.height - height / 2
        x: Theme.motion ? beamX.value : (root.width - width) / 2
        QtObject { id: beamX; property real value: -beam.width }
        SequentialAnimation {
            running: root.processing && root.visible && Theme.motion
            loops: Animation.Infinite
            NumberAnimation { target: beamX; property: "value"; from: -beam.width * 0.5; to: root.width - beam.width * 0.5
                              duration: 1500; easing.type: Easing.InOutSine }
            NumberAnimation { target: beamX; property: "value"; from: root.width - beam.width * 0.5; to: -beam.width * 0.5
                              duration: 1500; easing.type: Easing.InOutSine }
        }
    }
}
