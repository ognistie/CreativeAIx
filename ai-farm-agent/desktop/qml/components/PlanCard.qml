// Plano para aprovar, passo a passo: cada passo e aprovado ou pulado; o primeiro sem decisao abre com
// Aprovar / Pular. Rodape: "x de n decididos", Aprovar tudo, Executar (so com todos decididos e ao menos
// um aprovado) e Cancelar. Emite run([passos pulados, 1..n]) ou cancelled().
import QtQuick
import QtQuick.Layouts

GlassPanel {
    id: root
    property var steps: []               // "[AGENTE] tarefa"
    property var decisions: []           // "ok" | "skip" | ""
    signal run(var skipped)
    signal cancelled()

    onStepsChanged: decisions = steps.map(() => "")
    readonly property int decided: decisions.filter(d => d !== "").length
    readonly property int approved: decisions.filter(d => d === "ok").length
    readonly property int focusIndex: decisions.indexOf("")
    function decide(i, d) { const c = decisions.slice(); c[i] = d; decisions = c }
    function runNow() {
        const skipped = []
        decisions.forEach((d, i) => { if (d === "skip") skipped.push(i + 1) })
        run(skipped)
    }
    function parse(s) {
        const m = (s || "").match(/^\[(\w+)\]\s*/)
        return m ? { agent: m[1], text: s.substring(m[0].length) } : { agent: "", text: s || "" }
    }
    function iconFor(agent) {
        return ({ WEB: "globe", DESKTOP: "monitor", CODE: "code", DATA: "chart", FILE: "folder", EXTCODE: "terminal" })[agent] || "sparkle"
    }

    implicitHeight: col.implicitHeight + 32
    fill: Theme.bgGlassHi

    ColumnLayout {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 16
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { text: "Plano"; color: Theme.textPrimary; font.family: Theme.fontDisplay
                   font.pixelSize: Theme.sizeLg; font.weight: Theme.weightTitle }
            Rectangle {
                implicitWidth: countText.implicitWidth + 14; implicitHeight: 20; radius: 10
                color: Theme.bgChip
                Text { id: countText; anchors.centerIn: parent; text: root.steps.length + (root.steps.length === 1 ? " passo" : " passos")
                       color: Theme.textSecondary; font.family: Theme.fontMono; font.pixelSize: Theme.sizeXs }
            }
            Item { Layout.fillWidth: true }
            Text { text: root.decided + " de " + root.steps.length + " decididos"; color: Theme.textTertiary
                   font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm; font.features: Theme.tabular }
        }

        Repeater {
            model: root.steps
            delegate: Rectangle {
                id: stepBox
                readonly property var p: root.parse(modelData)
                readonly property string d: root.decisions[index] || ""
                readonly property bool open: index === root.focusIndex
                Layout.fillWidth: true
                implicitHeight: stepCol.implicitHeight + 18
                radius: Theme.nested(Theme.r4, 8)
                color: open ? Theme.bgSurface : Theme.alpha(Theme.bgSurface, 0)
                opacity: d === "skip" ? 0.55 : 1
                Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }
                Behavior on opacity { NumberAnimation { duration: Theme.dur(Theme.durFast) } }
                Enter { target: stepCol; order: index }    // a entrada anima o conteudo; a opacidade de "pulado" fica no cartao
                ColumnLayout {
                    id: stepCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 9
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Icon { name: root.iconFor(stepBox.p.agent); size: 15; color: Theme.textSecondary }
                        Text {
                            Layout.fillWidth: true
                            text: stepBox.p.text
                            color: Theme.textPrimary
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.sizeMd
                            font.strikeout: stepBox.d === "skip"
                            wrapMode: stepBox.open ? Text.Wrap : Text.NoWrap
                            elide: stepBox.open ? Text.ElideNone : Text.ElideRight
                        }
                        Rectangle {          // selo de estado
                            implicitWidth: stateText.implicitWidth + 14; implicitHeight: 20; radius: 10
                            color: stepBox.d === "ok" ? Theme.alpha(Theme.success, 0.16)
                                 : stepBox.d === "skip" ? Theme.bgChip : Theme.bgChip
                            Text { id: stateText; anchors.centerIn: parent
                                   text: stepBox.d === "ok" ? "Aprovado" : stepBox.d === "skip" ? "Pulado" : "Planejado"
                                   color: stepBox.d === "ok" ? Theme.success : Theme.textSecondary
                                   font.family: Theme.fontSans; font.pixelSize: Theme.sizeXs }
                            TapHandler { enabled: stepBox.d !== ""; onTapped: root.decide(index, "") }   // desfazer a decisao
                        }
                    }
                    RowLayout {
                        visible: stepBox.open
                        Layout.leftMargin: 25
                        spacing: 8
                        Text { visible: stepBox.p.agent !== ""; text: Theme.agentLabel(stepBox.p.agent); color: Theme.textTertiary
                               font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm }
                        Item { width: 4 }
                        Button { text: "Aprovar"; icon: ""; variant: "primary"; compact: true; onClicked: root.decide(index, "ok") }
                        Button { text: "Pular"; variant: "ghost"; compact: true; onClicked: root.decide(index, "skip") }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 2
            spacing: 8
            Text { text: root.approved + (root.approved === 1 ? " aprovado" : " aprovados"); color: Theme.textTertiary
                   font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm; font.features: Theme.tabular }
            Item { Layout.fillWidth: true }
            Button { text: "Cancelar"; variant: "ghost"; compact: true; onClicked: root.cancelled() }
            Button { text: "Aprovar tudo"; compact: true; visible: root.decided < root.steps.length
                     onClicked: root.decisions = root.steps.map((_, i) => root.decisions[i] || "ok") }
            Button {
                text: "Executar"; variant: "primary"; compact: true
                enabled: root.decided === root.steps.length && root.approved > 0
                onClicked: root.runNow()
            }
        }
    }
}
