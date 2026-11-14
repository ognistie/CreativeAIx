// Biblioteca: grade de temas em cards (capa em degradê, numero na trilha, nivel, minutos de leitura) e uma pagina
// de leitura por tema: artigo em portugues, pratica no app, termos e limites; as referencias ficam no FIM.
// Conteudo de core/library.py + core/library_articles.py. Voltar preserva a busca e o filtro.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import "../components" as C

Item {
    id: root
    objectName: "libraryView"
    readonly property bool narrow: width < 860

    property string query: ""
    property string level: ""
    property var items: []
    property var current: null              // tema aberto na pagina de leitura (null = grade)
    property string verifiedOn: ""

    readonly property var levelNames: ({ iniciante: "Iniciante", intermediario: "Intermediário", avancado: "Avançado" })
    readonly property var kindNames: ({ documentacao: "Documentação", pesquisa: "Pesquisa publicada",
                                        preprint: "Preprint", didatico: "Material didático" })
    // Capa de cada tema: tres cores (base, luz 1, luz 2), pela ordem da trilha
    readonly property var covers: C.Theme.artCovers

    function reload() {
        const r = JSON.parse(Bridge.librarySearch(query, level, ""))
        items = r.items
        verifiedOn = r.verified_on
    }
    function openTopic(id) {
        const all = JSON.parse(Bridge.librarySearch("", "", "")).items
        const t = all.find(x => x.id === id)
        if (t) { current = t; reader.contentY = 0 }
    }
    function back() { current = null; grid.forceActiveFocus() }
    function fmtDate(d) { const p = (d || "").split("-"); return p.length === 3 ? p[2] + "/" + p[1] + "/" + p[0] : d }
    Component.onCompleted: reload()
    Keys.onEscapePressed: if (current) back()      // Esc volta da leitura para a grade (busca preservada)

    // ══ Grade de temas ═══════════════════════════════════════════════
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        anchors.topMargin: 16
        spacing: 12
        visible: !root.current

        GridLayout {
            Layout.fillWidth: true
            columns: root.narrow ? 1 : 3
            columnSpacing: 12
            rowSpacing: 8
            ColumnLayout {
                spacing: 2
                Text { text: "Biblioteca"; color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay
                       font.pixelSize: C.Theme.sizeXl + 6; font.weight: C.Theme.weightTitle
                       font.letterSpacing: C.Theme.tracking(C.Theme.sizeXl + 6) }
                Text { text: "Dez temas de AI Engineering para ler em ordem, cada um com prática no app."
                       color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm + 1 }
            }
            Item { Layout.fillWidth: true; visible: !root.narrow }
            C.AppField {
                objectName: "librarySearch"
                Layout.preferredWidth: root.narrow ? -1 : 300
                Layout.fillWidth: root.narrow
                placeholderText: "Buscar tema, termo ou autor"
                onTextChanged: { root.query = text; root.reload() }
            }
        }
        RowLayout {
            spacing: 6
            Repeater {
                model: [["", "Todos"], ["iniciante", "Iniciante"], ["intermediario", "Intermediário"], ["avancado", "Avançado"]]
                C.Chip { objectName: "libLevel_" + (modelData[0] || "todos"); text: modelData[1]
                         selected: root.level === modelData[0]; onClicked: { root.level = modelData[0]; root.reload() } }
            }
            Item { width: 8 }
            Text { text: root.items.length + (root.items.length === 1 ? " tema" : " temas") + " · comece pelo 01"
                   color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
        }

        GridView {
            id: grid
            objectName: "libraryGrid"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            readonly property int perRow: Math.max(1, Math.floor(width / 216))
            cellWidth: Math.floor(width / perRow)
            cellHeight: 300
            model: root.items
            keyNavigationEnabled: true
            activeFocusOnTab: true
            Keys.onReturnPressed: if (currentIndex >= 0) root.openTopic(root.items[currentIndex].id)
            delegate: Item {
                id: cell
                width: grid.cellWidth
                height: grid.cellHeight
                readonly property var pal: root.covers[(modelData.order - 1) % root.covers.length]
                readonly property bool focusHere: grid.activeFocus && grid.currentIndex === index
                Rectangle {
                    id: card
                    anchors.fill: parent
                    anchors.margins: 8
                    radius: C.Theme.r3
                    color: C.Theme.bgSurface
                    border.width: cell.focusHere ? 2 : 1
                    border.color: cell.focusHere ? C.Theme.focusRing : C.Theme.hairline
                    scale: cardMouse.pressed ? C.Theme.press : (cardMouse.containsMouse ? 1.015 : 1)
                    Behavior on scale { NumberAnimation { duration: C.Theme.dur(C.Theme.durFast); easing.type: C.Theme.easeOut } }
                    clip: true

                    // Capa: base + duas luzes difusas (sem shader; funciona no renderizador por software)
                    Item {
                        id: cover
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                        height: parent.height * 0.62
                        Rectangle { anchors.fill: parent; color: cell.pal[0] }
                        Repeater {
                            model: [[0.25, 0.35, 0.9, 1], [0.78, 0.7, 0.8, 2]]
                            Shape {
                                id: blob
                                readonly property real d: cover.width * modelData[2]
                                width: d; height: d
                                x: cover.width * modelData[0] - d / 2
                                y: cover.height * modelData[1] - d / 2
                                ShapePath {
                                    strokeWidth: -1; strokeColor: "transparent"
                                    fillGradient: RadialGradient {
                                        centerX: blob.d / 2; centerY: blob.d / 2; centerRadius: blob.d / 2
                                        focalX: blob.d / 2; focalY: blob.d / 2
                                        GradientStop { position: 0.0; color: cell.pal[modelData[3]] }
                                        GradientStop { position: 1.0; color: C.Theme.alpha(cell.pal[modelData[3]], 0) }
                                    }
                                    startX: 0; startY: 0
                                    PathLine { x: blob.d; y: 0 }
                                    PathLine { x: blob.d; y: blob.d }
                                    PathLine { x: 0; y: blob.d }
                                    PathLine { x: 0; y: 0 }
                                }
                            }
                        }
                        Text { anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
                               text: ("0" + modelData.order).slice(-2); color: "white"; opacity: 0.9
                               font.family: C.Theme.fontMono; font.pixelSize: C.Theme.sizeSm }
                        Rectangle {
                            visible: modelData.order <= 3
                            anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                            implicitWidth: startText.implicitWidth + 14; implicitHeight: 20; radius: 10
                            color: Qt.rgba(1, 1, 1, 0.88)
                            Text { id: startText; anchors.centerIn: parent; text: "comece aqui"; color: C.Theme.artBadgeText
                                   font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                        }
                    }
                    ColumnLayout {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: cover.bottom
                        anchors.margins: 12
                        spacing: 4
                        Text { Layout.fillWidth: true; text: modelData.title; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                               color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd; font.weight: Font.DemiBold }
                        Text { text: root.levelNames[modelData.level] + " · " + modelData.minutes + " min · " + modelData.readings.length + " leituras"
                               color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                    }
                    MouseArea { id: cardMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: { grid.currentIndex = index; root.openTopic(modelData.id) } }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.title + ", " + root.levelNames[modelData.level]
                }
            }
            C.EmptyState {
                anchors.centerIn: parent
                visible: grid.count === 0
                icon: "search"
                title: "Nenhum tema com essa busca"
                text: "Tente outro termo ou tire o filtro de nível."
            }
        }
    }

    // ══ Pagina de leitura ════════════════════════════════════════════
    Flickable {
        id: reader
        anchors.fill: parent
        visible: !!root.current
        clip: true
        contentWidth: width
        contentHeight: page.implicitHeight + 64
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: page
            width: Math.min(720, reader.width - 48)
            x: (reader.width - width) / 2
            y: 20
            spacing: 14

            C.Button { objectName: "libraryBack"; text: "← Biblioteca"; variant: "ghost"; compact: true
                       onClicked: root.back() }
            // Capa larga do tema
            Rectangle {
                id: banner
                Layout.fillWidth: true
                implicitHeight: 120
                radius: C.Theme.r3
                clip: true
                readonly property var pal: root.current ? root.covers[(root.current.order - 1) % root.covers.length] : C.Theme.artCovers[0]
                color: pal[0]
                Rectangle { width: banner.width * 0.7; height: width; radius: width / 2; x: -width * 0.2; y: -height * 0.55
                            color: C.Theme.alpha(banner.pal[1], 0.55) }
                Rectangle { width: banner.width * 0.5; height: width; radius: width / 2; x: banner.width * 0.62; y: -height * 0.2
                            color: C.Theme.alpha(banner.pal[2], 0.45) }
                Text { anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 16
                       text: root.current ? ("0" + root.current.order).slice(-2) + " · " + root.levelNames[root.current.level]
                                            + " · " + root.current.minutes + " min de leitura" : ""
                       color: "white"; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
            }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: root.current ? root.current.title : ""
                   color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay; font.pixelSize: C.Theme.sizeHero - 6
                   font.weight: C.Theme.weightTitle; font.letterSpacing: C.Theme.tracking(C.Theme.sizeHero - 6) }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeight: 1.35; text: root.current ? root.current.intro : ""
                   color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeLg }
            RowLayout {
                visible: !!root.current && root.current.prereqs.length > 0
                spacing: 6
                Text { text: "Antes, leia:"; color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
                Repeater {
                    model: root.current ? root.current.prereqs : []
                    C.Chip { text: modelData; onClicked: root.openTopic(modelData) }
                }
            }
            // Artigo
            Repeater {
                model: root.current ? root.current.article : []
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    spacing: 8
                    Text { text: modelData.h; color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay
                           font.pixelSize: C.Theme.sizeXl; font.weight: C.Theme.weightTitle }
                    Repeater {
                        model: modelData.p
                        Text { Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeight: 1.4; text: modelData; textFormat: Text.PlainText
                               color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd + 1 }
                    }
                }
            }
            C.Eyebrow { text: "Por que importa"; Layout.topMargin: 8 }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeight: 1.35; text: root.current ? root.current.why : ""
                   color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd + 1 }
            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: 6
                implicitHeight: practice.implicitHeight + 28
                radius: C.Theme.r3
                color: C.Theme.bgSurface
                border.width: 1
                border.color: C.Theme.hairline
                ColumnLayout {
                    id: practice
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14
                    spacing: 6
                    C.Eyebrow { text: "Pratique no app" }
                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeight: 1.3; text: root.current ? root.current.practice : ""
                           color: C.Theme.textPrimary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd }
                }
            }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap
                   text: "Termos-chave: " + (root.current ? root.current.terms.join(" · ") : "")
                   color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
            RowLayout {
                visible: !!root.current && root.current.limits !== ""
                Layout.fillWidth: true
                spacing: 8
                C.Icon { name: "alert-triangle"; size: 14; color: C.Theme.warning; Layout.alignment: Qt.AlignTop }
                Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: root.current ? root.current.limits : ""
                       color: C.Theme.textSecondary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeSm }
            }

            // Referencias: so no fim
            Rectangle { Layout.fillWidth: true; Layout.topMargin: 14; implicitHeight: 1; color: C.Theme.hairline }
            Text { text: "Leituras e referências"; color: C.Theme.textPrimary; font.family: C.Theme.fontDisplay
                   font.pixelSize: C.Theme.sizeLg; font.weight: C.Theme.weightTitle }
            Repeater {
                model: root.current ? root.current.readings : []
                delegate: ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: (index + 1) + ". " + modelData.title
                        color: linkMouse.containsMouse ? C.Theme.accent : C.Theme.textPrimary
                        font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeMd
                        font.underline: linkMouse.containsMouse
                        MouseArea { id: linkMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: Qt.openUrlExternally(modelData.url) }
                        Accessible.role: Accessible.Link
                        Accessible.name: modelData.title
                    }
                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap
                           text: modelData.authors + " · " + modelData.year + " · " + root.kindNames[modelData.kind]
                                 + (modelData.venue ? " (" + modelData.venue + ")" : "") + (modelData.note ? " — " + modelData.note : "")
                           color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs }
                }
            }
            Text { text: "Links e títulos conferidos na fonte em " + root.fmtDate(root.verifiedOn) + "."
                   color: C.Theme.textTertiary; font.family: C.Theme.fontSans; font.pixelSize: C.Theme.sizeXs; Layout.topMargin: 4 }
        }
    }
}
