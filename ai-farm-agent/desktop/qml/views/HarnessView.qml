// Harness: como os agentes trabalham e como a plataforma se parece. Instrucoes por
// agente (clique no no do fluxo), padrao das respostas, aparencia (cor, paleta,
// ambiente, movimento, cantos), telas da barra lateral e versoes para desfazer.
// A aparencia muda ao vivo; "Salvar" grava (com versao), "Descartar" volta.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components" as C

Item {
    id: root
    property var saved: null
    property var draft: null
    property var versions: []
    property bool writable: true
    property string selected: "MAESTRO"
    property string message: ""
    signal harnessSaved(var harness)

    readonly property bool dirty: draft !== null && saved !== null && JSON.stringify(draft) !== JSON.stringify(saved)
    readonly property var agents: ["WEB", "DESKTOP", "CODE", "DATA", "FILE", "EXTCODE"]
    readonly property var accents: ["#16897E", "#0A7CFF", "#5B5BF7", "#8B5CF6", "#E0457B", "#F0663A", "#E59E1A", "#14A37F", "#111112"]
    // Ficha do agente escolhido (Bridge.agentProfile: papel, regras do Cerebro, skills, sugestoes)
    property var profile: null
    property bool rulesOpen: false
    signal openNote(string rel)
    signal openYou()
    function agentIcon(a) {
        return ({ YOU: "user", MAESTRO: "route", WEB: "globe", DESKTOP: "monitor", CODE: "code",
                  DATA: "chart", FILE: "folder" })[a] || "box"
    }
    function hasCustom(a) { return !!(draft && draft.agents[a] && draft.agents[a].instructions) }
    function loadProfile() {
        const r = JSON.parse(Bridge.agentProfile(selected))
        profile = r.ok ? r : null
        rulesOpen = false
    }
    function pick(a) {
        selected = a
        instructions.text = draft ? draft.agents[a].instructions : ""
        loadProfile()
    }
    function toggleQuick(line) {
        let lines = instructions.text.split("\n").map(x => x.trim()).filter(x => x)
        const i = lines.indexOf(line)
        if (i >= 0) lines.splice(i, 1); else lines.push(line)
        instructions.text = lines.join("\n").slice(0, 1500)
        patch(["agents", selected, "instructions"], instructions.text)
    }

    function clone(o) { return JSON.parse(JSON.stringify(o)) }
    function reload() {
        const r = JSON.parse(Bridge.harnessGet())
        if (!r.ok) { message = r.error || "Indisponível"; return }
        saved = r.harness; delete saved.label
        draft = clone(saved)
        versions = r.versions
        writable = r.writable
        instructions.text = draft.agents[selected].instructions
        extra.text = draft.response.extra
        hexField.text = draft.appearance.accent
    }
    function patch(path, value) {
        const d = clone(draft)
        let o = d
        for (let i = 0; i < path.length - 1; i++) o = o[path[i]]
        o[path[path.length - 1]] = value
        draft = d
        if (path[0] === "appearance") { C.Theme.applyAppearance(draft.appearance); lookTimer.restart() }
    }
    // Aparencia (tema, foto, cores) vale na hora e fica salva sozinha: antes ficava como "nao salva" e
    // sumia ao trocar de tela. Os outros campos continuam esperando o Salvar.
    Timer { id: lookTimer; interval: 450; onTriggered: root.saveAppearance() }
    function saveAppearance() {
        if (!saved || !draft) return
        const out = clone(saved); out.appearance = clone(draft.appearance)
        const r = JSON.parse(Bridge.harnessSave(JSON.stringify(out), "aparência"))
        if (!r.ok) { flash(r.error || "Não salvou a aparência"); return }
        const s2 = clone(saved); s2.appearance = r.harness.appearance; saved = s2
        const vr = JSON.parse(Bridge.harnessGet()); if (vr.ok) versions = vr.versions
        harnessSaved(r.harness)
    }
    function save() {
        const r = JSON.parse(Bridge.harnessSave(JSON.stringify(draft), "editado no app"))
        if (!r.ok) { flash(r.error || "Não salvou"); return }
        reload()
        C.Theme.applyAppearance(saved.appearance)
        harnessSaved(saved)
        flash("Harness salvo · versão anterior guardada")
    }
    function discard() {
        draft = clone(saved)
        instructions.text = draft.agents[selected].instructions
        extra.text = draft.response.extra
        hexField.text = draft.appearance.accent
        C.Theme.applyAppearance(saved.appearance)
    }
    function flash(t) { message = t; msgTimer.restart() }

    // ── Criador: uma frase vira uma proposta que voce revisa e aprova ──
    property string creatorState: "idle"      // idle | thinking | review | error
    property var proposal: null
    property string creatorError: ""
    function propose() {
        const t = creatorInput.text.trim()
        if (t.length < 3 || creatorState === "thinking") return
        creatorState = "thinking"; proposal = null; creatorError = ""
        Bridge.creatorPropose(t)
    }
    function applyProposal() {
        const r = JSON.parse(Bridge.creatorApply(proposal.id))
        if (!r.ok) { creatorError = r.error; creatorState = "error"; return }
        const n = (r.notes || []).length
        proposal = null; creatorState = "idle"; creatorInput.text = ""
        reload(); C.Theme.applyAppearance(saved.appearance); harnessSaved(saved)
        flash("Aplicado" + (n ? " · " + n + (n === 1 ? " nota no Cérebro" : " notas no Cérebro") : "") + " · dá para desfazer em Versões")
    }
    function discardProposal() {
        if (proposal) Bridge.creatorDiscard(proposal.id)
        proposal = null; creatorState = "idle"
    }
    function fieldLabel(f) {
        const p = f.split(".")
        const part = { response: "Respostas", appearance: "Aparência", modules: "Barra lateral", dev: "Desenvolvedor" }
        const names = { tone: "tom", length: "tamanho", extra: "padrão extra", accent: "cor de destaque", palette: "paleta",
                        ambient: "ambiente", motion: "movimento", radius: "cantos", mode: "tema", blur: "desfoque do vidro",
                        wallpaper: "papel de parede", dim: "escurecimento", mesh: "fundo", flow: "fluxo", fluted: "vidro canelado",
                        brain: "Cérebro", you: "Você", history: "Histórico" }
        if (p[0] === "agents") return C.Theme.agentLabel(p[1]) + " · instruções"
        return (part[p[0]] || p[0]) + " · " + (names[p[p.length - 1]] || p[p.length - 1])
    }
    function show(v) {
        if (v === true) return "ligado"
        if (v === false) return "desligado"
        if (v === null || v === undefined || v === "") return "—"
        return String(v)
    }
    Connections {
        target: Bridge
        function onCreatorReady(json) {
            const r = JSON.parse(json)
            if (!r.ok) { root.creatorError = r.error || "Não deu certo"; root.creatorState = "error"; return }
            root.proposal = r.proposal
            root.creatorState = "review"
        }
    }
    Timer { id: msgTimer; interval: 2600; onTriggered: root.message = "" }

    Component.onCompleted: { reload(); loadProfile() }
    onVisibleChanged: {
        if (visible) { if (!dirty) reload(); else C.Theme.applyAppearance(draft.appearance) }
        else { if (lookTimer.running) { lookTimer.stop(); saveAppearance() } if (saved) C.Theme.applyAppearance(saved.appearance) }
    }
    Shortcut { sequence: "Ctrl+S"; enabled: root.visible && root.dirty; onActivated: root.save() }

    C.ScrollPage {
        anchors.fill: parent
        maxWidth: 980
        spacing: 22
        bottomPadding: 90

        // Cabecalho
        C.PageHeader {
            eyebrow: "Plataforma"
            title: "Harness"
            subtitle: "Ajuste como os agentes trabalham juntos e como a plataforma se parece. São preferências: as regras de segurança continuam valendo."
        }

        C.IntroCard {
            Layout.fillWidth: true
            key: "harness"
            place: "o Harness"
            title: "Ajuste como a plataforma trabalha"
            lead: "Aqui você muda o jeito dos agentes e a cara do app, sem mexer em código. "
                + "As regras de segurança ficam no código e continuam valendo."
            steps: [["sparkle", "Descreva a mudança", "Escreva em uma frase o que quer mudar. O app mostra o antes e depois, e você aplica ou descarta."],
                    ["sliders", "Ajuste cada agente", "Escolha um agente em Como os agentes trabalham, veja como ele está programado e escreva suas preferências."],
                    ["palette", "Personalize", "Cor de destaque, paleta, luzes de fundo, cantos e as telas da barra lateral."],
                    ["history", "Desfaça quando quiser", "Cada vez que você salva, a versão anterior fica em Versões."]]
        }

        // ═══ Criar com uma frase ════════════════════════════════════
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: creatorCol.implicitHeight + 36
            visible: root.writable
            fill: C.Theme.bgGlassHi
            ColumnLayout {
                id: creatorCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 18
                spacing: 12
                RowLayout {
                    spacing: 10
                    Rectangle {
                        width: 30; height: 30; radius: 10
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: C.Theme.splashPeach }
                            GradientStop { position: 1; color: C.Theme.splashLilac }
                        }
                        C.Icon { anchors.centerIn: parent; glyph: ""; size: 14; color: C.Theme.textPrimary }
                    }
                    SectionTitle { title: "Descreva a mudança"
                                   note: "Ex.: respostas mais curtas, o agente de código testa antes de entregar, destaque em lilás. Você revisa antes de aplicar." }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Field {
                        Layout.fillWidth: true
                        implicitHeight: 40
                        focused: creatorInput.activeFocus
                        TextField {
                            id: creatorInput
                            objectName: "creatorInput"
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            enabled: root.creatorState !== "thinking"
                            placeholderText: root.dirty ? "Salve ou descarte as alterações abaixo antes" : "O que você quer mudar?"
                            placeholderTextColor: C.Theme.textTertiary
                            color: C.Theme.textPrimary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeMd
                            background: null
                            maximumLength: 1200
                            onAccepted: if (!root.dirty) root.propose()
                        }
                    }
                    Rectangle {
                        implicitWidth: proposeRow.implicitWidth + 28
                        implicitHeight: 40
                        radius: 20
                        readonly property bool can: creatorInput.text.trim().length >= 3 && root.creatorState !== "thinking" && !root.dirty
                        color: can ? C.Theme.accent : C.Theme.alpha(C.Theme.textPrimary, 0.08)
                        Behavior on color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                        RowLayout {
                            id: proposeRow
                            anchors.centerIn: parent
                            spacing: 8
                            C.Spinner { visible: root.creatorState === "thinking"; size: 13; color: C.Theme.textSecondary }
                            Text { text: root.creatorState === "thinking" ? "Pensando…" : "Propor"
                                   color: parent.parent.can ? C.Theme.textInverse : C.Theme.textSecondary
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd; font.weight: Font.Medium }
                        }
                        MouseArea { anchors.fill: parent; enabled: parent.can; cursorShape: Qt.PointingHandCursor; onClicked: root.propose() }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Propor mudança"
                    }
                }

                Text {
                    visible: root.creatorState === "error"
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: root.creatorError
                    color: C.Theme.danger
                    font.family: C.Theme.fontSans
                    font.pixelSize: C.Theme.sizeSm + 1
                }

                // Proposta para revisar
                ColumnLayout {
                    visible: root.creatorState === "review" && root.proposal !== null
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: root.proposal ? (root.proposal.empty ? "Nada para mudar com esse pedido." : root.proposal.summary) : ""
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeLg
                        font.weight: Font.Medium
                    }
                    Repeater {
                        model: root.proposal ? root.proposal.changes : []
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: chCol.implicitHeight + 16
                            radius: C.Theme.rMd
                            color: C.Theme.bgSurface
                            border.width: 1
                            border.color: C.Theme.hairline
                            ColumnLayout {
                                id: chCol
                                anchors.fill: parent
                                anchors.margins: 8
                                anchors.leftMargin: 12
                                spacing: 3
                                Text { text: root.fieldLabel(modelData.field); color: C.Theme.textSecondary
                                       font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Text { Layout.maximumWidth: parent.width * 0.42; text: root.show(modelData.before); elide: Text.ElideRight
                                           color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
                                           font.strikeout: modelData.before !== null && modelData.before !== "" }
                                    C.Icon { glyph: ""; size: 11; color: C.Theme.accent }
                                    Text { Layout.fillWidth: true; text: root.show(modelData.after); wrapMode: Text.Wrap
                                           color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                                }
                            }
                        }
                    }
                    Repeater {
                        model: root.proposal ? root.proposal.notes : []
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: noteCol.implicitHeight + 16
                            radius: C.Theme.rMd
                            color: C.Theme.bgSurface
                            border.width: 1
                            border.color: C.Theme.hairline
                            ColumnLayout {
                                id: noteCol
                                anchors.fill: parent
                                anchors.margins: 8
                                anchors.leftMargin: 12
                                spacing: 3
                                Text { text: (modelData.mode === "criar" ? "Nota nova · " : "Acrescentar em · ") + modelData.rel.replace(/\.md$/, "")
                                       color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                Text { Layout.fillWidth: true; text: modelData.content; maximumLineCount: 4; elide: Text.ElideRight
                                       wrapMode: Text.Wrap; color: C.Theme.textPrimary
                                       font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                            }
                        }
                    }
                    Repeater {
                        model: root.proposal ? root.proposal.warnings.map(w => ["", C.Theme.warning, w])
                                                 .concat(root.proposal.rejected.map(w => ["", C.Theme.danger, "Recusado: " + w]))
                                                 .concat(root.proposal.not_done.map(w => ["", C.Theme.textSecondary, "Não feito: " + w])) : []
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            C.Icon { glyph: modelData[0]; size: 12; color: modelData[1]; Layout.alignment: Qt.AlignTop }
                            Text { Layout.fillWidth: true; text: modelData[2]; wrapMode: Text.Wrap; color: modelData[1]
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
                        }
                    }
                    RowLayout {
                        Layout.topMargin: 4
                        spacing: 8
                        C.Button {
                            text: "Aplicar"
                            icon: ""
                            variant: "primary"
                            visible: root.proposal && !root.proposal.empty
                            onClicked: root.applyProposal()
                        }
                        C.Button { text: root.proposal && root.proposal.empty ? "Fechar" : "Descartar"; onClicked: root.discardProposal() }
                    }
                }
            }
        }

        // ═══ Agentes: quem faz o que, como esta programado e suas instrucoes ═══
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: agCol.implicitHeight + 36
            visible: root.draft !== null

            ColumnLayout {
                id: agCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 18
                spacing: 16
                SectionTitle {
                    title: "Como os agentes trabalham"
                    note: "Você pede, o Maestro monta o plano e cada agente executa a sua parte. Escolha um agente para ver "
                        + "como ele está programado hoje e dizer como você prefere que ele trabalhe."
                }

                // Caminho de um pedido: Voce -> Maestro -> agentes
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Repeater {
                        model: ["YOU", "→", "MAESTRO", "→"].concat(root.agents)
                        Item {
                            width: modelData === "→" ? 18 : stepPill.implicitWidth
                            height: 32
                            C.Icon { visible: modelData === "→"; anchors.centerIn: parent; name: "arrow-right"; size: 14
                                     color: C.Theme.textTertiary }
                            Rectangle {
                                id: stepPill
                                visible: modelData !== "→"
                                readonly property bool on: modelData === root.selected
                                implicitWidth: stepRow.implicitWidth + 22
                                height: 32
                                radius: 16
                                color: on ? C.Theme.alpha(C.Theme.accent, 0.12) : (stepMouse.containsMouse ? C.Theme.bgGlassHi : C.Theme.bgGlass)
                                border.width: 1
                                border.color: on ? C.Theme.alpha(C.Theme.accent, 0.5) : C.Theme.hairline
                                RowLayout {
                                    id: stepRow
                                    anchors.centerIn: parent
                                    spacing: 6
                                    C.Icon { name: root.agentIcon(modelData); size: 14
                                             color: stepPill.on ? C.Theme.accent : C.Theme.textSecondary }
                                    Text { text: modelData === "YOU" ? "Você" : C.Theme.agentLabel(modelData)
                                           color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: 13
                                           font.weight: stepPill.on ? Font.Medium : Font.Normal }
                                    Rectangle { visible: modelData !== "YOU" && root.hasCustom(modelData)
                                                width: 6; height: 6; radius: 3; color: C.Theme.accent }
                                }
                                MouseArea { id: stepMouse; anchors.fill: parent; hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: modelData === "YOU" ? root.openYou() : root.pick(modelData) }
                                Accessible.role: Accessible.Button
                                Accessible.name: modelData === "YOU" ? "Você" : C.Theme.agentLabel(modelData)
                            }
                        }
                    }
                }

                // Ficha do agente escolhido
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: card.implicitHeight + 36
                    radius: C.Theme.rLg
                    color: C.Theme.bgSurface
                    border.width: 1
                    border.color: C.Theme.hairline
                    ColumnLayout {
                        id: card
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 18
                        spacing: 14

                        RowLayout {
                            spacing: 14
                            Rectangle {
                                width: 46; height: 46; radius: 14
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: C.Theme.splashPeach }
                                    GradientStop { position: 1; color: C.Theme.splashLilac }
                                }
                                C.Icon { anchors.centerIn: parent; name: root.agentIcon(root.selected); size: 22; color: C.Theme.textPrimary }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text { text: C.Theme.agentLabel(root.selected); color: C.Theme.textPrimary
                                       font.family: C.Theme.fontDisplay; font.pixelSize: C.Theme.sizeXl + 2; font.weight: C.Theme.weightTitle }
                                Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: root.profile ? root.profile.role : ""
                                       color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: width > 640 ? 2 : 1
                            columnSpacing: 24
                            rowSpacing: 14

                            // O que faz
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignTop
                                spacing: 6
                                Text { text: "O que faz"; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                       font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                                Repeater {
                                    model: root.profile ? root.profile.does : []
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        C.Icon { name: "check"; size: 13; color: C.Theme.accent; Layout.alignment: Qt.AlignTop }
                                        Text { Layout.fillWidth: true; text: modelData; wrapMode: Text.Wrap; color: C.Theme.textPrimary
                                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
                                    }
                                }
                                Text { Layout.topMargin: 2; Layout.fillWidth: true; wrapMode: Text.Wrap
                                       text: root.profile ? "Trabalha com: " + root.profile.uses : ""
                                       color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                C.KeyValue { Layout.fillWidth: true; label: "Recebe"; value: root.profile && root.profile.inputs ? root.profile.inputs : "" }
                                C.KeyValue { Layout.fillWidth: true; last: true; label: "Ferramentas"
                                             value: root.profile && root.profile.tools ? (root.profile.tools.join(", ") || "nenhuma no executor") : "" }
                                Text { text: "Limites"; Layout.topMargin: 4; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                       font.pixelSize: C.Theme.sizeSm + 1; font.weight: Font.DemiBold }
                                Repeater {
                                    model: root.profile && root.profile.limits ? root.profile.limits : []
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        C.Icon { name: "lock"; size: 12; color: C.Theme.textTertiary; Layout.alignment: Qt.AlignTop; Layout.topMargin: 2 }
                                        Text { Layout.fillWidth: true; text: modelData; wrapMode: Text.Wrap; color: C.Theme.textSecondary
                                               font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                    }
                                }
                                Text { text: "Exemplos de pedido"; Layout.topMargin: 4; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                       font.pixelSize: C.Theme.sizeSm + 1; font.weight: Font.DemiBold }
                                Repeater {
                                    model: root.profile && root.profile.examples ? root.profile.examples : []
                                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "“" + modelData + "”"
                                           color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                }
                            }

                            // Como esta programado hoje (vem do Cerebro)
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignTop
                                spacing: 6
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { Layout.fillWidth: true; text: "Como está programado hoje"; color: C.Theme.textPrimary
                                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                                    Text {
                                        visible: root.profile && root.profile.note !== ""
                                        text: "Editar no Cérebro"
                                        color: C.Theme.accent
                                        font.family: C.Theme.fontSans
                                        font.pixelSize: C.Theme.sizeSm + 1
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                    onClicked: root.openNote(root.profile.note) }
                                    }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: root.profile && root.profile.rules ? root.profile.rules
                                          : "Sem regras escritas no Cérebro para este agente ainda."
                                    wrapMode: Text.Wrap
                                    maximumLineCount: root.rulesOpen ? 400 : 6
                                    elide: Text.ElideRight
                                    color: C.Theme.textSecondary
                                    font.family: C.Theme.fontSans
                                    font.pixelSize: C.Theme.sizeSm + 1
                                    lineHeight: 1.15
                                }
                                Text {
                                    visible: root.profile && root.profile.rules && root.profile.rules.split("\n").length > 6
                                    text: root.rulesOpen ? "Mostrar menos" : "Mostrar tudo"
                                    color: C.Theme.accent
                                    font.family: C.Theme.fontSans
                                    font.pixelSize: C.Theme.sizeSm
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                                onClicked: root.rulesOpen = !root.rulesOpen }
                                }
                                Flow {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 4
                                    spacing: 6
                                    visible: root.profile && root.profile.skills.length > 0
                                    Text { text: "Skills:"; color: C.Theme.textTertiary; font.family: C.Theme.fontSans
                                           font.pixelSize: C.Theme.sizeSm; height: 26; verticalAlignment: Text.AlignVCenter }
                                    Repeater {
                                        model: root.profile ? root.profile.skills : []
                                        Rectangle {
                                            implicitWidth: skText.implicitWidth + 16
                                            implicitHeight: 26
                                            radius: 13
                                            color: C.Theme.alpha(C.Theme.textPrimary, 0.05)
                                            Text { id: skText; anchors.centerIn: parent; text: modelData.name; color: C.Theme.textSecondary
                                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                            C.ToolTipHint { text: modelData.purpose; shown: skHover.hovered }
                                            HoverHandler { id: skHover }
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: C.Theme.hairline }

                        // Suas instrucoes para este agente
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: "Suas instruções para " + C.Theme.agentLabel(root.selected)
                                   color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
                                   font.weight: Font.DemiBold }
                            Text { text: instructions.text.length + " / 1500"; color: C.Theme.textTertiary
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                        }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: "Valem a partir da próxima tarefa, junto com as regras acima. São preferências: não liberam nada que o agente não possa fazer."
                            color: C.Theme.textSecondary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeSm + 1
                        }
                        Field {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 120
                            focused: instructions.activeFocus
                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: 10
                                TextArea {
                                    id: instructions
                                    wrapMode: TextArea.Wrap
                                    readOnly: !root.writable
                                    placeholderText: "Escreva do seu jeito, uma preferência por linha. Ou use as sugestões abaixo."
                                    placeholderTextColor: C.Theme.textTertiary
                                    color: C.Theme.textPrimary
                                    font.family: C.Theme.fontSans
                                    font.pixelSize: C.Theme.sizeMd
                                    background: null
                                    onTextChanged: if (activeFocus) root.patch(["agents", root.selected, "instructions"], text.slice(0, 1500))
                                }
                            }
                        }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 6
                            Text { text: "Sugestões rápidas:"; color: C.Theme.textTertiary; font.family: C.Theme.fontSans
                                   font.pixelSize: C.Theme.sizeSm; height: 30; verticalAlignment: Text.AlignVCenter }
                            Repeater {
                                model: root.profile ? root.profile.quick : []
                                C.Chip {
                                    text: modelData
                                    icon: instructions.text.indexOf(modelData) >= 0 ? "" : ""
                                    selected: instructions.text.indexOf(modelData) >= 0
                                    onClicked: root.toggleQuick(modelData)
                                }
                            }
                        }
                    }
                }
            }
        }

        // ═══ Respostas ══════════════════════════════════════════════
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: respCol.implicitHeight + 36
            visible: root.draft !== null
            ColumnLayout {
                id: respCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12
                SectionTitle { title: "Padrão das respostas"; note: "Como o agente fala com você ao terminar cada pedido. Vale depois de Salvar." }
                RowLayout {
                    spacing: 6
                    Label_ { text: "Tom" }
                    Repeater {
                        model: [["natural", "Natural"], ["direto", "Direto"], ["detalhado", "Detalhado"], ["amigavel", "Amigável"], ["formal", "Formal"]]
                        C.Chip { text: modelData[1]; selected: root.draft && root.draft.response.tone === modelData[0]
                                 onClicked: root.patch(["response", "tone"], modelData[0]) }
                    }
                }
                RowLayout {
                    spacing: 6
                    Label_ { text: "Tamanho" }
                    Repeater {
                        model: [["curta", "Curta"], ["media", "Média"], ["longa", "Longa"]]
                        C.Chip { text: modelData[1]; selected: root.draft && root.draft.response.length === modelData[0]
                                 onClicked: root.patch(["response", "length"], modelData[0]) }
                    }
                }
                Field {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 70
                    focused: extra.activeFocus
                    ScrollView {
                    anchors.fill: parent
                    anchors.margins: 6
                    TextArea {
                        id: extra
                        wrapMode: TextArea.Wrap
                        placeholderText: "Algo mais? Ex.: termine dizendo onde salvou o arquivo."
                        placeholderTextColor: C.Theme.textTertiary
                        color: C.Theme.textPrimary
                        font.family: C.Theme.fontSans
                        font.pixelSize: C.Theme.sizeMd
                        background: null
                        onTextChanged: if (activeFocus) root.patch(["response", "extra"], text.slice(0, 1500))
                    }
                    }
                }
            }
        }

        // ═══ Aparencia ══════════════════════════════════════════════
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: lookCol.implicitHeight + 36
            visible: root.draft !== null
            ColumnLayout {
                id: lookCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14
                SectionTitle { title: "Aparência"; note: "Muda e fica salva na hora, sem precisar de Salvar. A anterior vai para Versões." }

                RowLayout {
                    spacing: 6
                    Label_ { text: "Tema" }
                    Repeater {
                        model: [["escuro", "Escuro", "moon", "Vidro escuro, padrão"], ["claro", "Claro", "sun", "Superfícies claras"]]
                        C.ChoiceTile { title: modelData[1]; icon: modelData[2]; hint: modelData[3]
                                       selected: root.draft && (root.draft.appearance.mode || "escuro") === modelData[0]
                                       onClicked: root.patch(["appearance", "mode"], modelData[0]) }
                    }
                    Item { width: 12 }
                    C.Chip { text: "Vidro com desfoque"; icon: "layers"
                             selected: root.draft && root.draft.appearance.blur !== false
                             onClicked: root.patch(["appearance", "blur"], root.draft.appearance.blur === false) }
                }

                RowLayout {
                    spacing: 10
                    Label_ { text: "Destaque" }
                    Repeater {
                        model: root.accents
                        Rectangle {
                            width: 26; height: 26; radius: 13
                            color: modelData
                            readonly property bool on: root.draft && root.draft.appearance.accent.toUpperCase() === modelData.toUpperCase()
                            border.width: on ? 3 : 0
                            border.color: C.Theme.bgSurface
                            scale: swMouse.containsMouse ? 1.12 : 1
                            Behavior on scale { NumberAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
                            Rectangle { visible: parent.on; anchors.centerIn: parent; width: 32; height: 32; radius: 16
                                        color: "transparent"; border.width: 1.5; border.color: modelData }
                            C.Icon { visible: parent.on; anchors.centerIn: parent; name: "check"; size: 13; color: "white" }
                            MouseArea { id: swMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: { root.patch(["appearance", "accent"], modelData); hexField.text = modelData } }
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: "Cor " + modelData + (on ? ", escolhida" : "")
                        }
                    }
                    Field {
                        implicitWidth: 100
                        implicitHeight: 30
                        focused: hexField.activeFocus
                        TextField {
                            id: hexField
                            anchors.fill: parent
                            anchors.leftMargin: 4
                            font.family: C.Theme.fontMono
                            font.pixelSize: C.Theme.sizeSm + 1
                            color: C.Theme.textPrimary
                            background: null
                            maximumLength: 7
                            validator: RegularExpressionValidator { regularExpression: /#[0-9A-Fa-f]{0,6}/ }
                            onTextEdited: if (/^#[0-9A-Fa-f]{6}$/.test(text)) root.patch(["appearance", "accent"], text.toUpperCase())
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Label_ { text: "Paleta"; Layout.alignment: Qt.AlignTop; Layout.topMargin: 6 }
                    Flow {
                    Layout.fillWidth: true
                    spacing: 10
                    Repeater {
                        model: [["abismo", "Abismo"], ["ameixa", "Ameixa"], ["nevoa", "Névoa"], ["matcha", "Matcha"], ["seda", "Seda"],
                                ["aurora", "Aurora"], ["brisa", "Brisa"], ["coral", "Coral"], ["menta", "Menta"],
                                ["lavanda", "Lavanda"], ["areia", "Areia"], ["oceano", "Oceano"], ["aurora-boreal", "Boreal"]]
                        Rectangle {
                            id: pal
                            readonly property var tones: C.Theme.palettes[modelData[0]]
                            readonly property bool on: root.draft && root.draft.appearance.palette === modelData[0]
                            width: 112; height: 64; radius: C.Theme.rMd
                            color: tones[0]
                            clip: true
                            Rectangle { x: -14; y: -18; width: 70; height: 70; radius: 35; color: pal.tones[1]; opacity: 0.85 }
                            Rectangle { x: 64; y: -24; width: 64; height: 64; radius: 32; color: pal.tones[2]; opacity: 0.85 }
                            Rectangle { x: 34; y: 30; width: 70; height: 70; radius: 35; color: pal.tones[3]; opacity: 0.85 }
                            Text { anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 8
                                   text: modelData[1]; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                   font.pixelSize: C.Theme.sizeSm; font.weight: Font.Medium }
                            Rectangle {      // borda por cima do desenho (a selecao nao some atras das cores)
                                anchors.fill: parent
                                radius: parent.radius
                                color: "transparent"
                                border.width: pal.on ? 2 : 1
                                border.color: pal.on ? C.Theme.accent : C.Theme.hairline
                            }
                            C.Icon { visible: pal.on; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 6
                                     name: "check"; size: 14; color: C.Theme.accent }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: root.patch(["appearance", "palette"], modelData[0]) }
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: "Paleta " + modelData[1]
                        }
                    }
                    }
                }

                // Fundo: malha organica em GPU (com as cores da paleta) ou luzes; fluxo e vidro canelado
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Label_ { text: "Fundo" }
                    C.Chip { objectName: "bgMesh"; text: "Malha"; icon: ""
                             selected: root.draft && root.draft.appearance.mesh !== false
                             onClicked: root.patch(["appearance", "mesh"], true) }
                    C.Chip { text: "Luzes"; selected: root.draft && root.draft.appearance.mesh === false
                             onClicked: root.patch(["appearance", "mesh"], false) }
                    Item { width: 14 }
                    Repeater {
                        model: [["parado", "Parado"], ["sutil", "Sutil"], ["normal", "Normal"]]
                        C.Chip { text: modelData[1]
                                 selected: root.draft && (root.draft.appearance.flow || "sutil") === modelData[0]
                                 onClicked: root.patch(["appearance", "flow"], modelData[0]) }
                    }
                    Item { width: 14 }
                    C.Chip { objectName: "bgFluted"; text: "Vidro canelado"
                             selected: root.draft && root.draft.appearance.fluted === true
                             onClicked: root.patch(["appearance", "fluted"], !(root.draft.appearance.fluted === true)) }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs
                    text: "A malha é um gradiente orgânico desenhado pela placa de vídeo com as cores da paleta, em meia resolução e "
                        + "a 30 quadros, e para quando a janela é minimizada. Sem placa de vídeo o app usa as luzes. "
                        + "O vidro canelado refrata só o fundo; o texto fica sempre sobre o vidro liso."
                }

                // Papel de parede: catalogo com credito + imagens importadas (camada pessoal, fora do git)
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Label_ { text: "Papel de parede"; Layout.alignment: Qt.AlignTop; Layout.topMargin: 6 }
                    ColumnLayout {
                        id: wpCol
                        Layout.fillWidth: true
                        spacing: 8
                        property var items: []
                        function refresh() { const r = JSON.parse(Bridge.wallpapersList()); items = r.ok ? r.items : [] }
                        Component.onCompleted: refresh()
                        Flow {
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle {      // sem foto: so as luzes
                                readonly property bool on: root.draft && !root.draft.appearance.wallpaper
                                width: 112; height: 64; radius: C.Theme.rMd
                                color: C.Theme.bgChip
                                border.width: on ? 2 : 1
                                border.color: on ? C.Theme.accent : C.Theme.hairline
                                Text { anchors.centerIn: parent; text: "Sem foto"; color: C.Theme.textSecondary
                                       font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                            onClicked: root.patch(["appearance", "wallpaper"], "") }
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: "Sem papel de parede"
                            }
                            Repeater {
                                model: wpCol.items
                                Rectangle {
                                    id: wp
                                    readonly property bool on: root.draft && root.draft.appearance.wallpaper === modelData.id
                                    width: 112; height: 64; radius: C.Theme.rMd
                                    color: C.Theme.bgSurface
                                    clip: true
                                    Image { anchors.fill: parent; source: "file:///" + modelData.thumb.replace(/\\/g, "/")
                                            fillMode: Image.PreserveAspectCrop; asynchronous: true; smooth: true }
                                    Rectangle { anchors.fill: parent; radius: parent.radius; color: "transparent"
                                                border.width: wp.on ? 2 : 1; border.color: wp.on ? C.Theme.accent : C.Theme.hairline }
                                    C.Icon { visible: wp.on; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 6
                                             name: "check"; size: 14; color: C.Theme.accent }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; acceptedButtons: Qt.LeftButton | Qt.RightButton
                                                onClicked: (e) => {
                                                    if (e.button === Qt.RightButton) { if (modelData.id.indexOf("personal:") === 0) wpMenu.popup(); return }
                                                    root.patch(["appearance", "wallpaper"], modelData.id)
                                                } }
                                    C.AppMenu { id: wpMenu
                                        C.AppMenuItem { text: "Remover imagem"; iconName: "x"; danger: true
                                                        onTriggered: { if (wp.on) root.patch(["appearance", "wallpaper"], ""); Bridge.wallpaperRemove(modelData.id); wpCol.refresh() } } }
                                    C.ToolTipHint { text: modelData.title + (modelData.author ? " — " + modelData.author + ", " + modelData.year + " · " + modelData.license : " (sua imagem)")
                                                    shown: wpHover.hovered }
                                    HoverHandler { id: wpHover }
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData.title
                                }
                            }
                            Rectangle {      // importar
                                width: 112; height: 64; radius: C.Theme.rMd
                                color: impMouse.containsMouse ? C.Theme.bgGlassHi : C.Theme.bgChip
                                border.width: 1; border.color: C.Theme.hairline
                                ColumnLayout { anchors.centerIn: parent; spacing: 2
                                    C.Icon { name: "image"; size: 16; color: C.Theme.textSecondary; Layout.alignment: Qt.AlignHCenter }
                                    Text { text: "Importar"; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm } }
                                MouseArea { id: impMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: wpDialog.open() }
                                Accessible.role: Accessible.Button
                                Accessible.name: "Importar imagem"
                            }
                        }
                        RowLayout {
                            visible: root.draft && root.draft.appearance.wallpaper !== ""
                            spacing: 10
                            Text { text: "Escurecer"; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
                            Slider { id: dimSlider; Layout.preferredWidth: 180; from: 0; to: 1; stepSize: 0.05
                                     value: root.draft ? (root.draft.appearance.dim === undefined ? 0.35 : root.draft.appearance.dim) : 0.35
                                     onMoved: root.patch(["appearance", "dim"], Math.round(value * 100) / 100) }
                            Text { text: Math.round(dimSlider.value * 100) + "%"; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                        }
                        Text { Layout.fillWidth: true; wrapMode: Text.Wrap; color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs
                               text: "As cores do tema saem da foto (paleta extraída, com contraste medido). Imagens importadas ficam só na sua pasta pessoal (PNG, JPG ou WebP até 15 MB)." }
                    }
                }
                FileDialog {
                    id: wpDialog
                    title: "Escolher imagem"
                    nameFilters: ["Imagens (*.png *.jpg *.jpeg *.webp)"]
                    onAccepted: {
                        const r = JSON.parse(Bridge.wallpaperImport(selectedFile.toString()))
                        if (!r.ok) { root.flash(r.error || "Não importou"); return }
                        wpCol.refresh()
                        root.patch(["appearance", "wallpaper"], r.item.id)
                        root.flash("Imagem importada")
                    }
                }

                RowLayout {
                    spacing: 10
                    Label_ { text: "Ambiente" }
                    Slider {
                        id: ambientSlider
                        Layout.preferredWidth: 220
                        from: 0; to: 1; stepSize: 0.05
                        value: root.draft ? root.draft.appearance.ambient : 0.55
                        onMoved: root.patch(["appearance", "ambient"], Math.round(value * 100) / 100)
                    }
                    Text { text: Math.round(ambientSlider.value * 100) + "%"; color: C.Theme.textSecondary
                           font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                    Item { width: 12 }
                    C.Chip { text: root.draft && root.draft.appearance.motion ? "Luzes em movimento" : "Luzes paradas"
                             icon: ""; selected: root.draft && root.draft.appearance.motion
                             onClicked: root.patch(["appearance", "motion"], !root.draft.appearance.motion) }
                }

                RowLayout {
                    spacing: 6
                    Label_ { text: "Cantos" }
                    Repeater {
                        model: [["reto", "Retos"], ["suave", "Suaves"], ["redondo", "Redondos"]]
                        C.Chip { text: modelData[1]; selected: root.draft && root.draft.appearance.radius === modelData[0]
                                 onClicked: root.patch(["appearance", "radius"], modelData[0]) }
                    }
                }
            }
        }

        // ═══ Barra lateral ══════════════════════════════════════════
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: modCol.implicitHeight + 36
            visible: root.draft !== null
            ColumnLayout {
                id: modCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12
                SectionTitle { title: "Barra lateral"; note: "Escolha as telas que aparecem. O Harness fica sempre na barra lateral. Vale depois de Salvar." }
                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: [["brain", "Cérebro", ""], ["you", "Você", ""], ["history", "Histórico", ""]]
                        C.Chip { text: modelData[1]; icon: modelData[2]; selected: root.draft && root.draft.modules[modelData[0]]
                                 onClicked: root.patch(["modules", modelData[0]], !root.draft.modules[modelData[0]]) }
                    }
                }
            }
        }

        // ═══ Desenvolvedor ══════════════════════════════════════════
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: devCol.implicitHeight + 36
            visible: root.draft !== null
            ColumnLayout {
                id: devCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12
                SectionTitle { title: "Desenvolvedor"; note: "Mude a plataforma por dentro. Nível 1 e 2 são ajustes sem código, validados e com versões. Nível 3 pede ao Claude Code ou ao Codex uma mudança de código numa cópia separada: você vê o diff, o gate roda e só entra se você aplicar." }

                RowLayout {
                    spacing: 6
                    C.Chip { text: "Modo Desenvolvedor"; icon: "terminal"; selected: root.draft && root.draft.dev.enabled
                             onClicked: root.patch(["dev", "enabled"], !root.draft.dev.enabled) }
                    C.Chip { visible: root.draft && root.draft.dev.enabled
                             text: "Mudanças de código (nível 3)"; icon: "code"; selected: root.draft && root.draft.dev.code_changes
                             onClicked: root.patch(["dev", "code_changes"], !root.draft.dev.code_changes) }
                }

                // Nivel 1: textos da tela inicial
                ColumnLayout {
                    visible: root.draft && root.draft.dev.enabled
                    Layout.fillWidth: true
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Label_ { text: "Saudação" }
                        Field { Layout.fillWidth: true; implicitHeight: 32; focused: greetField.activeFocus
                            TextField { id: greetField; anchors.fill: parent; anchors.leftMargin: 8; background: null
                                        placeholderText: "Como posso ajudar?"; placeholderTextColor: C.Theme.textTertiary
                                        color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1
                                        maximumLength: 60; text: root.draft ? root.draft.dev.greeting : ""
                                        onTextEdited: root.patch(["dev", "greeting"], text) } }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Label_ { text: "Dica" }
                        Field { Layout.fillWidth: true; implicitHeight: 32; focused: hintField.activeFocus
                            TextField { id: hintField; anchors.fill: parent; anchors.leftMargin: 8; background: null
                                        placeholderText: "Digite ou fale um pedido..."; placeholderTextColor: C.Theme.textTertiary
                                        color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1
                                        maximumLength: 160; text: root.draft ? root.draft.dev.hint : ""
                                        onTextEdited: root.patch(["dev", "hint"], text) } }
                    }
                }

                // Nivel 2: atalhos de tarefa e cartoes (JSON validado; viram pedidos normais)
                Repeater {
                    model: root.draft && root.draft.dev.enabled ? [["shortcuts", "Atalhos de tarefa", "label", "Rótulo"], ["cards", "Cartões", "title", "Título"]] : []
                    ColumnLayout {
                        id: devList
                        readonly property string key: modelData[0]
                        readonly property string mainField: modelData[2]
                        Layout.fillWidth: true
                        spacing: 6
                        RowLayout {
                            Label_ { text: modelData[1]; Layout.preferredWidth: -1 }
                            C.Button { text: "Adicionar"; compact: true; variant: "ghost"
                                       enabled: root.draft[devList.key].length < 8
                                       onClicked: {
                                           const items = root.draft.dev[devList.key].slice()
                                           items.push(devList.key === "cards" ? { title: "", text: "", icon: "sparkle", request: "" }
                                                                              : { label: "", icon: "sparkle", request: "" })
                                           root.patch(["dev", devList.key], items)
                                       } }
                        }
                        Repeater {
                            model: root.draft.dev[devList.key]
                            RowLayout {
                                id: devRow
                                Layout.fillWidth: true
                                spacing: 8
                                function set(field, value) {
                                    const items = root.draft.dev[devList.key].slice()
                                    items[index] = Object.assign({}, items[index]); items[index][field] = value
                                    root.patch(["dev", devList.key], items)
                                }
                                Field { Layout.preferredWidth: 180; implicitHeight: 30; focused: f1.activeFocus
                                    TextField { id: f1; anchors.fill: parent; anchors.leftMargin: 8; background: null; placeholderText: modelData[3] || "Nome"
                                                placeholderTextColor: C.Theme.textTertiary; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                                font.pixelSize: C.Theme.sizeSm + 1; text: modelData[devList.mainField] || ""
                                                onTextEdited: devRow.set(devList.mainField, text) } }
                                Field { Layout.fillWidth: true; implicitHeight: 30; focused: f2.activeFocus
                                    TextField { id: f2; anchors.fill: parent; anchors.leftMargin: 8; background: null; placeholderText: "Pedido em linguagem natural"
                                                placeholderTextColor: C.Theme.textTertiary; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                                                font.pixelSize: C.Theme.sizeSm + 1; text: modelData.request || ""
                                                onTextEdited: devRow.set("request", text) } }
                                C.IconButton { name: "x"; hint: "Remover"
                                               onClicked: { const items = root.draft.dev[devList.key].slice(); items.splice(index, 1); root.patch(["dev", devList.key], items) } }
                            }
                        }
                    }
                }

                // Nivel 3: proposta de codigo numa worktree
                ColumnLayout {
                    visible: root.draft && root.draft.dev.enabled && root.draft.dev.code_changes
                    Layout.fillWidth: true
                    spacing: 8
                    property var proposals: []
                    property string busy: ""
                    property string openDiff: ""
                    property string diffText: ""
                    function refresh() { const r = JSON.parse(Bridge.devList()); proposals = r.ok ? r.items : [] }
                    Component.onCompleted: refresh()
                    Connections {
                        target: Bridge
                        function onDevChanged(json) {
                            const e = JSON.parse(json)
                            if (e.status === "progress") { devProgress.text = e.message; return }
                            devProgress.text = e.status === "error" ? e.message : ""
                            if (e.status !== "error") root.flash(e.status === "proposed" ? "Proposta pronta: veja o diff e verifique"
                                                               : e.status === "checked" ? "Gate verde: pode aplicar"
                                                               : e.status === "rejected" ? "Recusada: tocou arquivo fora do permitido"
                                                               : e.status === "gate_failed" ? "Gate reprovou" : "")
                            devL3.busy = ""
                            devL3.refresh()
                        }
                    }
                    id: devL3
                    Text { text: "Mudança de código (nível 3)"; color: C.Theme.textPrimary; font.family: C.Theme.fontSans
                           font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1
                           text: "Só telas e componentes QML (desktop/qml/views, components e dev). Núcleo, políticas, bridge e config nunca mudam por aqui. Pedido → worktree separada → diff → gate → você aplica; desfazer é um clique." }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Field { Layout.fillWidth: true; implicitHeight: 34; focused: devReq.activeFocus
                            TextField { id: devReq; anchors.fill: parent; anchors.leftMargin: 8; background: null
                                        placeholderText: "Ex.: na tela Sobre, mostre a versão em destaque"; placeholderTextColor: C.Theme.textTertiary
                                        color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1; maximumLength: 300 } }
                        Repeater {
                            model: [["claude", "Claude Code", "bolt"], ["codex", "Codex", "terminal"]]
                            C.Chip { text: modelData[1]; icon: modelData[2]; selected: devTool.value === modelData[0]; onClicked: devTool.value = modelData[0] }
                        }
                        QtObject { id: devTool; property string value: "claude" }
                        C.Button { text: "Propor"; variant: "primary"; compact: true
                                   enabled: devReq.text.trim().length >= 8 && devL3.busy === ""
                                   onClicked: {
                                       const r = JSON.parse(Bridge.devPropose(devReq.text.trim(), devTool.value))
                                       if (!r.ok) { root.flash(r.error || "Não propôs"); return }
                                       devL3.busy = "propor"; devProgress.text = "Criando a worktree e chamando " + (devTool.value === "claude" ? "o Claude Code" : "o Codex") + "..."
                                   } }
                    }
                    Text { id: devProgress; visible: text !== ""; Layout.fillWidth: true; elide: Text.ElideMiddle
                           color: C.Theme.textTertiary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs }
                    Repeater {
                        model: devL3.proposals.slice(0, 6)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Rectangle { width: 8; height: 8; radius: 4
                                            color: modelData.status === "applied" || modelData.status === "checked" ? C.Theme.success
                                                 : modelData.status === "rejected" || modelData.status === "failed" || modelData.status === "gate_failed" ? C.Theme.danger
                                                 : C.Theme.warning }
                                Text { Layout.fillWidth: true; elide: Text.ElideRight; color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1
                                       text: modelData.request + "  ·  " + (modelData.tool === "claude" ? "Claude Code" : "Codex") + "  ·  " + modelData.status }
                                C.Button { visible: modelData.diff_size > 0 && modelData.status !== "applied"; text: devL3.openDiff === modelData.id ? "Fechar diff" : "Ver diff"; compact: true; variant: "ghost"
                                           onClicked: { if (devL3.openDiff === modelData.id) { devL3.openDiff = "" } else { const r = JSON.parse(Bridge.devDiff(modelData.id)); devL3.diffText = r.ok ? r.diff : (r.error || ""); devL3.openDiff = modelData.id } } }
                                C.Button { visible: modelData.status === "proposed" || modelData.status === "gate_failed"; text: "Verificar"; compact: true
                                           enabled: devL3.busy === ""
                                           onClicked: { Bridge.devCheck(modelData.id); devL3.busy = "gate"; devProgress.text = "Rodando o gate na worktree (alguns minutos)..." } }
                                C.Button { visible: modelData.status === "checked"; text: "Aplicar"; compact: true; variant: "primary"
                                           onClicked: { const r = JSON.parse(Bridge.devAct(modelData.id, "apply")); root.flash(r.ok ? "Aplicado (merge local)" : (r.error || "Não aplicou")) } }
                                C.Button { visible: modelData.status === "applied"; text: "Desfazer"; compact: true
                                           onClicked: { const r = JSON.parse(Bridge.devAct(modelData.id, "undo")); root.flash(r.ok ? "Desfeito (revert)" : (r.error || "Não desfez")) } }
                                C.Button { visible: ["proposed", "checked", "gate_failed"].indexOf(modelData.status) >= 0; text: "Descartar"; compact: true; variant: "ghost"
                                           onClicked: { const r = JSON.parse(Bridge.devAct(modelData.id, "discard")); root.flash(r.ok ? "Descartada" : (r.error || "")) } }
                            }
                            Text { visible: modelData.summary !== "" && devL3.openDiff !== modelData.id; Layout.fillWidth: true; Layout.leftMargin: 16; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
                                   text: modelData.summary; color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                            Text { visible: modelData.gate !== null && modelData.gate !== undefined; Layout.leftMargin: 16; color: modelData.gate && modelData.gate.ok ? C.Theme.success : C.Theme.danger
                                   font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs; text: modelData.gate ? ("gate: " + (modelData.gate.ok ? "verde" : "reprovou — " + String(modelData.gate.detail).slice(0, 160))) : "" }
                            Rectangle {
                                visible: devL3.openDiff === modelData.id
                                Layout.fillWidth: true
                                Layout.leftMargin: 16
                                implicitHeight: Math.min(320, diffView.contentHeight + 16)
                                radius: C.Theme.rSm
                                color: C.Theme.bgSurface
                                border.width: 1
                                border.color: C.Theme.hairline
                                ScrollView {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    clip: true
                                    TextArea { id: diffView; readOnly: true; text: devL3.diffText; wrapMode: Text.NoWrap; background: null
                                               color: C.Theme.textPrimary; font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeXs; selectByMouse: true }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ═══ Versoes ════════════════════════════════════════════════
        C.GlassPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: verCol.implicitHeight + 36
            visible: root.versions.length > 0
            ColumnLayout {
                id: verCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 6
                SectionTitle { title: "Versões"; note: "Cada vez que você salva, a versão anterior fica guardada aqui." }
                Repeater {
                    model: root.versions.slice(0, 8)
                    RowLayout {
                        Layout.fillWidth: true
                        C.Icon { glyph: ""; size: 12; color: C.Theme.textTertiary }
                        Text {
                            Layout.fillWidth: true
                            text: modelData.when.slice(6, 8) + "/" + modelData.when.slice(4, 6) + " " + modelData.when.slice(9, 11) + ":" + modelData.when.slice(11, 13)
                                + (modelData.label ? "  ·  " + modelData.label : "")
                            color: C.Theme.textPrimary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeSm + 1
                        }
                        C.Button { text: "Restaurar"; compact: true; variant: "ghost"
                                   onClicked: {
                                       const r = JSON.parse(Bridge.harnessRestore(modelData.id))
                                       if (r.ok) { root.reload(); C.Theme.applyAppearance(root.saved.appearance); root.harnessSaved(root.saved); root.flash("Versão restaurada") }
                                       else root.flash(r.error || "Não restaurou")
                                   } }
                    }
                }
            }
        }
    }

    // Barra de salvar (aparece quando ha mudancas)
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.dirty || root.message ? 22 : -70
        Behavior on anchors.bottomMargin { NumberAnimation { duration: C.Theme.dur(C.Theme.durNormal); easing.type: Easing.OutCubic } }
        implicitWidth: barRow.implicitWidth + 24
        implicitHeight: 48
        radius: 24
        color: C.Theme.primary
        RowLayout {
            id: barRow
            anchors.centerIn: parent
            spacing: 10
            Text {
                Layout.leftMargin: 8
                text: root.message || "Alterações não salvas"
                color: C.Theme.textInverse
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeMd
            }
            Rectangle {
                visible: root.dirty
                implicitWidth: 92; implicitHeight: 32; radius: 16
                color: discardMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
                Text { anchors.centerIn: parent; text: "Descartar"; color: C.Theme.textInverse
                       font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
                MouseArea { id: discardMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.discard() }
            }
            Rectangle {
                visible: root.dirty
                implicitWidth: 92; implicitHeight: 32; radius: 16
                color: C.Theme.accent
                Text { anchors.centerIn: parent; text: "Salvar"; color: C.Theme.textInverse
                       font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1; font.weight: Font.Medium }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.save() }
            }
        }
    }

    // ── pecas locais ────────────────────────────────────────────────
    component SectionTitle: ColumnLayout {
        property string title: ""
        property string note: ""
        Layout.fillWidth: true
        spacing: 2
        Text { text: parent.title; color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay
               font.pixelSize: C.Theme.sizeLg + 1; font.weight: C.Theme.weightTitle }
        Text { visible: parent.note !== ""; Layout.fillWidth: true; text: parent.note; wrapMode: Text.Wrap
               color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
    }
    component Label_: Text {
        Layout.preferredWidth: 78
        color: C.Theme.textSecondary
        font.family: C.Theme.fontSans
        font.pixelSize: C.Theme.sizeSm + 1
    }
    component Field: Rectangle {
        property bool focused: false
        radius: C.Theme.rMd
        color: C.Theme.bgSurface
        border.width: 1
        border.color: focused ? C.Theme.alpha(C.Theme.accent, 0.55) : C.Theme.hairline
        Behavior on border.color { ColorAnimation { duration: C.Theme.dur(C.Theme.durFast) } }
    }
}
