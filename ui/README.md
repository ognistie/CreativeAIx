# Creative AIx — interface

React + TypeScript + Vite + Tailwind. O app (`python app/main.py`) abre esta interface em janelas Qt
(QtWebEngine, `app/desktop/web_host.py`) e ela conversa com o núcleo Python por WebSocket local
(JSON-RPC 2.0, token por execução). `dist/` é o que o app carrega e vai no repositório: quem só usa o app
não precisa de Node.

## Desenvolver

Requisitos: Node.js 22 LTS ou mais novo.

```powershell
cd ui
npm ci
npm run dev          # http://127.0.0.1:1420/?demo  (núcleo falso, sem Python)
npm run build        # atualiza ui/dist, que o app carrega
```

`?nosplash` pula a abertura; `#galeria` mostra os componentes do design system.

## Gerados (não edite à mão)

```powershell
npm run contract     # src/lib/contract.gen.ts  <- app/desktop (métodos e eventos do núcleo)
npm run tokens       # src/styles/tokens.css e src/lib/icons.gen.ts  <- app/design/*.json
```

A CI confere os dois (`contract:check`, `tokens:check`) e o carimbo de `dist/` (`build:check`).
