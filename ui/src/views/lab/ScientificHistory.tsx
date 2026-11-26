import { useCallback, useEffect, useState } from "react";
import { Button, GlassPanel } from "../../components/ui";
import { core } from "../../lib/host";

interface Entry {
  id: string;
  when: string;
  objective?: string;
  candidate?: string;
  baseline?: string;
  run?: string;
  result: string;
  origin?: string;
  reasons?: string[];
  rates?: Record<string, number | null>;
}

export function ScientificHistory({ agent }: { agent: string }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Entry | null>(null);
  const [busy, setBusy] = useState(false);
  const reload = useCallback(async () => {
    try {
      const result = await core().call("rsiHistory", agent) as { ok: boolean; entries?: Entry[]; error?: string };
      if (!result.ok) throw new Error(result.error || "Não foi possível consultar a memória científica.");
      setEntries(result.entries || []);
      setError("");
    } catch (err) { setError(String(err)); }
  }, [agent]);
  useEffect(() => { void reload(); }, [reload]);

  async function decide(decision: string) {
    if (!selected?.candidate) return;
    setBusy(true);
    try {
      const result = await core().call("rsiDecide", selected.candidate, decision, true) as { ok: boolean; error?: string };
      if (!result.ok) throw new Error(result.error || "A decisão foi recusada.");
      setSelected(null);
      await reload();
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }

  return <GlassPanel className="my-4 p-4">
    <div className="flex items-center justify-between gap-3">
      <h3 className="font-semibold text-fg">Memória científica · RSI</h3>
      <Button onClick={() => void reload()}>Atualizar</Button>
    </div>
    {error && <p role="alert" className="my-2 text-sm">{error}</p>}
    {entries.length === 0 && <p className="my-3 text-sm text-fg-muted">Nenhuma hipótese registrada para este agente.</p>}
    {entries.map(entry => <article key={entry.id} className="my-3 border-t border-white/10 py-3">
      <p className="text-sm text-fg">{entry.objective || entry.candidate || "Decisão do operador"}</p>
      <p className="text-xs text-fg-muted">{entry.when} · {entry.result} · {entry.origin || "Registro local"}</p>
      {entry.rates && Object.entries(entry.rates).map(([version, rate]) =>
        <p key={version} className="text-xs text-fg-muted">{version} · {rate === null ? "Sem taxa válida" : (rate * 100).toFixed(1) + "%"}</p>)}
      {entry.reasons?.map(reason => <p key={reason} className="text-xs text-fg-muted">{reason}</p>)}
      {entry.candidate && <Button onClick={() => setSelected(entry)}>Revisar {entry.candidate}</Button>}
    </article>)}
    {selected && <div className="border-t border-white/10 pt-3">
      <p className="text-sm text-fg">Confirmar decisão para {selected.candidate}?</p>
      <p className="my-2 text-xs text-fg-muted">A promoção passa pela avaliação reservada exigida pelo Lab. O histórico de versões mantém o rollback.</p>
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => void decide("promover")}>Confirmar promoção</Button>
        <Button disabled={busy} onClick={() => void decide("rejeitar")}>Rejeitar hipótese</Button>
        <Button disabled={busy} onClick={() => setSelected(null)}>Cancelar</Button>
      </div>
    </div>}
  </GlassPanel>;
}
