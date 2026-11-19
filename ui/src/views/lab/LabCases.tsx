import { useState } from "react";
import { Button, Field, GlassPanel } from "../../components/ui";
import { core, saveLabDocument } from "../../lib/host";

export type EvalCase = {
  id: string;
  task: string;
  split?: "development" | "holdout";
  risk?: "safe" | "requires_approval" | "prohibited";
  setup?: Record<string, string>;
  expect: Record<string, unknown>;
  context?: string;
};
export type EvalSet = { name: string; agent: string; title: string; version: number; hash: string; cases: EvalCase[] };
type Revision = { version: number; hash: string };
type DatasetReply = { ok?: boolean; error?: string; set?: EvalSet; revisions?: Revision[] };
const emptyCase = (): EvalCase => ({ id: "", task: "", split: "development", risk: "safe", expect: {} });
const empty = (agent: string): EvalSet => ({ name: "", agent, title: "", version: 0, hash: "", cases: [emptyCase()] });

export function LabCases({ agent, selection, onChange, onClose }: {
  agent: string;
  selection?: EvalSet;
  onChange: (set: EvalSet) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(() => structuredClone(selection ?? empty(agent)));
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(0);
  const [historical, setHistorical] = useState<EvalSet | null>(null);
  const current = draft.cases[editing];
  const title = historical ? `Revisão ${historical.version}` : "Casos de teste";
  const patch = (change: Partial<EvalCase>) => {
    setDraft((row) => ({ ...row, cases: row.cases.map((item, i) => i === editing ? { ...item, ...change } : item) }));
  };
  const request = async (data: object) => {
    const reply = await core().call("labDataset", JSON.stringify(data)) as DatasetReply;
    if (!reply?.ok || !reply.set) throw new Error(reply?.error || "O núcleo não concluiu a operação.");
    return { set: reply.set, revisions: reply.revisions ?? [] };
  };
  const act = async (fn: () => Promise<void>) => {
    setMessage("");
    setSaving(true);
    try { await fn(); } catch (error) { setMessage((error as Error).message); }
    finally { setSaving(false); }
  };
  const save = () => act(async () => {
    const reply = await request({ ...draft, action: "save", expected: draft.hash || "new" });
    setDraft(reply.set);
    setRevisions(reply.revisions);
    onChange(reply.set);
    setMessage(`Revisão ${reply.set.version} salva.`);
  });
  const load = (hash = "") => act(async () => {
    const reply = await request({ action: "read", name: draft.name, revision: hash });
    setRevisions(reply.revisions);
    if (!hash) {
      setDraft(reply.set);
      setEditing(0);
      setHistorical(null);
    } else {
      setHistorical(reply.set);
    }
  });
  const importCaseSet = (file?: File) => {
    if (!file) return;
    void act(async () => {
      if (file.size > 256 * 1024) throw new Error("Use um arquivo JSON de até 256 KiB.");
      const parsed = JSON.parse(await file.text()) as Partial<EvalSet>;
      if (parsed.agent !== agent || !Array.isArray(parsed.cases) || typeof parsed.name !== "string"
          || !parsed.cases.length || parsed.cases.some((item) => !item || typeof item !== "object" || !item.expect
          || Array.isArray(item.expect) || typeof item.expect !== "object" || typeof item.task !== "string" || typeof item.id !== "string")) {
        throw new Error("Escolha um arquivo de casos válido para este agente.");
      }
      const validated = await core().call("labDataset", JSON.stringify({ action: "validate", agent, name: parsed.name, cases: parsed.cases })) as DatasetReply;
      if (!validated?.ok) throw new Error(validated?.error || "O conjunto não passou pela validação.");
      setDraft({ ...empty(agent), name: parsed.name, title: typeof parsed.title === "string" ? parsed.title : "", cases: parsed.cases });
      setEditing(0);
      setHistorical(null);
      setMessage("Revise os casos importados e salve como um conjunto.");
    });
  };

  return <GlassPanel className="space-y-4 p-5">
    <header className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-md font-semibold text-fg">{title}</h3>
      <div className="flex flex-wrap gap-2">
        <Button size="compact" disabled={saving} onClick={() => {
          setDraft(empty(agent)); setHistorical(null); setRevisions([]); setEditing(0); setMessage("");
        }}>Novo conjunto</Button>
        <Button size="compact" onClick={onClose}>Voltar à comparação</Button>
      </div>
    </header>
    <p className="text-sm text-fg-muted">Use tarefas, arquivos e valores sintéticos. Os casos reservados servem para confirmar o resultado final.</p>
    {message && <p className="text-sm text-fg" role="status">{message}</p>}
    <fieldset disabled={saving} className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="grid gap-1 text-sm text-fg-muted">Identificador
          <Field value={draft.name} readOnly={draft.version > 0} placeholder="arquivos-teste" maxLength={64}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </label>
        <label className="grid gap-1 text-sm text-fg-muted">Título
          <Field value={draft.title} maxLength={80} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        <label className="inline-flex cursor-pointer items-center rounded-full border border-hairline px-3 text-sm text-fg">
          Importar casos <input type="file" className="ml-2 max-w-48 text-xs" accept=".json,application/json"
            aria-label="Importar casos JSON" onChange={(e) => { importCaseSet(e.target.files?.[0]); e.currentTarget.value = ""; }} />
        </label>
        <Button size="compact" onClick={() => void act(async () => {
          const row = historical ?? draft;
          const { name, title, cases } = row;
          await saveLabDocument(`lab-casos-${/^[a-z0-9-]{1,64}$/.test(name) ? name : "rascunho"}.json`, JSON.stringify({ name, title, agent, cases }, null, 2));
        })}>Exportar casos</Button>
        {draft.version > 0 && <Button size="compact" onClick={() => void load()}>Ver revisões</Button>}
      </div>
      {revisions.length > 0 && <div className="flex flex-wrap gap-2">
        {revisions.map((row) => <Button key={row.hash} size="compact" onClick={() => void load(row.hash)}>Ver v{row.version}</Button>)}
      </div>}
      {historical ? <div className="space-y-2 rounded-r3 border border-hairline p-3">
        <p className="text-sm text-fg">Revisão {historical.version} · {historical.cases.length} casos · {historical.hash.slice(0, 12)}</p>
        <ul className="space-y-1 text-sm text-fg-muted">{historical.cases.map((row) => <li key={row.id}>{row.id} · {row.task}</li>)}</ul>
        <Button size="compact" variant="primary" onClick={() => { onChange(historical); onClose(); }}>Usar esta revisão na comparação</Button>
        <Button className="ml-2" size="compact" onClick={() => setHistorical(null)}>Voltar à edição</Button>
      </div> : <>
        <div className="flex flex-wrap gap-2">
          {draft.cases.map((item, i) => <Button key={i} size="compact" aria-pressed={editing === i} variant={editing === i ? "primary" : "secondary"}
            onClick={() => setEditing(i)}>{item.id || `Caso ${i + 1}`}</Button>)}
          <Button size="compact" icon="plus" disabled={draft.cases.length >= 24} onClick={() => {
            setEditing(draft.cases.length); setDraft({ ...draft, cases: [...draft.cases, emptyCase()] });
          }}>Adicionar caso</Button>
        </div>
        {current && <div key={editing} className="space-y-3 rounded-r3 border border-hairline p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <label className="grid gap-1 text-sm text-fg-muted">ID do caso
              <Field value={current.id} maxLength={64} onChange={(e) => patch({ id: e.target.value })} />
            </label>
            <label className="grid gap-1 text-sm text-fg-muted">Grupo
              <select className={fieldStyle} value={current.split ?? "development"} onChange={(e) => patch({ split: e.target.value as EvalCase["split"] })}>
                <option value="development">Desenvolvimento</option><option value="holdout">Validação reservada</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-fg-muted">Risco
              <select className={fieldStyle} value={current.risk ?? "safe"} onChange={(e) => patch({ risk: e.target.value as EvalCase["risk"] })}>
                <option value="safe">Seguro</option><option value="requires_approval">Exige aprovação</option><option value="prohibited">Proibido</option>
              </select>
            </label>
          </div>
          <Text label={agent === "FILE" ? "Pedido (use {ws} para a pasta de teste)" : "Pedido"} value={current.task}
            onChange={(task) => patch({ task })} />
          <Text label="Contexto sintético (opcional)" value={current.context ?? ""} onChange={(context) => patch({ context })} />
          <Expectations agent={agent} row={current} onChange={patch} />
          <Button size="compact" variant="danger" disabled={draft.cases.length === 1} onClick={() => {
            setDraft({ ...draft, cases: draft.cases.filter((_, i) => i !== editing) }); setEditing(Math.max(0, editing - 1));
          }}>Remover caso</Button>
        </div>}
        <Button variant="primary" disabled={!draft.name.trim()} onClick={() => void save()}>Salvar revisão</Button>
      </>}
    </fieldset>
  </GlassPanel>;
}

const fieldStyle = "min-w-0 rounded-r2 border border-hairline bg-surface px-2 py-2 text-sm text-fg";

function Text({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="grid gap-1 text-sm text-fg-muted">
    {label}<textarea className={fieldStyle} value={value} rows={2} onChange={(e) => onChange(e.target.value)} />
  </label>;
}

const lines = (value: string) => value.split(/\r?\n/).map((v) => v.trim()).filter(Boolean);

function entries(value: string) {
  return lines(value).flatMap((line) => {
    const eq = line.indexOf("=");
    return eq < 1 ? [] : [[line.slice(0, eq).trim(), line.slice(eq + 1)] as const];
  });
}

function mapText(value: unknown) {
  return value && typeof value === "object"
    ? Object.entries(value).map(([name, text]) => `${name}=${typeof text === "string" && !text.includes("\n") ? text : JSON.stringify(text)}`).join("\n")
    : "";
}

function EntryText({ label, value, save }: { label: string; value: unknown; save: (value: string) => void }) {
  const [text, setText] = useState(() => mapText(value));
  return <Text label={label} value={text} onChange={(next) => { setText(next); save(next); }} />;
}

function Expectations({ agent, row, onChange }: { agent: string; row: EvalCase; onChange: (row: Partial<EvalCase>) => void }) {
  const expect = row.expect;
  const set = (key: string, value: unknown) => onChange({ expect: { ...expect, [key]: value } });
  const parseString = (value: string) => {
    try { return value.startsWith('"') ? String(JSON.parse(value)) : value; } catch { return value; }
  };
  const strings = (value: string) => Object.fromEntries(entries(value).map(([key, val]) => [key, parseString(val)]));
  if (agent === "FILE") return <div className="grid gap-3 md:grid-cols-2">
    <EntryText label="Arquivos iniciais (nome=conteúdo)" value={row.setup} save={(value) => onChange({ setup: strings(value) })} />
    <TextList label="Caminhos que devem existir (um por linha)" value={expect.exists} onChange={(value) => set("exists", value)} />
    <TextList label="Caminhos que devem estar ausentes" value={expect.absent} onChange={(value) => set("absent", value)} />
    <EntryText label="Conteúdo esperado (nome=trecho)" value={expect.contains} save={(value) => set("contains", strings(value))} />
    <label className="flex items-center gap-2 text-sm text-fg"><input type="checkbox" checked={expect.blocked_or_inside === true}
      onChange={(e) => set("blocked_or_inside", e.target.checked)} /> Conferir limites da pasta</label>
  </div>;
  if (agent === "MAESTRO") return <>
    <TextList label="Agentes na ordem esperada (um por linha)" value={expect.agents} onChange={(value) => set("agents", value)} />
    <label className="flex items-center gap-2 text-sm text-fg"><input type="checkbox" checked={expect.clarify === true}
      onChange={(e) => onChange({ expect: { agents: expect.agents ?? [], clarify: e.target.checked } })} /> Deve pedir esclarecimento</label>
  </>;
  if (agent === "CODE") return <EntryText label="Arquivos esperados (nome=trecho)" value={expect.files} save={(value) => set("files", strings(value))} />;
  const sheets = (expect.sheets ?? {}) as Record<string, Record<string, unknown>>;
  const cells = Object.fromEntries(Object.entries(sheets).flatMap(([title, values]) =>
    Object.entries(values).map(([address, value]) => [`${title}!${address}`, value])));
  return <EntryText label="Células esperadas (Aba!A1=valor)" value={cells} save={(value) => {
    const next: Record<string, Record<string, unknown>> = Object.create(null);
    for (const [key, raw] of entries(value)) {
      const [sheet, address] = key.split("!");
      if (!sheet || !address) continue;
      let parsed: unknown = raw;
      try { parsed = JSON.parse(raw); } catch { /* Texto ou fórmula. */ }
      (next[sheet] ??= Object.create(null))[address] = parsed;
    }
    set("sheets", next);
  }} />;
}

function TextList({ label, value, onChange }: { label: string; value: unknown; onChange: (rows: string[]) => void }) {
  const [text, setText] = useState(Array.isArray(value) ? value.join("\n") : "");
  return <Text label={label} value={text} onChange={(next) => { setText(next); onChange(lines(next)); }} />;
}
