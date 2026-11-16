import { memo, useEffect, useMemo, useState } from "react";
import { DevProposals } from "../../components/DevProposals";
import { Button, Field, GlassPanel, Icon, Skeleton, Spinner } from "../../components/ui";
import { cn } from "../../lib/cn";
import { core } from "../../lib/host";
import { call, type Spec } from "./types";

// Codigo do agente: leitura dos arquivos que o definem (lista fechada no nucleo) e mudancas pelo Modo
// Desenvolvedor — Claude Code ou Codex numa copia separada, com diff, gate de testes e desfazer.
// O app nao grava codigo direto desta tela: cada mudanca e revisada antes de entrar.

export function AgentCode({ agent, name, files }: { agent: string; name: string; files: Spec["files"] }) {
  const own = files.filter((f) => !f.shared);
  const shared = files.filter((f) => f.shared);
  const [path, setPath] = useState(own[0]?.path ?? files[0]?.path ?? "");
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [find, setFind] = useState("");
  const [codeOn, setCodeOn] = useState<boolean | null>(null);
  const [enabling, setEnabling] = useState(false);

  useEffect(() => {
    if (!path) return;
    setText(null);
    setError("");
    void call(core().call("studioSource", agent, path)).then((r) => (r.ok ? setText((r.file as { text: string }).text) : setError(r.error || "Não deu para abrir.")));
  }, [agent, path]);

  useEffect(() => {
    void call(core().call("harnessGet")).then((r) => r.ok && setCodeOn(!!(r.harness as { dev?: { code_changes?: boolean } }).dev?.code_changes));
  }, []);

  const enable = async () => {
    setEnabling(true);
    const r = await call(core().call("harnessGet"));
    if (r.ok) {
      const h = r.harness as { dev: Record<string, unknown> };
      h.dev = { ...h.dev, enabled: true, code_changes: true };
      const s = await call(core().call("harnessSave", JSON.stringify(h), "Mudanças de código ligadas"));
      if (s.ok) setCodeOn(true);
      else setError(s.error || "Não deu para ligar.");
    }
    setEnabling(false);
  };

  const context = `[Agente ${name}] Arquivos principais: ${own.map((f) => f.path).join(", ")}.`;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 xl:grid-cols-[250px_minmax(0,1fr)] [&>*]:min-w-0">
        <GlassPanel className="p-3">
          <FileGroup title="Deste agente" files={own} path={path} onPick={setPath} />
          {shared.length > 0 && <FileGroup title="Compartilhados" files={shared} path={path} onPick={setPath} />}
        </GlassPanel>

        <GlassPanel className="min-w-0 overflow-hidden p-0">
          <div className="flex flex-wrap items-center gap-2 border-b border-hairline px-4 py-2.5">
            <Icon name="file" size={14} className="text-fg-muted" />
            <span className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-fg">app/{path}</span>
            <span className="flex items-center gap-1 rounded-full bg-chip px-2 py-0.5 text-xs text-fg-muted">
              <Icon name="lock" size={11} /> Só leitura
            </span>
            <Field value={find} onChange={(e) => setFind(e.target.value)} placeholder="Destacar no arquivo" aria-label="Destacar texto no arquivo" className="h-7 w-48 text-xs" />
          </div>
          {error ? (
            <p className="p-4 text-sm text-bad-ink">{error}</p>
          ) : text === null ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className={cn("h-3.5 rounded", ["w-2/5", "w-3/4", "w-1/2", "w-5/6", "w-2/3", "w-1/3"][i])} />
              ))}
            </div>
          ) : (
            <CodeView text={text} find={find} />
          )}
        </GlassPanel>
      </div>

      <GlassPanel className="p-5">
        <h3 className="flex items-center gap-2 text-md font-semibold text-fg">
          <Icon name="code" size={16} className="text-fg-muted" /> Mudar o código de {name}
        </h3>
        <p className="mt-1 max-w-3xl text-sm text-fg-muted">
          Descreva a mudança. O Claude Code ou o Codex trabalha numa cópia separada do projeto; você lê o diff, roda os testes (gate) e só então aplica. Dá
          para desfazer depois.
        </p>
        <div className="mt-4">
          {codeOn === null ? (
            <Spinner />
          ) : codeOn ? (
            <DevProposals context={context} filter={`[Agente ${name}]`} placeholder={`Ex.: no ${name}, registrar o tempo de cada passo no log`} />
          ) : (
            <div className="flex flex-wrap items-center gap-3 rounded-r3 border border-dashed border-hairline-hi p-4">
              <Icon name="lock" size={18} className="text-fg-muted" />
              <p className="min-w-0 flex-1 text-sm text-fg">
                Mudanças de código estão desligadas. Ao ligar, você poderá pedir alterações revisadas; nada é aplicado sem você.
              </p>
              <Button variant="primary" icon="shield-check" disabled={enabling} onClick={() => void enable()}>
                {enabling ? <Spinner size={12} /> : null} Ligar mudanças de código
              </Button>
            </div>
          )}
        </div>
      </GlassPanel>
    </div>
  );
}

function FileGroup({ title, files, path, onPick }: { title: string; files: Spec["files"]; path: string; onPick: (p: string) => void }) {
  return (
    <div className="mb-2 last:mb-0">
      <p className="px-2 pb-1.5 pt-1 text-xs font-medium uppercase tracking-[0.08em] text-fg-muted">{title}</p>
      <ul className="space-y-0.5">
        {files.map((f) => {
          const on = f.path === path;
          return (
            <li key={f.path}>
              <button
                type="button"
                aria-current={on ? "true" : undefined}
                title={f.doc || f.path}
                onClick={() => onPick(f.path)}
                className={cn("flex w-full items-center gap-2 rounded-r2 px-2 py-1.5 text-left transition-colors", on ? "bg-row-hover" : "hover:bg-hover")}
              >
                <Icon name="file-text" size={13} className="shrink-0 text-fg-muted" />
                <span className={cn("min-w-0 flex-1 truncate font-mono text-[12px]", on ? "text-fg" : "text-fg-muted")}>{f.path.split("/").pop()}</span>
                <span className="shrink-0 text-[11px] tabular-nums text-fg-muted">{f.lines}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Realce simples de Python (palavra-chave, texto, comentario, numero): leve, sem biblioteca.
const KW = /\b(def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|with|try|except|finally|raise|yield|lambda|None|True|False|pass|break|continue|async|await|is|global|nonlocal)\b/g;

function highlight(line: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /(#.*$)|("""|''')|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?\b)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  const kw = (s: string, key: string) => {
    const parts: React.ReactNode[] = [];
    let i = 0;
    for (const k of s.matchAll(KW)) {
      parts.push(s.slice(i, k.index));
      parts.push(
        <span key={`${key}-${k.index}`} className="text-[var(--code-kw)]">
          {k[0]}
        </span>,
      );
      i = (k.index ?? 0) + k[0].length;
    }
    parts.push(s.slice(i));
    return parts;
  };
  while ((m = re.exec(line))) {
    out.push(...kw(line.slice(last, m.index), `k${last}`));
    const cls = m[1] ? "text-[var(--code-comment)] italic" : m[2] || m[3] ? "text-[var(--code-str)]" : "text-[var(--code-num)]";
    out.push(
      <span key={m.index} className={cls}>
        {m[0]}
      </span>,
    );
    last = m.index + m[0].length;
  }
  out.push(...kw(line.slice(last), `k${last}e`));
  return out;
}

const CodeView = memo(function CodeView({ text, find }: { text: string; find: string }) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const q = find.trim().toLowerCase();
  const hits = useMemo(() => (q.length >= 2 ? lines.reduce((n, l) => n + (l.toLowerCase().includes(q) ? 1 : 0), 0) : 0), [lines, q]);
  return (
    <div className="relative">
      {q.length >= 2 && <p className="border-b border-hairline px-4 py-1.5 text-xs text-fg-muted">{hits} linha(s) com “{find}”</p>}
      <pre className="max-h-[62vh] select-text overflow-auto py-2 font-mono text-[12.5px] leading-[1.6] text-fg">
        {lines.map((l, i) => {
          const hit = q.length >= 2 && l.toLowerCase().includes(q);
          return (
            <div key={i} className={cn("flex", hit && "bg-accent/15")}>
              <span aria-hidden className="w-12 shrink-0 select-none pr-3 text-right tabular-nums text-fg-subtle/70">
                {i + 1}
              </span>
              <code className="whitespace-pre pr-6">{highlight(l)}</code>
            </div>
          );
        })}
      </pre>
    </div>
  );
});
