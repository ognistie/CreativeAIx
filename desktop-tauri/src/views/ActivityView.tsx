import { useCallback, useEffect, useState } from "react";
import { Button, EmptyState, GlassPanel, Skeleton, StatusDot } from "../components/ui";
import { agentLabel } from "../lib/agents";
import { core } from "../lib/tauri";
import { fmtCost, fmtDuration, fmtTokens } from "../lib/taskStore";
import { useCoreEvent } from "../lib/useCore";
import { Page } from "./Page";

// ActivityView.qml: o que esta rodando, o que espera por voce, uso do mes e quando os agentes trabalham.
// Graficos com uma cor so (destaque): custo por agente vira barras rotuladas, nao fatias coloridas.

interface Summary {
  running: string;
  attention: Array<{ kind: string; text: string; task: string }>;
  today: Array<{ time: string; task: string; ok: boolean; duration_ms: number; agents: string[]; status: string }>;
  usage: {
    cost: number;
    calls: number;
    tokens: number;
    runs: number;
    success_rate: number;
    segments: Array<{ agent: string; cost: number; share: number }>;
    daily: Array<{ day: string; cost: number }>;
  };
  heatmap: { rows: number[][]; peak: number; weekdays: string[] };
}

const MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

export function ActivityView({ onAnswer }: { onAnswer?: () => void }) {
  const [s, setS] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    core()
      .call("activitySummary")
      .then((r) => {
        const v = r as Summary & { ok?: boolean; error?: string };
        if (v.ok === false) setError(v.error || "Não deu para ler a atividade.");
        else setS(v);
      })
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);
  useCoreEvent("historyChanged", load);
  useCoreEvent("runningChanged", load);

  return (
    <Page wide title="Atividade" subtitle="O que seus agentes estão fazendo, o que espera por você e quanto custou este mês.">
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad">{error}</p>}
      {!s ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40 rounded-r4" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Panel title="Rodando agora" dot={s.running ? "bg-ok" : undefined}>
            <p className="text-md text-fg">{s.running || <span className="text-fg-muted">Nada rodando. O agente espera o próximo pedido.</span>}</p>
          </Panel>
          <Panel title="Precisa de você" dot={s.attention.length ? "bg-warn" : undefined}>
            {s.attention.length === 0 ? (
              <p className="text-md text-fg-muted">Nenhuma pergunta pendente.</p>
            ) : (
              s.attention.map((a, i) => (
                <div key={i} className="flex items-start gap-2.5">
                  <StatusDot status="clarify" />
                  <div className="flex-1">
                    <p className="text-md text-fg">{a.text}</p>
                    {a.task && <p className="mt-0.5 text-xs text-fg-subtle">{a.task}</p>}
                  </div>
                  {onAnswer && (
                    <Button size="compact" variant="primary" onClick={onAnswer}>
                      Responder
                    </Button>
                  )}
                </div>
              ))
            )}
          </Panel>

          <Panel title={`Uso do mês · desde 1º de ${MONTHS[new Date().getMonth()]}`} className="md:col-span-2">
            <div className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-5">
              <Figure label="Custo" value={fmtCost(s.usage.cost)} />
              <Figure label="Tarefas" value={String(s.usage.runs)} />
              <Figure label="% ok" value={`${s.usage.success_rate}%`} />
              <Figure label="Chamadas" value={String(s.usage.calls)} />
              <Figure label="Tokens" value={fmtTokens(s.usage.tokens)} />
            </div>
            <div className="grid gap-6 md:grid-cols-[3fr_2fr]">
              <DailyBars daily={s.usage.daily} />
              <AgentBars segments={s.usage.segments} />
            </div>
            <p className="mt-4 text-xs text-fg-subtle">
              Tarefas: pedidos executados no mês (simulações não contam). % ok: concluídos sem erro. Custo estimado pelo uso de tokens.
            </p>
          </Panel>

          <Panel title="Quando seus agentes trabalham · 30 dias" className="md:col-span-2">
            <Heatmap h={s.heatmap} />
          </Panel>

          <Panel title="Hoje" className="md:col-span-2">
            {s.today.length === 0 ? (
              <EmptyState icon="clock" title="Nenhuma tarefa hoje">
                Peça algo na Conversa: cada tarefa aparece aqui com hora, resultado e duração.
              </EmptyState>
            ) : (
              <ul className="-mx-2">
                {s.today.map((t, i) => (
                  <li key={i} className="flex items-center gap-3 rounded-r2 px-2 py-2 hover:bg-row-hover">
                    <span className="w-11 text-xs tabular-nums text-fg-subtle">{t.time}</span>
                    <StatusDot status={t.ok ? "ok" : "failed"} size={14} />
                    <span className="min-w-0 flex-1 truncate text-md text-fg">{t.task}</span>
                    <span className="hidden text-xs text-fg-subtle sm:inline">{t.agents.map(agentLabel).join(", ")}</span>
                    <span className="w-14 text-right text-xs tabular-nums text-fg-muted">{fmtDuration(t.duration_ms)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}
    </Page>
  );
}

function Panel({ title, dot, className, children }: { title: string; dot?: string; className?: string; children: React.ReactNode }) {
  return (
    <GlassPanel className={`animate-enter p-5 ${className ?? ""}`}>
      <h2 className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
        {dot && <span className={`size-2 rounded-full ${dot}`} />}
        {title}
      </h2>
      {children}
    </GlassPanel>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-fg-muted">{label}</p>
      <p className="mt-0.5 text-xl font-medium tabular-nums tracking-[-0.01em] text-fg">{value}</p>
    </div>
  );
}

/** Custo por dia (14 dias): barras finas de uma cor, cantos de 4px no topo, valor na dica. */
function DailyBars({ daily }: { daily: Summary["usage"]["daily"] }) {
  const max = Math.max(...daily.map((d) => d.cost), 0);
  return (
    <figure>
      <figcaption className="mb-3 text-xs text-fg-subtle">Custo por dia · últimos 14 dias</figcaption>
      <div className="flex h-28 items-end gap-[2px] border-b border-hairline" role="img" aria-label={`Custo por dia, máximo ${fmtCost(max)}`}>
        {daily.map((d) => (
          <div key={d.day} className="group relative flex h-full flex-1 items-end" title={`${d.day}: ${fmtCost(d.cost)}`}>
            <div
              className="w-full rounded-t-[4px] bg-accent opacity-85 transition-opacity group-hover:opacity-100"
              style={{ height: max > 0 ? `${Math.max(d.cost > 0 ? 3 : 0, (d.cost / max) * 100)}%` : "0%" }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] tabular-nums text-fg-subtle">
        <span>{daily[0]?.day}</span>
        <span>{daily.at(-1)?.day}</span>
      </div>
      <table className="sr-only">
        <caption>Custo por dia</caption>
        <tbody>
          {daily.map((d) => (
            <tr key={d.day}>
              <th>{d.day}</th>
              <td>{fmtCost(d.cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

/** Custo por agente: barras horizontais rotuladas (identidade pelo nome, nao pela cor). */
function AgentBars({ segments }: { segments: Summary["usage"]["segments"] }) {
  return (
    <figure>
      <figcaption className="mb-3 text-xs text-fg-subtle">Custo por agente</figcaption>
      {segments.length === 0 ? (
        <p className="text-sm text-fg-muted">Sem custo registrado no mês.</p>
      ) : (
        <ul className="space-y-2.5">
          {segments.map((sg) => (
            <li key={sg.agent} title={`${agentLabel(sg.agent)}: ${fmtCost(sg.cost)} (${Math.round(sg.share * 100)}%)`}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-fg">{agentLabel(sg.agent)}</span>
                <span className="tabular-nums text-fg-muted">
                  {fmtCost(sg.cost)} · {Math.round(sg.share * 100)}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-chip">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(2, sg.share * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

/** Mapa de calor 7x24: uma cor (destaque), intensidade pela quantidade de tarefas iniciadas na hora. */
function Heatmap({ h }: { h: Summary["heatmap"] }) {
  const peak = h.peak || 1;
  return (
    <figure>
      <div className="grid grid-cols-[2.5rem_1fr] gap-x-2 gap-y-[3px]" role="img" aria-label={`Tarefas por dia da semana e hora; pico de ${h.peak}`}>
        {h.rows.map((row, d) => (
          <div key={d} className="contents">
            <span className="text-[11px] leading-[14px] text-fg-subtle">{h.weekdays[d]}</span>
            <div className="grid grid-cols-24 gap-[3px]" style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}>
              {row.map((n, hour) => (
                <span
                  key={hour}
                  title={`${h.weekdays[d]} ${hour}h: ${n} ${n === 1 ? "tarefa" : "tarefas"}`}
                  className="h-[14px] rounded-[3px]"
                  style={{
                    background: n ? "var(--accent)" : "var(--bg-chip)",
                    opacity: n ? 0.25 + 0.75 * (n / peak) : 1,
                  }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 grid grid-cols-[2.5rem_1fr] gap-x-2 text-[10px] text-fg-subtle">
        <span />
        <div className="flex justify-between font-mono">
          <span>0h</span>
          <span>12h</span>
          <span>23h</span>
        </div>
      </div>
      <figcaption className="mt-3 text-xs text-fg-subtle">
        Tarefas iniciadas por hora{h.peak ? ` (pico: ${h.peak})` : ""}. Mais escuro, mais tarefas.
      </figcaption>
    </figure>
  );
}
