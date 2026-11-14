// Campo de texto de uma linha no estilo do app (borda fina, foco na cor de destaque).
import QtQuick
import QtQuick.Controls

TextField {
    id: f
    implicitHeight: 38
    leftPadding: 12
    rightPadding: 12
    color: Theme.textPrimary
    placeholderTextColor: Theme.textTertiary
    selectionColor: Theme.alpha(Theme.accent, 0.25)
    selectedTextColor: Theme.textPrimary
    font.family: Theme.fontSans
    font.pixelSize: Theme.sizeMd
    background: Rectangle {
        radius: Theme.rMd
        color: Theme.bgSurface
        border.width: 1
        border.color: f.activeFocus ? Theme.alpha(Theme.accent, 0.6) : Theme.hairlineHi
        Behavior on border.color { ColorAnimation { duration: Theme.dur(Theme.durFast) } }
    }
}
