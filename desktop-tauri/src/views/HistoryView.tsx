import { useCallback, useEffect, useMemo, useState } from "react";
import { Chip, EmptyState, Field, Skeleton, Spinner, StatusDot } from "../components/ui";
import { agentLabel } from "../lib/agents";
import { cn } from "../lib/cn";
import { core } from "../lib/tauri";
import { fmtCost, fmtDuration } from "../lib/taskStore";
import { useCoreEvent } from "../lib/useCore";
import { Page } from "./Page";

// HistoryView.qml: execucoes com resultado, duracao e custo; ao abrir, os passos e a evidencia (registro de tarefas).

interface Entry {
  id: string;
  task: string;
  success: boolean;
  duration_ms?: number;
  created_at?: number | string;
  error?: string;
  agents?: string[];
  metrics?: { api_calls?: number; tokens_est?: number; cost_usd?: number };
}

interface Stats {
  total?: number;
  success_rate?: number;
  total_cost_usd?: number;
  avg_duration_ms?: number;
}

interface Detail {
  ok: boolean;
  found?: boolean;
  state?: string;
  steps?: Array<{ step: number; action: string; description: string; ok: boolean | null; verified: boolean }>;
  error?: string;
}

type Filter = "todos" | "ok" | "falha";

function when(v: Entry["created_at"]): string {
  if (v == null) return "";
  const d = typeof v === "number" ? new Date(v * 1000) : new Date(v);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function HistoryView() {
  const [items, setItems] = useState<Entry[] | null>(null);
  const [stats, setStats] = useState<Stats>({});
  const [filter, setFilter] = useState<Filter>("todos");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    core()
      .call("loadHistory")
      .then((r) => {
        const v = r as { items?: Entry[]; stats?: Stats };
        setItems(v.items ?? []);
        setStats(v.stats ?? {});
      })
      .catch(() => setItems([]));
  }, []);
  useEffect(load, [load]);
  useCoreEvent("historyChanged", load);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items ?? []).filter(
      (e) => (filter === "todos" || (filter === "ok") === !!e.success) && (!q || e.task.toLowerCase().includes(q)),
    );
  }, [items, filter, query]);

  return (
    <Page title="Histórico" subtitle="Tudo o que o agente executou, com o resultado, o tempo e o custo de cada pedido.">
      {items && items.length > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Execuções" value={String(stats.total ?? items.length)} />
          <Stat label="Deram certo" value={`${String(stats.success_rate ?? 0).replace(".", ",")}%`} />
          <Stat label="Tempo médio" value={fmtDuration(stats.avg_duration_ms ?? 0)} />
          <Stat label="Custo total" value={fmtCost(stats.total_cost_usd ?? 0)} />
        </div>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {(["todos", "ok", "falha"] as const).map((f) => (
          <Chip key={f} selected={filter === f} onClick={() => setFilter(f)}>
            {{ todos: "Todos", ok: "Deram certo", falha: "Com falha" }[f]}
          </Chip>
        ))}
        <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar pedido" aria-label="Buscar pedido" className="ml-auto h-8 w-56 text-sm" />
      </div>
      {items === null ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-r3" />
          ))}
        </div>
      ) : shown.length === 0 ? (
        <EmptyState icon="history" title={items.length ? "Nada com esse filtro" : "Nenhuma execução ainda"}>
          {items.length ? "Tente outro filtro ou busca." : "O que o agente fizer aparece aqui, com os passos e a evidência de cada um."}
        </EmptyState>
      ) : (
        <ul className="overflow-hidden rounded-r3 border border-edge bg-glass">
          {shown.map((e) => (
            <li key={e.id} className="border-b border-hairline last:border-0">
              <button
                type="button"
                aria-expanded={open === e.id}
                onClick={() => setOpen(open === e.id ? null : e.id)}
                className="motion-fast flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-row-hover"
              >
                <StatusDot status={e.success ? "ok" : "failed"} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-md text-fg">{e.task}</span>
                  <span className="mt-0.5 block text-xs text-fg-subtle">
                    {[when(e.created_at), (e.agents ?? []).map(agentLabel).join(", ")].filter(Boolean).join(" · ")}
                  </span>
                </span>
                <span className="shrink-0 text-right text-xs tabular-nums text-fg-muted">
                  {fmtDuration(e.duration_ms ?? 0)}
                  <br />
                  {fmtCost(e.metrics?.cost_usd ?? 0)}
                </span>
              </button>
              {open === e.id && <DetailView entry={e} />}
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-r3 border border-edge bg-glass px-4 py-3">
      <p className="text-xs text-fg-muted">{label}</p>
      <p className="mt-1 text-lg font-medium tabular-nums text-fg">{value}</p>
    </div>
  );
}

function DetailView({ entry }: { entry: Entry }) {
  const [d, setD] = useState<Detail | null>(null);
  useEffect(() => {
    core()
      .call("historyDetail", entry.id)
      .then((r) => setD(r as Detail))
      .catch(() => setD({ ok: false, error: "Registro indisponível." }));
  }, [entry.id]);

  return (
    <div className="animate-enter border-t border-hairline bg-surface/40 px-4 py-3 pl-11">
      {entry.error && <p className="mb-2 text-sm text-bad">{entry.error}</p>}
      {!d ? (
        <Spinner />
      ) : !d.ok || !d.found ? (
        <p className="text-sm text-fg-subtle">{d.error || "Sem passos registrados para esta execução."}</p>
      ) : (
        <ol className="space-y-1.5">
          {(d.steps ?? []).map((s) => (
            <li key={s.step} className="flex items-start gap-2 text-sm">
              <StatusDot status={s.ok === null ? "warn" : s.ok ? "ok" : "failed"} size={13} />
              <span className={cn("text-fg", s.ok === false && "text-bad")}>
                {s.description || s.action}
                {s.verified && <span className="ml-1.5 text-xs text-ok">conferido</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
