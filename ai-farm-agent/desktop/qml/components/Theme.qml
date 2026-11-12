// Tokens visuais. Identidade da abertura em todo o app: luzes suaves de fundo
// (paleta) atras de paineis de vidro. Dois temas: escuro (padrao) e claro.
// Mude aqui e a UI segue: nenhuma tela usa cor solta.
// accent, palette, ambient, motion, radiusStyle, mode e blur sao gravaveis: Main.qml aplica
// o que o usuario salvou (Bridge.appearance) ao abrir e ao salvar o Harness.
// Cada token com tema e escrito como `dark ? <escuro> : <claro>` numa linha so:
// scripts/check_contrast.py le este arquivo e mede o contraste AA de cada par.
pragma Singleton
import QtQuick

QtObject {
    // ─── Tema ───────────────────────────────────────────────────────
    property string mode: "escuro"          // escuro | claro
    readonly property bool dark: mode === "escuro"
    property bool blur: true                // vidro com desfoque real do fundo (so com GPU)
    // O fundo (Ambient) que os paineis de vidro desfocam; Main.qml aponta ao abrir
    property Item backdrop: null
    // Papel de parede (E4): url da imagem, escurecimento e a paleta extraida dela (core/wallpapers.py).
    // Com foto, as luzes e o destaque vem da paleta e o vidro ganha o reforco medido para AA.
    property string wallpaper: ""
    property string wallpaperUrl: ""
    property real dim: 0.35
    // O escurecimento (escuro) ou o veu branco (claro) nunca fica abaixo do minimo medido na foto para o texto
    // solto ler com AA (core/wallpapers.py: min_dim / min_veil)
    // Claro com foto: o texto solto (titulo, sugestoes) ganha vidro atras dele em vez de velar a imagem inteira
    readonly property bool photoLight: photo !== null && !dark
    readonly property real photoVeil: photo ? Math.max(dim, dark ? (photo.min_dim || 0) : (photo.min_veil || 0)) : 0
    property var photo: null
    readonly property real glassBoost: photo ? (photo.glass_boost || 0) : 0

    // ─── Superficies ────────────────────────────────────────────────
    property color bgSidebar:   dark ? Qt.rgba(0.004, 0.075, 0.072, 0.58) : Qt.rgba(0.975, 0.985, 0.978, 0.70)
    readonly property color bgBase:      splashBase
    property color bgSurface:   dark ? "#0F2422" : "#FFFFFF"
    // Vidro: paineis sobre o ambiente (texto com contraste AA medido sobre a luz mais clara)
    property color bgGlass:     dark ? Qt.rgba(0.004, 0.115, 0.11, 0.70) : Qt.rgba(0.985, 0.99, 0.985, 0.74)
    property color bgGlassHi:   dark ? Qt.rgba(0.0, 0.17, 0.16, 0.84) : Qt.rgba(1, 1, 1, 0.88)
    property color glassEdge:   dark ? Qt.rgba(0.93, 1, 1, 0.10) : Qt.rgba(1, 1, 1, 0.90)
    property color bgSurfaceHi: dark ? "#19302E" : "#E9EFEB"
    property color bgHover:     dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.04)
    property color bgPressed:   dark ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.07)
    // Pilulas e linhas de lista: repouso e hover sobre vidro
    property color bgChip:      dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.50)
    property color bgRowHover:  dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.60)
    property color hairline:    dark ? Qt.rgba(0.93, 1, 1, 0.10) : Qt.rgba(0, 0.22, 0.20, 0.12)
    property color hairlineHi:  dark ? Qt.rgba(0.93, 1, 1, 0.18) : Qt.rgba(0, 0.22, 0.20, 0.20)
    property color sheen:       dark ? Qt.rgba(1, 1, 1, 0.045) : Qt.rgba(1, 1, 1, 0.0)
    property color shadow:      dark ? Qt.rgba(0, 0, 0, 0.35) : Qt.rgba(0.35, 0.25, 0.45, 0.06)
    // ─── Elevacao: profundidade em vez de contorno ──────────────────
    // Claro: sombra macia em camadas (sem borda). Escuro: so uma borda de luz interna, quase invisivel.
    property color edge:        dark ? Qt.rgba(0.93, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.0)
    property color shadowSoft:  dark ? Qt.rgba(0, 0, 0, 0.0) : Qt.rgba(0.02, 0.12, 0.11, 0.045)
    readonly property int edgeWidth: dark ? 1 : 0

    // ─── Texto ──────────────────────────────────────────────────────
    property color textPrimary:   dark ? "#EDFFFE" : "#102825"
    property color textSecondary: dark ? "#BBC7C6" : "#4C625E"
    property color textTertiary:  dark ? "#A8B8B6" : "#4F6561"
    property color textInverse:   dark ? "#011D1C" : "#FFFFFF"

    // ─── Acao primaria, destaque e status ───────────────────────────
    property color primary:   dark ? "#EDFFFE" : "#102825"
    property color accent:             "#16897E"
    property color success:   dark ? "#4CC56A" : "#28A745"
    property color danger:    dark ? "#FF6B5F" : "#E5372B"
    property color warning:   dark ? "#F2A33A" : "#D97706"
    readonly property color info:      accent
    property color phosphor:  dark ? "#FDE9FF" : "#6B3A73"
    property color focusRing: dark ? "#9FE6DF" : "#156B64"

    // ─── Ambiente (luzes da abertura) ───────────────────────────────
    // aurora = o filme de lancamento (pessego, laranja, lilas); as outras sao variacoes.
    // Cada paleta tem a versao clara e a escura (base + 3 luzes).
    property string palette: "abismo"
    property real ambient: 0.55          // intensidade das luzes no app (0 = so a base)
    property bool motion: true           // luzes em deriva lenta; false = paradas
    // Fundo: "malha" = gradiente organico em GPU (shader) com as cores da paleta; "luzes" = manchas classicas.
    // Sem GPU (renderizador por software) a malha cai para as luzes. fluxo: parado | sutil | normal.
    property bool mesh: true
    property string flow: "sutil"
    property bool fluted: false          // vidro canelado sobre o fundo (nunca atras de texto: so no ambiente)
    readonly property real flowSpeed: !motion || flow === "parado" ? 0 : (flow === "normal" ? 1.0 : 0.45)
    readonly property var palettes: ({
        "abismo": ["#F4F7F4", "#CFE6DF", "#E3EEE6", "#E4DDEF"],
        "ameixa": ["#F8F3F5", "#E9C9D8", "#F1D3DC", "#D9C8E6"],
        "nevoa":  ["#F6F5EE", "#CFE7DD", "#E4EFE3", "#D6E6E4"],
        "matcha": ["#F5F2E8", "#D2DFB8", "#E8E2CC", "#C9D9B4"],
        "seda":   ["#FBF4F1", "#F6C7B8", "#F3CAD6", "#DCCBF2"],
        "aurora": ["#FBF7F4", "#F8C3AE", "#F9D29A", "#D7C6F4"],
        "brisa":  ["#F5F8FB", "#B9DDF6", "#C7EEDC", "#D9D0F7"],
        "coral":  ["#FBF6F3", "#F7B4A8", "#F6D5B8", "#F2C4DD"],
        "menta":  ["#F4FAF7", "#BDE8D5", "#DDF0C4", "#C6DDF4"],
        "lavanda": ["#F8F6FC", "#D9CCF7", "#F3D0E8", "#C9D6F7"],
        "areia":  ["#FBF8F2", "#F2DDB8", "#EFCBB0", "#DCE3CF"],
        "oceano": ["#F3F7FA", "#A9CFEF", "#B5E3E6", "#C8C4F2"],
        "aurora-boreal": ["#F4F8F8", "#B3EBD9", "#BFD5F7", "#E2C8F4"]
    })
    readonly property var darkPalettes: ({
        "abismo": ["#011D1C", "#003734", "#0E4A47", "#3A2E4A"],
        "ameixa": ["#160B14", "#4A1C3A", "#6E2A4A", "#3A1A4A"],
        "nevoa":  ["#0B1715", "#1E4A40", "#2C5A50", "#20403E"],
        "matcha": ["#10140C", "#34482A", "#4A5236", "#2C4030"],
        "seda":   ["#170E14", "#6A3038", "#5E2A4E", "#3E2A66"],
        "aurora": ["#120F17", "#7A3E3A", "#7A5A2A", "#4A3A78"],
        "brisa":  ["#0E141B", "#2A4F6E", "#2E5E4C", "#3F3C70"],
        "coral":  ["#161013", "#8A3F3A", "#7A5540", "#6E3F62"],
        "menta":  ["#0F1613", "#2E6A54", "#4C6B2E", "#2F4F78"],
        "lavanda": ["#13111A", "#4E3F80", "#703F66", "#3A4C7A"],
        "areia":  ["#17140F", "#7A6236", "#73513D", "#4E5A3E"],
        "oceano": ["#0E141A", "#255C86", "#2A6E72", "#3E3A7A"],
        "aurora-boreal": ["#0E1516", "#2A6E5A", "#2F4F78", "#5A3F78"]
    })
    readonly property var tones: (photo && dark) ? [photo.base].concat(photo.tones) : ((dark ? darkPalettes : palettes)[palette] || palettes["abismo"])
    readonly property color splashBase:   tones[0]
    readonly property color splashPeach:  tones[1]
    readonly property color splashOrange: tones[2]
    readonly property color splashLilac:  tones[3]

    // ─── Espacamento e raios ────────────────────────────────────────
    readonly property int sp1: 4
    readonly property int sp2: 8
    readonly property int sp3: 12
    readonly property int sp4: 16
    readonly property int sp5: 24
    readonly property int sp6: 32

    // Cantos: suave (padrao), reto ou redondo. Uma escala so (r1..r4); dentro de algo arredondado use
    // nested(raio de fora, espacamento): o canto de dentro acompanha o de fora (raio aninhado).
    property string radiusStyle: "suave"
    readonly property real rScale: radiusStyle === "reto" ? 0.35 : (radiusStyle === "redondo" ? 1.6 : 1.0)
    readonly property int r1: Math.round(6 * rScale)      // selos, marcas pequenas
    readonly property int r2: Math.round(10 * rScale)     // campos, linhas de lista, itens da barra lateral
    readonly property int r3: Math.round(16 * rScale)     // cartoes
    readonly property int r4: Math.round(20 * rScale)     // paineis
    readonly property int rSm: r2
    readonly property int rMd: r3
    readonly property int rLg: r4
    readonly property int rComposer: Math.round(22 * rScale)   // a caixa de pedido: o componente ancora
    function nested(outer, pad) { return Math.max(2, Math.round(outer - pad)) }

    function applyAppearance(a) {
        if (!a) return
        if (/^#[0-9A-Fa-f]{6}$/.test(a.accent || "")) accent = a.accent
        if (palettes[a.palette]) palette = a.palette
        if (typeof a.ambient === "number") ambient = Math.max(0, Math.min(1, a.ambient))
        if (typeof a.motion === "boolean") motion = a.motion
        if (["suave", "reto", "redondo"].indexOf(a.radius) >= 0) radiusStyle = a.radius
        if (a.mode === "escuro" || a.mode === "claro") mode = a.mode
        if (typeof a.blur === "boolean") blur = a.blur
        if (typeof a.dim === "number") dim = Math.max(0, Math.min(1, a.dim))
        if (typeof a.mesh === "boolean") mesh = a.mesh
        if (["parado", "sutil", "normal"].indexOf(a.flow) >= 0) flow = a.flow
        if (typeof a.fluted === "boolean") fluted = a.fluted
        if (typeof a.wallpaper === "string") setWallpaper(a.wallpaper, a.accent)
    }

    // Troca a foto do fundo e deriva o tema dela (a cor de destaque salva continua valendo se houver)
    function setWallpaper(id, savedAccent) {
        if (id === wallpaper) return
        wallpaper = id
        if (!id || typeof Bridge === "undefined") { wallpaperUrl = ""; photo = null; return }
        const r = JSON.parse(Bridge.wallpaperInfo(id))
        if (!r.ok) { wallpaper = ""; wallpaperUrl = ""; photo = null; return }
        wallpaperUrl = "file:///" + r.item.path.split("\\").join("/")
        photo = r.item.palette
        if (!/^#[0-9A-Fa-f]{6}$/.test(savedAccent || "")) accent = photo.accent
    }

    // Largura maxima da coluna de leitura (tela de tarefa e historico)
    readonly property int contentMax: 760

    // ─── Tipografia ─────────────────────────────────────────────────
    readonly property string fontSans:    "Segoe UI Variable Text"
    // Titulos: Segoe UI Variable Display (vem no Windows 11), peso 500 e tracking negativo; texto: Segoe UI Variable.
    readonly property string fontDisplay: "Segoe UI Variable Display"
    readonly property int weightTitle: Font.Medium
    function tracking(px) { return px >= 28 ? -px * 0.03 : (px >= 18 ? -px * 0.015 : 0) }
    readonly property real trackingLabel: 1.1          // micro-rotulos em caixa alta
    readonly property string fontMono:    "Cascadia Mono"
    readonly property string fontIcons:   "Segoe Fluent Icons"

    readonly property int sizeXs:   11
    readonly property int sizeSm:   12
    readonly property int sizeMd:   14
    readonly property int sizeLg:   16
    readonly property int sizeXl:   20
    readonly property int sizeHero: 34

    // ─── Movimento: uma gramatica so ────────────────────────────────
    // fast = cor, hover, pressao; normal = tamanho e posicao; slow = entradas grandes. Tudo passa por
    // dur(): com "luzes paradas" (motion = false) as duracoes viram 0 e nada se move.
    readonly property int durFast: 140
    readonly property int durNormal: 220
    readonly property int durPanel: 320
    readonly property int durSlow: 400
    readonly property int easeStandard: Easing.InOutCubic   // cor e estado
    readonly property int easeOut: Easing.OutCubic          // entrar, crescer
    readonly property int easeIn: Easing.InCubic            // sair
    readonly property real press: 0.985                      // escala ao pressionar (discreta)
    readonly property int stagger: 40                        // atraso entre itens de uma lista que entra
    function dur(ms) { return motion ? ms : 0 }
    // Numeros tabulares (metricas, custo, tempo): os digitos nao "dancam" ao mudar
    readonly property var tabular: ({ "tnum": 1 })

    function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    // Arte (capas da Biblioteca, pastas do Diario): sempre escura por baixo e texto branco em cima, nos dois
    // temas, como uma capa de livro. Tres cores cada: base, luz 1, luz 2.
    readonly property var artCovers: [["#0E4A47", "#3FD0B8", "#F2C14E"], ["#1D2B6B", "#5B8CFF", "#E86FB2"],
                                      ["#3A1D5C", "#B07CFF", "#56D3F0"], ["#5A2A12", "#FF8A3D", "#FFD36E"],
                                      ["#123B2A", "#5BD48A", "#C9F06B"], ["#40154A", "#FF5FA2", "#8A7CFF"],
                                      ["#0D2F52", "#39A0FF", "#7CF2D6"], ["#2B2B2B", "#C7C7C7", "#FF6B5F"],
                                      ["#1C3D16", "#8ED65B", "#3FB7D6"], ["#4A1F12", "#FF7A59", "#FFB86B"]]
    readonly property var artFolders: ({ rotinas: ["#B0245F", "#FF8FB1", "#FFC9DA"], notas: ["#283A94", "#F5D76E", "#7FD1FF"],
                                         agentes: ["#1C1C1F", "#6A6A70", "#C8C8CE"], assuntos: ["#0E5A52", "#4FD1B5", "#F2C14E"] })
    readonly property color artInk:      "#151515"      // botao "+" sobre a arte
    readonly property color artInkHover: "#000000"
    readonly property color artBadgeText: "#102825"     // selo claro sobre a arte

    // Nome amigavel do agente (o backend usa CODE, DATA, ...)
    function agentLabel(name) {
        switch ((name || "").toUpperCase()) {
            case "MAESTRO": return "Maestro"
            case "CODE":    return "Código"
            case "DATA":    return "Dados"
            case "WEB":     return "Web"
            case "DESKTOP": return "Desktop"
            case "FILE":    return "Arquivos"
            case "EXTCODE": return "Claude / Codex"
            case "MEMORY":  return "Memória"
            case "SYSTEM":  return "Sistema"
            default:        return name || ""
        }
    }
}
