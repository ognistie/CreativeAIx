// Paleta de comandos (Ctrl+K): busca no app inteiro com teclado. Setas navegam, Enter executa, Esc fecha.
// Cada resultado mostra a area e a acao (e o atalho, quando existe). A paleta so NAVEGA ou PREENCHE: nada
// e executado direto daqui — "Pedir na Conversa" coloca o texto na caixa de pedido e a pessoa envia, com as
// mesmas permissoes e confirmacoes da tela. O dono fornece os resultados (`provider`) e trata `chosen`.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    objectName: "commandPalette"
    // provider(query) -> [{ kind, id, title, area, icon, hint }]
    property var provider: function (q) { return [] }
    property var results: []
    property int current: 0
    signal chosen(var item)

    modal: true
    focus: true
    width: Math.min(600, (parent ? parent.width : 600) - 48)
    height: Math.min(460, box.implicitHeight)
    x: ((parent ? parent.width : width) - width) / 2
    y: Math.round((parent ? parent.height : 600) * 0.14)
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function refresh() {
        results = provider(field.text.trim())
        current = results.length ? 0 : -1
    }
    function run(i) {
        if (i < 0 || i >= results.length) return
        const item = results[i]
        close()
        chosen(item)
    }
    onAboutToShow: { field.text = ""; refresh() }       // limpa ANTES de aparecer: quem ja digita nao perde texto
    onOpened: field.forceActiveFocus()

    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.dur(Theme.durFast); easing.type: Theme.easeOut } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.dur(Theme.durFast); easing.type: Theme.easeIn } }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, Theme.dark ? 0.45 : 0.18) }

    background: Rectangle {
        radius: Theme.r4
        color: Theme.bgSurface
        border.width: 1
        border.color: Theme.hairlineHi
    }

    contentItem: ColumnLayout {
        id: box
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 14
            spacing: 10
            Icon { name: "search"; size: 16; color: Theme.textTertiary }
            TextField {
                id: field
                objectName: "paletteField"
                Layout.fillWidth: true
                background: null
                padding: 0
                placeholderText: "Buscar telas, ações, Diário, Biblioteca e conversas…"
                placeholderTextColor: Theme.textTertiary
                color: Theme.textPrimary
                font.family: Theme.fontSans
                font.pixelSize: Theme.sizeLg
                onTextChanged: root.refresh()
                Keys.onPressed: (e) => {
                    if (e.key === Qt.Key_Down) { root.current = Math.min(root.results.length - 1, root.current + 1); list.positionViewAtIndex(root.current, ListView.Contain); e.accepted = true }
                    else if (e.key === Qt.Key_Up) { root.current = Math.max(0, root.current - 1); list.positionViewAtIndex(root.current, ListView.Contain); e.accepted = true }
                    else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) { root.run(root.current); e.accepted = true }
                }
                Accessible.name: "Buscar comandos"
            }
            Text { text: "Esc"; color: Theme.textTertiary; font.family: Theme.fontMono; font.pixelSize: Theme.sizeXs }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 360)
            Layout.margins: 6
            clip: true
            model: root.results
            spacing: 1
            delegate: Rectangle {
                width: list.width
                height: 40
                radius: Theme.r2
                readonly property bool on: index === root.current
                color: on ? Theme.bgRowHover : Theme.alpha(Theme.bgRowHover, 0)
                Behavior on color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 10
                    Icon { name: modelData.icon || "arrow-right"; size: 15; color: on ? Theme.accent : Theme.textSecondary }
                    Text { Layout.fillWidth: true; text: modelData.title; elide: Text.ElideRight
                           color: Theme.textPrimary; font.family: Theme.fontSans; font.pixelSize: Theme.sizeMd }
                    Text { visible: !!modelData.hint; text: modelData.hint || ""; color: Theme.textTertiary
                           font.family: Theme.fontMono; font.pixelSize: Theme.sizeXs }
                    Text { text: modelData.area; color: Theme.textTertiary; font.family: Theme.fontSans; font.pixelSize: Theme.sizeXs }
                }
                MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onEntered: root.current = index; onClicked: root.run(index) }
                Accessible.role: Accessible.ListItem
                Accessible.name: modelData.title + ", " + modelData.area
            }
        }
        Text {
            visible: root.results.length === 0
            Layout.margins: 16
            text: "Nada encontrado."
            color: Theme.textTertiary; font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }
        Text {
            Layout.margins: 10
            Layout.leftMargin: 14
            text: "↑↓ navegar   Enter abrir   Esc fechar   ·   Pedidos vão para a caixa de texto: você envia."
            color: Theme.textTertiary; font.family: Theme.fontSans; font.pixelSize: Theme.sizeXs
        }
    }
}
