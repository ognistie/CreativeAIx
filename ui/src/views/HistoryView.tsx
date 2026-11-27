import { useCallback, useEffect, useMemo, useState } from "react";
import { Chip, EmptyState, Field, Icon, Skeleton, Spinner, StatusDot, type IconName } from "../components/ui";
import { agentLabel } from "../lib/agents";
import { cn } from "../lib/cn";
import { core } from "../lib/host";
import { fmtCost, fmtDuration } from "../lib/taskStore";
import { useCoreEvent } from "../lib/useCore";
import { Page } from "./Page";

// HistoryView: execucoes com resultado, duracao e custo; ao abrir, os passos e a evidencia (registro de tarefas).

interface Entry {
  id: string;
  task: string;
  success: boolean;
  duration_ms?: number;
  created_at?: number | string;
  started_at?: string;
  error?: string;
  agents?: string[];
  subtasks?: Array<{ agent?: string }>;
  metrics?: { api_calls?: number; tokens_est?: number; cost_usd?: number; cost_known?: boolean };
}

interface Stats {
  total?: number;
  success_rate?: number;
  total_cost_usd?: number;
  unknown_cost_runs?: number;
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

function entryAgents(entry: Entry): string[] {
  return [...new Set(entry.agents ?? entry.subtasks?.flatMap(({ agent }) => agent ? [agent] : []) ?? [])];
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
          <Stat icon="layers" label="Execuções" value={String(stats.total ?? items.length)} />
          <Stat icon="check-circle" label="Deram certo" value={`${String(stats.success_rate ?? 0).replace(".", ",")}%`} />
          <Stat icon="clock" label="Tempo médio" value={fmtDuration(stats.avg_duration_ms ?? 0)} />
          <Stat icon="chart" label={stats.unknown_cost_runs ? "Subtotal com custo registrado" : "Custo total"}
            value={stats.unknown_cost_runs === stats.total && stats.total ? "Desconhecido" : fmtCost(stats.total_cost_usd ?? 0)} />
        </div>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {(["todos", "ok", "falha"] as const).map((f) => (
          <Chip key={f} icon={({ todos: "list", ok: "check-circle", falha: "alert-circle" } as const)[f]} selected={filter === f} onClick={() => setFilter(f)}>
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
        <ul className="space-y-3">
          {shown.map((e) => (
            <li key={e.id} className="roll-item">
              <div className={cn("receipt overflow-hidden rounded-r3 border border-edge bg-glass backdrop-blur-xl", open === e.id && "border-hairline-hi")}>
                <button
                  type="button"
                  aria-expanded={open === e.id}
                  onClick={() => setOpen(open === e.id ? null : e.id)}
                  className="motion-fast flex w-full items-stretch text-left transition-colors hover:bg-row-hover"
                >
                  <span aria-hidden className={cn("receipt-stub grid w-14 shrink-0 place-items-center", e.success ? "text-ok-ink" : "text-bad-ink")}>
                    <Icon name={e.success ? "verified" : "alert-triangle"} size={20} />
                  </span>
                  <span className="min-w-0 flex-1 px-4 py-3">
                    <span className="block truncate text-md font-medium text-fg">{e.task}</span>
                    <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-fg-muted">
                      <span className="flex items-center gap-1">
                        <Icon name="calendar" size={11} /> {when(e.started_at ?? e.created_at)}
                      </span>
                      {entryAgents(e).length > 0 && (
                        <span className="flex items-center gap-1">
                          <Icon name="network" size={11} /> {entryAgents(e).map(agentLabel).join(", ")}
                        </span>
                      )}
                      <span className={cn("font-mono uppercase tracking-[0.08em]", e.success ? "text-ok-ink" : "text-bad-ink")}>{e.success ? "concluída" : "falhou"}</span>
                    </span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end justify-center gap-0.5 px-4 text-xs tabular-nums text-fg-muted">
                    <span className="flex items-center gap-1">
                      <Icon name="clock" size={11} /> {fmtDuration(e.duration_ms ?? 0)}
                    </span>
                    <span>{e.metrics?.cost_usd === undefined || e.metrics.cost_known === false
                      || (e.metrics.cost_usd === 0 && e.metrics.cost_known !== true && e.metrics.api_calls !== 0)
                      ? "Custo desconhecido" : fmtCost(e.metrics.cost_usd)}</span>
                  </span>
                  <span aria-hidden className="grid w-9 shrink-0 place-items-center text-fg-muted">
                    <Icon name={open === e.id ? "chevron-up" : "chevron-down"} size={14} />
                  </span>
                </button>
                {open === e.id && <DetailView entry={e} />}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}

function Stat({ icon, label, value }: { icon: IconName; label: string; value: string }) {
  return (
    <div className="rounded-r3 border border-edge bg-glass px-4 py-3 backdrop-blur-xl">
      <p className="flex items-center gap-1.5 text-xs text-fg-muted">
        <Icon name={icon} size={12} /> {label}
      </p>
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
    <div className="animate-enter border-t border-hairline bg-surface/40 px-4 py-3 pl-[72px]">
      {entry.error && <p className="mb-2 text-sm text-bad-ink">{entry.error}</p>}
      {!d ? (
        <Spinner />
      ) : !d.ok || !d.found ? (
        <p className="text-sm text-fg-subtle">{d.error || "Sem passos registrados para esta execução."}</p>
      ) : (
        <ol className="space-y-1.5">
          {(d.steps ?? []).map((s) => (
            <li key={s.step} className="flex items-start gap-2 text-sm">
              <StatusDot status={s.ok === null ? "warn" : s.ok ? "ok" : "failed"} size={13} />
              <span className={cn("text-fg", s.ok === false && "text-bad-ink")}>
                {s.description || s.action}
                {s.verified && <span className="ml-1.5 text-xs text-ok-ink">conferido</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
