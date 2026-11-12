// Rotulo pequeno em caixa alta, mono e espacado ("01 · PERFIL", "AGENTES DE CODIGO"): marca a secao
// sem disputar com o titulo. Ponto opcional na cor de destaque (ou de status).
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root
    property string text: ""
    property bool dot: false
    property color dotColor: Theme.accent
    property color color: Theme.textTertiary
    spacing: 8
    Rectangle { visible: root.dot; width: 6; height: 6; radius: 3; color: root.dotColor }
    Text {
        text: root.text.toUpperCase()
        color: root.color
        font.family: Theme.fontMono
        font.pixelSize: Theme.sizeXs
        font.letterSpacing: 1.4
    }
}
