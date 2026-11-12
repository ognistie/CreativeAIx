// Caixa de entrada da tarefa. Enter envia, Shift+Enter quebra linha.
// Cresce ate ~6 linhas e depois rola. Opcoes ficam dentro da caixa.
// Voz: o microfone grava uma mensagem de audio (clica, fala, envia);
// "Conversa" deixa o microfone aberto e cada fala vira pedido.
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Rectangle {
    id: root

    property alias text: input.text
    property bool running: false
    property alias dryRun: simulatePill.checked
    property alias genReport: reportPill.checked
    property string placeholder: "Descreva uma tarefa..."
    // Voz: idle | recording | listening | thinking | speaking
    property string voiceState: "idle"
    property real voiceLevel: 0
    property bool liveOn: false
    property int queued: 0
    property double recStartedAt: 0
    property string voiceHotkey: "Ctrl+Alt+V"
    // Versao do mini chat: sem as opcoes Simular/Relatorio
    property bool compact: false
    readonly property bool recording: voiceState === "recording"

    signal submitted(string task)
    signal stopRequested()
    signal micClicked()
    signal recordCancel()
    signal liveSwitched(bool on)

    function focusInput() { input.forceActiveFocus(); input.cursorPosition = input.length }

    readonly property bool canSend: !running && input.text.trim().length > 0

    // Anexos (+ ou arrastar): o pedido leva os caminhos e a conversa passa a "conhecer" os
    // arquivos — "resume esta planilha" le o arquivo de verdade
    property var attachments: []

    function addFiles(urls) {
        const list = attachments.slice()
        for (let i = 0; i < urls.length; i++) {
            let p = decodeURIComponent(urls[i].toString().replace(/^file:\/{2,3}/, ""))
            if (p && list.indexOf(p) < 0) list.push(p)
        }
        attachments = list.slice(-6)
        focusInput()
    }
    function removeFile(i) {
        const list = attachments.slice(); list.splice(i, 1); attachments = list
    }
    function baseName(p) { return p.split(/[\\/]/).pop() }

    function send() {
        if (!canSend) return
        let text = input.text.trim()
        if (attachments.length) {
            const ok = JSON.parse(Bridge.attachFiles(JSON.stringify(attachments)))
            if (ok.length) text += "\n\nArquivos anexados:\n" + ok.map(p => "- " + p).join("\n")
            attachments = []
        }
        errorText = ""
        sending = true
        submitted(text)
    }

    FileDialog {
        id: fileDialog
        title: "Anexar arquivos"
        fileMode: FileDialog.OpenFiles
        onAccepted: root.addFiles(selectedFiles)
    }

    DropArea {
        anchors.fill: parent
        onDropped: (drop) => { if (drop.hasUrls) root.addFiles(drop.urls) }
    }

    property int recSeconds: 0
    Timer {
        interval: 250; repeat: true; running: root.recording
        onTriggered: root.recSeconds = Math.floor((Date.now() - root.recStartedAt) / 1000)
    }

    // ─── Estados (componente ancora) ───────────────────────────────
    // idle -> focus -> typing -> sending -> processing -> idle; error a qualquer momento (com texto e icone).
    // As mudancas sao de opacidade, cor e habilitacao: o campo de texto nunca e recriado (cursor e rascunho ficam).
    property string errorText: ""
    property bool sending: false
    readonly property string phase: errorText !== "" ? "error"
        : running ? "processing"
        : sending ? "sending"
        : input.activeFocus && input.length > 0 ? "typing"
        : input.activeFocus || recording ? "focus"
        : "idle"
    onRunningChanged: if (running) sending = false
    Timer { interval: 4000; running: root.sending; onTriggered: root.sending = false }
    Connections { target: input; function onTextChanged() { if (root.errorText !== "") root.errorText = "" } }

    implicitHeight: body.implicitHeight + 28
    // Claro com foto: vidro fosco (desfoque real com GPU) com sombra macia e borda de luz, em vez da caixa opaca
    readonly property bool frosted: Theme.photoLight
    radius: Theme.rComposer
    color: frosted ? "transparent" : Theme.bgSurface
    border.width: 1
    border.color: phase === "error" ? Theme.alpha(Theme.danger, 0.55)
                : frosted ? Theme.glassEdge          // vidro fosco: so a borda de luz, tambem em foco
                : (phase === "focus" || phase === "typing") ? Theme.alpha(Theme.focusRing, 0.55)
                : hoverArea.hovered ? Theme.hairlineHi : Theme.hairline
    Behavior on border.color { ColorAnimation { duration: Theme.dur(Theme.durFast); easing.type: Theme.easeStandard } }
    HoverHandler { id: hoverArea }

    GlassPanel {
        objectName: "composerGlass"
        z: -1
        anchors.fill: parent
        visible: root.frosted
        radius: root.radius
        fill: Theme.bgGlass                  // translucido: o reforco medido para a foto (glassBoost) garante o AA
    }

    // Brilho de voz atras da caixa (nasce da borda de baixo); nao confundir com o andamento do agente
    VoiceGlow {
        objectName: "voiceGlow"
        z: -2
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: parent.height
        state_: root.voiceState
        level: root.voiceLevel
    }

    // Anel de foco suave (foco do teclado, digitando ou gravando)
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        radius: parent.radius + 4
        color: "transparent"
        border.width: 4
        border.color: Theme.alpha(root.phase === "error" ? Theme.danger : Theme.focusRing, 0.12)
        opacity: (root.phase === "focus" || root.phase === "typing" || root.phase === "error") ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }
    }

    // Andamento do agente: fio fino na borda de baixo (diferente do brilho de voz)
    Item {
        objectName: "runTrack"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: root.radius
        anchors.rightMargin: root.radius
        anchors.bottomMargin: 1
        height: 2
        clip: true
        opacity: root.phase === "processing" || root.phase === "sending" ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.dur(Theme.durNormal) } }
        Rectangle {
            id: runBar
            width: parent.width * 0.3
            height: 2
            radius: 1
            color: Theme.focusRing
            x: Theme.motion ? -width : (parent.width - width) / 2
            NumberAnimation on x {
                running: Theme.motion && (root.phase === "processing" || root.phase === "sending")
                from: -runBar.width; to: runBar.parent.width
                duration: Theme.dur(1400); loops: Animation.Infinite; easing.type: Easing.InOutSine
            }
        }
    }

    ColumnLayout {
        id: body
        anchors.fill: parent
        anchors.margins: 14
        anchors.leftMargin: 18
        spacing: 8

        // Erro: mensagem e icone (nunca so a cor da borda)
        RowLayout {
            objectName: "composerError"
            Layout.fillWidth: true
            visible: root.errorText !== ""
            spacing: 8
            Icon { name: "alert-circle"; size: 14; color: Theme.danger }
            Text {
                Layout.fillWidth: true
                text: root.errorText
                color: Theme.textPrimary
                font.family: Theme.fontSans
                font.pixelSize: Theme.sizeSm
                wrapMode: Text.Wrap
            }
            Text {
                text: "Fechar"
                color: errClose.containsMouse ? Theme.textPrimary : Theme.textSecondary
                font.family: Theme.fontSans
                font.pixelSize: Theme.sizeSm
                MouseArea { id: errClose; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor; onClicked: root.errorText = "" }
            }
        }

        // Arquivos anexados (etiquetas com x para tirar)
        Flow {
            Layout.fillWidth: true
            visible: root.attachments.length > 0
            spacing: 6
            Repeater {
                model: root.attachments
                delegate: Rectangle {
                    width: chipRow.implicitWidth + 16
                    height: 26
                    radius: 8
                    color: Theme.bgSurfaceHi
                    RowLayout {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { glyph: ""; size: 11; color: Theme.textSecondary }
                        Text {
                            text: root.baseName(modelData)
                            color: Theme.textPrimary
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.sizeSm
                            elide: Text.ElideMiddle
                            Layout.maximumWidth: 180
                        }
                        Icon {
                            glyph: ""; size: 9; color: Theme.textTertiary
                            MouseArea {
                                anchors.fill: parent; anchors.margins: -5
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.removeFile(index)
                            }
                        }
                    }
                    ToolTipHint { text: modelData; shown: chipHover.hovered }
                    HoverHandler { id: chipHover }
                }
            }
        }

        // Texto (ou, gravando, a barra da mensagem de audio)
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(Math.max(input.implicitHeight, 24), 140)

            ScrollView {
                id: scroller
                anchors.fill: parent
                visible: !root.recording
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                TextArea {
                    id: input
                    placeholderText: root.liveOn ? "Conversa ao vivo: pode falar (ou digitar)..." : root.placeholder
                    placeholderTextColor: Theme.textTertiary
                    color: Theme.textPrimary
                    selectionColor: Theme.alpha(Theme.info, 0.35)
                    selectedTextColor: Theme.textPrimary
                    font.family: Theme.fontSans
                    font.pixelSize: 15
                    wrapMode: TextArea.Wrap
                    background: null
                    padding: 0
                    topPadding: 4
                    readOnly: root.running

                    Keys.onPressed: (event) => {
                        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                && !(event.modifiers & Qt.ShiftModifier)) {
                            event.accepted = true
                            root.send()
                        }
                    }
                    Accessible.name: "Tarefa"
                }
            }

            RowLayout {
                anchors.fill: parent
                visible: root.recording
                spacing: 10

                Rectangle {
                    width: 10; height: 10; radius: 5
                    color: Theme.accent
                    SequentialAnimation on opacity {
                        running: root.recording; loops: Animation.Infinite
                        NumberAnimation { to: 0.25; duration: Theme.dur(600) }
                        NumberAnimation { to: 1.0; duration: Theme.dur(600) }
                    }
                }
                Text {
                    text: Math.floor(root.recSeconds / 60) + ":" + ("0" + (root.recSeconds % 60)).slice(-2)
                    color: Theme.textPrimary
                    font.family: Theme.fontSans
                    font.pixelSize: 15
                    font.features: { "tnum": 1 }
                }
                // Barras de volume
                Row {
                    spacing: 3
                    Repeater {
                        model: 18
                        Rectangle {
                            width: 3
                            radius: 1.5
                            anchors.verticalCenter: parent.verticalCenter
                            height: 4 + 16 * Math.max(0, Math.min(1, root.voiceLevel * (0.55 + 0.45 * Math.abs(Math.sin(index * 1.7)))))
                            color: Theme.alpha(Theme.accent, 0.8)
                            Behavior on height { NumberAnimation { duration: Theme.dur(80) } }
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: root.compact ? "Ouvindo..." : "Gravando — clique em enviar quando terminar"
                    color: Theme.textTertiary
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.sizeSm
                    elide: Text.ElideRight
                }
                Text {
                    text: "Cancelar"
                    color: cancelMouse.containsMouse ? Theme.textPrimary : Theme.textSecondary
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.sizeSm
                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        anchors.margins: -6
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.recordCancel()
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            // + anexar arquivos
            Rectangle {
                Layout.preferredWidth: root.frosted ? 32 : 28
                Layout.preferredHeight: root.frosted ? 32 : 28
                radius: width / 2
                color: root.frosted ? Theme.alpha(Theme.bgSurface, addMouse.containsMouse ? 0.85 : 0.55)
                     : addMouse.containsMouse ? Theme.bgHover : Theme.alpha(Theme.bgHover, 0)
                border.width: root.frosted ? 0 : 1
                border.color: Theme.hairline
                Icon { anchors.centerIn: parent; glyph: ""; size: 12; color: Theme.textSecondary }
                MouseArea {
                    id: addMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    enabled: !root.running
                    onClicked: fileDialog.open()
                }
                ToolTipHint { text: "Anexar arquivos (ou arraste para cá)"; shown: addMouse.containsMouse }
                Accessible.role: Accessible.Button
                Accessible.name: "Anexar arquivos"
            }

            TogglePill {
                id: simulatePill
                visible: !root.compact
                text: "Simular"
                icon: ""
                tooltip: "Mostra o plano sem executar nada no computador"
            }
            TogglePill {
                id: reportPill
                visible: !root.compact
                text: "Relatório"
                icon: ""
                tooltip: "Gera um resumo da execução ao final (1 chamada extra de IA)"
            }
            TogglePill {
                id: livePill
                text: "Conversa"
                icon: ""
                tooltip: "Microfone aberto: fale à vontade, cada pedido é executado em seguida"
                checked: root.liveOn
                // O estado real vem do backend; clique ou teclado so pedem a troca
                manual: true
                onToggled: root.liveSwitched(!root.liveOn)
            }

            Item { Layout.fillWidth: true }

            Text {
                visible: text !== ""
                text: root.voiceState === "thinking" ? "Entendendo..."
                    : root.voiceState === "speaking" ? "Falando..."
                    : root.liveOn && root.voiceState === "listening"
                      ? "Ouvindo" + (root.queued > 0 ? " · " + root.queued + " na fila" : "")
                    : (!root.compact && !root.running && input.activeFocus && input.length > 0) ? "Shift+Enter nova linha"
                    : ""
                color: root.liveOn && root.voiceState === "listening" ? Theme.accent : Theme.textTertiary
                font.family: Theme.fontSans
                font.pixelSize: Theme.sizeXs
                Layout.rightMargin: 4
            }

            // Microfone: grava a mensagem de audio; gravando, vira "enviar audio"
            Rectangle {
                id: micBtn
                visible: !root.liveOn
                Layout.preferredWidth: 36
                Layout.preferredHeight: 36
                radius: 18
                color: root.recording ? Theme.accent
                     : root.frosted ? (micMouse.containsMouse ? Theme.bgSurfaceHi : Theme.bgSurface)
                     : (micMouse.containsMouse ? Theme.bgHover : Theme.alpha(Theme.bgHover, 0))
                border.width: root.recording ? 0 : 1
                border.color: Theme.hairline

                Rectangle {
                    anchors.centerIn: parent
                    visible: root.recording
                    width: parent.width + 12 * root.voiceLevel
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: 2
                    border.color: Theme.alpha(Theme.accent, 0.3)
                    Behavior on width { NumberAnimation { duration: Theme.dur(90) } }
                }
                Spinner {
                    anchors.centerIn: parent
                    visible: root.voiceState === "thinking" && !root.recording
                    size: 14
                }
                Icon {
                    anchors.centerIn: parent
                    visible: !(root.voiceState === "thinking" && !root.recording)
                    glyph: root.recording ? "" : ""
                    size: 14
                    color: root.recording ? Theme.textInverse : Theme.textSecondary
                }
                MouseArea {
                    id: micMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.micClicked()
                }
                ToolTipHint {
                    text: root.recording ? "Enviar áudio" : "Gravar áudio (" + root.voiceHotkey + ")"
                    shown: micMouse.containsMouse
                }
                Accessible.role: Accessible.Button
                Accessible.name: root.recording ? "Enviar áudio" : "Gravar áudio"
            }

            // Enviar / Parar
            Rectangle {
                id: sendBtn
                visible: !root.recording
                Layout.preferredWidth: 36
                Layout.preferredHeight: 36
                radius: 18
                // Vazio: tinta suave do destaque (ja diz "e aqui que envia"); com texto: tinta cheia
                color: root.running ? Theme.bgSurfaceHi
                     : (root.canSend ? Theme.primary : Theme.alpha(Theme.accent, 0.14))
                border.width: root.running ? 1 : 0
                border.color: Theme.hairlineHi
                scale: sendMouse.pressed ? Theme.press : 1
                Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }
                Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast); easing.type: Theme.easeOut } }

                Spinner { anchors.centerIn: parent; visible: root.phase === "sending"; size: 14 }
                Icon {
                    anchors.centerIn: parent
                    visible: root.phase !== "sending"
                    glyph: root.running ? "" : ""
                    size: root.running ? 12 : 14
                    color: root.running ? Theme.textPrimary
                         : (root.canSend ? Theme.textInverse : Theme.accent)
                }
                MouseArea {
                    id: sendMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: (root.running || root.canSend) ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: root.running ? root.stopRequested() : root.send()
                }
                ToolTipHint {
                    text: root.running ? "Parar execução (Esc)" : "Executar (Enter)"
                    shown: sendMouse.containsMouse
                }
                Accessible.role: Accessible.Button
                Accessible.name: root.running ? "Parar" : "Executar"
            }
        }
    }
}
