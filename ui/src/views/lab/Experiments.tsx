import { useCallback, useEffect, useRef, useState } from "react";
import { AppDialog, Button, EmptyState, Field, GlassPanel, Spinner } from "../../components/ui";
import { core, saveLabDocument } from "../../lib/host";
import { LabCases, type EvalSet } from "./LabCases";
import { useCoreEvent } from "../../lib/useCore";

interface Version {
  id: string;
  n: number;
  note: string;
  instructions: string;
  params: { model?: string; effort?: string; max_tokens?: number };
  published: boolean;
  archived?: boolean;
  tested?: boolean;
}
interface Trace {
  kind: string;
  action?: string;
  params?: Record<string, unknown>;
  reason?: string;
  checks?: Array<{ ok: boolean; check: string }>;
}
interface Result {
  case: string;
  task?: string;
  trial?: number;
  feedback?: { note: string }[];
  version: string;
  status: string;
  trace: Trace[];
  reason?: string;
  source_run?: string;
  applied?: Record<string, unknown>;
}
interface RunRow {
  id: string;
  origin: "real" | "simulado" | "fixture";
  agent?: string;
  status: string;
  set: string;
  set_version: number;
  versions: string[];
}
interface Run extends RunRow {
  summary: Record<string, { passed: number; cases: number; valid?: number; cost_usd: number; cost_known?: boolean; calls?: number; latency_ms_avg: number | null;
    latency_ms_p50?: number | null; latency_ms_p95?: number | null; warnings?: string[] }>;
  results: Result[];
  dataset_snapshot?: EvalSet;
  stopped_by?: string;
  task_id?: string;
  events?: { seq: number; at: string; type: string; case?: string; version?: string; status?: string }[];
  protocol?: { hypothesis?: string };
  split?: string;
  context_mode?: string;
  repeats?: number;
  comparison?: { regressions: { case: string; trial: number }[]; improvements: { case: string; trial: number }[]; pairs: number; recommendation: string };
}

type Proposal = { agent: string; baseline: string; dataset_hash: string; origin: string; objective: string; instructions: string;
  hypothesis: string; measurement: string; risk: string; count: number };

const STATUS: Record<string, string> = {
  passou: "Passou", falhou: "Falhou", falha_ferramenta: "Falha da ferramenta",
  falha_planejamento: "Falha no plano", falha_execucao: "Falha na execução",
  indisponivel: "Indisponível", cancelado: "Cancelado", concluido: "Concluído",
  timeout: "Tempo esgotado", orcamento: "Limite atingido", running: "Em andamento", interrupted: "Interrompido",
};
const amount = (value: number) => `US$ ${value.toFixed(3).replace(".", ",")}`;
const origin = (run: RunRow) => run.origin === "real" ? "Inferência real" : run.origin === "fixture" ? "Fixture local" : "Replay";
const selectClass = "min-w-0 rounded-r2 border border-hairline bg-surface px-3 py-2 text-sm text-fg";
type Reply = { ok?: boolean; error?: string } & Record<string, unknown>;

export function Experiments({ agent, evidence, onEvidence, onExperiments }: { agent: string; evidence: boolean; onEvidence: () => void; onExperiments: () => void }) {
  const [versions, setVersions] = useState<Version[]>([]);
  const [candidate, setCandidate] = useState("");
  const [sets, setSets] = useState<EvalSet[]>([]);
  const [selectedSet, setSelectedSet] = useState("");
  const [historical, setHistorical] = useState<EvalSet | null>(null);
  const [casesOpen, setCasesOpen] = useState(false);
  const [history, setHistory] = useState<RunRow[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const selectionRequest = useRef(0);
  const [mode, setMode] = useState<RunRow["origin"]>(agent === "MAESTRO" ? "fixture" : "simulado");
  const [split, setSplit] = useState("all");
  const [repeats, setRepeats] = useState(1);
  const [deadline, setDeadline] = useState(180);
  const [calls, setCalls] = useState(40);
  const [tokens, setTokens] = useState(160000);
  const [context, setContext] = useState("fixture");
  const [budget, setBudget] = useState("0,50");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [promo, setPromo] = useState<{ ok: boolean; reasons?: string[]; warning?: string } | null>(null);
  const [rollback, setRollback] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [parent, setParent] = useState<Version | null>(null);
  const [variantNote, setVariantNote] = useState("");
  const [notice, setNotice] = useState("");
  const [includeHypothesis, setIncludeHypothesis] = useState(false);
  const [effort, setEffort] = useState("");
  const [model, setModel] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [diff, setDiff] = useState<string[] | null>(null);
  const [objective, setObjective] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [ask, setAsk] = useState<"" | "real" | "promote" | "rollback" | "research">("");
  const testable = ["FILE", "MAESTRO", "CODE", "DATA"].includes(agent);
  const base = versions.find((v) => v.published);
  const variant = versions.find((v) => v.id === candidate);
  const dataset = historical ?? sets.find((s) => s.name === selectedSet) ?? sets[0];
  const count = (dataset?.cases ?? []).filter((row) => split === "all" || (row.split ?? "development") === split).length;
  const limit = Number(budget.replace(",", "."));
  const validBudget = limit >= 0.01 && limit <= 5;
  const validLimits = deadline >= 15 && deadline <= 600 && calls >= 1 && calls <= 200 && tokens >= 512 && tokens <= 1000000;
  const available = Boolean(base && (mode === "fixture" || variant) && dataset && count && repeats >= 1 && repeats <= 5);

  const call = useCallback(async (promise: Promise<unknown>, showError = true): Promise<Reply> => {
    try {
      const response = (await promise) as Reply;
      if (response.ok === false && showError) setError(response.error || "A operação falhou.");
      return response;
    } catch (err) {
      setError((err as Error).message);
      return { ok: false };
    }
  }, []);

  const loadVersions = useCallback(async () => {
    const reply = await call(core().call("labVersions", agent));
    if (!reply.ok) return;
    const rows = (reply.versions as Version[]) ?? [];
    setVersions(rows);
    setRollback(Boolean(reply.rollback_available));
    setCandidate((id) => rows.some((v) => v.id === id && !v.published && !v.archived) ? id : rows.filter((v) => !v.published && !v.archived).at(-1)?.id ?? "");
    setPromo(null);
  }, [agent, call]);

  const loadRun = useCallback(async (id: string) => {
    const selection = ++selectionRequest.current;
    setIncludeHypothesis(false);
    const reply = await call(core().call("labRunDetail", id));
    if (reply.ok && selection === selectionRequest.current) setRun(reply.run as Run);
  }, [call]);

  const loadHistory = useCallback(async (chooseLatest = false) => {
    if (!testable) return;
    const reply = await call(core().call("labRuns"));
    if (!reply.ok) return;
    const running = Boolean(reply.busy);
    const rows = ((reply.runs as RunRow[]) ?? [])
      .filter((row) => row.agent === agent || (!row.agent && row.versions.some((id) => id.startsWith(`${agent.toLowerCase()}-`))));
    setHistory(rows);
    setBusy(running);
    if (chooseLatest && rows[0]) await loadRun(rows[0].id);
  }, [agent, call, loadRun, testable]);

  useEffect(() => { void loadVersions(); }, [loadVersions]);
  useEffect(() => {
    if (!testable) return;
    void call(core().call("labEvalSets")).then((reply) => {
      if (reply.ok) setSets(((reply.sets as EvalSet[]) ?? []).filter((set) => set.agent === agent));
    });
    void loadHistory(true);
  }, [agent, call, loadHistory, testable]);

  useCoreEvent("labProgress", useCallback((payload) => {
    if ((payload as { agent?: string }).agent === agent) setProgress((n) => n + 1);
  }, [agent]));
  useCoreEvent("labFinished", useCallback((payload: unknown) => {
    if (!testable) return;
    const reply = payload as { ok: boolean; run?: Run; proposal?: Proposal; error?: string };
    setBusy(false);
    setPromo(null);
    if (reply.proposal?.agent === agent) setProposal(reply.proposal);
    if (reply.ok && reply.run?.agent === agent) {
      ++selectionRequest.current;
      setRun(reply.run);
      void loadRun(reply.run.id);
    }
    if (!reply.ok) setError(reply.error || "O experimento falhou.");
    void loadHistory();
  }, [agent, loadHistory, loadRun, testable]));

  const create = async () => {
    if (!base || draft === null) return;
    setError("");
    const result = await call(core().call("labCreateVariant", JSON.stringify({
      agent, base: parent?.id ?? base.id, instructions: draft, note: variantNote.trim(),
      params: { ...(effort ? { effort } : {}), ...(model.trim() ? { model: model.trim() } : {}), ...(maxTokens ? { max_tokens: Number(maxTokens) } : {}) },
    })));
    if (!result.ok) return;
    await loadVersions();
    setCandidate((result.version as Version).id);
    setDraft(null);
  };

  const start = async (confirmed: boolean) => {
    if (!base || !dataset || busy || !available || (mode !== "fixture" && !variant)) return;
    setBusy(true);
    setProgress(0);
    setError("");
    const reply = await call(core().call("labRun", JSON.stringify({
      set: dataset.name, revision: dataset.hash, versions: mode === "fixture" ? [base.id] : [base.id, variant!.id],
      mode, confirmed, budget: limit, split, repeats, timeout: deadline, calls, tokens, context, objective, hypothesis: variant?.note,
    })));
    if (!reply.ok) setBusy(false);
    else onEvidence();
  };

  const chooseDataset = (row: EvalSet) => {
    const latest = sets.find((set) => set.name === row.name);
    setHistorical(latest && latest.version > row.version ? row : null);
    if (!latest || latest.version <= row.version) {
      setSets((items) => [...items.filter((item) => item.name !== row.name), row]);
    }
    setSelectedSet(row.name);
    setProposal(null);
  };

  const suggest = async (paid: boolean) => {
    if (!dataset || !objective.trim() || busy) return;
    setError("");
    setBusy(true);
    setProposal(null);
    const reply = await call(core().call("labResearch", JSON.stringify({
      agent, objective, set: dataset.name, revision: dataset.hash, mode: paid ? "real" : "fixture", confirmed: paid, budget: limit,
    })));
    if (!reply.ok) setBusy(false);
  };

  const exportReport = async (format: "md" | "json") => {
    if (!run) return;
    setError("");
    try {
      const reply = await call(core().call("labReport", run.id, format, includeHypothesis ? run.protocol?.hypothesis ?? "" : ""));
      if (reply.ok && typeof reply.content === "string" && await saveLabDocument(`lab-relatorio-${run.id}.${format}`, reply.content)) setNotice("Relatório salvo.");
    } catch (reason) { setError((reason as Error).message); }
  };

  const chooseHistorical = (row: EvalSet) => {
    setHistorical({ ...row, name: row.name ?? run!.set, version: row.version ?? run!.set_version });
    setSelectedSet(row.name ?? run!.set);
    setContext(run?.context_mode ?? "fixture");
    setMode("simulado");
    setCasesOpen(false);
    onExperiments();
  };

  return (
    <div className="space-y-4">
      {notice && <p role="status" className="text-sm text-fg">{notice}</p>}
      {error && <p role="alert" className="rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}
      {busy && (
        <div className="flex flex-wrap items-center gap-3 rounded-r3 border border-hairline p-3" role="status">
          <Spinner /><span className="text-sm text-fg">Experimento em andamento · {progress} casos concluídos nesta sessão</span>
          <Button size="compact" onClick={() => void core().call("labCancel").catch((err: Error) => setError(err.message))}>Parar após o caso atual</Button>
        </div>
      )}
      {evidence ? (
        !testable ? <EmptyState icon="flask" title="Avaliação ainda não disponível" /> :
        <GlassPanel className="space-y-4 p-5">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-md font-semibold text-fg">Histórico de comparações</h3>
            {history.length > 0 && <select aria-label="Comparação no histórico" value={run?.id ?? ""} className={selectClass}
              onChange={(e) => {
                const entry = history.find((row) => row.id === e.target.value);
                if (entry) void loadRun(entry.id);
              }}>
              {!run && <option value="" disabled>Escolher comparação</option>}
              {history.map((row) => <option key={row.id} value={row.id}>
                {row.id} · {origin(row)} · {STATUS[row.status] ?? row.status}
              </option>)}
            </select>}
          </header>
          {!run ? <EmptyState icon="flask" title="Ainda sem evidências">Execute uma comparação em Experimentos.</EmptyState> : <RunEvidence key={run.id} run={run} onFeedback={async (row, note) => {
            const reply = await call(core().call("labFeedback", JSON.stringify({ run: run.id, version: row.version, case: row.case, trial: row.trial ?? 1, note })));
            if (reply.ok) await loadRun(run.id);
            return Boolean(reply.ok);
          }} />}
          {run && <div className="flex flex-wrap items-center gap-2">
            {run.protocol?.hypothesis && <label className="flex items-center gap-2 text-xs text-fg-muted"><input type="checkbox" checked={includeHypothesis}
              onChange={(e) => setIncludeHypothesis(e.target.checked)} /> Incluir a hipótese no relatório</label>}
            <Button size="compact" onClick={() => void exportReport("md")}>Exportar relatório Markdown</Button>
            <Button size="compact" onClick={() => void exportReport("json")}>Exportar relatório JSON</Button>
            {run.dataset_snapshot && <Button size="compact" onClick={() => chooseHistorical(run.dataset_snapshot!)}>Selecionar esta revisão para novo teste</Button>}
          </div>}
          {variant && run?.origin === "real" && run.versions.includes(variant.id) && (
            <div className="flex flex-wrap items-center gap-3 border-t border-hairline pt-3">
              <Button size="compact" onClick={async () => {
                const result = await call(core().call("labPromotionCheck", variant.id), false);
                setPromo({ ok: !!result.ok, reasons: (result.reasons as string[]) ?? [result.error || "Evidência insuficiente."], warning: String(result.warning ?? "") });
              }}>Conferir promoção de {variant.id}</Button>
              {promo?.warning && <p className="text-sm text-warn-ink">{promo.warning}</p>}
              {promo && (promo.ok
                ? <Button size="compact" variant="primary" onClick={() => setAsk("promote")}>Promover instruções</Button>
                : <p className="text-sm text-fg-muted">{promo.reasons?.join(". ")}</p>)}
            </div>
          )}
        </GlassPanel>
      ) : (
        casesOpen ? <LabCases key={dataset?.hash ?? agent} agent={agent} selection={sets.find((s) => s.name === dataset?.name)}
          onChange={chooseDataset} onClose={() => setCasesOpen(false)} /> :
        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <GlassPanel className="space-y-4 p-5">
            <header className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-md font-semibold text-fg">Versões</h3>
              <Button size="compact" icon="plus" disabled={!base || draft !== null} onClick={() => {
                setParent(base!);
                setDraft(base!.instructions);
                setEffort(""); setModel(""); setMaxTokens("");
                setVariantNote("");
              }}>Criar variante</Button>
            </header>
            {base && <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-fg-muted">Referência ativa <strong className="text-fg">{base.id}</strong></p>
              {rollback && <Button size="compact" onClick={() => setAsk("rollback")}>Restaurar versão anterior</Button>}
            </div>}
            {draft !== null && (
              <div className="grid gap-3 rounded-r3 border border-hairline bg-surface p-3">
                <p className="text-xs text-fg-muted">Rascunho a partir de {parent?.id ?? base?.id}</p>
                <Field aria-label="Hipótese da variante" placeholder="Hipótese da variante" value={variantNote} maxLength={200} onChange={(e) => setVariantNote(e.target.value)} />
                <textarea className="w-full resize-y rounded-r2 border border-hairline bg-surface p-3 text-sm text-fg" rows={5}
                  aria-label="Instruções da variante" maxLength={700} value={draft} onChange={(e) => setDraft(e.target.value)} />
                {testable && <label className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">Esforço no teste
                  <select className={selectClass} value={effort} onChange={(e) => setEffort(e.target.value)}>
                    <option value="">Herdar</option><option value="low">Baixo</option><option value="medium">Médio</option><option value="high">Alto</option>
                  </select>
                </label>}
                {testable && <div className="grid gap-2 sm:grid-cols-2">
                  <Field aria-label="Modelo da variante" value={model} placeholder={(parent ?? base)?.params.model} onChange={(e) => setModel(e.target.value)} />
                  <Field aria-label="Tokens máximos da variante" type="number" min={256} max={32000} value={maxTokens} placeholder={String((parent ?? base)?.params.max_tokens ?? "")} onChange={(e) => setMaxTokens(e.target.value)} />
                </div>}
                <div className="flex justify-end gap-2">
                  <Button size="compact" onClick={() => setDraft(null)}>Cancelar</Button>
                  <Button size="compact" variant="primary" disabled={draft === (parent ?? base)?.instructions && !effort && !model && !maxTokens} onClick={() => void create()}>Salvar variante</Button>
                </div>
              </div>
            )}
            <label className="grid gap-1 text-sm text-fg-muted">Variante para comparar
              <select className={selectClass} value={candidate} onChange={(e) => { setCandidate(e.target.value); setPromo(null); setDiff(null); }}>
                <option value="">Escolher variante</option>
                {versions.filter((v) => !v.published && !v.archived).map((v) => <option key={v.id} value={v.id}>{v.id} · {v.tested ? "Testada" : "Pronta para teste"}{v.note ? ` · ${v.note}` : ""}</option>)}
              </select>
            </label>
            {variant && <details className="text-sm text-fg-muted">
              <summary className="cursor-pointer text-fg">Ver instruções e parâmetros da variante</summary>
              <p className="my-2 whitespace-pre-wrap break-words">{variant.instructions || "Sem instruções adicionais"}</p>
              <p>{variant.params.model} · esforço {variant.params.effort} · até {variant.params.max_tokens} tokens por chamada de planejamento</p>
            </details>}
            {base && variant && <div className="flex flex-wrap gap-2"><Button size="compact" onClick={async () => {
              const result = await call(core().call("labDiff", base.id, variant.id));
              if (result.ok) setDiff((result.lines as string[]) ?? []);
            }}>Ver diferenças</Button>
              <Button size="compact" disabled={draft !== null} onClick={() => {
                setParent(variant); setDraft(variant.instructions); setVariantNote(""); setEffort(""); setModel(""); setMaxTokens("");
              }}>Duplicar como rascunho</Button>
              <Button size="compact" disabled={busy} onClick={async () => {
                if ((await call(core().call("labArchive", variant.id, true))).ok) { setDiff(null); await loadVersions(); }
              }}>Arquivar variante</Button>
            </div>}
            {versions.some((v) => v.archived) && <details className="rounded-r2 border border-hairline p-3">
              <summary className="cursor-pointer text-sm text-fg">Variantes arquivadas</summary>
              <ul className="mt-2 space-y-2">{versions.filter((v) => v.archived).map((row) => <li key={row.id} className="flex items-center justify-between gap-2 text-sm text-fg-muted">
                {row.id}<Button size="compact" disabled={busy} onClick={async () => {
                  if ((await call(core().call("labArchive", row.id, false))).ok) await loadVersions();
                }}>Reativar</Button>
              </li>)}</ul>
            </details>}
            {diff && <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-r2 bg-surface p-3 text-xs text-fg">{diff.join("\n") || "Sem diferenças"}</pre>}
          </GlassPanel>
          <GlassPanel className="space-y-4 p-5">
            <header className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-md font-semibold text-fg">Comparar versões</h3>
              {testable && <Button size="compact" onClick={() => setCasesOpen(true)}>Casos de teste</Button>}
            </header>
            {testable ? <>
              <label className="grid gap-1 text-sm text-fg-muted">Conjunto de casos
                <select className={selectClass} value={historical ? "historical" : (dataset?.name ?? "")} onChange={(e) => {
                  if (e.target.value !== "historical") { setHistorical(null); setSelectedSet(e.target.value); setProposal(null); setContext("fixture"); }
                }}>
                  {historical && <option value="historical">{historical.name} · revisão {historical.version} do histórico</option>}
                  {!sets.length && <option value="">Nenhum conjunto disponível</option>}
                  {sets.map((s) => <option key={s.name} value={s.name}>{s.title || s.name} · v{s.version} · {s.cases.length} casos</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-sm text-fg-muted">Modo de execução
                <select className={selectClass} value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
                  {agent === "MAESTRO" && <option value="fixture">Roteamento local · sem execução</option>}
                  <option value="simulado">Replay de planos gravados · sem custo</option>
                  <option value="real">Inferência real · usa o provedor</option>
                </select>
              </label>
              <p className="text-sm text-fg-muted">{mode === "simulado"
                ? "O replay reaplica planos gravados nas mesmas versões e na mesma revisão de casos."
                : mode === "fixture" ? "Verifica os atalhos reais do Maestro no cenário local, sem executar subtarefas."
                : "Cada chamada reserva orçamento com base na estimativa de entrada e no limite de saída. Use apenas dados sintéticos que podem ser enviados ao provedor."}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1 text-sm text-fg-muted">Grupo de casos
                  <select className={selectClass} value={split} onChange={(e) => setSplit(e.target.value)}>
                    <option value="all">Todos</option><option value="development">Desenvolvimento</option><option value="holdout">Validação reservada</option>
                  </select>
                </label>
                <label className="grid gap-1 text-sm text-fg-muted">Repetições por caso
                  <Field type="number" min={1} max={5} value={repeats} onChange={(e) => setRepeats(Number(e.target.value))} />
                </label>
              </div>
              {mode === "real" && <>
                <label className="flex items-center gap-2 text-sm text-fg-muted">Limite de custo estimado em US$
                  <Field value={budget} onChange={(e) => setBudget(e.target.value)} className="w-24" />
                </label>
                <details className="rounded-r2 border border-hairline p-3">
                  <summary className="cursor-pointer text-sm text-fg">Tempo, chamadas e contexto</summary>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    <label className="grid gap-1 text-sm text-fg-muted">Tempo máximo (segundos)
                      <Field type="number" value={deadline} min={15} max={600} onChange={(e) => setDeadline(Number(e.target.value))} />
                    </label>
                    <label className="grid gap-1 text-sm text-fg-muted">Chamadas máximas
                      <Field type="number" value={calls} min={1} max={200} onChange={(e) => setCalls(Number(e.target.value))} />
                    </label>
                    <label className="grid gap-1 text-sm text-fg-muted">Tokens totais
                      <Field type="number" value={tokens} min={512} max={1000000} onChange={(e) => setTokens(Number(e.target.value))} />
                    </label>
                    <label className="grid gap-1 text-sm text-fg-muted">Contexto dos casos
                      <select className={selectClass} value={context} onChange={(e) => setContext(e.target.value)}>
                        <option value="fixture">Referências sintéticas da fixture</option><option value="none">Sem referências extras</option>
                      </select>
                    </label>
                  </div>
                </details>
              </>}
              <Button variant="primary" icon="play" disabled={busy || !available || (mode === "real" && (!validBudget || !validLimits))}
                onClick={() => mode === "real" ? setAsk("real") : void start(false)}>{mode === "fixture" ? "Verificar roteamento" : "Rodar comparação"}</Button>
              <details className="rounded-r2 border border-hairline p-3">
                <summary className="cursor-pointer text-sm font-medium text-fg">Pesquisa assistida</summary>
                <div className="mt-3 space-y-2">
                  <label className="grid gap-1 text-sm text-fg-muted">Objetivo
                    <Field value={objective} maxLength={400} onChange={(e) => { setObjective(e.target.value); setProposal(null); }} />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button size="compact" disabled={busy || !dataset || !objective.trim()} onClick={() => void suggest(false)}>Propor hipótese local</Button>
                    <Button size="compact" disabled={busy || !dataset || !objective.trim()} onClick={() => setAsk("research")}>Propor com o provedor</Button>
                  </div>
                  {proposal && <article className="space-y-2 rounded-r2 bg-surface p-3 text-sm text-fg-muted">
                    <p className="font-medium text-fg">Hipótese · {proposal.origin}</p>
                    <p>{proposal.hypothesis}</p><p>{proposal.measurement} · {proposal.count} casos.</p><p>{proposal.risk}</p>
                    <p className="whitespace-pre-wrap">{proposal.instructions}</p>
                    <Button size="compact" variant="primary" disabled={draft !== null || proposal.baseline !== base?.id || proposal.dataset_hash !== dataset?.hash}
                      onClick={() => {
                        setParent(base ?? null);
                        setDraft(proposal.instructions); setVariantNote(proposal.hypothesis); setEffort(""); setModel(""); setMaxTokens("");
                        setSplit("development"); setMode("real");
                      }}>Revisar como variante</Button>
                  </article>}
                </div>
              </details>
            </> : <p className="text-sm text-fg-muted">Avaliação ainda não disponível para este agente. Você pode editar e salvar variantes para revisão.</p>}
          </GlassPanel>
        </div>
      )}
      <AppDialog open={ask === "real"} onOpenChange={(open) => !open && setAsk("")}
        title="Rodar com o provedor?"
        description={`Até ${count * repeats} avaliações por versão, ${calls} chamadas no total e teto estimado de ${validBudget ? amount(limit) : "US$ —"}. Pedidos sintéticos e instruções das versões serão enviados ao provedor. A cobrança pode divergir da estimativa.`}
        actions={<><Button onClick={() => setAsk("")}>Cancelar</Button>
          <Button variant="primary" disabled={!validBudget} onClick={() => { setAsk(""); void start(true); }}>Rodar</Button></>} />
      <AppDialog open={ask === "promote"} onOpenChange={(open) => !open && setAsk("")}
        title="Promover instruções da variante?"
        description={`As instruções desta versão vão alterar o Harness ativo. A versão anterior ficará disponível para restauração no Lab. ${promo?.warning ?? ""}`}
        actions={<><Button onClick={() => setAsk("")}>Cancelar</Button>
          <Button variant="primary" onClick={async () => {
            setAsk("");
            if (!variant) return;
            const result = await call(core().call("labPromote", variant.id));
            if (result.ok) { setNotice("Instruções publicadas no Harness ativo."); void loadVersions(); }
          }}>Promover</Button></>} />
      <AppDialog open={ask === "rollback"} onOpenChange={(open) => !open && setAsk("")}
        title="Restaurar a versão anterior?"
        description="As instruções anteriores voltam ao Harness ativo. O histórico de variantes e evidências continua disponível."
        actions={<><Button onClick={() => setAsk("")}>Cancelar</Button>
          <Button variant="primary" onClick={async () => {
            setAsk("");
            if (base && (await call(core().call("labRollback", agent, base.id, true))).ok) {
              setNotice("A versão anterior voltou a ficar ativa.");
              await loadVersions();
            }
          }}>Restaurar</Button></>} />
      <AppDialog open={ask === "research"} onOpenChange={(open) => !open && setAsk("")}
        title="Usar o provedor para a hipótese?"
        description="Uma chamada recebe o objetivo, as instruções da versão ativa e uma contagem de resultados de desenvolvimento. A comparação exige uma confirmação separada."
        actions={<><Button onClick={() => setAsk("")}>Cancelar</Button>
          <label className="flex items-center gap-2 text-xs text-fg-muted">Limite em US$ <Field className="w-24" value={budget} onChange={(e) => setBudget(e.target.value)} /></label>
          <Button variant="primary" disabled={!validBudget} onClick={() => { setAsk(""); void suggest(true); }}>Propor hipótese</Button></>} />
    </div>
  );
}

function RunEvidence({ run, onFeedback }: { run: Run; onFeedback: (row: Result, note: string) => Promise<boolean> }) {
  const [feedback, setFeedback] = useState("");
  const [writing, setWriting] = useState<string | null>(null);
  const cases = [...new Map(run.results.map((row) => [`${row.case}#${row.trial ?? 1}`, row])).entries()];
  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-muted">
        {origin(run)} · {run.set} v{run.set_version} · {STATUS[run.status] ?? run.status}
        {run.dataset_snapshot ? ` · conjunto ${run.dataset_snapshot.hash.slice(0, 12)}` : " · registro anterior aos snapshots"}
      </p>
      {run.task_id && <details className="rounded-r2 border border-hairline p-3 text-xs text-fg-muted">
        <summary className="cursor-pointer">Eventos da execução · {run.task_id}</summary>
        {run.events ? <ol className="mt-2 max-h-52 space-y-1 overflow-y-auto">{run.events.map((event) => <li key={event.seq}>
          {event.at.slice(11)} · {event.case ? `${event.case} · ${event.version} · ${STATUS[event.status ?? ""] ?? event.status}` : event.type === "created" ? "Início" : "Encerramento"}
        </li>)}</ol> : <p className="mt-2">Selecione a rodada no histórico para carregar os eventos.</p>}
      </details>}
      {run.stopped_by && <p className="text-sm text-warn-ink">{run.stopped_by}</p>}
      {run.comparison && run.versions.length === 2 && <p className="rounded-r2 border border-hairline p-2 text-sm text-fg">
        {run.comparison.pairs} pares válidos · {run.comparison.regressions.length} regressões · {run.comparison.improvements.length} melhorias · Próximo passo {run.comparison.recommendation}
      </p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {run.versions.map((id) => {
          const stats = run.summary?.[id];
          if (!stats) return null;
          return (
            <div key={id} className="rounded-r2 border border-hairline p-3">
              <p className="font-medium text-fg">{id}</p>
              <p className="mt-1 text-sm text-fg-muted">{stats.passed} de {stats.valid ?? stats.cases} casos válidos passaram</p>
              <p className="text-sm text-fg-muted">
                {stats.latency_ms_avg == null ? "Latência indisponível" : `${stats.latency_ms_avg} ms por caso, medidos localmente`}
              </p>
              <p className="text-sm text-fg-muted">
                {run.origin !== "real" ? "Sem chamadas ao provedor" : stats.calls ? `${stats.cost_known === true ? amount(stats.cost_usd) + " estimados" : "Custo desconhecido"} · ${stats.calls} chamadas` : "Custo indisponível"}
              </p>
              {stats.latency_ms_p50 != null && <p className="text-sm text-fg-muted">p50 {stats.latency_ms_p50} ms{stats.latency_ms_p95 != null ? ` · p95 ${stats.latency_ms_p95} ms` : ""}</p>}
              {stats.warnings?.length ? <p className="mt-1 text-xs text-warn-ink">{stats.warnings.join(" · ")}</p> : null}
            </div>
          );
        })}
      </div>
      {cases.map(([key, row]) => {
        const rows = run.versions.flatMap((v) => run.results.filter((r) => r.case === row.case && (r.trial ?? 1) === (row.trial ?? 1) && r.version === v));
        const regression = rows[0]?.status === "passou" && Boolean(rows[1]) && !["passou", "indisponivel", "cancelado", "falha_execucao", "timeout"].includes(rows[1]!.status);
        return <details className="rounded-r2 border border-hairline p-3" key={key}>
          <summary className="cursor-pointer text-sm font-medium text-fg">
            {row.case}{(run.repeats ?? 1) > 1 ? ` · rodada ${row.trial ?? 1}` : ""} · {rows.map((r) => STATUS[r.status] ?? r.status).join(" / ")}{regression ? " · Regressão" : ""}
          </summary>
          {row.task && <p className="mt-2 text-sm text-fg-muted">{row.task}</p>}
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {rows.map((r) => <div key={r.version} className="min-w-0 space-y-1 break-words text-sm text-fg-muted">
              <p className="font-medium text-fg">{r.version}</p>
              {r.reason && <p>{r.reason}</p>}
              {r.source_run && <p>Plano gravado em {r.source_run}</p>}
              {r.applied && <p>Planejamento aplicado · {Object.entries(r.applied).map(([key, val]) => `${key}: ${val ?? "padrão"}`).join(" · ")}</p>}
              <ul className="list-inside list-disc">
                {r.trace.flatMap((t, i) => t.kind === "verificado"
                  ? (t.checks ?? []).map((c, j) => <li key={`${i}-${j}`}>{c.ok ? "✓" : "✗"} {c.check}</li>)
                  : t.action ? [<li key={i}>{t.action} · {t.reason ?? t.kind}{t.params ? ` · ${Object.values(t.params).join(" → ")}` : ""}</li>] : [])}
              </ul>
              {r.feedback?.map((item, index) => <p key={index} className="rounded-r2 bg-hover p-2">{item.note}</p>)}
              {run.status !== "running" && (writing === `${key}:${r.version}`
                ? <form className="flex flex-wrap gap-2" onSubmit={async (event) => {
                    event.preventDefault();
                    if (feedback.trim() && await onFeedback(r, feedback)) { setFeedback(""); setWriting(null); }
                  }}>
                    <Field aria-label={`Observação de ${r.version}`} value={feedback} maxLength={500} onChange={(e) => setFeedback(e.target.value)} />
                    <Button type="submit" size="compact" disabled={!feedback.trim()}>Salvar observação</Button>
                  </form>
                : <Button size="compact" onClick={() => { setFeedback(""); setWriting(`${key}:${r.version}`); }}>Anotar</Button>)}
            </div>)}
          </div>
        </details>;
      })}
    </div>
  );
}
