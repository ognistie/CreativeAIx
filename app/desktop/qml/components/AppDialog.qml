// Dialogo no estilo do app: vidro claro, titulo na fonte de titulos, botoes do app no
// rodape. Conteudo como filhos. `acceptText`, `rejectText` e `danger` (botao vermelho).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dlg
    property string acceptText: "OK"
    property string rejectText: "Cancelar"
    property bool danger: false
    property bool canAccept: true
    modal: true
    width: 440
    padding: 22
    topPadding: 8

    Overlay.modal: Rectangle { color: Qt.rgba(0.1, 0.08, 0.15, 0.22) }

    background: Rectangle {
        radius: Theme.rLg
        color: Theme.bgSurface
        border.width: 1
        border.color: Theme.hairline
        Rectangle {
            z: -1
            anchors.fill: parent
            anchors.topMargin: 10
            anchors.bottomMargin: -10
            radius: parent.radius
            color: Qt.rgba(0.2, 0.15, 0.3, 0.10)
        }
    }
    header: Text {
        text: dlg.title
        leftPadding: 22
        rightPadding: 22
        topPadding: 20
        bottomPadding: 6
        color: Theme.textPrimary
        font.family: Theme.fontDisplay
        font.pixelSize: Theme.sizeXl
        font.weight: Theme.weightTitle
    }
    footer: Item {
        implicitHeight: 64
        RowLayout {
            anchors.right: parent.right
            anchors.rightMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Rectangle {
                implicitWidth: noText.implicitWidth + 32
                implicitHeight: 36
                radius: 18
                color: noMouse.containsMouse ? Theme.bgHover : Qt.rgba(0, 0, 0, 0)
                border.width: 1
                border.color: Theme.hairlineHi
                Text { id: noText; anchors.centerIn: parent; text: dlg.rejectText; color: Theme.textPrimary
                       font.family: Theme.fontSans; font.pixelSize: 13; font.weight: Font.Medium }
                MouseArea { id: noMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: dlg.reject() }
                Accessible.role: Accessible.Button
                Accessible.name: dlg.rejectText
            }
            Rectangle {
                implicitWidth: okText.implicitWidth + 32
                implicitHeight: 36
                radius: 18
                opacity: dlg.canAccept ? 1 : 0.4
                color: dlg.danger ? Theme.danger : Theme.primary
                Text { id: okText; anchors.centerIn: parent; text: dlg.acceptText; color: Theme.textInverse
                       font.family: Theme.fontSans; font.pixelSize: 13; font.weight: Font.Medium }
                MouseArea { anchors.fill: parent; enabled: dlg.canAccept; cursorShape: Qt.PointingHandCursor
                            onClicked: dlg.accept() }
                Accessible.role: Accessible.Button
                Accessible.name: dlg.acceptText
            }
        }
    }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.dur(Theme.durNormal) }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.dur(Theme.durNormal); easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.dur(Theme.durFast) } }
}
