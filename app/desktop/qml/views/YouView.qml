// Voce: o seu segundo cerebro. Seis cartoes guiados (perfil, rotinas, tarefas,
// jeito de falar, padrao de respostas, skills para os agentes). O texto salva
// sozinho na sua pasta pessoal e entra no contexto dos agentes como preferencia.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components" as C

Item {
    id: root
    property var sections: []
    property bool writable: true
    property string error: ""
    signal openBrain()

    readonly property int filled: sections.filter(s => (s.text || "").trim().length > 0).length
    readonly property var glyphs: ({
        "Perfil": "", "Rotinas": "", "Tarefas frequentes": "",
        "Jeito de falar": "", "Padrão de respostas": "", "Skills para os agentes": ""
    })
    readonly property var examples: ({
        "Perfil": "Ex.: Trabalho com marketing digital. Pode me chamar pelo primeiro nome.",
        "Rotinas": "Ex.: Toda segunda às 9h reviso a planilha de campanhas e envio um resumo.",
        "Tarefas frequentes": "Ex.: Abrir o painel de anúncios e exportar o relatório da semana em Excel.",
        "Jeito de falar": "Ex.: \"bloquinho\" = Bloco de Notas · \"a planilha\" = a planilha de campanhas.",
        "Padrão de respostas": "Ex.: Respostas curtas, em tópicos, sem explicar o óbvio.",
        "Skills para os agentes": "Ex.: Em planilhas, sempre valores em R$ e um gráfico de colunas."
    })

    function reload() {
        const r = JSON.parse(Bridge.youProfile())
        if (!r.ok) { error = r.error || "Indisponível"; return }
        error = ""
        sections = r.sections
        writable = r.writable
    }
    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload()

    C.ScrollPage {
        anchors.fill: parent
        maxWidth: 980
        spacing: 22

        // Cabecalho
        C.PageHeader {
            eyebrow: "Perfil · " + root.filled + " de " + root.sections.length + " preenchidos"
            title: "Você"
            subtitle: "O que os agentes devem saber sobre você. Escreva do seu jeito: salva sozinho e vale para as próximas tarefas."
            // Progresso
            ColumnLayout {
                spacing: 6
                Rectangle {
                    implicitWidth: 120; implicitHeight: 6; radius: 3
                    color: C.Theme.alpha(C.Theme.textPrimary, 0.08)
                    Rectangle {
                        height: parent.height; radius: 3
                        width: parent.width * (root.sections.length ? root.filled / root.sections.length : 0)
                        color: C.Theme.accent
                        Behavior on width { NumberAnimation { duration: C.Theme.dur(C.Theme.durSlow); easing.type: Easing.OutCubic } }
                    }
                }
            }
        }

        C.IntroCard {
            Layout.fillWidth: true
            key: "you"
            place: "a seção Você"
            title: "Seu perfil para os agentes"
            lead: "Conte como você trabalha e fala. Os agentes leem isto antes de planejar e executar, "
                + "e passam a fazer as coisas do seu jeito."
            steps: [["edit", "Escreva livremente", "Cada cartão é um assunto. Frases curtas funcionam melhor: um item por linha."],
                    ["check", "Salva sozinho", "Ao parar de digitar, o texto é guardado na sua pasta pessoal, fora do repositório do projeto."],
                    ["sparkle", "Vale na próxima tarefa", "O que você preencher vai junto com cada pedido para o modelo de IA (Maestro e agentes). Cartão vazio não vai."]]
        }

        Text {
            visible: root.error !== ""
            text: root.error
            color: C.Theme.danger
            font.family: C.Theme.fontSans
            font.pixelSize: C.Theme.sizeMd
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width > 760 ? 2 : 1
            columnSpacing: 14
            rowSpacing: 14

            Repeater {
                model: root.sections
                C.GlassPanel {
                    id: card
                    Layout.fillWidth: true
                    Layout.preferredHeight: 236
                    fill: area.activeFocus ? C.Theme.bgGlassHi : C.Theme.bgGlass
                    property string state_: ""
                    property string lastSaved: modelData.text || ""

                    Timer {
                        id: autosave
                        interval: 900
                        onTriggered: card.persist()
                    }
                    function persist() {
                        if (area.text === card.lastSaved) return
                        const r = JSON.parse(Bridge.youSave(modelData.name, area.text))
                        if (r.ok) { card.lastSaved = area.text; card.state_ = "Salvo" }
                        else card.state_ = r.error || "Não salvou"
                        badgeTimer.restart()
                    }
                    Timer { id: badgeTimer; interval: 1800; onTriggered: card.state_ = "" }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle {
                                width: 30; height: 30; radius: 10
                                color: (area.text || "").trim() ? C.Theme.alpha(C.Theme.accent, 0.14) : C.Theme.alpha(C.Theme.textPrimary, 0.05)
                                C.Icon { anchors.centerIn: parent; glyph: root.glyphs[modelData.name] || ""; size: 14
                                         color: (area.text || "").trim() ? C.Theme.accent : C.Theme.textSecondary }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.name
                                color: C.Theme.textPrimary
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeLg
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: card.state_
                                visible: text !== ""
                                color: card.state_ === "Salvo" ? C.Theme.success : C.Theme.danger
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeSm
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: modelData.hint
                            wrapMode: Text.Wrap
                            color: C.Theme.textSecondary
                            font.family: C.Theme.fontSans
                            font.pixelSize: C.Theme.sizeSm + 1
                        }
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            TextArea {
                                id: area
                                text: modelData.text || ""
                                readOnly: !root.writable
                                wrapMode: TextArea.Wrap
                                placeholderText: root.examples[modelData.name] || ""
                                placeholderTextColor: C.Theme.textTertiary
                                color: C.Theme.textPrimary
                                selectionColor: C.Theme.alpha(C.Theme.accent, 0.25)
                                font.family: C.Theme.fontSans
                                font.pixelSize: C.Theme.sizeMd
                                leftPadding: 0
                                background: null
                                onTextChanged: if (activeFocus) autosave.restart()
                                onActiveFocusChanged: if (!activeFocus) card.persist()
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            C.Icon { glyph: ""; size: 13; color: C.Theme.textTertiary }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: "Guardado na pasta do seu cérebro e enviado junto com os pedidos ao modelo de IA. É preferência: não libera nada que os agentes não possam fazer."
                color: C.Theme.textTertiary
                font.family: C.Theme.fontSans
                font.pixelSize: C.Theme.sizeSm
            }
            C.Button { text: "Abrir no Cérebro"; icon: ""; compact: true; onClicked: root.openBrain() }
        }
    }
}
