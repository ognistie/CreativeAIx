import { useCallback, useEffect, useMemo, useState } from "react";
import { AppDialog, AppMenu, Button, Chip, EmptyState, Field, GlassPanel, Spinner, StatusDot } from "../components/ui";
import { agentLabel } from "../lib/agents";
import { cn } from "../lib/cn";
import { core } from "../lib/host";
import { useCoreEvent } from "../lib/useCore";

// LabView.qml: AI Research Lab. Versoes das instrucoes de um agente, comparacao nos mesmos casos
// (simulado, ou real com confirmacao e teto de custo), resultado por caso com o rastro e promocao.

interface Version {
  id: string;
  n: number;
  note: string;
  instructions: string;
  params: { model?: string; effort?: string; max_tokens?: number };
  published: boolean;
}

interface Result {
  case: string;
  version: string;
  status: string;
  trace: Array<{ kind: string; action?: string; params?: Record<string, unknown>; reason?: string; checks?: Array<{ ok: boolean; check: string }> }>;
}

interface Run {
  id: string;
  versions: string[];
  summary: Record<string, { passed: number; cases: number; cost_usd: number; latency_ms_avg: number | null; origin: string }>;
  results: Result[];
}

type Reply = { ok?: boolean; error?: string } & Record<string, unknown>;

const AGENTS = ["FILE", "DATA", "WEB", "CODE", "DESKTOP", "EXTCODE", "MAESTRO"];
const STATUS: Record<string, string> = {
  passou: "Passou",
  falhou: "Falhou",
  falha_ferramenta: "Falha da ferramenta",
  falha_planejamento: "Falha no plano",
  indisponivel: "Indisponível",
  cancelado: "Cancelado",
};
const EFFORTS = [
  { v: "", l: "Igual" },
  { v: "low", l: "Baixo" },
  { v: "medium", l: "Médio" },
  { v: "high", l: "Alto" },
];
const money = (v: number) => `US$ ${(v || 0).toFixed(3).replace(".", ",")}`;
const BUDGET_MAX = 5;

export function LabView() {
  const [agent, setAgent] = useState("FILE");
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionA, setA] = useState("");
  const [versionB, setB] = useState("");
  const [sets, setSets] = useState<Array<{ name: string; cases?: unknown[] }>>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [mode, setMode] = useState<"simulado" | "real">("simulado");
  const [budget, setBudget] = useState("0,50");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<Array<Record<string, unknown>>>([]);
  const [message, setMessage] = useState("");
  const [promo, setPromo] = useState<{ ok: boolean; reasons?: string[] } | null>(null);
  const [creating, setCreating] = useState(false);
  const [instr, setInstr] = useState("");
  const [effort, setEffort] = useState("");
  const [ask, setAsk] = useState<"" | "real" | "promote">("");
  const [open, setOpen] = useState<Result | null>(null);
  const testable = agent === "FILE";
  const runCases = (sets[0]?.cases?.length ?? 0) * [versionA, versionB].filter((v, i, a) => v && a.indexOf(v) === i).length;

  const call = useCallback(async (p: Promise<unknown>): Promise<Reply> => {
    try {
      const r = (await p) as Reply;
      if (r.ok === false) setMessage(r.error || "Não deu certo.");
      return r;
    } catch (e) {
      setMessage((e as Error).message);
      return { ok: false };
    }
  }, []);

  const label = (id: string) => {
    const v = versions.find((x) => x.id === id);
    return v ? `v${v.n}` : id;
  };

  const loadVersions = useCallback(async () => {
    const r = await call(core().call("labVersions", agent));
    if (!r.ok) return;
    const vs = (r.versions as Version[]) ?? [];
    setVersions(vs);
    const pub = vs.find((v) => v.published);
    const a = pub ? pub.id : (vs[0]?.id ?? "");
    setA(a);
    setB((b) => (vs.some((v) => v.id === b) && b !== a ? b : (vs.filter((v) => v.id !== a).at(-1)?.id ?? "")));
    setPromo(null);
  }, [agent, call]);

  useEffect(() => {
    void loadVersions();
    setCreating(false);
  }, [loadVersions]);

  useEffect(() => {
    void (async () => {
      const s = await call(core().call("labEvalSets"));
      if (s.ok) setSets((s.sets as Array<{ name: string; cases?: unknown[] }>) ?? []);
      const r = await call(core().call("labRuns"));
      const runs = (r.runs as Array<{ id: string }>) ?? [];
      if (r.ok && runs.length) {
        const d = await call(core().call("labRunDetail", runs[0]!.id));
        if (d.ok) setRun(d.run as Run);
      }
      if (r.busy) setBusy(true);
    })();
  }, [call]);

  const checkPromo = useCallback(async () => {
    if (!versionB) return;
    const r = await call(core().call("labPromotionCheck", versionB));
    if (r.ok !== undefined) setPromo(r as { ok: boolean; reasons?: string[] });
  }, [versionB, call]);

  useCoreEvent("labProgress", useCallback((p: unknown) => setProgress((x) => [...x, p as Record<string, unknown>]), []));
  useCoreEvent(
    "labFinished",
    useCallback(
      (p: unknown) => {
        const r = p as { ok: boolean; run?: Run; error?: string };
        setBusy(false);
        if (!r.ok) return setMessage(r.error || "O experimento falhou.");
        setRun(r.run ?? null);
        void checkPromo();
      },
      [checkPromo],
    ),
  );

  const start = async (confirmed: boolean) => {
    const vs = [versionA, versionB].filter((v, i, a) => v && a.indexOf(v) === i);
    const r = await call(
      core().call("labRun", JSON.stringify({ set: sets[0]?.name ?? "", versions: vs, mode, confirmed, budget: parseFloat(budget.replace(",", ".")) || 0 })),
    );
    if (r.ok) {
      setBusy(true);
      setProgress([]);
      setMessage("");
      setOpen(null);
      setPromo(null);
    }
  };

  const createVersion = async () => {
    const r = await call(core().call("labCreateVariant", JSON.stringify({ agent, base: versionA, instructions: instr, params: effort ? { effort } : {}, note: "" })));
    if (!r.ok) return;
    setCreating(false);
    setInstr("");
    await loadVersions();
    setB((r.version as Version).id);
  };

  const cases = useMemo(() => {
    if (!run) return [];
    return [...new Set(run.results.map((r) => r.case))];
  }, [run]);

  return (
    <div className="h-full overflow-y-auto px-8">
      <div className="mx-auto max-w-6xl py-12">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-[28px] font-medium tracking-[-0.03em] text-fg">AI Research Lab</h1>
            <p className="mt-1.5 max-w-xl text-md text-fg-muted">
              Mude as instruções de um agente numa versão separada, compare com a atual nos mesmos casos e só publique se melhorar.
            </p>
          </div>
          <AppMenu
            trigger={<Button icon="chevron-down">Agente: {agentLabel(agent)}</Button>}
            items={AGENTS.map((a) => ({ label: agentLabel(a), onSelect: () => setAgent(a) }))}
          />
        </header>
        {message && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad">{message}</p>}

        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          {/* 1. Versoes */}
          <GlassPanel className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-md font-medium text-fg">1 · Versões</h2>
              {!creating && (
                <Button size="compact" icon="plus" onClick={() => setCreating(true)}>
                  Nova versão
                </Button>
              )}
            </div>
            {creating && (
              <div className="mb-4 rounded-r3 border border-hairline bg-surface p-3">
                <textarea
                  value={instr}
                  onChange={(e) => setInstr(e.target.value)}
                  rows={4}
                  placeholder="Instruções desta versão (ex.: confira o destino antes de copiar)"
                  aria-label="Instruções da versão"
                  className="w-full select-text resize-y bg-transparent text-[13px] text-fg outline-none placeholder:text-fg-subtle"
                />
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-fg-subtle">Esforço</span>
                  {EFFORTS.map((e) => (
                    <Chip key={e.v} selected={effort === e.v} onClick={() => setEffort(e.v)}>
                      {e.l}
                    </Chip>
                  ))}
                </div>
                <div className="mt-3 flex justify-end gap-2">
                  <Button size="compact" variant="ghost" onClick={() => setCreating(false)}>
                    Cancelar
                  </Button>
                  <Button size="compact" variant="primary" disabled={!instr.trim()} onClick={() => void createVersion()}>
                    Criar versão
                  </Button>
                </div>
              </div>
            )}
            <ul className="space-y-1.5">
              {versions.map((v) => {
                const isB = v.id === versionB;
                return (
                  <li key={v.id}>
                    <button
                      type="button"
                      onClick={() => !v.published && (setB(v.id), setPromo(null))}
                      className={cn("w-full rounded-r2 border px-3 py-2 text-left", isB ? "border-accent/50 bg-accent/10" : "border-hairline hover:bg-hover")}
                    >
                      <span className="flex items-center gap-2 text-sm">
                        <span className="font-medium text-fg">v{v.n}</span>
                        {v.published && <span className="text-xs text-ok">publicada · A</span>}
                        {isB && <span className="text-xs text-accent">comparando · B</span>}
                        {v.params.effort && <span className="ml-auto text-xs text-fg-subtle">esforço {v.params.effort}</span>}
                      </span>
                      <span className="mt-0.5 line-clamp-2 block text-xs text-fg-muted">{v.note || v.instructions || "Sem instruções extras"}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </GlassPanel>

          <div className="space-y-5">
            {/* 2. Comparar */}
            <GlassPanel className="p-5">
              <h2 className="mb-3 text-md font-medium text-fg">2 · Comparar</h2>
              {!testable ? (
                <p className="text-sm text-fg-muted">
                  Para {agentLabel(agent)} dá para criar e publicar versões, mas ainda não há casos que confiram o resultado no disco. Hoje a comparação roda só com o
                  agente de Arquivos.
                </p>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-fg">
                    {label(versionA)} × {versionB ? label(versionB) : "—"}
                  </span>
                  <span className="text-sm text-fg-subtle">em {sets[0]?.name ?? "—"}</span>
                  <span className="mx-2 h-5 w-px bg-hairline" />
                  <Chip selected={mode === "simulado"} onClick={() => setMode("simulado")}>
                    Simulado
                  </Chip>
                  <Chip selected={mode === "real"} onClick={() => setMode("real")}>
                    Real (custa)
                  </Chip>
                  {mode === "real" && (
                    <label className="flex items-center gap-1.5 text-sm text-fg-muted">
                      até US$
                      <Field value={budget} onChange={(e) => setBudget(e.target.value)} className="h-8 w-20 text-sm" aria-label="Orçamento em dólares" />
                    </label>
                  )}
                  <span className="flex-1" />
                  {busy ? (
                    <>
                      <Spinner />
                      <span className="text-sm text-fg-muted">{progress.length} casos</span>
                      <Button size="compact" onClick={() => void core().call("labCancel")}>
                        Parar
                      </Button>
                    </>
                  ) : (
                    <Button size="compact" variant="primary" icon="play" disabled={!versionA} onClick={() => (mode === "real" ? setAsk("real") : void start(false))}>
                      Rodar
                    </Button>
                  )}
                </div>
              )}
            </GlassPanel>

            {/* 3. Resultado */}
            <GlassPanel className="p-5">
              <h2 className="mb-3 text-md font-medium text-fg">3 · Resultado</h2>
              {!run ? (
                <EmptyState icon="sparkle" title="Ainda sem comparação">
                  Crie uma versão, escolha-a à esquerda e clique em Rodar.
                </EmptyState>
              ) : (
                <>
                  <div className="mb-4 grid gap-3 sm:grid-cols-2">
                    {run.versions.map((v) => {
                      const s = run.summary[v];
                      if (!s) return null;
                      return (
                        <div key={v} className="rounded-r3 border border-hairline p-3">
                          <p className="text-sm font-medium text-fg">
                            {label(v)} · {s.passed} de {s.cases} passaram
                          </p>
                          <p className="mt-0.5 text-xs text-fg-muted">
                            {money(s.cost_usd)} · {s.latency_ms_avg !== null ? `${(s.latency_ms_avg / 1000).toFixed(1).replace(".", ",")} s por caso` : "—"} ·{" "}
                            {s.origin === "real" ? "medido com o modelo" : "simulado"}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                  <ul className="overflow-hidden rounded-r3 border border-hairline">
                    {cases.map((c) => {
                      const rows = run.versions.map((v) => run.results.find((r) => r.case === c && r.version === v)).filter(Boolean) as Result[];
                      return (
                        <li key={c} className="border-b border-hairline last:border-0">
                          <button type="button" onClick={() => setOpen(rows.at(-1) ?? null)} className="flex w-full flex-wrap items-center gap-3 px-3 py-2 text-left hover:bg-row-hover">
                            <span className="min-w-0 flex-1 text-sm text-fg">{c}</span>
                            {rows.map((r) => (
                              <span key={r.version} className="flex items-center gap-1.5 text-xs text-fg-muted">
                                <StatusDot status={r.status === "passou" ? "ok" : r.status === "cancelado" || r.status === "indisponivel" ? "cancelled" : "failed"} size={13} />
                                {label(r.version)} · {STATUS[r.status] ?? r.status}
                              </span>
                            ))}
                          </button>
                          {open && open.case === c && (
                            <ul className="space-y-1 border-t border-hairline bg-surface/50 px-4 py-2 font-mono text-[12px]">
                              {open.trace
                                .filter((t) => t.kind !== "planejado")
                                .map((t, i) => (
                                  <li key={i} className={cn(t.kind === "bloqueado" || t.kind === "falha_ferramenta" ? "text-warn" : "text-fg-muted")}>
                                    {t.kind === "verificado"
                                      ? (t.checks ?? []).map((k) => `${k.ok ? "✓" : "✗"} ${k.check}`).join("    ")
                                      : `${t.kind === "bloqueado" ? "bloqueado pelo executor: " : t.kind === "falha_ferramenta" ? "falhou: " : ""}${t.action ?? ""} ${Object.entries(t.params ?? {})
                                          .map(([k, v]) => `${k}=${String(v)}`)
                                          .join(", ")}${t.reason ? ` (${t.reason})` : ""}`}
                                  </li>
                                ))}
                            </ul>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                  {versionB && (
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      <Button size="compact" variant="primary" disabled={!promo?.ok} onClick={() => setAsk("promote")}>
                        Promover {label(versionB)}
                      </Button>
                      {!promo ? (
                        <Button size="compact" variant="ghost" onClick={() => void checkPromo()}>
                          Conferir se pode promover
                        </Button>
                      ) : (
                        <span className={cn("text-sm", promo.ok ? "text-ok" : "text-fg-subtle")}>
                          {promo.ok ? "Pode promover: não piorou em nenhum caso no teste real." : `Para promover: ${(promo.reasons ?? []).join("; ")}.`}
                        </span>
                      )}
                    </div>
                  )}
                </>
              )}
            </GlassPanel>
          </div>
        </div>
      </div>

      <AppDialog
        open={ask === "real"}
        onOpenChange={(o) => !o && setAsk("")}
        title="Rodar com o modelo de verdade?"
        description={`${runCases} casos, até ${2 * runCases} chamadas ao modelo. Para quando o orçamento de US$ ${budget} acabar (teto US$ ${BUDGET_MAX},00). As ações rodam numa pasta temporária e passam pelas regras de sempre.`}
        actions={
          <>
            <Button variant="ghost" onClick={() => setAsk("")}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                setAsk("");
                void start(true);
              }}
            >
              Rodar
            </Button>
          </>
        }
      />
      <AppDialog
        open={ask === "promote"}
        onOpenChange={(o) => !o && setAsk("")}
        title="Promover esta versão?"
        description={`As instruções de ${label(versionB)} passam a valer no Harness. A configuração anterior fica nas versões do Harness.`}
        actions={
          <>
            <Button variant="ghost" onClick={() => setAsk("")}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                setAsk("");
                const r = await call(core().call("labPromote", versionB));
                if (r.ok) void loadVersions();
              }}
            >
              Promover
            </Button>
          </>
        }
      />
    </div>
  );
}
