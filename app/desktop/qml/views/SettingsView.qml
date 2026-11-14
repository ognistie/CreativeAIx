// Configuracoes: instrucoes personalizadas (valem para todo pedido), como o agente executa,
// voz e interface. Grava em desktop/data/settings.json (Bridge.saveSettings).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components" as C

Item {
    id: root

    property var s: ({})
    property bool dirty: false
    property string savedMsg: ""

    function reload() {
        s = JSON.parse(Bridge.getSettings())
        instructions.text = s.instructions || ""
        dirty = false
    }
    function save(patch) {
        const out = JSON.parse(Bridge.saveSettings(JSON.stringify(patch)))
        if (out.ok) {
            s = Object.assign({}, s, out)
            savedMsg = "Salvo"
            savedTimer.restart()
        }
    }
    Timer { id: savedTimer; interval: 1800; onTriggered: root.savedMsg = "" }
    // Agentes de codigo: estado real das CLIs e do MCP (Bridge.codingAgentsCheck responde em codingStatus)
    property var coding: null
    property bool checking: false
    function checkCoding() { if (checking) return; checking = true; Bridge.codingAgentsCheck() }
    property var providers: { try { return JSON.parse(Bridge.providerStatus()).providers || [] } catch (e) { return [] } }
    function toolState(t) { return !coding ? "checking" : (!t.installed ? "missing" : (t.logged_in ? "ready" : "login")) }
    Connections {
        target: Bridge
        function onCodingStatus(json) { root.coding = JSON.parse(json); root.checking = false }
    }
    Component.onCompleted: reload()
    onVisibleChanged: if (visible) { reload(); if (!coding) checkCoding() }

    C.ScrollPage {
        anchors.fill: parent
        maxWidth: 760
        spacing: 18

        C.PageHeader {
            eyebrow: "Preferências"
            title: "Configurações"
            subtitle: "Como o app executa, fala e se conecta ao Claude Code e ao Codex. Muda na hora; nada aqui libera o que o agente não pode fazer."
            Text { visible: root.savedMsg !== ""; text: root.savedMsg; color: C.Theme.success; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
        }

        // ── Agentes de codigo ───────────────────────────────────────
        // ── Provedores do app: so o estado (configurado ou nao), nunca a chave ──
        Section {
            objectName: "providersSection"
            eyebrow: "01 · Provedores"
            title: "Modelos que o app usa"
            note: "As chaves ficam no arquivo .env do projeto, no seu computador. Esta tela só diz se estão lá; o valor nunca aparece."
            Repeater {
                model: root.providers
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    C.Icon { name: modelData.configured ? "check" : "alert-circle"; size: 14
                             color: modelData.configured ? C.Theme.success : C.Theme.warning }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text { text: modelData.name + " · " + modelData.use; Layout.fillWidth: true; elide: Text.ElideRight
                               color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                        Text { visible: !modelData.configured; text: modelData.next; Layout.fillWidth: true; wrapMode: Text.Wrap
                               color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                    }
                    Text { text: modelData.configured ? "chave configurada" : "sem chave"
                           color: modelData.configured ? C.Theme.textTertiary : C.Theme.warning
                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                }
            }
        }

        Section {
            eyebrow: "02 · Agentes de código"
            title: "Claude Code e Codex"
            note: "Peça “… com o Claude” ou “… com o Codex”, ou escolha no topo da Conversa. Eles trabalham só na pasta "
                + "do projeto que você citar, com a sessão que você já fez em cada um. O app nunca pede nem guarda chave."
            Repeater {
                model: root.coding && root.coding.tools ? root.coding.tools : [{ name: "Claude Code" }, { name: "Codex" }]
                delegate: RowLayout {
                    id: toolRow
                    Layout.fillWidth: true
                    spacing: 12
                    readonly property string st: root.toolState(modelData)
                    readonly property color tone: st === "ready" ? C.Theme.success : (st === "checking" ? C.Theme.textTertiary : C.Theme.warning)
                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        Layout.topMargin: 2
                        width: 34; height: 34; radius: 10
                        color: C.Theme.bgChip
                        border.width: 1; border.color: C.Theme.hairline
                        C.Icon { anchors.centerIn: parent; name: modelData.name === "Codex" ? "terminal" : "bolt"; size: 16; color: C.Theme.textPrimary }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        RowLayout {
                            spacing: 8
                            Text { text: modelData.name; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                   font.pixelSize: C.Theme.sizeMd; font.weight: Font.Medium }
                            Text { visible: !!modelData.version; text: modelData.version || ""; color: C.Theme.textTertiary
                                   font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                        }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            color: C.Theme.textSecondary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeSm
                            text: toolRow.st === "ready" ? "Pronto para usar" + (modelData.detail ? " · " + modelData.detail : "")
                                : toolRow.st === "login" ? modelData.login_help
                                : toolRow.st === "missing" ? modelData.install_help
                                : "Verificando…"
                        }
                    }
                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        implicitWidth: stLabel.implicitWidth + 22
                        implicitHeight: 24
                        radius: 12
                        color: C.Theme.alpha(toolRow.tone, 0.14)
                        border.width: 1
                        border.color: C.Theme.alpha(toolRow.tone, 0.45)
                        Text {
                            id: stLabel
                            anchors.centerIn: parent
                            color: toolRow.tone
                            font.family: C.Theme.fontMono
                            font.pixelSize: C.Theme.sizeXs
                            font.letterSpacing: 1.0
                            text: (toolRow.st === "ready" ? "conectado" : toolRow.st === "login" ? "falta entrar"
                                  : toolRow.st === "missing" ? "não instalado" : "verificando").toUpperCase()
                        }
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: C.Theme.hairline }
            SettingSwitch {
                label: "Deixar o Claude e o Codex consultarem o Cérebro (MCP)"
                detail: "Servidor MCP local, só de leitura: busca e leitura de notas, andamento das tarefas e projetos criados. "
                      + "Nenhuma ferramenta executa ação no computador."
                      + (root.coding && root.coding.mcp ? (root.coding.mcp.ok ? "  ·  " + root.coding.mcp.tools.length + " ferramentas respondendo"
                                                                            : "  ·  servidor não respondeu") : "")
                checked: root.s.coding_mcp !== false
                onToggled: (v) => root.save({ coding_mcp: v })
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                C.Button { text: root.checking ? "Verificando…" : "Verificar de novo"; compact: true
                           enabled: !root.checking; onClicked: root.checkCoding() }
                Text { text: "Tempo máximo, teto de custo e pastas com acesso total ficam em config.yaml (coding_agents)."
                       Layout.fillWidth: true; wrapMode: Text.Wrap
                       color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
            }
        }

        // ── Instrucoes personalizadas ───────────────────────────────
        Section {
            eyebrow: "03 · Pedidos"
            title: "Instruções personalizadas"
            note: "Valem para todo pedido, como as instruções de projeto do Claude e do ChatGPT. "
                + "São preferências: não liberam nada que o agente não possa fazer."
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 130
                radius: C.Theme.rMd
                color: C.Theme.bgSurface
                border.width: 1
                border.color: instructions.activeFocus ? C.Theme.alpha(C.Theme.accent, 0.45) : C.Theme.hairline
                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 10
                    TextArea {
                        id: instructions
                        wrapMode: TextArea.Wrap
                        placeholderText: "Ex.: responda curto e direto · planilhas sempre em R$ com gráfico · "
                                       + "salve arquivos na pasta Documentos/IA"
                        placeholderTextColor: C.Theme.textTertiary
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeMd
                        background: null
                        onTextChanged: root.dirty = text !== (root.s.instructions || "")
                        Keys.onPressed: (e) => {
                            if (text.length >= 1500 && e.text && e.key !== Qt.Key_Backspace) e.accepted = true
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: instructions.text.length + " / 1500"
                    color: C.Theme.textTertiary
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeXs
                }
                Text {
                    visible: root.savedMsg !== ""
                    text: root.savedMsg
                    color: C.Theme.success
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeSm
                }
                C.Button {
                    text: "Salvar"
                    variant: "primary"
                    compact: true
                    enabled: root.dirty
                    onClicked: { root.save({ instructions: instructions.text }); root.dirty = false }
                }
            }
        }

        // ── Execucao ────────────────────────────────────────────────
        Section {
            eyebrow: "04 · Execução"
            title: "Execução"
            SettingSwitch {
                label: "Revisar o plano antes de executar"
                detail: "Mostra os passos e espera você aprovar antes de mexer no PC (pedidos digitados). "
                      + "Como no Cowork e no ChatGPT Work."
                checked: !!root.s.plan_review
                onToggled: (v) => root.save({ plan_review: v })
            }
        }

        // ── Voz ─────────────────────────────────────────────────────
        Section {
            eyebrow: "05 · Voz"
            title: "Voz"
            note: "Voz sintetizada por IA. Fora do modo Conversa, o microfone e a transcrição ficam no computador."
            SettingSwitch {
                label: "Conversa em tempo real com GPT-Live"
                detail: "No modo Conversa, o áudio do microfone vai para a OpenAI enquanto há conversa. Cobrado por "
                      + "segundo de sessão aberta (cerca de US$ 3 por hora); fecha sozinha sem atividade. "
                      + "Desligado, a conversa usa a transcrição local."
                checked: root.s.live_conversation !== false
                onToggled: (v) => root.save({ live_conversation: v })
            }
            SettingSwitch {
                label: "Interromper falando"
                detail: "Fale por cima do agente e ele se cala na hora para ouvir você."
                checked: root.s.barge_in !== false
                onToggled: (v) => root.save({ barge_in: v })
            }
            SettingSwitch {
                label: "Sinal sonoro ao terminar de falar"
                detail: "Um toque curto confirma que a fala chegou, antes da resposta."
                checked: root.s.earcon !== false
                onToggled: (v) => root.save({ earcon: v })
            }
        }

        // ── Interface ───────────────────────────────────────────────
        Section {
            eyebrow: "06 · Interface"
            title: "Interface"
            note: "Vale a partir da próxima vez que o app abrir."
            SettingSwitch {
                label: "Tela de abertura"
                checked: root.s.splash !== false
                onToggled: (v) => root.save({ splash: v })
            }
            SettingSwitch {
                label: "Mini chat quando o agente vai para outro app"
                checked: root.s.mini_chat !== false
                onToggled: (v) => root.save({ mini_chat: v })
            }
        }

        // ── Atalhos ─────────────────────────────────────────────────
        Section {
            eyebrow: "07 · Teclado"
            title: "Atalhos"
            Repeater {
                model: [
                    { k: "Acesso rápido (de qualquer app)", v: (root.s.hotkeys || {}).quick },
                    { k: "Gravar / conversar por voz", v: (root.s.hotkeys || {}).voice },
                    { k: "Parar a execução", v: (root.s.hotkeys || {}).stop },
                ]
                delegate: RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: modelData.k
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeMd
                    }
                    Rectangle {
                        implicitWidth: keyText.implicitWidth + 16
                        implicitHeight: 24
                        radius: 6
                        color: C.Theme.bgSurfaceHi
                        Text {
                            id: keyText
                            anchors.centerIn: parent
                            text: modelData.v ? modelData.v.split("+").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" + ")
                                              : "indisponível"
                            color: C.Theme.textSecondary
                            font.family: C.Theme.fontMono
                            font.pixelSize: C.Theme.sizeSm
                        }
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                text: "Os atalhos ficam em config.yaml (seções ui e voice)."
                color: C.Theme.textTertiary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeSm
                wrapMode: Text.Wrap
            }
        }
    }

    // ── Pecas locais ────────────────────────────────────────────────
    // Cada secao e um cartao de vidro com rotulo mono, titulo e uma linha de apoio
    component Section: C.GlassPanel {
        id: sec
        property string eyebrow: ""
        property string title: ""
        property string note: ""
        default property alias content: inner.data
        Layout.fillWidth: true
        implicitHeight: secCol.implicitHeight + 40
        ColumnLayout {
            id: secCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            spacing: 10
            C.Eyebrow { visible: sec.eyebrow !== ""; text: sec.eyebrow }
            Text {
                text: sec.title
                color: C.Theme.textPrimary
                font.family: C.Theme.fontDisplay
                font.pixelSize: C.Theme.sizeLg + 2
                font.weight: C.Theme.weightTitle
            }
            Text {
                visible: sec.note !== ""
                Layout.fillWidth: true
                text: sec.note
                color: C.Theme.textSecondary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeSm + 1
                wrapMode: Text.Wrap
            }
            ColumnLayout {
                id: inner
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 14
            }
        }
    }

    component SettingSwitch: RowLayout {
        id: sw
        property string label: ""
        property string detail: ""
        property bool checked: false
        signal toggled(bool value)
        Layout.fillWidth: true
        spacing: 14
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text {
                Layout.fillWidth: true
                text: sw.label
                color: C.Theme.textPrimary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd
                wrapMode: Text.Wrap
            }
            Text {
                visible: sw.detail !== ""
                Layout.fillWidth: true
                text: sw.detail
                color: C.Theme.textTertiary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeSm
                wrapMode: Text.Wrap
            }
        }
        Rectangle {
            implicitWidth: 40
            implicitHeight: 22
            radius: 11
            color: sw.checked ? C.Theme.accent : C.Theme.bgSurfaceHi
            border.width: sw.checked ? 0 : 1
            border.color: C.Theme.hairlineHi
            Behavior on color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
            Rectangle {
                width: 16; height: 16; radius: 8
                y: 3
                x: sw.checked ? parent.width - width - 3 : 3
                color: "white"
                Behavior on x { NumberAnimation { duration: C.Theme.dur(C.Theme.durFast); easing.type: Easing.OutCubic } }
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: sw.toggled(!sw.checked)
            }
            Accessible.role: Accessible.CheckBox
            Accessible.name: sw.label
            Accessible.checked: sw.checked
        }
    }
}
