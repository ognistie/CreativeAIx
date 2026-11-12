// Ficha chave/valor: rotulo a esquerda, valor a direita, linha fina embaixo (metadados escaneaveis).
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string label: ""
    property string value: ""
    property bool last: false
    property bool numeric: false          // numeros tabulares (custo, tempo, contagens)
    Layout.fillWidth: true
    spacing: 0
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 8
        Layout.bottomMargin: 8
        spacing: 12
        Text { text: root.label; color: Theme.textSecondary; font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm + 1 }
        Item { Layout.fillWidth: true }
        Text {
            text: root.value
            color: Theme.textPrimary
            font.family: Theme.fontSans
            font.pixelSize: Theme.sizeSm + 1
            font.weight: Font.Medium
            font.features: root.numeric ? Theme.tabular : ({})
            horizontalAlignment: Text.AlignRight
        }
    }
    Rectangle { visible: !root.last; Layout.fillWidth: true; implicitHeight: 1; color: Theme.hairline }
}
