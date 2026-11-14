// Item do AppMenu: icone de linha + texto; `danger` pinta de vermelho (ex.: Excluir).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

MenuItem {
    id: item
    property string iconName: ""
    property bool danger: false
    implicitHeight: 34
    leftPadding: 10
    rightPadding: 10

    contentItem: RowLayout {
        spacing: 10
        opacity: item.enabled ? 1 : 0.4
        Icon {
            visible: item.iconName !== ""
            name: item.iconName
            size: 15
            color: item.danger ? Theme.danger : Theme.textSecondary
        }
        Text {
            Layout.fillWidth: true
            text: item.text
            color: item.danger ? Theme.danger : Theme.textPrimary
            font.family: Theme.fontSans
            font.pixelSize: Theme.sizeMd - 1
            elide: Text.ElideRight
        }
    }
    background: Rectangle {
        radius: Theme.rSm
        color: item.highlighted ? (item.danger ? Theme.alpha(Theme.danger, 0.08) : Theme.alpha(Theme.accent, 0.10))
                                : Qt.rgba(1, 1, 1, 0)
    }
}
