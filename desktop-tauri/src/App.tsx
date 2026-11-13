import { useCallback, useEffect, useState } from "react";
import { Titlebar } from "./components/Titlebar";
import { applyAppearance, type Appearance } from "./lib/appearance";
import { core, inTauri, restartCore } from "./lib/tauri";
import { useCoreStatus } from "./lib/useCore";

// Fase 2: casca e protocolo. Esta tela confere a ligacao com o nucleo (status, provedores, eventos ao vivo).
// As telas de verdade (Tarefa, Historico, Cerebro...) chegam na Fase 4.

interface Provider {
  name: string;
  use: string;
  configured: boolean;
  next: string;
}

interface LoggedEvent {
  at: string;
  name: string;
  payload: unknown;
}

const WATCHED = [
  "phaseChanged", "planReady", "stepStart", "stepDone", "taskDone", "executionFinished", "errorRaised",
  "cancelled", "answerReady", "assistantMessage", "voiceState", "runningChanged", "windowRequest", "quickEntry",
] as const;

export function App() {
  const status = useCoreStatus();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [events, setEvents] = useState<LoggedEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (status !== "open") return;
    core()
      .call("appearance")
      .then((a) => applyAppearance(a as Appearance))
      .catch(() => {});
    core()
      .call("providerStatus")
      .then((r) => setProviders((r as { providers?: Provider[] }).providers ?? []))
      .catch((e: Error) => setError(e.message));
  }, [status]);

  useEffect(() => {
    const offs = WATCHED.map((name) =>
      core().on(name, (payload: unknown) =>
        setEvents((list) => [{ at: new Date().toLocaleTimeString(), name, payload }, ...list].slice(0, 60)),
      ),
    );
    return () => offs.forEach((off) => off());
  }, []);

  const restart = useCallback(() => {
    setError("");
    restartCore().catch((e: unknown) => setError(String(e)));
  }, []);

  return (
    <div className="flex h-full flex-col">
      <Titlebar>
        <StatusPill status={status} />
      </Titlebar>
      <main className="grid flex-1 grid-cols-1 gap-4 overflow-auto p-6 md:grid-cols-2">
        <section className="rounded-xl border border-hairline bg-surface p-5">
          <h2 className="mb-1 text-base font-semibold">Núcleo</h2>
          <p className="mb-4 text-sm text-fg-muted">
            {inTauri
              ? "Python rodando como sidecar, ligado por WebSocket local com token."
              : "Fora da casca Tauri: abra com npm run tauri dev."}
          </p>
          {error && <p className="mb-3 rounded-md bg-bad/15 p-2 text-sm text-bad">{error}</p>}
          <ul className="space-y-2">
            {providers.map((p) => (
              <li key={p.name} className="flex items-start gap-3 text-sm">
                <span className={`mt-1.5 size-2 rounded-full ${p.configured ? "bg-ok" : "bg-warn"}`} />
                <span>
                  <strong className="font-medium">{p.name}</strong>
                  <span className="block text-fg-muted">{p.configured ? p.use : p.next}</span>
                </span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={restart}
            disabled={!inTauri}
            className="mt-5 rounded-lg border border-hairline px-3 py-1.5 text-sm hover:bg-hover disabled:opacity-40"
          >
            Reiniciar núcleo
          </button>
        </section>
        <section className="flex min-h-0 flex-col rounded-xl border border-hairline bg-surface p-5">
          <h2 className="mb-3 text-base font-semibold">Eventos ao vivo</h2>
          {events.length === 0 ? (
            <p className="text-sm text-fg-muted">Nenhum evento ainda. Fale com o agente pela interface Qt ou pela voz.</p>
          ) : (
            <ol className="min-h-0 flex-1 space-y-1 overflow-auto font-mono text-xs">
              {events.map((e, i) => (
                <li key={i} className="truncate">
                  <span className="text-fg-muted">{e.at}</span> <span className="text-accent">{e.name}</span>{" "}
                  {JSON.stringify(e.payload)}
                </li>
              ))}
            </ol>
          )}
        </section>
      </main>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const label = { open: "conectado", connecting: "conectando…", closed: "desconectado" }[status] ?? status;
  const color = status === "open" ? "bg-ok" : status === "connecting" ? "bg-warn" : "bg-bad";
  return (
    <span role="status" className="flex items-center gap-2 text-xs text-fg-muted">
      <span className={`size-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
