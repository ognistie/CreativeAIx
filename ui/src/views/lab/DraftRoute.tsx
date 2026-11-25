import { useEffect, useState } from "react";
import { Button, Field } from "../../components/ui";
import { core } from "../../lib/host";
import { AGENTS, AGENT_LOOK, call } from "./types";

type Route = { agent: string; prefix: string };
type SavedRoutes = { base?: string; rota_salva?: Route; rota_aplicada?: Route };
type Trial = { matched: boolean; agent?: string; original?: string[]; revision: string; rule: string };

function routeRequest(note: string, action: string, data: object = {}) {
  return call(core().call("labDraftRoute", JSON.stringify({ note, action, ...data })));
}

export function DraftRoute({ note }: { note: string }) {
  const [saved, setSaved] = useState<SavedRoutes | null>(null);
  const [route, setRoute] = useState<Route>({ agent: "", prefix: "" });
  const [request, setRequest] = useState("");
  const [trial, setTrial] = useState<Trial | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void routeRequest(note, "load").then((reply) => {
      if (!active) return;
      if (!reply.ok) { setError(reply.error ?? "Não deu para ler a rota."); return; }
      const routes = reply as SavedRoutes;
      setSaved(routes);
      setRoute(routes.rota_salva ?? { agent: routes.base ?? "DESKTOP", prefix: "" });
    });
    return () => { active = false; };
  }, [note]);

  const act = async (action: "save" | "apply" | "test", applied = false) => {
    setBusy(true);
    setError("");
    setTrial(null);
    const reply = await routeRequest(note, action, { route, request, applied, confirmed: action === "apply" });
    setBusy(false);
    if (!reply.ok) { setError(reply.error ?? "Não deu para concluir."); return; }
    if (action === "test") setTrial(reply.trial as Trial);
    else setSaved(reply as SavedRoutes);
  };

  const ready = route.prefix.trim().length >= 2;
  const dirty = route.agent !== saved?.rota_salva?.agent || route.prefix.trim() !== saved?.rota_salva?.prefix;
  return (
    <section className="space-y-3" aria-label="Rota do rascunho">
      <p className="text-sm text-fg-muted">Simule qual agente receberia um pedido pelo início da frase. O teste só verifica a rota.</p>
      {saved && <>
        <label className="flex items-center gap-2 text-sm">Agente-base
          <select value={route.agent} onChange={(e) => setRoute({ ...route, agent: e.target.value })}
            className="rounded-r2 border border-hairline bg-surface px-3 py-2">
            {AGENTS.slice(1).map((agent) => <option key={agent} value={agent}>{AGENT_LOOK[agent]!.name}</option>)}
          </select>
        </label>
        <Field aria-label="Início do pedido" placeholder="Início do pedido (ex.: organize arquivos)" value={route.prefix}
          maxLength={80} onChange={(e) => setRoute({ ...route, prefix: e.target.value })} />
        <Field aria-label="Pedido de teste" placeholder="Digite um pedido para testar a rota" value={request}
          maxLength={1000} onChange={(e) => setRequest(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          <Button size="compact" disabled={busy || !ready || !request.trim()} onClick={() => void act("test")}>Testar prévia</Button>
          <Button size="compact" disabled={busy || !ready || !dirty} onClick={() => void act("save")}>Salvar rota</Button>
          <Button size="compact" disabled={busy || dirty || !saved.rota_salva} onClick={() => void act("apply")}>Aplicar rota aos pedidos</Button>
          {saved.rota_aplicada && <Button size="compact" disabled={busy || !request.trim()} onClick={() => void act("test", true)}>Testar rota aplicada</Button>}
        </div>
        {saved.rota_aplicada && <p className="text-xs text-fg-muted">Rota aplicada aos pedidos reais — {AGENT_LOOK[saved.rota_aplicada.agent]?.name} · {saved.rota_aplicada.prefix}</p>}
      </>}
      {trial && <div role="status" className="rounded-r2 bg-surface p-3 text-sm">
        <p>{trial.matched
          ? `O pedido chegou ao rascunho com a rota de ${AGENT_LOOK[trial.agent ?? ""]?.name}.`
          : trial.original?.length ? `Seguiu a rota original para ${trial.original.map((agent) => AGENT_LOOK[agent]?.name ?? agent).join(", ")}.`
            : "O início do pedido não ativou o rascunho. A rota original depende do Maestro."}</p>
        <p className="text-xs text-fg-muted">Versão {trial.revision} · Regra “{trial.rule}”</p>
      </div>}
      {error && <p role="alert" className="text-sm text-bad-ink">{error}</p>}
    </section>
  );
}
