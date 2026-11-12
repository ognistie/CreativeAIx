// Estado vazio: um icone, uma frase, uma explicacao curta e UMA acao primaria.
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string icon: "sparkle"
    property string title: ""
    property string text: ""
    property string action: ""
    signal triggered()
    spacing: 8
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: 40; height: 40; radius: Theme.r2
        color: Theme.bgChip
        Icon { anchors.centerIn: parent; name: root.icon; size: 18; color: Theme.textSecondary }
    }
    Text { Layout.alignment: Qt.AlignHCenter; text: root.title; color: Theme.textPrimary
           font.family: Theme.fontSans; font.pixelSize: Theme.sizeMd; font.weight: Font.DemiBold }
    Text { visible: root.text !== ""; Layout.alignment: Qt.AlignHCenter; Layout.maximumWidth: 360
           horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; text: root.text
           color: Theme.textSecondary; font.family: Theme.fontSans; font.pixelSize: Theme.sizeSm + 1 }
    Button { visible: root.action !== ""; Layout.alignment: Qt.AlignHCenter; Layout.topMargin: 4
             text: root.action; variant: "primary"; compact: true; onClicked: root.triggered() }
}
