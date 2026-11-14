// Cabecalho das telas: rotulo mono, titulo grande e justo, uma linha de apoio e, a direita, o que a
// tela quiser (progresso, botoes). Mesmo desenho em todas as telas. No tema claro com papel de parede,
// ganha um vidro atras (em vez de velar a pintura inteira).
import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property string eyebrow: ""
    property string title: ""
    property string subtitle: ""
    default property alias trailing: side.data
    Layout.fillWidth: true
    Layout.bottomMargin: 4
    implicitHeight: row.implicitHeight

    Rectangle {
        visible: Theme.photoLight
        x: -18
        y: -14
        width: textCol.width + 36
        height: parent.height + 28
        radius: Theme.rLg
        color: Theme.bgGlass
        border.width: 1
        border.color: Theme.hairline
    }

    RowLayout {
        id: row
        width: parent.width
        spacing: 16

        ColumnLayout {
            id: textCol
            Layout.fillWidth: true
            spacing: 6
            Eyebrow { visible: root.eyebrow !== ""; text: root.eyebrow; dot: true }
            Text {
                text: root.title
                color: Theme.textPrimary
                font.family: Theme.fontDisplay
                font.pixelSize: Theme.sizeHero + 6
                font.weight: Theme.weightTitle
                font.letterSpacing: Theme.tracking(Theme.sizeHero + 6)
            }
            Text {
                visible: root.subtitle !== ""
                Layout.fillWidth: true
                Layout.maximumWidth: 640
                text: root.subtitle
                wrapMode: Text.Wrap
                color: Theme.textSecondary
                font.family: Theme.fontSans
                font.pixelSize: Theme.sizeMd + 1
                lineHeight: 1.2
            }
        }
        RowLayout {
            id: side
            Layout.alignment: Qt.AlignBottom | Qt.AlignRight
            spacing: 8
        }
    }
}
