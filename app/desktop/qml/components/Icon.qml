// Icones de linha do app: desenhados em vetor (viewBox 24x24, traco fino com pontas
// arredondadas), na cor que voce passar. Use `name` ("search", "brain"...) ou, por
// compatibilidade, `glyph` com o codigo antigo da Segoe Fluent Icons: o codigo vira o
// desenho equivalente. Codigo sem desenho cai na fonte do sistema, como antes.
import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property string name: ""
    property string glyph: ""
    property int size: 16
    property color color: Theme.textSecondary
    property real weight: 1.7

    implicitWidth: size
    implicitHeight: size

    readonly property var fromGlyph: ({
        "": "chevron-down", "": "chevron-up", "": "edit", "": "plus",
        "": "x", "": "more", "": "settings", "": "stop", "": "link",
        "": "mic", "": "search", "": "arrow-right", "": "refresh",
        "": "lock", "": "check", "": "arrow-up", "": "save",
        "": "volume", "": "play", "": "chevron-right", "": "globe",
        "": "user", "": "alert-circle", "": "eye", "": "alert-triangle",
        "": "monitor", "": "history", "": "clock", "": "folder-open",
        "": "eye", "": "help", "": "file", "": "external", "": "folder",
        "": "x", "": "message", "": "brain", "": "messages",
        "": "folder-plus", "": "list", "": "clock", "": "code",
        "": "sparkle", "": "info", "": "box", "": "chart",
        "": "checklist", "": "sliders", "": "file-text", "": "eye-off"
    })

    readonly property var paths: ({
        "plus": "M12 5v14M5 12h14",
        "x": "M6 6l12 12M18 6L6 18",
        "check": "M5 12.5l4.5 4.5L19 7",
        "chevron-down": "M6 9l6 6l6-6",
        "chevron-up": "M6 15l6-6l6 6",
        "chevron-right": "M9 6l6 6l-6 6",
        "arrow-right": "M5 12h14M13 6l6 6l-6 6",
        "arrow-up": "M12 19V5M6 11l6-6l6 6",
        "edit": "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
        "more": "M5 12h.01M12 12h.01M19 12h.01",
        "settings": "M19.02 10.42L21.47 10.42L21.47 13.58L19.02 13.58L18.09 15.85L19.81 17.58L17.58 19.81L15.85 18.09L13.58 19.02L13.58 21.47L10.42 21.47L10.42 19.02L8.15 18.09L6.42 19.81L4.19 17.58L5.91 15.85L4.98 13.58L2.53 13.58L2.53 10.42L4.98 10.42L5.91 8.15L4.19 6.42L6.42 4.19L8.15 5.91L10.42 4.98L10.42 2.53L13.58 2.53L13.58 4.98L15.85 5.91L17.58 4.19L19.81 6.42L18.09 8.15zM12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z",
        "stop": "M8 6h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z",
        "link": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
        "mic": "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
        "search": "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14zM20 20l-4-4",
        "refresh": "M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6",
        "lock": "M8 11V8a4 4 0 0 1 8 0v3M6 11h12v9H6z",
        "save": "M5 4h11l3 3v13H5zM8 4v5h7V4M8 20v-6h8v6",
        "volume": "M4 9h4l5-4v14l-5-4H4zM16.5 9.5a3.5 3.5 0 0 1 0 5M19 6.5a7.5 7.5 0 0 1 0 11",
        "play": "M8 5.5l10.5 6.5L8 18.5z",
        "globe": "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM3 12h18M12 3c2.5 2.5 3.8 5.5 3.8 9s-1.3 6.5-3.8 9M12 3c-2.5 2.5-3.8 5.5-3.8 9s1.3 6.5 3.8 9",
        "user": "M12 4a4 4 0 1 0 0 8a4 4 0 1 0 0-8zM4.5 20.5a7.5 7.5 0 0 1 15 0",
        "alert-circle": "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM12 8v5M12 16v.01",
        "alert-triangle": "M12 4L2.8 19.5h18.4zM12 10v4M12 17v.01",
        "eye": "M2.5 12Q12 2.5 21.5 12Q12 21.5 2.5 12zM12 9.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5z",
        "eye-off": "M2.5 12Q12 2.5 21.5 12Q12 21.5 2.5 12zM12 9.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5zM4 4l16 16",
        "monitor": "M3.5 5h17v11h-17zM8 20h8M12 16v4",
        "history": "M3.5 12a8.5 8.5 0 1 0 2.5-6M3.5 4v4h4M12 7.5V12l3 2",
        "clock": "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM12 7.5V12l3 2",
        "folder": "M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z",
        "folder-open": "M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v1M3.5 7.5v9a2 2 0 0 0 2 2h12l3-8h-14l-3 8",
        "folder-plus": "M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2zM12 10.5v5M9.5 13h5",
        "help": "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM9.6 9.3a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.2.9-1.2 1.7v.3M12 16.5v.01",
        "file": "M6.5 3h7l5 5v13h-12zM13.5 3v5h5",
        "file-text": "M6.5 3h7l5 5v13h-12zM13.5 3v5h5M9.5 13h6M9.5 17h6",
        "external": "M14 4h6v6M20 4l-9 9M18 14v5H5V6h5",
        "message": "M4.5 5h15v11h-10l-5 4z",
        "messages": "M4 5h11v8H8.5L4 16.5zM9 16v1h6.5l4.5 3.5V9h-3",
        "brain": "M12 3.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5zM5.5 15.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5zM18.5 15.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5zM10.8 8.2l-4.1 7.6M13.2 8.2l4.1 7.6M8 18h8",
        "list": "M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01",
        "code": "M8 8l-4 4l4 4M16 8l4 4l-4 4M13.5 5l-3 14",
        "sparkle": "M12 3.5l1.7 5L19 10l-5.3 1.6L12 16.5l-1.7-4.9L5 10l5.3-1.5zM18.5 15l.7 2l2 .8l-2 .7l-.7 2l-.7-2l-2-.7l2-.8z",
        "info": "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM12 11v5M12 8v.01",
        "box": "M12 3l8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5l8-4.5M12 12v9",
        "chart": "M4 4v16h16M8.5 16v-4M12.5 16V8M16.5 16v-6",
        "checklist": "M4 6.5l1.5 1.5L8 5.5M4 12.5l1.5 1.5L8 11.5M4 18.5l1.5 1.5L8 17.5M11.5 7h8.5M11.5 13h8.5M11.5 19h8.5",
        "sliders": "M4 7h8M18 7h2M15 4.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5zM4 17h2M12 17h8M9 14.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5z",
        "palette": "M12 3.5a8.5 8.5 0 1 0 0 17c1.2 0 1.8-.8 1.8-1.7c0-1-.8-1.4-.8-2.3c0-1 .8-1.7 1.8-1.7h2.2a3.5 3.5 0 0 0 3.5-3.5c0-4.3-3.8-7.8-8.5-7.8zM7.5 11.5h.01M10 7.5h.01M14.5 7.5h.01",
        "route": "M6 4a2 2 0 1 0 0 4a2 2 0 1 0 0-4zM18 16a2 2 0 1 0 0 4a2 2 0 1 0 0-4zM8 6h7.5a3.5 3.5 0 0 1 0 7h-7a3.5 3.5 0 0 0 0 7H16",
        "sun": "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8zM12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4",
        "moon": "M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z",
        "layers": "M12 3.5l9 4.5l-9 4.5l-9-4.5zM3 12.5l9 4.5l9-4.5M3 17l9 4.5l9-4.5",
        "sidebar": "M4 5.5h16v13H4zM9.5 5.5v13",
        "bolt": "M13 2.5L5 13.5h6l-1 8l8-11h-6z",
        "terminal": "M4 5h16v14H4zM7.5 9l3 3l-3 3M12.5 15h4",
        "image": "M4 5h16v14H4zM8 10a1.5 1.5 0 1 0 0-3a1.5 1.5 0 0 0 0 3zM4 16l5-5l4 4l3-3l4 4",
        "book": "M3 5h6a3 3 0 0 1 3 3v12a2.5 2.5 0 0 0-2.5-2.5H3zM21 5h-6a3 3 0 0 0-3 3v12a2.5 2.5 0 0 1 2.5-2.5H21z",
        "notebook": "M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6zM9 3v18M12.5 8h3.5M12.5 12h3.5",
        "flask": "M9 3h6M10 3v6l-5.2 8.7A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-3.3L14 9V3M7.2 15h9.6",
        "command": "M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"
    })

    readonly property string key: name !== "" ? name : (fromGlyph[glyph] || "")
    // Troca de desenho (play <-> stop, + <-> x): o novo entra girando um pouco e crescendo, em vez de saltar
    property bool _ready: false
    Component.onCompleted: _ready = true
    onKeyChanged: if (_ready && Theme.motion) morph.restart()
    ParallelAnimation {
        id: morph
        NumberAnimation { target: root; property: "rotation"; from: -40; to: 0; duration: Theme.dur(Theme.durNormal); easing.type: Theme.easeOut }
        NumberAnimation { target: root; property: "scale"; from: 0.6; to: 1; duration: Theme.dur(Theme.durNormal); easing.type: Easing.OutBack }
        NumberAnimation { target: root; property: "opacity"; from: 0; to: 1; duration: Theme.dur(Theme.durFast) }
    }
    readonly property string d: paths[key] || ""

    Shape {
        visible: root.d !== ""
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.color
            strokeWidth: root.weight * 24 / Math.max(12, root.size) * (root.size >= 20 ? 0.9 : 1)
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.d }
        }
    }

    // Sem desenho: o glifo antigo da fonte do sistema (compatibilidade)
    Text {
        visible: root.d === "" && root.glyph !== ""
        anchors.centerIn: parent
        text: root.glyph
        color: root.color
        font.family: Theme.fontIcons
        font.pixelSize: root.size
        renderType: Text.NativeRendering
    }
}
