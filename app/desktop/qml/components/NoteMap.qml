// Mapa local de ligacoes: a nota no centro, as que ela liga ou que a citam no
// primeiro anel e as vizinhas destas no segundo. Clique num no para ir ate ele
// (o mapa se reorganiza em volta da nova nota).
import QtQuick

Item {
    id: root
    property var graph: null
    property string center: ""
    signal picked(string rel)

    // Elipses que usam a area toda (o painel e mais largo que alto)
    readonly property real r1: Math.min(width * 0.26, height * 0.36)
    readonly property real r2: Math.min(width * 0.42, height * 0.62)
    readonly property real squash: Math.min(1, height * 0.86 / Math.max(1, width * 0.86))
    readonly property var layout: compute(graph, center, width, height)

    // Registros automaticos (execucoes, diario) ficam por ultimo: o mapa mostra primeiro o curado
    function weight(id) { return /^(40 Execucoes|50 Diario)\//.test(id) || /^\d{4}-\d{2}-\d{2}/.test(id) ? 1 : 0 }

    function compute(g, c, w, h) {
        if (!g || !c || w <= 0) return { nodes: [], edges: [] }
        const adj = {}
        const link = (a, b) => { (adj[a] = adj[a] || []).indexOf(b) < 0 && adj[a].push(b) }
        for (const e of g.edges) { link(e.from, e.to); link(e.to, e.from) }
        const title = {}
        for (const n of g.nodes) title[n.id] = n.title
        const rank = (a, b) => weight(a) - weight(b) || (adj[b] || []).length - (adj[a] || []).length
        const ring1 = (adj[c] || []).slice().sort(rank).slice(0, 12)
        const ring2 = [], parent = {}
        ring1.forEach((r, i) => {
            const kids = (adj[r] || []).filter(x => x !== c && ring1.indexOf(x) < 0 && ring2.indexOf(x) < 0)
                                       .sort(rank).slice(0, 2)
            for (const x of kids) if (ring2.length < 16) { ring2.push(x); parent[x] = i }
        })
        const cx = w / 2, cy = h / 2
        const place = (a, r) => [cx + Math.cos(a) * r, cy + Math.sin(a) * r * squash]
        const nodes = [{ id: c, title: title[c] || c, x: cx, y: cy, level: 0 }]
        const step1 = 2 * Math.PI / Math.max(1, ring1.length)
        ring1.forEach((id, i) => {
            const p = place(-Math.PI / 2 + i * step1, r1)
            nodes.push({ id: id, title: title[id] || id, x: p[0], y: p[1], level: 1 })
        })
        // Segundo anel: na ordem dos "pais" (fica perto deles), espalhado sem amontoar
        const step2 = 2 * Math.PI / Math.max(1, ring2.length)
        ring2.forEach((id, i) => {
            const p = place(-Math.PI / 2 + i * step2 + step2 / 2, r2)
            nodes.push({ id: id, title: title[id] || id, x: p[0], y: p[1], level: 2 })
        })
        const shown = {}
        for (const n of nodes) shown[n.id] = n
        const edges = []
        for (const n of nodes)
            for (const x of (adj[n.id] || [])) {
                const m = shown[x]
                // Sem fios entre vizinhos distantes do mesmo anel: so o que ajuda a ler
                if (m && n.id < x && (n.level === 0 || m.level === 0 || n.level !== m.level)) edges.push([n, m])
            }
        return { nodes: nodes, edges: edges }
    }

    onLayoutChanged: wires.requestPaint()

    // Aneis guia
    Repeater {
        model: [root.r1, root.r2]
        Rectangle {
            x: root.width / 2 - modelData; y: root.height / 2 - modelData * root.squash
            width: modelData * 2; height: modelData * 2 * root.squash
            radius: width / 2
            color: "transparent"
            border.width: 1
            border.color: Theme.alpha(Theme.textPrimary, 0.05)
        }
    }

    Canvas {
        id: wires
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            for (const e of root.layout.edges) {
                const strong = e[0].level === 0 || e[1].level === 0
                ctx.strokeStyle = strong ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45)
                                         : "rgba(30,30,40,0.10)"
                ctx.lineWidth = strong ? 1.4 : 1
                ctx.beginPath()
                ctx.moveTo(e[0].x, e[0].y)
                const mx = (e[0].x + e[1].x) / 2, my = (e[0].y + e[1].y) / 2
                ctx.quadraticCurveTo(mx + (root.height / 2 - my) * 0.08, my + (mx - root.width / 2) * 0.08, e[1].x, e[1].y)
                ctx.stroke()
            }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    Repeater {
        model: root.layout.nodes
        Rectangle {
            id: node
            readonly property int level: modelData.level
            x: modelData.x - width / 2
            y: modelData.y - height / 2
            width: Math.min(level === 0 ? 220 : (level === 1 ? 160 : 130), label.implicitWidth + (level === 2 ? 16 : 24))
            height: level === 0 ? 38 : (level === 1 ? 30 : 24)
            radius: height / 2
            color: level === 0 ? Theme.accent : (mouse.containsMouse ? Theme.bgSurface : (level === 1 ? Theme.bgGlassHi : Theme.bgGlass))
            border.width: level === 0 ? 0 : 1
            border.color: level === 1 ? Theme.alpha(Theme.accent, mouse.containsMouse ? 0.7 : 0.35) : Theme.hairline
            opacity: 0
            scale: mouse.containsMouse && level > 0 ? 1.06 : 1
            Behavior on scale { NumberAnimation { duration: Theme.dur(Theme.durFast) } }
            Component.onCompleted: appear.start()
            NumberAnimation { id: appear; target: node; property: "opacity"; to: node.level === 2 ? 0.85 : 1
                              duration: Theme.dur(260 + node.level * 140); easing.type: Easing.OutCubic }
            Text {
                id: label
                anchors.centerIn: parent
                width: Math.min(implicitWidth, parent.width - 14)
                text: modelData.title
                elide: Text.ElideRight
                color: node.level === 0 ? Theme.textInverse : (node.level === 1 ? Theme.textPrimary : Theme.textSecondary)
                font.family: Theme.fontSans
                font.pixelSize: node.level === 0 ? 14 : (node.level === 1 ? 12 : 11)
                font.weight: node.level === 0 ? Font.DemiBold : Font.Normal
            }
            MouseArea {
                id: mouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: node.level > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: if (node.level > 0) root.picked(modelData.id)
            }
            Accessible.role: Accessible.Button
            Accessible.name: modelData.title
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.layout.nodes.length <= 1
        anchors.verticalCenterOffset: 50
        text: root.graph ? "Esta nota ainda não tem ligações. Use [[Nome]] no texto." : "Carregando o mapa…"
        color: Theme.textTertiary
        font.family: Theme.fontSans
        font.pixelSize: Theme.sizeSm + 1
    }
}
