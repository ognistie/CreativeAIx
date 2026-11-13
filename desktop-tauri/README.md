# Creative AIx — interface Tauri

Nova interface do Creative AIx: Tauri 2 (Rust) + React + TypeScript + Vite + Tailwind.
O núcleo continua sendo o Python de `ai-farm-agent/`. A casca sobe esse núcleo como sidecar
(`main.py --ui tauri --headless`) e conversa com ele por WebSocket local (JSON-RPC 2.0, token por execução).

A interface PySide6/QML continua sendo a padrão (`ui.shell: qt` no `config.yaml`) até esta ter paridade.
Plano, contrato e riscos: [docs/architecture/tauri-ui.md](../docs/architecture/tauri-ui.md).

## Requisitos (só para desenvolver a interface)

- Ambiente Python do projeto (`scripts/setup.ps1`)
- Node.js 22 LTS ou mais novo
- Rust estável (`rustup`) e as ferramentas de build C++ do Visual Studio
- WebView2 (já vem no Windows 11)

```powershell
scripts/setup.ps1 -WithTauri
```

## Rodar

```powershell
cd desktop-tauri
npm run tauri dev
```

A casca procura o Python em `CREATIVE_AIX_PYTHON`, depois em `.venv/Scripts/python.exe` na raiz do
repositório, e por fim usa `python` do PATH. O `main.py` vem de `CREATIVE_AIX_APP` ou de
`ai-farm-agent/`.

## Contrato

`src/lib/contract.gen.ts` é gerado a partir do Python. Não edite à mão:

```powershell
npm run contract        # regenera
npm run contract:check  # a CI falha se estiver desatualizado
```

Os métodos têm os mesmos nomes dos `@Slot`s do `desktop/bridge.py` e os eventos, os mesmos nomes dos
Signals. O mesmo pedido funciona no QML e aqui.

## Instalador

O workflow `.github/workflows/release.yml` faz tudo na CI (tag `v*` ou manual). Para gerar localmente:

```powershell
python ai-farm-agent/scripts/build_core.py
python ai-farm-agent/scripts/smoke_packaged_core.py build/core-bundle/core/creative-aix-core.exe
cd desktop-tauri
npx tauri build --config src-tauri/tauri.release.conf.json
```

Sai um instalador NSIS por usuário em `src-tauri/target/release/bundle/nsis/`. As chaves do usuário
ficam em `%APPDATA%\Creative AIx\.env`. Atualização automática e medições:
[docs/architecture/tauri-ui.md](../docs/architecture/tauri-ui.md), seção 11.

## Estrutura

| Caminho | O que é |
| --- | --- |
| `src/lib/core.ts` | cliente do núcleo: chamadas tipadas, eventos, reconexão |
| `src/lib/tauri.ts` | ponte com o Rust (`core_info`, `restart_core`) e cliente compartilhado |
| `src/components/Titlebar.tsx` | barra de título própria (a janela não tem moldura) |
| `src/App.tsx` | janela principal |
| `src/mini.tsx` | janela do mini chat |
| `src-tauri/src/sidecar.rs` | sobe, anuncia, reinicia e encerra o núcleo Python |
| `src-tauri/capabilities/default.json` | permissões mínimas das janelas (sem shell, sem fs) |
