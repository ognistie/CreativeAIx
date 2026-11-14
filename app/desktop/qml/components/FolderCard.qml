// Pasta do Diario: corpo com arte em degrade (luzes difusas, sem shader), aba no alto, nome e contagem; as entradas
// mais recentes aparecem como folhas atras da pasta e sobem em leque com o cursor em cima. "+" cria uma entrada nela.
import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property string name: ""
    property int count: 0
    property var recent: []                 // ate 3 titulos
    property var palette: Theme.artFolders.notas
    property string hint: ""
    signal opened()
    signal addRequested()

    implicitWidth: 300
    implicitHeight: 230
    readonly property bool hot: mouse.containsMouse || root.activeFocus
    activeFocusOnTab: true
    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) { root.opened(); e.accepted = true }
    }

    // Folhas (entradas recentes) atras da pasta
    Repeater {
        model: root.recent.slice(0, 3)
        Rectangle {
            readonly property real fan: index - 1
            width: root.width * 0.62
            height: root.height * 0.5
            x: root.width * 0.18 + fan * (root.hot ? 26 : 6)
            y: root.height * 0.12 - (root.hot ? 28 + index * 6 : index * 3)
            rotation: root.hot ? fan * 5 : fan * 1.5
            radius: 12
            color: Theme.bgSurface
            border.width: 1
            border.color: Theme.hairline
            Behavior on x { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }
            Behavior on y { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }
            Behavior on rotation { NumberAnimation { duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut } }
            Text { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                   text: modelData; elide: Text.ElideRight; color: Theme.textSecondary
                   font.family: Theme.fontSans; font.pixelSize: Theme.sizeXs }
        }
    }

    // Aba da pasta
    Rectangle {
        x: 0; y: root.height * 0.30 - 14
        width: root.width * 0.42; height: 30
        radius: 12
        color: Qt.darker(root.palette[0], 1.15)
    }
    // Corpo da pasta com a arte
    Rectangle {
        id: body
        y: root.height * 0.30
        width: root.width
        height: root.height * 0.70
        radius: 18
        color: root.palette[0]
        clip: true
        scale: mouse.pressed ? Theme.press : 1
        Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast) } }
        Repeater {
            model: [[0.3, 0.2, 1.1, 1], [0.85, 0.85, 0.9, 2]]
            Shape {
                id: light
                readonly property real d: body.width * modelData[2]
                width: d; height: d
                x: body.width * modelData[0] - d / 2
                y: body.height * modelData[1] - d / 2
                ShapePath {
                    strokeWidth: -1; strokeColor: "transparent"
                    fillGradient: RadialGradient {
                        centerX: light.d / 2; centerY: light.d / 2; centerRadius: light.d / 2; focalX: light.d / 2; focalY: light.d / 2
                        GradientStop { position: 0.0; color: Theme.alpha(Qt.color(root.palette[modelData[3]]), 0.9) }
                        GradientStop { position: 1.0; color: Theme.alpha(Qt.color(root.palette[modelData[3]]), 0) }
                    }
                    startX: 0; startY: 0
                    PathLine { x: light.d; y: 0 }
                    PathLine { x: light.d; y: light.d }
                    PathLine { x: 0; y: light.d }
                    PathLine { x: 0; y: 0 }
                }
            }
        }
        // Vidro: brilho no alto e base escura para o texto ler sobre qualquer arte
        Rectangle { anchors.fill: parent; radius: parent.radius
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.16) }
                        GradientStop { position: 0.45; color: Qt.rgba(1, 1, 1, 0.0) }
                        GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.42) }
                    } }
        Column {
            anchors.left: parent.left; anchors.right: plus.left; anchors.bottom: parent.bottom
            anchors.leftMargin: 18; anchors.rightMargin: 10; anchors.bottomMargin: 16
            spacing: 2
            Text { width: parent.width; elide: Text.ElideRight; text: root.name; color: "white"
                   font.family: Theme.fontSans; font.pixelSize: Theme.sizeLg; font.weight: Font.DemiBold }
            Text { text: root.count + (root.count === 1 ? " item" : " itens")
                   color: Qt.rgba(1, 1, 1, 0.82); font.family: Theme.fontMono; font.pixelSize: Theme.sizeXs }
            Text { visible: root.hint !== ""; width: parent.width; elide: Text.ElideRight; text: root.hint
                   color: Qt.rgba(1, 1, 1, 0.70); font.family: Theme.fontSans; font.pixelSize: Theme.sizeXs }
        }
        Rectangle {
            id: plus
            objectName: "folderAdd"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 14
            width: 38; height: 38; radius: 19
            color: plusMouse.containsMouse ? Theme.artInkHover : Theme.artInk
            Icon { anchors.centerIn: parent; name: "plus"; size: 15; color: "white" }
            MouseArea { id: plusMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.addRequested() }
            Accessible.role: Accessible.Button
            Accessible.name: "Nova entrada em " + root.name
        }
    }
    // Anel de foco do teclado
    Rectangle { x: body.x - 4; y: body.y - 4; width: body.width + 8; height: body.height + 8; radius: body.radius + 4
                color: "transparent"; border.width: 2; border.color: Theme.focusRing; visible: root.activeFocus }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        z: -1
        onClicked: root.opened()
    }
    Accessible.role: Accessible.Button
    Accessible.name: root.name + ", " + root.count + " itens"
}
