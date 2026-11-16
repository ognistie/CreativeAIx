import { useCallback, useEffect, useState } from "react";
import { cn } from "../lib/cn";
import { core } from "../lib/host";
import { useCoreEvent } from "../lib/useCore";
import { AppDialog, Button, EmptyState, Field, Segmented, Spinner, StatusDot } from "./ui";

// Mudanca de codigo pelo Modo Desenvolvedor (core/dev_mode.py): Claude Code ou Codex trabalham numa copia
// separada (worktree). Voce le o diff, roda o gate (testes) e so entra no app se aplicar; aplicar tem desfazer.
// Usado no Harness (geral) e no AI Research Lab (com o contexto do agente no pedido).

export interface DevProposal {
  id: string;
  tool: string;
  request: string;
  status: string;
  summary: string;
  files: string[];
  gate: { ok: boolean } | null;
}

type Reply = { ok: boolean; error?: string } & Record<string, unknown>;
const call = (p: Promise<unknown>) => p.then((r) => r as Reply).catch((e: Error) => ({ ok: false, error: e.message }) as Reply);

const STATUS: Record<string, string> = {
  proposed: "Proposta pronta",
  checking: "Rodando o gate",
  checked: "Gate concluído",
  gate_failed: "Gate reprovou",
  applied: "Aplicada",
  reverted: "Desfeita",
  discarded: "Descartada",
  failed: "Falhou",
  rejected: "Recusada",
};

export const devStatus = (p: DevProposal) =>
  p.status === "applied" || (p.status === "checked" && p.gate?.ok)
    ? "ok"
    : ["failed", "rejected", "gate_failed"].includes(p.status)
      ? "failed"
      : ["reverted", "discarded"].includes(p.status)
        ? "cancelled"
        : "warn";

export function DevProposals({
  context = "",
  filter,
  placeholder = "Descreva a mudança de código",
}: {
  /** Texto colocado antes do pedido (ex.: qual agente e quais arquivos). */
  context?: string;
  /** Mostra so as propostas cujo pedido contem este texto. */
  filter?: string;
  placeholder?: string;
}) {
  const [items, setItems] = useState<DevProposal[]>([]);
  const [request, setRequest] = useState("");
  const [tool, setTool] = useState<"claude" | "codex">("claude");
  const [progress, setProgress] = useState("");
  const [sending, setSending] = useState(false);
  const [diff, setDiff] = useState<{ id: string; text: string } | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(() => void call(core().call("devList")).then((r) => r.ok && setItems((r.items as DevProposal[]) ?? [])), []);
  useEffect(refresh, [refresh]);
  useCoreEvent(
    "devChanged",
    useCallback(
      (p: unknown) => {
        const e = p as { status: string; message: string };
        setProgress(e.status === "progress" ? e.message : "");
        if (e.status === "error") setError(e.message);
        refresh();
      },
      [refresh],
    ),
  );

  const act = async (id: string, action: string) => {
    const r = await call(core().call("devAct", id, action));
    if (!r.ok) setError(r.error || "");
    refresh();
  };

  const send = async () => {
    setError("");
    setSending(true);
    const r = await call(core().call("devPropose", context ? `${context}\n\n${request.trim()}` : request.trim(), tool));
    setSending(false);
    if (!r.ok) setError(r.error || "Não deu para pedir a mudança.");
    else setRequest("");
  };

  const shown = filter ? items.filter((p) => p.request.includes(filter)) : items;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Field
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && request.trim().length >= 5 && !sending && void send()}
          placeholder={placeholder}
          className="min-w-[260px] flex-1"
          aria-label="Mudança de código"
        />
        <Segmented
          label="Ferramenta"
          value={tool}
          onValueChange={setTool}
          options={[
            { value: "claude", label: "Claude Code" },
            { value: "codex", label: "Codex" },
          ]}
        />
        <Button variant="primary" icon="code" disabled={request.trim().length < 5 || sending} onClick={() => void send()}>
          {sending ? <Spinner size={12} /> : null} Pedir mudança
        </Button>
      </div>
      {progress && (
        <p className="mt-2 flex items-center gap-2 text-sm text-fg-muted" role="status">
          <Spinner size={12} /> {progress}
        </p>
      )}
      {error && <p className="mt-2 rounded-r2 bg-bad/10 p-2.5 text-sm text-bad-ink">{error}</p>}
      {shown.length === 0 ? (
        <EmptyState icon="code" title="Nenhuma proposta de código ainda">
          Peça uma mudança acima. Ela é feita numa cópia separada; nada muda no app até você aplicar.
        </EmptyState>
      ) : (
        <ul className="mt-4 space-y-2">
          {shown.map((p) => (
            <li key={p.id} className="rounded-r3 border border-hairline bg-surface/40 p-3 text-sm">
              <p className="flex items-start gap-2 text-fg">
                <StatusDot status={devStatus(p)} size={13} />
                <span className="min-w-0 flex-1 whitespace-pre-line">{p.request.replace(context, "").trim()}</span>
                <span className="shrink-0 rounded-full bg-chip px-2 py-0.5 text-xs text-fg-muted">
                  {p.tool === "codex" ? "Codex" : "Claude Code"} · {STATUS[p.status] ?? p.status}
                </span>
              </p>
              {p.summary && <p className="mt-1.5 text-fg-muted">{p.summary}</p>}
              {p.files.length > 0 && (
                <p className="mt-1.5 flex flex-wrap gap-1">
                  {p.files.map((f) => (
                    <span key={f} className="rounded-[4px] bg-chip px-1.5 py-0.5 font-mono text-[11px] text-fg-muted">
                      {f}
                    </span>
                  ))}
                </p>
              )}
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                <Button
                  size="compact"
                  variant="ghost"
                  icon="file-text"
                  onClick={async () => {
                    const r = await call(core().call("devDiff", p.id));
                    if (r.ok) setDiff({ id: p.id, text: String(r.diff ?? "") });
                  }}
                >
                  Ver diff
                </Button>
                {(p.status === "proposed" || p.status === "gate_failed") && (
                  <Button size="compact" icon="shield-check" onClick={() => void core().call("devCheck", p.id)}>
                    Rodar o gate
                  </Button>
                )}
                {p.status === "checked" && p.gate?.ok && (
                  <Button size="compact" variant="primary" icon="check" onClick={() => void act(p.id, "apply")}>
                    Aplicar
                  </Button>
                )}
                {p.status === "applied" && (
                  <Button size="compact" icon="undo" onClick={() => void act(p.id, "undo")}>
                    Desfazer
                  </Button>
                )}
                {!["applied", "reverted", "discarded"].includes(p.status) && (
                  <Button size="compact" variant="ghost" icon="trash" onClick={() => void act(p.id, "discard")}>
                    Descartar
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <AppDialog open={!!diff} onOpenChange={(o) => !o && setDiff(null)} title="Diff da proposta">
        <DiffView text={diff?.text ?? ""} />
        <div className="mt-4 flex justify-end">
          <Button icon="x" onClick={() => setDiff(null)}>
            Fechar
          </Button>
        </div>
      </AppDialog>
    </div>
  );
}

/** Diff unificado com linhas coloridas (+ verde, - vermelho), legivel nos dois temas. */
function DiffView({ text }: { text: string }) {
  if (!text.trim()) return <p className="text-sm text-fg-muted">Sem diferenças.</p>;
  return (
    <pre className="max-h-[60vh] select-text overflow-auto rounded-r2 border border-hairline bg-surface p-3 font-mono text-[12px] leading-relaxed">
      {text.split("\n").map((l, i) => (
        <div
          key={i}
          className={cn(
            "px-1",
            l.startsWith("+") && !l.startsWith("+++") && "bg-ok/10 text-fg",
            l.startsWith("-") && !l.startsWith("---") && "bg-bad/10 text-fg",
            (l.startsWith("@@") || l.startsWith("diff ")) && "text-accent-ink",
            !/^[+\-@d]/.test(l) && "text-fg-muted",
          )}
        >
          {l || " "}
        </div>
      ))}
    </pre>
  );
}
